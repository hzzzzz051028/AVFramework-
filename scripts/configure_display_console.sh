#!/usr/bin/env bash
# Make HDMI a product display, not a Linux text console.
# SSH and the board's serial console remain available for recovery.
set -euo pipefail

ENV_FILE=/boot/orangepiEnv.txt

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing $ENV_FILE; this board does not use the Orange Pi boot layout." >&2
  exit 1
fi

install -m 0644 "$ENV_FILE" "${ENV_FILE}.screencast-backup"
if grep -q '^console=' "$ENV_FILE"; then
  sed -i 's/^console=.*/console=serial/' "$ENV_FILE"
else
  printf '\nconsole=serial\n' >> "$ENV_FILE"
fi

# Do not let either getty implementation create a login prompt on the
# dedicated display VT.  systemd's autovt helper is distinct from getty@ and
# can otherwise recreate agetty whenever the display service switches to tty2.
systemctl mask getty@tty2.service autovt@tty2.service >/dev/null 2>&1 || true
systemctl stop autovt@tty2.service >/dev/null 2>&1 || true

echo "HDMI text console disabled for next boot; serial console and SSH remain available."
echo "Backup: ${ENV_FILE}.screencast-backup"
