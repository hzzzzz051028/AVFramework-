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

### 2026-08-31 — 验证板端 HTTPS 证书是 WSS 卡点

- 实测证书：`cert.pem` 为自签名证书，`CN=orangepi5pro`，没有 `Subject Alternative Name`（无 IP SAN）。
- 影响：通过 `https://192.168.50.1` 或 `https://192.168.1.109` 访问时，主机名/IP 与证书不匹配；浏览器可能允许页面例外，但 WSS/Fetch 仍可能失败，符合此前 `WS 超时` 与 `Failed to fetch` 现象。
- 下一步：生成带 `192.168.50.1`、`192.168.1.109`、`orangepi5pro` SAN 的本地 CA/服务器证书，并在测试电脑安装 CA；之后重新验证纯浏览器直投。

### 当前环境状态

- 用户当前无 RK3588 板端环境。暂停所有 AP、证书部署、HDMI/KMS 和实机性能验证；保持本机 Mock/桌面测试与代码迭代。
- 板端恢复后优先：部署补齐 Authority/Subject Key Identifier 的新 TLS 证书、信任本地 CA、验证 `https://192.168.50.1` + WSS 纯浏览器投屏。

### 2026-08-31 — 无板子环境验证

- 自动化：12 项 pytest、`compileall` 均通过。
- 桌面媒体：本机 Homebrew GStreamer 1.28.6 在加载环境变量后通过诊断；`nice`、`webrtcbin`、H.264 depay/parser/decoder、`fakesink` 均可用。未加载环境变量时 PyGObject 无法定位 Homebrew GLib 动态库。
- 浏览器 Mock E2E：启动 `tools/run_mock_server.py` 后，浏览器 Canvas 测试媒体成功连接 WebSocket、创建 Offer/ICE；`/api/receiver/status` 确认 MockReceiver 进入 `playing`；停止后页面显示“已停止”，active session 清空。

### 2026-08-31 — 无硬件媒体管道模拟

- 范围：不模拟 AP、DHCP 或 HDMI，仅验证媒体管道。
- 新增：`tools/check_media_pipeline.py`，使用本机 GStreamer `videotestsrc → videoconvert → fakesink` 以及 `videotestsrc → x264enc → h264parse → avdec_h264 → fakesink` 进行 headless 实帧检查。
- 实测：1280×720/30fps、2 秒运行，raw 与 H.264 编解码回环均处理 60 帧（29.9fps）；pytest 12 项通过。
- 结论：发送端默认 H.264 与软件解码回退的媒体处理逻辑可继续无板子开发；MPP、KMS/HDMI 仍待板端验收。

### 2026-08-31 — 毕设嵌入式化第二阶段规划（待硬件回归通过后实施）

- 判断：当前“浏览器/WebRTC/GStreamer/HDMI”闭环具备可用性，但若只停留在该层，项目更偏软件工程，嵌入式特色不足。
- 实施前置：待 RK3588 重新在场，完成稳定实机回归（真实屏幕、长时播放、启停/断连）后，再进入本阶段，避免过早扩展。
- 设备化：把 AP/DHCP/mDNS、投屏服务和 HDMI 待机引导界面整合为上电即用的独立终端；形成待机、配网、发现、连接、投屏、断连恢复、异常降级的设备状态机。
- 硬件链路：评估并尽量落地 RK3588 MPP 硬件解码、RGA 缩放与 DRM/KMS 显示，记录内存拷贝路径；对比软件解码回退路径。
- 自适应与可靠性：根据分辨率、帧率、CPU、温度、丢包等指标实施 720p/1080p、码率和帧率的降级策略；补齐单发送端抢占、断网重连和资源释放。
- 可量化验收：采集并展示首帧时间、端到端时延、帧率/丢帧、CPU/内存、温度、重连时间等数据，形成软/硬件方案对比。
- 可选控制面：网页/手机管理页用于设备状态、网络配置、日志导出与基础运维；不阻塞核心投屏闭环。
- 拟定论文表达：`基于 RK3588 的自主组网低时延无线投屏终端设计与实现`。
- 已提前实现第一批无硬件骨架：新增设备级 `ready/connecting/casting/degraded/fault/stopping` 状态机；ReceiverSupervisor 自动转发媒体生命周期事件；新增会话、播放、完成、失败和首帧耗时指标。
- 新增 `GET /api/device/runtime` 和 `POST /api/device/telemetry`。遥测策略根据温度、CPU、丢包率和丢帧率输出 `1080p30/720p30/720p20` 建议；当前明确为 dry-run，不会自动干预真实投屏。
- 真实板端接入：`hdmi_receiver.py` 仅在视频 pad、解码链和 KMS sink 完成链接后，经信令回报 `receiver_status=playing`；服务端据此进入 `casting`，避免把“子进程已启动”误计为已出画面。停止与启动失败也会回写整机状态。
- 验证：MockReceiver 与 legacy HDMI worker 回报两条路径均可驱动 `ready → connecting → casting → ready`，自动化测试增至 19 项。

### 2026-08-31 — 待机页内容层与显示层拆分

