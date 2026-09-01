"""Network-mode detection shared by the API and the standby UI.

The media pipeline does not care how packets reach the receiver.  This module
only describes the current onboarding path so the device can distinguish an
existing LAN, an offline AP, and an AP with a usable uplink.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class NetworkStatus:
    mode: str
    label: str
    ap_active: bool
    uplink_configured: bool
    uplink_interface: str | None
    addresses: dict[str, list[str]]

    def to_dict(self) -> dict:
        return asdict(self)


def classify_network(
    *,
    wlan_mode: str | None,
    default_interface: str | None,
    addresses: dict[str, list[str]] | None = None,
) -> NetworkStatus:
    """Classify a network topology from already-observed interface facts."""
    wlan_mode = (wlan_mode or "").lower()
    ap_active = wlan_mode == "ap"
    addresses = addresses or {}

    if ap_active:
        has_uplink = bool(default_interface and default_interface != "wlan0")
        return NetworkStatus(
            mode="ap_uplink" if has_uplink else "standalone_ap",
            label="AP + 有线上行" if has_uplink else "仅局域网 AP",
            ap_active=True,
            uplink_configured=has_uplink,
            uplink_interface=default_interface if has_uplink else None,
            addresses=addresses,
        )

    wired_interfaces = [
        name for name, values in addresses.items()
        if values and name != "lo" and name.startswith(("en", "eth", "eno", "ens", "enx", "usb"))
    ]
    wired_interface = (
        default_interface
        if default_interface and default_interface.startswith(("en", "eth", "eno", "ens", "enx", "usb"))
        else (wired_interfaces[0] if wired_interfaces else None)
    )
    if wired_interface:
        return NetworkStatus(
            mode="wired_lan",
            label="有线局域网",
            ap_active=False,
            uplink_configured=bool(default_interface == wired_interface),
            uplink_interface=wired_interface,
            addresses=addresses,
        )

    if default_interface:
        return NetworkStatus(
            mode="same_lan",
            label="现有局域网",
            ap_active=False,
            uplink_configured=True,
            uplink_interface=default_interface,
            addresses=addresses,
        )

    return NetworkStatus(
        mode="offline",
        label="未连接网络",
        ap_active=False,
        uplink_configured=False,
        uplink_interface=None,
        addresses=addresses,
    )


def _run(command: list[str], timeout: float = 1.0) -> str:
    try:
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return ""


def _addresses() -> dict[str, list[str]]:
    raw = _run(["ip", "-j", "-4", "addr", "show"])
    try:
        rows = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    result: dict[str, list[str]] = {}
    for row in rows if isinstance(rows, list) else []:
        name = row.get("ifname")
        if not name:
            continue
        result[name] = [item.get("local") for item in row.get("addr_info", []) if item.get("local")]
    return result


def _default_interface() -> str | None:
    raw = _run(["ip", "-j", "route", "show", "default"])
    try:
        rows = json.loads(raw)
    except (TypeError, ValueError):
        rows = []
    for row in rows if isinstance(rows, list) else []:
        if row.get("dev"):
            return row["dev"]
    # BusyBox/ip from older images may not support JSON output.
    text = _run(["ip", "route", "show", "default"])
    match = re.search(r"\bdev\s+(\S+)", text)
    return match.group(1) if match else None


def _wlan_mode(interface: str = "wlan0") -> str | None:
    text = _run(["iw", "dev", interface, "info"])
    match = re.search(r"^\s*type\s+(\S+)", text, re.MULTILINE)
    return match.group(1) if match else None


def detect_network_status() -> NetworkStatus:
    """Read Linux network state without changing any connection."""
    return classify_network(
        wlan_mode=_wlan_mode(),
        default_interface=_default_interface(),
        addresses=_addresses(),
    )
