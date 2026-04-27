---
name: webrtc-screen-sharing
description: WebRTC 无线投屏系统开发经验 - Windows 本地开发 + RK3588 硬件部署
---

# WebRTC 无线投屏系统 - 开发经验 Skill

## 项目概述

基于 WebRTC 的无线投屏接收器，用于 RK3588 硬件部署。支持浏览器发起投屏，接收端通过 GStreamer 解码并显示。

**技术栈：**
- 后端：Python + aiohttp + GStreamer
- 前端：原生 JavaScript + WebRTC API
- 信令：WHEP (RFC 9372) + WebSocket 兼容
- 硬件加速：MPP decode + RGA scale + DRM/KMS display

**当前状态：** Windows 本地开发环境，10/10 功能测试通过，准备 RK3588 移植。

---

## 核心架构

```
browser (sender)              receiver (RK3588)
    |                              |
    |-- getUserMedia ----->     webrtcbin
    |                              |
    |-- WebRTC SDP ----->      gst-launch
    |                              |
    |-- ICE candidates -->    mpp/rga/drm
                                  |
                               HDMI/LCD
```

**后端模块：**
- `backend/server.py` - HTTP/WebSocket 服务器，WHEP 信令端点
- `backend/signaling_server.py` - 独立信令服务器（备用）
- `gst/receiver.py` - WebRTC 接收器，管理 GStreamer 管线
- `gst/compositor.py` - 多路视频合成
- `gst/audio_mixer.py` - 音频混音
- `mdns_service.py` - mDNS 设备发现

**前端模块：**
- `frontend/sender.html` - 投屏发送端
- `frontend/view.html` - 观看端
- `frontend/dashboard.html` - 状态控制面板

---

## 开发经验总结

### 1. 静态文件路由

**问题：** aiohttp 静态文件路由，lambda 函数返回 404

**错误代码：**
```python
app.router.add_get("/sender.html", lambda r: web.FileResponse(FRONTEND_DIR / "sender.html"))
```

**解决方案：** 使用 async 函数替代 lambda
```python
async def sender_html_handler(request):
    sender_path = FRONTEND_DIR / "sender.html"
    if sender_path.exists():
        return web.FileResponse(sender_path)
    return web.Response(text="Sender page not found", status=404)

app.router.add_get("/sender.html", sender_html_handler)
```

**原因：** aiohttp 路由处理器需要协程函数，lambda 可能不被正确识别。

---

### 2. WebSocket 超时参数

**问题：** `websockets.connect()` 不支持 `timeout` 参数
```python
async with websockets.connect("ws://localhost:8080/ws", timeout=5) as ws:
```

**解决方案：** 使用 `asyncio.wait_for()`
```python
async with websockets.connect("ws://localhost:8080/ws") as ws:
    await asyncio.wait_for(ws.recv(), timeout=5.0)
```

---

### 3. Windows 控制台编码

**问题：** emoji 字符在 Windows 控制台显示为乱码

**解决方案：** 使用纯文本标记
```python
# 坏: print("[✅] Test passed")
# 好: print("[PASS] Test passed")
```

---

### 4. 设备发现 (mDNS)

**实现：**
- `mdns_service.py` - 使用 zeroconf 库
- 自动广播服务到局域网
- 前端自动发现并列出可用设备

**注意：** Windows 开发环境可能没有 zeroconf，需要容错处理：
```python
try:
    from zeroconf import ServiceInfo, Zeroconf
except ImportError:
    logger.warning("zeroconf 未安装，mDNS 功能不可用")
```

---

### 5. GStreamer WebRTC 关键点

**Promise 必须用 wait()，不能 interrupt()：**
```python
# 错误：interrupt() 会中断异步操作，Answer 不会生成
promise = Gst.Promise.new()
element.emit("set-remote-description", offer, promise)
promise.interrupt()  # ❌

# 正确：wait() 等待操作完成
promise = Gst.Promise.new()
element.emit("set-remote-description", offer, promise)
promise.wait()  # ✅
```

**GLib 线程必须 join：**
```python
def stop(self):
    if self._pipeline:
        self._pipeline.set_state(Gst.State.NULL)
    if self._loop:
        self._loop.quit()
    if self._glib_thread and self._glib_thread.is_alive():
        self._glib_thread.join(timeout=5)  # 必须等待，否则 MPP 硬件状态残留
```

