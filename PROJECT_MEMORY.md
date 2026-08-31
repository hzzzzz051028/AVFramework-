# 项目开发记忆

> 本文档是本项目的长期开发记忆。开始新一轮开发、恢复任务或上下文被压缩后，应优先阅读本文档，再查看相关代码和 `REFACTOR_PLAN.md`。
>
> 每次发生实际代码、配置、部署、测试或架构决策变更时，都必须同步更新“变更记录”和相关章节。

## 1. 项目目标

毕设建议题目：

**基于 WebRTC 与 RK3588 的低延迟无线投屏系统设计与实现**

目标是在局域网中实现：浏览器采集 PC 屏幕，通过 WebRTC 发送至 RK3588，由 GStreamer 接收、解码并通过 DRM/KMS 输出至 HDMI，同时提供设备发现、连接管理、状态监控、异常恢复和性能测试能力。

详细重构方案见 [`REFACTOR_PLAN.md`](REFACTOR_PLAN.md)。

## 2. Git 基线

- 远程仓库：`https://github.com/hzzzzz051028/AVFramework-.git`
- 目标开发分支：`python-webrtc-screen-share`
- 已验证基线提交：`28b64ad`
- 基线提交说明：`feat: Add RK3588 monitoring dashboard with system metrics API`
- 不以 `main` 或 `mac` 作为当前毕设开发主线。

### 分支背景

- `mac`：早期浏览器到浏览器版本，Node.js WebSocket 信令，包含 ICE/TURN 和自动播放修复。
- `python-webrtc-screen-share`：在早期版本基础上改为 Python/aiohttp，并加入 RK3588 GStreamer、DRM/KMS HDMI 输出和 mDNS；仓库记录表明已在 Orange Pi 5 Pro 上验证出画面。

## 3. 已验证的核心链路

当前应保护的可运行基线为：

```text
Chrome / frontend/p2p-sender.html
  → getDisplayMedia()
  → WebSocket short-format 信令
  → backend/server.py 房间中继
  → 自动启动 backend/hdmi_receiver.py
  → GStreamer webrtcbin
  → RTP depay / decode / videoconvert / videoscale
  → kmssink
  → RK3588 HDMI 输出
```

媒体流通过 WebRTC 在浏览器和 RK3588 接收器之间传输；Python 主服务主要负责信令、会话和接收进程生命周期，不转发媒体数据。

### 核心文件

| 文件 | 当前职责 |
|---|---|
| `frontend/p2p-sender.html` | 已验证的浏览器投屏发送端 |
| `backend/server.py` | aiohttp、信令房间、API、HDMI 子进程管理 |
| `backend/hdmi_receiver.py` | GStreamer WebRTC 接收和 kmssink 输出 |
| `backend/mdns_service.py` | mDNS 广播和设备发现 |
| `backend/config.py` | 服务和媒体配置 |
| `frontend/dashboard.html` | 设备状态和控制面板 |

## 4. 当前关键约束

以下约束来源于仓库中的 RK3588 实机记录。在重新验证前，不应随意破坏。

### WebRTC

- 当前稳定链路使用 short-format 信令：`t`、`s`、`c`、`m`、`l`。
- 当前 `p2p-sender.html` 中的 STUN 配置不能在没有实测的情况下删除。
- Offer 在 `setLocalDescription()` 后发送。
- ICE Candidate 可能早于 Remote Description 到达，接收端必须缓存并延后添加。
- viewer 重连时 sender 需要创建新的 PeerConnection/Offer，避免黑屏。

### RK3588/GStreamer

- 已验证设备：Orange Pi 5 Pro（RK3588）。
- 仓库记录的 GStreamer 版本：1.16.3。
- 已验证显示分辨率：`1024×600`。
- 已验证 DRM overlay plane：`71`。
- primary plane `57` 在当时环境中被 fbcon 占用。
- 已验证管线需要 `videoconvert`、`videoscale` 和强制输出尺寸的 `capsfilter`。
- `webrtcbin` 与 `kmssink` 位于同一个 GStreamer Pipeline。
- 当前 HDMI 接收器主要完成视频链路，音频尚未形成同等可信的闭环。

### 服务

- 外部入口通常为 8080；本机 HDMI receiver 使用 8081 上的 `/ws`。
- sender 首次 Offer 会触发 HDMI receiver 子进程启动。
- sender 停止或断开会触发子进程回收。
- zeroconf 操作当前放在线程中，以避免阻塞 aiohttp 事件循环。

## 5. 已识别问题

1. 正式入口未统一：默认 `sender.html` 与已验证的 `p2p-sender.html` 并存。
2. short/long 两套信令格式并存，部分前后端消息不匹配。
3. `server.py` 职责过多，包含 API、信令、状态和进程管理。
4. `simple_server.py`、`signaling_server.py` 等历史实现尚未归档。
5. `hdmi_receiver.py` 写死 `1024×600` 和 Plane ID `71`。
6. 当前 HDMI 管线使用的软件解码器没有证明 MPP 硬解已经实际启用。
7. `CompositorManager` 的动态流接入仍为空实现，多画面尚未闭环。
8. `AudioManager` 与 HDMI 接收主链尚未完整集成。
9. 现有测试主要覆盖 HTTP、静态页面和 WebSocket ping，没有覆盖真实媒体链路。
10. 历史测试依赖 `requests`；现已通过 `requirements-dev.txt` 提供完整开发依赖，历史脚本仍未迁移为 pytest。
11. 部署/SSH 脚本存在固定 IP、用户名或密码，应在重构中移除。
12. 浏览器通过局域网 HTTP 地址使用 `getDisplayMedia()` 存在安全上下文风险，需要正式 HTTPS 方案。

