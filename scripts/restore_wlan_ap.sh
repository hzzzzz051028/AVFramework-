#!/usr/bin/env bash
# Restore the product AP only after MiracleCast has released wlan0.  The
# dedicated wpa_supplicant can take several seconds to disappear after wifid
# exits; attempting activation earlier leaves wlan0 unavailable.
set -euo pipefail

systemctl start wpa_supplicant.service
nmcli device set wlan0 managed yes || true

for _ in $(seq 1 15); do
  if nmcli connection up RK-Screencast ifname wlan0 >/dev/null 2>&1; then
    systemctl start screencast-standby.service
    exit 0
  fi
  sleep 1
done

echo 'Timed out restoring the RK-Screencast AP on wlan0' >&2
exit 1
