"""
WebRTC 接收器模块
每个投屏会话对应一个 StreamReceiver 实例，管理 GStreamer webrtcbin 管线
支持 WHEP (RFC 9372) 信令协议
"""

import asyncio
import json
import logging
import threading
import uuid

from .hardware import hardware

logger = logging.getLogger(__name__)

# 尝试导入 gi (GObject Introspection - GStreamer Python 绑定)
try:
    import gi
    gi.require_version("Gst", "1.0")
    gi.require_version("GstWebRTC", "1.0")
    gi.require_version("GstSdp", "1.0")
    from gi.repository import Gst, GstWebRTC, GstSdp, GLib
    Gst.init(None)
    HAS_GST = True
except (ImportError, ValueError) as e:
    HAS_GST = False
    logger.warning("GStreamer Python 绑定不可用, WebRTC 接收器将运行在模拟模式: %s", e)


class StreamReceiver:
    """单个 WebRTC 投屏流的接收器

    管理 GStreamer 管线: webrtcbin → depay → decode → (compositor / sink)
    """

    def __init__(self, session_id, config=None, on_pad_created=None):
        self.session_id = session_id
        self._config = config
        self._on_pad_created = on_pad_created
        self._pipeline = None
        self._webrtcbin = None
        self._loop = None
        self._glib_ctx = None
        self._glib_thread = None
        self._answer = None
        self._answer_event = threading.Event()
        self._state = "created"
        self._stats = {"bytes_received": 0, "frames_decoded": 0, "packets_lost": 0}

    @property
    def state(self):
        return self._state

    @property
    def answer_sdp(self):
        """返回 SDP Answer 字符串 (WHEP 用)"""
        if self._answer:
            return self._answer.sdp.as_text()
        return None

    @property
    def stats(self):
        return dict(self._stats)

    @property
    def is_active(self):
        return self._state in ("connecting", "connected")

    # ---- 生命周期 ----

    def create_pipeline(self, output_sink_string=None):
        """创建 GStreamer 管线并启动 GLib 主循环线程"""
        if not HAS_GST:
            logger.warning("[%s] GStreamer 不可用, 跳过管线创建", self.session_id)
            return False

        # 创建专用 GLib 主上下文 + 线程
        self._glib_ctx = GLib.MainContext.new()
        self._loop = GLib.MainLoop.new(self._glib_ctx, False)
        self._glib_thread = threading.Thread(target=self._loop.run, daemon=True)
        self._glib_thread.start()
        logger.info("[%s] GLib 主循环线程已启动", self.session_id)

        # 在 GLib 上下文中创建管线 (确保信号回调在此上下文派发)
        self._pipeline = Gst.Pipeline.new(f"receiver-{self.session_id}")

        # webrtcbin
        self._webrtcbin = Gst.ElementFactory.make("webrtcbin", f"webrtc-{self.session_id}")
        if not self._webrtcbin:
            logger.error("[%s] 无法创建 webrtcbin, 检查 GStreamer WebRTC 插件", self.session_id)
            return False

        self._webrtcbin.set_property("bundle-policy", "max-bundle")
        self._pipeline.add(self._webrtcbin)

        # Bus 监控
        bus = self._pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self._on_bus_message)

        # 连接 on-negotiation-needed 信号 → 自动生成 Answer
        self._webrtcbin.connect("on-negotiation-needed", self._on_negotiation_needed)

        # 连接 pad-added 信号 → 动态创建解码管线
        self._webrtcbin.connect("pad-added", self._on_pad_added)

        # 连接 ICE 候选收集
        self._webrtcbin.connect("on-ice-candidate", self._on_ice_candidate)

        # 连接状态变化
        self._webrtcbin.connect("notify::ice-connection-state", self._on_ice_state)
        self._webrtcbin.connect("notify::connection-state", self._on_connection_state)

        logger.info("[%s] 管线已创建", self.session_id)
        return True

    def set_offer(self, sdp_offer_text):
        """设置远端 SDP Offer, 阻塞等待 Answer 生成"""
        if not HAS_GST:
            return None

        self._state = "connecting"
        self._answer = None
        self._answer_event.clear()

        # 解析 SDP
        ret, sdp_msg = GstSdp.SDPMessage.new()
        if ret != GstSdp.SDPResult.OK:
            logger.error("[%s] 无法创建 SDP 消息", self.session_id)
            return None

        GstSdp.sdp_message_parse_buffer(sdp_offer_text.encode(), sdp_msg)

        # 创建 SDP Offer
        offer = GstWebRTC.WebRTCSessionDescription.new(
            GstWebRTC.WebRTCSDPType.OFFER, sdp_msg,
        )

        # 在 GLib 主循环线程中设置远端描述 (确保信号在该上下文派发)
        def do_set_remote():
            promise = Gst.Promise.new()
            self._webrtcbin.emit("set-remote-description", offer, promise)
            promise.wait()

        if self._glib_ctx:
            self._glib_ctx.invoke_full(0, do_set_remote)
        else:
            do_set_remote()

        logger.info("[%s] 等待 Answer 生成...", self.session_id)

        # 阻塞等待 on-negotiation-needed → create-answer → _on_answer_created
        if not self._answer_event.wait(timeout=15):
            logger.error("[%s] Answer 生成超时", self.session_id)
            return None

        logger.info("[%s] Answer 就绪", self.session_id)
        return self.answer_sdp

    def add_ice_candidate(self, candidate, sdp_mid, sdp_mline_index):
        """添加 ICE 候选"""
        if not HAS_GST or not self._webrtcbin:
            return

        try:
            self._webrtcbin.emit("add-ice-candidate", sdp_mline_index, candidate)
        except Exception as e:
            logger.warning("[%s] 添加 ICE 候选失败: %s", self.session_id, e)

    def set_tlp_candidates(self, candidates):
        """WHEP: 批量设置 ICE candidates (from SDP a=candidate lines or link header)"""
        for cand in candidates:
            sdp_mid = cand.get("candidate", "").split(" ").index("typ") if "typ" in cand.get("candidate", "") else ""
            self.add_ice_candidate(
                candidate=cand.get("candidate", ""),
                sdp_mid=cand.get("sdpMid", "0"),
                sdp_mline_index=cand.get("sdpMLineIndex", 0),
            )

    def start(self, loop=None):
        """启动管线 (设置 PLAYING 状态)"""
        if not self._pipeline:
            return

        ret = self._pipeline.set_state(Gst.State.PLAYING)
        if ret == Gst.StateChangeReturn.FAILURE:
            logger.error("[%s] 管线启动失败", self.session_id)
            self._state = "failed"
            return

        logger.info("[%s] 管线已启动 (PLAYING)", self.session_id)

    def stop(self):
        """停止并清理管线"""
        self._state = "disconnected"

        if self._pipeline:
            self._pipeline.set_state(Gst.State.NULL)
            self._pipeline = None
        self._webrtcbin = None

        if self._loop:
            self._loop.quit()
        if self._glib_thread and self._glib_thread.is_alive():
            self._glib_thread.join(timeout=5)
        self._loop = None
        self._glib_thread = None

        logger.info("[%s] 管线已停止", self.session_id)

    # ---- 内部回调 ----

    def _on_bus_message(self, bus, message):
        """GStreamer Bus 消息处理"""
        t = message.type
        if t == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            logger.error("[%s] GST ERROR: %s — %s", self.session_id, err, debug)
        elif t == Gst.MessageType.WARNING:
            warn, debug = message.parse_warning()
            logger.warning("[%s] GST WARNING: %s — %s", self.session_id, warn, debug)
        elif t == Gst.MessageType.EOS:
            logger.info("[%s] GST EOS (流结束)", self.session_id)
        elif t == Gst.MessageType.STATE_CHANGED:
            if message.src == self._pipeline:
                old, new, pending = message.parse_state_changed()
                logger.info("[%s] 管线状态: %s → %s", self.session_id, old.value_nick, new.value_nick)
        elif t == Gst.MessageType.STREAM_STATUS:
            logger.debug("[%s] GST stream-status", self.session_id)
        elif t == Gst.MessageType.NEW_CLOCK:
            logger.info("[%s] GST 新时钟", self.session_id)
        elif t == Gst.MessageType.ASYNC_DONE:
            logger.info("[%s] GST async-done", self.session_id)
        elif t == Gst.MessageType.PROPERTY_NOTIFY:
            src, prop_name, value = message.parse_property_notify()
            logger.debug("[%s] GST property-notify: %s = %s", self.session_id, prop_name, value)
        elif t == Gst.MessageType.LATENCY:
            logger.debug("[%s] GST latency", self.session_id)

    def _on_negotiation_needed(self, element):
        """自动生成 SDP Answer"""
        logger.info("[%s] 协商开始, 生成 Answer", self.session_id)

        promise = Gst.Promise.new_with_change_func(
            self._on_answer_created, element, None,
        )
        element.emit("create-answer", None, promise)

    def _on_answer_created(self, promise, element, user_data):
        """Answer 创建完成"""
        reply = promise.get_reply()
        if not reply:
            logger.error("[%s] Answer 创建失败", self.session_id)
            return

        answer = reply.get_value("answer")
        if not answer:
            logger.error("[%s] Answer 为空", self.session_id)
            return

        self._answer = answer

        # 设置本地描述
        set_promise = Gst.Promise.new()
        element.emit("set-local-description", answer, set_promise)
        set_promise.wait()

        logger.info("[%s] SDP Answer 已生成 (%d bytes)", self.session_id, len(answer.sdp.as_text()))
        self._answer_event.set()

    def _on_pad_added(self, element, pad):
        """远端流 pad 添加 → 创建解码分支"""
        caps = pad.query_caps(None)
        name = caps.to_string()

        is_video = "video" in name.lower()
        kind = "video" if is_video else "audio"
        logger.info("[%s] 收到 %s 流: %s", self.session_id, kind, name[:80])

        if is_video:
            self._create_video_branch(pad, caps)
        else:
            self._create_audio_branch(pad, caps)

        if self._on_pad_created:
            self._on_pad_created(pad, is_video)

    def _create_video_branch(self, pad, caps):
        """创建视频解码分支

        rtp...depay ! rkmpph264dec ! videoconvert ! autovideosink
        """
        pipeline = self._pipeline
        if not pipeline:
            return

        decode_element = hardware.get_gst_decode_element()

        # depayloader
        depay_name = "rtph264depay"
        if "H265" in caps.to_string() or "h265" in caps.to_string() or "VP9" in caps.to_string():
            depay_name = "rtpvp9depay" if "VP9" in caps.to_string() else "rtph265depay"
            decode_element = hardware.get_gst_decode_element_h265()

        depay = Gst.ElementFactory.make(depay_name, f"depay-v-{self.session_id}")
        decoder = Gst.ElementFactory.make(decode_element, f"decode-v-{self.session_id}")
        convert = Gst.ElementFactory.make("videoconvert", f"convert-v-{self.session_id}")
        sink = Gst.ElementFactory.make("autovideosink", f"sink-v-{self.session_id}")

        if not depay or not decoder or not convert:
            logger.error("[%s] 无法创建视频元素: depay=%s decode=%s convert=%s sink=%s",
                         self.session_id, bool(depay), bool(decoder), bool(convert), bool(sink))
            return

        pipeline.add(depay)
        pipeline.add(decoder)
        pipeline.add(convert)
        if sink:
            pipeline.add(sink)

        depay.link(decoder)
        decoder.link(convert)
        if sink:
            convert.link(sink)

        sink.sync_state_with_parent() if sink else None
        convert.sync_state_with_parent()
        depay.sync_state_with_parent()
        decoder.sync_state_with_parent()

        pad.link(depay.get_static_pad("sink"))

        logger.info("[%s] 视频分支: %s ! %s ! videoconvert ! autovideosink",
                     self.session_id, depay_name, decode_element)

    def _create_audio_branch(self, pad, caps):
        """创建音频解码分支

        rtpopusdepay ! opusdec ! audioconvert ! autoaudiosink
        """
        pipeline = self._pipeline
        if not pipeline:
            return

        depay = Gst.ElementFactory.make("rtpopusdepay", f"depay-a-{self.session_id}")
        decoder = Gst.ElementFactory.make("opusdec", f"decode-a-{self.session_id}")
        convert = Gst.ElementFactory.make("audioconvert", f"convert-a-{self.session_id}")
        sink = Gst.ElementFactory.make("autoaudiosink", f"sink-a-{self.session_id}")

        if not depay or not decoder or not convert:
            logger.error("[%s] 无法创建音频元素", self.session_id)
            return

        pipeline.add(depay)
        pipeline.add(decoder)
        pipeline.add(convert)
        if sink:
            pipeline.add(sink)

        depay.link(decoder)
        decoder.link(convert)
        if sink:
            convert.link(sink)

        sink.sync_state_with_parent() if sink else None
        convert.sync_state_with_parent()
        depay.sync_state_with_parent()
        decoder.sync_state_with_parent()

        pad.link(depay.get_static_pad("sink"))

        logger.info("[%s] 音频分支: rtpopusdepay ! opusdec ! audioconvert ! autoaudiosink",
                     self.session_id)

    def _on_ice_candidate(self, element, mline_index, candidate):
        """收集本地 ICE 候选"""
        logger.debug("[%s] ICE candidate: %s", self.session_id, candidate.candidate[:60])

    def _on_ice_state(self, element, pspec):
        """ICE 连接状态变化"""
        state = element.get_property("ice-connection-state")
        state_name = state.value_name if state else "unknown"
        logger.info("[%s] ICE 状态: %s", self.session_id, state_name)

        if state and state.value_nick == "completed":
            self._state = "connected"
        elif state and state.value_nick == "failed":
            self._state = "failed"

    def _on_connection_state(self, element, pspec):
        """WebRTC 连接状态变化"""
        state = element.get_property("connection-state")
        state_name = state.value_name if state else "unknown"
        logger.info("[%s] 连接状态: %s", self.session_id, state_name)

        if state and state.value_nick == "connected":
            self._state = "connected"
        elif state and state.value_nick == "disconnected":
            self._state = "disconnected"
        elif state and state.value_nick == "failed":
            self._state = "failed"


