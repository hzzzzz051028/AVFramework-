"""
多画面合成器模块
使用 GStreamer compositor 实现动态分屏布局
单路时绕过 compositor 直连 sink, 零合成开销
"""

import logging

from .hardware import hardware

try:
    from .display import DisplayManager
    HAS_DISPLAY = True
except (ImportError, Exception):
    HAS_DISPLAY = False
    logging.getLogger(__name__).warning("DisplayManager 不可用，合成器将使用默认配置")

logger = logging.getLogger(__name__)

# 布局模式定义
LAYOUTS = {
    1: (1, 1),   # 全屏
    2: (1, 2),   # 1×2
    3: (2, 2),   # 2×2 (第4格空)
    4: (2, 2),   # 2×2
    5: (3, 2),   # 3×2 (第6格空)
    6: (3, 2),   # 3×2
    7: (3, 3),   # 3×3 (第8-9格空)
    8: (3, 3),   # 3×3 (第9格空)
    9: (3, 3),   # 3×3
}

# 手动布局映射
MANUAL_LAYOUTS = {
    "1x1": (1, 1),
    "1x2": (1, 2),
    "2x2": (2, 2),
    "3x2": (3, 2),
    "3x3": (3, 3),
}


class CompositorManager:
    """管理多画面合成管线

    负责动态创建/销毁 compositor 的输入 pad,
    管理布局计算, 以及单路绕过优化。
    """

    def __init__(self, config=None):
        self._config = config
        self._display = DisplayManager(config) if HAS_DISPLAY else None
        self._compositor = None
        self._pipeline = None
        self._current_layout = "auto"
        self._forced_layout = None
        self._sinks = {}  # session_id → compositor sink pad
        self._active_count = 0

    def get_layout(self, stream_count):
        """根据活跃流数量返回布局 (rows, cols)"""
        if self._forced_layout:
            return MANUAL_LAYOUTS.get(self._forced_layout, LAYOUTS.get(stream_count, (3, 3)))

        if self._current_layout != "auto":
            return MANUAL_LAYOUTS.get(self._current_layout, LAYOUTS.get(stream_count, (3, 3)))

        return LAYOUTS.get(stream_count, (3, 3))

    def calculate_position(self, index, rows, cols, output_w=1920, output_h=1080):
        """计算第 index 路流在合成画面中的位置和大小

        返回: (x, y, width, height)
        """
        cell_w = output_w // cols
        cell_h = output_h // rows

        row = index // cols
        col = index % cols

        x = col * cell_w
        y = row * cell_h

        return x, y, cell_w, cell_h

    def set_layout(self, layout):
        """设置布局模式"""
        if layout in MANUAL_LAYOUTS:
            self._forced_layout = layout
            logger.info("[Compositor] 布局切换为: %s", layout)
        elif layout == "auto":
            self._forced_layout = None
            self._current_layout = "auto"
            logger.info("[Compositor] 布局切换为: auto")
        else:
            logger.warning("[Compositor] 未知布局: %s", layout)

    def should_use_compositor(self, stream_count):
        """判断是否需要 compositor (单路绕过)"""
        if self._forced_layout:
            forced = MANUAL_LAYOUTS.get(self._forced_layout, (1, 1))
            return forced[0] * forced[1] > 1
        return stream_count > 1

    def get_pipeline_description(self, stream_count):
        """生成完整管线描述

        单路: depay ! decode ! videoconvert ! scale ! sink
        多路: depay ! decode ! videoconvert ! scale → compositor → sink

        注意: 这个方法只返回 sink/compositor 部分,
        webrtcbin → depay → decode 部分由 receiver.py 负责
        """
        sink = self._display.build_sink_string() if self._display else "autovideosink"
        use_compositor = self.should_use_compositor(stream_count)

        if not use_compositor:
            # 单路直连
            return f"videoconvert ! {sink}"

        # 多路合成
        rows, cols = self.get_layout(stream_count)
        output_w = self._config.get("display", "width") if self._config else 1920
        output_h = self._config.get("display", "height") if self._config else 1080

        # compositor 输出尺寸
        caps = f"video/x-raw, width={output_w}, height={output_h}"

        return f"compositor name=mix ! {caps} ! videoconvert ! {sink}"

    def build_compositor_sink_request(self, index, stream_count):
        """为 compositor 第 index 路输入生成 pad 属性

        返回 GStreamer request pad 属性字符串,
        用于 compositor.get_request_pad()
        """
        rows, cols = self.get_layout(stream_count)
        output_w = self._config.get("display", "width") if self._config else 1920
        output_h = self._config.get("display", "height") if self._config else 1080

        x, y, w, h = self.calculate_position(index, rows, cols, output_w, output_h)

        return {
            "pad_name": f"sink_{index}",
            "x": x,
            "y": y,
            "width": w,
            "height": h,
            "zorder": index,
        }

    def on_stream_added(self, session_id, video_src_pad):
        """新视频流加入时的处理

        video_src_pad: 来自 receiver 的 videoconvert src pad
        """
        pass  # 将在集成到管线管理器时实现

    def on_stream_removed(self, session_id):
        """视频流移除时的处理"""
        pass  # 将在集成到管线管理器时实现

    def get_status(self):
        """返回合成器状态"""
        return {
            "layout": self._forced_layout or "auto",
            "active_streams": self._active_count,
            "using_compositor": self.should_use_compositor(self._active_count),
            "display": self._display.get_mode_info() if self._display else {"mode": "default"},
        }

    @property
    def display_manager(self):
        return self._display
