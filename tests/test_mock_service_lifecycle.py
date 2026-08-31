from __future__ import annotations

import asyncio

import pytest

import server
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


@pytest.fixture
async def mock_service(aiohttp_client):
    backend = MockReceiver()
    supervisor = ReceiverSupervisor(backend)
    app = server.create_app(receiver_supervisor=supervisor)
    app.on_startup.clear()
    app.on_cleanup.clear()
    client = await aiohttp_client(app)
    return client, backend, supervisor


@pytest.mark.asyncio
async def test_websocket_offer_drives_mock_receiver_lifecycle(mock_service) -> None:
    client, backend, supervisor = mock_service
    session_id = "mock-service-session"
    sender = await client.ws_connect("/ws")

    await sender.send_json({"t": "offer", "s": session_id, "sdp": "v=0\r\n"})
    await wait_for_state(supervisor, session_id, ReceiverState.PLAYING)

    playing = backend.status(session_id)
    assert playing.backend == "mock"
    assert playing.details["media_config"] == {"codec": "H264"}
    assert supervisor.active_session_id == session_id

    response = await client.get("/api/receiver/status")
    status = await response.json()
    assert status["configured"] is True
    assert status["active_session_id"] == session_id
    assert status["session"]["state"] == "playing"
    assert status["session"]["backend"] == "mock"

    await sender.close()
    await wait_for_state(supervisor, session_id, ReceiverState.STOPPED)
    assert supervisor.active_session_id is None

    response = await client.get(
        "/api/receiver/status", params={"session_id": session_id}
    )
    status = await response.json()
    assert status["active_session_id"] is None
    assert status["session"]["state"] == "stopped"
