#!/usr/bin/env python3
"""
无线投屏接收器 - 主服务
aiohttp HTTP/WebSocket 服务 + WHEP (RFC 9372) 信令
"""

import asyncio
import json
import logging
import os
import socket
import time
from datetime import datetime
from pathlib import Path

from aiohttp import web

from config import config
from gst.hardware import hardware
from gst.receiver import StreamReceiverManager, HAS_GST
from gst.compositor import CompositorManager
from gst.audio_mixer import AudioManager

# ========================================
# 日志
# ========================================
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
logger = logging.getLogger(__name__)

# ========================================
# 路径
# ========================================
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"

# ========================================
# 全局实例
# ========================================
receiver_manager = StreamReceiverManager(config=config)
compositor = CompositorManager(config=config)
audio_manager = AudioManager(config=config)


def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "localhost"


# ========================================
# WHEP API (RFC 9372)
# ========================================
async def whep_create_session(request):
    """POST /api/sessions - 创建 WHEP 投屏会话"""
    # 检查并发上限
    max_sessions = config.max_sessions
    if receiver_manager.session_count >= max_sessions:
        return web.json_response(
            {"error": "maximum sessions reached", "max": max_sessions},
            status=429,
        )

    body = await request.json()
    sdp_offer = body.get("sdp") or body.get("offer")

    if not sdp_offer:
        return web.json_response({"error": "missing SDP offer"}, status=400)

    # 创建接收器
    receiver = await receiver_manager.create_session()

    # 创建 GStreamer 管线
    receiver.create_pipeline()

    # 设置 Offer → 生成 Answer (GLib 循环阻塞, 需要在线程中运行)
    loop = asyncio.get_event_loop()
    answer = await loop.run_in_executor(None, receiver.set_offer, sdp_offer)

    # 启动管线
    receiver.start()

    if not answer:
        return web.json_response(
            {"error": "failed to process SDP offer"},
            status=500,
        )

    return web.json_response(
        {
            "id": receiver.session_id,
            "sdp": answer,
            "status": receiver.state,
        },
        status=201,
        headers={
            "Location": f"/api/sessions/{receiver.session_id}",
            "ETag": f'"{receiver.session_id}"',
        },
    )


async def whep_patch_session(request):
    """PATCH /api/sessions/{id} - 添加 ICE candidates (trickle ICE)"""
    session_id = request.match_info["id"]
    receiver = await receiver_manager.get_session(session_id)

    if not receiver:
        return web.json_response({"error": "session not found"}, status=404)

    body = await request.json()
    candidates = body.get("candidates", [])

    for cand in candidates:
        receiver.add_ice_candidate(
            candidate=cand.get("candidate", ""),
            sdp_mid=cand.get("sdpMid", "0"),
            sdp_mline_index=cand.get("sdpMLineIndex", 0),
        )

    return web.json_response({"status": "ok"})


async def whep_delete_session(request):
    """DELETE /api/sessions/{id} - 断开会话"""
    session_id = request.match_info["id"]
    removed = await receiver_manager.remove_session(session_id)

    if not removed:
        return web.json_response({"error": "session not found"}, status=404)

    return web.json_response({"status": "removed"})


# ========================================
# 状态和控制 API
# ========================================
async def api_status(request):
    """GET /api/status - 设备状态"""
    return web.json_response({
        "hardware": hardware.capabilities,
        "compositor": compositor.get_status(),
        "audio": audio_manager.get_status(),
        "sessions": receiver_manager.get_status_list(),
        "uptime": _get_uptime(),
    })


async def api_set_layout(request):
    """PUT /api/display/layout - 切换布局"""
    body = await request.json()
    layout = body.get("layout", "auto")
    compositor.set_layout(layout)
    return web.json_response({"status": "ok", "layout": layout})


async def api_set_volume(request):
    """PUT /api/audio/master - 主音量"""
    body = await request.json()
    volume = body.get("volume", audio_manager.master_volume)
    audio_manager.set_volume(volume)
    return web.json_response({"status": "ok", "volume": audio_manager.master_volume})


async def health_check(request):
    """GET /health"""
    return web.json_response({
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "gst_available": HAS_GST,
        "sessions": receiver_manager.session_count,
    })


async def server_info(request):
    """GET /info"""
    return web.json_response({
        "server": "Wireless Display Receiver",
        "version": "3.0.0",
        "platform": hardware.summary(),
        "local_ip": get_local_ip(),
        "http_port": config.http_port,
        "ws_port": config.ws_port,
        "max_sessions": config.max_sessions,
        "gst_available": HAS_GST,
        "sessions": receiver_manager.get_status_list(),
    })


# ========================================
# WebSocket (向后兼容)
# ========================================
async def ws_handler(request):
    """WebSocket 信令端点 (兼容旧版浏览器端)"""
    ws = web.WebSocketResponse(heartbeat=30)
    await ws.prepare(request)

    client_id = id(ws)
    peer = request.remote or "unknown"
    logger.info("[WS] 客户端连接: %s from %s", client_id, peer)

    try:
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                    await handle_ws_message(ws, client_id, data)
                except json.JSONDecodeError:
                    await ws.send_json({"type": "error", "message": "invalid json"})
            elif msg.type == web.WSMsgType.ERROR:
                logger.error("[WS] 错误: %s", ws.exception())
    finally:
        await handle_ws_disconnect(ws, client_id)
        logger.info("[WS] 客户端断开: %s", client_id)

    return ws


