#!/usr/bin/env python3
"""Run the web application with a hardware-free MockReceiver backend."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from aiohttp import web


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import server  # noqa: E402
from receivers import MockReceiver, ReceiverSupervisor  # noqa: E402


async def run(host: str, port: int, transition_delay: float) -> None:
    backend = MockReceiver(transition_delay=transition_delay)
    supervisor = ReceiverSupervisor(backend)
    app = server.create_app(receiver_supervisor=supervisor)

    # Mock development must not probe GStreamer/DRM or start mDNS.
    app.on_startup.clear()

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()

    print(
        f"Mock receiver web app: http://{host}:{port}/p2p-sender.html?testMedia=1",
        flush=True,
    )
    print(f"Receiver status API:   http://{host}:{port}/api/receiver/status", flush=True)

    try:
        await asyncio.Event().wait()
    finally:
        await runner.cleanup()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8090)
    parser.add_argument("--transition-delay", type=float, default=0.05)
    args = parser.parse_args()
    try:
        asyncio.run(run(args.host, args.port, args.transition_delay))
    except KeyboardInterrupt:
        print("\nMock receiver web app stopped.")


if __name__ == "__main__":
    main()
