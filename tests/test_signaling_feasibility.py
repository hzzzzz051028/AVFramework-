from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock

import pytest

import server


@pytest.fixture(autouse=True)
def reset_signaling_state(monkeypatch):
    server.rooms.clear()
    server.ws_to_client.clear()
    server.client_to_ws.clear()
    server.client_to_room.clear()
    server.client_to_peer.clear()
    server.ws_sessions.clear()
    server._next_client_id[0] = 0
    monkeypatch.setattr(server, "_auto_start_display", AsyncMock())
    yield
    server.rooms.clear()
    server.ws_to_client.clear()
    server.client_to_ws.clear()
    server.client_to_room.clear()
    server.client_to_peer.clear()
    server.ws_sessions.clear()


@pytest.fixture
async def signaling_client(aiohttp_client):
    app = server.create_app()
    app.on_startup.clear()
    app.on_cleanup.clear()
    return await aiohttp_client(app)


async def receive_json(ws, timeout: float = 1.0) -> dict:
    message = await asyncio.wait_for(ws.receive(), timeout=timeout)
    return json.loads(message.data)


@pytest.mark.asyncio
async def test_short_protocol_offer_answer_and_bidirectional_ice(signaling_client) -> None:
    sender = await signaling_client.ws_connect("/ws")
    session_id = "feasibility-room"
    offer_sdp = "v=0\r\na=mock-offer\r\n"

    await sender.send_json({"t": "offer", "s": session_id, "sdp": offer_sdp})

    viewer = await signaling_client.ws_connect("/ws")
    await viewer.send_json({"t": "reg", "s": session_id})

    registration = await receive_json(viewer)
    assert registration["t"] == "reg_ok"
    assert registration["s"] == session_id
    assert registration["sender_ip"] == "127.0.0.1"

    new_viewer = await receive_json(sender)
    assert new_viewer == {"t": "new_viewer", "s": session_id}

    await sender.send_json({"t": "offer", "s": session_id, "sdp": offer_sdp})
    relayed_offer = await receive_json(viewer)
    assert relayed_offer == {"t": "offer", "s": session_id, "sdp": offer_sdp}

    answer_sdp = "v=0\r\na=mock-answer\r\n"
    await viewer.send_json({"t": "answer", "s": session_id, "sdp": answer_sdp})
    relayed_answer = await receive_json(sender)
    assert relayed_answer == {"t": "answer", "s": session_id, "sdp": answer_sdp}

    sender_candidate = "candidate:sender 1 udp 1 192.0.2.1 5000 typ host"
    await sender.send_json(
        {"t": "ice", "s": session_id, "c": sender_candidate, "m": "0", "l": 0}
    )
    assert await receive_json(viewer) == {
        "t": "ice",
        "s": session_id,
        "c": sender_candidate,
        "m": "0",
        "l": 0,
    }

    viewer_candidate = "candidate:viewer 1 udp 1 192.0.2.2 5001 typ host"
    await viewer.send_json(
        {"t": "ice", "s": session_id, "c": viewer_candidate, "m": "0", "l": 0}
    )
    assert await receive_json(sender) == {
        "t": "ice",
        "s": session_id,
        "c": viewer_candidate,
        "m": "0",
        "l": 0,
    }

    await viewer.close()
    await sender.close()


@pytest.mark.asyncio
async def test_viewer_cannot_join_unknown_room(signaling_client) -> None:
    viewer = await signaling_client.ws_connect("/ws")
    await viewer.send_json({"t": "reg", "s": "missing-room"})

    response = await receive_json(viewer)
    assert response["t"] == "error"
    assert response["s"] == "missing-room"
    assert "room not found" in response["msg"]

    await viewer.close()


@pytest.mark.asyncio
async def test_sender_ice_is_replayed_when_viewer_joins_late(signaling_client) -> None:
    sender = await signaling_client.ws_connect("/ws")
    session_id = "late-viewer"
    candidate = "candidate:early 1 udp 1 192.0.2.3 5002 typ host"

    await sender.send_json({"t": "offer", "s": session_id, "sdp": "v=0\r\n"})
    await sender.send_json(
        {"t": "ice", "s": session_id, "c": candidate, "m": "0", "l": 0}
    )

    viewer = await signaling_client.ws_connect("/ws")
    await viewer.send_json({"t": "reg", "s": session_id})

    assert (await receive_json(viewer))["t"] == "reg_ok"
    assert await receive_json(viewer) == {
        "t": "ice",
        "s": session_id,
        "c": candidate,
        "m": "0",
        "l": 0,
    }
    assert await receive_json(sender) == {"t": "new_viewer", "s": session_id}

    await viewer.close()
    await sender.close()


@pytest.mark.asyncio
async def test_sender_disconnect_notifies_viewer_and_cleans_room(signaling_client) -> None:
    sender = await signaling_client.ws_connect("/ws")
    session_id = "disconnect-room"
    await sender.send_json({"t": "offer", "s": session_id, "sdp": "v=0\r\n"})

    viewer = await signaling_client.ws_connect("/ws")
    await viewer.send_json({"t": "reg", "s": session_id})
    await receive_json(viewer)
    await receive_json(sender)

    await sender.close()
    assert await receive_json(viewer) == {"t": "stopped", "s": session_id}

    await viewer.close()
    for _ in range(10):
        if session_id not in server.rooms:
            break
        await asyncio.sleep(0)
    assert session_id not in server.rooms


@pytest.mark.asyncio
async def test_sender_stop_detaches_sender_before_websocket_disconnect(signaling_client) -> None:
    sender = await signaling_client.ws_connect("/ws")
    session_id = "explicit-stop-room"
    await sender.send_json({"t": "offer", "s": session_id, "sdp": "v=0\r\n"})

    viewer = await signaling_client.ws_connect("/ws")
    await viewer.send_json({"t": "reg", "s": session_id})
    await receive_json(viewer)
    await receive_json(sender)

    sender_cid = server.rooms[session_id].sender
    assert sender_cid is not None

    await sender.send_json({"t": "stop", "s": session_id})
    assert await receive_json(viewer) == {"t": "stopped", "s": session_id}

    for _ in range(10):
        if sender_cid not in server.client_to_room:
            break
        await asyncio.sleep(0)
    assert sender_cid not in server.client_to_room
    assert server.rooms[session_id].sender is None

    # 关闭 sender 不应再次按 viewer 路径修改房间；最后一个 viewer 离开后才删房间。
    await sender.close()
    assert session_id in server.rooms
    await viewer.close()
    for _ in range(10):
        if session_id not in server.rooms:
            break
        await asyncio.sleep(0)
    assert session_id not in server.rooms
