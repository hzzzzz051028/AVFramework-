#!/usr/bin/env bash
# Configure the RK3588 Wi-Fi interface as the standalone screencast AP.
# NetworkManager shared mode provides DHCP, DNS forwarding and masquerading.

set -euo pipefail

AP_IFACE="${AP_IFACE:-wlan0}"
AP_CONNECTION="${AP_CONNECTION:-RK-Screencast}"
AP_SSID="${AP_SSID:-RK-Screencast}"
AP_PASSWORD="${AP_PASSWORD:-RKcast2026}"
AP_ADDRESS="${AP_ADDRESS:-192.168.50.1/24}"
# Prefer a non-DFS 5 GHz channel for a display AP.  RK3588's Broadcom radio
# supports it in AP mode and 2.4 GHz / 20 MHz is too constrained for a
# high-resolution, low-latency video stream.  Older 2.4 GHz-only boards can
# still explicitly use ``AP_BAND=bg AP_CHANNEL=1``.
AP_BAND="${AP_BAND:-a}"
AP_CHANNEL="${AP_CHANNEL:-36}"

if [[ "${EUID}" -ne 0 ]]; then
  echo "请使用 sudo 运行此脚本" >&2
  exit 1
fi
command -v nmcli >/dev/null || { echo "未找到 nmcli" >&2; exit 1; }
command -v iw >/dev/null || { echo "未找到 iw" >&2; exit 1; }
if ! nmcli device show "${AP_IFACE}" >/dev/null 2>&1; then
  echo "未找到无线网卡: ${AP_IFACE}" >&2
  nmcli device status >&2 || true
  exit 1
fi
if [[ "${#AP_PASSWORD}" -lt 8 ]]; then
  echo "AP_PASSWORD 至少需要 8 个字符" >&2
  exit 1
fi

if nmcli --fields NAME connection show | sed 's/^ *//; s/ *$//' | grep -Fxq "${AP_CONNECTION}"; then
  nmcli connection modify "${AP_CONNECTION}" \
    connection.interface-name "${AP_IFACE}" 802-11-wireless.ssid "${AP_SSID}"
else
  nmcli connection add type wifi ifname "${AP_IFACE}" \
    con-name "${AP_CONNECTION}" ssid "${AP_SSID}"
fi

nmcli connection modify "${AP_CONNECTION}" \
  connection.autoconnect yes \
  connection.autoconnect-retries 0 \
  802-11-wireless.mode ap \
  802-11-wireless.band "${AP_BAND}" \
  802-11-wireless.channel "${AP_CHANNEL}" \
  802-11-wireless.powersave 2 \
  802-11-wireless-security.key-mgmt wpa-psk \
  802-11-wireless-security.proto rsn \
  802-11-wireless-security.pairwise ccmp \
  802-11-wireless-security.psk "${AP_PASSWORD}" \
  ipv4.method shared \
  ipv4.addresses "${AP_ADDRESS}" \
  ipv4.gateway "" \
  ipv4.dns "" \
  ipv4.never-default yes \
  ipv6.method disabled

install -d -m 0755 /etc/sysctl.d
printf '%s\n' 'net.ipv4.ip_forward=1' > /etc/sysctl.d/99-screencast-ap.conf
sysctl --load /etc/sysctl.d/99-screencast-ap.conf >/dev/null

nmcli connection down "${AP_CONNECTION}" >/dev/null 2>&1 || true

# Some brcmfmac/wpa_supplicant combinations retain the previous managed-mode
# state for one activation cycle.  Resetting the radio before the first retry
# makes this command reliable after switching from a client profile to AP.
if ! nmcli connection up "${AP_CONNECTION}" >/dev/null 2>&1; then
  nmcli radio wifi off || true
  sleep 2
  nmcli radio wifi on
  sleep 2
  nmcli connection up "${AP_CONNECTION}"
fi

echo
echo "AP 已启用"
nmcli --fields GENERAL.CONNECTION,GENERAL.STATE,IP4.ADDRESS,IP4.GATEWAY device show "${AP_IFACE}"
echo
echo "SSID: ${AP_SSID}"
echo "网关/投屏地址: ${AP_ADDRESS%/*}"
echo "服务页面: https://${AP_ADDRESS%/*}:8080/standby.html"
echo "WebSocket: ws://${AP_ADDRESS%/*}:8081"
