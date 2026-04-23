"""
显示输出管理模块
管理 kmssink (DRM/KMS → HDMI) 或 autovideosink (开发回退)
"""

import logging

from .hardware import hardware

logger = logging.getLogger(__name__)


class DisplayManager:
    """管理视频显示输出管线"""

    def __init__(self, config=None):
        self._config = config
        self._pipeline = None
        self._sink_name = hardware.get_gst_sink_element()
        self._drm_connector = None

    def _get_connector(self):
        if self._config:
            conn = self._config.get("hardware", "drm_connector")
            if conn and conn != "auto":
                return conn
        return None

    def build_sink_string(self, connector_override=None):
        """构建显示 sink 的 GStreamer 元素字符串

        kmssink:
            kmssink connector-id=<N> sync=true show-preroll-frame=false

        autovideosink (开发环境):
            autovideosink sync=true
        """
        connector = connector_override or self._get_connector()

        if self._sink_name == "kmssink":
            parts = ["kmssink", "sync=true", "show-preroll-frame=false"]
            if connector and connector != "auto":
                try:
                    parts.append(f"connector-id={int(connector)}")
                except ValueError:
                    parts.append(f"connector-id={connector}")
            return " ".join(parts)

        return "autovideosink sync=true"

    def build_full_pipeline(self, input_caps, connector_override=None):
        """构建从输入 caps 到显示输出的完整管线描述

        input_caps: 例如 'video/x-raw, width=1920, height=1080, framerate=30/1'
        返回: pipeline string (不含 webrtcbin 部分)
        """
        sink = self.build_sink_string(connector_override)
        scale = hardware.get_gst_scale_element()

        if scale != "videoscale":
            scale_elem = f"{scale}"
        else:
            scale_elem = "videoscale"

        pipeline = (
            f"{input_caps} ! "
            f"videoconvert ! "
            f"{scale_elem} ! "
            f"{sink}"
        )
        return pipeline

    @property
    def sink_name(self):
        return self._sink_name

    @property
    def is_hardware_display(self):
        return self._sink_name == "kmssink"

    def get_mode_info(self):
        """返回当前显示模式信息"""
        info = {
            "sink": self._sink_name,
            "hardware": self.is_hardware_display,
        }
        if self._sink_name == "kmssink":
            info["connector"] = self._get_connector() or "auto"
            info["output"] = "DRM/KMS → HDMI"
        else:
            info["output"] = "Window (开发模式)"
        return info
