#!/usr/bin/env bash
# The physical Wi-Fi Direct interface is wlan0 (ifindex 3) on the RK3588.
set -euo pipefail

MIRACLE_BIN=/opt/screencast/vendor/miraclecast/bin
PLAYER=/opt/screencast/scripts/miracast_player_rk.sh
LINK_PATH=/org/freedesktop/miracle/wifi/link/_33

# `After=` only guarantees that wifid was started; it does not guarantee that
# its D-Bus object for wlan0 has been registered.  Running sinkctl earlier
# silently drops the `run 3` command and leaves the receiver undiscoverable.
for _ in $(seq 1 15); do
  if busctl --system get-property org.freedesktop.miracle.wifi "$LINK_PATH" \
      org.freedesktop.miracle.wifi.Link Managed >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

if ! busctl --system get-property org.freedesktop.miracle.wifi "$LINK_PATH" \
    org.freedesktop.miracle.wifi.Link Managed >/dev/null 2>&1; then
  echo 'MiracleCast wlan0 link was not registered within 15 seconds' >&2
  exit 1
fi

# Use sinkctl's positional command instead of piping interactive commands.
# Its interactive reader does not reliably consume pipe input under systemd,
# leaving WfdSubelements empty and making the receiver undiscoverable.
busctl --system set-property org.freedesktop.miracle.wifi "$LINK_PATH" \
  org.freedesktop.miracle.wifi.Link FriendlyName s RK-Screencast

exec "$MIRACLE_BIN/miracle-sinkctl" \
  --audio 0 \
  --external-player "$PLAYER" \
  --log-level info \
  --log-journal-level info \
  run 3
