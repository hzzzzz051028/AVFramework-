from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_exclusive_native_cast_guard_prevents_standby_plane_contention() -> None:
    standby = (ROOT / "scripts" / "screencast-standby.service").read_text()
    airplay = (ROOT / "scripts" / "screencast-airplay-poc.service").read_text()
    watcher = (ROOT / "scripts" / "airplay_display_watch.sh").read_text()
    miracast = (ROOT / "scripts" / "screencast-miracast-wifid.service").read_text()

    assert "ConditionPathExists=!/run/screencast/display-exclusive-active" in standby
    assert "/usr/bin/rm -f /run/screencast/display-exclusive-active" in airplay
    assert "-dacp /run/screencast/airplay-client" in airplay
    assert "screencast-airplay-display-watch.service" in airplay
    assert "NetworkManager-wait-online.service" in airplay
    assert "airplay-client" in watcher
    assert "display-exclusive-active" in watcher
    assert "/usr/bin/touch /run/screencast/display-exclusive-active" in miracast


def test_svg_fallback_contains_operational_information() -> None:
    renderer = (ROOT / "backend" / "standby_renderers" / "svg_kms.py").read_text()

    for label in ("MEMORY", "TEMP", "UPTIME", "AP / LAN", "WEBRTC", "AIRPLAY", "MIRACAST"):
        assert label in renderer


def test_display_console_blocks_both_getty_implementations_on_tty2() -> None:
    setup = (ROOT / "scripts" / "configure_display_console.sh").read_text()
    service = (ROOT / "scripts" / "screencast-display-console.service").read_text()

    assert "getty@tty2.service autovt@tty2.service" in setup
    assert "systemctl stop autovt@tty2.service" in setup
    assert "mask --runtime autovt@tty2.service" in service