## 6. 已确定的开发决策

1. 后续开发以 `python-webrtc-screen-share` 为唯一目标分支。
2. 以提交 `28b64ad` 所包含的 RK3588 实机链路作为稳定基线。
3. 采取渐进式重构，不从零重写，不先堆叠扩展功能。
4. 优先完成单发送端、单接收端、单路 H.264 视频闭环。
5. 音频作为建议功能，多画面、录制、远程控制作为扩展功能。
6. 最终只保留一套正式发送端、一套信令协议和一套 RK3588 接收链路。
7. 重构过程中必须提供软件解码回退，硬件解码需要用日志和实验数据证明。
8. 每个阶段都需要可运行验收，不能只依据页面或 API 可访问判断投屏成功。
9. 实际测量结果优先于文档中的历史描述。
10. 在变更稳定链路前先增加保护性测试或保留可快速回退的基线。

## 7. 推荐实施顺序

1. 在 RK3588 实机复现现有基线并记录环境。
2. 修复并统一正式入口，保留当前 short-format 协议直至基线测试建立。
3. 增加信令集成测试和接收进程生命周期测试。
4. 定义统一信令协议与状态机，并分阶段迁移发送端和接收端。
5. 拆分 `server.py` 的 API、信令、会话和进程管理职责。
6. 重构 GStreamer 管线，配置化显示参数并接入 MPP 硬解/软件回退。
7. 完成 HTTPS、mDNS、重连、错误提示和监控。
8. 执行性能、稳定性和弱网实验，整理毕设材料。

## 7.1 架构评审优先级（2026-08-30）

整体技术路线保留：浏览器 WebRTC Sender + aiohttp 控制面 + GStreamer/RK3588 媒体面。优先优化运行模型和模块边界，不更换核心技术栈。

### P0：先保证唯一可运行主链

1. 正式首页统一到已验证的 P2P Sender，避免 `sender.html` 长格式消息与服务端 short-format 房间协议不匹配。
2. WHEP、浏览器 viewer、终端转发等非主线能力先从正式路由或默认流程隔离，避免共用消息分发造成语义冲突。
3. 明确产品首期只支持单活跃 HDMI 会话；当前全局 `_display_process` 与“最大 4 会话”的配置和文档不一致。

### P1：建立清晰状态所有权

1. 引入 `SessionManager`，统一持有 WebSocket、Room、ICE 缓存、Receiver 和 Display 状态。
2. 引入 `ReceiverSupervisor`，统一处理子进程启动、就绪、失败、停止、超时和日志，不在 aiohttp handler 中直接管理 `Popen`。
3. 使用显式会话状态机替代分散的全局字典和布尔状态。
4. 给 pending ICE 增加上限、去重、会话 TTL 和断开清理，防止长期增长。

### P1：媒体层统一

1. 当前 `gst/receiver.py` 和 `hdmi_receiver.py` 是两套接收实现，应定义共同 Receiver 接口，首期只保留 HDMI 主实现。
2. 将 codec、decoder、输出尺寸、connector、plane 和 sink 选择放入统一 PipelineBuilder。
3. 自动探测 MPP/DRM，失败时使用软件解码或开发 sink，并把实际选择暴露到状态 API。
4. 多画面和音频在真正接入 Pipeline 前不作为已实现能力对外暴露。

### P2：运行与工程质量

1. 依赖通过 app context 注入，不在模块导入时创建全局 Manager。
2. 所有阻塞操作移出 asyncio 事件循环；子进程等待和 mDNS 同步调用不得阻塞 HTTP/WS。
3. 配置增加 schema 校验、深拷贝和错误日志，禁止静默吞掉非法配置。
4. 外部入口与本机 receiver 通道分离；本机通道只绑定 loopback，外部入口使用 HTTPS。
5. 增加设备配对、消息大小限制、输入校验和访问控制。

## 7.2 硬件解耦方案（2026-08-30）

硬件解耦边界确定为“aiohttp 控制服务 ↔ Receiver Backend”。前端、信令、会话状态机、API、设备发现和大部分测试不得直接依赖 RK3588、GStreamer、MPP 或 DRM。

### 统一 Receiver 接口

控制服务只依赖以下抽象行为：

```text
start(session_id, signaling_url, media_config)
stop(session_id)
status(session_id)
events()
```

至少提供三种实现：

1. `MockReceiver`：无 GStreamer、无硬件；模拟注册、Answer、连接、播放、失败和退出，用于信令/生命周期测试。
2. `DesktopGStreamerReceiver`：使用 GStreamer 软件解码和 `autovideosink`/`fakesink`，用于 Mac/Linux 桌面媒体联调。
3. `RK3588Receiver`：使用 MPP/RGA/DRM/KMS 和 `kmssink`，只在真实设备上运行。

### 统一 Worker 事件

Receiver 通过内部 IPC/loopback WebSocket 向控制服务报告：

```text
receiver.started
signaling.connected
webrtc.negotiating
webrtc.connected
pipeline.playing
pipeline.error
receiver.stopped
metrics.updated
```

控制服务只根据这些事件更新会话状态，不检查 GStreamer 对象或 DRM 状态。

### 平台适配边界

媒体 Worker 内部再分为：

- `HardwareProbe`：探测 decoder、RGA、DRM connector/plane。
- `PipelineBuilder`：根据能力和配置构建管线。
- `DecoderSelector`：MPP 优先、软件回退。
- `DisplaySinkFactory`：`kmssink`、`autovideosink`、`fakesink`。

