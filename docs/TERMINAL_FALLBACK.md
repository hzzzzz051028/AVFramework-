# 终端转发保底方案

## 方案概述

当视频投屏不可用时，可以将 PC 的终端 shell 转发到 RK3588 显示器上。

```
┌─────────────────────────────────────────────────────────────────┐
│                        正常模式                                   │
│                                                                  │
│   PC ──WebRTC视频──▶ RK3588 ──HDMI──▶ 显示器                     │
│   (整个屏幕)                                                      │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                        保底模式                                   │
│                                                                  │
│   PC ──WebSocket──▶ RK3588 ──HDMI──▶ 显示器                      │
│   (终端 shell)                                                    │
│                                                                  │
│   用户可以在 RK3588 的显示器上看到并操作 PC 的命令行！             │
└─────────────────────────────────────────────────────────────────┘
```

## 使用方法

### 方式1: 共享终端窗口 (最简单)

1. PC 上打开终端 (PowerShell/CMD/Terminal)
2. 访问 `http://<rk3588_ip>:8080`
3. 点击"开始共享"
4. 选择"**窗口**"标签
5. 选择终端窗口
6. 完成！终端显示在 RK3588 连接的显示器上

### 方式2: 终端转发服务 (推荐)

**PC 端**:
```bash
# 运行终端转发器
python tools/terminal_forwarder.py

# 输入 RK3588 IP 地址
# 终端内容将实时转发到 RK3588
```

**RK3588 端**:
```
访问 http://<rk3588_ip>:8080/terminal-view.html
```

## 技术架构

### PC 端 (terminal_forwarder.py)

```python
1. 启动本地 shell 进程 (PowerShell/bash)
2. 读取 stdout/stderr
3. 通过 WebSocket 转发到 RK3588
4. 接收 RK3588 发送的命令
5. 写入 shell stdin
```

### RK3588 端 (terminal-view.html)

```javascript
1. 建立 WebSocket 连接
2. 接收终端输出并显示
3. 支持命令输入
4. 实时滚动更新
```

## 部署说明

### RK3588 端配置

需要在 `server.py` 中添加终端 WebSocket 服务：

```python
# 添加到 server.py
async def terminal_ws_handler(request):
    """终端 WebSocket 端点"""
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    async for msg in ws:
        if msg.type == web.WSMsgType.TEXT:
            # 转发消息到已连接的终端
            pass

    return ws

# 添加路由
app.router.add_get("/ws/terminal", terminal_ws_handler)
```

### 使用场景

| 场景 | 使用方案 |
|------|----------|
| 视频投屏稳定 | 视频模式 (推荐) |
| 网络带宽不足 | 终端模式 |
| 只需命令行操作 | 终端模式 |
| 调试诊断 | 终端模式 |
| 视频编码失败 | 终端模式 |

## 终端功能

- ✅ 实时显示 shell 输出
- ✅ 支持命令输入
- ✅ 彩色输出支持
- ✅ 自动滚动
- ✅ 时间戳
- ✅ 行数限制
- ✅ 断线重连

## 示例操作

```
# 在 RK3588 显示器上看到的终端界面

[10:30:15] 系统就绪
[10:30:20] $ top
[10:30:20] PID  USER      PR  NI    VIRT    RES    SHR S  %CPU  %MEM
[10:30:20]  1   root      20   0   12345    6789    123 R  5.3   2.1
[10:30:25] $ htop
[10:30:25] ... (htop 界面)
```

## 对比

| 特性 | 视频投屏 | 终端转发 |
|------|----------|----------|
| 带宽需求 | 高 | 低 |
| 延迟 | 中 | 低 |
| 显示内容 | 整个屏幕 | 终端界面 |
| 交互能力 | 完整GUI | 命令行 |
| 适用场景 | 演示、监控 | 管理、调试 |
