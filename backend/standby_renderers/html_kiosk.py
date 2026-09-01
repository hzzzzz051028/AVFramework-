#!/usr/bin/env python3
"""HTML standby renderer for a Wayland kiosk environment.

This is optional on the board. It keeps the product UI in the browser while
the SVG/KMS renderer remains the boot-safe fallback.
"""

import argparse
import os
import shutil
import signal
import subprocess


def find_browser():
    configured = os.getenv("SCREENCAST_STANDBY_BROWSER")
    if configured:
        return configured if shutil.which(configured) else None
    for name in ("chromium", "chromium-browser", "google-chrome"):
        path = shutil.which(name)
        if path:
            return path
    return None


def is_available():
    return find_browser() is not None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--url",
        default=os.getenv(
            "SCREENCAST_STANDBY_URL",
            "http://127.0.0.1:8081/standby.html",
        ),
    )
    parser.add_argument("--width", type=int, default=int(os.getenv("SCREENCAST_DISPLAY_WIDTH", "2560")))
    parser.add_argument("--height", type=int, default=int(os.getenv("SCREENCAST_DISPLAY_HEIGHT", "1440")))
    args = parser.parse_args()
    browser = find_browser()
    if browser is None:
        raise SystemExit("a Chromium-compatible browser is required for HTML standby")

    browser_args = [
        browser,
        "--kiosk",
        "--app=" + args.url,
        "--noerrdialogs",
        "--disable-session-crashed-bubble",
        "--disable-infobars",
        "--disable-pinch",
        "--ozone-platform=wayland",
        f"--window-size={args.width},{args.height}",
    ]
    if shutil.which("cage"):
        command = ["cage", "--"] + browser_args
    else:
        command = browser_args
    process = subprocess.Popen(command)

    def stop_child(_signum, _frame):
        if process.poll() is None:
            process.terminate()

    signal.signal(signal.SIGTERM, stop_child)
    signal.signal(signal.SIGINT, stop_child)
    try:
        return process.wait()
    finally:
        if process.poll() is None:
            process.terminate()
