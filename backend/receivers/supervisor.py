"""Single-active-session receiver lifecycle coordinator."""

from __future__ import annotations

import asyncio
from typing import Any, Callable, Dict, Mapping, Optional

from .base import ReceiverBackend, ReceiverEvent, ReceiverSnapshot, ReceiverState


class ReceiverSupervisor:
    """Owns receiver lifecycle without knowing hardware implementation details."""

    def __init__(
        self,
        backend: ReceiverBackend,
        event_handler: Optional[Callable[[ReceiverEvent], None]] = None,
    ) -> None:
        self._backend = backend
        self._active_session_id: Optional[str] = None
        self._lock = asyncio.Lock()
        self._event_handler = event_handler
        self._observer_tasks: Dict[str, asyncio.Task] = {}

    @property
    def active_session_id(self) -> Optional[str]:
        return self._active_session_id

    @property
    def backend(self) -> ReceiverBackend:
        return self._backend

    def set_event_handler(
        self, event_handler: Optional[Callable[[ReceiverEvent], None]]
    ) -> None:
        self._event_handler = event_handler

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
                await self._finish_observer(previous_session)

            await self._backend.start(session_id, signaling_url, media_config)
            self._active_session_id = session_id
            self._observer_tasks[session_id] = asyncio.create_task(
                self._observe(session_id),
                name=f"receiver-observer-{session_id}",
            )

    async def stop(self, session_id: str) -> None:
        async with self._lock:
            if self._active_session_id != session_id:
                return
            await self._backend.stop(session_id)
            self._active_session_id = None
            await self._finish_observer(session_id)

    async def stop_all(self) -> None:
        async with self._lock:
            if self._active_session_id is None:
                return
            session_id = self._active_session_id
            await self._backend.stop(session_id)
            self._active_session_id = None
            await self._finish_observer(session_id)

    def status(self, session_id: Optional[str] = None) -> Optional[ReceiverSnapshot]:
        target = session_id or self._active_session_id
        if target is None:
            return None
        return self._backend.status(target)

    async def _observe(self, session_id: str) -> None:
        try:
            while True:
                event = await self._backend.next_event()
                if event.snapshot.session_id != session_id:
                    continue
                if self._event_handler is not None:
                    self._event_handler(event)
                if event.snapshot.state in {
                    ReceiverState.FAILED,
                    ReceiverState.STOPPED,
                }:
                    if (
                        event.snapshot.state == ReceiverState.FAILED
                        and self._active_session_id == session_id
                    ):
                        self._active_session_id = None
                    return
        except asyncio.CancelledError:
            raise
        finally:
            if self._observer_tasks.get(session_id) is asyncio.current_task():
                self._observer_tasks.pop(session_id, None)

    async def _finish_observer(self, session_id: str) -> None:
        task = self._observer_tasks.get(session_id)
        if task is None:
            return
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=0.5)
        except asyncio.TimeoutError:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
