"""
音频混音模块
多路 Opus 音频解码 → audioconvert → audiomixer → pulsesink
"""

import logging

logger = logging.getLogger(__name__)


class AudioManager:
    """管理音频输出管线

    将多路音频流混音后输出到音频设备。
    单路时直连, 多路时使用 audiomixer (或adder)。
    """

    def __init__(self, config=None):
        self._config = config
        self._audio_enabled = True
        self._master_volume = 80
        self._streams = {}  # session_id → audio info
        self._output_device = "auto"

        if config:
            self._audio_enabled = config.get("audio", "enabled", default=True)
            self._master_volume = config.get("audio", "master_volume", default=80)
            self._output_device = config.get("audio", "output_device", default="auto")

    @property
    def enabled(self):
        return self._audio_enabled

    @property
    def master_volume(self):
        return self._master_volume

    @master_volume.setter
    def master_volume(self, value):
        self._master_volume = max(0, min(100, int(value)))
        logger.info("[Audio] 主音量: %d%%", self._master_volume)

    def set_volume(self, value):
        """设置主音量 (0-100)"""
        self.master_volume = value

    def get_sink_string(self):
        """构建音频输出 sink 的 GStreamer 元素字符串"""
        device_param = ""
        if self._output_device and self._output_device != "auto":
            device_param = f" device={self._output_device}"

        volume = self._master_volume / 100.0
        return f"volume volume={volume:.2f} ! pulsesink{device_param}"

    def build_audio_pipeline_suffix(self, stream_count):
        """构建音频管线后缀

        单路: audioconvert ! volume ! pulsesink
        多路: audiomixer ! audioconvert ! volume ! pulsesink
        """
        sink = self.get_sink_string()

        if stream_count <= 1:
            return f"audioconvert ! {sink}"
        return f"audiomixer name=amix ! audioconvert ! {sink}"

    def on_audio_added(self, session_id):
        """新音频流加入"""
        self._streams[session_id] = {"state": "active"}
        logger.info("[Audio] 音频流加入: %s (总数: %d)", session_id, len(self._streams))

    def on_audio_removed(self, session_id):
        """音频流移除"""
        self._streams.pop(session_id, None)
        logger.info("[Audio] 音频流移除: %s (总数: %d)", session_id, len(self._streams))

    def get_status(self):
        """返回音频状态"""
        return {
            "enabled": self._audio_enabled,
            "master_volume": self._master_volume,
            "output_device": self._output_device,
            "active_streams": len(self._streams),
        }
