#!/usr/bin/env python3
"""Native HDMI display receiver - GStreamer WebRTC + kmssink (no browser)."""
import asyncio, json, logging, os, re, socket, subprocess, sys, threading, time
import websockets

logging.basicConfig(level=logging.INFO, format="[HDMI] %(message)s")
log = logging.getLogger(__name__)

import gi
gi.require_version('Gst', '1.0')
gi.require_version('GstWebRTC', '1.0')
gi.require_version('GstSdp', '1.0')
from gi.repository import Gst, GstWebRTC, GstSdp

Gst.init(None)

# Keep the known RK3588 baseline while allowing per-device overrides.  The
# board may be connected to a different DRM output/mode during development.
DISPLAY_W = int(os.environ.get("SCREENCAST_DISPLAY_WIDTH", "1024"))
DISPLAY_H = int(os.environ.get("SCREENCAST_DISPLAY_HEIGHT", "600"))
PLANE_ID = int(os.environ.get("SCREENCAST_KMS_PLANE_ID", "71"))
LAN_H264_MIN_KBPS = int(os.environ.get("SCREENCAST_LAN_H264_MIN_KBPS", "10500"))
LAN_H264_START_KBPS = int(os.environ.get("SCREENCAST_LAN_H264_START_KBPS", "19500"))
LAN_H264_MAX_KBPS = int(os.environ.get("SCREENCAST_LAN_H264_MAX_KBPS", "30000"))


