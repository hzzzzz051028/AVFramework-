"""Desktop GStreamer receiver capability gate.

The media worker is intentionally not started until the host passes the
GStreamer probe.  Keeping this check behind the ReceiverBackend contract lets
the control plane fail clearly instead of importing GI at server startup.
"""

from __future__ import annotations

import asyncio
import os
import sys
from typing import Any, Dict, Mapping, Optional, Tuple

from .base import ReceiverBackend, ReceiverEvent, ReceiverSnapshot, ReceiverState


class DesktopGStreamerReceiver(ReceiverBackend):
    """Fail-closed desktop backend scaffold for the second development stage."""

    def __init__(self) -> None:
        self._snapshots: Dict[str, ReceiverSnapshot] = {}
        self._events: asyncio.Queue = asyncio.Queue()
        self._processes: Dict[str, asyncio.subprocess.Process] = {}

    async def start(
        self,
        session_id: str,
        signaling_url: str,
        media_config: Optional[Mapping[str, Any]] = None,
    ) -> None:
        await self._set_state(
            session_id,
            ReceiverState.STARTING,
            {
                "signaling_url": signaling_url,
                "media_config": dict(media_config or {}),
            },
        )
        available, details = self.probe()
        if not available:
            details["reason"] = "gstreamer_unavailable"
            await self._set_state(session_id, ReceiverState.FAILED, details)
            return

        worker = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "desktop_receiver_worker.py")
        )
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            worker,
            session_id,
            signaling_url,
            stdin=asyncio.subprocess.DEVNULL,
        )
        self._processes[session_id] = process
        await self._set_state(session_id, ReceiverState.SIGNALING, details)

    async def stop(self, session_id: str) -> None:
        process = self._processes.pop(session_id, None)
        if process and process.returncode is None:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
        if session_id in self._snapshots:
            await self._set_state(session_id, ReceiverState.STOPPED)

    def status(self, session_id: str) -> Optional[ReceiverSnapshot]:
        return self._snapshots.get(session_id)

    async def next_event(self, timeout: Optional[float] = None) -> ReceiverEvent:
        if timeout is None:
            return await self._events.get()
        return await asyncio.wait_for(self._events.get(), timeout=timeout)

    @staticmethod
    def probe() -> Tuple[bool, Dict[str, Any]]:
        """Return availability without raising GI import errors."""
        try:
            import gi

            gi.require_version("Gst", "1.0")
            gi.require_version("GstWebRTC", "1.0")
            gi.require_version("GstSdp", "1.0")
            from gi.repository import Gst

            Gst.init(None)
            required = (
                "webrtcbin",
                "rtph264depay",
                "h264parse",
                "videoconvert",
                "videoscale",
                "fakesink",
            )
            missing = [
                name for name in required if Gst.ElementFactory.find(name) is None
            ]
            if Gst.Registry.get().find_plugin("nice") is None:
                missing.insert(1, "nice plugin")
            decoder = next(
                (
                    name
                    for name in ("avdec_h264", "vtdec_h264")
                    if Gst.ElementFactory.find(name) is not None
                ),
                None,
            )
            if decoder is None:
                missing.append("H.264 decoder")
            details = {"missing": missing, "decoder": decoder}
            return not missing, details
        except (ImportError, ValueError) as exc:
            return False, {"missing": ["PyGObject/GStreamer"], "error": str(exc)}

    async def _set_state(
        self,
        session_id: str,
        state: ReceiverState,
        details: Optional[Mapping[str, Any]] = None,
    ) -> None:
        previous = self._snapshots.get(session_id)
        merged = dict(previous.details) if previous else {}
        merged.update(details or {})
        snapshot = ReceiverSnapshot(
            session_id=session_id,
            state=state,
            backend="desktop",
            details=merged,
        )
        self._snapshots[session_id] = snapshot
        await self._events.put(
            ReceiverEvent(type="receiver.%s" % state.value, snapshot=snapshot)
        )
