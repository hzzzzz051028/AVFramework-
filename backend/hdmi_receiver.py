#!/usr/bin/env python3
"""Native HDMI display receiver - GStreamer WebRTC + kmssink (no browser)."""
import asyncio, json, logging, os, re, socket, subprocess, sys
import websockets

logging.basicConfig(level=logging.INFO, format="[HDMI] %(message)s")
log = logging.getLogger(__name__)

import gi
gi.require_version('Gst', '1.0')
gi.require_version('GstWebRTC', '1.0')
gi.require_version('GstSdp', '1.0')
from gi.repository import Gst, GstWebRTC, GstSdp

Gst.init(None)

DISPLAY_W, DISPLAY_H = 1024, 600
PLANE_ID = 71


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

    def _send_signaling(self, msg):
        if self.loop and not self.loop.is_closed():
            self.loop.call_soon_threadsafe(self._do_send, msg)
        else:
            self.pending_msgs.append(msg)

    def _do_send(self, msg):
        asyncio.ensure_future(self._async_send(msg))

    async def _async_send(self, msg):
        try:
            if self.ws and not self.ws.closed:
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
        self.pipe.add(self.webrtc)
        self.webrtc.connect("on-ice-candidate", self._on_ice_candidate)
        self.webrtc.connect("pad-added", self._on_pad_added)

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

            depay = dec = conv = scale = capsf = sink = None
            if encoding == "H264":
                depay = Gst.ElementFactory.make("rtph264depay", None)
                dec = Gst.ElementFactory.make("avdec_h264", None)
            elif encoding == "H265":
                depay = Gst.ElementFactory.make("rtph265depay", None)
                dec = Gst.ElementFactory.make("avdec_h265", None)
            elif encoding == "VP8":
                depay = Gst.ElementFactory.make("rtpvp8depay", None)
                dec = Gst.ElementFactory.make("vp8dec", None)
            elif encoding == "VP9":
                depay = Gst.ElementFactory.make("rtpvp9depay", None)
                dec = Gst.ElementFactory.make("vp9dec", None)
            else:
                log.error("Unsupported codec: %s", encoding)
                return

            conv = Gst.ElementFactory.make("videoconvert", None)
            scale = Gst.ElementFactory.make("videoscale", None)
            capsf = Gst.ElementFactory.make("capsfilter", None)
            sink = Gst.ElementFactory.make("kmssink", None)
            if not all([depay, dec, conv, scale, capsf, sink]):
                log.error("Missing elements for %s", encoding)
                return

            sink.set_property("plane-id", PLANE_ID)
            scale.set_property("add-borders", False)
            capsf.set_property("caps", Gst.Caps.from_string(
                "video/x-raw, width=%d, height=%d" % (DISPLAY_W, DISPLAY_H)))

            elems = [depay, dec, conv, scale, capsf, sink]
            for e in elems:
                self.pipe.add(e)

            depay.link(dec)
            dec.link(conv)
            conv.link(scale)
            scale.link(capsf)
            capsf.link(sink)

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

        except Exception as e:
            log.error("PAD_ADDED exception: %s", e)

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
                sdp_text = sdp.as_text()
                log.info("Answer created (len=%d), sending...", len(sdp_text))
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
        # 从 candidate 字符串提取主机名: a=candidate:... <host> <port> ...
        m = re.search(r'(a=candidate:\S+ +)(\S+\.local)( +\d+ )(.*)', candidate_str)
        if not m:
            log.warning("Cannot parse .local candidate: %s", candidate_str[:80])
            return candidate_str
        hostname = m.group(2)
        try:
            # 用 avahi-resolve 解析 .local 名
            result = subprocess.run(
                ["avahi-resolve-host-name", "-4", hostname],
                capture_output=True, text=True, timeout=2)
            if result.returncode == 0 and result.stdout.strip():
                ip = result.stdout.strip().split()[-1]
                resolved = f"{m.group(1)}{ip}{m.group(3)}{m.group(4)}"
                log.info("Resolved %s -> %s", hostname, ip)
                return resolved
        except Exception as e:
            log.warning("avahi-resolve failed for %s: %s", hostname, e)
        # fallback: Python socket
        try:
            infos = socket.getaddrinfo(hostname, None, socket.AF_INET)
            if infos:
                ip = infos[0][4][0]
                resolved = f"{m.group(1)}{ip}{m.group(3)}{m.group(4)}"
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