- 用户方向：待机界面要具备投屏产品的观赏性，支持轮播视觉、二维码/Wi-Fi 引导、投屏状态和 RK3588 资源占用；同时页面必须能脱离板子独立开发和预览。
- 新增页面：`frontend/standby.html`、`standby.css`、`standby.js`。深色玻璃质感布局包含轮播主视觉、三步连接引导、Quick Connect 二维码卡片、CPU/内存/温度/运行时间和 MPP/RGA/KMS 能力标签；`?demo=1` 使用本地演示数据。
- 新增素材：`frontend/assets/standby/ambient-cast.png`，原创无文字抽象背景，可替换或继续扩展为本地轮播图，不依赖 CDN。
- 新增 API：`GET /standby`、`GET /standby.html`、`GET /api/device/wifi-qr.svg`。二维码在板端调用 `qrencode` 生成；开发机没有该命令时返回明确的视觉回退 SVG。
- 结构拆分：原 `backend/standby_display.py` 降为兼容入口；静态 SVG→GStreamer→KMS 实现移至 `backend/standby_renderers/svg_kms.py`；增加可选 `html_kiosk.py`（Chromium/cage），默认仍保持 SVG/KMS 启动安全回退。
- 依赖准备：RK3588 安装脚本补充 `qrencode` 和 `fonts-noto-cjk`；尚未在板上安装/启用 Chromium/cage，待硬件回来后单独验证 DRM 所有权与 kiosk 稳定性。
- 验证：页面与二维码接口本地返回 200，自动化测试增至 21 项；`compileall` 与 `git diff --check` 通过。

### 2026-08-31 — 待机页真实设备部署（HTML 暂不切换）

- 板端：`orangepi5pro` / RK3588，`192.168.1.109` SSH 恢复；`screencast.service` 与 `screencast-standby.service` 均 active。
- 部署：通过 `scripts/remote_service.sh deploy` 上传页面、renderer 和后端改动；HTTPS `/standby.html` 返回 200，`/api/device/runtime` 为 `ready`，`/api/device/wifi-qr.svg` 返回真实二维码（`X-QR-Available: true`），`/api/status` 确认 GStreamer 1.16.3、MPP/RGA/DRM/KMS 均可用。
- 当前物理 HDMI：继续使用 SVG/KMS 回退，未影响原有稳定待机和投屏闭环。
- 阻塞：板端 apt DNS 无法解析 `repo.huaweicloud.com`，`chromium-browser` 与 `fonts-noto-cjk` 安装失败；镜像当前无 Chromium/cage/中文字体，因此 HTML kiosk 尚未切换。修复 DNS 后再安装并做 DRM 所有权试验。

### 2026-08-31 — 不切换笔记本 Wi-Fi 的真实投屏连接验证

- 网络路径：笔记本默认网关仍通过 Wi-Fi `en0` 上网；到板端 `192.168.1.109` 的路由走独立有线接口 `en7`。外网 `https://example.com` 返回 200，说明 Codex/互联网连接未受影响。
- 浏览器测试：通过板端 `http://192.168.1.109:8081/p2p-sender.html?testMedia=1` 启动真实 Canvas 测试媒体，WebSocket、Offer/Answer、ICE 均成功，浏览器状态到 `connected`。
- RK3588 实链路：板端 `hdmi_receiver.py` 成功接收 VP8，日志出现 `VIDEO PIPELINE LINKED: VP8 (plane-id=71, 2560x1440)`；runtime 进入 `casting`，首帧耗时约 2075 ms。
- 回收：浏览器停止后 runtime 回到 `ready`，`sessions_started=1`、`sessions_played=1`、`sessions_completed=1`、`sessions_failed=0`；待机服务重新 active。
- 结论：可在笔记本保持 Wi-Fi 上网的情况下，用有线管理链路完成真实投屏验证。若要测试“笔记本只连 RK AP 仍能上网”，需单独验证板端 Ethernet 上行/NAT，不应与本次投屏回归混在一起。
- 操作固化：真实屏幕使用 `.venv/bin/python tools/run_sender_dev.py --device-host 192.168.1.109 --device-port 8081`；页面必须从 localhost 打开，避免 `http://192.168.1.109:8081` 非安全上下文导致 `getDisplayMedia` 不可用。以太网地址 `192.168.1.109` 与 AP 地址 `192.168.50.1` 不可混用。
- 故障修复：发现 `run_sender_dev.py` 原先把 `/ws` 放入 `?ws=` 参数，而 `p2p-sender.html` 还会追加 `/ws`，实际请求变成 `/ws/ws` 并被板端 404；启动器现已只传 WebSocket origin，并新增回归测试。
- 修复复验：板端日志中的 `/ws/ws 404` 已消失；重新启动修复后的发送页后，真实以太网链路再次完成 `WS 已连接`、`ICE connected`、`P2P 连接成功`，runtime 进入 `casting`；停止后回到 `ready`，第二次会话累计完成且失败数仍为 0。旧的 8090 启动器进程需在用户终端按 Ctrl-C 后重启，才能加载修复。
- 用户确认：以太网链路连接正常，已可以稳定投屏；笔记本 Wi-Fi 上网和 Codex 使用不受影响。该链路作为后续硬件开发的稳定调试通道。

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

### 2026-08-31 — AP 与延迟判断

