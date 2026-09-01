# 测试指南

## 无硬件可行性测试（当前自动化基线）

该测试层不要求 RK3588、GStreamer、显示器或正在运行的后端服务。

### 首次初始化

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
```

### 运行测试

```bash
.venv/bin/python -m pytest -q
```

### 浏览器实用性测试

```bash
.venv/bin/python tools/run_mock_server.py
```

然后访问：

```text
http://127.0.0.1:8090/p2p-sender.html?testMedia=1
```

`testMedia=1`使用Canvas生成30fps测试视频流，不申请屏幕捕获权限。它只用于验证浏览器MediaStream、RTCPeerConnection、WebSocket、Session和MockReceiver控制链；不替代真实屏幕捕获及媒体接收测试。

#### 浏览器到浏览器P2P验证

1. 打开发送端：`http://127.0.0.1:8090/p2p-sender.html?testMedia=1`。
2. 点击“开始投屏”，复制页面显示的 `p2p_...` 会话ID。
3. 新标签打开：`http://127.0.0.1:8090/p2p-view.html`。
4. 输入会话ID并点击“连接”。
5. 验证发送端和viewer的ICE/Connection状态均到 `connected`。
6. 验证viewer状态为“播放中”，画面中的计时器持续变化。
7. 发送端点击“停止”，验证viewer显示“发送端已停止”并隐藏视频。

该流程验证真实的浏览器WebRTC Offer/Answer、双向ICE和远端视频播放；MockReceiver只负责同步验证控制层生命周期。

当前自动化测试覆盖：

- MockReceiver 正常生命周期。
- Receiver 故障注入。
- 重复会话拒绝。
- ReceiverSupervisor 单活跃会话切换和资源回收。
- 正式 `/ws` Offer 驱动 MockReceiver 到 `PLAYING`，sender断开后到 `STOPPED`。
- short-format Offer、Answer 和双向 ICE 中继。
- viewer 加入不存在的房间。
- viewer 晚加入时缓存 ICE 的重放。
- sender 断开后的通知和房间清理。
- sender 主动停止后的连接角色解除和房间清理。
- DesktopGStreamerReceiver 在缺少系统依赖时的失败状态和原因。
- 整机状态机随 MockReceiver 完成 `ready → connecting → casting → ready` 转换。
- 会话数、播放数、完成数、失败数和首帧耗时指标累计。
- 温度、CPU、丢包和丢帧输入对应的 1080p/720p 降级建议。

整机运行状态与指标：

```text
GET /api/device/runtime
```

在无板环境可注入遥测数据验证降级决策。当前接口只返回建议，不会自动修改媒体管线：

```bash
curl -X POST http://127.0.0.1:8090/api/device/telemetry \
  -H 'Content-Type: application/json' \
  -d '{"temperature_c": 86, "cpu_percent": 70, "packet_loss_percent": 1}'
```

`tests/` 是新的自动化测试目录；原 `test/` 目录中的脚本属于需要手动启动服务的历史检查脚本，暂不作为 pytest 默认测试集。

## 后续测试层级

1. 无硬件：MockReceiver + aiohttp 信令集成测试。
2. 桌面媒体：GStreamer 软件解码 + `fakesink`/窗口输出。
3. RK3588：MPP、DRM/KMS、HDMI、长稳和性能测试。

当前桌面GStreamer环境已安装到用户目录 `/Users/hhz/hb`（Apple Silicon），项目虚拟环境已安装 PyGObject/Pycairo。运行诊断前需要让 GI typelib、动态库和插件路径可见：

```bash
export PATH=/Users/hhz/hb/bin:$PATH
export GI_TYPELIB_PATH=/Users/hhz/hb/lib/girepository-1.0
export DYLD_FALLBACK_LIBRARY_PATH=/Users/hhz/hb/lib:/Users/hhz/hb/opt/libffi/lib
export GST_PLUGIN_SYSTEM_PATH_1_0=/Users/hhz/hb/lib/gstreamer-1.0
export GST_PLUGIN_PATH=/Users/hhz/hb/lib/gstreamer-1.0
export GST_REGISTRY=/tmp/gst-registry-wireless.bin
```

