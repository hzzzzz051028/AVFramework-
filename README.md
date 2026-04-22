# 🎬 AVFramework - 简易音视频框架

一个基于 **C++/FFmpeg** 后端 + **Web** 前端的音视频处理框架。

## 📋 功能特性

### 后端服务 (C++/FFmpeg)
- 📹 **音视频采集** - 支持摄像头、麦克风、屏幕捕获
- 🎞️ **转码处理** - 格式转换、编码、解码、滤镜处理
- 📡 **流媒体服务** - RTMP 推拉流、HLS、DASH
- 🌐 **WebRTC 支持** - 实时音视频通信
- 🔧 **HTTP API** - RESTful API 控制接口

### 前端应用 (Web)
- ▶️ **播放器** - HLS/DASH/FLV 播放器
- 📹 **录制上传** - 浏览器端录制与上传
- 🎬 **实时通信** - WebRTC 客户端
- 🎨 **管理界面** - 流管理与监控

## 🏗️ 项目结构

```
video_test/
├── backend/               # C++/FFmpeg 后端
│   ├── src/
│   │   ├── core/         # 核心音视频处理
│   │   ├── api/          # HTTP/WebSocket API
│   │   ├── webrtc/       # WebRTC 信令与处理
│   │   └── utils/        # 工具类
│   ├── include/          # 头文件
│   └── CMakeLists.txt    # 构建配置
├── frontend/              # Web 前端
│   ├── src/
│   │   ├── components/   # UI 组件
│   │   ├── player/       # 播放器
│   │   ├── webrtc/       # WebRTC 客户端
│   │   └── services/     # API 调用
│   └── package.json
├── docker/               # Docker 配置
└── scripts/              # 构建脚本
```

## 🚀 快速开始

### 环境要求

**后端:**
- C++17 或更高
- FFmpeg 5.0+ (开发库)
- CMake 3.15+
- OpenSSL

**前端:**
- Node.js 18+
- npm 或 yarn

### 后端构建

```bash
cd backend
mkdir build && cd build
cmake ..
make
./avframework
```

### 前端运行

```bash
cd frontend
npm install
npm run dev
```

### Docker 部署

```bash
docker-compose up -d
```

## 📖 API 文档

### RESTful API

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | /api/upload | 上传视频文件 |
| GET | /api/streams | 获取流列表 |
| POST | /api/transcode | 开始转码任务 |
| GET | /api/stream/{id} | 获取流信息 |

### WebSocket 信令

用于 WebRTC 通信的信令接口。

## 🔧 配置

后端配置文件: `backend/config.json`

```json
{
  "http_port": 8080,
  "websocket_port": 8081,
  "rtmp_port": 1935,
  "hls_path": "./hls",
  "temp_path": "./temp"
}
```

## 📝 License

MIT
