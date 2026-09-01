from __future__ import annotations

from device_runtime import AdaptationPolicy, DeviceRuntime, DeviceState
from receivers import ReceiverEvent, ReceiverSnapshot, ReceiverState


class FakeClock:
    def __init__(self) -> None:
        self.value = 100.0

    def __call__(self) -> float:
        return self.value


def event(session_id: str, state: ReceiverState, **details) -> ReceiverEvent:
    return ReceiverEvent(
        type=f"receiver.{state.value}",
        snapshot=ReceiverSnapshot(session_id, state, "mock", details),
    )


def test_runtime_tracks_device_state_and_time_to_play() -> None:
    clock = FakeClock()
    runtime = DeviceRuntime(clock=clock)

    runtime.handle_receiver_event(event("cast-1", ReceiverState.STARTING))
    assert runtime.state == DeviceState.CONNECTING
    clock.value += 0.35
    runtime.handle_receiver_event(event("cast-1", ReceiverState.PLAYING))

    snapshot = runtime.snapshot()
    assert snapshot["state"] == "casting"
    assert snapshot["metrics"]["sessions_started"] == 1
    assert snapshot["metrics"]["sessions_played"] == 1
    assert snapshot["metrics"]["last_time_to_play_ms"] == 350.0

    runtime.handle_receiver_event(event("cast-1", ReceiverState.STOPPED))
    snapshot = runtime.snapshot()
    assert snapshot["state"] == "ready"
    assert snapshot["available"] is True
    assert snapshot["metrics"]["sessions_completed"] == 1


def test_runtime_records_receiver_failure_as_degraded() -> None:
    runtime = DeviceRuntime()
    runtime.handle_receiver_event(event("bad", ReceiverState.STARTING))
    runtime.handle_receiver_event(
        event("bad", ReceiverState.FAILED, reason="decoder_error")
    )

    snapshot = runtime.snapshot()
    assert snapshot["state"] == "degraded"
    assert snapshot["metrics"]["sessions_failed"] == 1
    assert snapshot["last_error"]["details"]["reason"] == "decoder_error"


def test_legacy_hdmi_worker_can_report_real_playback() -> None:
    runtime = DeviceRuntime()
    runtime.begin_session("legacy-1")
    assert runtime.snapshot()["state"] == "connecting"

    runtime.mark_session_playing("legacy-1", {"codec": "VP8"})
    assert runtime.snapshot()["state"] == "casting"

    runtime.end_session("legacy-1")
    assert runtime.snapshot()["state"] == "ready"


def test_adaptation_policy_recommends_but_does_not_apply() -> None:
    policy = AdaptationPolicy()
    normal = policy.evaluate({"temperature_c": 60, "packet_loss_percent": 0})
    constrained = policy.evaluate({"cpu_percent": 85})
    critical = policy.evaluate({"temperature_c": 88, "packet_loss_percent": 4})

    assert normal["recommended_profile"]["name"] == "1080p30"
    assert constrained["recommended_profile"]["name"] == "720p30"
    assert critical["recommended_profile"]["name"] == "720p20"
    assert critical["automatic_apply"] is False