class StreamReceiverManager:
    """管理所有活跃的 StreamReceiver 实例"""

    def __init__(self, config=None, on_pad_created=None):
        self._config = config
        self._on_pad_created = on_pad_created
        self._receivers = {}  # session_id → StreamReceiver
        self._lock = asyncio.Lock()

    async def create_session(self, session_id=None):
        """创建新的接收会话"""
        async with self._lock:
            if session_id is None:
                session_id = f"sess_{uuid.uuid4().hex[:8]}"

            if session_id in self._receivers:
                raise ValueError(f"会话 {session_id} 已存在")

            receiver = StreamReceiver(
                session_id=session_id,
                config=self._config,
                on_pad_created=self._on_pad_created,
            )
            self._receivers[session_id] = receiver
            logger.info("[Manager] 会话已创建: %s (活跃: %d)",
                         session_id, len(self._receivers))
            return receiver

    async def get_session(self, session_id):
        return self._receivers.get(session_id)

    async def remove_session(self, session_id):
        """移除并停止会话"""
        async with self._lock:
            receiver = self._receivers.pop(session_id, None)
            if receiver:
                receiver.stop()
                logger.info("[Manager] 会话已移除: %s (活跃: %d)",
                             session_id, len(self._receivers))
                return True
            return False

    async def stop_all(self):
        async with self._lock:
            for receiver in self._receivers.values():
                receiver.stop()
            self._receivers.clear()
            logger.info("[Manager] 所有会话已停止")

    @property
    def active_sessions(self):
        return {sid: r for sid, r in self._receivers.items() if r.is_active}

    @property
    def session_count(self):
        return len(self._receivers)

    def get_status_list(self):
        """返回所有会话的状态摘要"""
        return [
            {
                "session_id": sid,
                "state": r.state,
                "stats": r.stats,
            }
            for sid, r in self._receivers.items()
        ]