- AP 与以太网使用同一套发送页、WebSocket 信令、WebRTC 媒体管道、GStreamer 解码和 HDMI 输出，功能上等价；变化仅是发送端访问地址从 `192.168.1.109` 切换为 AP 网关 `192.168.50.1`。
- 当前 AP 已配置为 `192.168.50.0/24` 经板端 Ethernet 上行的 NAT/转发模式（`ip_forward=1`、`POSTROUTING MASQUERADE`）；AP 客户端应可访问投屏服务，并可经有线上行访问互联网，仍需用独立客户端做 DHCP/DNS/外网实测。
- 当前无线参数为 2.4 GHz、20 MHz；高码率投屏不一定比有线低延迟，若驱动支持，后续应比较 5 GHz/更宽信道与 2.4 GHz 的稳定性。
- 已观测到的约 1.7–2.1 s 主要是“协商到首帧”的启动时间，不等同于稳定播放的端到端交互延迟。稳定延迟的首要优化方向是发送端限制分辨率/帧率、减少队列，以及将接收端当前软件解码路径切换到 RK MPP 硬件解码并配合 RGA/KMS；AP/以太网只作为传输层 A/B 变量。
- AP 配置固化：新增 `scripts/configure_ap.sh` 与 `scripts/remote_service.sh ap-setup`，以 NetworkManager shared 模式幂等配置 SSID、WPA2、固定网关、DHCP/DNS/NAT 和 IPv4 转发；默认保留 Ethernet 默认路由作为可选上行。完整断网测试步骤写入 `TESTING.md`。
- AP 实测补充：AP 客户端已成功获得 `192.168.50.x` 租约，板端 `wlan0`、dnsmasq、转发和 MASQUERADE 均正常；但板端到静态默认网关 `192.168.1.1` ping 不通，板端自身访问外网也超时。当前 Ethernet 是调试链路/直连链路，不是可达互联网的路由器上行，因此 AP 无法提供外网并非投屏或 NAT 代码故障。若产品需要 AP 上网，Ethernet 必须接入真实有线路由器，或额外配置电脑 Internet Sharing。
- 浏览器发送端现状：`tools/run_sender_dev.py` 只是在开发阶段提供 localhost 安全上下文，让 `getDisplayMedia()` 可用；产品化不应依赖它。可选方向为（1）让用户一次性信任设备 CA 后直接打开 `https://192.168.50.1:8080/p2p-sender.html`，页面通过同端口 WSS 连接；（2）使用 Electron/Tauri 原生发送端，彻底绕开浏览器证书和安全上下文限制。

### 2026-08-31 — 低延迟第一轮

- 发送端：`p2p-sender.html` 与 `sender.html` 默认请求并二次约束 `1280×720@30fps`，将 H.264 放在视频编码偏好首位，限制发送帧率/码率并使用 `maintain-framerate`；局域网投屏不再依赖公网 STUN。
- RK 接收端：`hdmi_receiver.py` 调低 WebRTC RTP jitterbuffer 到 20ms 并启用超时丢旧帧；只在解码后使用单帧 leaky queue，避免丢压缩参考帧；KMS sink 关闭同步/处理 deadline，默认不再走 CPU `videoscale`，交给 KMS plane 缩放。
- 解码选择：按实际 GStreamer factory 探测 MPP/V4L2/软件解码，而不是仅依据 `/dev/mpp_service` 判断。当前板端未安装 `rkmpph264dec`/`v4l2h264dec` factory，实际回退 `avdec_h264`；后续安装 Rockchip GStreamer 插件后可自动切换硬解。
- 实测：低延迟首轮复测已从约 5.4s 首帧回落到约 2.0s；当前仍缺少摄像机/时间戳式端到端稳态延迟测量，50ms 目标需在真实 720p30 与硬件解码路径上验收。

### 2026-08-31 — RK3588 MPP 硬解插件接入

- 根因确认：Orange Pi 5 Pro 的内核有 `/dev/mpp_service`，但初始系统缺少 `librockchip_mpp` 与 `mppvideodec` GStreamer factory，因此真实 H.264 会话实际使用 `avdec_h264` 软件解码；不能只凭设备节点宣称硬解可用。
- 板端环境：Ubuntu 20.04/aarch64、Linux `5.10.160-rockchip-rk3588`、GStreamer `1.16.3`。以官方 Rockchip MPP 源码原生构建 MPP 库，并以匹配的 Rockchip GStreamer 插件构建 `mppvideodec`。
- 隔离安装：MPP 放在 `/opt/screencast/vendor/mpp`，插件放在 `/opt/screencast/vendor/gstreamer-rockchip/lib/gstreamer-1.0`；不覆盖系统 GStreamer 或系统 MPP 库。`scripts/enable_mpp_plugin.sh` 先以独立 registry 探测插件，随后仅为 `screencast.service` 设置 `GST_PLUGIN_PATH` 和 `LD_LIBRARY_PATH`。回退方式是删除 `/etc/systemd/system/screencast.service.d/mpp.conf` 后重启服务。
- 验证：`gst-inspect-1.0 mppvideodec` 已列出 AVC/HEVC/VP8/VP9 硬解能力；板端实跑 `videotestsrc → x264enc → h264parse → mppvideodec → fakesink`，720p30、60 帧正常结束并输出 NV12。MPP 的启动提示 `client 12 driver is not ready` 未阻止实际 H.264 解码。
- 代码：`hdmi_receiver.py` 现在优先选择 `mppvideodec`，并在 H.264/H.265 depay 后加入无缓存的 `h264parse/h265parse`，满足 MPP 所需的 `parsed` AU caps；保留旧 BSP factory 与 `avdec_*` 回退。硬件状态 API 现在区分 MPP 设备存在与实际 GStreamer decoder factory。
- 待验收：把服务加载插件后做完整 WebRTC→MPP→KMS 实机回归，记录 CPU、首帧和摄像机/时间戳端到端稳态延迟；在未测得数据前不得宣称已经达到 50ms。

### 2026-08-31 — MPP 服务级实机回归通过

- 部署：`scripts/remote_service.sh deploy && scripts/remote_service.sh enable-mpp` 已在 `192.168.1.109` 执行；`screencast.service.d/mpp.conf` 仅注入隔离插件路径与 MPP 库路径，服务启动正常。
- 状态：`GET /api/status` 返回 `mpp_available: true`、`mpp_device_available: true`、`mpp_decoder: "mppvideodec"`。
- 全链路验证：浏览器 Canvas 测试媒体成功建立 WebSocket、Offer/Answer 和 ICE；板端 receiver 日志明确出现 `Stream encoding: H264`、`Decoder selected: mppvideodec`、`VIDEO PIPELINE LINKED: H264 (plane-id=71, 2560x1440)`，MPP 进一步记录 `hal_h264d_vdpu34x`、1280×720 解码配置。停止后 receiver 无残留，整机 runtime 回到 `ready`，待机服务恢复 active，失败数为 0。
- 资源观察：720p30 测试流播放时 `hdmi_receiver.py` 约 10% CPU；此前软件解码同类测试约 66% CPU。这是一次短时采样，后续仍需要 10–30 分钟稳定性与物理端到端延迟测试。
- 当前结论：硬件解码路径已经实机生效，消除了软件解码的主要瓶颈；`last_time_to_play_ms≈1747` 是协商/首帧指标，不能代表稳态延迟，也不能据此宣称满足 50ms。

