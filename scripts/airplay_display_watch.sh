#!/usr/bin/env bash
# Switch the KMS standby renderer only while UxPlay has a connected client.
set -euo pipefail

runtime_dir="${SCREENCAST_RUNTIME_DIR:-/run/screencast}"
client_file="${SCREENCAST_AIRPLAY_DACP_FILE:-$runtime_dir/airplay-client}"
guard_file="$runtime_dir/display-exclusive-active"
systemctl_bin="${SYSTEMCTL_BIN:-/usr/bin/systemctl}"
interval="${SCREENCAST_AIRPLAY_WATCH_INTERVAL:-0.2}"
state="idle"

activate() {
  install -d -m 0755 "$runtime_dir"
  touch "$guard_file"
  "$systemctl_bin" stop screencast-standby.service
  state="casting"
}

deactivate() {
  rm -f "$guard_file"
  "$systemctl_bin" start screencast-standby.service
  state="idle"
}

trap 'rm -f "$guard_file"' TERM INT
if [[ -e "$client_file" ]]; then
  activate
else
  deactivate
fi
while true; do
  if [[ -e "$client_file" ]]; then
    [[ "$state" == "casting" ]] || activate
  else
    [[ "$state" == "idle" ]] || deactivate
  fi
  sleep "$interval"
done
