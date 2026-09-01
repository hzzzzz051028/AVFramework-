#!/usr/bin/env bash
# Switch the board between the supported onboarding modes.
#
# Usage:
#   sudo bash configure_network_mode.sh standalone-ap
#   sudo UPLINK_CONNECTION='Home WiFi' bash configure_network_mode.sh same-lan
#   sudo WIRED_CONNECTION='enP4p65s0' bash configure_network_mode.sh wired-lan
#   sudo bash configure_network_mode.sh ap-uplink

set -euo pipefail

MODE="${1:-}"
AP_CONNECTION="${AP_CONNECTION:-RK-Screencast}"
UPLINK_CONNECTION="${UPLINK_CONNECTION:-}"
UPLINK_SSID="${UPLINK_SSID:-}"
UPLINK_PASSWORD="${UPLINK_PASSWORD:-}"
UPLINK_IFACE="${UPLINK_IFACE:-wlan0}"
WIRED_CONNECTION="${WIRED_CONNECTION:-}"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

usage() {
  echo "用法: $0 {wired-lan|same-lan|standalone-ap|ap-uplink}" >&2
  exit 2
}

[[ -n "${MODE}" ]] || usage
command -v nmcli >/dev/null || { echo "未找到 nmcli" >&2; exit 1; }

case "${MODE}" in
  wired-lan)
    nmcli connection modify "${AP_CONNECTION}" connection.autoconnect no 2>/dev/null || true
    nmcli connection down "${AP_CONNECTION}" >/dev/null 2>&1 || true
    if [[ -n "${WIRED_CONNECTION}" ]]; then
      nmcli connection up "${WIRED_CONNECTION}"
    else
      WIRED_CONNECTION="$(nmcli -t -f NAME,TYPE connection show | awk -F: '$2 == "802-3-ethernet" { print $1; exit }')"
      if [[ -n "${WIRED_CONNECTION}" ]]; then
        nmcli connection up "${WIRED_CONNECTION}"
      else
        echo "未找到有线 NetworkManager profile，请设置 WIRED_CONNECTION。" >&2
        exit 1
      fi
    fi
    ;;
  same-lan)
    # Stop AP autoconnect so the sender remains on the existing LAN.
    nmcli connection modify "${AP_CONNECTION}" connection.autoconnect no 2>/dev/null || true
    nmcli connection down "${AP_CONNECTION}" >/dev/null 2>&1 || true
    if [[ -n "${UPLINK_CONNECTION}" ]]; then
      nmcli connection up "${UPLINK_CONNECTION}"
    elif [[ -n "${UPLINK_SSID}" ]]; then
      [[ -n "${UPLINK_PASSWORD}" ]] || { echo "UPLINK_PASSWORD 不能为空" >&2; exit 1; }
      nmcli device wifi connect "${UPLINK_SSID}" password "${UPLINK_PASSWORD}" ifname "${UPLINK_IFACE}"
    else
      echo "AP 已关闭；请通过 UPLINK_CONNECTION 指定现有 LAN 连接，或手动配置 Ethernet。"
    fi
    ;;
  standalone-ap)
    nmcli connection modify "${AP_CONNECTION}" connection.autoconnect yes 2>/dev/null || true
    "${SCRIPT_DIR}/configure_ap.sh"
    ;;
  ap-uplink)
    nmcli connection modify "${AP_CONNECTION}" connection.autoconnect yes 2>/dev/null || true
    "${SCRIPT_DIR}/configure_ap.sh"
    if ! ip route show default | grep -qv 'dev wlan0'; then
      echo "警告：AP 已启动，但尚未发现 wlan0 之外的默认上行路由。" >&2
      echo "请将 Ethernet 接入可用路由器，或先配置 UPLINK_CONNECTION。" >&2
    else
      echo "已发现有线上行路由，AP + Uplink 模式生效。"
    fi
    ;;
  *) usage ;;
esac
