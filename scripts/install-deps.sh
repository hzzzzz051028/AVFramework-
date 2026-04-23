#!/bin/bash
# ========================================
# 无线投屏接收器 - RK3588 依赖安装脚本
# 适用于 Debian/Ubuntu (Rockchip 官方镜像)
# ========================================

set -e

COLOR_RED='\033[0;31m'
COLOR_GREEN='\033[0;32m'
COLOR_YELLOW='\033[1;33m'
COLOR_NC='\033[0m'

info()  { echo -e "${COLOR_GREEN}[INFO]${COLOR_NC} $*"; }
warn()  { echo -e "${COLOR_YELLOW}[WARN]${COLOR_NC} $*"; }
error() { echo -e "${COLOR_RED}[ERROR]${COLOR_NC} $*"; }

# ---- 检测系统 ----
if [ -f /etc/os-release ]; then
    . /etc/os-release
    info "系统: $PRETTY_NAME"
else
    error "无法检测系统版本"
    exit 1
fi

# ---- 1. 系统基础依赖 ----
info "安装系统依赖..."
sudo apt-get update
sudo apt-get install -y \
    python3 \
    python3-pip \
    python3-gi \
    python3-dev \
    gir1.2-gst-plugins-base-1.0 \
    gir1.2-gstreamer-1.0 \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-libav \
    gstreamer1.0-tools \
    gstreamer1.0-x \
    libglib2.0-dev \
    pkg-config \
    cmake \
    git \
    wget

# ---- 2. GStreamer WebRTC 插件 ----
info "安装 GStreamer WebRTC 支持..."
sudo apt-get install -y \
    gstreamer1.0-plugins-rstp \
    gstreamer1.0-rtsp-server \
    libnice10 \
    libsrtp2-1 \
    libwebrtc-audio-processing1

# ---- 3. Rockchip MPP / RGA (RK3588 专用) ----
info "检查 Rockchip 硬件支持..."
if ls /sys/class/video4linux/video* 1>/dev/null 2>&1; then
    warn "检测到 RK 设备节点, 尝试安装 Rockchip GStreamer 插件..."

    # MPP 库
    sudo apt-get install -y \
        librockchip-mpp-dev \
        librga-dev \
        rockchip-multimedia-config \
        2>/dev/null || {
        warn "apt 未找到 rockchip 包, 尝试从源码安装..."
        # 从 Rockchip 官方仓库安装
        ROCKCHIP_GST_DIR="/opt/rockchip-gst"
        if [ ! -d "$ROCKCHIP_GST_DIR" ]; then
            git clone https://github.com/RockChip-GStreamer/gst-rockchip.git "$ROCKCHIP_GST_DIR" || \
                warn "无法克隆 gst-rockchip, 请手动安装"
        fi
    }

    # GStreamer rockchip 插件 (rkmpph264dec, rkrgascale 等)
    if pkg-config --exists gstreamer-rkmpp 2>/dev/null; then
        info "GStreamer Rockchip 插件已安装"
    else
        warn "GStreamer Rockchip 插件未找到, 硬件解码可能不可用"
        warn "请参考: https://github.com/RockChip-GStreamer/gst-rockchip"
    fi
else
    warn "未检测到 Rockchip 设备, 将使用软件解码 (开发模式)"
fi

# ---- 4. PulseAudio (音频输出) ----
info "安装音频支持..."
sudo apt-get install -y \
    pulseaudio \
    gstreamer1.0-pulseaudio \
    libpulse-dev

# ---- 5. Python 依赖 ----
info "安装 Python 依赖..."
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
REQUIREMENTS="$PROJECT_DIR/backend/requirements.txt"

if [ -f "$REQUIREMENTS" ]; then
    pip3 install -r "$REQUIREMENTS"
else
    pip3 install aiohttp psutil
fi

# ---- 6. 验证 ----
info ""
info "========== 安装验证 =========="

# GStreamer
if command -v gst-launch-1.0 &>/dev/null; then
    GST_VER=$(gst-launch-1.0 --version | head -1)
    info "GStreamer: $GST_VER"
else
    error "GStreamer 未安装"
fi

# WebRTC 插件
if gst-inspect-1.0 webrtcbin &>/dev/null; then
    info "webrtcbin: 可用"
else
    error "webrtcbin: 不可用"
fi

# Python gi
if python3 -c "import gi; gi.require_version('Gst', '1.0')" 2>/dev/null; then
    info "Python GI (GStreamer): 可用"
else
    error "Python GI (GStreamer): 不可用"
fi

# MPP (RK3588)
if [ -e /dev/mpp_service ] || [ -e /dev/dri/renderD128 ]; then
    info "Rockchip MPP: 检测到"
else
    warn "Rockchip MPP: 未检测到 (软件回退)"
fi

# DRM/KMS
if ls /dev/dri/card* 1>/dev/null 2>&1; then
    info "DRM/KMS: 可用"
else
    warn "DRM/KMS: 不可用"
fi

# aiohttp
if python3 -c "import aiohttp" 2>/dev/null; then
    info "aiohttp: 可用"
else
    error "aiohttp: 未安装"
fi

info ""
info "========== 完成 =========="
info "运行: cd backend && python3 server.py"
