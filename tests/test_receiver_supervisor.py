from __future__ import annotations

import asyncio

import pytest

from receivers import MockReceiver, ReceiverState, ReceiverSupervisor


async def wait_for_state(
    supervisor: ReceiverSupervisor,
    session_id: str,
    expected: ReceiverState,
    timeout: float = 1.0,
) -> None:
    async def poll() -> None:
        while True:
            snapshot = supervisor.status(session_id)
            if snapshot and snapshot.state == expected:
                return
            await asyncio.sleep(0)

    await asyncio.wait_for(poll(), timeout=timeout)


@pytest.mark.asyncio
async def test_supervisor_switches_single_active_session() -> None:
    backend = MockReceiver()
    supervisor = ReceiverSupervisor(backend)

    await supervisor.start("first", "ws://127.0.0.1/internal")
    await wait_for_state(supervisor, "first", ReceiverState.PLAYING)

    await supervisor.start("second", "ws://127.0.0.1/internal")
    assert backend.status("first").state == ReceiverState.STOPPED
    assert supervisor.active_session_id == "second"
    await wait_for_state(supervisor, "second", ReceiverState.PLAYING)

    await supervisor.stop_all()
    assert backend.status("second").state == ReceiverState.STOPPED
    assert supervisor.active_session_id is None