不要为每个 GStreamer element 创建一层抽象；只在平台选择和完整管线构建处隔离差异。

### 开发模式

配置支持：

```text
receiver.backend = mock | desktop | rk3588
display.sink = fake | auto | kms
decoder.mode = software | auto | hardware
```

预期工作分布：约 70%–80% 的前端、信令、状态机、API、Supervisor 和测试可脱离硬件开发；约 20%–30% 的 codec、MPP、DRM/KMS、HDMI、性能和长稳测试必须在 RK3588 上完成。

### 三层验收

1. 无硬件：MockReceiver 完成会话状态和故障注入测试。
2. 桌面媒体：真实 WebRTC + GStreamer + `fakesink`/窗口输出完成协议和解码测试。
3. RK3588：真实 MPP/DRM/HDMI 完成最终功能和性能验收。

### 正式三段式开发节奏

后续开发固定分为三个部分，每部分完成验收后再进入下一部分：

#### 第一部分：无硬件控制层

- 统一正式前端入口和信令协议。
- 实现 SessionManager、状态机和 ReceiverSupervisor。
- 实现 MockReceiver。
- 拆分 API、信令和进程生命周期职责。
- 测试重点：单元测试、WebSocket 信令集成测试、状态转换、超时、重连、故障注入和资源回收。

完成标准：不连接 RK3588、不安装 GStreamer，也能完整演示会话从创建到播放/失败/停止的控制流程。

#### 第二部分：桌面真实媒体层

- 实现 DesktopGStreamerReceiver。
- 使用软件解码和 `autovideosink`/`fakesink`。
- 验证真实 Offer/Answer、ICE、H.264、动态 pad、视频接收和重复连接。
- 测试重点：桌面端媒体集成测试、无界面 `fakesink` 测试、重复连接和短时间稳定性测试。

完成标准：普通开发机可完成浏览器到 GStreamer 的真实视频传输，不依赖 RK3588。

#### 第三部分：RK3588 硬件层

- 将现有稳定 HDMI 链包装为 RK3588Receiver。
- 接入 MPP、RGA、DRM/KMS，并保留软件回退。
- 自动探测 connector、plane 和显示模式。
- 完成 HDMI、长稳、弱网和性能实验。
- 测试重点：硬件冒烟测试、端到端测试、20 次重连、1/8 小时稳定性、硬解/软解对比和性能数据采集。

完成标准：RK3588 可稳定输出 HDMI，硬件能力和性能结果可通过日志、监控和实验数据证明。

### 测试递进原则

```text
第一部分：大量快速测试，完全不依赖媒体和硬件
    ↓
第二部分：少量真实媒体集成测试，使用桌面软件环境
    ↓
第三部分：数量更少但覆盖关键风险的 RK3588 实机测试
```

上层测试不得依赖下层环境；硬件测试不重复验证已经由单元和信令集成测试覆盖的业务逻辑。

### 当前自动化测试基线

- 隔离环境：项目根目录 `.venv`（不提交 Git）。
- 开发依赖：`requirements-dev.txt`。
- 测试配置：`pytest.ini`，默认只收集新 `tests/`，不收集历史 `test/` 手动脚本。
- 运行命令：`.venv/bin/python -m pytest -q`。
- 2026-08-31 最新结果：Python 3.13.2，11项测试全部通过。
- 已覆盖：MockReceiver 生命周期/故障/重复会话、ReceiverSupervisor 单活跃会话切换、正式 `/ws` 驱动 MockReceiver 到 `PLAYING`/`STOPPED`、short-format Offer/Answer/双向 ICE、晚加入 ICE 重放、未知房间、sender 断开清理、sender 主动停止后的角色与房间清理、桌面 backend 缺少 GStreamer 时的失败闭环。
- 生产侧 Receiver 接口保持 Python 3.8 兼容写法，以适配可能使用 Ubuntu 20.04 的 RK3588 环境。
- 浏览器无权限测试入口：`/p2p-sender.html?testMedia=1`，使用Canvas `captureStream(30)`生成1280×720测试流。

## 8. 工期结论

在现有实机链路确实可复现的前提下：

- 最小演示版：约 3–4 周。
- 可答辩版本：约 7–9 周。
- 推荐完整版本：约 9–11 周。
- 音频、多画面等完整扩展版：约 14–18 周。

最大风险来自 RK3588 MPP 插件、DRM/KMS 占用、浏览器 codec 协商、HTTPS 屏幕捕获和 ICE Candidate 兼容性。

## 9. 变更记录规范

每次变更在本节顶部追加，格式如下：

```text
### YYYY-MM-DD — 简短标题

- 目标：本次修改解决什么问题。
- 修改：涉及哪些文件和核心行为。
- 验证：运行了哪些测试，结果如何。
- 决策：新增了哪些以后必须遵守的约束。
- 未完成：遗留问题和下一步。
```

## 10. 变更记录

### 2026-08-31 — 固化 RK3588 有线网卡地址

- 目标：让板端网络重启或开机后稳定使用固定 IP，支持持续远程部署和运维。
- 修改：通过 NetworkManager 修改连接 `enP4p65s0`：`ipv4.method=manual`、地址 `192.168.1.109/24`、网关 `192.168.1.1`、DNS `192.168.1.1,8.8.8.8`、`connection.autoconnect=yes`。
- 验证：连接重新激活成功；`ip addr`显示 `192.168.1.109/24`；默认路由为 `192.168.1.1`；SSH 可重新连接；`screencast.service` 为 active；HTTPS `/health` 返回 `status: ok`。
- 决策：板端固定地址绑定有线接口 `enP4p65s0`；无线 `wlan0` 不参与当前服务入口。
- 未完成：DNS 对外解析仍需结合现场路由器确认；之前 `repo.huaweicloud.com` 解析失败可能是网络出口或 DNS 服务限制。