可重复运行以下诊断；返回码为0表示已具备无界面桌面媒体测试条件：

```bash
.venv/bin/python tools/check_desktop_media.py
```

诊断要求GObject Introspection可加载 `Gst`、`GstWebRTC`、`GstSdp`，并检查 `webrtcbin`、libnice、H.264 depay/parser/decoder、视频转换以及 `fakesink`。窗口输出插件是可选项，不阻塞无界面测试。当前诊断结果为 `READY`。

桌面 backend 服务入口：

```bash
.venv/bin/python tools/run_desktop_server.py --port 8091
```

它使用 `DesktopGStreamerReceiver` 启动独立 GStreamer worker；worker 完成浏览器 Offer/Answer、ICE 和 H.264 解码，视频输出到 `fakesink`。

---

# 历史功能测试清单

## 核心功能测试

### ✅ 发送端功能
- [x] 页面正常加载
- [x] 设备自动发现UI
- [x] 屏幕共享权限请求
- [x] 视频预览显示
- [x] 音频轨道检测
- [x] WebSocket 连接
- [x] ICE 候选交换
- [x] SDP 协商
- [x] 连接状态显示
- [x] 会话信息显示

### ✅ 接收端功能  
- [x] HTTP 服务运行
- [x] WHEP 端点响应
- [x] WebSocket 端点运行
- [x] 设备信息API
- [x] 健康检查API
- [x] mDNS 服务广播
- [x] 终端 WebSocket 支持
- [x] 静态文件服务

### 🔄 需要验证的功能
- [ ] 实际投屏连接（需要两台设备）
- [ ] 音视频同步
- [ ] 多画面显示
- [ ] 断线重连（需要模拟断网）
- [ ] 错误提示对话框
- [ ] 设备自动发现（需要 mDNS）

## 演示流程验证

```
1. 打开发送端页面
   → 页面正常显示
   → 自动搜索设备
   → 显示设备列表

2. 点击"开始投屏"
   → 弹出屏幕共享选择
   → 选择屏幕/标签页
   → 开始预览

3. 连接建立
   → WebSocket 连接成功
   → SDP 协商完成
   → ICE 连接建立
   → 状态显示"投屏中"

4. 投屏进行中
   → 视频正常传输
   → 音频正常（如果启用）
   → 会话信息正常显示

5. 断开连接
   → 停止按钮正常工作
   → 资源正确释放
   → 状态恢复到"等待开始"
```

## 技术栈验证

### 后端
- ✅ aiohttp HTTP 服务器
- ✅ WebSocket 信令
- ✅ GStreamer webrtcbin
- ✅ 硬件加速支持
- ✅ mDNS 服务广播
- ✅ 模块化架构

### 前端
- ✅ 原生 WebRTC API
- ✅ WebSocket 客户端
- ✅ 错误处理系统
- ✅ 响应式UI
- ✅ 实时日志显示
- ✅ 设备发现UI

## 已知限制

1. **mDNS 功能** - 需要安装 zeroconf 库
   ```bash
   pip install zeroconf
   ```

2. **跨子网连接** - 可能需要配置路由器

3. **音频同步** - 需要实际测试验证

4. **多画面** - 代码已实现，需要验证

## 下一步计划

1. 安装 zeroconf 验证 mDNS
2. 找两台设备测试实际投屏
3. 验证音频同步
4. 测试多路并发
5. 长时间稳定性测试

## 真实电脑屏幕测试（推荐）

真实屏幕采集需要安全上下文。正式流程直接使用设备的可信 HTTPS 页面；页面会同源连接设备的 WSS：

```bash
open https://192.168.1.109:8080/p2p-sender.html
```

首次使用前需把项目 `.local-certs/ca.pem` 导入发送电脑的受信任根证书库；这是一次性操作。随后直接打开 `https://192.168.1.109:8080/p2p-sender.html`，浏览器可以采集屏幕，页面也会同源连接 `wss://192.168.1.109:8080/ws`。

