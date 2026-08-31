#!/usr/bin/env python3
"""Run headless GStreamer media-pipeline checks without RK3588 hardware."""

from __future__ import annotations

import argparse
import sys
import time


def load_gst():
    try:
        import gi

        gi.require_version("Gst", "1.0")
        gi.require_version("GLib", "2.0")
        from gi.repository import GLib, Gst

        Gst.init(None)
        return GLib, Gst
    except Exception as exc:
        raise RuntimeError("PyGObject/GStreamer unavailable: %s" % exc)


def run_pipeline(glib, gst, description: str, duration: float) -> dict:
    pipeline = gst.parse_launch(description)
    sink = pipeline.get_by_name("sink")
    if sink is None:
        raise RuntimeError("pipeline must contain fakesink name=sink")

    result = {"frames": 0, "error": None, "duration": 0.0}
    loop = glib.MainLoop()
    started_at = time.monotonic()

    def on_handoff(_sink, _buffer, _pad):
        result["frames"] += 1

    def on_message(_bus, message):
        if message.type == gst.MessageType.ERROR:
            error, debug = message.parse_error()
            result["error"] = "%s%s" % (error, (": " + debug) if debug else "")
            loop.quit()
        elif message.type == gst.MessageType.EOS:
            loop.quit()

    sink.connect("handoff", on_handoff)
    bus = pipeline.get_bus()
    bus.add_signal_watch()
    bus.connect("message", on_message)
    pipeline.set_state(gst.State.PLAYING)
    glib.timeout_add(int(duration * 1000), loop.quit)
    loop.run()
    result["duration"] = time.monotonic() - started_at
    pipeline.set_state(gst.State.NULL)
    bus.remove_signal_watch()
    if result["error"]:
        raise RuntimeError(result["error"])
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=float, default=2.0)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--fps", type=int, default=30)
    args = parser.parse_args()
    try:
        glib, gst = load_gst()
        raw = (
            "videotestsrc is-live=true pattern=ball ! "
            "video/x-raw,width={w},height={h},framerate={fps}/1 ! "
            "videoconvert ! fakesink name=sink sync=false signal-handoffs=true"
        ).format(w=args.width, h=args.height, fps=args.fps)
        h264 = (
            "videotestsrc is-live=true pattern=ball ! "
            "video/x-raw,width={w},height={h},framerate={fps}/1 ! "
            "x264enc tune=zerolatency speed-preset=ultrafast key-int-max={fps} bitrate=4000 ! "
            "h264parse ! avdec_h264 ! videoconvert ! "
            "fakesink name=sink sync=false signal-handoffs=true"
        ).format(w=args.width, h=args.height, fps=args.fps)
        checks = (("raw", raw), ("h264 round-trip", h264))
        for name, description in checks:
            result = run_pipeline(glib, gst, description, args.seconds)
            fps = result["frames"] / result["duration"] if result["duration"] else 0
            print("%s: %d frames, %.1f fps" % (name, result["frames"], fps))
            if result["frames"] < max(1, int(args.seconds * args.fps * 0.5)):
                raise RuntimeError("%s produced too few frames" % name)
    except Exception as exc:
        print("MEDIA PIPELINE CHECK FAILED: %s" % exc)
        return 1
    print("MEDIA PIPELINE CHECK PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
