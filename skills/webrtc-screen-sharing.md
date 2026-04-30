---
name: webrtc-screen-sharing
description: P2P 无线投屏系统 - 已在 RK3588 上验证通过的生产版本
---

# P2P 无线投屏系统

## 项目概述

基于 WebRTC 的 P2P 无线投屏系统，Chrome 浏览器捕获屏幕，通过信令服务器中继 SDP/ICE，RK3588 使用 GStreamer webrtcbin 解码后通过 kmssink 直接输出到 HDMI。

**技术栈：**
- 前端：原生 JavaScript + WebRTC API (p2p-sender.html)
- 后端：Python + aiohttp (server.py) 信令中继 + HDMI 自动启停
- 接收：GStreamer 1.16.3 + webrtcbin + kmssink (hdmi_receiver.py)
- 发现：zeroconf mDNS (mdns_service.py)

**当前状态：** ✅ 已在 Orange Pi 5 Pro (RK3588) 上验证通过，HDMI 投屏正常工作

---

## 系统架构

```
Chrome (sender)                    RK3588 接收端
┌──────────────────┐               ┌─────────────────────────────────┐
│ p2p-sender.html  │               │  server.py (aiohttp)           │
│                  │──HTTPS:8080──▶│  ├─ /ws (信令中继)             │
│ RTCPeerConnection │               │  ├─ /api/discover (mDNS发现)    │
│ STUN: google:19302│               │  ├─ /api/sessions (WHEP)       │
│                  │               │  │                              │
│ getDisplayMedia() │               │  │  hdmi_receiver.py (子进程)     │
│ → createOffer    │               │  ├─ ws://localhost:8081/ws      │
│ → send(sdp)      │               │  └─ GStreamer webrtcbin         │
│                  │               │     → depay → dec → videoconvert │
└──────────────────┘               │     → videoscale → capsfilter   │
                                   │     → kmssink(plane-id=71)     │
                                   └─────────────────────────────────┘
```

### 双端口

| 端口 | 协议 | 用途 |
|------|------|------|
| 8080 | HTTPS (cert.pem/key.pem) | 外部访问：前端页面、信令 WS、REST API |
| 8081 | HTTP (无 SSL) | 本地 HDMI 显示：hdmi_receiver.py 的 WS |

### 信令流程 (Room-based, short 格式)

```
1. sender: getDisplayMedia() → createOffer() → send({t:"offer", s:sid, sdp})
2. server: 首次 offer → 自动启动 hdmi_receiver.py 子进程
3. hdmi_receiver: WS 连 8081 → send({t:"reg", s:sid})
4. server: 转发 offer + 缓存 pending ICE → 新 viewer
5. hdmi_receiver: set-remote-description → create-answer → send answer
6. server: 转发 answer → sender
7. 双方交换 ICE candidates
8. P2P 连接建立 → 视频 → kmssink → HDMI 输出
```

### 消息格式 (short)

```json
{"t": "offer",  "s": "p2p_xxx", "sdp": "v=0\r\n..."}
{"t": "answer", "s": "p2p_xxx", "sdp": "v=0\r\n..."}
{"t": "ice",    "s": "p2p_xxx", "c": "candidate...", "m": "0", "l": 0}
{"t": "reg",    "s": "p2p_xxx"}
{"t": "stop",   "s": "p2p_xxx"}
```

---

## 关键文件

| 文件 | 职责 | 修改频率 |
|------|------|---------|
| `frontend/p2p-sender.html` | Chrome 端屏幕捕获 + WebRTC sender | 低 (核心逻辑已稳定) |
| `backend/server.py` | 信令中继、HDMI 启停、mDNS、API | 中 (可加功能) |
| `backend/hdmi_receiver.py` | GStreamer webrtcbin → kmssink HDMI 输出 | 低 (已验证) |
| `backend/mdns_service.py` | mDNS 广播/发现 (zeroconf) | 低 (已稳定) |
| `backend/config.py` | 端口、分辨率、codec 等配置 | 低 |
| `backend/gst/` | GStreamer 硬件抽象层 | 低 |

---

## ⚠️ 前端 WebRTC 绝对约束

> 以下规则来自反复踩坑验证。违反任何一条都会导致投屏完全不可用。

### 1. STUN server 必须保留

```javascript
// ✅ 必须
pc = new RTCPeerConnection({ iceServers: [{ urls: 'stun:stun.l.google.com:19302' }] });

// ❌ 绝对不行 - Chrome 只发 .local candidate
pc = new RTCPeerConnection({ iceServers: [] });
```