**ICE 候选添加（跨版本兼容）：**
```python
# 错误：WebRTCICECandidate.init 在很多版本不存在
ice = GstWebRTC.WebRTCICECandidate.init(sdp_mid, mline_index, candidate)

# 正确：直接用 emit
self._webrtcbin.emit("add-ice-candidate", mline_index, candidate)
```

**ICE candidate handler 必须在 setLocalDescription 之前设置：**
```javascript
// 错误：部分候选会丢失
const offer = await pc.createOffer();
await pc.setLocalDescription(offer);
pc.onicecandidate = handler;  // ❌ 太晚了

// 正确：
pc.onicecandidate = handler;  // ✅ 先注册
const offer = await pc.createOffer();
await pc.setLocalDescription(offer);
```

---

### 6. 连接稳定性

**重连前必须关闭旧 PeerConnection：**
```javascript
// 错误：旧 PC 泄漏，RK3588 上 MPP 编码器会话被耗尽
function handleReconnect() {
    connectWS();  // 创建新 PC，旧的没人关
}

// 正确：
function cleanupPeerConnection() {
    if (pc) { pc.close(); pc = null; }
}
function handleReconnect() {
    cleanupPeerConnection();  // 先关旧的
    connectWS();
}
```

**重连时要检查 MediaStream 轨道是否还活着：**
```javascript
// 错误：用户可能已经通过浏览器 UI 停止了共享
if (localStream) { connectWS(); }

// 正确：
if (localStream && localStream.getTracks().some(t => t.readyState === 'live')) {
    connectWS();
}
```

**连接失败时必须清理 MediaStream：**
```javascript
} catch (e) {
    // 缺这个会导致屏幕录制指示器永远不消失
    if (localStream) {
        localStream.getTracks().forEach(t => t.stop());
        localStream = null;
    }
}
```

### 7. 服务端会话管理

**WS 断连不能清理所有 session：**
```python
# 错误：任何一个客户端断开，所有投屏都被杀掉
async def handle_ws_disconnect(ws, client_id):
    for s in receiver_manager.get_status_list():
        await receiver_manager.remove_session(s["session_id"])

# 正确：用映射表跟踪每个客户端的 session
ws_sessions = {}  # client_id → set of session_ids

def handle_ws_disconnect(ws, client_id):
    for sid in ws_sessions.pop(client_id, set()):
        asyncio.ensure_future(receiver_manager.remove_session(sid))
```

**SDP 处理失败必须清理已创建的 session：**
```python
receiver = await receiver_manager.create_session()
try:
    answer = await loop.run_in_executor(None, receiver.set_offer, sdp_offer)
    if not answer:
        await receiver_manager.remove_session(receiver.session_id)  # 必须！
        return web.json_response({"error": "..."}, status=500)
except Exception:
    await receiver_manager.remove_session(receiver.session_id)  # 必须！
    raise
```

### 8. asyncio 注意事项

**不能在 async 函数里用 time.sleep()：**
```python
# 错误：冻结整个服务器，所有请求都卡住
async def api_handler():
    time.sleep(2.0)  # ❌

# 正确：
async def api_handler():
    await asyncio.sleep(2.0)  # ✅
```

**get_event_loop() 已废弃：**
```python
# Python 3.10+
loop = asyncio.get_running_loop()  # ✅
# 不是
loop = asyncio.get_event_loop()    # ❌ DeprecatedWarning
```

---

## 测试方法

### 本地功能测试
```bash
# 启动服务器
cd backend
python server.py

# 运行测试（另一个终端）
python test/local_test_simple.py
```

**测试覆盖：**
- HTTP API: `/health`, `/info`, `/api/status`, `/api/discover`
- WebSocket: 主信令端点 + 终端端点
- 静态文件: 所有前端页面

**预期结果：** 10/10 tests passing

---

## RK3588 移植要点

### 依赖安装
```bash
# 硬件编解码器
apt-get install gstreamer1.0-rockchip1

# DRM/KMS 显示
apt-get install libdrm-dev

# mDNS
pip3 install zeroconf
```

### GStreamer 管线差异
```bash
# Windows (软件解码)
... ! vp8dec ! ...

# RK3588 (硬件解码)
... ! rkmppdec ! ...
```

### 显示输出
```bash
# Windows (测试用)
... ! autovideosink

# RK3588 (HDMI 输出)
... ! rkmppdec ! kmssink
```

