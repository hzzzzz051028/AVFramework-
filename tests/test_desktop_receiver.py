import pytest

from receivers import DesktopGStreamerReceiver, ReceiverState


@pytest.mark.asyncio
async def test_desktop_receiver_fails_clearly_when_gstreamer_is_unavailable(monkeypatch) -> None:
    receiver = DesktopGStreamerReceiver()
    monkeypatch.setattr(
        receiver,
        "probe",
        lambda: (False, {"missing": ["PyGObject/GStreamer"]}),
    )

    await receiver.start("desktop-test", "ws://127.0.0.1/internal")

    snapshot = receiver.status("desktop-test")
    assert snapshot is not None
    assert snapshot.backend == "desktop"
    assert snapshot.state == ReceiverState.FAILED
    assert snapshot.details["reason"] == "gstreamer_unavailable"
