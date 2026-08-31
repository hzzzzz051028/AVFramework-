#!/usr/bin/env python3
"""Serve the sender on localhost so browsers allow real screen capture."""
import argparse
from functools import partial
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8090)
    args = parser.parse_args()
    frontend = Path(__file__).resolve().parents[1] / 'frontend'
    handler = partial(SimpleHTTPRequestHandler, directory=str(frontend))
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(f'Real screen: http://{args.host}:{args.port}/p2p-sender.html?ws=ws%3A%2F%2F192.168.1.109%3A8081')
    print(f'Test media:  http://{args.host}:{args.port}/p2p-sender.html?ws=ws%3A%2F%2F192.168.1.109%3A8081&testMedia=1')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
