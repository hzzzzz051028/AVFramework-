#!/usr/bin/env bash
# Video player launched by MiracleCast after a Miracast/WFD RTSP handshake.
# MiracleCast passes the negotiated RTP port with "-p" and optionally the
# negotiated source size with "-r".  Keep the transport stream intact until
# it reaches h264parse; dropping at the compressed-stream level corrupts GOPs.
set -euo pipefail

PORT=7236

while getopts ':p:r:s:d:a' option; do
  case "$option" in
    p) PORT="$OPTARG" ;;
    # The HDMI plane selects the display size.  Never software-scale here.
    r|s|d|a) ;;
    *) exit 2 ;;
  esac
done

export GST_PLUGIN_PATH="${GST_PLUGIN_PATH:-/opt/screencast/vendor/gstreamer-rockchip/lib/gstreamer-1.0}"
export LD_LIBRARY_PATH="${LD_LIBRARY_PATH:-/opt/screencast/vendor/mpp/lib}"

exec /usr/bin/gst-launch-1.0 -e \
  udpsrc port="$PORT" caps='application/x-rtp,media=video' ! \
  rtpjitterbuffer latency=25 drop-on-latency=false ! \
  rtpmp2tdepay ! tsdemux name=demux \
  demux. ! queue max-size-buffers=0 max-size-bytes=0 max-size-time=0 ! \
  h264parse ! mppvideodec ! \
  queue max-size-buffers=2 max-size-bytes=0 max-size-time=0 leaky=downstream ! \
  kmssink plane-id=71 sync=false max-lateness=0
