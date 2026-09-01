from __future__ import annotations

from display_arbiter import DisplayArbiter


class FakeClock:
    def __init__(self) -> None:
        self.value = 10.0

    def __call__(self) -> float:
        return self.value


def test_hdmi_lease_rejects_a_second_source_without_replacement() -> None:
    clock = FakeClock()
    arbiter = DisplayArbiter(clock=clock)

    first = arbiter.acquire("airplay", "airplay-1")
    second = arbiter.acquire("webrtc", "room-1", replace=False)

    assert first["accepted"] is True
    assert second == {
        "accepted": False,
        "reason": "display_busy",
        "active": {"source": "airplay", "session_id": "airplay-1"},
    }
    clock.value += 5
    assert arbiter.snapshot()["active"]["duration_seconds"] == 5.0


def test_release_only_removes_its_matching_lease() -> None:
    arbiter = DisplayArbiter()
    arbiter.acquire("miracast", "p2p-1")

    assert arbiter.release("miracast", "wrong") is False
    assert arbiter.snapshot()["active"]["source"] == "miracast"
    assert arbiter.release("miracast", "p2p-1") is True
    assert arbiter.snapshot()["active"] is None