### 2026-08-31 — 产品硬约束确认

- 发送端目标：允许多种电脑/终端发起投屏，不能把特定客户端、特定操作系统或互联网访问作为核心前置条件；优先零安装、网页入口，原生客户端作为增强方案。
- 使用体验目标：加入投屏器网络后，不能无故破坏用户原有上网能力。AP-only 模式只能保证局域网投屏，不能同时保证互联网；要满足“不干涉设备使用”，正式产品必须优先支持 Ethernet 上行的 AP+NAT，或后续评估 AP+STA/中继模式。
- 现实边界：纯浏览器方案在桌面 Chrome/Edge/Firefox 上可覆盖主要电脑平台，但 iOS/Android 对“捕获整个设备屏幕”有系统限制；移动端全屏投屏需要原生 MediaProjection/ReplayKit 或系统 AirPlay/投屏协议，不能承诺由网页无条件实现。
- 会话模型：虽然配置允许多个 WebRTC 会话，但单个 HDMI 输出同一时刻只能呈现一个发送端；产品行为应明确为“多设备可连接、单设备上屏”，实现抢占/确认或排队，避免多个发送端争抢显示管线。

### 2026-08-31 — “零要求发送端”与网络不干涉的边界

- 投屏不需要互联网：WebRTC/信令可在本地链路完成；完全无上行时，Standalone AP 仍必须允许离线投屏。
- 不能承诺无条件保留互联网：如果发送设备只有一个 Wi-Fi 网卡，连接到投屏器 AP 后就离开原 Wi-Fi，且 AP 没有上行时，互联网在物理上无法保留；这不是软件缺陷。
- 产品网络模式应分层：
  1. `Wired LAN`：RK3588 通过 Ethernet 接入现有局域网，发送设备保持原网络；链路最稳定，优先用于低延迟调试和演示。
  2. `Same-LAN`：RK3588 作为现有路由器的 Wi-Fi 客户端，发送设备继续使用原网络，优先保证“不切网”。即使该 LAN 无互联网，也可以投屏。
  3. `Standalone AP`：RK3588 自建局域网，完全离线可投屏；待机页明确“仅局域网”，不伪装成可上网。
  4. `AP + Uplink`：Ethernet 上行优先，后续评估 AP+STA/中继；发送设备连 RK AP 后由 RK3588 提供 NAT 上网。
- 若要在发送设备保持原 Wi-Fi 上网的同时走独立投屏链路，只能使用第二网络接口（Ethernet/USB Wi-Fi）或 Wi-Fi Direct/P2P；单网卡、无上行时不存在通用方案。

### 2026-08-31 — 外部信令安全收敛

