# 屏幕共享系统

基于 WebRTC P2P 技术的局域网屏幕共享应用。

## 功能特性

- 📤 **屏幕共享**：实时共享屏幕、窗口或浏览器标签页
- 📥 **远程观看**：在另一个浏览器中实时观看共享的屏幕
- 🏠 **局域网访问**：所有数据在本地传输，无需外网连接
- ⚡ **低延迟**：基于 WebRTC P2P 技术
- 🐍 **Python 后端**：简单易用的 Python 服务器

## 技术架构

```
┌─────────────┐
│  共享端     │ → getDisplayMedia() 捕获屏幕
│  (Browser A) │   ↓
└─────────────┘   WebRTC Peer Connection
                  ↓
┌─────────────┐
│  信令服务器  │ → WebSocket 协调连接
│  (Python)    │   ↓
└─────────────┘   P2P 直连
                  ↓
┌─────────────┐
│  观看端     │ → 接收并显示屏幕流
│  (Browser B) │
└─────────────┘
```

## 环境要求

### 软件要求

| 软件 | 版本要求 |
|------|----------|
| Python | 3.8+ |
| 浏览器 | Chrome 72+, Edge 79+, Firefox 67+ |

## 快速开始

### 1. 安装依赖

```bash
cd backend
pip install -r requirements.txt
```

### 2. 启动服务器

```bash
python server.py
```

或使用启动脚本：
```bash
scripts\start-server.bat
```

### 3. 访问系统

**在主机上：**
- 浏览器打开：`http://localhost:8080`
- 点击"开始共享"
- 复制会话 ID

**在观看设备上：**
- 浏览器打开：`http://YOUR_IP:8080/view.html`
- 输入会话 ID
- 点击"连接"

## 端口说明

| 端口 | 用途 |
|------|------|
| 8080 | HTTP 服务器（网页） |
| 8081 | WebSocket 服务器（信令） |

## 目录结构

```
video_test/
├── backend/
│   ├── server.py          # Python 信令服务器
│   └── requirements.txt   # Python 依赖
├── frontend/
│   ├── screenshare.html   # 共享端界面
│   └── view.html          # 观看端界面
├── scripts/
│   └── start-server.bat   # 启动脚本
└── docs/
    └── QUICK_LAN_GUIDE.md # 快速使用指南
```

## API 端点

| 端点 | 功能 |
|------|------|
| `/` | 屏幕共享界面 |
| `/view.html` | 观看界面 |
| `/health` | 健康检查 |
| `/info` | 服务器信息 |

## 常见问题

### Q: 观看设备无法连接？

**A:** 检查防火墙是否允许端口 8080/8081

```powershell
New-NetFirewallRule -DisplayName "Screen Share" -Direction Inbound -Protocol TCP -LocalPort 8080,8081 -Action Allow
```

### Q: 本机无法共享屏幕？

**A:** 使用 `http://localhost:8080` 而不是 `http://IP:8080`

### Q: 如何查看本机 IP？

**A:** 
```powershell
ipconfig
```
找到"IPv4 地址"

## 许可证

MIT License
