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


async def wait_for_device_state(client, expected: str, timeout: float = 1.0):
    async def poll():
        while True:
            response = await client.get("/api/device/runtime")
            snapshot = await response.json()
            if snapshot["state"] == expected:
                return snapshot
            await asyncio.sleep(0)

    return await asyncio.wait_for(poll(), timeout=timeout)


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
    runtime = await wait_for_device_state(client, "casting")

    playing = backend.status(session_id)
    assert playing.backend == "mock"
    assert playing.details["media_config"] == {"codec": "H264"}
    assert supervisor.active_session_id == session_id
    assert runtime["active_session_id"] == session_id
    assert runtime["metrics"]["sessions_played"] == 1

    response = await client.get("/api/receiver/status")
    status = await response.json()
    assert status["configured"] is True
    assert status["active_session_id"] == session_id
    assert status["session"]["state"] == "playing"
    assert status["session"]["backend"] == "mock"

    await sender.close()
    await wait_for_state(supervisor, session_id, ReceiverState.STOPPED)
    runtime = await wait_for_device_state(client, "ready")
    assert supervisor.active_session_id is None
    assert runtime["metrics"]["sessions_completed"] == 1

    response = await client.get(
        "/api/receiver/status", params={"session_id": session_id}
    )
    status = await response.json()
    assert status["active_session_id"] is None
    assert status["session"]["state"] == "stopped"


@pytest.mark.asyncio
async def test_legacy_hdmi_status_drives_product_state(
    aiohttp_client, monkeypatch
) -> None:
    async def fake_start(session_id, device_runtime=None, display_arbiter=None):
        server._display_room_id = session_id

    async def fake_stop(restore_standby=True):
        server._display_process = None
        server._display_room_id = None

    monkeypatch.setattr(server, "_auto_start_display", fake_start)
    monkeypatch.setattr(server, "_stop_display", fake_stop)
    server._display_process = None
    server._display_room_id = None

    app = server.create_app()
    app.on_startup.clear()
    app.on_cleanup.clear()
    client = await aiohttp_client(app)
    sender = await client.ws_connect("/ws")
    viewer = await client.ws_connect("/ws")
    session_id = "legacy-hdmi-session"

    await sender.send_json({"t": "offer", "s": session_id, "sdp": "v=0\r\n"})
    await wait_for_device_state(client, "connecting")
    await viewer.send_json({"t": "reg", "s": session_id})
    registration = await viewer.receive_json()
    assert registration["t"] == "reg_ok"

    await viewer.send_json({
        "t": "receiver_status",
        "s": session_id,
        "state": "playing",
        "details": {"codec": "VP8", "plane_id": 71},
    })
    runtime = await wait_for_device_state(client, "casting")
    assert runtime["active_session_id"] == session_id
    assert runtime["metrics"]["sessions_played"] == 1

    await sender.send_json({"t": "stop", "s": session_id})
    runtime = await wait_for_device_state(client, "ready")
    assert runtime["metrics"]["sessions_completed"] == 1

    await viewer.close()
    await sender.close()
