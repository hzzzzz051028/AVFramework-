#!/usr/bin/env bash
# Remote deployment and operations for the RK3588 receiver.
set -euo pipefail

RK_USER="${RK_USER:-orangepi}"
RK_HOST="${RK_HOST:-192.168.1.109}"
RK_DIR="${RK_DIR:-/opt/screencast}"
SERVICE="${SERVICE:-screencast}"
SSH_OPTS=(-o ConnectTimeout=10 -o ServerAliveInterval=30 -o StrictHostKeyChecking=accept-new)
TARGET="${RK_USER}@${RK_HOST}"

usage() {
  cat <<'EOF'
Usage: scripts/remote_service.sh <command>

Commands:
  check    verify SSH connectivity and board identity
  install  run the full RK3588 dependency/systemd installer remotely
  deploy   upload current backend/frontend and reload the service
  install-certs upload the matching device certificate, key and public CA
  ap-setup configure the standalone Wi-Fi AP on the board
  network-mode switch between same-lan, standalone-ap and ap-uplink
  enable-mpp enable the isolated Rockchip MPP GStreamer decoder plugin
  airplay-install build and install the isolated UxPlay AirPlay POC receiver
  airplay-start start the AirPlay POC (it replaces the HDMI standby page)
  airplay-stop stop the AirPlay POC and restore the HDMI standby page
  airplay-status show the AirPlay POC status and recent logs
  miracast-install build and install the isolated MiracleCast POC receiver
  miracast-start start the Miracast POC (temporarily replaces the AP on wlan0)
  miracast-stop stop the Miracast POC and restore the AP/standby page
  miracast-status show Miracast POC status and recent logs
  display-console-setup make HDMI a clean product display (reboot required)
  start    start the systemd service
  stop     stop the systemd service
  restart  restart the systemd service
  status   show systemd status and application health
  logs     follow service logs (Ctrl-C to exit)
  shell    open an interactive shell on the board

Environment overrides: RK_USER, RK_HOST, RK_DIR, SERVICE
EOF
}

remote() {
  ssh "${SSH_OPTS[@]}" "$TARGET" "$@"
}

check() {
  remote "hostname; uname -a; printf 'service=%s dir=%s\n' '$SERVICE' '$RK_DIR'"
}

install() {
  local installer=/tmp/screencast-install-rk3588.sh
  scp "${SSH_OPTS[@]}" scripts/install-rk3588.sh "$TARGET:$installer"
  remote "sudo bash '$installer'; rm -f '$installer'"
}

deploy() {
  # macOS tar may otherwise synthesize AppleDouble ``._*`` metadata files on
  # Linux.  They are not application assets and should never reach the board.
  COPYFILE_DISABLE=1 tar --exclude='.git' --exclude='.venv' --exclude='__pycache__' --exclude='.pytest_cache' --exclude='._*' --exclude='.DS_Store' \
    -czf - backend frontend scripts | \
    ssh "${SSH_OPTS[@]}" "$TARGET" \
      "rm -rf /tmp/screencast-release; mkdir -p /tmp/screencast-release; tar -xzf - -C /tmp/screencast-release"
  remote "sudo mkdir -p '$RK_DIR' /etc/systemd/system/'$SERVICE'.service.d; sudo cp -a /tmp/screencast-release/backend '$RK_DIR/'; sudo cp -a /tmp/screencast-release/frontend '$RK_DIR/'; sudo cp /tmp/screencast-release/scripts/screencast-standby.service /etc/systemd/system/screencast-standby.service; sudo cp /tmp/screencast-release/scripts/screencast-display-console.service /etc/systemd/system/screencast-display-console.service; sudo cp /tmp/screencast-release/scripts/screencast-airplay-poc.service /etc/systemd/system/screencast-airplay-poc.service; sudo cp /tmp/screencast-release/scripts/screencast-airplay-display-watch.service /etc/systemd/system/screencast-airplay-display-watch.service; sudo cp /tmp/screencast-release/scripts/screencast-miracast-wifid.service /etc/systemd/system/screencast-miracast-wifid.service; sudo cp /tmp/screencast-release/scripts/screencast-miracast-sink.service /etc/systemd/system/screencast-miracast-sink.service; sudo install -m 0755 /tmp/screencast-release/scripts/airplay_display_watch.sh '$RK_DIR/scripts/airplay_display_watch.sh'; sudo install -m 0755 /tmp/screencast-release/scripts/miracast_player_rk.sh '$RK_DIR/scripts/miracast_player_rk.sh'; sudo install -m 0755 /tmp/screencast-release/scripts/miracast_sink_runner.sh '$RK_DIR/scripts/miracast_sink_runner.sh'; sudo cp /tmp/screencast-release/scripts/screencast-pairing.conf /etc/systemd/system/'$SERVICE'.service.d/pairing.conf; sudo systemctl daemon-reload; sudo systemctl enable --now screencast-display-console.service screencast-standby.service; rm -rf /tmp/screencast-release"
  install_certs
  echo "Deployed and restarted $SERVICE on $TARGET"
}

