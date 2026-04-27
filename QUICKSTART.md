# 快速启动和测试指南

## 本地测试（单机）

### 1. 启动接收端服务器

```bash
cd backend
python server.py
```

服务器会显示：
```
本机 IP:        10.10.30.213
Web 界面:       http://10.10.30.213:8080
WebSocket:      ws://10.10.30.213:8081
```

### 2. 打开发送端页面

浏览器访问：`http://localhost:8080/sender.html`

### 3. 测试功能

**基础功能测试**：
- [ ] 页面正常加载，样式正确
- [ ] 设备列表显示（当前为空）
- [ ] 点击"开始投屏"，屏幕共享选择弹出
- [ ] 选择"标签页"，预览正常显示
- [ ] 控制台日志正常输出

**设备发现测试**（需要 zeroconf）：
```bash
# 安装依赖
pip install zeroconf

# 重启服务器后测试
curl http://localhost:8080/api/discover
# 应该返回设备列表
```

**错误处理测试**：
- [ ] 尝试无效的 IP 地址
- [ ] 取消屏幕共享
- [ ] 网络断开（拔网线）

## 局域网测试（两台设备）

### 设备 A：接收端（RK3588 或模拟）

```bash
# 启动服务器
cd backend
python server.py

# 记录 IP 地址
# 例如：192.168.1.100
```

### 设备 B：发送端（PC 浏览器）

```
1. 访问 http://192.168.1.100:8080/sender.html
2. 点击"开始投屏"
3. 选择屏幕/标签页
4. 查看接收端是否显示
```

## 功能验证清单

### 必须验证的核心功能
- [x] 页面加载和 UI
- [x] 屏幕共享启动
- [ ] 实际视频传输（需要两台设备）
- [ ] 音频传输（需要两台设备 + 音频设备）
- [ ] 连接状态更新
- [ ] 错误提示显示

### 可选验证的进阶功能
- [ ] 设备自动发现
- [ ] 断线重连
- [ ] 多画面切换
- [ ] 终端模式
- [ ] 配置界面

## 已知问题和解决方案

| 问题 | 解决方案 |
|------|----------|
| 页面样式异常 | 检查 CSS 加载 |
| 设备列表为空 | 正常，需要 mDNS 或手动输入 |
| 连接失败 | 检查网络和防火墙 |
| 音频无声音 | 检查系统音频输出 |
| 视频花屏 | 降低分辨率或码率 |

## 开发调试

### 查看日志

**服务器日志**：
```bash
# 查看实时日志
journalctl -u screencast -f

# 或直接运行查看输出
python server.py
```

**浏览器日志**：
- 按 F12 打开开发者工具
- 查看 Console 标签
- 查看 Network 标签

### 常用调试命令

```bash
# 检查端口占用
netstat -tlnp | grep 8080

# 检查进程
ps aux | grep server.py

# 检查 GStreamer
gst-inspect-1.0 webrtcbin

# 测试 API
curl http://localhost:8080/health
curl http://localhost:8080/api/status
curl http://localhost:8080/api/discover
```
