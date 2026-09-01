#!/usr/bin/env bash
# Enable the isolated Rockchip MPP GStreamer plugin for screencast.service.
#
# The plugin and MPP library are deliberately kept under /opt/screencast so
# this script never replaces distro GStreamer libraries.  Running it is safe
# to repeat.  To roll back, remove mpp.conf and restart the service.
set -euo pipefail

SERVICE="${SERVICE:-screencast}"
MPP_ROOT="${MPP_ROOT:-/opt/screencast/vendor/mpp}"
PLUGIN_ROOT="${PLUGIN_ROOT:-/opt/screencast/vendor/gstreamer-rockchip/lib/gstreamer-1.0}"
DROPIN_DIR="/etc/systemd/system/${SERVICE}.service.d"

if [[ ! -f "${MPP_ROOT}/lib/librockchip_mpp.so.1" ]]; then
  echo "MPP library not found: ${MPP_ROOT}/lib/librockchip_mpp.so.1" >&2
  exit 1
fi

if [[ ! -f "${PLUGIN_ROOT}/libgstrockchipmpp.so" ]]; then
  echo "MPP GStreamer plugin not found: ${PLUGIN_ROOT}/libgstrockchipmpp.so" >&2
  exit 1
fi

probe_registry="$(mktemp /tmp/screencast-gst-registry.XXXXXX)"
trap 'rm -f "${probe_registry}"' EXIT

env \
  LD_LIBRARY_PATH="${MPP_ROOT}/lib" \
  GST_PLUGIN_PATH="${PLUGIN_ROOT}" \
  GST_REGISTRY="${probe_registry}" \
  gst-inspect-1.0 mppvideodec >/dev/null

sudo install -d -m 0755 "${DROPIN_DIR}"
sudo tee "${DROPIN_DIR}/mpp.conf" >/dev/null <<EOF
[Service]
Environment="GST_PLUGIN_PATH=${PLUGIN_ROOT}"
Environment="LD_LIBRARY_PATH=${MPP_ROOT}/lib"
EOF

sudo systemctl daemon-reload
sudo systemctl restart "${SERVICE}"
sudo systemctl --no-pager --full status "${SERVICE}"
