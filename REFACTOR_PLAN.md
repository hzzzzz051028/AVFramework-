# 基于 WebRTC 与 RK3588 的无线投屏系统重构方案

## 1. 项目定位

### 1.1 毕设题目建议

**基于 WebRTC 与 RK3588 的低延迟无线投屏系统设计与实现**

### 1.2 建设目标

完成一个可在局域网内稳定运行的无线投屏系统。PC 端通过浏览器采集屏幕，使用 WebRTC 将音视频发送至 RK3588，RK3588 通过 GStreamer 和硬件解码完成 HDMI 输出，同时提供设备发现、连接管理、状态监控和异常恢复能力。

### 1.3 核心成果

1. 可稳定演示的端到端投屏系统。
2. 清晰、可维护的前后端和媒体处理架构。
3. RK3588 硬件解码与 DRM/KMS 原生显示能力。
4. 可复现的延迟、帧率、资源占用和弱网性能实验。
5. 与实现一致的设计文档、测试报告和论文材料。

## 2. 重构原则

1. **先单路闭环，再扩展功能**：单发送端到单接收端必须优先稳定。
2. **只保留一条正式主链路**：统一发送页面、信令协议和接收实现。
3. **控制面和媒体面分离**：Python 管理信令和设备状态，媒体通过 WebRTC P2P 传输。
4. **硬件能力可配置、可回退**：优先使用 RK3588 MPP、RGA、DRM/KMS，不可用时回退到软件实现。
5. **设计必须可测试**：每个核心模块需要状态、日志和自动化验证入口。
6. **功能描述必须与实际实现一致**：未完成能力不能出现在正式功能清单中。

## 3. 项目范围

### 3.1 必须完成

- 浏览器屏幕采集与本地预览。
- WebSocket 信令与 WebRTC SDP/ICE 协商。
- 单路视频投屏。
- RK3588 H.264 硬件解码，软件解码回退。
- DRM/KMS HDMI 原生输出。
- mDNS 设备广播与发现。
- 开始、停止、断线清理和自动重连。
- 运行状态、连接状态和硬件能力监控。
- HTTPS 或安全的本地发送端方案。
- 单元测试、信令集成测试和端到端测试流程。
- 性能数据采集与实验报告。

### 3.2 建议完成

- 系统音频传输和 HDMI/音频设备输出。
- 发送端码率、分辨率和帧率配置。
- PIN 码或一次性配对机制。
- 日志下载和故障诊断页面。

### 3.3 扩展功能

- 多发送端、多画面合成。
- 画面录制和截图。
- 跨网段或公网 TURN 中继。
- 远程控制。

扩展功能不影响核心系统验收，时间不足时不进入正式主线。

## 4. 目标架构

```text
┌──────────────────────── PC 浏览器 ────────────────────────┐
│  Sender UI                                                │
│  getDisplayMedia → MediaStream → RTCPeerConnection        │
└──────────────┬───────────────────────────────┬─────────────┘
               │ WebSocket 信令                │ WebRTC 媒体
               ▼                               ▼
┌──────────────────────── RK3588 ───────────────────────────┐
│  aiohttp 控制服务                 GStreamer Receiver       │
│  ├─ 静态页面/API                  ├─ webrtcbin              │
│  ├─ Room/Session 状态机           ├─ RTP depay              │
│  ├─ mDNS                          ├─ MPP/软件解码            │
│  ├─ Metrics                       ├─ RGA/视频缩放            │
│  └─ Receiver 生命周期管理         └─ DRM/KMS → HDMI          │
└────────────────────────────────────────────────────────────┘
```

### 4.1 控制面

由 aiohttp 服务负责：

- HTTP/HTTPS 页面和 REST API。
- WebSocket 信令。
- 会话状态机。
- 接收器进程或媒体实例的生命周期。
- mDNS、设备信息和监控数据。

### 4.2 媒体面

视频不经过 Python 转发：

```text
Browser RTCPeerConnection → GStreamer webrtcbin → decoder → kmssink
```

