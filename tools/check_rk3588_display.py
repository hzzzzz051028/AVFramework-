#!/usr/bin/env python3
"""Print DRM connector/mode information used to configure the RK3588 sink."""

import glob
import os
import subprocess


def main():
    print("DRM devices:", ", ".join(sorted(glob.glob("/dev/dri/*"))) or "none")
    for status_path in sorted(glob.glob("/sys/class/drm/card*-*/status")):
        connector = status_path.rsplit("/", 2)[-2]
        status = open(status_path, encoding="utf-8").read().strip()
        modes_path = status_path.replace("/status", "/modes")
        modes = []
        if os.path.exists(modes_path):
            modes = [line.strip() for line in open(modes_path, encoding="utf-8") if line.strip()]
        print(f"{connector}: {status}; modes={', '.join(modes[:8]) or '-'}")
    try:
        result = subprocess.run(
            ["modetest", "-M", "rockchip", "-p"],
            capture_output=True, text=True, timeout=5, check=False,
        )
        print("\nPlanes (first lines):")
        lines = result.stdout.splitlines()
        start = next((i for i, line in enumerate(lines) if line.startswith("Plane")), 0)
        print("\n".join(lines[start:start + 24]))
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        print(f"modetest unavailable: {exc}")


if __name__ == "__main__":
    main()