- 风险修复：此前外部发送端使用明文 `ws://设备:8081/ws`，且无 Origin、配对或速率限制；同一局域网内任意主机可尝试建立投屏会话。
- 新边界：`8080` 为唯一外部 HTTPS/WSS 入口；服务缺失 `cert.pem/key.pem` 时拒绝启动外部投屏。`8081` 改为仅绑定 `127.0.0.1`，只供板内 `hdmi_receiver.py` 使用，外部 TCP 客户端不可达。
- 配对：服务每次启动生成随机 8 位投屏码，写入权限 `0640` 的 `/run/screencast/pairing-code`；SVG/KMS 待机页（以及未来 HTML kiosk）读取并显示它。外部 WSS 连接必须先发送配对码，错误尝试按来源 60 秒内限制 5 次；投屏码不在公开设备信息接口中返回。
- 浏览器保护：外部 WS 必须是 TLS 且仅接受同设备 HTTPS 页面或 localhost 开发页的 Origin；WHEP 与终端调试 WebSocket 收敛为本机接口。
- 证书：本地 `.local-certs/` 保存配套的服务证书、私钥和公开 CA。`remote_service.sh deploy` 会把三者以受限权限安装到板端，公开 CA 可通过 `/api/device/ca.pem` 下载；发送电脑需一次性信任该 CA 后再使用 WSS。私钥不会在日志或 HTTP 接口中公开。
- 部署验证：已将匹配的服务证书/私钥/CA 安装到 `192.168.1.109`；`openssl` 以 `.local-certs/ca.pem` 验证返回 `0 (ok)`。板端端口为 `0.0.0.0:8080` 和 `127.0.0.1:8081`；Mac 外部访问 8081 被拒绝。外部 WSS 实测：缺失 Origin 得到 403、未配对 ping 得到 `pairing_required`、正确投屏码后可得到 `pair_ok` 和 pong。
- 待验收：在发送电脑的浏览器/系统证书库一次性信任 `.local-certs/ca.pem` 后，使用 HDMI 投屏码完成一次真实浏览器媒体投屏回归；这是严格 HTTPS/WSS 不能自动绕过的用户侧信任步骤。
- 发送页主流程更新：CA 被信任后，直接访问设备 IP 的 `https://<device-ip>:8080/p2p-sender.html`。该页面本身是安全上下文，并同源连接 `wss://<device-ip>:8080/ws`；`tools/run_sender_dev.py` 只保留给无证书/前端调试，不属于产品使用路径。
- 同步修复：SVG/KMS 待机页是静态渲染，曾在服务重启竞态中读取到上一轮投屏码。新增 `screencast.service.d/pairing.conf`，在服务启动前删除旧 runtime code；SVG renderer 最多等待 20 秒新码生成；部署脚本会等待 HTTPS 健康检查通过后才重启待机服务。
- 显示问题排查：一次真实 WSS 会话已完成 H.264、MPP 解码和管线链接，但 HDMI 只露出 shell cursor；DRM 显示 plane 未绑定 framebuffer。MPP 输出为 NV12，待机页面在同一 plane 的 RGB 输出正常，因此 receiver 现在默认在最终 scanout 前强制 `BGRx`；硬解保留，后续可用 RGA 取代这一步 CPU 转换。
- 隔离验证：动态 `BGRx → KMS` 和 `H.264(x264) → MPP → BGRx → KMS` 均在 HDMI 实机可见，故 KMS 与 MPP 均可用。真实 WebRTC H.264 日志显示 `is_avcC=1`，只接受序列头而未实际显示帧；接收器改为在 `h264parse/h265parse` 后强制 `stream-format=byte-stream,alignment=au`，使用已验证的 MPP Annex-B 输入路径，待重新投屏复验。
- A/B 开关：新增 `SCREENCAST_VIDEO_DECODER=auto|hardware|software`。当前准备以 `software` 做一次仅替换解码器的实机对照；该开关用于定位浏览器 H.264/Mpp 兼容性，不作为最终低延迟配置。
- A/B 结果：`software` 解码下真实浏览器 WebRTC 画面成功出现在 HDMI，延迟可接受，确认黑屏根因是 MPP 与浏览器 H.264 的兼容性，而不是网络/信令/KMS。初次输出出现发灰、混入底层 shell：plane 71 是预乘 alpha overlay，`BGRx` 未提供有效 alpha。scanout 格式改为 `ARGB`（alpha 255），待实际画质复验；递归画面则是“投整个屏幕且屏幕上含发送页”的正常镜像反馈，不是编码失真。
- 画质根因：软件解码日志出现 `reference frames exceeds max`、`decode_slice_header error` 和 `no frame`。此前为追求低延迟把 `rtpjitterbuffer` 设为 20ms 且 `drop-on-latency=true`，会丢弃压缩 H.264 RTP 包并破坏整个 GOP。已改为 80ms、`drop-on-latency=false`；仅允许在解码后的 raw-frame queue 丢弃过期帧。先以软件解码验证完整画质，再回到 MPP 兼容性优化。
- 格式复验：BSP 对 `ARGB` 的 KMS caps 虽宣称可用，但经 kmssink 实测没有 scanout，故回退已实机可见的 `BGRx`；后续通过 plane 属性关闭混合或选择更合适的 overlay plane 解决色彩，而不再以 ARGB 作为默认。
- 当前软件 A/B 的资源采样：真实浏览器流约 `1108×718`，`hdmi_receiver.py` 占约 82% CPU，其中渲染链线程约 55%、RTP jitterbuffer 约 23%。因此它只能作为“能否正确显示”的兼容性基线，无法同时满足全屏 2K 清晰度与流畅度；恢复 MPP 硬解是性能验收前提。
- 质量测试修正：发送页默认不再显示本地 `<video>` 预览（可用 `?preview=1` 显式打开）。整屏采集包含该预览会形成递归编码画面，导致每一层都更模糊、卡顿；该现象不能用于评估端到端画质。发送页优先把浏览器提供的 H.264 Constrained Baseline codec 放到 SDP 偏好首位，以提高 RK MPP 对浏览器流的兼容性。
- 性能瓶颈定位：在 MPP 已选中的实机流中，MPP 解码线程低于 1% CPU，但 `render-q` 线程约 93% CPU；根因是为绕开早期黑屏而强制的 `NV12 → BGRx` CPU `videoconvert`。KMS overlay plane 71 的实际格式列表包含 `NV12`，因此接收器新增 `SCREENCAST_RENDER_FORMAT=native` 零拷贝分支（MPP NV12 直连 kmssink），先作实机显示/性能验证；若 BSP 仍黑屏，保留 BGRx 作为已验证可见的回退。
- 零拷贝实测：实际 HDMI 已正常出画，延迟与帧率均改善；媒体线程总计约 3–4% CPU，证明 MPP→NV12→KMS 已消除 BGRx 转换瓶颈。剩余“切换窗口时短暂发糊/掉帧”归因于浏览器此前 `maintain-framerate` 的自适应降分辨率策略。发送端改为 `contentHint=detail`、`maintain-resolution`、720p 上限 60fps 和 14 Mbps；取舍是网络不足时允许少量丢帧以换取界面/文字不被降清晰度。
- 分辨率产品决策：720p 不再作为默认。发送页提供可见档位，默认 `2K 清晰档`（请求/上限 `2560×1440@30fps`、30 Mbps），另有 `1080P 平衡档`（`1920×1080@30fps`、18 Mbps）和弱网 `720P 实时档`（`1280×720@60fps`、14 Mbps）。连接日志必须报告浏览器 `getSettings()` 的实际宽高和帧率；浏览器不能凭约束凭空放大低分辨率输入，因此该日志是验证“输入对齐”的依据。
- 掉帧诊断收敛：用户确认 720p 与 2K 都有严重掉帧/运动模糊，不能再把问题归因于分辨率设置。新增发送端每 3 秒采集 WebRTC `outbound-rtp` 与 `remote-inbound-rtp`：实际 fps、发送 kbps、编码/发送帧数、接收端回报的 UDP 丢包、quality limitation reason 和 RTT；通过已认证 WSS 信令仅发送该小型统计并记入板端 journal。下一步须根据这组数据区分链路丢包与浏览器编码限速后再改变媒体管线。
- 首轮发送统计：2K 实际采集 `2560×1440@30fps`；链路 RTT 约 2–4ms、RTCP 回报 UDP 丢包为 0。发送 fps 在画面稳定后可达 29–30，但实时码率多数仅约 0.6–1.2 Mbps、运动时短时峰值约 4.8 Mbps，远低于 30 Mbps 上限；并非板端 CPU 或网络丢包。此前 `contentHint=detail + maintain-resolution` 会引导 Chrome 偏向静态清晰度/合帧，改为 `contentHint=motion + maintain-framerate`，并显式报告 `setParameters` 是否被浏览器接受；同时在页面显示浏览器提供的 H.264 fmtp/profile，供下一步确认 profile/level 限制。
- iOS 信任流程：新增 `/api/device/ios-ca.mobileconfig`，动态生成只含设备公开根 CA 的 iOS 配置描述文件（不含私钥）。iPhone 下载后仍必须在“设置 → 通用 → 关于本机 → 证书信任设置”开启该 CA 的完全信任；这符合 Apple 的手动证书信任行为。
- 显示链掉帧诊断：在 `mppvideodec` 源 pad 与 `kmssink` sink pad 增加无队列的 3 秒 FrameStats 计数（decoded/presented fps）。下一次实机运动测试可判定帧是否在 MPP 前被限制、在 render queue 被丢弃，或已送达 kmssink 而仍表现为显示节奏问题；在该数据出现前不盲目改动网络/分辨率参数。
- 发送端回归结论：运动优先下仍有严重掉帧，统计明确为 `qualityLimitationReason=bandwidth`，实际仅约 0.2–1 Mbps，RTT 2–3ms、丢包 0。推断是旧版 GStreamer WebRTC 接收端未向 Chromium 提供可用的初始带宽估计，Chrome 自行将 H.264 码率压低。发送页在所有协商 H.264 fmtp 上加入 Chromium 局域网提示 `x-google-min/start/max-bitrate`（按档位计算；2K 为约 10.5/19.5/30 Mbps），但仍保留 RTCP 自适应回退；下一轮验收检查实际 kbps 是否抬升及 `quality_limit` 是否解除。
- 深入回归证据：发送端 SDP 提示未解除 `quality_limit=bandwidth`；MPP 日志证明 Chrome 在同一会话内把编码分辨率从约 `2216×1438` 降至 `1662×1076`、再降至 `1108×718`，这正是动态画面模糊的直接原因。不能归咎于网络丢包（仍为 0）。提示改为在 `hdmi_receiver.py` 发送给 Chrome 的 SDP **Answer** 中注入；若该 A/B 仍失败，根因收敛为 GStreamer 1.16 的接收端带宽反馈能力不足，需升级/替换 WebRTC transport，而非继续修改捕获分辨率。
- HDMI 背景收敛：视频使用 KMS overlay plane 71；试图由第二个 `kmssink` 占用 primary plane 57 作为黑色遮罩不可靠（DRM master/主平面仍由 fbcon 持有），已撤回。改为显示专用虚拟终端：`screencast-display-console.service` 将 HDMI 前台固定到无 getty 的 tty2 并清空它；`configure_display_console.sh` 将 Orange Pi 启动参数设为 `console=serial`，从下一次重启起完全不把内核控制台投到 HDMI。SSH 与 ttyS2 串口维护通道保留。回滚可恢复 `/boot/orangepiEnv.txt.screencast-backup` 后重启。
- AP 首轮实测：投屏清晰度可接受，但相较 Ethernet 增加延迟和动态掉帧。板端排查确认当前 AP 被固定为 `2.4 GHz / channel 1 / 20 MHz`，单流实际能力约 72 Mbps；无线芯片为 Broadcom `wl`，`iw phy` 显示 AP 支持 5 GHz 非 DFS 信道 36/40/44/48，单流 VHT 理论约 433 Mbps。`configure_ap.sh` 默认改为 5 GHz channel 36；2.4 GHz-only 设备可显式传入 `AP_BAND=bg AP_CHANNEL=1`。另：AP 的 NAT、IP forwarding、FORWARD 规则正确，但板端 Ethernet 默认网关 `192.168.1.1` 不可达、板端自身不能访问 `1.1.1.1`，所以 AP 客户端不能上网属于缺失真实上行而非转发代码问题。
- 待机页产品化：完整网页 `frontend/standby.html` 已存在，但板端缺少稳定的 kiosk 浏览器。实机验证 Weston DRM 可在 tty2 接管 HDMI；Cog/WPE 0.4 在该 BSP EGL 路径段错误，Firefox 136 在 Weston 8 kiosk 全屏触发 Wayland `xdg_surface buffer does not match configured state`，两者均不适合当前产品路径。SVG/KMS fallback 因而升级为与网页相同的信息结构和视觉语言（品牌栏、氛围背景、三步引导、Device Pulse、Wi-Fi/二维码/投屏码卡片），保持无浏览器、无网络、开机可用。网页继续作为管理/开发入口；待未来升级图形栈后再启用 `SCREENCAST_STANDBY_MODE=html`。
- 手机端调研结论：不走手机浏览器 `getDisplayMedia()`；手机整机投屏必须有原生发送端。Android 使用 `MediaProjection`→`VirtualDisplay`→libwebrtc H.264 视频轨，Android 10+/14+ 需用户授权与 `mediaProjection` 类型前台服务；可直接复用当前 WSS 配对、offer/answer/ICE 信令以及 RK MPP→KMS 接收链。iOS 使用 ReplayKit 的系统广播/扩展采集 `CMSampleBuffer`，再交给 libwebrtc；此路径需要 Apple 开发者签名与真机 POC，且当前 Apple 文档中部分 BroadcastSampleHandler 接口标为 deprecated，不能在验证前承诺交付。原生客户端的最小后端改动是增加无浏览器 Origin 的 native WSS 通道，同时通过二维码设备指纹/证书 pinning + 现有投屏码做认证；不得直接放宽浏览器 Origin 校验。首个实现目标：Android 720p30、无系统音频、二维码发现/配对、横竖屏切换，验通后再做 iOS 与音频。
- AirPlay 边界：iPhone 系统级“屏幕镜像”要求板端实现 AirPlay Receiver 协议，不能复用现有网页/WebRTC sender；Apple 当前公开框架主要描述 App 内向 AirPlay/第三方路由发送媒体，未提供可直接部署到 Linux/RK3588 的通用 AirPlay Receiver SDK。RK3588 的 H.264 MPP 解码能力不是障碍，协议发现、配对/FairPlay 兼容与产品授权才是风险。产品策略：将开源 AirPlay receiver（如 UxPlay）作为隔离 POC/可选兼容模式评估，不作为毕设核心链路或交付承诺；稳定的 iPhone 全屏投屏主路径仍是原生 iOS App + ReplayKit + WebRTC。若接入 AirPlay，必须进入统一 display arbiter，避免与 WebRTC 会话同时争抢 HDMI plane。
- AirPlay POC 难度评估（2026-09）：候选 UxPlay 可用自定义 GStreamer video sink/decoder，适合尝试 `H.264 → mppvideodec → NV12 → kmssink plane 71`。板端已具备 Avahi mDNS、GStreamer、`h264parse`、`kmssink`、AAC 软件解码和 5 GHz AP；仅缺 `libavahi-compat-libdnssd-dev`、`libplist-dev` 两个构建依赖，且当前交互 shell 未加载 service 专用 MPP plugin path（需为 AirPlay service 注入）。HDMI 音频 sink 当前未安装，视频 POC 应先不含音频。预估：出图 POC 2–4 个有效开发日；接入显示仲裁、休眠/断连恢复、密码/配对、iOS 机型回归 1–2 周；达到产品级兼容/安全/维护 3–6 周以上。关键风险：UxPlay 为 GPL 开源兼容实现、Apple DRM 内容无法镜像、AirPlay 协议更新带来回归；仅作为可选模式，不替代原生 iOS 发送端。