class NativeReceiver:
    def __init__(self, sid, ws_url):
        self.sid = sid
        self.ws_url = ws_url
        self.pipe = None
        self.webrtc = None
        self.ws = None
        self.loop = None
        self.pending_msgs = []
        self.running = True
        self._decode_elems = []
        self._ice_queue = []       # 缓存 set-remote-description 完成前的 ICE
        self._remote_desc_set = False
        self._sender_ip = ""
        self._frame_stats_lock = threading.Lock()
        self._frame_stats_started = time.monotonic()
        self._frames_decoded = 0
        self._frames_presented = 0

    def _note_frame(self, stage):
        """Count decode/display buffers without adding another media queue."""
        with self._frame_stats_lock:
            if stage == "decoded":
                self._frames_decoded += 1
            else:
                self._frames_presented += 1
            elapsed = time.monotonic() - self._frame_stats_started
            if elapsed >= 3.0:
                log.info("FrameStats: decoded=%d (%.1ffps) presented=%d (%.1ffps)",
                         self._frames_decoded, self._frames_decoded / elapsed,
                         self._frames_presented, self._frames_presented / elapsed)
                self._frame_stats_started = time.monotonic()
                self._frames_decoded = 0
                self._frames_presented = 0

    def _on_decoded_buffer(self, _pad, _info):
        self._note_frame("decoded")
        return Gst.PadProbeReturn.OK

    def _on_presented_buffer(self, _pad, _info):
        self._note_frame("presented")
        return Gst.PadProbeReturn.OK

    @staticmethod
    def _with_lan_h264_bitrate_hints(sdp_text):
        """Put Chromium LAN bitrate hints in the receiver's SDP answer.

        GStreamer 1.16 does not provide Chrome with a useful initial video
        bandwidth estimate on every build.  These answer-side H.264 fmtp
        hints prevent Chrome from immediately downscaling a clean LAN stream
        to sub-Mbps. RTCP feedback remains free to lower bitrate if needed.
        """
        changed = 0
        lines = []
        for line in sdp_text.splitlines():
            if line.startswith("a=fmtp:") and "profile-level-id=" in line.lower():
                line = re.sub(r";x-google-(?:min|start|max)-bitrate=\d+", "", line,
                              flags=re.IGNORECASE)
                line += (";x-google-min-bitrate=%d;x-google-start-bitrate=%d;"
                         "x-google-max-bitrate=%d" % (
                             LAN_H264_MIN_KBPS, LAN_H264_START_KBPS,
                             LAN_H264_MAX_KBPS))
                changed += 1
            lines.append(line)
        return "\r\n".join(lines) + "\r\n", changed

    def _send_signaling(self, msg):
        if self.loop and not self.loop.is_closed():
            self.loop.call_soon_threadsafe(self._do_send, msg)
        else:
            self.pending_msgs.append(msg)

    def _do_send(self, msg):
        asyncio.ensure_future(self._async_send(msg))

    async def _async_send(self, msg):
        try:
            # websockets 15 ClientConnection no longer exposes ``closed``;
            # send and let the connection exception handle a concurrent close.
            if self.ws:
                await self.ws.send(json.dumps(msg))
        except Exception as e:
            log.warning("WS send failed: %s", e)

    def _on_ice_candidate(self, element, mline_index, candidate):
        log.info("ICE candidate: %s", (candidate or "null")[:60])
        self._send_signaling({
            "t": "ice", "s": self.sid,
            "c": candidate, "m": "", "l": mline_index
        })

    def _create_pipeline(self):
        self.pipe = Gst.Pipeline.new("hdmi-receiver")
        self.webrtc = Gst.ElementFactory.make("webrtcbin", "recv")
        self.webrtc.set_property("bundle-policy", "max-bundle")
        # GStreamer 1.16 does not expose the jitterbuffer latency property on
        # every webrtcbin build.  Set it when available and also tune any
        # dynamically-created rtpjitterbuffer in _on_deep_element_added.
        if self.webrtc.find_property("latency"):
            self.webrtc.set_property("latency", 80)
        self.webrtc.connect("deep-element-added", self._on_deep_element_added)
        self.pipe.add(self.webrtc)
        self.webrtc.connect("on-ice-candidate", self._on_ice_candidate)
        self.webrtc.connect("pad-added", self._on_pad_added)

    def _on_deep_element_added(self, _bin, _sub_bin, element):
        """Keep WebRTC's RTP jitterbuffer bounded for interactive display."""
        try:
            factory = element.get_factory()
            name = factory.get_name() if factory else ""
            if name == "rtpjitterbuffer":
                if element.find_property("latency"):
                    element.set_property("latency", 80)
                if element.find_property("drop-on-latency"):
                    # RTP H.264 packets contain reference frames. Dropping a
                    # late compressed packet corrupts the following GOP and
                    # is worse than adding a bounded 80 ms of jitter delay.
                    element.set_property("drop-on-latency", False)
                if element.find_property("faststart-min-packets"):
                    element.set_property("faststart-min-packets", 1)
                log.info("Low-latency RTP jitterbuffer enabled")
        except Exception as exc:
            log.debug("Unable to tune RTP jitterbuffer: %s", exc)

    @staticmethod
    def _make_decoder(encoding):
        """Use an installed hardware decoder, otherwise a tuned software one."""
        candidates = {
            # ``mppvideodec`` is the modern Rockchip MPP element.  It is a
            # multi-codec decoder and is supplied by libgstrockchipmpp.so.
            # Keep the older per-codec factory names for vendor images that
            # ship a different Rockchip plugin, then retain software fallback.
            "H264": ("mppvideodec", "rkmpph264dec", "v4l2h264dec", "avdec_h264"),
            "H265": ("mppvideodec", "rkmpph265dec", "v4l2h265dec", "avdec_h265"),
            "VP8": ("mppvideodec", "vp8dec", "avdec_vp8"),
            "VP9": ("mppvideodec", "vp9dec", "avdec_vp9"),
        }.get(encoding, ())
        preference = os.getenv("SCREENCAST_VIDEO_DECODER", "auto").lower()
        if preference == "software":
            candidates = tuple(name for name in candidates if name.startswith("avdec_"))
        elif preference == "hardware":
            candidates = tuple(name for name in candidates if not name.startswith("avdec_"))
        for factory_name in candidates:
            decoder = Gst.ElementFactory.make(factory_name, None)
            if decoder:
                if factory_name.startswith("vp8") and decoder.find_property("threads"):
                    decoder.set_property("threads", 4)
                if factory_name.startswith("vp8") and decoder.find_property("post-processing"):
                    decoder.set_property("post-processing", False)
                if factory_name.startswith("avdec") and decoder.find_property("max-threads"):
                    decoder.set_property("max-threads", 4)
                log.info("Decoder selected: %s", factory_name)
                return decoder
        return None

    @staticmethod
    def _make_live_queue(name):
        queue = Gst.ElementFactory.make("queue", name)
        if queue:
            queue.set_property("max-size-buffers", 1)
            queue.set_property("max-size-bytes", 0)
            queue.set_property("max-size-time", 0)
            queue.set_property("leaky", 2)  # downstream: drop stale frames
        return queue

    def _cleanup_decode_chain(self):
        for e in self._decode_elems:
            try:
                e.set_state(Gst.State.NULL)
                self.pipe.remove(e)
            except Exception:
                pass
        self._decode_elems = []

    def _on_pad_added(self, element, pad):
        log.info("PAD_ADDED: name=%s", pad.name)
        if not pad.name.startswith("src_"):
            return

        try:
            src_caps = pad.query_caps(None)
            s = src_caps.get_structure(0)
            encoding = s.get_string("encoding-name") if s.has_field("encoding-name") else ""
            log.info("Stream encoding: %s", encoding)

            self._cleanup_decode_chain()

            depay = parser = codec_caps = dec = render_queue = conv = scale = capsf = sink = None
            if encoding == "H264":
                depay = Gst.ElementFactory.make("rtph264depay", None)
                # MPP requires access units with the ``parsed`` caps flag.
                # h264parse does this without adding a frame queue.
                parser = Gst.ElementFactory.make("h264parse", None)
            elif encoding == "H265":
                depay = Gst.ElementFactory.make("rtph265depay", None)
                parser = Gst.ElementFactory.make("h265parse", None)
            elif encoding == "VP8":
                depay = Gst.ElementFactory.make("rtpvp8depay", None)
            elif encoding == "VP9":
                depay = Gst.ElementFactory.make("rtpvp9depay", None)
            else:
                log.error("Unsupported codec: %s", encoding)
                return

            dec = self._make_decoder(encoding)
            render_queue = self._make_live_queue("render-q")

            sink = Gst.ElementFactory.make("kmssink", None)
            # The RK MPP decoder exports NV12.  On this board's Esmart KMS
            # plane, an NV12 DMA buffer may negotiate successfully yet never
            # produce a DRM framebuffer.  The standby renderer's RGB path is
            # proven on the same plane, so make the final scanout buffer BGRx
            # by default.  MPP still performs the expensive decode in
            # hardware; only the final display conversion is CPU-side.
            # ARGB is advertised by this BSP's KMS plane but doesn't produce
            # scanout frames through kmssink. BGRx is the verified working
            # path; alpha blending is handled separately by plane properties.
            render_format = os.getenv("SCREENCAST_RENDER_FORMAT", "BGRx")
            if render_format.lower() in ("native", "nv12", "auto"):
                render_format = ""
            # Native mode retains the MPP decoder's NV12 buffer up to the RK
            # overlay plane. This zero-copy fast path avoids a full CPU core
            # being spent on the final NV12 -> BGRx conversion.
            if render_format:
                conv = Gst.ElementFactory.make("videoconvert", None)
            if render_format:
                capsf = Gst.ElementFactory.make("capsfilter", None)
            force_software_scale = os.getenv("SCREENCAST_SOFTWARE_SCALE", "0").lower() in ("1", "true", "yes")
            if force_software_scale:
                scale = Gst.ElementFactory.make("videoscale", None)
            if not all([depay, dec, render_queue, sink]) or (render_format and not conv) or (encoding in ("H264", "H265") and not parser) or (force_software_scale and not scale) or (render_format and not capsf):
                log.error("Missing elements for %s", encoding)
                return

            if parser and parser.find_property("config-interval"):
                # Keep parameter sets with every IDR so a receiver that
                # joins/reconnects can decode immediately.
                parser.set_property("config-interval", -1)

            if parser:
                # Browser WebRTC normally carries H.264 as AVC/avcC.  The
                # RK MPP plugin advertises AVC support, but on this BSP it
                # accepts the sequence header and then emits no frames from
                # live avcC input.  Feed its proven Annex-B path instead.
                codec_caps = Gst.ElementFactory.make("capsfilter", None)
                if not codec_caps:
                    log.error("Missing codec capsfilter for %s", encoding)
                    return
                codec_name = "video/x-h264" if encoding == "H264" else "video/x-h265"
                codec_caps.set_property("caps", Gst.Caps.from_string(
                    "%s,stream-format=byte-stream,alignment=au" % codec_name
                ))

            sink.set_property("plane-id", PLANE_ID)
            if sink.find_property("sync"):
                sink.set_property("sync", False)
            if sink.find_property("async"):
                sink.set_property("async", False)
            if sink.find_property("max-lateness"):
                sink.set_property("max-lateness", 0)
            if sink.find_property("processing-deadline"):
                sink.set_property("processing-deadline", 0)
            if sink.find_property("show-preroll-frame"):
                sink.set_property("show-preroll-frame", False)
            elems = [depay]
            if parser:
                elems.extend([parser, codec_caps])
            elems.extend([dec, render_queue])
            if conv:
                elems.append(conv)
            if force_software_scale:
                scale.set_property("add-borders", False)
                elems.append(scale)
            if capsf:
                caps = "video/x-raw,format=%s" % render_format
                if force_software_scale:
                    caps += ",width=%d,height=%d" % (DISPLAY_W, DISPLAY_H)
                capsf.set_property("caps", Gst.Caps.from_string(caps))
                elems.append(capsf)
            elems.append(sink)
            for e in elems:
                self.pipe.add(e)

            # Never drop compressed RTP frames before decoding: H.264/VP8
            # reference frames would be invalidated.  The leaky queue after
            # decoding drops only stale raw frames when the display is late.
            if parser:
                depay.link(parser)
                parser.link(codec_caps)
                codec_caps.link(dec)
            else:
                depay.link(dec)
            dec.link(render_queue)
            if force_software_scale:
                (conv or render_queue).link(scale)
                if capsf:
                    scale.link(capsf)
                    capsf.link(sink)
                else:
                    scale.link(sink)
            else:
                # Let the KMS plane scale the decoded frame. This avoids a
                # full-resolution CPU videoscale pass on RK3588.
                if capsf:
                    conv.link(capsf)
                    capsf.link(sink)
                elif conv:
                    conv.link(sink)
                else:
                    render_queue.link(sink)

            decoder_pad = dec.get_static_pad("src")
            sink_pad = sink.get_static_pad("sink")
            if decoder_pad:
                decoder_pad.add_probe(Gst.PadProbeType.BUFFER, self._on_decoded_buffer)
            if sink_pad:
                sink_pad.add_probe(Gst.PadProbeType.BUFFER, self._on_presented_buffer)

            ret = pad.link(depay.get_static_pad("sink"))
            if ret != Gst.PadLinkReturn.OK:
                log.error("Pad link FAILED: %s", ret)
                for e in elems:
                    self.pipe.remove(e)
                return

            self._decode_elems = elems
            for e in elems:
                e.sync_state_with_parent()

            log.info("=== VIDEO PIPELINE LINKED: %s (plane-id=%d, %dx%d) ===",
                     encoding, PLANE_ID, DISPLAY_W, DISPLAY_H)
            self._send_signaling({
                "t": "receiver_status",
                "s": self.sid,
                "state": "playing",
                "details": {
                    "codec": encoding,
                    "plane_id": PLANE_ID,
                    "display_width": DISPLAY_W,
                    "display_height": DISPLAY_H,
                },
            })

        except Exception as e:
            log.error("PAD_ADDED exception: %s", e)
            self._send_signaling({
                "t": "receiver_status",
                "s": self.sid,
                "state": "failed",
                "details": {"reason": "video_pipeline_link_failed", "error": str(e)},
            })

    def _handle_offer(self, sdp_str):
        log.info("Processing offer (len=%d)...", len(sdp_str))
        ret, sdp_msg = GstSdp.sdp_message_new_from_text(sdp_str)
        if ret != 0:
            log.error("Failed to parse SDP: ret=%s", ret)
            return
        offer = GstWebRTC.WebRTCSessionDescription.new(
            GstWebRTC.WebRTCSDPType.OFFER, sdp_msg)

        promise = Gst.Promise.new()
        self.webrtc.emit("set-remote-description", offer, promise)
        promise.interrupt()

        promise = Gst.Promise.new_with_change_func(self._on_answer_created)
        self.webrtc.emit("create-answer", None, promise)

    def _on_answer_created(self, promise, user_data=None):
        promise.wait()
        reply = promise.get_reply()
        if reply:
            answer = reply.get_value("answer")
            if answer:
                p = Gst.Promise.new()
                self.webrtc.emit("set-local-description", answer, p)
                p.interrupt()
                sdp = answer.sdp
                sdp_text, bitrate_hints = self._with_lan_h264_bitrate_hints(sdp.as_text())
                log.info("Answer created (len=%d), sending...", len(sdp_text))
                if bitrate_hints:
                    log.info("Answer H.264 LAN bitrate hints: %d/%d/%d kbps",
                             LAN_H264_MIN_KBPS, LAN_H264_START_KBPS,
                             LAN_H264_MAX_KBPS)
                self._send_signaling({"t": "answer", "s": self.sid, "sdp": sdp_text})
                # set-remote-description 已完成（promise.wait 后），flush 缓存的 ICE
                self._remote_desc_set = True
                self._flush_ice_queue()
        try:
            promise.unref()
        except Exception:
            pass

    def _add_ice_candidate(self, candidate, sdp_mid, sdp_mline_index):
        if not candidate:
            return
        log.info("Add ICE: %s", candidate[:60])
        if self._remote_desc_set:
            self._do_add_ice(candidate, sdp_mid, sdp_mline_index)
        else:
            log.info("Queue ICE (remote desc not set yet)")
            self._ice_queue.append((candidate, sdp_mid, sdp_mline_index))

    def _resolve_mdns_candidate(self, candidate_str):
        """解析 .local ICE candidate，替换为真实 IP"""
        if '.local' not in candidate_str:
            return candidate_str
        # 浏览器 candidate 可能带或不带 ``a=``，按字段定位 .local 主机名。
        fields = candidate_str.split()
        host_index = next(
            (index for index, value in enumerate(fields) if value.endswith(".local")),
            None,
        )
        if host_index is None:
            log.warning("Cannot parse .local candidate: %s", candidate_str[:80])
            return candidate_str
        hostname = fields[host_index]
        if self._sender_ip:
            fields[host_index] = self._sender_ip
            resolved = " ".join(fields)
            log.info("Resolved %s -> %s (sender peer)", hostname, self._sender_ip)
            return resolved
        try:
            # 用 avahi-resolve 解析 .local 名
            result = subprocess.run(
                ["avahi-resolve-host-name", "-4", hostname],
                capture_output=True, text=True, timeout=2)
            if result.returncode == 0 and result.stdout.strip():
                ip = result.stdout.strip().split()[-1]
                fields[host_index] = ip
                resolved = " ".join(fields)
                log.info("Resolved %s -> %s", hostname, ip)
                return resolved
        except Exception as e:
            log.warning("avahi-resolve failed for %s: %s", hostname, e)
        # fallback: Python socket
        try:
            infos = socket.getaddrinfo(hostname, None, socket.AF_INET)
            if infos:
                ip = infos[0][4][0]
                fields[host_index] = ip
                resolved = " ".join(fields)
                log.info("Resolved %s -> %s (socket)", hostname, ip)
                return resolved
        except Exception as e:
            log.warning("socket resolve failed for %s: %s", hostname, e)
        log.warning("Cannot resolve .local candidate, dropping: %s", candidate_str[:80])
        return None

    def _do_add_ice(self, candidate, sdp_mid, sdp_mline_index):
        resolved = self._resolve_mdns_candidate(candidate)
        if resolved is None:
            return
        try:
            self.webrtc.emit("add-ice-candidate", int(sdp_mline_index), resolved)
        except Exception as e:
            log.warning("add-ice-candidate failed: %s", e)

    def _flush_ice_queue(self):
        if not self._ice_queue:
            return
        log.info("Flushing %d queued ICE candidates", len(self._ice_queue))
        for candidate, sdp_mid, sdp_mline_index in self._ice_queue:
            self._do_add_ice(candidate, sdp_mid, sdp_mline_index)
        self._ice_queue.clear()

    async def _ws_loop(self):
        while self.running:
            try:
                async with websockets.connect(
                    self.ws_url, max_size=2**20, ping_interval=20, ping_timeout=10
                ) as ws:
                    self.ws = ws
                    log.info("WS connected")
                    await ws.send(json.dumps({"t": "reg", "s": self.sid}))
                    log.info("Registered as viewer: %s", self.sid)

                    for m in self.pending_msgs:
                        await ws.send(json.dumps(m))
                    self.pending_msgs.clear()

                    async for msg in ws:
                        try:
                            d = json.loads(msg)
                        except json.JSONDecodeError:
                            continue

                        t = d.get("t", "")
                        if t == "error":
                            msg_text = d.get("msg", "")
                            log.error("Server error: %s", msg_text)
                            if "not found" in msg_text or "no sender" in msg_text:
                                log.info("Session not ready, waiting 3s...")
                                await asyncio.sleep(3)
                            break
                        elif t == "reg_ok":
                            self._sender_ip = d.get("sender_ip", "") or ""
                            log.info("Sender peer address: %s", self._sender_ip)
                        elif t == "offer":
                            self._cleanup_decode_chain()
                            self._handle_offer(d["sdp"])
                        elif t == "ice":
                            self._add_ice_candidate(d.get("c", ""), d.get("m", ""), d.get("l", 0))
                        elif t == "stopped":
                            log.info("Sender stopped, waiting for reconnect...")
                            await asyncio.sleep(2)
                            break

            except websockets.ConnectionClosed:
                log.warning("WS disconnected, reconnecting in 3s...")
            except Exception as e:
                log.error("WS error: %s", e)

            if self.running:
                await asyncio.sleep(3)

    async def run(self):
        self.loop = asyncio.get_running_loop()
        self._create_pipeline()
        ret = self.pipe.set_state(Gst.State.PLAYING)
        if ret == Gst.StateChangeReturn.FAILURE:
            log.error("Pipeline failed to start")
            return
        log.info("GStreamer pipeline started, connecting to %s ...", self.ws_url)
        await self._ws_loop()
        log.info("Shutting down...")
        self._cleanup_decode_chain()
        self.pipe.set_state(Gst.State.NULL)


async def main():
    if len(sys.argv) < 2:
        print("Usage: hdmi_receiver.py <session_id> [ws_url]")
        sys.exit(1)

    sid = sys.argv[1]
    ws_url = sys.argv[2] if len(sys.argv) > 2 else "ws://localhost:8081/ws"

    receiver = NativeReceiver(sid, ws_url)
    await receiver.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
