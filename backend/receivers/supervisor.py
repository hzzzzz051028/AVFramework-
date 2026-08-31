"""Single-active-session receiver lifecycle coordinator."""

from __future__ import annotations

import asyncio
from typing import Any, Mapping, Optional

from .base import ReceiverBackend, ReceiverSnapshot


class ReceiverSupervisor:
    """Owns receiver lifecycle without knowing hardware implementation details."""

    def __init__(self, backend: ReceiverBackend) -> None:
        self._backend = backend
        self._active_session_id: Optional[str] = None
        self._lock = asyncio.Lock()

    @property
    def active_session_id(self) -> Optional[str]:
        return self._active_session_id

    @property
    def backend(self) -> ReceiverBackend:
        return self._backend

    async def start(
        self,
        session_id: str,
        signaling_url: str,
        media_config: Optional[Mapping[str, Any]] = None,
    ) -> None:
        async with self._lock:
            if self._active_session_id == session_id:
                return

            previous_session = self._active_session_id
            if previous_session is not None:
                await self._backend.stop(previous_session)
                self._active_session_id = None

            await self._backend.start(session_id, signaling_url, media_config)
            self._active_session_id = session_id

    async def stop(self, session_id: str) -> None:
        async with self._lock:
            if self._active_session_id != session_id:
                return
            await self._backend.stop(session_id)
            self._active_session_id = None

    async def stop_all(self) -> None:
        async with self._lock:
            if self._active_session_id is None:
                return
            session_id = self._active_session_id
            await self._backend.stop(session_id)
            self._active_session_id = None

    def status(self, session_id: Optional[str] = None) -> Optional[ReceiverSnapshot]:
        target = session_id or self._active_session_id
        if target is None:
            return None
        return self._backend.status(target)
