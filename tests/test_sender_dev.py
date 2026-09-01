from __future__ import annotations

from pathlib import Path
import importlib.util


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "run_sender_dev.py"
SPEC = importlib.util.spec_from_file_location("run_sender_dev", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_sender_dev_passes_websocket_origin_not_endpoint_path() -> None:
    assert MODULE.build_ws_base("192.168.1.109", 8080) == "wss://192.168.1.109:8080"
    assert MODULE.build_ws_base("127.0.0.1", 8081, "ws") == "ws://127.0.0.1:8081"


def test_sender_pages_keep_low_latency_capture_profile() -> None:
    root = MODULE_PATH.parents[1]
    p2p = (root / "frontend" / "p2p-sender.html").read_text(encoding="utf-8")
    sender = (root / "frontend" / "sender.html").read_text(encoding="utf-8")
    assert "2K 清晰档" in p2p
    assert "width: 2560" in p2p
    assert "height: 1440" in p2p
    assert "realtime" in p2p
    assert "maintain-framerate" in p2p
    assert "contentHint = 'motion'" in p2p
    assert "max: 1280" in sender
    assert "max: 720" in sender
    assert "max: 30" in sender
    assert "maintain-framerate" in sender
    assert "pairingCode" in p2p
    assert "pair_ok" in p2p
    assert "localPreviewEnabled" in p2p
    assert "Constrained Baseline" in p2p
    assert "sender_stats" in p2p
    assert "quality_limit" in p2p
    assert "x-google-start-bitrate" in p2p


def test_hdmi_receiver_prefers_modern_mpp_decoder_and_parses_h26x() -> None:
    root = MODULE_PATH.parents[1]
    receiver = (root / "backend" / "hdmi_receiver.py").read_text(encoding="utf-8")
    assert '"H264": ("mppvideodec"' in receiver
    assert '"H265": ("mppvideodec"' in receiver
    assert 'Gst.ElementFactory.make("h264parse", None)' in receiver
    assert 'Gst.ElementFactory.make("h265parse", None)' in receiver
    assert "stream-format=byte-stream,alignment=au" in receiver
    assert "SCREENCAST_VIDEO_DECODER" in receiver
    assert 'SCREENCAST_RENDER_FORMAT", "BGRx"' in receiver
    assert "zero-copy fast path" in receiver
    assert "FrameStats: decoded=" in receiver
    assert "Answer H.264 LAN bitrate hints" in receiver
    assert "KMS black mask started" in receiver
    assert 'element.set_property("drop-on-latency", False)' in receiver


def test_mpp_enable_script_keeps_vendor_plugin_isolated() -> None:
    root = MODULE_PATH.parents[1]
    script = (root / "scripts" / "enable_mpp_plugin.sh").read_text(encoding="utf-8")
    assert "GST_PLUGIN_PATH" in script
    assert "LD_LIBRARY_PATH" in script
    assert "mppvideodec" in script