### 2026-08-31 — 完成首次远程部署与服务运维验证

- 目标：通过统一远程入口将当前代码部署到 Orange Pi 5 Pro，并验证 systemd 服务可运行、健康接口可访问。
- 修改：执行 `scripts/remote_service.sh deploy`，上传当前 `backend/`、`frontend/`、`scripts/`；板端 `screencast.service` 已重启。运维脚本 `status` 改为优先检查 `https://127.0.0.1:8080/health`，失败再回退 HTTP。
- 验证：SSH 连接 `orangepi5pro` 成功；板端服务 `active (running)`，GStreamer 1.16.3、MPP、RGA、DRM/KMS 均被检测到；`https://192.168.1.109:8080/health` 返回 `status: ok`、`gst_available: true`、`sessions: 0`。
- 阻塞：首次 `install` 因板端 DNS 无法解析 `repo.huaweicloud.com` 中止，未执行系统升级/依赖安装；本次 deploy 复用了板端已有依赖和服务配置。
- 决策：板端服务入口是 HTTPS 8080；远程 status 必须同时兼容 HTTPS 和 HTTP，不能只用明文 curl。
- 未完成：修复板端 DNS 后再单独执行 `scripts/remote_service.sh install`；需要通过真实投屏验证 HDMI 输出和硬件解码。

### 2026-08-31 — 建立远程部署与运维入口

- 目标：将板端部署、启停、状态、日志和交互 shell 统一为可重复的远程服务操作流程。
- 修改：新增 `scripts/remote_service.sh` 和 `docs/REMOTE_OPERATIONS.md`；默认目标为 `orangepi@192.168.1.109`，支持 `RK_USER`、`RK_HOST`、`RK_DIR`、`SERVICE` 覆盖；部署通过 SSH 流式上传当前 backend/frontend/scripts，并保留板端配置。
- 验证：脚本语法通过；SSH 已到达 `192.168.1.109` 但当前执行环境未通过公钥/密码认证，因此尚未执行远程 install/deploy。
- 决策：远程脚本不写入密码，优先使用 SSH 公钥；首次新主机自动接受 host key，已有 host key 变更仍拒绝。
- 未完成：在本机配置可用 SSH 公钥后执行 `check`，再进行首次 `install` 和 `deploy`；部署前需确认板端当前服务状态。

### 2026-08-31 — 增加桌面媒体环境诊断入口

- 目标：将第二阶段DesktopGStreamerReceiver的环境前置条件变成可重复、可判定的检查，而不是依赖人工逐项执行命令。
- 修改：新增 `tools/check_desktop_media.py`；检查GStreamer CLI、PyGObject的 `Gst/GstWebRTC/GstSdp` 命名空间、WebRTC/libnice、H.264接收解码链、`fakesink`以及可选窗口sink；更新 `TESTING.md`。
- 验证：当前Darwin arm64/Python 3.13.2环境按预期返回 `NOT READY`（缺少 `gi`，诊断退出码1）；10项pytest、`compileall`和 `git diff --check`继续通过。
- 决策：`fakesink`和至少一个H.264软件/系统解码器是无界面桌面媒体测试的硬条件；窗口sink只用于人工观察，不作为自动化测试硬条件。
- 未完成：需要安装原生GStreamer及Python GI绑定后再次运行诊断；通过前不实现无法本机执行验证的DesktopGStreamerReceiver。

### 2026-08-31 — 建立桌面接收器失败闭环

- 目标：开始第二部分实现，同时避免在没有GStreamer的开发机上误报媒体播放成功。
- 修改：新增 `DesktopGStreamerReceiver` backend；启动时复用 GI/GStreamer 能力探测，缺依赖或 worker 尚未接入时进入 `FAILED` 并保留结构化原因；导出统一 backend 并补测试。
- 验证：当前环境可稳定得到 `gstreamer_unavailable`，不触发模块导入异常；完整测试结果见最新自动化基线。
- 决策：真实 webrtcbin worker 接入前，Desktop backend 不得进入 `SIGNALING`、`CONNECTED` 或 `PLAYING` 状态。
- 未完成：实现桌面 GStreamer worker（Offer/Answer、ICE、动态 pad、软件解码和 fakesink）。

### 2026-08-31 — 安装并验证桌面 GStreamer 依赖

- 目标：为第二部分真实媒体联调准备本机环境。
- 修改：在用户目录 `/Users/hhz/hb` 安装 Homebrew、GStreamer 1.28.6、`libnice-gstreamer`、`pygobject3`、`libffi` 和构建工具；在项目 `.venv`（Python 3.13.2）编译安装 `Pycairo` 与 `PyGObject`。
- 验证：设置 GI、动态库和插件路径后，`tools/check_desktop_media.py` 返回 `READY`；确认 `webrtcbin`、nice plugin、H.264 depay/parser/`avdec_h264`、`videoconvert`、`videoscale`、`fakesink` 和 `autovideosink` 可用；11项pytest全部通过。
- 决策：桌面媒体命令必须显式设置 `/Users/hhz/hb` 的运行时路径；GStreamer registry 使用独立文件，避免插件扫描缓存干扰。
- 未完成：尚未执行真实浏览器到 GStreamer 的 Offer/Answer、ICE 和视频解码闭环；下一步实现并运行 Desktop worker。

