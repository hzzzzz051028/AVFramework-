from __future__ import annotations

from pairing import PairingManager


def test_pairing_code_is_fixed_width_numeric() -> None:
    pairing = PairingManager()
    assert pairing.code.isdigit()
    assert len(pairing.code) == 8


def test_pairing_accepts_correct_code_and_rate_limits_failures() -> None:
    now = [0.0]
    pairing = PairingManager(code="12345678", attempts=2, window_seconds=10, clock=lambda: now[0])
    assert pairing.verify("00000000", "sender") == (False, "pairing_failed")
    assert pairing.verify("11111111", "sender") == (False, "pairing_failed")
    assert pairing.verify("12345678", "sender") == (False, "pairing_rate_limited")
    now[0] = 11.0
    assert pairing.verify("12345678", "sender") == (True, "pairing_ok")


def test_pairing_writes_runtime_code_with_restrictive_permissions(tmp_path) -> None:
    target = tmp_path / "runtime" / "pairing-code"
    PairingManager(code="12345678", code_file=target)
    assert target.read_text(encoding="ascii") == "12345678\n"
    assert target.stat().st_mode & 0o777 == 0o640
