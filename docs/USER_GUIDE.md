# 🖥️ 屏幕共享系统 - 完整使用指引

## 📋 目录
- [系统概述](#系统概述)
- [环境要求](#环境要求)
- [安装配置](#安装配置)
- [使用指南](#使用指南)
- [故障排除](#故障排除)
- [高级配置](#高级配置)

---

## 系统概述

### 功能说明
本系统是一个基于 WebRTC 的屏幕共享应用，支持：
- 📤 **屏幕共享**：实时共享你的屏幕、窗口或浏览器标签页
- 📥 **远程观看**：在另一个浏览器中实时观看共享的屏幕
- 🏠 **本地运行**：所有数据在本地传输，无需外网连接
- ⚡ **低延迟**：基于 WebRTC P2P 技术，实现毫秒级延迟

### 技术架构
```
┌─────────────┐
│  共享端     │ → getDisplayMedia() 捕获屏幕
│  (Browser A) │   ↓
└─────────────┘   WebRTC Peer Connection
                  ↓
┌─────────────┐
│  信令服务器  │ → WebSocket 协调连接
│ (Node.js)    │   ↓
└─────────────┘   P2P 直连
                  ↓
┌─────────────┐
│  观看端     │ → 接收并显示屏幕流
│  (Browser B) │
└─────────────┘
```

---

## 环境要求

### 硬件要求

| 组件 | 最低配置 | 推荐配置 |
|------|----------|----------|
| **CPU** | 双核 2.0GHz | 四核 2.5GHz+ |
| **内存** | 4GB RAM | 8GB+ RAM |
| **网络** | 本地回环 | 本地千兆网络 |
| **显卡** | 集成显卡 | 独立显卡（硬件加速） |
| **显示器** | 1280×720 | 1920×1080 或更高 |

### 软件要求

| 软件 | 版本要求 | 推荐版本 | 下载地址 |
|------|----------|----------|----------|
| **操作系统** | Windows 10 1809+ | Windows 11 | - |
| **Node.js** | 18.x+ | 20.x LTS | [nodejs.org](https://nodejs.org/) |
| **浏览器** | 支持 WebRTC | 最新版 | 见下方 |
| **C++ 编译器** | MSVC 19.44+ | Visual Studio 2022 | [visualstudio.microsoft.com](https://visualstudio.microsoft.com/) |
| **CMake** | 3.15+ | 3.28+ | [cmake.org](https://cmake.org/) |

### 浏览器支持

| 浏览器 | 版本要求 | 屏幕共享 | WebRTC | 备注 |
|--------|----------|----------|--------|------|
| **Google Chrome** | 72+ | ✅ | ✅ | 最佳兼容性 |
| **Microsoft Edge** | 79+ | ✅ | ✅ | 基于 Chromium |
| **Mozilla Firefox** | 72+ | ✅ | ✅ | 需启用相应权限 |
| **Opera** | 60+ | ✅ | ✅ | 基于 Chromium |

### 推荐配置

#### 开发环境配置
```
操作系统：Windows 11 专业版
处理器：Intel Core i7 / AMD Ryzen 7
内存：16GB DDR4
存储：512GB NVMe SSD
网络：本地回环 / 千兆局域网
```

#### 生产环境配置
```
操作系统：Windows Server 2022
处理器：Intel Xeon / AMD EPYC
内存：32GB DDR4 ECC
存储：1TB NVMe SSD
网络：万兆企业级网络
```

---

## 安装配置

### 步骤 1：安装 Node.js

#### Windows 安装

1. **下载安装包**
   - 访问：https://nodejs.org/
   - 下载：LTS 版本（推荐 20.x）
   - 文件名：`node-v20.x.x-x64.msi`

2. **运行安装程序**
   ```
   双击 .msi 文件
   → 接受许可协议
   → 选择安装路径（默认：C:\Program Files\nodejs\）
   → 确保 "Add to PATH" 已勾选
   → 点击 "Install"
   ```

3. **验证安装**
   ```powershell
   node --version
   npm --version
   ```

   预期输出：
   ```
   v20.x.x
   10.x.x
   ```

#### Chocolatey 安装（推荐给开发者）

```powershell
# 以管理员身份运行 PowerShell
choco install nodejs-lts
```

### 步骤 2：安装项目依赖

```bash
cd C:\Users\1000003244\Desktop\video_test\backend
npm install
```

预期输出：
```
added 29 packages, and audited 30 packages in 3s
```

### 步骤 3：配置防火墙

**Windows 防火墙配置**

1. 打开 "Windows Defender 防火墙"
2. 点击 "高级设置"
3. 选择 "入站规则"
4. 点击 "新建规则" → "端口"
   - 规则名称：`Screen Share Server`
   - 端口：`8081`
   - 协议：`TCP`
   - 操作：`允许连接`
5. 保存规则

**第三方防火墙**

如果使用企业防火墙软件，确保允许：
- TCP 端口 8080（HTTP）
- TCP 端口 8081（WebSocket）
- Node.js 可执行文件

### 步骤 4：配置浏览器权限

#### Chrome/Edge

1. 打开浏览器设置
2. 搜索 "权限"
3. 点击 "网站设置" → "权限"
4. 确保 "屏幕共享" 权限已启用

#### Firefox

1. 地址栏输入：`about:config`
2. 搜索：`media.getdisplaymedia`
3. 设置为：`true`

---

## 使用指南

### 快速开始

#### 启动系统

**方式 1：使用脚本（推荐）**

```bash
scripts\test-screenshare.bat
```

**方式 2：手动启动**

1. 启动信令服务器：
   ```bash
   cd backend
   npm start
   ```

2. 打开网页界面：
   ```bash
   start frontend\screenshare.html
   ```

### 共享屏幕步骤

#### 1. 选择共享模式

在打开的 `screenshare.html` 页面中：
- 确保选中"📤 共享屏幕"模式
- 按钮应该显示为高亮状态

#### 2. 开始共享

1. 点击"🎬 开始共享"按钮
2. 浏览器会弹出屏幕选择对话框
3. 选择要共享的内容：

```
┌─────────────────────────────┐
│  选择要共享的内容            │
├─────────────────────────────┤
│  ● 整个屏幕                  │
│  │   屏幕 1 (1920×1080)      │
│  ● 应用窗口                  │
│  │   Chrome                  │
│  ● 浏览器标签页              │
│  │   当前标签页              │
└─────────────────────────────┘
```

4. 选择后点击"共享"按钮

#### 3. 获取会话 ID

系统会自动生成一个会话 ID：
```
会话 ID: sess_abc123
```

**重要：** 复制或记录这个 ID，观看端需要使用它。

#### 4. 验证共享

- 在"准备就绪"位置应该显示本地屏幕画面
- 状态显示："✅ 屏幕共享已启动！会话 ID: sess_abc123"

### 观看屏幕步骤

#### 1. 切换到观看模式

在 `screenshare.html` 页面中：
- 点击"📥 观看屏幕"按钮
- 界面切换到观看模式

#### 2. 输入会话 ID

在"输入会话 ID"输入框中：
- 输入共享端提供的会话 ID
- 例如：`sess_abc123`

#### 3. 建立连接

1. 点击"🔗 连接"按钮
2. 等待连接建立（通常 2-5 秒）
3. 连接成功后：
   - 视频窗口会显示共享的屏幕
   - 状态显示："✅ 已连接到屏幕共享！"

#### 4. 控制选项

观看端提供以下控制：
- **音量控制**：调整系统音量
- **全屏模式**：按 `F11` 进入/退出全屏
- **截图功能**：使用系统截图工具

### 停止共享

#### 共享端停止

1. 点击"🛑 停止共享"按钮
2. 本地视频停止显示
3. 观看端连接自动断开

#### 观看端断开

1. 点击"🛑 断开连接"按钮
2. 视频画面停止显示
3. 可以重新连接其他会话

---

## 故障排除

### 常见问题

#### 问题 1：无法启动服务器

**症状：**
```
Error: listen EADDRINUSE: address already in use :::8081
```

**解决方案：**
```powershell
# 方法 1：关闭占用端口的进程
netstat -ano | findstr :8081
taskkill /F /PID <进程ID>

# 方法 2：使用不同端口
# 修改 backend/signaling-server.js 中的端口
const WS_PORT = 8082;  // 改为其他端口
```

#### 问题 2：按钮点击无反应

**症状：**
- 点击任何按钮都没有反应
- JavaScript 控制台无错误信息

**解决方案：**

1. 检查浏览器是否支持：
   - 按 `F12` 打开开发者工具
   - 查看 Console 标签是否有错误
   - 确认没有 JavaScript 错误

2. 清除浏览器缓存：
   - `Ctrl + Shift + Delete`
   - 勾选"缓存的图像和文件"
   - 点击"清除数据"

3. 尝试其他浏览器：
   - Chrome/Edge → Firefox
   - Firefox → Chrome

#### 问题 3：无法选择屏幕

**症状：**
- 点击"开始共享"后没有屏幕选择对话框
- 浏览器提示权限被拒绝

**解决方案：**

1. 检查浏览器权限：
   - 地址栏左侧点击锁图标
   - 查看"网站设置"中的权限
   - 确保"屏幕捕获"权限为"允许"

2. 使用 HTTPS 或 localhost：
   - 如果是通过网络访问，需要 HTTPS
   - 本地文件可以直接访问

3. 检查屏幕录制权限：
   - Windows 设置 → 隐私 → 屏幕录制
   - 确允允许访问

#### 问题 4：连接超时

**症状：**
- 输入会话 ID 后一直显示"正在连接"
- 长时间无响应

**解决方案：**

1. 检查服务器状态：
   ```
   浏览器打开：http://localhost:8080/health
   应该返回：{"status":"ok","sessions":0}
   ```

2. 确认会话 ID 正确：
   - 区分大小写
   - 检查是否有多余空格
   - 重新输入完整的会话 ID

3. 重启服务器：
   ```bash
   # 停止当前服务器
   taskkill /F /IM node.exe
   
   # 重新启动
   cd backend
   npm start
   ```

#### 问题 5：画面卡顿或延迟

**症状：**
- 视频画面不流畅
- 延迟很高

**解决方案：**

1. 降低分辨率：
   ```
   共享时选择特定窗口而不是整个屏幕
   避免共享高分辨率内容
   ```

2. 关闭不必要的应用：
   ```
   关闭占用 CPU 的应用程序
   暂停下载和更新
   ```

3. 检查网络：
   ```
   ping localhost
   确保本地网络正常
   ```

### 高级故障排除

#### 查看日志

**浏览器控制台日志：**
1. 按 `F12` 打开开发者工具
2. 切换到 "Console" 标签
3. 查看日志输出：
   ```
   [WS] WebSocket connected
   [Session] Created: sess_abc123
   📹 Received screen share track
   🔄 Connection state: connected
   ```

**服务器日志：**
```
在服务器窗口查看实时日志：
[WS] Client connected: 123456789
[Session] Created: sess_abc123
[Session] Client 987654321 joined: sess_abc123
```

#### 性能监控

**浏览器性能监控：**
1. 按 `F12` 打开开发者工具
2. 切换到 "Performance" 标签
3. 点击 "录制"按钮
4. 执行操作后停止录制
5. 分析性能瓶颈

**系统资源监控：**
```powershell
# CPU 使用率
Get-Counter '\Processor(_Total)\% Processor Time'

# 内存使用
Get-Counter '\Memory\Available MBytes'

# 网络连接
netstat -an | findstr :8081
```

---

## 高级配置

### 自定义端口

#### 修改服务器端口

编辑 `backend/signaling-server.js`：

```javascript
const HTTP_PORT = 8080;  // 修改 HTTP 端口
const WS_PORT = 8081;    // 修改 WebSocket 端口
```

**更新前端配置：**

编辑 `frontend/screenshare.html`：

```javascript
const WS_URL = 'ws://localhost:8081';  // 修改为新端口
```

### 自定义 ICE 服务器

编辑 HTML 文件中的配置：

```javascript
const config = {
  iceServers: [
    { urls: 'stun:stun.l.google.com:19302' },
    { urls: 'stun:stun1.l.google.com:19302' },
    // 添加自定义 STUN/TURN 服务器
    {
      urls: 'turn:your-turn-server.com:3478',
      username: 'user',
      credential: 'pass'
    }
  ]
};

this.pc = new RTCPeerConnection(config);
```

### 调整视频质量

修改 SDP Offer 创建时的参数：

```javascript
const offer = await this.pc.createOffer({
  offerToReceiveVideo: false,
  offerToReceiveAudio: false,
  voiceActivityDetection: false,
  iceRestart: false
});
```

### 添加音频共享

修改屏幕捕获配置：

```javascript
this.localStream = await navigator.mediaDevices.getDisplayMedia({
  video: {
    cursor: "always",
    width: { ideal: 1920 },
    height: { ideal: 1080 },
    frameRate: { ideal: 30 }
  },
  audio: true  // 添加音频捕获
});
```

**注意：** 需要系统音频权限

### 设置会话超时

在信令服务器中添加超时逻辑：

```javascript
// 设置会话超时时间（毫秒）
const SESSION_TIMEOUT = 30 * 60 * 1000; // 30分钟

// 定时清理过期会话
setInterval(() => {
  const now = Date.now();
  for (const [sessionId, session] of sessions.entries()) {
    if (now - session.createdAt > SESSION_TIMEOUT) {
      sessions.delete(sessionId);
      console.log(`[Session] Timeout: ${sessionId}`);
    }
  }
}, 60000); // 每分钟检查一次
```

---

## 性能优化

### 网络优化

#### 启用 QoS（服务质量）

1. 打开组策略编辑器：`gpedit.msc`
2. 导航到：计算机配置 → 管理模板 → 网络 → QoS 数据包计划程序
3. 启用"限制可保留带宽"
4. 为端口 8081 设置高优先级

#### 调整缓冲区大小

```javascript
// 在创建 PeerConnection 时配置
this.pc = new RTPeerConnection({
  iceServers: this.config,
  iceTransportPolicy: 'all',
  bundlePolicy: 'max-bundle',
  rtcpMuxPolicy: 'require'
});
```

### 资源优化

#### 限制视频分辨率

```javascript
// 捕获时限制分辨率
this.localStream = await navigator.mediaDevices.getDisplayMedia({
  video: {
    width: { max: 1920 },
    height: { max: 1080 },
    frameRate: { max: 30 }
  },
  audio: false
});
```

#### 启用硬件加速

确保浏览器启用了硬件加速：
- Chrome：`chrome://flags` → 搜索"hardware"
- Edge：`edge://flags` → 搜索"hardware"
- 启用 "Hardware-accelerated video decode"
- 启用 "WebRTC Hardware Video Encoding"

---

## 安全配置

### 网络安全

#### 限制本地访问

在信令服务器中添加来源检查：

```javascript
const ALLOWED_ORIGINS = ['localhost', '127.0.0.1'];

httpServer.on('request', (req, res) => {
  const origin = req.headers.origin;
  if (ALLOWED_ORIGINS.includes(origin)) {
    res.setHeader('Access-Control-Allow-Origin', origin);
  }
  // ... 其他处理
});
```

#### 启用 WSS（加密 WebSocket）

```javascript
const WebSocket = require('ws');
const fs = require('fs');

const wss = new WebSocket.Server({
  port: WS_PORT,
  cert: fs.readFileSync('path/to/cert.pem'),
  key: fs.readFileSync('path/to/key.pem')
});
```

### 隐私保护

#### 禁用日志记录敏感信息

```javascript
// 不要在日志中记录屏幕内容
// 不要记录用户操作细节
```

#### 会话隔离

```javascript
// 每个会话独立，不共享数据
// 会话结束后立即清理所有数据
```

---

## 附录

### 键盘快捷键

| 功能 | 快捷键 |
|------|--------|
| 刷新页面 | `F5` |
| 开发者工具 | `F12` |
| 全屏模式 | `F11` |
| 停止加载 | `Esc` |
| 查找 | `Ctrl+F` |
| 保存页面 | `Ctrl+S` |

### 命令行快捷方式

```bash
# 快速启动
cd C:\Users\1000003244\Desktop\video_test
npm start && start frontend\screenshare.html

# 停止所有 Node 进程
taskkill /F /IM node.exe

# 检查端口占用
netstat -ano | findstr :8080 :8081

# 查看系统资源
tasklist | findstr node
```

### 支持和帮助

**文档位置：**
- 主文档：`README.md`
- 快速开始：`QUICKSTART.md`
- 功能说明：`SCREENSHARE_GUIDE.md`

**获取帮助：**
1. 查看浏览器控制台日志
2. 查看服务器终端输出
3. 检查本文档的故障排除部分

---

**版本信息**
- 当前版本：1.0.0
- 最后更新：2026-04-22
- 技术栈：Node.js + WebRTC + WebSocket

**许可证**
MIT License - 详见 LICENSE 文件