### 2026-09-01 — AirPlay 接收 POC 已构建（待 iPhone 真机发现/出图验收）

- 实现边界：新建独立 `screencast-airplay-poc.service`，不修改稳定 WebRTC 接收服务；默认不启用。它启动时与 `screencast-standby.service` 互斥并占用 KMS plane 71，停止后恢复待机页。因此 POC 阶段不能和 WebRTC HDMI 会话并发，统一 display arbiter 留待后续集成。
- 接收器：UxPlay 1.74（上游提交 `aec205d49302df8d4eb291b9e927ed428b2d0166`）在 Orange Pi 5 Pro 上实际编译成功；默认使用其内置 minimal mDNS responder（Avahi/dns-sd 版本保留作回退），请求 `2560x1440@30`、H.264 `mppvideodec` 与 `kmssink plane-id=71 sync=false`，并以 `-as 0` 明确关闭音频，先收敛视频链路。
- BSP 兼容处理：Ubuntu 20.04 的 `libplist` 2.1 pkg-config 模块名称为 `libplist`，而 UxPlay 的 2.1 特性检测只查询 `libplist-2.0`，会错误使用旧 API 并编译失败。`install_airplay_poc.sh` 对上游构建目录应用名称兼容补丁，并保留 `libplist-2.0` fallback；该脚本还固定构建依赖与 upstream revision，供后续复现。
- 板端已安装二进制至 `/opt/screencast/vendor/uxplay/bin/uxplay`，10 秒空载启动实测完成 socket 初始化、使用系统 MAC 注册、干净退出；MPP plugin 路径在服务单元中独立注入。systemd 单元已启动且 mDNS 自查发现 `_airplay._tcp.local` 的 `RK-Cast`。双网卡地址验证：用 AP 接口浏览时该记录解析为 `192.168.50.1`，用 Ethernet 接口浏览时解析为 `192.168.1.109`，因此不会把 AP 客户端错误导向有线地址。首次 iPhone 测试时已捕获 AP 上的 iPhone mDNS 查询与板端响应，但 iOS 仍未显示接收器；因此切换为 UxPlay 内置 mDNS responder 复测，旧 Avahi 构建保留为 `uxplay-avahi`。复测后 iPhone 已发现并发起真实 AirPlay 镜像；板端日志确认 MPP H.264 硬解开始处理竖屏 `662×1440` 流。仍需用户确认 HDMI 实际出画，并做清晰度、帧率、延迟与断连恢复验收。
- 运维：`scripts/remote_service.sh airplay-start|airplay-stop|airplay-status`；若板端需要重建可用 `airplay-install`（需板端可访问 GitHub）。
- 首次 iPhone 实机性能：控制中心发现及连接成功，MPP 日志确认硬解输入；但实际画面为分钟级延迟、帧率不足。实际 UxPlay pipeline 默认在 `mppvideodec` 后插入两次 `videoconvert`（含强制 RGB/sRGB 色彩往返）与 `videoscale`，且缓冲需要专门控制。初版错误地在 H.264 parser 前将 queue 设为 `leaky=downstream`，实机日志出现 `h264parse: No valid frames found before end of stream`：AirPlay 单个输入 buffer 不保证是完整参考帧，不能在压缩码流层丢弃。修正策略：恢复完整压缩码流；只在 `mppvideodec` **之后**的 raw-frame queue 保留两帧并丢弃陈旧帧；服务保持可见的 RGB 输出、请求/允许 60fps。待立即实机复验。
- AirPlay 重连诊断（2026-09）：iPhone 在实际重连会话中上报 `encoderCurrentFPS=60`、`sinkOverflowDropFPS=0`、`encoderQueueDropFPS=0`、`encoderDropFPS=0`、`queuedFramesAvg=0`、近零 `lossAvg`，RTT 约 12–15ms；因此延迟/卡顿不在手机编码队列或 AP 传输。当前可见路径仍为 `mppvideodec → raw-frame leaky queue → videoconvert → RGB/sRGB → videoconvert → videoscale → kmssink`，优先验证移除 RGB 往返的原生 NV12 输出。2026-09-01 已将 POC 服务暂改为 `RK-Cast-Native`，追加 `-srgb no -vc identity`；保留原二进制及服务历史参数，若黑屏即可回退。
- Miracast POC（2026-09）：小米系统的“投屏/无线显示”目标协议为 Miracast（Wi‑Fi Direct + WFD RTSP），与 AirPlay/WebRTC 是独立接收器。RK3588 `wlan0` 已确认支持 `P2P-device/P2P-GO`，成功编译并启动 MiracleCast（上游 `albfan/miraclecast` 提交 `0b7f1f1f6586dc65ff480f3cda5c2170a70aa020`）。运行时必须由 MiracleCast 独占 `wlan0`，因此独立服务会停止 NetworkManager/wpa_supplicant（Ethernet 管理不受影响），停止后自动恢复它们、AP 与待机页。显示播放器为 `RTP/MPEG-TS → h264parse → mppvideodec → NV12 → kmssink plane 71`，仅在解码后保留两帧以限制延迟；Miracast POC 默认不启用。首次启动的 D-Bus `-13` 是新策略未加载，执行 `systemctl reload dbus.service` 后，`miracle-wifid`、专用 wpa_supplicant 与 sinkctl 已正常运行，友好名称为 `RK-Screencast`。待用小米真机从系统投屏入口发现、连接并验证媒体协商。
- Miracast POC 复盘：手机已能发现 `RK-Screencast`，但首次连接失败后板端 Ethernet 上的 SSH 出现握手前断连；重启并重新配置网卡后，`enP4p65s0`、`wlan0/RK-Screencast` AP 和待机页均恢复。初版 service 停止了整个 NetworkManager，虽然仅意图释放 WLAN，却会扰动 Ethernet 管理通道；已改为只对 `wlan0` 执行 `nmcli disconnect`/`managed no`，保留 NetworkManager 对 Ethernet 的管理，停止时显式 `managed yes` 并重新拉起 `RK-Screencast` AP；移除失败自动重启，防止反复切换网卡。下一轮仅在此隔离恢复机制确认后进行连接协商。