### 2026-08-31 — 接入桌面 GStreamer worker 并修正开发端口

- 目标：让 `DesktopGStreamerReceiver` 实际启动独立 worker，并完成浏览器到 `webrtcbin` 的桌面接收联调。
- 修改：新增 `backend/desktop_receiver_worker.py`，复用现有 WebRTC/ICE 处理并将解码链输出到 `fakesink`；新增 `tools/run_desktop_server.py`；修正桌面开发服务将 worker 信令地址绑定到实际启动端口，而非固定 8081。
- 验证：GStreamer worker 可启动；首次联调发现固定端口导致 worker 重试，已修正，待重启服务后复测真实 Offer/Answer/ICE。
- 决策：开发服务的 HTTP/WS 单端口模式必须显式同步 `config.server.ws_port`；RK3588 双端口部署仍保留原配置。
- 未完成：确认 worker 端 `webrtcbin` 进入连接/播放并补充 worker 状态事件和日志采集。

### 2026-08-31 — 完成首轮浏览器到桌面 GStreamer 联调

- 目标：验证 Desktop worker 能否接收浏览器测试媒体并完成真实 WebRTC 协商。
- 结果：sender 收到 GStreamer Answer（约2332字节），双方 ICE 与连接状态进入 `connected`；worker 日志确认收到 Offer、创建 Answer、发送 ICE，并运行 H.264 软件解码链配置。
- 修复：`websockets` 15 的 `ClientConnection` 无 `closed` 属性，改为直接发送并捕获连接异常；mDNS candidate 正则兼容浏览器不带 `a=` 前缀的 candidate 文本。
- 限制：本机连接随后出现 `disconnected/failed`，尚未证明持续播放和解码帧计数；当前 worker 仍无状态事件回传，动态 pad/管线播放需继续专项排查。
- 决策：首轮只认定 Offer/Answer/ICE 可行，不将短暂 `connected` 视为桌面媒体验收通过。
- 下一步：为 worker 增加 GStreamer bus、pad-added、pipeline state 和统计事件，通过 Supervisor 状态 API暴露；继续定位 macOS 多网卡/ICE候选导致的连接不稳定。

### 2026-08-31 — 改进桌面 ICE 与解码观测

- 目标：减少 macOS 浏览器 mDNS candidate 无法解析造成的 ICE 不稳定，并为持续解码提供可观测信号。
- 修改：worker 使用 `reg_ok.sender_ip` 替换 `.local` candidate 主机字段；`fakesink` 开启 handoff 并按帧输出 `decoded_frames`；candidate 解析改为按字段定位 `.local` 主机名。
- 验证：本地 resolver 单测可将 `abc.local` 转为 `127.0.0.1`；控制层11项pytest继续通过。
- 未完成：需要再次运行完整桌面 E2E确认持续 `decoded_frames`；尚未将帧计数接入 Supervisor 状态 API。

### 2026-08-31 — 修复主动停止后的连接角色残留

- 目标：修复 sender 主动发送 `stop` 后，其 WebSocket 随后关闭时被误判为 viewer 并重复清理房间的问题。
- 修改：`backend/server.py` 在 sender 主动停止时立即移除 `client_to_room` 映射；没有 viewer 时同步删除空房间；新增显式停止集成测试。
- 验证：10项pytest全部通过；`pip check`无损坏依赖；`compileall`与 `git diff --check`通过。
- 决策：会话角色结束时必须同时清理角色字段和连接到房间的反向索引，不能依赖后续 WebSocket 断开补偿。
- 未完成：当前房间状态仍由多个全局映射共同持有，后续应收敛进 SessionManager。

### 2026-08-31 — 浏览器P2P真实媒体链验证通过

- 目标：在没有GStreamer和RK3588的情况下继续验证真实Offer/Answer、ICE连接和远端媒体播放。
- 环境：本地Mock Web服务；两个内置浏览器标签；发送端使用Canvas测试媒体，viewer使用现有 `p2p-view.html`。
- 结果：sender收到 `new_viewer`后重新创建Offer；viewer生成并返回Answer（本次4868字节）；双方交换ICE，ICE和Connection状态均进入 `connected`；viewer触发video `ontrack`并显示“播放中”。
- 视频：viewer远端video `readyState=4`、`paused=false`、可见，浏览器报告解码尺寸640×360；动态测试计时画面可见。
- 停止：sender点击停止后viewer收到 `stopped`、状态改为“发送端已停止”并隐藏视频；MockReceiver状态为 `stopped`，活跃会话清空。
- 桌面媒体阻塞：Apple M2 Pro当前没有GStreamer CLI、PyGObject/`gi`、关键插件、Homebrew或容器运行时，暂不能执行DesktopGStreamer测试。
- 决策：浏览器P2P测试作为真实WebRTC协议和媒体传输的第二条保护链；DesktopGStreamer仍是第二阶段目标，但需要先安装原生依赖。
- 未完成：真实屏幕选择需人工授权；未验证GStreamer `webrtcbin/fakesink`和RK3588硬件接收。

### 2026-08-31 — 完成首轮Web实用性测试

