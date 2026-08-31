from __future__ import annotations

import pytest

from receivers import MockReceiver, ReceiverState


async def collect_states(receiver: MockReceiver, count: int) -> list[ReceiverState]:
    states = []
    for _ in range(count):
        event = await receiver.next_event(timeout=1)
        states.append(event.snapshot.state)
    return states


@pytest.mark.asyncio
async def test_mock_receiver_reaches_playing_and_stops() -> None:
    receiver = MockReceiver()

    await receiver.start(
        "session-1",
        "ws://127.0.0.1:8081/internal/receiver",
        {"codec": "H264", "sink": "fake"},
    )

    assert await collect_states(receiver, 5) == [
        ReceiverState.STARTING,
        ReceiverState.SIGNALING,
        ReceiverState.NEGOTIATING,
        ReceiverState.CONNECTED,
        ReceiverState.PLAYING,
    ]
    assert receiver.status("session-1").state == ReceiverState.PLAYING

    await receiver.stop("session-1")
    stopped = await receiver.next_event(timeout=1)
    assert stopped.type == "receiver.stopped"
    assert receiver.status("session-1").state == ReceiverState.STOPPED


@pytest.mark.asyncio
async def test_mock_receiver_supports_failure_injection() -> None:
    receiver = MockReceiver(fail_at=ReceiverState.CONNECTED)

    await receiver.start("session-fail", "ws://127.0.0.1/internal")

    assert await collect_states(receiver, 4) == [
        ReceiverState.STARTING,
        ReceiverState.SIGNALING,
        ReceiverState.NEGOTIATING,
        ReceiverState.FAILED,
    ]
    snapshot = receiver.status("session-fail")
    assert snapshot.state == ReceiverState.FAILED
    assert snapshot.details["failed_at"] == ReceiverState.CONNECTED.value


@pytest.mark.asyncio
async def test_mock_receiver_rejects_duplicate_active_session() -> None:
    receiver = MockReceiver(transition_delay=0.05)
    await receiver.start("duplicate", "ws://127.0.0.1/internal")

    with pytest.raises(ValueError, match="already active"):
        await receiver.start("duplicate", "ws://127.0.0.1/internal")

    await receiver.stop("duplicate")
