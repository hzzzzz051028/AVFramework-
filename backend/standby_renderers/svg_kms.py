#!/usr/bin/env python3
"""Static emergency renderer: SVG -> GStreamer -> DRM/KMS.

The normal standby content lives in ``frontend/standby.html``. This renderer
is intentionally kept as a hardware-safe fallback for boot and for boards
without a kiosk browser. It owns no product layout code beyond the fallback.
"""

import argparse
import base64
import os
import shutil
import signal
import subprocess
import tempfile
import time
from pathlib import Path


def _esc(value):
    return (str(value).replace('&', '&amp;').replace('<', '&lt;')
            .replace('>', '&gt;').replace('"', '&quot;'))


def _pairing_code(code_file, wait_seconds=0):
    """Read the service code, waiting through a concurrent service startup."""
    deadline = time.monotonic() + max(0, wait_seconds)
    while True:
        try:
            value = Path(code_file).read_text(encoding='ascii').strip()
        except OSError:
            value = ''
        if value.isdigit() and len(value) == 8:
            return value
        if time.monotonic() >= deadline:
            return '--------'
        time.sleep(.2)


def render(args):
    if not shutil.which('qrencode'):
        raise SystemExit('qrencode is required for the SVG fallback')

    tmp = Path(tempfile.mkdtemp(prefix='screencast-standby-'))
    qr = tmp / 'wifi-qr.png'
    svg = tmp / 'standby.svg'
    wifi = f'WIFI:T:WPA;S:{args.ssid};P:{args.password};;'
    pairing_code = _pairing_code(args.pair_code_file, args.pair_code_wait)
    subprocess.run(['qrencode', '-o', str(qr), '-s', '8', wifi], check=True)
    qr_data = base64.b64encode(qr.read_bytes()).decode('ascii')
    asset = Path(__file__).resolve().parents[2] / 'frontend' / 'assets' / 'standby' / 'ambient-cast.png'
    try:
        ambient_data = base64.b64encode(asset.read_bytes()).decode('ascii')
    except OSError:
        ambient_data = ''

    # This is intentionally the no-browser representation of standby.html:
    # it shares the same information architecture and dark product language,
    # but stays entirely inside the proven SVG -> KMS boot path.
    image_layer = (
        f'<image href="data:image/png;base64,{ambient_data}" xlink:href="data:image/png;base64,{ambient_data}" '
        f'width="{args.width}" height="{args.height}" preserveAspectRatio="xMidYMid slice" opacity=".34"/>'
        if ambient_data else ''
    )
    svg.write_text(f'''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{args.width}" height="{args.height}" viewBox="0 0 {args.width} {args.height}">
<defs>
  <linearGradient id="veil" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#0a0e20" stop-opacity=".42"/><stop offset=".65" stop-color="#121534" stop-opacity=".82"/><stop offset="1" stop-color="#090b17" stop-opacity=".98"/></linearGradient>
  <linearGradient id="card" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#26284a" stop-opacity=".94"/><stop offset="1" stop-color="#151629" stop-opacity=".94"/></linearGradient>
  <linearGradient id="accent" x1="0" y1="0" x2="1" y2="0"><stop stop-color="#8c78ff"/><stop offset="1" stop-color="#56c9ff"/></linearGradient>
</defs>
<rect width="100%" height="100%" fill="#090b17"/>{image_layer}<rect width="100%" height="100%" fill="url(#veil)"/>
<rect x="0" y="0" width="100%" height="118" fill="#0b0d1f" fill-opacity=".56"/>
<circle cx="100" cy="59" r="22" fill="none" stroke="#8d7aff" stroke-width="6"/><path d="M91 59h18M100 50v18" stroke="#ffffff" stroke-width="4" stroke-linecap="round"/>
<text x="140" y="69" fill="#ffffff" font-family="sans-serif" font-size="34" font-weight="bold">RK <tspan fill="#a99aff">CAST</tspan></text>
<text x="{args.width - 70:.0f}" y="50" text-anchor="end" fill="#adb3d4" font-family="sans-serif" font-size="23">RK WIRELESS DISPLAY</text>
<circle cx="{args.width - 148:.0f}" cy="82" r="6" fill="#57e3a8"/><text x="{args.width - 70:.0f}" y="90" text-anchor="end" fill="#dfe4ff" font-family="sans-serif" font-size="21">READY</text>
<text x="{args.width * .085:.0f}" y="{args.height * .245:.0f}" fill="#aaa2ff" font-family="sans-serif" font-size="22" letter-spacing="5">01 / WIRELESS DISPLAY</text>
<text x="{args.width * .085:.0f}" y="{args.height * .355:.0f}" fill="#ffffff" font-family="sans-serif" font-size="78" font-weight="bold">Bring your screen</text>
<text x="{args.width * .085:.0f}" y="{args.height * .435:.0f}" fill="#ffffff" font-family="sans-serif" font-size="78" font-weight="bold">to the <tspan fill="#9e89ff">big screen.</tspan></text>
<text x="{args.width * .085:.0f}" y="{args.height * .505:.0f}" fill="#c5cae7" font-family="sans-serif" font-size="28">Connect to the display Wi-Fi, then open the casting page.</text>
<g font-family="sans-serif"><rect x="{args.width * .085:.0f}" y="{args.height * .58:.0f}" width="{args.width * .145:.0f}" height="165" rx="18" fill="#25264a"/><text x="{args.width * .105:.0f}" y="{args.height * .62:.0f}" fill="#9f91ff" font-size="20">01</text><text x="{args.width * .105:.0f}" y="{args.height * .657:.0f}" fill="#ffffff" font-size="24" font-weight="bold">Join Wi-Fi</text><text x="{args.width * .105:.0f}" y="{args.height * .691:.0f}" fill="#aeb5d8" font-size="18">Use the QR code</text>
<rect x="{args.width * .245:.0f}" y="{args.height * .58:.0f}" width="{args.width * .145:.0f}" height="165" rx="18" fill="#1c1d35"/><text x="{args.width * .265:.0f}" y="{args.height * .62:.0f}" fill="#9f91ff" font-size="20">02</text><text x="{args.width * .265:.0f}" y="{args.height * .657:.0f}" fill="#ffffff" font-size="24" font-weight="bold">Open casting</text><text x="{args.width * .265:.0f}" y="{args.height * .691:.0f}" fill="#aeb5d8" font-size="18">Enter the address</text>
<rect x="{args.width * .405:.0f}" y="{args.height * .58:.0f}" width="{args.width * .145:.0f}" height="165" rx="18" fill="#1c1d35"/><text x="{args.width * .425:.0f}" y="{args.height * .62:.0f}" fill="#9f91ff" font-size="20">03</text><text x="{args.width * .425:.0f}" y="{args.height * .657:.0f}" fill="#ffffff" font-size="24" font-weight="bold">Enter code</text><text x="{args.width * .425:.0f}" y="{args.height * .691:.0f}" fill="#aeb5d8" font-size="18">Start sharing</text></g>
<rect x="{args.width * .085:.0f}" y="{args.height * .75:.0f}" width="{args.width * .465:.0f}" height="{args.height * .125:.0f}" rx="20" fill="#111329" fill-opacity=".88" stroke="#343662"/>
<text x="{args.width * .11:.0f}" y="{args.height * .795:.0f}" fill="#9da4c8" font-family="sans-serif" font-size="18" letter-spacing="3">DEVICE PULSE</text><text x="{args.width * .11:.0f}" y="{args.height * .84:.0f}" fill="#ffffff" font-family="sans-serif" font-size="27" font-weight="bold">HDMI READY</text>
<text x="{args.width * .30:.0f}" y="{args.height * .795:.0f}" fill="#9da4c8" font-family="sans-serif" font-size="18">CODEC</text><text x="{args.width * .30:.0f}" y="{args.height * .84:.0f}" fill="#ffffff" font-family="sans-serif" font-size="27" font-weight="bold">MPP / KMS</text>
<text x="{args.width * .46:.0f}" y="{args.height * .795:.0f}" fill="#9da4c8" font-family="sans-serif" font-size="18">NETWORK</text><text x="{args.width * .46:.0f}" y="{args.height * .84:.0f}" fill="#57e3a8" font-family="sans-serif" font-size="27" font-weight="bold">AP READY</text>
<rect x="{args.width * .64:.0f}" y="{args.height * .17:.0f}" width="{args.width * .285:.0f}" height="{args.height * .71:.0f}" rx="28" fill="url(#card)" stroke="#3a3b68" stroke-width="2"/>
<text x="{args.width * .675:.0f}" y="{args.height * .235:.0f}" fill="#a99aff" font-family="sans-serif" font-size="20" letter-spacing="4">QUICK CONNECT</text><circle cx="{args.width * .89:.0f}" cy="{args.height * .227:.0f}" r="6" fill="#57e3a8"/>
<rect x="{args.width * .714:.0f}" y="{args.height * .275:.0f}" width="{args.width * .136:.0f}" height="{args.width * .136:.0f}" rx="18" fill="#ffffff"/>
<image x="{args.width * .720:.0f}" y="{args.height * .287:.0f}" width="{args.width * .124:.0f}" height="{args.width * .124:.0f}" href="data:image/png;base64,{qr_data}" xlink:href="data:image/png;base64,{qr_data}"/>
<text x="{args.width * .782:.0f}" y="{args.height * .535:.0f}" text-anchor="middle" fill="#cbd0ec" font-family="sans-serif" font-size="20">SCAN TO JOIN WI-FI</text>
<text x="{args.width * .685:.0f}" y="{args.height * .59:.0f}" fill="#aab0d4" font-family="sans-serif" font-size="18">NETWORK NAME</text><text x="{args.width * .685:.0f}" y="{args.height * .625:.0f}" fill="#ffffff" font-family="sans-serif" font-size="31" font-weight="bold">{_esc(args.ssid)}</text>
<text x="{args.width * .685:.0f}" y="{args.height * .67:.0f}" fill="#aab0d4" font-family="sans-serif" font-size="18">PASSWORD</text><text x="{args.width * .685:.0f}" y="{args.height * .705:.0f}" fill="#ffffff" font-family="sans-serif" font-size="31" font-weight="bold">{_esc(args.password)}</text>
<text x="{args.width * .685:.0f}" y="{args.height * .75:.0f}" fill="#aab0d4" font-family="sans-serif" font-size="18">CASTING CODE</text><rect x="{args.width * .678:.0f}" y="{args.height * .767:.0f}" width="{args.width * .21:.0f}" height="68" rx="12" fill="#34345f"/><text x="{args.width * .783:.0f}" y="{args.height * .815:.0f}" text-anchor="middle" fill="#ffffff" font-family="monospace" font-size="37" font-weight="bold" letter-spacing="7">{pairing_code}</text>
<text x="{args.width / 2:.0f}" y="{args.height * .955:.0f}" text-anchor="middle" fill="#9da4c8" font-family="sans-serif" font-size="19">RK3588  ·  LOW LATENCY WIRELESS DISPLAY  ·  {_esc(args.address)}</text>
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
        return proc.wait()
    finally:
        if proc.poll() is None:
            proc.terminate()
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--width', type=int, default=int(os.getenv('SCREENCAST_DISPLAY_WIDTH', '2560')))
    parser.add_argument('--height', type=int, default=int(os.getenv('SCREENCAST_DISPLAY_HEIGHT', '1440')))
    parser.add_argument('--plane-id', type=int, default=int(os.getenv('SCREENCAST_KMS_PLANE_ID', '71')))
    parser.add_argument('--ssid', default=os.getenv('SCREENCAST_WIFI_SSID', 'RK-Screencast'))
    parser.add_argument('--password', default=os.getenv('SCREENCAST_WIFI_PASSWORD', 'RKcast2026'))
    parser.add_argument('--address', default=os.getenv('SCREENCAST_ADDRESS', 'https://192.168.50.1:8080'))
    parser.add_argument('--pair-code-file', default=os.getenv('SCREENCAST_PAIRING_CODE_FILE', '/run/screencast/pairing-code'))
    parser.add_argument('--pair-code-wait', type=float, default=float(os.getenv('SCREENCAST_PAIRING_CODE_WAIT', '20')))
    return render(parser.parse_args())


if __name__ == '__main__':
    raise SystemExit(main())