- 目标：在真实浏览器页面中验证前端、MediaStream、RTCPeerConnection、WebSocket、Session和MockReceiver控制链。
- 修改：新增 `/api/receiver/status`；新增 `tools/run_mock_server.py`；`p2p-sender.html`增加仅由 `?testMedia=1`启用的1280×720 Canvas测试视频，不改变正常 `getDisplayMedia()`路径；补充浏览器测试说明。
- 浏览器结果：页面与设备扫描正常；无zeroconf时显示明确空状态；测试视频可见并持续更新；WebSocket连接成功；生成SDP Offer（本次5308字节）并收集3个ICE候选。
- Receiver结果：会话 `p2p_mtghnzxn`通过状态API确认进入 `playing`；点击停止后进入 `stopped`，`active_session_id`清空。
- 回归：9项pytest通过，`compileall`和`git diff --check`通过。
- 限制：内置浏览器不能操作系统屏幕选择器，真实 `getDisplayMedia()`授权仍需人工浏览器测试；MockReceiver不生成SDP Answer，因此本轮不验证ICE连接成功和远端媒体接收。
- 决策：Canvas测试媒体作为第一层Web可重复测试入口保留；真实屏幕捕获与真实媒体接收分别进入人工浏览器测试和第二阶段DesktopGStreamer测试。
- 未完成：自动化浏览器E2E尚未纳入pytest/CI；正式首页仍未统一到P2P发送端。

### 2026-08-31 — 验证Supervisor与正式WebSocket完整生命周期

- 目标：验证硬件无关Receiver能否通过正式aiohttp信令流程启动和回收，而不只是独立单元测试。
- 修改：新增 `ReceiverSupervisor` 单活跃会话协调器；`create_app()`支持可选注入Supervisor；`/ws`在首次Offer、主动停止和sender断开时驱动Supervisor；新增Supervisor和Mock服务生命周期测试。
- 兼容：默认 `create_app()`未注入Supervisor时仍调用原 `_auto_start_display()`/`_stop_display()`，RK3588现有启动路径保持不变。
- 验证：9项pytest全部通过；确认Offer可驱动MockReceiver到 `PLAYING`，sender断开后到 `STOPPED`，切换会话会先停止旧Receiver。
- 决策：后续真实Desktop/RK3588 Receiver统一由Supervisor管理；迁移阶段继续保留默认旧硬件路径作为回退。
- 未完成：Supervisor尚未消费Receiver事件并发布状态API；Mock模式尚未提供命令行配置入口；真实GStreamer Receiver尚未适配统一接口。

### 2026-08-31 — 建立无硬件测试环境并完成首轮可行性试验

- 目标：在不连接 RK3588、不安装 GStreamer的条件下验证测试技术栈、现有short-format信令和Receiver硬件解耦接口。
- 修改：新增 `.venv` 忽略规则、`requirements-dev.txt`、`pytest.ini`、`backend/receivers/`统一接口与MockReceiver、`tests/`自动化测试；更新 `TESTING.md`。
- 修复：viewer注册时原代码读取不存在的 `WebSocketResponse.remote`，导致连接异常关闭；现改为在WebSocket注册时显式保存并清理peer信息。
- 验证：Python 3.13.2下7项pytest全部通过，`pip check`无损坏依赖，`compileall`和`git diff --check`通过。
- 决策：新自动化测试统一放在 `tests/`；历史 `test/`暂不默认收集；Receiver生产接口保持Python 3.8兼容；首轮不改RK3588媒体管线。
- 未完成：MockReceiver尚未接入正式服务的ReceiverSupervisor；未验证真实SDP媒体协商和RK3588实机。

### 2026-08-31 — 确定三段式开发与递进测试策略

- 目标：将硬件解耦方案落实为明确的开发顺序和阶段验收。
- 修改：未修改运行代码；确定“无硬件控制层 → 桌面真实媒体层 → RK3588 硬件层”三部分开发节奏，并规定对应测试层级。
- 验证：三个阶段分别覆盖控制逻辑、真实 WebRTC/GStreamer 媒体链和 RK3588 专有能力，阶段依赖方向清晰。
- 决策：每部分通过完成标准后再进入下一部分；上层测试不依赖下层环境，实机测试聚焦硬件和性能风险。
- 未完成：第一部分的详细任务拆分和首批保护性测试尚未实施。

### 2026-08-30 — 确定硬件解耦边界

- 目标：支持大部分功能脱离 RK3588 开发，同时保留真实硬件专项开发路径。
- 修改：未修改运行代码；在本文档新增 Receiver Backend、三种实现、Worker 事件、平台适配边界和三层验收方案。
- 验证：方案覆盖当前 `server.py` 子进程管理和 `hdmi_receiver.py` 媒体执行职责，可渐进迁移现有稳定链路。
- 决策：控制面只依赖统一 Receiver 接口；RK3588 细节限制在媒体 Worker 内；保留独立媒体进程作为故障隔离边界。
- 未完成：Receiver 接口、MockReceiver 和 ReceiverSupervisor 尚未实现。

### 2026-08-30 — 完成架构评审

- 目标：判断现有架构是否需要优化，并确定重构优先级。
- 修改：未修改运行代码；在本文档增加 P0/P1/P2 架构优化清单。
- 验证：复核 `server.py` 路由、信令分发、全局状态、HDMI 子进程管理、双端口监听、GStreamer 接收实现、发送端协议和 compositor/audio 占位实现。
- 决策：保留 WebRTC + aiohttp + GStreamer + DRM/KMS 技术路线；先统一主链和状态所有权，再重构媒体层，最后处理扩展功能。
- 未完成：尚未在 RK3588 实机复现基线，评审结论目前基于仓库代码和历史运行记录。

### 2026-08-30 — 建立项目长期记忆

