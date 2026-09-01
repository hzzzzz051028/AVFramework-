"""One-owner policy for the HDMI display plane."""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class DisplayLease:
    source: str
    session_id: str
    acquired_at: float


class DisplayArbiter:
    """Discovery may coexist; the physical HDMI plane has one owner."""
    SOURCES = {"webrtc", "airplay", "miracast"}

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._lease: DisplayLease | None = None
        self._last_transition: dict | None = None

    def acquire(self, source: str, session_id: str, *, replace: bool = True) -> dict:
        if source not in self.SOURCES:
            raise ValueError("unsupported display source")
        if not session_id:
            raise ValueError("session_id is required")
        previous = self._lease
        if previous and (previous.source != source or previous.session_id != session_id) and not replace:
            return {"accepted": False, "reason": "display_busy", "active": self._as_dict(previous)}
        self._lease = DisplayLease(source, session_id, self._clock())
        self._last_transition = {"action": "acquire", "source": source, "session_id": session_id,
                                 "replaced": self._as_dict(previous)}
        return {"accepted": True, "replaced": self._as_dict(previous), "active": self._as_dict(self._lease)}

    def release(self, source: str | None = None, session_id: str | None = None) -> bool:
        lease = self._lease
        if lease is None or (source and lease.source != source) or (session_id and lease.session_id != session_id):
            return False
        self._lease = None
        self._last_transition = {"action": "release", "source": lease.source, "session_id": lease.session_id}
        return True

    def snapshot(self) -> dict:
        active = self._as_dict(self._lease)
        if active:
            active["duration_seconds"] = round(self._clock() - self._lease.acquired_at, 1)
        return {"active": active, "sources": {name: {"discovery_can_remain": True, "display_exclusive": True}
                for name in sorted(self.SOURCES)}, "last_transition": self._last_transition}

    @staticmethod
    def _as_dict(lease: DisplayLease | None) -> dict | None:
        return None if lease is None else {"source": lease.source, "session_id": lease.session_id}
