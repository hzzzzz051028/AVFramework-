from __future__ import annotations

import pytest

import server


@pytest.fixture
async def client(aiohttp_client):
    app = server.create_app()
    app.on_startup.clear()
    app.on_cleanup.clear()
    return await aiohttp_client(app)


@pytest.mark.asyncio
async def test_standby_page_is_independent_browser_route(client) -> None:
    response = await client.get("/standby.html?demo=1")
    assert response.status == 200
    body = await response.text()
    assert "DEVICE PULSE" in body
    assert "QUICK CONNECT" in body
    assert "standby.css" in body


@pytest.mark.asyncio
async def test_wifi_qr_endpoint_has_safe_development_fallback(client) -> None:
    response = await client.get("/api/device/wifi-qr.svg")
    assert response.status == 200
    assert response.content_type == "image/svg+xml"
    assert response.headers["X-QR-Available"] in {"true", "false"}
    assert "<svg" in await response.text()


@pytest.mark.asyncio
async def test_local_standby_can_read_the_pairing_code(client) -> None:
    response = await client.get("/api/device/pairing-code")
    assert response.status == 200
    data = await response.json()
    assert data["code"].isdigit()
    assert len(data["code"]) == 8
