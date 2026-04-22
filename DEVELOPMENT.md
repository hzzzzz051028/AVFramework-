# AVFramework 开发指南

## 目录

- [环境搭建](#环境搭建)
- [开发流程](#开发流程)
- [API 参考](#api-参考)
- [架构说明](#架构说明)

## 环境搭建

### 后端开发环境

**Linux (Ubuntu/Debian):**

```bash
# 安装依赖
sudo apt-get update
sudo apt-get install -y build-essential cmake pkg-config \
    libavcodec-dev libavformat-dev libavutil-dev \
    libswscale-dev libswresample-dev libssl-dev \
    nlohmann-json3-dev

# 构建项目
cd backend
mkdir build && cd build
cmake ..
make -j$(nproc)
```

**Windows (MSVC):**

```batch
# 安装 vcpkg
git clone https://github.com/Microsoft/vcpkg.git
cd vcpkg
.\bootstrap-vcpkg.bat

# 安装依赖
.\vcpkg install ffmpeg:x64-windows
.\vcpkg install openssl:x64-windows
.\vcpkg install nlohmann-json:x64-windows

# 构建项目
cd backend
mkdir build
cd build
cmake .. -DCMAKE_TOOLCHAIN_FILE=[vcpkg root]/scripts/buildsystems/vcpkg.cmake
cmake --build . --config Release
```

### 前端开发环境

```bash
cd frontend
npm install
npm run dev
```

## 开发流程

### 启动开发服务器

**后端:**

```bash
cd backend/build
./avframework
```

**前端:**

```bash
cd frontend
npm run dev
```

**Docker (一键启动):**

```bash
docker-compose up -d
```

### 调试

#### 后端调试

使用 GDB:

```bash
gdb ./avframework
(gdb) run
```

#### 前端调试

在浏览器中打开开发者工具 (F12)，所有日志都会输出到控制台。

## API 参考

### REST API

#### 获取流列表

```http
GET /api/streams
```

响应:

```json
{
  "streams": [
    {
      "id": "stream_001",
      "url": "rtmp://localhost/live/stream_001",
      "width": 1920,
      "height": 1080,
      "fps": 30,
      "active": true
    }
  ]
}
```

#### 创建流

```http
POST /api/streams
Content-Type: application/json

{
  "stream_id": "stream_001",
  "width": 1920,
  "height": 1080,
  "fps": 30
}
```

#### 开始推流

```http
POST /api/streams/{stream_id}/start
Content-Type: application/json

{
  "source_url": "rtmp://source.example.com/live/stream"
}
```

#### 停止推流

```http
POST /api/streams/{stream_id}/stop
```

#### 删除流

```http
DELETE /api/streams/{stream_id}
```

#### 转码

```http
POST /api/transcode
Content-Type: application/json

{
  "input_url": "/path/to/input.mp4",
  "output_url": "/path/to/output.m3u8",
  "output_width": 1920,
  "output_height": 1080,
  "output_fps": 30
}
```

### WebSocket 信令

#### 连接

```javascript
const ws = new WebSocket('ws://localhost:8081');
```

#### 创建会话

```json
{
  "type": "create_session"
}
```

#### 加入会话

```json
{
  "type": "join_session",
  "session_id": "sess_123456"
}
```

#### SDP Offer

```json
{
  "type": "offer",
  "session_id": "sess_123456",
  "sdp": "{\"type\":\"offer\",\"sdp\":\"...\"}"
}
```

#### SDP Answer

```json
{
  "type": "answer",
  "session_id": "sess_123456",
  "sdp": "{\"type\":\"answer\",\"sdp\":\"...\"}"
}
```

#### ICE Candidate

```json
{
  "type": "ice_candidate",
  "session_id": "sess_123456",
  "candidate": "{\"candidate\":\"...\",\"sdpMid\":\"...\",\"sdpMLineIndex\":0}"
}
```

## 架构说明

### 后端架构

```
backend/
├── src/
│   ├── core/           # 核心音视频处理
│   │   ├── av_decoder.cpp    # 解码器
│   │   ├── av_encoder.cpp    # 编码器
│   │   ├── av_processor.cpp  # 处理器 (转码/滤镜)
│   │   └── av_streamer.cpp   # 流媒体服务
│   ├── api/            # HTTP/WebSocket API
│   │   ├── http_server.cpp
│   │   └── websocket_server.cpp
│   ├── webrtc/         # WebRTC 信令
│   │   └── signaling_server.cpp
│   ├── utils/          # 工具类
│   │   ├── logger.cpp
│   │   └── config.cpp
│   └── main.cpp        # 主入口
└── include/            # 头文件
```

### 前端架构

```
frontend/
├── src/
│   ├── components/     # UI 组件
│   ├── player/         # 播放器
│   │   └── VideoPlayer.js
│   ├── webrtc/         # WebRTC 客户端
│   │   └── WebRTCClient.js
│   ├── services/       # API 调用
│   │   └── API.js
│   └── main.js         # 主入口
└── index.html
```

### 数据流

#### 播放流程

```
用户请求 → 前端播放器 → HTTP API → 流媒体服务 → HLS/DASH → 用户
```

#### 推流流程

```
推流源 → RTMP → 流媒体服务 → 编码器 → HLS/DASH → CDN
```

#### WebRTC 流程

```
客户端A → WebSocket → 信令服务器 → WebSocket ← 客户端B
    ↓                                              ↑
  P2P 连接 ←────────────────────────────────────→ P2P 连接
```

## 常见问题

### FFmpeg 相关

**问题**: 找不到 FFmpeg 库

**解决方案**:
```bash
# 检查 FFmpeg 是否安装
ffmpeg -version

# 安装 FFmpeg 开发库
sudo apt-get install libavcodec-dev libavformat-dev libavutil-dev
```

### WebSocket 连接失败

**问题**: WebSocket 无法连接

**解决方案**:
1. 检查防火墙设置
2. 确认 WebSocket 服务端口 (8081) 开放
3. 检查 CORS 配置

### HLS 播放卡顿

**问题**: HLS 播放不流畅

**解决方案**:
1. 调整 HLS 分片大小和时长
2. 增加 HTTP 缓存
3. 使用 CDN 加速
