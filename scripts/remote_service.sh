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
  tar --exclude='.git' --exclude='.venv' --exclude='__pycache__' --exclude='.pytest_cache' \
    -czf - backend frontend scripts | \
    ssh "${SSH_OPTS[@]}" "$TARGET" \
      "rm -rf /tmp/screencast-release; mkdir -p /tmp/screencast-release; tar -xzf - -C /tmp/screencast-release"
  remote "sudo mkdir -p '$RK_DIR'; sudo cp -a /tmp/screencast-release/backend '$RK_DIR/'; sudo cp -a /tmp/screencast-release/frontend '$RK_DIR/'; sudo cp /tmp/screencast-release/scripts/screencast-standby.service /etc/systemd/system/screencast-standby.service; sudo systemctl daemon-reload; sudo systemctl enable screencast-standby.service; sudo systemctl restart '$SERVICE'; sudo systemctl restart screencast-standby.service; rm -rf /tmp/screencast-release"
  echo "Deployed and restarted $SERVICE on $TARGET"
}

case "${1:-}" in
  check) check ;;
  install) install ;;
  deploy) deploy ;;
  start) remote "sudo systemctl start '$SERVICE'" ;;
  stop) remote "sudo systemctl stop '$SERVICE'" ;;
  restart) remote "sudo systemctl restart '$SERVICE'" ;;
  status) remote "sudo systemctl status '$SERVICE' --no-pager; printf '\nHealth:\n'; (curl -kfsS --max-time 5 https://127.0.0.1:8080/health || curl -fsS --max-time 5 http://127.0.0.1:8080/health)" ;;
  logs) remote "sudo journalctl -u '$SERVICE' -f -n 100" ;;
  shell) ssh "${SSH_OPTS[@]}" "$TARGET" ;;
  *) usage; exit 2 ;;
esac
