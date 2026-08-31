"""Deterministic receiver backend for hardware-free development and tests."""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Mapping, Optional

from .base import ReceiverBackend, ReceiverEvent, ReceiverSnapshot, ReceiverState


_START_SEQUENCE = (
    ReceiverState.SIGNALING,
    ReceiverState.NEGOTIATING,
    ReceiverState.CONNECTED,
    ReceiverState.PLAYING,
)


class MockReceiver(ReceiverBackend):
    def __init__(
        self,
        *,
        transition_delay: float = 0.0,
        fail_at: Optional[ReceiverState] = None,
    ) -> None:
        self._transition_delay = transition_delay
        self._fail_at = fail_at
        self._snapshots: Dict[str, ReceiverSnapshot] = {}
        self._tasks: Dict[str, asyncio.Task] = {}
        self._events: asyncio.Queue = asyncio.Queue()

    async def start(
        self,
        session_id: str,
        signaling_url: str,
        media_config: Optional[Mapping[str, Any]] = None,
    ) -> None:
        current = self._snapshots.get(session_id)
        if current and current.state not in {
            ReceiverState.FAILED,
            ReceiverState.STOPPED,
        }:
            raise ValueError(f"receiver session already active: {session_id}")

        await self._set_state(
            session_id,
            ReceiverState.STARTING,
            {
                "signaling_url": signaling_url,
                "media_config": dict(media_config or {}),
            },
        )
        self._tasks[session_id] = asyncio.create_task(
            self._run_start_sequence(session_id),
            name=f"mock-receiver-{session_id}",
        )

    async def stop(self, session_id: str) -> None:
        task = self._tasks.pop(session_id, None)
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        if session_id in self._snapshots:
            await self._set_state(session_id, ReceiverState.STOPPED)

    def status(self, session_id: str) -> Optional[ReceiverSnapshot]:
        return self._snapshots.get(session_id)

    async def next_event(self, timeout: Optional[float] = None) -> ReceiverEvent:
        if timeout is None:
            return await self._events.get()
        return await asyncio.wait_for(self._events.get(), timeout=timeout)

    async def _run_start_sequence(self, session_id: str) -> None:
        try:
            for state in _START_SEQUENCE:
                if self._transition_delay:
                    await asyncio.sleep(self._transition_delay)
                if self._fail_at == state:
                    await self._set_state(
                        session_id,
                        ReceiverState.FAILED,
                        {"failed_at": state.value},
                    )
                    return
                await self._set_state(session_id, state)
        finally:
            self._tasks.pop(session_id, None)

    async def _set_state(
        self,
        session_id: str,
        state: ReceiverState,
        details: Optional[Mapping[str, Any]] = None,
    ) -> None:
        previous = self._snapshots.get(session_id)
        merged_details = dict(previous.details) if previous else {}
        merged_details.update(details or {})
        snapshot = ReceiverSnapshot(
            session_id=session_id,
            state=state,
            backend="mock",
            details=merged_details,
        )
        self._snapshots[session_id] = snapshot
        await self._events.put(
            ReceiverEvent(type=f"receiver.{state.value}", snapshot=snapshot)
        )