Python 只负责创建、配置和销毁媒体管线。

## 5. 目标目录结构

```text
backend/
├── app.py                       # 应用入口和生命周期
├── config.py                    # 配置加载与校验
├── api/
│   ├── health.py                # 健康检查
│   ├── display.py               # 显示控制
│   ├── discovery.py             # 设备发现
│   └── system.py                # 系统指标
├── signaling/
│   ├── protocol.py              # 信令消息定义和校验
│   ├── session.py               # 会话状态机
│   └── websocket.py             # WebSocket 处理
├── media/
│   ├── receiver.py              # 接收器接口与生命周期
│   ├── pipeline.py              # GStreamer 管线构建
│   ├── hardware.py              # MPP/RGA/DRM 探测
│   └── display.py               # HDMI/KMS 输出
└── services/
    ├── mdns.py
    ├── metrics.py
    └── process_manager.py

frontend/
├── sender/                      # 唯一正式发送端
├── dashboard/                   # 设备管理页面
└── shared/                      # 信令客户端、错误处理和样式

config/
└── receiver.example.json

tests/
├── unit/
├── integration/
└── e2e/
```

## 6. 统一信令协议

废除当前 short/long 双格式，统一使用可读字段。

### 6.1 消息封装

```json
{
  "version": 1,
  "type": "offer",
  "session_id": "abc123",
  "payload": {}
}
```

### 6.2 核心消息

| 消息 | 方向 | 用途 |
|---|---|---|
| `sender.register` | 发送端 → 服务 | 创建投屏会话 |
| `receiver.register` | 接收端 → 服务 | 加入会话 |
| `offer` | 发送端 → 接收端 | SDP Offer |
| `answer` | 接收端 → 发送端 | SDP Answer |
| `ice` | 双向 | ICE Candidate |
| `session.stop` | 双向 | 主动停止 |
| `session.state` | 服务 → 客户端 | 状态变化 |
| `error` | 服务 → 客户端 | 标准错误响应 |
| `ping/pong` | 双向 | 心跳检测 |

### 6.3 会话状态机

```text
IDLE → REGISTERED → NEGOTIATING → CONNECTED
                           │           │
                           └→ FAILED ←─┘
                                │
                              CLOSED
```

每个状态变化必须记录时间、原因和会话 ID。

## 7. 媒体管线方案

### 7.1 视频主链路

```text
webrtcbin
  → RTP depay
  → parse
  → rkmpp decoder / software decoder
  → videoconvert or RGA
  → capsfilter
  → kmssink
```

### 7.2 编解码策略

首期只保证 H.264：

1. 浏览器优先选择 H.264。
2. RK3588 优先使用 MPP H.264 解码器。
3. MPP 不可用时回退到 `avdec_h264`。
4. VP8、VP9、H.265 放到兼容性扩展阶段。

### 7.3 显示策略

- 自动探测 DRM connector、plane 和当前显示模式。
- 分辨率、旋转和 sink 从配置读取。
- 生产环境使用 `kmssink`。
- 开发环境使用 `autovideosink` 或 `fakesink`。
- 禁止在正式代码中写死 `1024×600` 和 Plane ID。

### 7.4 音频策略

音频作为第二阶段独立接入：

```text
webrtcbin → rtpopusdepay → opusdec → audioconvert → audio sink
```

先保证视频稳定，再处理音视频同步和输出设备选择。

## 8. 配置和部署

### 8.1 配置项

```json
{
  "server": {
    "host": "0.0.0.0",
    "port": 8080,
    "https": true
  },
  "webrtc": {
    "codec": "H264",
    "max_sessions": 1,
    "ice_servers": []
  },
  "display": {
    "sink": "auto",
    "connector": "auto",
    "plane_id": "auto",
    "width": "auto",
    "height": "auto"
  },
  "media": {
    "hardware_decode": true,
    "software_fallback": true
  }
}
```

### 8.2 部署要求