**原因**: STUN 即使被墙不可达，有配置时 Chrome 仍发 host candidate。去掉后只发 mDNS `.local`，RK3588 的 libnice 无法解析。

### 2. createOffer 必须 setLocalDescription 后立即发送

```javascript
// ✅ 必须
await pc.setLocalDescription(offer);
send({ t:'offer', s: sessionId, sdp: offer.sdp });

// ❌ 绝对不行 - STUN 不可达时永远不完成
await pc.setLocalDescription(offer);
await new Promise(resolve => { pc.onicecandidate = e => { if (!e.candidate) resolve(); }; });
```

### 3. 所有 ICE candidate 必须原样转发

```javascript
// ✅ 必须 - 包括 .local 的
pc.onicecandidate = (e) => {
  if (!e.candidate) return;
  send({ t:'ice', s: sessionId, c: e.candidate.candidate, m: e.candidate.sdpMid, l: e.candidate.sdpMLineIndex });
};

// ❌ 绝对不行 - 过滤后可能无可用 candidate
if (e.candidate.candidate.includes('.local')) return;
```

### 4. start() 必须自己调 connectWS()

```javascript
// ✅ start() 内部连 WS
async function start() {
  stream = await getDisplayMedia(...);
  if (!ws || ws.readyState === WebSocket.CLOSED) {
    await connectWS();
    setupWSHandler();
  }
  setupPC();
  await createOffer();
}
```

### 5. setupPC() 中 onicecandidate 在 setLocalDescription 之前注册

```javascript
function setupPC() {
  pc = new RTCPeerConnection({ iceServers: [...] });
  pc.onicecandidate = (e) => { ... };  // ✅ 先注册
  stream.getTracks().forEach(t => pc.addTrack(t, stream));
}

async function createOffer() {
  setupPC();
  const offer = await pc.createOffer();
  await pc.setLocalDescription(offer);  // 后设置
  send({ t:'offer', s: sessionId, sdp: offer.sdp });
}
```

---

## RK3588 HDMI 显示约束

| 约束 | 值 | 原因 |
|------|-----|------|
| 显示分辨率 | 1024×600 | 外接 HDMI 显示器实际分辨率 |
| DRM plane | plane-id=71 | plane 57 (primary) 被 fbcon 占用 (refcount=2) |
| capsfilter | 必须 width=1024,height=600 | kmssink 接受任意尺寸，不强制则 videoscale 不缩放 |
| videoconvert | 必须 | 解码输出 (I420/NV12) → kmssink 可接受 (BGRx) |
| Pipeline | 必须单 pipeline | webrtcbin 和 kmssink 必须在同一个 pipeline 中 |
| preexec_fn | os.setpgrp | 子进程独立进程组，kill 不影响主进程 |

### GStreamer Pipeline

```
webrtcbin (bundle-policy=max-bundle)
  → rtph264depay → avdec_h264    (或 VP8/VP9/H265)
  → videoconvert
  → videoscale (add-borders=false)
  → capsfilter (video/x-raw, width=1024, height=600)
  → kmssink (plane-id=71)
```

---

## GStreamer 1.16 API 差异 (RK3588 Ubuntu 20.04)

| 操作 | GStreamer 1.16 | 备注 |
|------|-------------|------|
| 获取 SDP 文本 | `answer.sdp` (属性) | 不是方法 `answer.sdp()` |
| 等待 Promise | `promise.wait()` | `interrupt()` 不等完成 |
| ICE candidate | `emit("add-ice-candidate", mline_idx, candidate)` | 无 `WebRTCICECandidate.init` |
| 绑定信号 | 位置参数 `element.connect("signal", callback)` | 无 kwargs |

---

## 后端关键约束

### zeroconf 必须在独立线程

`mdns_service.py` 中所有 zeroconf 操作必须通过 `ThreadPoolExecutor` 在独立线程执行。

**原因**: zeroconf 0.136.2 内部用 asyncio，在 `asyncio.run()` 事件循环中直接调用触发 `EventLoopBlocked`。

### HDMI 自动启停

- `server.py` 全局 `_display_process` + `_display_room_id`
- sender 首发 offer (`is_new=True`) → `_auto_start_display(sid)` → subprocess 启动 hdmi_receiver.py
- sender stop/断连 → `_stop_display()` → `os.killpg(pid, SIGTERM)`
- 新 session → 先 stop 旧的再 start 新的
- 日志输出到 `/tmp/hdmi_receiver.log` (每次覆盖)

