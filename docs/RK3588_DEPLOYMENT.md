# RK3588 投屏器部署指南

## 一、系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                     RK3588 硬件设备                          │
│                                                              │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐  │
│  │  发送端 PC   │     │  发送端 PC   │     │  发送端 PC   │  │
│  └──────┬──────┘     └──────┬──────┘     └──────┬──────┘  │
│         │                    │                    │         │
│         └────────────────────┼────────────────────┘         │
│                              │ WebRTC                        │
│                              ▼                               │
│  ┌─────────────────────────────────────────────────────┐   │
│  │           Python server.py (aiohttp)                 │   │
│  │           + GStreamer webrtcbin                     │   │
│  └─────────────────────────────────────────────────────┘   │
│                              │                               │
│                              ▼                               │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  MPP硬解 → RGA硬缩放 → DRM/KMS → HDMI/DP 输出        │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
                       ┌──────────┐
                       │  显示器   │
                       │  电视    │
                       │ 投影仪   │
                       └──────────┘
```

## 二、显示输出方案

### 2.1 直接显示 (生产模式)

```python
# backend/gst/display.py 自动选择
kmssink  → DRM/KMS → HDMI/DP 直接输出
```

**特点**:
- ✅ 无需桌面环境
- ✅ 无需 X11
- ✅ 直接操作 framebuffer
- ✅ 零延迟

### 2.2 保底方案

| 异常情况 | 保底方案 |
|----------|----------|
| 显示输出失败 | 串口调试输出 |
| 服务崩溃 | systemd 自动重启 |
| 网络异常 | 状态日志记录 |
| 串口不可用 | 本地日志文件 |

## 三、部署步骤

### 3.1 准备工作

```bash
# 1. 刷写系统 (Ubuntu 20.04/22.04 for RK3588)
# 推荐发行版:
#   - Armbian
#   - Radxa Debian
#   - Ubuntu Server

# 2. 连接到设备
ssh root@<rk3588_ip>

# 3. 上传代码
scp -r backend/ root@<rk3588_ip>:/opt/screencast/
scp -r frontend/ root@<rk3588_ip>:/opt/screencast/
scp scripts/install-rk3588.sh root@<rk3588_ip>:/tmp/
```

### 3.2 自动部署

```bash
# 在 RK3588 上执行
sudo bash /tmp/install-rk3588.sh
```

脚本会自动完成：
1. 系统更新
2. 安装 GStreamer 和依赖
3. 安装 Python 库
4. 创建服务用户
5. 配置 systemd 服务
6. 开机自启动

### 3.3 手动部署 (如需自定义)

```bash
# 安装 GStreamer
sudo apt-get install -y \
    gstreamer1.0-tools \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    python3-gi-3.0 \
    gir1.2-gstreamer-1.0

# 安装 Rockchip 硬件加速
sudo apt-get install -y librockchip-mpp gstreamer1.0-rockchip1

# 安装 Python 依赖
pip3 install aiohttp websockets pyserial

# 测试显示输出
sudo modetest -c  # 查看 HDMI 连接器
```

## 四、配置说明

### 4.1 主配置文件

```bash
/opt/screencast/backend/receiver_config.json
```

```json
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
```

### 4.2 HDMI 连接器配置

```bash
# 查看可用连接器
cat /sys/class/drm/card0-HDMI-A-1/status
cat /sys/class/drm/card0-HDMI-A-2/status

# 指定连接器 (修改配置文件)
"drm_connector": "HDMI-A-1"  # 或 connector-id 数字
```

## 五、服务管理

```bash
# 启动服务
sudo systemctl start screencast

# 停止服务
sudo systemctl stop screencast

# 重启服务
sudo systemctl restart screencast

# 查看状态
sudo systemctl status screencast

# 查看日志
sudo journalctl -u screencast -f

# 开机自启动
sudo systemctl enable screencast

# 禁用自启动
sudo systemctl disable screencast
```

## 六、保底方案使用

### 6.1 串口调试

```bash
# 连接串口 (USB转串口)
sudo minicom -D /dev/ttyUSB0 -b 115200

# 或
sudo screen /dev/ttyUSB0 115200
```

串口会输出：
- 系统启动状态
- WebRTC 连接状态
- 错误信息
- 心跳信号 (证明系统活着)

### 6.2 日志文件

```bash
# 实时日志
tail -f /var/log/screencast/screencast.log

# 搜索错误
grep ERROR /var/log/screencast/screencast.log

# 系统日志
journalctl -u screencast --since "1 hour ago"
```

### 6.3 本地调试

```bash
# SSH 登录后手动运行 (便于调试)
cd /opt/screencast/backend
python3 server.py

# 使用 GStreamer 调试模式
GST_DEBUG=3 python3 server.py
```

## 七、使用流程

### 7.1 发送端 (任意 PC)

```
1. 打开浏览器 (Chrome/Edge/Firefox)
2. 访问 http://<rk3588_ip>:8080
3. 选择"共享屏幕"
4. 点击"开始共享"
5. 选择屏幕/窗口
6. 完成！
```

### 7.2 接收端状态

访问 `http://<rk3588_ip>:8080/dashboard` 查看：
- 硬件状态
- 活跃会话
- 切换布局
- 调节音量

## 八、故障排查

| 问题 | 可能原因 | 解决方案 |
|------|----------|----------|
| 无显示 | HDMI 未连接 | 检查线缆，查看 `cat /sys/class/drm/*/status` |
| 显示黑屏 | 解码失败 | 检查日志，尝试软解 (设置 hw_decode: false) |
| 无法连接 | 防火墙 | 开放 8080/8081 端口 |
| 性能卡顿 | 硬解未启用 | 检查 MPP 驱动，降低分辨率/帧率 |
| 音频无声音 | PulseAudio | 检查 `pactl info` |

## 九、性能优化

### 9.1 硬件加速确认

```bash
# 检查 MPP 设备
ls -la /dev/mpp_service
ls -la /sys/class/video4linux/video10

# 检查 RGA 设备
ls -la /dev/rga*

# 检查 DRM 设备
ls -la /dev/dri/
```

### 9.2 推荐配置

| 场景 | 分辨率 | 帧率 | 编码 |
|------|--------|------|------|
| 标准 1080p | 1920x1080 | 30fps | H.264 |
| 高质量 | 1920x1080 | 60fps | H.264 |
| 多画面 | 1920x1080 | 30fps | H.264 |

## 十、产品化建议

### 10.1 外壳设计
- 散热: RK3588 需要散热片/风扇
- 接口: HDMI输出、LAN口、USB口(调试)

### 10.2 系统优化
```bash
# 禁用不必要的服务
sudo systemctl disable bluetooth

# 设置性能模式
echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor

# 增加 GPU 频率
# 参考: /etc/mpp.conf
```

### 10.3 定制启动画面
```bash
# 替换开机 Logo
# 参考: /boot/boot.bmp 或 splash 屏幕
```