install_certs() {
  local ca_file=.local-certs/ca.pem
  local certificate_file=.local-certs/cert.pem
  local key_file=.local-certs/key.pem
  if [[ ! -f "$ca_file" || ! -f "$certificate_file" || ! -f "$key_file" ]]; then
    echo "Missing local TLS material in .local-certs; refusing certificate update" >&2
    return 1
  fi
  scp "${SSH_OPTS[@]}" "$ca_file" "$certificate_file" "$key_file" "$TARGET:/tmp/"
  remote "sudo install -m 0644 /tmp/ca.pem '$RK_DIR/backend/ca.pem'; sudo install -m 0644 /tmp/cert.pem '$RK_DIR/backend/cert.pem'; sudo install -m 0600 /tmp/key.pem '$RK_DIR/backend/key.pem'; rm -f /tmp/ca.pem /tmp/cert.pem /tmp/key.pem; sudo systemctl restart '$SERVICE'"
  remote "for attempt in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do curl -kfsS --max-time 1 https://127.0.0.1:8080/health >/dev/null && break; sleep 1; done; curl -kfsS --max-time 1 https://127.0.0.1:8080/health >/dev/null; sudo systemctl restart screencast-standby.service"
}

ap_setup() {
  local remote_script=/tmp/screencast-configure-ap.sh
  scp "${SSH_OPTS[@]}" scripts/configure_ap.sh "$TARGET:$remote_script"
  remote "sudo bash '$remote_script'; rm -f '$remote_script'"
}

network_mode() {
  local remote_dir=/tmp/screencast-network-scripts
  ssh "${SSH_OPTS[@]}" "$TARGET" "rm -rf '$remote_dir'; mkdir -p '$remote_dir'"
  scp "${SSH_OPTS[@]}" scripts/configure_ap.sh scripts/configure_network_mode.sh \
    "$TARGET:$remote_dir/"
  remote "sudo bash '$remote_dir/configure_network_mode.sh' '${2:-}'; rm -rf '$remote_dir'"
}

enable_mpp() {
  local remote_script=/tmp/screencast-enable-mpp-plugin.sh
  scp "${SSH_OPTS[@]}" scripts/enable_mpp_plugin.sh "$TARGET:$remote_script"
  remote "sudo bash '$remote_script'; rm -f '$remote_script'"
}

airplay_install() {
  local remote_script=/tmp/screencast-install-airplay-poc.sh
  scp "${SSH_OPTS[@]}" scripts/install_airplay_poc.sh "$TARGET:$remote_script"
  remote "sudo bash '$remote_script'; rm -f '$remote_script'"
}

miracast_install() {
  local remote_dir=/tmp/screencast-miracast-install
  ssh "${SSH_OPTS[@]}" "$TARGET" "rm -rf '$remote_dir'; mkdir -p '$remote_dir'"
  scp "${SSH_OPTS[@]}" scripts/install_miracast_poc.sh scripts/miracast_player_rk.sh \
    scripts/miracast_sink_runner.sh scripts/restore_wlan_ap.sh scripts/screencast-miracast-wifid.service \
    scripts/screencast-miracast-sink.service "$TARGET:$remote_dir/"
  remote "sudo mkdir -p '$RK_DIR/scripts'; sudo install -m 0755 '$remote_dir/miracast_player_rk.sh' '$RK_DIR/scripts/miracast_player_rk.sh'; sudo install -m 0755 '$remote_dir/miracast_sink_runner.sh' '$RK_DIR/scripts/miracast_sink_runner.sh'; sudo install -m 0755 '$remote_dir/restore_wlan_ap.sh' '$RK_DIR/scripts/restore_wlan_ap.sh'; sudo install -m 0644 '$remote_dir/screencast-miracast-wifid.service' /etc/systemd/system/screencast-miracast-wifid.service; sudo install -m 0644 '$remote_dir/screencast-miracast-sink.service' /etc/systemd/system/screencast-miracast-sink.service; sudo bash '$remote_dir/install_miracast_poc.sh'; rm -rf '$remote_dir'"
}

case "${1:-}" in
  check) check ;;
  install) install ;;
  deploy) deploy ;;
  install-certs) install_certs ;;
  ap-setup) ap_setup ;;
  network-mode) network_mode "$@" ;;
  enable-mpp) enable_mpp ;;
  airplay-install) airplay_install ;;
  airplay-start) remote "sudo systemctl start screencast-airplay-poc.service" ;;
  airplay-stop) remote "sudo systemctl stop screencast-airplay-poc.service" ;;
  airplay-status) remote "sudo systemctl status screencast-airplay-poc.service --no-pager; printf '\nRecent logs:\n'; sudo journalctl -u screencast-airplay-poc.service -n 80 --no-pager" ;;
  miracast-install) miracast_install ;;
  miracast-start) remote "sudo systemctl start screencast-miracast-sink.service" ;;
  miracast-stop) remote "sudo systemctl stop screencast-miracast-sink.service" ;;
  miracast-status) remote "sudo systemctl status screencast-miracast-wifid.service screencast-miracast-sink.service --no-pager; printf '\nRecent logs:\n'; sudo journalctl -u screencast-miracast-wifid.service -u screencast-miracast-sink.service -n 120 --no-pager" ;;
  display-console-setup) scp "${SSH_OPTS[@]}" scripts/configure_display_console.sh "$TARGET:/tmp/screencast-configure-display-console.sh"; remote "sudo bash /tmp/screencast-configure-display-console.sh; rm -f /tmp/screencast-configure-display-console.sh" ;;
  start) remote "sudo systemctl start '$SERVICE'" ;;
  stop) remote "sudo systemctl stop '$SERVICE'" ;;
  restart) remote "sudo systemctl restart '$SERVICE'" ;;
  status) remote "sudo systemctl status '$SERVICE' --no-pager; printf '\nHealth:\n'; (curl -kfsS --max-time 5 https://127.0.0.1:8080/health || curl -fsS --max-time 5 http://127.0.0.1:8080/health)" ;;
  logs) remote "sudo journalctl -u '$SERVICE' -f -n 100" ;;
  shell) ssh "${SSH_OPTS[@]}" "$TARGET" ;;
  *) usage; exit 2 ;;
esac