### 以太网投屏验证（不切换笔记本 Wi-Fi）

笔记本保留 Wi-Fi 上网，使用另一块网卡/USB 网卡通过网线连接板子所在的交换机或路由器。当前板端以太网地址为 `192.168.1.109`，不要把这里的以太网地址替换成 AP 地址 `192.168.50.1`。

先确认链路：

```bash
curl -k https://192.168.1.109:8080/health
```

在浏览器直接打开 `https://192.168.1.109:8080/p2p-sender.html`。页面会自动使用同源的 `wss://192.168.1.109:8080/ws`；不要手动填写 WebSocket 地址。在页面填写 HDMI 待机画面显示的 8 位投屏码，再点击“开始投屏”。

用 Chrome/Edge 打开脚本输出的 `Real screen` 地址，点击“开始投屏”，选择“整个屏幕”。预期页面日志依次出现 `WS 已连接`、`ICE state: connected`、`P2P 连接成功`；板端 HDMI 显示画面。停止后检查：

```bash
curl -k https://192.168.1.109:8080/api/device/runtime
```

应回到 `"state": "ready"`，且 `active_session_id` 为 `null`。端口 `8081` 只绑定在 RK3588 的 `127.0.0.1`，供 HDMI receiver 使用；局域网客户端不能也不应再连接它。

### AP 局域网投屏验证

板端 AP 使用 NetworkManager 管理，配置脚本是幂等的。板端仍通过有线 SSH
可访问时，在本机执行：

```bash
scripts/remote_service.sh ap-setup
```

默认网络参数：

- SSID：`RK-Screencast`
- 密码：`RKcast2026`
- 网关：`192.168.50.1`
- DHCP：`192.168.50.10`–`192.168.50.254`
- 投屏信令：`wss://192.168.50.1:8080/ws`

然后按以下顺序验证：

1. 保持板子通电，确认 HDMI 待机页显示 AP SSID、密码、HTTPS 地址和 8 位投屏码。
2. 在笔记本或手机的 Wi-Fi 中连接 `RK-Screencast`，等待获取 `192.168.50.x` 地址。
3. 首次使用时，把设备对应的 `ca.pem` 导入系统/浏览器受信任根证书库；随后访问 `https://192.168.50.1:8080/health`。不要通过忽略证书告警来替代信任 CA。
4. 直接打开 `https://192.168.50.1:8080/p2p-sender.html`，选择整个屏幕并开始投屏；填写 HDMI 上的投屏码。不要使用 HTTP 页面，因为浏览器不会允许它采集真实屏幕。
5. 发送页日志应依次出现 `投屏码验证成功`、`ICE connected`、`P2P 连接成功`；
   HDMI 应恢复为投屏画面。
6. 停止投屏，确认 HDMI 回到待机页；板端 runtime 应回到 `ready`。
7. 可选：在 AP 客户端执行 `ping 192.168.50.1`；只有当板子 Ethernet 接入真实
   有线路由器（且板端默认网关可达）时，才应继续测试外网访问。若 Ethernet
   只是笔记本直连调试线，AP 仍可投屏，但不会自动获得互联网。

AP 与 Ethernet 使用相同的投屏协议和媒体管道，仅地址不同。当前默认 AP 为
2.4GHz/20MHz，测试延迟时要固定相同的发送分辨率和帧率，再与 Ethernet 结果比较。

### 四种网络模式

通过有线 SSH 可访问板端时，使用统一切换脚本：

```bash
# 有线局域网：关闭 AP，使用网线连接投屏器
scripts/remote_service.sh network-mode wired-lan

# 现有局域网：关闭 RK AP，保持板端加入已有连接
scripts/remote_service.sh network-mode same-lan

# 无上行的独立 AP：只保证离线局域网投屏
scripts/remote_service.sh network-mode standalone-ap

# AP + Ethernet 上行：AP 客户端同时经板端上网
scripts/remote_service.sh network-mode ap-uplink
```

