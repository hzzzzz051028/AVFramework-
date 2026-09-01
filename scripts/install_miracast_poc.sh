#!/usr/bin/env bash
# Build an isolated MiracleCast receiver.  This is intentionally not enabled:
# a Miracast session takes exclusive ownership of wlan0 and the HDMI plane.
set -euo pipefail

RK_DIR="${RK_DIR:-/opt/screencast}"
PREFIX="$RK_DIR/vendor/miraclecast"
REVISION="0b7f1f1f6586dc65ff480f3cda5c2170a70aa020"
BUILD_ROOT="$(mktemp -d /tmp/screencast-miracast-build.XXXXXX)"
trap 'rm -rf "$BUILD_ROOT"' EXIT

apt-get update
apt-get install -y --no-install-recommends \
  git meson ninja-build pkg-config libsystemd-dev libudev-dev libreadline-dev \
  gstreamer1.0-tools gstreamer1.0-plugins-bad

git clone https://github.com/albfan/miraclecast.git "$BUILD_ROOT/source"
git -C "$BUILD_ROOT/source" checkout --detach "$REVISION"
meson setup "$BUILD_ROOT/build" "$BUILD_ROOT/source" \
  --prefix="$PREFIX" -Dbuild-tests=false
ninja -C "$BUILD_ROOT/build"
ninja -C "$BUILD_ROOT/build" install

install -d -m 0755 "$RK_DIR/scripts" /etc/dbus-1/system.d
install -m 0755 "$RK_DIR/scripts/miracast_player_rk.sh" "$RK_DIR/scripts/miracast_player_rk.sh"
install -m 0755 "$RK_DIR/scripts/miracast_sink_runner.sh" "$RK_DIR/scripts/miracast_sink_runner.sh"
install -m 0755 "$RK_DIR/scripts/restore_wlan_ap.sh" "$RK_DIR/scripts/restore_wlan_ap.sh"
install -m 0644 "$PREFIX/etc/dbus-1/system.d/org.freedesktop.miracle.conf" \
  /etc/dbus-1/system.d/org.freedesktop.miracle.conf
install -m 0644 "$RK_DIR/scripts/screencast-miracast-wifid.service" \
  /etc/systemd/system/screencast-miracast-wifid.service
install -m 0644 "$RK_DIR/scripts/screencast-miracast-sink.service" \
  /etc/systemd/system/screencast-miracast-sink.service
systemctl reload dbus.service
systemctl daemon-reload
echo "Miracast POC installed. Start manually with: systemctl start screencast-miracast-sink.service"