---

## 当前文件结构

```
video_test/
├── backend/
│   ├── server.py              # 主服务器（推荐）
│   ├── signaling_server.py    # 独立信令服务器
│   ├── config.py              # 配置文件
│   └── mdns_service.py        # mDNS 服务
├── gst/
│   ├── receiver.py            # WebRTC 接收器
│   ├── compositor.py          # 视频合成
│   └── audio_mixer.py         # 音频混音
├── frontend/
│   ├── sender.html            # 投屏发送端
│   ├── view.html              # 观看端
│   ├── dashboard.html         # 控制面板
│   └── error-handler.js       # 统一错误处理
├── test/
│   └── local_test_simple.py   # 本地功能测试
└── skills/
    └── webrtc-screen-sharing.md  # 本文件
```

---

## 更新日志

### 2026-04-27 (2) - 全面缺陷修复
**状态**: 10/10 测试通过

**receiver.py (3 fixes)**
- `stop()` 添加 `glib_thread.join(timeout=5)` 等待线程结束，防止 MPP 硬件解码器残留状态导致 segfault
- `promise.interrupt()` → `promise.wait()`，SDP 协商才能正确完成
- `add_ice_candidate()` 移除不兼容的 `WebRTCICECandidate.init`，改用直接 emit `(mline_index, candidate)`

**server.py (6 fixes)**
- WHEP 创建失败时自动 `remove_session()`，防止 session 泄漏耗尽 `max_sessions`
- `handle_ws_disconnect` 新增 `ws_sessions` 映射，只清理该客户端的 session（之前会杀掉所有客户端）
- 所有 `request.json()` 加 try/catch 返回 400
- `asyncio.get_event_loop()` → `asyncio.get_running_loop()`（3.10+ 兼容）
- `get_local_ip()` 加 finally 确保 socket 关闭
- Banner 中 WebSocket URL 从 `ws://ip:8081` 改为 `ws://ip:http_port/ws`

**sender.html (6 fixes)**
- 删除重复代码块（原 437-448 行和 627-635 行导致语法错误，页面无法加载）
- 重连前 `cleanupPeerConnection()` 关闭旧 PC，防止 MPP 编码器会话耗尽
- 连接失败 catch 中 `localStream.getTracks().forEach(t => t.stop())`
- ICE candidate handler 从 `setLocalDescription` 之后移到之前（WHEP 模式）
- `stopCast()` 发送 WHEP `DELETE` 清理服务端会话
- `getWsUrl()` 从硬编码 `:8081` 改为与 HTTP 共用端口

**mdns_service.py (2 fixes)**
- `discover()` 改为 `async` + `asyncio.sleep()`，不再阻塞整个服务器
- `DiscoveryListener.add_service()` 补充了实际的 `get_service_info` 调用

**view.html (4 fixes)**
- 加了 WebSocket 自动重连（最多 3 次，指数退避）
- `event.streams[0]` 空数组时回退到 `new MediaStream([event.track])`
- ICE candidate 发送前检查 `ws.readyState === WebSocket.OPEN`
- `handleOffer/handleIce` 加 try/catch

**audio_mixer.py (1 fix)**
- `pulsesink` 改为自适应 `autoaudiosink → pulsesink → alsasink`

**compositor.py (2 fixes)**
- `from .display import DisplayManager` 加 try/except 保护，避免模块导入失败导致整个服务无法启动
- 所有 `self._display` 调用加了 `if self._display` 存在性检查

---

### 2026-04-27 (1) - 初始测试通过
- ✅ Windows 本地环境 10/10 测试通过
- ✅ 静态文件路由修复（lambda → async handler）
- ✅ WebSocket 连接测试通过
- ✅ HTTP API 完整验证

### 下一步
- [ ] RK3588 硬件移植
- [ ] 硬件加速解码测试
- [ ] DRM/KMS 显示输出
- [ ] 端到端投屏功能测试
- [ ] 长时间稳定性测试

---

## 使用此 Skill

**导入新环境：**
1. 将 `skills/` 目录复制到新项目
2. 在对话中引用：`/webrtc-screen-sharing`

**更新进展：**
- 直接编辑本文件
- 记录遇到的问题和解决方案
- 更新"下一步"清单

**保持同步：**
- 每次重大修改后更新"更新日志"
- 记录环境差异（Windows vs Linux）
- 保存配置变更