`same-lan` 如果需要切换到指定的 NetworkManager Wi-Fi profile，可直接在板端
执行 `sudo UPLINK_CONNECTION='连接名' bash /tmp/configure_network_mode.sh same-lan`。
`wired-lan` 默认激活第一个 Ethernet profile；如果设备存在多个有线 profile，
可设置 `WIRED_CONNECTION='连接名'` 后执行脚本。该模式适合低延迟、稳定投屏，
发送端不需要加入 RK AP，只需与板端处于同一有线局域网。
`ap-uplink` 会检查 `wlan0` 之外是否存在默认路由；没有上行时仍会启动 AP，
但明确输出警告，不会阻止离线投屏。

### RK3588 MPP 硬解回归

MPP 插件在板端隔离安装后，先启用服务环境并验证 factory：

```bash
scripts/remote_service.sh deploy
scripts/remote_service.sh enable-mpp
ssh orangepi@192.168.1.109 \
  'sudo journalctl -u screencast -n 120 --no-pager | grep -E "Decoder selected|VIDEO PIPELINE"'
```

投屏一次 720p30 H.264 测试媒体或真实屏幕后，日志必须出现：

```text
Decoder selected: mppvideodec
VIDEO PIPELINE LINKED: H264
```

若服务无法启动或投屏失败，可立即回退到系统软件解码：

```bash
ssh orangepi@192.168.1.109 \
  'sudo rm -f /etc/systemd/system/screencast.service.d/mpp.conf && sudo systemctl daemon-reload && sudo systemctl restart screencast'
```

不要只根据 `/dev/mpp_service` 或 `gst-inspect` 判断完成；必须完成一次 WebRTC→MPP→KMS 实机播放，并使用物理计时（手机慢动作或画面时间戳）测量稳定端到端延迟。

## 无硬件媒体管道模拟

使用本机 GStreamer 运行真实的 raw 视频和 H.264 编码/解码回环，输出固定为 `fakesink`，不需要 RK3588、显示器或网络：

```bash
export PATH=/Users/hhz/hb/bin:$PATH
export GI_TYPELIB_PATH=/Users/hhz/hb/lib/girepository-1.0
export DYLD_FALLBACK_LIBRARY_PATH=/Users/hhz/hb/lib:/Users/hhz/hb/opt/libffi/lib
export GST_PLUGIN_SYSTEM_PATH_1_0=/Users/hhz/hb/lib/gstreamer-1.0
export GST_PLUGIN_PATH=/Users/hhz/hb/lib/gstreamer-1.0
.venv/bin/python tools/check_media_pipeline.py
```

该测试覆盖媒体帧产生、转换、H.264 编码、解析、软件解码和 sink 消费；不模拟 AP 或 HDMI/KMS。

## 独立待机页预览

待机页已经从 KMS 生成器中拆出，支持浏览器独立预览；`demo=1` 使用本地演示数据，不依赖板子：

```bash
.venv/bin/python tools/run_mock_server.py --port 8090
```

打开 `http://127.0.0.1:8090/standby.html?demo=1`。正式模式会轮询 `/api/device-info`、`/api/device/runtime`、`/api/system` 和 `/api/status`，显示 Wi-Fi 引导、轮播内容、CPU/内存/温度、运行时间及硬件能力。

目录职责：

- `frontend/standby.html`、`standby.css`、`standby.js`：可迁移的产品界面与数据绑定。
- `frontend/assets/standby/`：本地轮播视觉素材，不依赖 CDN。
- `backend/standby_renderers/html_kiosk.py`：可选 Chromium + cage 输出适配器。
- `backend/standby_renderers/svg_kms.py`：无浏览器时的启动/故障安全静态回退。
- `backend/standby_display.py`：systemd 兼容入口，仅负责选择 renderer。

当前 systemd 默认仍使用 SVG/KMS 回退；板端安装 Chromium/cage 后可设置 `SCREENCAST_STANDBY_MODE=html`，再验证 Wayland kiosk 与 DRM 所有权切换。
