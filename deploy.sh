#!/bin/bash
# deploy.sh - 一键部署到 RK3588
# 用法: bash deploy.sh [restart]
set -e

RK_USER="orangepi"
RK_HOST="192.168.1.109"
RK_DIR="/opt/screencast"

echo ">>> 上传文件..."
scp frontend/p2p-sender.html ${RK_USER}@${RK_HOST}:/tmp/
scp frontend/status.html ${RK_USER}@${RK_HOST}:/tmp/
scp backend/server.py ${RK_USER}@${RK_HOST}:/tmp/
scp backend/hdmi_receiver.py ${RK_USER}@${RK_HOST}:/tmp/
scp backend/mdns_service.py ${RK_USER}@${RK_HOST}:/tmp/
scp backend/config.py ${RK_USER}@${RK_HOST}:/tmp/

echo ">>> 部署到 ${RK_DIR}..."
ssh ${RK_USER}@${RK_HOST} "sudo cp /tmp/p2p-sender.html ${RK_DIR}/frontend/ && \
  sudo cp /tmp/status.html ${RK_DIR}/frontend/ && \
  sudo cp /tmp/server.py ${RK_DIR}/backend/ && \
  sudo cp /tmp/hdmi_receiver.py ${RK_DIR}/backend/ && \
  sudo cp /tmp/mdns_service.py ${RK_DIR}/backend/ && \
  sudo cp /tmp/config.py ${RK_DIR}/backend/"

if [ "$1" = "restart" ]; then
  echo ">>> 重启服务..."
  ssh ${RK_USER}@${RK_HOST} "sudo systemctl restart screencast"
fi

echo ">>> 完成!"
