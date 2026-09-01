from __future__ import annotations

import pytest

import server
from device_runtime import DeviceRuntime


@pytest.fixture
async def client(aiohttp_client):
    app = server.create_app(device_runtime=DeviceRuntime())
    app.on_startup.clear()
    app.on_cleanup.clear()
    return await aiohttp_client(app)


@pytest.mark.asyncio
async def test_runtime_api_starts_ready(client) -> None:
    response = await client.get("/api/device/runtime")
    assert response.status == 200
    data = await response.json()
    assert data["state"] == "ready"
    assert data["available"] is True
    assert data["adaptation"]["recommended_profile"]["name"] == "1080p30"


@pytest.mark.asyncio
async def test_telemetry_api_returns_degradation_recommendation(client) -> None:
    response = await client.post(
        "/api/device/telemetry",
        json={"temperature_c": 86, "cpu_percent": 70},
    )
    assert response.status == 200
    data = await response.json()
    assert data["adaptation"]["tier"] == "critical"
    assert data["adaptation"]["recommended_profile"]["name"] == "720p20"
    assert data["adaptation"]["automatic_apply"] is False
