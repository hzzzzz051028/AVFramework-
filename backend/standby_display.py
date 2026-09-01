#!/usr/bin/env python3
"""Compatibility entry point for the standby display service.

Product content is served by ``frontend/standby.html``. The current systemd
unit still invokes this path, which delegates to the hardware-safe SVG/KMS
fallback until a kiosk renderer is enabled on the board.
"""

import os

from standby_renderers.html_kiosk import is_available as html_available
from standby_renderers.html_kiosk import main as html_main
from standby_renderers.svg_kms import main as svg_main


def main():
    """Select HTML kiosk when explicitly enabled, otherwise use SVG/KMS."""
    if os.getenv("SCREENCAST_STANDBY_MODE", "svg").lower() == "html":
        if html_available():
            return html_main()
        print("[standby] HTML renderer unavailable; using SVG/KMS fallback", flush=True)
    return svg_main()


if __name__ == '__main__':
    raise SystemExit(main())
