#!/usr/bin/env python3
"""Desktop WebRTC receiver worker using GStreamer and fakesink."""

from __future__ import annotations

import asyncio
import sys

from hdmi_receiver import NativeReceiver


class DesktopReceiver(NativeReceiver):
    """Reuse signaling/ICE handling while replacing KMS with a headless sink."""

    def _on_pad_added(self, element, pad):
        if not pad.name.startswith("src_"):
            return
        src_caps = pad.query_caps(None)
        structure = src_caps.get_structure(0)
        encoding = (
            structure.get_string("encoding-name")
            if structure.has_field("encoding-name")
            else ""
        )
        self._cleanup_decode_chain()

        depay = decoder = None
        if encoding == "H264":
            depay = self._make_element("rtph264depay")
            decoder = self._make_element("avdec_h264")
        elif encoding == "H265":
            depay = self._make_element("rtph265depay")
            decoder = self._make_element("avdec_h265")
        if not depay or not decoder:
            return

        convert = self._make_element("videoconvert")
        sink = self._make_element("fakesink")
        if not convert or not sink:
            return
        sink.set_property("sync", False)
        sink.set_property("signal-handoffs", True)
        sink.connect("handoff", self._on_frame)
        elements = [depay, decoder, convert, sink]
        for item in elements:
            self.pipe.add(item)
        if not (depay.link(decoder) and decoder.link(convert) and convert.link(sink)):
            for item in elements:
                self.pipe.remove(item)
            return
        if pad.link(depay.get_static_pad("sink")) != 0:
            for item in elements:
                self.pipe.remove(item)
            return
        self._decode_elems = elements
        for item in elements:
            item.sync_state_with_parent()

    def _on_frame(self, sink, buffer, pad):
        self._frame_count = getattr(self, "_frame_count", 0) + 1
        if self._frame_count == 1 or self._frame_count % 30 == 0:
            print("[DESKTOP] decoded_frames=%d" % self._frame_count, flush=True)

    @staticmethod
    def _make_element(name):
        from gi.repository import Gst

        return Gst.ElementFactory.make(name, None)


async def main() -> None:
    if len(sys.argv) < 3:
        raise SystemExit("Usage: desktop_receiver_worker.py <session_id> <ws_url>")
    receiver = DesktopReceiver(sys.argv[1], sys.argv[2])
    await receiver.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