### 2026-09-01 — 产品控制层第一阶段：显示仲裁、网络总览、性能验收

- HDMI 仲裁：新增与硬件无关的 `backend/display_arbiter.py`。WebRTC、AirPlay、Miracast 可以分别被发现，但物理 HDMI plane 同一时刻只允许一个 `source + session_id` 持有租约。WebRTC 的真实自动启动、停止与断连路径已接入该租约；当 HDMI 已声明给 AirPlay/Miracast 时，会明确向 WebRTC sender 返回 `display_busy:<source>`，而不是悄悄覆盖画面。
- 运行接口：新增 `GET /api/product/status`，一次返回当前网络拓扑、HDMI 租约、设备 runtime、性能验收结果及三个协议的产品边界。新增仅本机可调用的 `POST /api/display/claim` 与 `POST /api/display/release`，供未来 AirPlay/Miracast service wrapper 在启动媒体管线前声明/释放 HDMI；这两个接口**不**会擅自启动或停止外部媒体服务。
- 质量指标：发送端已有的 `sender_stats` 被接入 `DeviceRuntime`，记录 fps、kbps、帧编码/发送数、RTCP 丢包、quality limitation 与 RTT。验收暂定为 `>=25fps`、丢包 `<3%`；状态为 `pass/investigate/awaiting_stream`。端到端时延仍需用摄像机或时间戳试验，不能把 WebRTC 统计代替为真实延迟。
- 待机页：`frontend/standby.js` 轮询产品状态；存在流统计时，展示 fps、码率和稳定性结论，存在 HDMI 租约时显示当前输出协议，便于现场演示与定位问题。
- 验证：本次范围 pytest 18 项通过；`compileall`、shell 语法和 diff 检查通过。全套 pytest 有 1 项既存失败：`tests/test_sender_dev.py` 仍断言 `hdmi_receiver.py` 包含已撤回的 `KMS black mask started` 日志，而当前基线实现并不存在该字符串；不要为满足断言把失效的 primary-plane 遮罩逻辑重新塞回媒体管线。

### 2026-09-01 — AirPlay 服务恢复

- 现象：AirPlay 接收器不可用时，根因是 `screencast-airplay-poc.service` 处于 `inactive (dead)`；并非 UxPlay 媒体管线报错。板端还提示其 systemd unit 文件已变更但未 reload。
- 处理：已执行 `sudo systemctl daemon-reload` 和 `sudo systemctl start screencast-airplay-poc.service`。服务目前 active，UxPlay 1.74 已初始化 server socket，并广播 AirPlay Features `0x527FFEE6`；Avahi 同时 active。当前接收器展示名称为 `RK-Cast-Native`。
- 注意：该 POC 单元仍是 disabled，板子重启后不会自行启动；这是为了避免它和 WebRTC 竞争 KMS plane 71。后续应由 display arbiter wrapper 负责显式模式切换，再决定是否改为产品级开机策略。