- 目标：为后续开发和上下文恢复提供统一事实来源。
- 修改：新增 `PROJECT_MEMORY.md`，记录目标分支、运行基线、架构结论、关键约束、已知问题、开发决策和工期。
- 验证：确认远程存在 `main`、`mac`、`python-webrtc-screen-share` 三个分支；当前处于 `python-webrtc-screen-share`，HEAD 为 `28b64ad`。
- 决策：后续每次实际代码、配置、部署、测试或架构变更都同步更新本文档；恢复任务时优先阅读本文档。
- 未完成：尚未在本轮开发中重新连接 RK3588 实机复现基线。

### 2026-08-31 — RK3588 实机闭环复现与显示输出定位

- 目标：在真实浏览器到 Orange Pi 5 Pro 的链路上验证信令、WebRTC 协商、GStreamer 接收和 HDMI/DRM 输出。
- 环境：Orange Pi 5 Pro，Ubuntu focal/aarch64，内核 `5.10.160-rockchip-rk3588`，GStreamer `1.16.3`；板端固定地址 `192.168.1.109`，服务 HTTPS `8080`、本机 WS `8081`。
- 结果：浏览器 Canvas 测试媒体成功触发板端 receiver；Answer、ICE、`PAD_ADDED`、VP8 depay/decoder 链均成功，说明控制面和媒体协商已通；断开后 receiver 能清理，健康检查恢复 `sessions=0`。
- 定位：当前 DRM `DP-1` connected，首选模式 `2560x1440@60`；`HDMI-A-1` disconnected。历史配置仍为 `1024x600 + plane 71`，`kmssink` 报 `drmModeSetPlane Invalid argument (-22)`，故尚未宣称 HDMI 画面验收通过。
- 修改：`backend/hdmi_receiver.py` 保留历史默认值，同时支持 `SCREENCAST_DISPLAY_WIDTH`、`SCREENCAST_DISPLAY_HEIGHT`、`SCREENCAST_KMS_PLANE_ID` 环境变量；新增 `tools/check_rk3588_display.py` 输出连接器、模式和 plane 信息。
- 下一步：连接目标 HDMI/DP 显示器后重新采集 connector/mode，按实测模式配置输出尺寸和 plane，再做画面验收；不要把当前 DP 状态误认为 HDMI 已验收。
- 部署备注：本地改动已通过 11 项 pytest、compileall 和 diff 检查；随后执行远程 deploy 时 SSH 连接中途断开，板端当前端口有响应但 SSH/health 未恢复，待板端重启或串口确认后重试部署。

### 2026-08-31 — HDMI-A 实机输出链路复验

- 条件：板端网络恢复，`HDMI-A-1 connected`，首选模式为 `2560x1440`；部署后 systemd drop-in 设置 `SCREENCAST_DISPLAY_WIDTH=2560`、`SCREENCAST_DISPLAY_HEIGHT=1440`、`SCREENCAST_KMS_PLANE_ID=71`。
- 结果：浏览器 Canvas 测试媒体再次完成 Offer/Answer、ICE checking→connected；板端日志出现 `PAD_ADDED`、VP8 接收和 `VIDEO PIPELINE LINKED ... 2560x1440`，此次未再出现 `drmModeSetPlane -22`，receiver 进程保持运行。
- 回收：浏览器停止投屏后 receiver 进程退出，健康接口恢复 `sessions=0`。
- 结论：信令、WebRTC、GStreamer、KMS 管线已完成实机闭环验证；物理屏幕上的最终画面仍建议由现场观察确认，后续可加入 pipeline playing/frame metrics 作为自动化证据。

### 2026-08-31 — 第一轮可用性测试：重复启停

- 方法：浏览器测试媒体连续建立并停止 3 次会话，每次等待 WebRTC 连接后再停止。
- 结果：3/3 次均达到 `ICE connected` 和 `CONN connected`，3/3 次页面显示“已停止”；板端健康接口恢复 `sessions=0`，无残留 `hdmi_receiver.py` 进程，日志未出现 KMS 或 GStreamer error。
- 结论：单用户短时重复启停通过；下一轮进入长时间持续播放和资源/帧率指标观察。

### 2026-08-31 — 真实屏幕入口问题定位

- 现象：用户从 `http://192.168.1.109:8080` 打开页面时，浏览器使用 `ws://` 连接 HTTPS 控制端口失败，同时 `navigator.mediaDevices` 不存在，无法调用 `getDisplayMedia()`。
- 修复：发送页在真实屏幕模式下增加 `window.isSecureContext` 检查并给出 HTTPS 操作提示；测试媒体模式仍允许 HTTP；部署时同步前端改动。
- 操作要求：真实电脑屏幕必须使用 `https://192.168.1.109:8080/p2p-sender.html`，首次访问需在浏览器确认自签名证书；Canvas 测试页可继续使用 `http://192.168.1.109:8081/...?...testMedia=1`。

### 2026-08-31 — 真实屏幕采集成功但 WSS 握手失败

- 现象：浏览器日志出现“屏幕捕获成功”，随后 `WS 连接失败`、`Failed to fetch`，并进入重复重连；说明安全上下文已满足，故障集中在 8080 TLS/WebSocket 握手或证书信任。
- 防护：发送页将自动重连限制为“连接曾成功后才重连”，避免初始握手失败时无限重试压垮板端。
- 状态：该前端修复已在本地完成，但板端在持续重连后暂时无响应，需恢复服务后重新部署；下一步先单独验证 `wss://192.168.1.109:8080/ws`，再恢复真实屏幕投屏。

### 2026-08-31 — 重新设计真实屏幕联调入口

