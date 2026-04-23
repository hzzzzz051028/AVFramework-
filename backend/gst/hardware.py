"""
硬件能力检测模块
检测 RK3588 平台上的 MPP (硬件编解码)、RGA (硬件缩放)、DRM/KMS (显示输出)
Windows/开发环境下提供软件回退
"""

import logging
import platform
import subprocess

logger = logging.getLogger(__name__)


class HardwareInfo:
    """平台硬件能力"""

    def __init__(self):
        self._platform = platform.system()
        self._machine = platform.machine()
        self._detected = False
        self._capabilities = {}

    def detect(self):
        """检测硬件能力"""
        self._detected = True
        is_linux = self._platform == "Linux"

        if not is_linux:
            logger.info("非 Linux 平台 (%s/%s), 硬件加速不可用", self._platform, self._machine)

        caps = {
            "platform": self._platform,
            "machine": self._machine,
            "gstreamer_available": False,
            "gst_version": None,
            "mpp_available": False,
            "rga_available": False,
            "drm_available": False,
        }

        # 检测 GStreamer
        gst_ver = self._check_gstreamer()
        if gst_ver:
            caps["gstreamer_available"] = True
            caps["gst_version"] = gst_ver

        # 检测 MPP (Rockchip Media Process Platform)
        caps["mpp_available"] = self._check_mpp()

        # 检测 RGA (Rockchip Graphics Acceleration)
        caps["rga_available"] = self._check_rga()

        # 检测 DRM/KMS
        caps["drm_available"] = self._check_drm()

        # 综合判定
        caps["hw_decode"] = caps["mpp_available"]
        caps["hw_encode"] = caps["mpp_available"]
        caps["hw_scale"] = caps["rga_available"]
        caps["hw_display"] = caps["drm_available"]

        if not caps["mpp_available"] and self._machine in ("aarch64", "arm64", "armv7l"):
            logger.warning("ARM 平台但未检测到 MPP, 检查 rockchip-mpp 包是否安装")

        self._capabilities = caps
        return caps

    def _check_gstreamer(self):
        # 优先通过 Python 绑定检测 (Windows 也能用)
        try:
            import gi
            gi.require_version("Gst", "1.0")
            from gi.repository import Gst
            Gst.init(None)
            ver = Gst.version_string()
            logger.info("GStreamer: %s (Python bindings)", ver)
            return ver
        except Exception:
            pass

        # 回退: subprocess 检测 CLI 工具
        try:
            r = subprocess.run(
                ["gst-launch-1.0", "--version"],
                capture_output=True, text=True, timeout=5,
            )
            if r.returncode == 0:
                for line in r.stdout.splitlines():
                    if line.startswith("gst-launch-1.0 version"):
                        ver = line.split("version")[-1].strip()
                        logger.info("GStreamer: %s", ver)
                        return ver
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return None

    def _check_mpp(self):
        checks = [
            "/sys/class/video4linux/video10",
            "/dev/mpp_service",
            "/dev/dri/renderD128",
        ]
        found = any(_path_exists(p) for p in checks)
        if found:
            logger.info("Rockchip MPP: 检测到")
        return found

    def _check_rga(self):
        checks = [
            "/dev/rga",
            "/dev/rga0",
            "/dev/rga1",
            "/dev/rga2",
        ]
        found = any(_path_exists(p) for p in checks)
        if found:
            logger.info("Rockchip RGA: 检测到")
        return found

    def _check_drm(self):
        if not _path_exists("/dev/dri"):
            return False
        try:
            entries = subprocess.run(
                ["ls", "/dev/dri/"],
                capture_output=True, text=True, timeout=5,
            )
            has_card = "card" in entries.stdout
            if has_card:
                logger.info("DRM/KMS: 检测到 (%s)", entries.stdout.strip())
            return has_card
        except subprocess.TimeoutExpired:
            return False

    def _check_gst_plugin(self, plugin_name):
        try:
            r = subprocess.run(
                ["gst-inspect-1.0", plugin_name],
                capture_output=True, text=True, timeout=5,
            )
            return r.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def get_gst_decode_element(self):
        """根据硬件返回合适的解码元素名"""
        if not self._detected:
            self.detect()

        if self._capabilities.get("mpp_available"):
            return "rkmpph264dec"
        return "avdec_h264"

    def get_gst_decode_element_h265(self):
        if not self._detected:
            self.detect()
        if self._capabilities.get("mpp_available"):
            return "rkmpph265dec"
        return "avdec_h265"

    def get_gst_scale_element(self):
        if not self._detected:
            self.detect()
        if self._capabilities.get("rga_available"):
            return "rkrgascale"
        return "videoscale"

    def get_gst_sink_element(self):
        if not self._detected:
            self.detect()
        if self._capabilities.get("drm_available"):
            return "kmssink"
        return "autovideosink"

    @property
    def capabilities(self):
        if not self._detected:
            self.detect()
        return dict(self._capabilities)

    @property
    def is_rockchip(self):
        if not self._detected:
            self.detect()
        return self._capabilities.get("mpp_available", False)

    def summary(self):
        """返回人类可读的硬件摘要"""
        if not self._detected:
            self.detect()
        c = self._capabilities
        lines = [
            f"平台: {c.get('platform', 'Unknown')} ({c.get('machine', 'Unknown')})",
            f"GStreamer: {'可用 ' + str(c['gst_version']) if c.get('gstreamer_available') else '未安装'}",
            f"MPP 硬解: {'可用' if c.get('mpp_available') else '不可用'}",
            f"RGA 硬缩放: {'可用' if c.get('rga_available') else '不可用'}",
            f"DRM/KMS 显示: {'可用' if c.get('drm_available') else '不可用'}",
        ]
        return "\n".join(lines)


def _path_exists(path):
    try:
        return __import__("os").path.exists(path)
    except Exception:
        return False


hardware = HardwareInfo()