- 删除仓库中的固定 IP、用户名和密码。
- 使用环境变量或部署配置传入设备地址。
- 提供 systemd 服务文件。
- 提供依赖检测命令和安装脚本。
- 服务异常退出后自动重启。
- 日志统一写入 journald，可选输出结构化日志。

## 9. 测试方案

### 9.1 单元测试

- 配置加载、覆盖和非法配置检查。
- 信令消息解析与校验。
- 会话状态转换。
- 房间创建、加入、退出和超时清理。
- codec、decoder 和 sink 选择。

### 9.2 集成测试

- aiohttp API 和 WebSocket 服务。
- 模拟 sender/receiver 完成 Offer、Answer、ICE 交换。
- 客户端异常断开后的资源清理。
- 重复 session ID 和会话上限处理。
- 接收器进程启动、退出和超时处理。

### 9.3 端到端测试

- PC 浏览器到 RK3588 HDMI 实际投屏。
- 开始、停止、重复投屏 20 次。
- 持续投屏 1 小时和 8 小时。
- 网线断开、Wi-Fi 抖动和发送端刷新页面。
- 720p、1080p，不同帧率和码率。
- 软件解码和硬件解码对比。

### 9.4 验收指标

| 指标 | 首期目标 |
|---|---|
| 单次连接成功率 | ≥ 95% |
| 连续 20 次连接成功率 | ≥ 90% |
| 1080p 局域网端到端延迟 | 目标 ≤ 250 ms |
| 连续运行时间 | ≥ 8 小时无崩溃 |
| 断线资源回收 | ≤ 5 秒 |
| 硬解 CPU 占用 | 明显低于软件解码，记录实测数据 |

最终论文使用实测结果，不预先承诺无法验证的数据。

## 10. 实施阶段

### 阶段一：建立可复现基线

目标：明确现在真正可运行的链路。

- 固定一个发送页面和一个接收实现。
- 记录当前设备环境、依赖版本和启动步骤。
- 修复阻塞端到端投屏的协议问题。
- 保存基线延迟、CPU、内存和日志。

验收：从全新环境按文档部署后，可完成一次稳定投屏。

### 阶段二：信令与服务重构

目标：统一协议，拆分服务职责。

- 定义统一信令协议。
- 实现会话状态机。
- 拆分 API、WebSocket、会话和进程管理。
- 清理旧服务器和重复页面。
- 补充单元测试和信令集成测试。

验收：信令自动化测试通过，断开连接后无残留会话和接收进程。

### 阶段三：媒体层重构

目标：形成可配置的 RK3588 媒体管线。

- 重构 GStreamer 管线构建器。
- 接入 MPP 硬件解码。
- 自动探测 DRM/KMS 显示参数。
- 增加软件回退和错误上报。
- 统一接收器生命周期。

验收：相同发送端可在硬解和软解模式下投屏，状态页面能显示实际使用的管线。

### 阶段四：可靠性和体验

目标：满足稳定演示要求。

- 解决 HTTPS/安全上下文。
- 完成 mDNS 发现和自动连接。
- 实现超时、重连和错误提示。
- 加入配对或最小访问控制。
- 完善管理面板和日志。

验收：换一台发送电脑后，无需修改代码即可发现设备并投屏。

### 阶段五：实验与论文材料

目标：形成可量化、可复现的毕设成果。

- 执行延迟和资源占用实验。
- 对比硬解与软解。
- 测试分辨率、帧率、码率和弱网影响。
- 整理架构图、时序图、状态机和测试结果。
- 保证论文描述与最终代码一致。

验收：实验脚本、原始数据、图表和结论可以重复生成。

## 11. 代码迁移策略

### 11.1 保留并改造

- `backend/server.py`：提取路由、信令和生命周期逻辑。
- `backend/hdmi_receiver.py`：提取为正式媒体接收模块。
- `backend/gst/hardware.py`：继续作为硬件能力探测基础。
- `backend/mdns_service.py`：整理为独立服务。
- `frontend/p2p-sender.html`：作为正式发送端原型。
- `frontend/dashboard.html`：作为管理面板原型。

