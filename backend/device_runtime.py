"""Device-level state, telemetry, and adaptation decisions.

This module deliberately contains no RK3588 or GStreamer imports.  Hardware
workers report receiver events and telemetry here; the control plane exposes a
stable product-level view to the standby screen and management UI.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, Mapping, Optional

from receivers import ReceiverEvent, ReceiverSnapshot, ReceiverState


class DeviceState(str, Enum):
    BOOTING = "booting"
    READY = "ready"
    CONNECTING = "connecting"
    CASTING = "casting"
    DEGRADED = "degraded"
    FAULT = "fault"
    STOPPING = "stopping"


@dataclass(frozen=True)
class StreamProfile:
    name: str
    width: int
    height: int
    framerate: int
    max_bitrate_kbps: int

    def as_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "width": self.width,
            "height": self.height,
            "framerate": self.framerate,
            "max_bitrate_kbps": self.max_bitrate_kbps,
        }


class AdaptationPolicy:
    """Pure decision function; applying a profile remains the sender's job."""

    NORMAL = StreamProfile("1080p30", 1920, 1080, 30, 8000)
    CONSTRAINED = StreamProfile("720p30", 1280, 720, 30, 4500)
    CRITICAL = StreamProfile("720p20", 1280, 720, 20, 2500)

    def evaluate(self, telemetry: Mapping[str, Any]) -> Dict[str, Any]:
        temperature = _number(telemetry.get("temperature_c"))
        cpu = _number(telemetry.get("cpu_percent"))
        packet_loss = _number(telemetry.get("packet_loss_percent"))
        dropped_frames = _number(telemetry.get("dropped_frame_percent"))

        critical_reasons = []
        constrained_reasons = []
        if temperature is not None:
            if temperature >= 85:
                critical_reasons.append("temperature>=85C")
            elif temperature >= 75:
                constrained_reasons.append("temperature>=75C")
        if cpu is not None:
            if cpu >= 95:
                critical_reasons.append("cpu>=95%")
            elif cpu >= 80:
                constrained_reasons.append("cpu>=80%")
        if packet_loss is not None:
            if packet_loss >= 10:
                critical_reasons.append("packet_loss>=10%")
            elif packet_loss >= 3:
                constrained_reasons.append("packet_loss>=3%")
        if dropped_frames is not None:
            if dropped_frames >= 10:
                critical_reasons.append("dropped_frames>=10%")
            elif dropped_frames >= 3:
                constrained_reasons.append("dropped_frames>=3%")

        if critical_reasons:
            tier = "critical"
            profile = self.CRITICAL
            reasons = critical_reasons + constrained_reasons
        elif constrained_reasons:
            tier = "constrained"
            profile = self.CONSTRAINED
            reasons = constrained_reasons
        else:
            tier = "normal"
            profile = self.NORMAL
            reasons = []

        return {
            "tier": tier,
            "recommended_profile": profile.as_dict(),
            "reasons": reasons,
            "automatic_apply": False,
        }


