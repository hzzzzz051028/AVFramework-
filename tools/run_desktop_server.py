#!/usr/bin/env python3
"""Run the web application with the DesktopGStreamerReceiver backend."""

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
from receivers import DesktopGStreamerReceiver, ReceiverSupervisor  # noqa: E402


async def run(host: str, port: int) -> None:
    # Desktop development server exposes HTTP and signaling on one port.
    # Keep the worker URL aligned with the port selected by this script.
    server.config._data["server"]["ws_port"] = port
    supervisor = ReceiverSupervisor(DesktopGStreamerReceiver())
    app = server.create_app(receiver_supervisor=supervisor)
    app.on_startup.clear()
    app.on_cleanup.clear()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    print(
        "Desktop receiver web app: http://%s:%s/p2p-sender.html?testMedia=1"
        % (host, port),
        flush=True,
    )
    try:
        await asyncio.Event().wait()
    finally:
        await supervisor.stop_all()
        await runner.cleanup()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8091)
    args = parser.parse_args()
    try:
        asyncio.run(run(args.host, args.port))
    except KeyboardInterrupt:
        print("\nDesktop receiver web app stopped.")


if __name__ == "__main__":
    main()
