#!/usr/bin/env python3
"""Serve the sender on localhost so browsers allow real screen capture."""
import argparse
from functools import partial
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import quote


def build_ws_base(device_host, device_port, scheme="wss"):
    """Return the WebSocket origin; p2p-sender.html appends ``/ws``."""
    return f'{scheme}://{device_host}:{device_port}'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8090)
    parser.add_argument('--device-host', default='192.168.50.1')
    parser.add_argument('--device-port', type=int, default=8080)
    parser.add_argument('--device-scheme', choices=('wss', 'ws'), default='wss')
    args = parser.parse_args()
    frontend = Path(__file__).resolve().parents[1] / 'frontend'
    handler = partial(SimpleHTTPRequestHandler, directory=str(frontend))
    server = ThreadingHTTPServer((args.host, args.port), handler)
    ws = build_ws_base(args.device_host, args.device_port, args.device_scheme)
    ws_param = quote(ws, safe='')
    print(f'Real screen: http://{args.host}:{args.port}/p2p-sender.html?ws={ws_param}')
    print(f'Test media:  http://{args.host}:{args.port}/p2p-sender.html?ws={ws_param}&testMedia=1')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
