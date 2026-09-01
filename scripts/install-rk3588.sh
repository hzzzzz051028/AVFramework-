#!/bin/bash
# RK3588 投屏器部署脚本
# 适用于 Ubuntu 20.04/22.04 on RK3588

set -e

echo "=========================================="
echo "  RK3588 投屏器 - 部署脚本"
echo "=========================================="
echo ""

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 检查是否为 root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}请使用 sudo 运行此脚本${NC}"
    exit 1
fi

# 1. 系统更新
echo -e "${YELLOW}[1/6] 更新系统...${NC}"
apt-get update
apt-get upgrade -y

# 2. 安装依赖
echo -e "${YELLOW}[2/6] 安装系统依赖...${NC}"

# Python 和 pip
apt-get install -y python3 python3-pip python3-venv

# GStreamer 核心
apt-get install -y \
    libgstreamer1.0-0 \
    gstreamer1.0-tools \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly

# GStreamer Python 绑定
apt-get install -y \
    python3-gi-3.0 \
    gobject-introspection \
    gir1.2-gstreamer-1.0 \
    gir1.2-gst-plugins-base-1.0

# Rockchip 硬件加速
apt-get install -y \
    librockchip-mpp \
    mpp-tools \
    gstreamer1.0-rockchip1 \
    gstreamer1.0-rockchip2 || echo -e "${YELLOW}Rockchip 插件可能需要手动安装${NC}"

# 音频
apt-get install -y \
    gstreamer1.0-pulseaudio \
    pulseaudio

# 网络和工具
apt-get install -y \
    curl \
    git \
    vim \
    htop \
    net-tools \
    qrencode \
    fonts-noto-cjk

# 串口调试
apt-get install -y \
    python3-serial \
    minicom

echo -e "${GREEN}系统依赖安装完成${NC}"

# 3. 配置显示输出
echo -e "${YELLOW}[3/6] 配置显示输出...${NC}"

# 测试显示输出
echo "检测显示设备..."
if [ -e /dev/dri ]; then
    ls -la /dev/dri/
    echo -e "${GREEN}DRM 设备存在${NC}"
else
    echo -e "${RED}未找到 DRM 设备${NC}"
fi

# 4. 安装 Python 依赖
echo -e "${YELLOW}[4/6] 安装 Python 依赖...${NC}"
pip3 install --break-system-packages --upgrade pip
pip3 install --break-system-packages \
    aiohttp \
    websockets \
    pyserial

# 5. 创建服务用户
echo -e "${YELLOW}[5/6] 配置服务用户...${NC}"
if ! id -u screencast &>/dev/null; then
    useradd -r -s /bin/false -d /opt/screencast screencast
    echo -e "${GREEN}创建服务用户 screencast${NC}"
fi

# 6. 安装应用
echo -e "${YELLOW}[6/6] 安装应用...${NC}"

INSTALL_DIR="/opt/screencast"
mkdir -p $INSTALL_DIR

# 复制文件
cp -r backend $INSTALL_DIR/
cp -r frontend $INSTALL_DIR/

# 设置权限
chown -R screencast:screencast $INSTALL_DIR

# 创建配置
cat > $INSTALL_DIR/backend/receiver_config.json <<EOF
{
  "server": {
    "host": "0.0.0.0",
    "http_port": 8080,
    "ws_port": 8081
  },
  "display": {
    "width": 1920,
    "height": 1080,
    "framerate": 60,
    "layout": "auto"
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
EOF

echo -e "${GREEN}应用安装完成: $INSTALL_DIR${NC}"

# 7. 安装 systemd 服务
echo ""
echo -e "${YELLOW}安装系统服务...${NC}"

cat > /etc/systemd/system/screencast.service <<EOF
[Unit]
Description=Wireless Display Receiver (RK3588)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=screencast
Group=screencast
WorkingDirectory=$INSTALL_DIR/backend
Environment="PYTHONUNBUFFERED=1"
Environment="GST_DEBUG=2"
ExecStart=/usr/bin/python3 server.py
Restart=always
RestartSec=5

# 安全限制
NoNewPrivileges=true
PrivateTmp=true

# 日志
StandardOutput=journal
StandardError=journal
SyslogIdentifier=screencast

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable screencast.service

echo ""
echo "=========================================="
echo -e "${GREEN}部署完成！${NC}"
echo "=========================================="
echo ""
echo "管理命令："
echo "  启动服务:   sudo systemctl start screencast"
echo "  停止服务:   sudo systemctl stop screencast"
echo "  重启服务:   sudo systemctl restart screencast"
echo "  查看状态:   sudo systemctl status screencast"
echo "  查看日志:   sudo journalctl -u screencast -f"
echo ""
echo "访问地址："
echo "  Web 界面:   http://$(hostname -I | awk '{print $1}'):8080"
echo "  状态面板:   http://$(hostname -I | awk '{print $1}'):8080/dashboard"
echo ""
echo "串口调试 (保底方案)："
echo "  连接串口:   sudo minicom -D /dev/ttyS0 -b 115200"
echo ""
echo "=========================================="