class DeviceRuntime:
    """Product-level state machine and session metrics accumulator."""

    def __init__(
        self,
        *,
        clock: Callable[[], float] = time.monotonic,
        policy: Optional[AdaptationPolicy] = None,
    ) -> None:
        self._clock = clock
        self._started_at = clock()
        self._state = DeviceState.READY
        self._state_since = self._started_at
        self._active_session_id: Optional[str] = None
        self._session_started_at: Optional[float] = None
        self._last_receiver_state: Optional[str] = None
        self._last_error: Optional[Dict[str, Any]] = None
        self._last_telemetry: Dict[str, Any] = {}
        self._stream_stats: Dict[str, Any] = {}
        self._policy = policy or AdaptationPolicy()
        self._metrics = {
            "sessions_started": 0,
            "sessions_played": 0,
            "sessions_completed": 0,
            "sessions_failed": 0,
            "last_time_to_play_ms": None,
        }
        self._seen_starting_sessions = set()
        self._seen_playing_sessions = set()
        self._seen_terminal_sessions = set()

    @property
    def state(self) -> DeviceState:
        return self._state

    @property
    def active_session_id(self) -> Optional[str]:
        return self._active_session_id

    @property
    def available(self) -> bool:
        return self._state in {DeviceState.READY, DeviceState.DEGRADED}

    def handle_receiver_event(self, event: ReceiverEvent) -> None:
        snapshot = event.snapshot
        sid = snapshot.session_id
        state = snapshot.state
        self._last_receiver_state = state.value

        if state == ReceiverState.STARTING:
            if sid not in self._seen_starting_sessions:
                self._seen_starting_sessions.add(sid)
                self._metrics["sessions_started"] += 1
            self._active_session_id = sid
            self._session_started_at = self._clock()
            self._transition(DeviceState.CONNECTING)
        elif state in {
            ReceiverState.SIGNALING,
            ReceiverState.NEGOTIATING,
            ReceiverState.CONNECTED,
        }:
            self._active_session_id = sid
            self._transition(DeviceState.CONNECTING)
        elif state == ReceiverState.PLAYING:
            if sid not in self._seen_playing_sessions:
                self._seen_playing_sessions.add(sid)
                self._metrics["sessions_played"] += 1
                if self._session_started_at is not None:
                    elapsed = (self._clock() - self._session_started_at) * 1000
                    self._metrics["last_time_to_play_ms"] = round(elapsed, 1)
            self._active_session_id = sid
            self._transition(DeviceState.CASTING)
        elif state == ReceiverState.FAILED:
            if sid not in self._seen_terminal_sessions:
                self._seen_terminal_sessions.add(sid)
                self._metrics["sessions_failed"] += 1
            self._active_session_id = None
            self._last_error = {
                "session_id": sid,
                "details": dict(snapshot.details),
            }
            self._transition(DeviceState.DEGRADED)
        elif state == ReceiverState.STOPPED:
            if sid not in self._seen_terminal_sessions:
                self._seen_terminal_sessions.add(sid)
                self._metrics["sessions_completed"] += 1
            if self._active_session_id == sid:
                self._active_session_id = None
            self._session_started_at = None
            self._transition(DeviceState.READY)

    def begin_session(self, session_id: str, backend: str = "legacy-hdmi") -> None:
        self._emit_compat_event(session_id, ReceiverState.STARTING, backend)

    def mark_session_playing(
        self,
        session_id: str,
        details: Optional[Mapping[str, Any]] = None,
        backend: str = "legacy-hdmi",
    ) -> None:
        self._emit_compat_event(
            session_id, ReceiverState.PLAYING, backend, details
        )

    def fail_session(
        self,
        session_id: str,
        details: Optional[Mapping[str, Any]] = None,
        backend: str = "legacy-hdmi",
    ) -> None:
        self._emit_compat_event(
            session_id, ReceiverState.FAILED, backend, details
        )

    def end_session(self, session_id: str, backend: str = "legacy-hdmi") -> None:
        self._emit_compat_event(session_id, ReceiverState.STOPPED, backend)

    def update_telemetry(self, telemetry: Mapping[str, Any]) -> Dict[str, Any]:
        allowed = {
            "temperature_c",
            "cpu_percent",
            "memory_percent",
            "packet_loss_percent",
            "dropped_frame_percent",
            "fps",
            "bitrate_kbps",
        }
        self._last_telemetry = {
            key: value for key, value in telemetry.items() if key in allowed
        }
        return self._policy.evaluate(self._last_telemetry)

    def record_stream_stats(self, session_id: str, stats: Mapping[str, Any]) -> Dict[str, Any]:
        allowed = {
            "fps",
            "kbps",
            "frames_encoded",
            "frames_sent",
            "packets_lost",
            "packets_received",
            "quality_limit",
            "rtt_ms",
        }
        self._stream_stats = {key: stats.get(key) for key in allowed if key in stats}
        self._stream_stats["session_id"] = session_id
        received = _number(self._stream_stats.get("packets_received")) or 0
        lost = _number(self._stream_stats.get("packets_lost")) or 0
        self.update_telemetry(
            {
                "fps": self._stream_stats.get("fps"),
                "bitrate_kbps": self._stream_stats.get("kbps"),
                "packet_loss_percent": (
                    round(lost * 100 / (lost + received), 3)
                    if lost + received
                    else 0
                ),
            }
        )
        return self.performance_snapshot()

    def performance_snapshot(self) -> Dict[str, Any]:
        fps = _number(self._stream_stats.get("fps"))
        loss = _number(self._last_telemetry.get("packet_loss_percent")) or 0
        if fps is None:
            verdict = "awaiting_stream"
        elif fps >= 25 and loss < 3:
            verdict = "pass"
        else:
            verdict = "investigate"
        return {
            "sender": dict(self._stream_stats),
            "telemetry": dict(self._last_telemetry),
            "verdict": verdict,
            "acceptance": {
                "target_fps": 30,
                "max_packet_loss_percent": 3,
                "note": "End-to-end latency needs a camera or timestamp test.",
            },
        }

    def mark_fault(self, reason: str) -> None:
        self._last_error = {"reason": reason}
        self._transition(DeviceState.FAULT)

    def mark_stopping(self) -> None:
        self._transition(DeviceState.STOPPING)

    def snapshot(self) -> Dict[str, Any]:
        now = self._clock()
        metrics = dict(self._metrics)
        metrics["service_uptime_seconds"] = round(now - self._started_at, 1)
        if self._session_started_at is not None:
            metrics["active_session_seconds"] = round(
                now - self._session_started_at, 1
            )
        else:
            metrics["active_session_seconds"] = None
        return {
            "state": self._state.value,
            "state_duration_seconds": round(now - self._state_since, 1),
            "available": self.available,
            "active_session_id": self._active_session_id,
            "receiver_state": self._last_receiver_state,
            "metrics": metrics,
            "telemetry": dict(self._last_telemetry),
            "adaptation": self._policy.evaluate(self._last_telemetry),
            "performance": self.performance_snapshot(),
            "last_error": self._last_error,
        }

    def _transition(self, state: DeviceState) -> None:
        if state != self._state:
            self._state = state
            self._state_since = self._clock()

    def _emit_compat_event(
        self,
        session_id: str,
        state: ReceiverState,
        backend: str,
        details: Optional[Mapping[str, Any]] = None,
    ) -> None:
        snapshot = ReceiverSnapshot(
            session_id=session_id,
            state=state,
            backend=backend,
            details=dict(details or {}),
        )
        self.handle_receiver_event(
            ReceiverEvent(type=f"receiver.{state.value}", snapshot=snapshot)
        )


def _number(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
