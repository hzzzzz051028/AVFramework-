#!/bin/bash
# RK3588 一键部署脚本
set -e

echo "[1/5] 更新系统..."
sudo apt-get update -y 2>&1 | tail -3

echo "[2/5] 安装系统依赖..."
sudo apt-get install -y --no-install-recommends \
    python3-pip python3-venv \
    libgstreamer1.0-0 \
    gstreamer1.0-tools \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly \
    python3-gi \
    gobject-introspection \
    gir1.2-gstreamer-1.0 \
    gir1.2-gst-plugins-base-1.0 \
    librockchip-mpp \
    mpp-tools \
    gstreamer1.0-rockchip1 \
    gstreamer1.0-rockchip2 \
    gstreamer1.0-libav \
    pulseaudio \
    git \
    curl \
    htop \
    net-tools \
    qrencode \
    fonts-noto-cjk \
    2>&1 | tail -10

echo "[3/5] 安装 Python 依赖..."
sudo pip3 install --break-system-packages --upgrade pip 2>&1 | tail -2
sudo pip3 install --break-system-packages \
    aiohttp \
    websockets \
    zeroconf \
    2>&1 | tail -5

echo "[4/5] 部署应用..."
sudo mkdir -p /opt/screencast
sudo cp -r backend frontend /opt/screencast/

# RK3588 专用配置
sudo tee /opt/screencast/backend/receiver_config.json > /dev/null <<'CFG'
{
  "server": {
    "host": "0.0.0.0",
    "http_port": 8080
  },
  "display": {
    "width": 1920,
    "height": 1080,
    "framerate": 30
  },
  "webrtc": {
    "max_sessions": 4,
    "preferred_codec": "H264"
  },
  "audio": {
    "enabled": true,
    "master_volume": 80
  },
  "hardware": {
    "hw_decode": true,
    "hw_scale": true,
    "drm_connector": "auto"
  }
}
CFG

echo "[5/5] 配置 systemd 服务..."
sudo tee /etc/systemd/system/screencast.service > /dev/null <<'SVC'
[Unit]
Description=Wireless Display Receiver (RK3588)
After=network-online.target sound.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/screencast/backend
Environment="PYTHONUNBUFFERED=1"
Environment="GST_DEBUG=2"
ExecStart=/usr/bin/python3 server.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=screencast

[Install]
WantedBy=multi-user.target
SVC

sudo systemctl daemon-reload
sudo systemctl enable screencast.service

echo ""
echo "========================================"
echo "  部署完成!"
echo "========================================"
echo "  启动: sudo systemctl start screencast"
echo "  日志: sudo journalctl -u screencast -f"
echo "  访问: http://$(hostname -I | awk '{print $1}'):8080"
echo "========================================"
