# RK3588 HDMI 采集卡屏幕共享方案

## 背景

一块 RK3588 开发板 + HDMI 采集卡，将任意平台 A 的 HDMI 输出采集并编码，LAN 内设备通过浏览器即可观看 A 的屏幕。

## 架构

```
Platform A (HDMI out)
       │
       ▼
  HDMI 采集卡 (USB/CSI → RK3588)
       │
       ▼
  RK3588 开发板
  ┌──────────────────────────────┐
  │ capture-server (主程序)       │
  │  ├─ FFmpeg: V4L2 采集 HDMI   │
  │  ├─ RK3588 硬件 H264 编码    │
  │  ├─ HTTP Server: 提供 HLS    │
  │  └─ WebSocket: 状态/控制      │
  └──────────────────────────────┘
       │ (LAN)
       ▼
  任意浏览器 → http://<板IP>:8080
```

**核心思路：** 不用 WebRTC（需要两端都跑 JS），改用 **HLS 直播流**——开发板采集 HDMI → 硬件编码 H264 → 生成 HLS m3u8/ts 片段 → 浏览器用 hls.js 播放。架构更简单，延迟约 2-5 秒，对屏幕共享场景够用。

## 实现步骤

### 1. 新建 `capture_main.cpp` — 主采集程序

**文件：** `backend/src/capture_main.cpp`

使用 FFmpeg 打开 V4L2 设备采集 HDMI 画面，硬件编码为 H264，输出 HLS 直播流，同时启动 HTTP Server 提供文件服务。

关键流程：
- `avformat_open_input` 打开 `/dev/video0`（V4L2 设备）
- `avformat_find_stream_info` 获取视频流参数
- 编码器优先使用 RK3588 硬件编码 `h264_rkmpp`，回退到 `libx264`
- 输出 HLS 格式，每 2 秒生成一个 ts 片段，保留最近 3 个
- HTTP Server 提供静态文件服务和 API

```cpp
// 输入: V4L2
avformat_open_input(&fmt_ctx, "/dev/video0", "v4l2", nullptr);

// 编码器: RK3588 硬件（回退到 libx264）
avcodec_find_encoder_by_name("h264_rkmpp");

// 输出: HLS
avformat_alloc_output_context2(..., nullptr, "stream.m3u8", hls_dir);

// HLS 选项
av_opt_set(dict, "hls_time", "2", 0);
av_opt_set(dict, "hls_list_size", "3", 0);
av_opt_set(dict, "hls_segment_filename", "seg_%03d.ts", 0);
```

HTTP 路由：
| 路径 | 说明 |
|------|------|
| `GET /live/stream.m3u8` | HLS 播放列表 |
| `GET /live/seg_xxx.ts` | 视频片段 |
| `GET /` | 观看页面 viewer.html |
| `GET /api/status` | 采集状态 JSON |

### 2. 新建 `viewer.html` — 观看页面

**文件：** `frontend/viewer.html`

- 单页应用，只有一个全屏视频播放器
- 自动连接 `http://<当前host>/live/stream.m3u8`
- 使用已有的 hls.js 播放
- 显示连接状态、分辨率信息
- 支持全屏、低延迟模式

### 3. 修改 HTTP Server — 支持静态文件服务

**文件：** `backend/src/api/http_server.cpp`、`backend/include/http_server.h`

当前 HTTP Server 只支持 JSON API 回调，需要增加：
- 设置静态文件根目录（如 `./web`）
- 识别文件路径请求，从磁盘读取文件返回
- 设置正确的 Content-Type：
  - `.html` → `text/html`
  - `.m3u8` → `application/vnd.apple.mpegurl`
  - `.ts` → `video/mp2t`
  - `.js` / `.css` → 对应 MIME 类型
- CORS 已有，无需改动

### 4. 修改 CMakeLists.txt — 添加 capture-server 目标

**文件：** `backend/CMakeLists.txt`

```cmake
option(BUILD_CAPTURE "Build HDMI capture server" ON)

if(BUILD_CAPTURE)
    find_package(FFmpeg REQUIRED COMPONENTS avcodec avformat avutil avdevice swscale)

    add_executable(capture-server
        src/capture_main.cpp
        src/api/http_server.cpp
        src/utils/logger.cpp
    )
    target_link_libraries(capture-server
        avcodec avformat avutil avdevice swscale pthread
    )
    set_target_properties(capture-server PROPERTIES
        RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
    )
endif()
```

### 5. 新建构建脚本

**文件：** `scripts/build-capture.sh`

RK3588 上本地编译 capture-server 的脚本。

## 文件变更清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/src/capture_main.cpp` | 新建 | HDMI 采集 + HLS 编码 + HTTP 服务主程序 |
| `backend/include/http_server.h` | 修改 | 添加静态文件目录配置接口 |
| `backend/src/api/http_server.cpp` | 修改 | 支持静态文件服务（m3u8/ts/html） |
| `backend/CMakeLists.txt` | 修改 | 添加 capture-server 构建目标 |
| `frontend/viewer.html` | 新建 | LAN 观看页面（hls.js 播放） |
| `scripts/build-capture.sh` | 新建 | RK3588 编译脚本 |

## RK3588 部署依赖

```bash
# Debian/Ubuntu on RK3588
apt install build- cmake- libavdevice-dev libavcodec-dev \
    libavformat-dev libavutil-dev libswscale-dev

# Rockchip MPP (硬件编码)
apt install librockchip-mpp-dev

# 如果发行版没有 rkmpp 编码器，需要从源码编译 FFmpeg:
# https://github.com/rockchip-linux/ffmpeg-rockchip
```

## 运行方式

```bash
# RK3588 上
./capture-server --device /dev/video0 --port 8080 --hls-dir ./live

# LAN 内任意设备浏览器打开
http://<RK3588的IP>:8080
```

## 验证方式

1. macOS 上先用 USB 摄像头模拟 V4L2 采集，验证采集→编码→HLS→播放完整链路
2. 在 RK3588 上连接 HDMI 采集卡，运行 capture-server
3. LAN 内设备浏览器打开 `http://<RK3588_IP>:8080` 验证画面
