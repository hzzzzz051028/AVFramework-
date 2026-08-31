"""Hardware-independent receiver contracts.

The control service depends on this module instead of importing GStreamer or
RK3588-specific APIs. Concrete backends may run in-process during tests or
supervise a separate media worker in production.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Optional


class ReceiverState(str, Enum):
    IDLE = "idle"
    STARTING = "starting"
    SIGNALING = "signaling"
    NEGOTIATING = "negotiating"
    CONNECTED = "connected"
    PLAYING = "playing"
    FAILED = "failed"
    STOPPED = "stopped"


@dataclass(frozen=True)
class ReceiverSnapshot:
    session_id: str
    state: ReceiverState
    backend: str
    details: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ReceiverEvent:
    type: str
    snapshot: ReceiverSnapshot


class ReceiverBackend(ABC):
    """Lifecycle boundary between the control plane and a media receiver."""

    @abstractmethod
    async def start(
        self,
        session_id: str,
        signaling_url: str,
        media_config: Optional[Mapping[str, Any]] = None,
    ) -> None:
        """Start receiving media for a session without blocking until playback."""

    @abstractmethod
    async def stop(self, session_id: str) -> None:
        """Stop a receiver session and release its resources."""

    @abstractmethod
    def status(self, session_id: str) -> Optional[ReceiverSnapshot]:
        """Return the latest immutable session snapshot."""

    @abstractmethod
    async def next_event(self, timeout: Optional[float] = None) -> ReceiverEvent:
        """Wait for the next lifecycle event from this backend."""