- 决策：真实屏幕发送端不再依赖板端自签名 HTTPS。使用电脑本机 `localhost` 提供前端，浏览器将其视为安全上下文；信令直接连接板端普通 `ws://192.168.1.109:8081/ws`。
- 修改：发送页支持 `?ws=` 覆盖信令地址；新增 `tools/run_sender_dev.py`；`TESTING.md` 增加真实屏幕测试步骤。
- 使用：运行 `.venv/bin/python tools/run_sender_dev.py`，用 Chrome/Edge 打开脚本输出的 Real screen 地址。
- 验证：本地 11 项测试、compileall、git diff --check 通过；待板端恢复后执行真实屏幕投屏复测。

### 2026-08-31 — 开始实现 HDMI 待机引导画面

- 目标：无投屏会话时，在 HDMI 上显示设备说明、Wi-Fi SSID/密码、访问地址和 Wi-Fi 二维码。
- 修改：新增 `backend/standby_display.py`，使用 `qrencode` 生成二维码、SVG/rsvg 渲染、`imagefreeze` 保持单帧，并通过 `kmssink` 输出；支持显示尺寸、plane、SSID、密码和地址环境变量。
- 板端能力：已确认 `qrencode`、GStreamer `rsvg`、`imagefreeze`、`kmssink` 均可用；代码已部署，独立渲染进程可启动。
- 当前阶段：待机渲染器暂以独立进程运行用于确认视觉布局，尚未接入 server 的启动/停止生命周期；确认画面后再实现“投屏开始隐藏、停止恢复”的自动切换。
- 反馈与修复：首次试运行出现 shell 覆盖（`getty@tty1` 的 fbcon 在 primary plane）；已在板端停用 `getty@tty1`，不影响 SSH。中文字体导致乱码，已改用英文/ASCII；二维码由 SVG 相对路径改为绝对 `file://` 路径。待用户确认 HDMI 画面后再接入生命周期。
- 第二轮修复：二维码改为 PNG Base64 内嵌到 SVG；启动待机渲染前主动向 `/dev/tty1` 写入终端清屏序列，并继续停用 `getty@tty1`，用于清除历史 shell 内容。待用户复核物理屏幕是否仍有 fbcon 覆盖。
- 生命周期接入：新增 `scripts/screencast-standby.service`，systemd 开机自动运行待机渲染；`server.py` 在投屏开始时停止该服务，投屏停止时恢复；部署脚本自动安装/启用该服务。板端当前 `screencast` 与 `screencast-standby` 均 active，健康接口正常。`getty@tty1` 已 disabled。
- 用户验收：用户确认待机画面已不再被 shell 覆盖，当前版本暂作为稳定基线冻结；后续进入功能迭代。
- 功能迭代 1：新增 `network` 配置项（设备名、AP SSID/密码/地址）及 `GET /api/device-info`，统一向待机页、客户端和管理端提供 onboarding 信息；新增接口测试，12 项 pytest 全部通过；板端 API 已部署并验证可返回 `192.168.50.1` 的 HTTPS/WS 地址。

### 2026-08-31 — 产品目标调整为单设备无线投屏网关

- 用户目标：借鉴小米拍拍的易用体验，但不复刻其发送端/接收端设备组网模式；RK3588 本身提供一个局域网，电脑连接该局域网后即可投屏。
- 产品边界：RK3588 = Wi-Fi AP/局域网网关 + 投屏控制服务 + WebRTC 接收器 + HDMI 输出；发送端是加入该局域网的电脑，不参与设备间组网。
- 推荐网络拓扑：RK3588 AP 模式（SSID/密码可配置）→ DHCP/DNS → 发送端；RK3588 固定网关地址（例如 `192.168.50.1`）只作为局域网内部服务地址；以太网保留为可选上行/调试接口。
- 推荐用户流程：上电 → 屏幕显示 SSID、密码、二维码/访问地址 → 电脑连接 AP → 打开发送端 → 选择屏幕 → HDMI 输出。
- 安全上下文决策：浏览器 `getDisplayMedia()` 需要安全上下文。开发阶段使用 localhost 发送端；产品化优先考虑本地发送端（Tauri/Electron/原生小工具）或安装本地 CA 的 HTTPS，而不是依赖自签名 IP 证书。
- 架构取舍：取消“发现多个接收设备并选择”的主流程；mDNS 仅作为可选便利能力，不能成为单设备投屏的必要依赖。首期只保留单活跃发送端，后续再考虑排队/抢占。
- 客户端决策：产品化发送端允许从浏览器页面升级为自研桌面客户端。首选 Electron 作为毕设 MVP（复用现有 HTML/JS/WebRTC，屏幕采集和连接流程实现成本最低）；Tauri/原生 GStreamer 客户端作为后续轻量化方向，不作为首期阻塞项。
- AP 能力实测：Orange Pi 5 Pro 的 `wlan0` 当前为 managed/disconnected，但 `iw list` 明确包含 `AP`、`P2P-GO`；板端已安装 `/usr/sbin/hostapd`、`/usr/sbin/dnsmasq` 和 `nmcli`。结论：硬件/驱动支持独立局域网热点，尚未写入热点配置。
- AP 首次配置完成：NetworkManager 连接 `RK-Screencast` 已启用并设置 `connection.autoconnect=yes`，SSID `RK-Screencast`，网关 `192.168.50.1/24`，DHCP shared 模式，地址池 `192.168.50.10-192.168.50.254`；实测 `wlan0 type AP`、dnsmasq 正常、8080 健康接口可从该地址访问；有线 `192.168.1.109` 保留 SSH 调试。
