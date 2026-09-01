from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_exclusive_native_cast_guard_prevents_standby_plane_contention() -> None:
    standby = (ROOT / "scripts" / "screencast-standby.service").read_text()
    airplay = (ROOT / "scripts" / "screencast-airplay-poc.service").read_text()
    miracast = (ROOT / "scripts" / "screencast-miracast-wifid.service").read_text()

    assert "ConditionPathExists=!/run/screencast/display-exclusive-active" in standby
    assert "/usr/bin/touch /run/screencast/display-exclusive-active" in airplay
    assert "/usr/bin/rm -f /run/screencast/display-exclusive-active" in airplay
    assert "/usr/bin/touch /run/screencast/display-exclusive-active" in miracast


def test_svg_fallback_contains_operational_information() -> None:
    renderer = (ROOT / "backend" / "standby_renderers" / "svg_kms.py").read_text()

    for label in ("MEMORY", "TEMP", "UPTIME", "AP / LAN", "WEBRTC", "AIRPLAY", "MIRACAST"):
        assert label in renderer