### 11.2 暂时归档

- `backend/simple_server.py`
- `backend/signaling_server.py`
- `frontend/screenshare.html`
- `frontend/view.html`
- `frontend/display.html`
- 终端模拟相关页面和工具

归档阶段先移动到 `legacy/`，确认新主线稳定后再删除，避免丢失可参考实现。

### 11.3 暂缓集成

- 当前 WHEP 实现。
- 多画面 compositor。
- 终端转发。

这些功能不得阻塞单路投屏主链路。

## 12. 风险与应对

| 风险 | 影响 | 应对方案 |
|---|---|---|
| 浏览器不允许 HTTP 屏幕捕获 | 无法开始投屏 | HTTPS 或 localhost 发送端 |
| 浏览器未协商 H.264 | RK3588 接收失败 | SDP codec preference 和能力检查 |
| MPP 插件名称随系统镜像变化 | 硬解不可用 | 启动检测、映射表和软件回退 |
| DRM plane/connector 不固定 | HDMI 黑屏 | 自动探测并允许配置覆盖 |
| ICE mDNS candidate 无法解析 | WebRTC 连接失败 | 正确处理 mDNS candidate，并保留局域网 host candidate |
| 子进程退出后状态不同步 | 重连失败或资源泄漏 | 统一 ReceiverManager 监督进程 |
| 功能范围过大 | 延误毕设 | 单路视频为硬性主线，其他均为扩展 |

## 13. 完成标准

满足以下条件后，项目可进入毕设答辩版本：

1. 仓库只有一套正式发送端、信令协议和接收链路。
2. 新环境可依据文档完成部署。
3. 任意同局域网电脑可发现 RK3588 并发起投屏。
4. 1080p 视频可稳定输出到 HDMI。
5. 硬件解码可被日志和监控数据证明。
6. 停止、断网和页面关闭后资源能够自动回收。
7. 自动化测试覆盖核心信令和生命周期。
8. 完成至少一组可复现的性能对比实验。
9. 文档、演示功能和代码实现保持一致。

## 14. 产品化架构方向：单设备无线投屏网关

项目最终形态调整为单设备网关，而非多接收端组网系统：

```text
电脑/发送端 ──加入 RK3588 Wi-Fi──> RK3588 AP + DHCP/DNS
                                      │
                                      ├─ 控制面：HTTP(S) / WebSocket
                                      ├─ 媒体面：WebRTC + GStreamer
                                      └─ 输出面：DRM/KMS → HDMI
```

### 14.1 网络层

- RK3588 默认工作在 AP 模式，提供独立局域网和 DHCP。
- 使用固定网关地址（建议独立网段，如 `192.168.50.1`），避免与家庭路由器地址冲突。
- 以太网作为可选上行和 SSH 调试链路，不影响 AP 内投屏。
- 首屏显示 SSID、密码和访问二维码；mDNS 只做便利发现，不作为核心依赖。

### 14.2 连接层

- 首期仅允许一个活跃发送端，第二个发送端得到“设备占用”提示。
- 控制服务负责配对、会话状态、心跳、停止和异常回收。
- 投屏媒体仍采用浏览器 WebRTC 到 RK3588 的单向链路。

### 14.3 发送端形态

- 开发阶段：localhost 发送页 + `ws://RK3588:8081/ws`。
- 产品阶段优先：Tauri/Electron/原生发送小工具，绕开浏览器安全上下文和证书障碍。
- 若坚持纯浏览器，则必须提供可信 HTTPS（本地 CA/域名证书），不能依赖自签名 IP 证书。

### 14.4 分阶段实现

1. AP 模式和固定网关地址；电脑可连接并访问设备页。
2. 单设备单会话控制，去除多设备发现作为主流程。
3. 本地发送端完成真实屏幕采集和 WebRTC 投屏。
4. 状态页、二维码配网、占用提示、断线回收。
5. 最后再加入音频、抢占策略、性能指标和多客户端扩展。