### ICE candidate 缓冲 (hdmi_receiver.py)

ICE candidates 可能在 `set-remote-description` 完成前到达，需要缓存到 `_ice_queue`，answer 创建后 `_flush_ice_queue()`。

### mDNS properties 的 bytes 问题

zeroconf 返回的 properties key/value 是 bytes，转 JSON 前必须 decode:
```python
props[k.decode() if isinstance(k, bytes) else k] = v.decode() if isinstance(v, bytes) else v
```

---

## 部署

```bash
# 前端
scp frontend/p2p-sender.html orangepi@192.168.1.109:/tmp/
ssh orangepi@192.168.1.109 "sudo cp /tmp/p2p-sender.html /opt/screencast/frontend/"

# 后端
scp backend/hdmi_receiver.py backend/server.py backend/mdns_service.py orangepi@192.168.1.109:/tmp/
ssh orangepi@192.168.1.109 "sudo cp /tmp/*.py /opt/screencast/backend/"

# 重启服务
ssh orangepi@192.168.1.109 "sudo systemctl restart screencast"

# 查看日志
ssh orangepi@192.168.1.109 "sudo journalctl -u screencast -f"
ssh orangepi@192.168.1.109 "cat /tmp/hdmi_receiver.log"
```

**SSH**: `orangepi@192.168.1.109`, 密码: `orangepi`

**Windows bash SSH 陷阱**: 直接 `ssh user@host "sudo cmd"` 可能 exit code 255。用 heredoc 绕过:
```bash
<< 'SCRIPT' | ssh user@host "bash -s"
sudo systemctl restart screencast
SCRIPT
```

---

## 修改安全准则

1. **前端只改 UI**: `setupPC()`、`createOffer()`、`onicecandidate`、`connectWS()`、`start()` 的逻辑不能动
2. **后端只加不改**: `handle_ws_message()` 信令流程和 `_auto_start_display`/`_stop_display` 逻辑不能改
3. **改完必须实测**: 涉及 WebRTC/信令的修改，部署后浏览器实测
4. **出问题先 revert**: 不要在坏状态上反复修补，`git checkout` 回退到上一个 commit

---

## 更新日志

### 2026-04-30 - RK3588 HDMI 投屏验证通过

**hdmi_receiver.py**
- 单 pipeline 方案验证: webrtcbin → depay → dec → videoconvert → videoscale → capsfilter → kmssink
- overlay plane 71 成功绑定，fbcon 占用 primary plane 57 无法替换
- capsfilter 强制 1024x600 解决 videoscale 不缩放问题
- videoconvert 解决 I420 → BGRx 格式不兼容
- ICE candidate 缓冲解决早期到达问题

**server.py**
- `_auto_start_display()` sender 首发 offer 自动拉起 hdmi_receiver.py
- `_stop_display()` sender stop/断开自动停止
- `/api/discover` mDNS 设备发现
- properties bytes → str 转换

**mdns_service.py**
- zeroconf 操作移到独立线程 (ThreadPoolExecutor) 解决 EventLoopBlocked
- 详细日志记录广播/发现全过程
- 自查验证: register 后立刻 get_service_info 确认广播成功

**p2p-sender.html**
- 设备发现 UI: 扫描按钮 + 设备列表 + 点击自动投屏
- `switchDevice()` + `start()` 一键切换设备并开始投屏
- `wsBase` 从 const 改为 let 支持动态切换目标设备

**踩坑教训**
- 去掉 STUN server → Chrome 只发 .local candidate → 投屏彻底失败
- 等 ICE gathering 完成 → STUN 不可达时永远不触发 → 页面卡死
- 过滤 .local candidate → 无可用 candidate → 连接不建立
- 解耦 connectWS 和 start → WS 状态不一致 → 多设备切换失败

### 2026-04-27 - 本地开发验证

- Windows 本地 10/10 测试通过
- 静态文件路由、WebSocket、HTTP API 全部验证
- receiver.py Promise/GStreamer 修复
- server.py session 泄漏修复
- asyncio 兼容性修复

### 2026-04-29 - RK3588 移植

- GStreamer 1.16.3 适配完成
- MPP 硬解、RGA 硬缩放验证
- mDNS 服务广播/发现实现
- Room-based 信令实现
