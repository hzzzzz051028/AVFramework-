"""Ephemeral, display-only pairing codes for external casting clients."""

from __future__ import annotations

import hmac
import os
import secrets
import time
from collections import defaultdict, deque
from pathlib import Path


class PairingManager:
    """Own the short-lived code shown on the receiver display.

    The code is intentionally not exposed by any HTTP API. It is kept in a
    root-owned runtime file only so the standby renderer can show the same
    code as the signaling server.
    """

    def __init__(
        self,
        code: str | None = None,
        code_file: Path | None = None,
        attempts: int = 5,
        window_seconds: int = 60,
        clock=time.monotonic,
    ) -> None:
        self.code = code or f"{secrets.randbelow(100_000_000):08d}"
        self.code_file = code_file
        self.attempts = attempts
        self.window_seconds = window_seconds
        self.clock = clock
        self._failures: dict[str, deque[float]] = defaultdict(deque)
        if self.code_file is not None:
            self._write_code_file()

    def _write_code_file(self) -> None:
        self.code_file.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
        temporary = self.code_file.with_suffix(".tmp")
        temporary.write_text(f"{self.code}\n", encoding="ascii")
        os.chmod(temporary, 0o640)
        temporary.replace(self.code_file)
        os.chmod(self.code_file, 0o640)

    def verify(self, candidate: object, peer: str) -> tuple[bool, str]:
        now = self.clock()
        failures = self._failures[peer]
        while failures and now - failures[0] >= self.window_seconds:
            failures.popleft()
        if len(failures) >= self.attempts:
            return False, "pairing_rate_limited"

        value = str(candidate or "")
        if hmac.compare_digest(value, self.code):
            failures.clear()
            return True, "pairing_ok"

        failures.append(now)
        return False, "pairing_failed"
