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

真实屏幕采集需要安全上下文。为避免板端自签名证书影响 WSS，优先在电脑本机提供发送页：

```bash
.venv/bin/python tools/run_sender_dev.py
```

然后用 Chrome/Edge 打开脚本输出的 `Real screen` 地址。页面运行在 `localhost`，屏幕采集可用，信令通过 `ws://192.168.1.109:8081/ws` 连接板端。

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
