# 🖥️ 屏幕共享系统 - 快速开始

## 📋 功能说明

一个简单的屏幕共享系统，支持：
- 📤 屏幕共享：在浏览器中共享你的屏幕
- 📥 远程观看：在另一个浏览器窗口观看共享的屏幕
- 🏠 本地运行：完全在本地运行，无需外网

## 🚀 快速启动

### 1️⃣ 编译服务器

```bash
cd backend
mkdir build && cd build

# 使用屏幕共享配置
cmake -f ../CMakeLists.screenshare.txt ..
cmake --build . --config Release
```

### 2️⃣ 启动服务器

```bash
# Windows
cd build\bin\Release
screenshare-server.exe

# 或指定端口
screenshare-server.exe --port 8081
```

### 3️⃣ 打开网页

**方式 1：直接打开**
```
在浏览器中打开: frontend/screenshare.html
```

**方式 2：使用本地服务器**
```bash
cd frontend
python -m http.server 3000
# 然后访问: http://localhost:3000/screenshare.html
```

## 📖 使用步骤

### 📤 共享屏幕（共享者）

1. 打开 `screenshare.html`
2. 确保选中"共享屏幕"模式
3. 点击"开始共享"按钮
4. 在弹出的窗口中选择要共享的屏幕/窗口/标签页
5. 点击"分享"按钮
6. 记下显示的"会话 ID"

### 📥 观看屏幕（观看者）

1. 打开同一个 `screenshare.html`（可以是新标签页）
2. 切换到"观看屏幕"模式
3. 输入共享者提供的"会话 ID"
4. 点击"连接"按钮
5. 等待连接建立

## 🛠️ 技术架构

```
┌─────────────────┐
│   浏览器 A      │  屏幕共享端
│  (共享屏幕)     │
└────────┬────────┘
         │ WebRTC
         │ getDisplayMedia()
         ↓
┌─────────────────┐
│  信令服务器      │  WebSocket:8081
│  (C++ 后端)      │
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│   浏览器 B      │  观看端
│  (观看屏幕)     │
└─────────────────┘
```

## 🔧 配置选项

### 服务器配置

```bash
# 使用默认端口 (8081)
screenshare-server.exe

# 自定义端口
screenshare-server.exe --port 9001
```

### 前端配置

在 `screenshare.html` 中修改：
```javascript
const WS_URL = 'ws://localhost:8081';  // 修改为你的服务器地址
```

## 📝 故障排除

### 问题 1：无法连接到服务器

**检查：**
- ✅ 服务器是否正在运行？
- ✅ 防火墙是否阻止了端口？
- ✅ 浏览器控制台是否有错误？

### 问题 2：屏幕共享失败

**检查：**
- ✅ 浏览器是否支持 `getDisplayMedia()`？
- ✅ 是否授予了屏幕共享权限？

### 问题 3：连接建立但看不到画面

**检查：**
- ✅ WebRTC 连接状态（查看浏览器控制台）
- ✅ ICE 候选是否成功交换

## 🌐 浏览器兼容性

| 浏览器 | 屏幕共享 | 观看 |
|--------|----------|------|
| Chrome | ✅ | ✅ |
| Edge | ✅ | ✅ |
| Firefox | ✅ | ✅ |
| Safari | ✅ | ✅ |

## 🎯 下一步改进

- [ ] 添加音频共享
- [ ] 支持多观看者
- [ ] 录制功能
- [ ] 聊天功能
- [ ] 文件传输

## 📞 获取帮助

遇到问题？查看：
- 浏览器控制台 (F12)
- 服务器终端输出
- WebSocket 连接状态
