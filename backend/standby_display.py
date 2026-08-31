#!/usr/bin/env python3
"""Render the RK3588 standby/onboarding screen to DRM/KMS."""
import argparse
import base64
import os
import shutil
import signal
import subprocess
import tempfile
from pathlib import Path


def esc(value):
    return (str(value).replace('&', '&amp;').replace('<', '&lt;')
            .replace('>', '&gt;').replace('"', '&quot;'))


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--width', type=int, default=int(os.getenv('SCREENCAST_DISPLAY_WIDTH', '2560')))
    p.add_argument('--height', type=int, default=int(os.getenv('SCREENCAST_DISPLAY_HEIGHT', '1440')))
    p.add_argument('--plane-id', type=int, default=int(os.getenv('SCREENCAST_KMS_PLANE_ID', '71')))
    p.add_argument('--ssid', default=os.getenv('SCREENCAST_WIFI_SSID', 'RK-Screencast'))
    p.add_argument('--password', default=os.getenv('SCREENCAST_WIFI_PASSWORD', 'RKcast2026'))
    p.add_argument('--address', default=os.getenv('SCREENCAST_ADDRESS', 'http://192.168.50.1:8080'))
    args = p.parse_args()
    if not shutil.which('qrencode'):
        raise SystemExit('qrencode is required')

    tmp = Path(tempfile.mkdtemp(prefix='screencast-standby-'))
    qr = tmp / 'wifi-qr.png'
    svg = tmp / 'standby.svg'
    wifi = f'WIFI:T:WPA;S:{args.ssid};P:{args.password};;'
    subprocess.run(['qrencode', '-o', str(qr), '-s', '8', wifi], check=True)
    qr_data = base64.b64encode(qr.read_bytes()).decode('ascii')
    svg.write_text(f'''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{args.width}" height="{args.height}" viewBox="0 0 {args.width} {args.height}">
<rect width="100%" height="100%" fill="#101426"/>
<circle cx="{args.width * .15:.0f}" cy="{args.height * .18:.0f}" r="220" fill="#27366b" opacity=".45"/>
<text x="{args.width * .1:.0f}" y="{args.height * .23:.0f}" fill="#ffffff" font-family="sans-serif" font-size="76" font-weight="bold">RK WIRELESS DISPLAY</text>
<text x="{args.width * .1:.0f}" y="{args.height * .30:.0f}" fill="#aab8e8" font-family="sans-serif" font-size="34">Connect your computer to this Wi-Fi to start casting</text>
<rect x="{args.width * .1:.0f}" y="{args.height * .42:.0f}" width="{args.width * .45:.0f}" height="{args.height * .27:.0f}" rx="28" fill="#1c2542"/>
<text x="{args.width * .14:.0f}" y="{args.height * .50:.0f}" fill="#8fa6ff" font-family="sans-serif" font-size="30">Wi-Fi SSID</text>
<text x="{args.width * .14:.0f}" y="{args.height * .57:.0f}" fill="#ffffff" font-family="sans-serif" font-size="52" font-weight="bold">{esc(args.ssid)}</text>
<text x="{args.width * .14:.0f}" y="{args.height * .63:.0f}" fill="#8fa6ff" font-family="sans-serif" font-size="30">Password: <tspan fill="#ffffff">{esc(args.password)}</tspan></text>
<text x="{args.width * .1:.0f}" y="{args.height * .80:.0f}" fill="#aab8e8" font-family="sans-serif" font-size="30">Open: {esc(args.address)}</text>
<rect x="{args.width * .70:.0f}" y="{args.height * .22:.0f}" width="560" height="560" rx="18" fill="#ffffff"/>
<image x="{args.width * .70 + 35:.0f}" y="{args.height * .22 + 35:.0f}" width="490" height="490" href="data:image/png;base64,{qr_data}" xlink:href="data:image/png;base64,{qr_data}"/>
<text x="{args.width * .70 + 280:.0f}" y="{args.height * .22 + 535:.0f}" text-anchor="middle" fill="#101426" font-family="sans-serif" font-size="26">SCAN TO CONNECT</text>
</svg>''', encoding='utf-8')
    cmd = ['gst-launch-1.0', '-q', 'filesrc', f'location={svg}', '!', 'rsvgdec', '!', 'imagefreeze', '!', 'videoconvert', '!', 'videoscale', '!',
           f'video/x-raw,width={args.width},height={args.height}', '!', 'kmssink', f'plane-id={args.plane_id}', 'sync=false']
    proc = subprocess.Popen(cmd)
    def stop_child(_signum, _frame):
        if proc.poll() is None:
            proc.terminate()
    signal.signal(signal.SIGTERM, stop_child)
    signal.signal(signal.SIGINT, stop_child)
    try:
        proc.wait()
    finally:
        if proc.poll() is None:
            proc.terminate()
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    main()
