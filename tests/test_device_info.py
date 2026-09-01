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
async def test_device_info_exposes_onboarding_values(client):
    response = await client.get("/api/device-info")
    assert response.status == 200
    data = await response.json()
    assert data["name"]
    assert data["ssid"]
    assert data["password"]
    assert data["address"] == "192.168.50.1"
    assert data["ws_url"].endswith(":8080/ws")
    assert data["ws_url"].startswith("wss://")
    assert data["pairing_required"] is True
    assert data["pairing_code_digits"] == 8
    assert data["available"] is True
