#!/usr/bin/env python3
"""Check whether this machine can run the desktop GStreamer receiver."""

from __future__ import annotations

import platform
import shutil
import sys
from typing import Dict, Optional


REQUIRED_ELEMENTS = (
    "webrtcbin",
    "rtph264depay",
    "h264parse",
    "videoconvert",
    "videoscale",
    "fakesink",
)
DECODER_ALTERNATIVES = ("avdec_h264", "vtdec_h264")
DISPLAY_SINK_ALTERNATIVES = ("autovideosink", "osxvideosink")


def _load_gstreamer():
    try:
        import gi

        gi.require_version("Gst", "1.0")
        gi.require_version("GstWebRTC", "1.0")
        gi.require_version("GstSdp", "1.0")
        from gi.repository import Gst

        Gst.init(None)
        return Gst, None
    except (ImportError, ValueError) as exc:
        return None, str(exc)


def _element_status(gst, name: str) -> bool:
    return gst.ElementFactory.find(name) is not None


def main() -> int:
    print("Desktop media environment")
    print("  platform: %s %s" % (platform.system(), platform.machine()))
    print("  python:   %s" % platform.python_version())
    print("  gst CLI:  %s" % (shutil.which("gst-inspect-1.0") or "missing"))

    gst, error = _load_gstreamer()
    if gst is None:
        print("  PyGObject/GStreamer introspection: missing")
        print("  reason: %s" % error)
        print("\nNOT READY: install GStreamer, GstWebRTC/GstSdp and PyGObject bindings.")
        return 1

    version = ".".join(str(part) for part in gst.version())
    print("  GStreamer: %s" % version)

    statuses: Dict[str, bool] = {}
    statuses["nice"] = gst.Registry.get().find_plugin("nice") is not None
    for name in REQUIRED_ELEMENTS + DECODER_ALTERNATIVES + DISPLAY_SINK_ALTERNATIVES:
        statuses[name] = _element_status(gst, name)

    print("\nRequired elements")
    print("  %-18s %s" % ("nice plugin", "ok" if statuses["nice"] else "missing"))
    for name in REQUIRED_ELEMENTS:
        print("  %-18s %s" % (name, "ok" if statuses[name] else "missing"))

    decoder: Optional[str] = next(
        (name for name in DECODER_ALTERNATIVES if statuses[name]), None
    )
    display_sink: Optional[str] = next(
        (name for name in DISPLAY_SINK_ALTERNATIVES if statuses[name]), None
    )
    print("\nAlternatives")
    print("  H.264 decoder: %s" % (decoder or "missing"))
    print("  window sink:   %s" % (display_sink or "missing (optional for fakesink tests)"))

    missing = [name for name in REQUIRED_ELEMENTS if not statuses[name]]
    if not statuses["nice"]:
        missing.insert(1, "nice plugin")
    if decoder is None:
        missing.append("H.264 decoder")
    if missing:
        print("\nNOT READY: missing %s" % ", ".join(missing))
        return 1

    print("\nREADY: headless DesktopGStreamerReceiver tests can run with fakesink.")
    if display_sink is None:
        print("Window output is unavailable, but this does not block headless tests.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