async def handle_ws_message(ws, client_id, data):
    """处理 WebSocket 消息"""
    msg_type = data.get("type")

    if msg_type == "ping":
        await ws.send_json({"type": "pong"})
        return

    # WHEP over WebSocket (兼容模式)
    if msg_type == "offer":
        session_id = data.get("session_id")
        if not session_id:
            session_id = f"ws_{int(time.time() * 1000) % 1000000}"

        sdp_offer = data.get("sdp") or data.get("offer")
        if not sdp_offer:
            await ws.send_json({"type": "error", "message": "missing sdp"})
            return

        try:
            receiver = await receiver_manager.create_session(session_id)
            receiver.create_pipeline()
            loop = asyncio.get_event_loop()
            answer = await loop.run_in_executor(None, receiver.set_offer, sdp_offer)
            receiver.start()

            if answer:
                await ws.send_json({
                    "type": "answer",
                    "session_id": session_id,
                    "sdp": answer,
                })
            else:
                await ws.send_json({"type": "error", "message": "failed to create answer"})
        except ValueError as e:
            await ws.send_json({"type": "error", "message": str(e)})
        return

    if msg_type == "ice_candidate":
        session_id = data.get("session_id")
        if session_id:
            receiver = await receiver_manager.get_session(session_id)
            if receiver:
                receiver.add_ice_candidate(
                    candidate=data.get("candidate", ""),
                    sdp_mid=data.get("sdpMid", "0"),
                    sdp_mline_index=data.get("sdpMLineIndex", 0),
                )
        return

    if msg_type == "set_layout":
        layout = data.get("layout", "auto")
        compositor.set_layout(layout)
        await ws.send_json({"type": "layout_changed", "layout": layout})
        return

    logger.warning("[WS] 未知消息类型: %s", msg_type)


async def handle_ws_disconnect(ws, client_id):
    """清理断开连接"""
    # 查找并清理该 ws 相关的会话
    sessions = receiver_manager.get_status_list()
    for s in sessions:
        await receiver_manager.remove_session(s["session_id"])


# ========================================
# 静态文件
# ========================================
async def index_handler(request):
    """首页 → 投屏发送端"""
    sender_path = FRONTEND_DIR / "sender.html"
    if sender_path.exists():
        return web.FileResponse(sender_path)
    # 回退到旧版
    old_path = FRONTEND_DIR / "screenshare.html"
    if old_path.exists():
        return web.FileResponse(old_path)
    return web.Response(text="Frontend not found", status=404)


async def dashboard_handler(request):
    """接收端状态面板"""
    dash_path = FRONTEND_DIR / "dashboard.html"
    if dash_path.exists():
        return web.FileResponse(dash_path)
    return web.Response(text="Dashboard not found", status=404)


# ========================================
# 应用工厂
# ========================================
_start_time = time.time()


def _get_uptime():
    return int(time.time() - _start_time)


def create_app():
    app = web.Application()

    # REST API (WHEP)
    app.router.add_post("/api/sessions", whep_create_session)
    app.router.add_patch("/api/sessions/{id}", whep_patch_session)
    app.router.add_delete("/api/sessions/{id}", whep_delete_session)

    # 状态和控制
    app.router.add_get("/api/status", api_status)
    app.router.add_put("/api/display/layout", api_set_layout)
    app.router.add_put("/api/audio/master", api_set_volume)

    # 健康检查
    app.router.add_get("/health", health_check)
    app.router.add_get("/info", server_info)

    # WebSocket
    app.router.add_get("/ws", ws_handler)

    # 页面
    app.router.add_get("/", index_handler)
    app.router.add_get("/dashboard", dashboard_handler)

    # 静态文件
    app.router.add_static("/static", FRONTEND_DIR, name="static")

    # 启动/关闭钩子
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)

    return app


async def on_startup(app):
    logger.info("检测硬件能力...")
    hardware.detect()

    if not HAS_GST:
        logger.warning("GStreamer 不可用 - WebRTC 接收器将运行在模拟模式")
        logger.warning("安装方法: scripts/install-deps.sh (Linux)")

    logger.info("硬件信息:\n%s", hardware.summary())


async def on_cleanup(app):
    logger.info("关闭所有会话...")
    await receiver_manager.stop_all()


# ========================================
# 主函数
# ========================================
def main():
    local_ip = get_local_ip()
    http_port = config.http_port
    ws_port = config.ws_port

    print("")
    print("=" * 55)
    print("   Wireless Display Receiver v3.0")
    print("   (Python + GStreamer + WebRTC)")
    print("=" * 55)
    print("")
    print("[接入方式]")
    print(f"  本机 IP:        {local_ip}")
    print(f"  Web 界面:       http://{local_ip}:{http_port}")
    print(f"  WebSocket:      ws://{local_ip}:{ws_port}")
    print(f"  WHEP 端点:      http://{local_ip}:{http_port}/api/sessions")
    print(f"  状态面板:       http://{local_ip}:{http_port}/dashboard")
    print("")
    print("[硬件]")
    print(f"  GStreamer:      {'已安装' if HAS_GST else '未安装 (模拟模式)'}")
    print(f"  最大并发:       {config.max_sessions} 路")
    print("")
    print("[API]")
    print(f"  POST   /api/sessions          创建投屏会话")
    print(f"  PATCH  /api/sessions/{{id}}     添加 ICE 候选")
    print(f"  DELETE /api/sessions/{{id}}     断开会话")
    print(f"  GET    /api/status            设备状态")
    print(f"  PUT    /api/display/layout    切换布局")
    print(f"  PUT    /api/audio/master      音量控制")
    print("")
    print("按 Ctrl+C 停止")
    print("=" * 55)
    print("")

    app = create_app()
    web.run_app(app, host=config.server_host, port=http_port, print=None)


if __name__ == "__main__":
    main()
