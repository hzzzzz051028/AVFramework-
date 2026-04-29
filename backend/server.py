#!/usr/bin/env python3
"""
无线投屏接收器 - 主服务
aiohttp HTTP/WebSocket 服务 + WHEP (RFC 9372) 信令
"""

import asyncio
import json
import logging
import os
import signal
import socket
import subprocess
import time
from datetime import datetime
from pathlib import Path

from aiohttp import web

from config import config
from gst.hardware import hardware
from gst.receiver import StreamReceiverManager, HAS_GST
from gst.compositor import CompositorManager
from gst.audio_mixer import AudioManager
from mdns_service import start_mdns, stop_mdns

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
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

# ========================================
# 全局实例
# ========================================
receiver_manager = StreamReceiverManager(config=config)
compositor = CompositorManager(config=config)
audio_manager = AudioManager(config=config)

# 终端 WebSocket 连接存储
terminal_clients = set()

# WS 客户端 → 会话 ID 映射 (用于断连时只清理该客户端的会话)
ws_sessions = {}  # client_id → set of session_ids


# ========================================
# 信令房间 (Room-based signaling)
# ========================================
class Room:
    def __init__(self, room_id):
        self.room_id = room_id
        self.sender = None          # sender 的 client_id (int)
        self.sender_fmt = "short"
        self.viewers = {}           # client_id → fmt
        self.pending_offer = {}     # fmt → msg dict
        self.pending_ice = []       # [{fmt: msg}, ...]

    def is_sender(self, client_id):
        return self.sender == client_id


rooms = {}              # room_id → Room
ws_to_client = {}       # id(ws) → client_id
client_to_ws = {}       # client_id → ws
client_to_room = {}     # client_id → room_id
_next_client_id = [0]


def _alloc_client_id():
    _next_client_id[0] += 1
    return _next_client_id[0]


def _get_client_id(ws):
    """通过 ws 对象获取 client_id"""
    return ws_to_client.get(id(ws))


def _get_ws(client_id):
    """通过 client_id 获取 ws 对象"""
    ws = client_to_ws.get(client_id)
    if ws is not None and ws.closed:
        return None
    return ws


def _register_ws(ws):
    """为新连接分配 client_id 并注册映射"""
    cid = _alloc_client_id()
    ws_to_client[id(ws)] = cid
    client_to_ws[cid] = ws
    return cid


def _unregister_ws(ws):
    """移除连接的所有映射"""
    ws_id = id(ws)
    cid = ws_to_client.pop(ws_id, None)
    if cid is not None:
        client_to_ws.pop(cid, None)
        client_to_room.pop(cid, None)
    return cid


async def _send_to(client_id, msg):
    """安全地向指定 client 发送消息"""
    ws = _get_ws(client_id)
    if ws is not None:
        try:
            await ws.send_json(msg)
            return True
        except Exception:
            return False
    return False


def get_local_ip():
    s = None
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        return ip
    except Exception:
        return "localhost"
    finally:
        if s:
            s.close()


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

    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "invalid JSON body"}, status=400)

    sdp_offer = body.get("sdp") or body.get("offer")

    if not sdp_offer:
        return web.json_response({"error": "missing SDP offer"}, status=400)

    # 创建接收器
    receiver = await receiver_manager.create_session()

    try:
        # 创建 GStreamer 管线
        receiver.create_pipeline()

        # 设置 Offer → 生成 Answer
        loop = asyncio.get_running_loop()
        answer = await loop.run_in_executor(None, receiver.set_offer, sdp_offer)

        # 启动管线
        receiver.start()

        if not answer:
            await receiver_manager.remove_session(receiver.session_id)
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
    except Exception as e:
        await receiver_manager.remove_session(receiver.session_id)
        logger.error("[WHEP] 创建会话失败: %s", e)
        return web.json_response({"error": str(e)}, status=500)


async def whep_patch_session(request):
    """PATCH /api/sessions/{id} - 添加 ICE candidates (trickle ICE)"""
    session_id = request.match_info["id"]
    receiver = await receiver_manager.get_session(session_id)

    if not receiver:
        return web.json_response({"error": "session not found"}, status=404)

    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "invalid JSON body"}, status=400)

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
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "invalid JSON body"}, status=400)
    layout = body.get("layout", "auto")
    compositor.set_layout(layout)
    return web.json_response({"status": "ok", "layout": layout})


async def api_set_volume(request):
    """PUT /api/audio/master - 主音量"""
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "invalid JSON body"}, status=400)
    volume = body.get("volume", audio_manager.master_volume)
    audio_manager.set_volume(volume)
    return web.json_response({"status": "ok", "volume": audio_manager.master_volume})


async def api_discover_devices(request):
    """GET /api/discover - 发现局域网内的投屏设备（mDNS）"""
    try:
        from mdns_service import MDNSDiscovery
        discovery = MDNSDiscovery()
        devices = await discovery.discover(timeout=2.0)

        # 转换为列表格式
        device_list = [
            {
                "id": name,
                "name": info["name"],
                "host": info["host"],
                "port": info["port"],
                "url": f"http://{info['host']}:{info['port']}",
                "properties": info.get("properties", {})
            }
            for name, info in devices.items()
        ]

        return web.json_response({"devices": device_list})
    except ImportError:
        return web.json_response({"devices": [], "error": "mDNS not available"})
    except Exception as e:
        return web.json_response({"devices": [], "error": str(e)})


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

    cid = _register_ws(ws)
    peer = request.remote or "unknown"
    print(f"[WS] 连接: cid={cid} from {peer}", flush=True)
    logger.info("[WS] 客户端连接: cid=%s from %s", cid, peer)

    try:
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                    await handle_ws_message(cid, data)
                except json.JSONDecodeError:
                    await ws.send_json({"type": "error", "message": "invalid json"})
            elif msg.type == web.WSMsgType.ERROR:
                logger.error("[WS] 错误: %s", ws.exception())
    finally:
        handle_ws_disconnect(ws, cid)
        logger.info("[WS] 客户端断开: cid=%s", cid)

    return ws


def _detect_format(data):
    """检测消息格式: 'short' (t/s/c/m/l keys) 或 'long' (type/session_id/candidate keys)"""
    if "t" in data and "type" not in data:
        return "short"
    return "long"


def _make_short(t, sid, **kw):
    msg = {"t": t, "s": sid}
    msg.update(kw)
    return msg


def _make_long(t, sid, **kw):
    msg = {"type": t, "session_id": sid}
    msg.update(kw)
    return msg


def _msg_for(fmt, t_short, t_long, sid, **kw):
    if fmt == "short":
        return _make_short(t_short, sid, **kw)
    return _make_long(t_long, sid, **kw)


async def handle_ws_message(cid, data):
    """处理 WebSocket 消息 - 同时支持 long 和 short 两种消息格式"""
    fmt = _detect_format(data)
    if fmt == "short":
        msg_type = data.get("t")
        sid_key = "s"
    else:
        msg_type = data.get("type")
        sid_key = "session_id"

    sid = data.get(sid_key, data.get("session_id", ""))
    print(f"[WS] cid={cid} msg={msg_type} fmt={fmt} sid={sid}", flush=True)

    if msg_type == "ping":
        await _send_to(cid, {"type": "pong"})
        return

    # WHEP over WebSocket (兼容模式) - 仅 long format
    if fmt == "long" and msg_type == "offer":
        session_id = data.get("session_id")
        if not session_id:
            session_id = f"ws_{int(time.time() * 1000) % 1000000}"

        sdp_offer = data.get("sdp") or data.get("offer")
        if not sdp_offer:
            await _send_to(cid, {"type": "error", "message": "missing sdp"})
            return

        try:
            receiver = await receiver_manager.create_session(session_id)
            receiver.create_pipeline()
            loop = asyncio.get_running_loop()
            answer = await loop.run_in_executor(None, receiver.set_offer, sdp_offer)
            receiver.start()

            if answer:
                ws_sessions.setdefault(cid, set()).add(session_id)
                await _send_to(cid, {"type": "answer", "session_id": session_id, "sdp": answer})
            else:
                await receiver_manager.remove_session(session_id)
                await _send_to(cid, {"type": "error", "message": "failed to create answer"})
        except ValueError as e:
            await _send_to(cid, {"type": "error", "message": str(e)})
        return

    if fmt == "long" and msg_type == "ice_candidate":
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
        await _send_to(cid, {"type": "layout_changed", "layout": layout})
        return

    # ---- 信令房间 (P2P sender ↔ viewer) ----
    if not sid:
        await _send_to(cid, _msg_for(fmt, "error", "error", "", msg="missing room_id"))
        return

    room = rooms.get(sid)

    # viewer 注册
    if msg_type in ("register_viewer", "reg"):
        if room is None or room.sender is None:
            await _send_to(cid, _msg_for(fmt, "error", "error", sid, msg="room not found or no sender"))
            return
        room.viewers[cid] = fmt
        client_to_room[cid] = sid
        # 告诉 viewer sender 的真实 IP (用于替换 mDNS candidates)
        sender_ws = _get_ws(room.sender)
        sender_ip = ""
        if sender_ws:
            r = sender_ws.remote
            sender_ip = r[0] if isinstance(r, tuple) else str(r).split(":")[0]
        print(f"[DEBUG] sender_ws={sender_ws} remote={sender_ws.remote if sender_ws else None} sender_ip={sender_ip}", flush=True)
        await _send_to(cid, _make_short("reg_ok", sid, sender_ip=sender_ip))
        # 转发缓存的 ICE candidates 给新 viewer
        for ice_pair in room.pending_ice:
            imsg = ice_pair.get(fmt)
            if imsg:
                await _send_to(cid, imsg)
        # 通知 sender 有新 viewer，让 sender 创建全新的 offer (解决重连黑屏)
        await _send_to(room.sender, _make_short("new_viewer", sid))
        print(f"[ROOM] viewer 加入: room={sid} cid={cid} viewers={len(room.viewers)}", flush=True)
        return

    # sender 发送 offer
    if msg_type in ("relay_offer", "offer") and fmt == "short":
        is_new = room is None or room.sender is None
        if room is None:
            room = Room(sid)
            rooms[sid] = room
        room.sender = cid
        room.sender_fmt = fmt
        client_to_room[cid] = sid
        # Auto-start HDMI display for new sender
        if is_new:
            asyncio.ensure_future(_auto_start_display(sid))
        sdp = data.get("sdp", "")
        offer_msgs = {
            "short": _make_short("offer", sid, sdp=sdp),
            "long": _make_long("offer", sid, sdp=sdp),
        }
        room.pending_offer = offer_msgs
        # 转发给所有在线 viewer
        for vcid, vfmt in list(room.viewers.items()):
            msg = offer_msgs.get(vfmt)
            if msg and await _send_to(vcid, msg):
                for ice_pair in room.pending_ice:
                    imsg = ice_pair.get(vfmt)
                    if imsg:
                        await _send_to(vcid, imsg)
        print(f"[ROOM] offer: room={sid} cid={cid} viewers={len(room.viewers)} sdp_len={len(sdp)}", flush=True)
        return

    # viewer 发送 answer
    if msg_type in ("relay_answer", "answer"):
        if room is None or room.sender is None:
            return
        sdp = data.get("sdp", "")
        answer_msg = _msg_for(room.sender_fmt, "answer", "answer", sid, sdp=sdp)
        await _send_to(room.sender, answer_msg)
        print(f"[ROOM] answer: room={sid} → sender={room.sender} sdp_len={len(sdp)}", flush=True)
        return

    # ICE candidate 中继
    if msg_type in ("relay_ice", "ice"):
        if room is None:
            return
        c = data.get("candidate", "") or data.get("c", "")
        m = data.get("sdpMid", "0") or data.get("m", "0")
        l = data.get("sdpMLineIndex", 0) or data.get("l", 0)
        ice_msgs = {
            "short": _make_short("ice", sid, c=c, m=m, l=l),
            "long": _make_long("ice_candidate", sid, candidate=c, sdpMid=m, sdpMLineIndex=l),
        }

        if room.is_sender(cid):
            # sender → viewers
            room.pending_ice.append(ice_msgs)
            for vcid, vfmt in list(room.viewers.items()):
                imsg = ice_msgs.get(vfmt)
                if imsg:
                    await _send_to(vcid, imsg)
        else:
            # viewer → sender
            imsg = ice_msgs.get(room.sender_fmt)
            if imsg:
                await _send_to(room.sender, imsg)
        return

    # stop / leave
    if msg_type in ("stop", "leave"):
        if room and room.is_sender(cid):
            for vcid, vfmt in list(room.viewers.items()):
                await _send_to(vcid, _msg_for(vfmt, "stopped", "stopped", sid))
            # Auto-stop HDMI display
            if _display_room_id == sid:
                asyncio.ensure_future(_stop_display())
            room.sender = None
            room.pending_offer = {}
            room.pending_ice = []
            print(f"[ROOM] sender 停止: room={sid}", flush=True)
        return

    logger.warning("[WS] 未知消息类型: %s", msg_type)


def handle_ws_disconnect(ws, cid):
    """清理断开连接"""
    # WHEP 会话清理
    session_ids = ws_sessions.pop(cid, set())
    for sid in session_ids:
        asyncio.ensure_future(receiver_manager.remove_session(sid))

    # Room 清理 - 先查 room_id 再 unregister
    room_id = client_to_room.get(cid)
    if room_id:
        room = rooms.get(room_id)
        if room is not None:
            if room.is_sender(cid):
                for vcid, vfmt in list(room.viewers.items()):
                    msg = _msg_for(vfmt, "stopped", "stopped", room_id)
                    asyncio.ensure_future(_send_to(vcid, msg))
                # Auto-stop HDMI display on sender disconnect
                if _display_room_id == room_id:
                    asyncio.ensure_future(_stop_display())
                room.sender = None
                room.pending_offer = {}
                room.pending_ice = []
                print(f"[ROOM] sender 断开: room={room_id}", flush=True)
                if not room.viewers:
                    rooms.pop(room_id, None)
            else:
                room.viewers.pop(cid, None)
                print(f"[ROOM] viewer 断开: room={room_id} cid={cid} 剩余={len(room.viewers)}", flush=True)
                if room.sender is None and not room.viewers:
                    rooms.pop(room_id, None)

    _unregister_ws(ws)


# ========================================
# 终端 WebSocket (保底方案)
# ========================================
async def terminal_ws_handler(request):
    """终端 WebSocket 端点 - 接收 PC 端转发的终端输出"""
    ws = web.WebSocketResponse(heartbeat=30)
    await ws.prepare(request)

    client_id = id(ws)
    peer = request.remote or "unknown"
    logger.info("[Terminal] 客户端连接: %s from %s", client_id, peer)

    terminal_clients.add(ws)

    try:
        # 发送欢迎消息
        await ws.send_json({
            'type': 'connected',
            'message': '终端 WebSocket 已连接',
            'timestamp': datetime.now().isoformat()
        })

        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                    logger.debug("[Terminal] 收到消息: %s", data.get('type'))

                    # 广播消息到所有其他终端客户端
                    # (支持多终端同时查看)
                    for client in terminal_clients:
                        if client != ws and not client.closed:
                            try:
                                await client.send_json(data)
                            except Exception:
                                pass

                except json.JSONDecodeError:
                    await ws.send_json({"type": "error", "message": "invalid json"})

            elif msg.type == web.WSMsgType.ERROR:
                logger.error("[Terminal] 错误: %s", ws.exception())

    finally:
        terminal_clients.discard(ws)
        logger.info("[Terminal] 客户端断开: %s", client_id)

    return ws


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


async def terminal_view_handler(request):
    """终端显示界面"""
    term_path = FRONTEND_DIR / "terminal-view.html"
    if term_path.exists():
        return web.FileResponse(term_path)
    return web.Response(text="Terminal view not found", status=404)


async def view_handler(request):
    """观看端界面"""
    view_path = FRONTEND_DIR / "view.html"
    if view_path.exists():
        return web.FileResponse(view_path)
    return web.Response(text="View page not found", status=404)


async def sender_html_handler(request):
    """发送端界面 (直接访问 sender.html)"""
    sender_path = FRONTEND_DIR / "sender.html"
    if sender_path.exists():
        return web.FileResponse(sender_path)
    return web.Response(text="Sender page not found", status=404)


async def p2p_sender_handler(request):
    """P2P 投屏端 (minimal)"""
    path = FRONTEND_DIR / "p2p-sender.html"
    if path.exists():
        return web.FileResponse(path)
    return web.Response(text="P2P sender not found", status=404)


# ========================================
# HDMI 显示管理
# ========================================
_display_process = None
_display_room_id = None


async def display_handler(request):
    """HDMI 显示页面"""
    path = FRONTEND_DIR / "display.html"
    if path.exists():
        return web.FileResponse(path)
    return web.Response(text="Display page not found", status=404)


async def api_display_start(request):
    """POST /api/display/start - 启动 HDMI 原生显示 (GStreamer webrtcbin + kmssink)"""
    global _display_process
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "invalid json"}, status=400)

    sid = body.get("session_id", "")
    if not sid:
        return web.json_response({"error": "missing session_id"}, status=400)

    await _stop_display()

    # 使用纯 HTTP 端口的 WebSocket
    ws_url = f"ws://localhost:{config.ws_port}/ws"
    script = str(Path(__file__).resolve().parent / "hdmi_receiver.py")

    try:
        log_file = open("/tmp/hdmi_receiver.log", "w")
        _display_process = subprocess.Popen(
            ["python3", script, sid, ws_url],
            stdout=log_file, stderr=log_file,
            preexec_fn=os.setpgrp,
        )
        time.sleep(2)

        if _display_process.poll() is not None:
            log_file.close()
            with open("/tmp/hdmi_receiver.log") as f:
                log_content = f.read()
            logger.error("[DISPLAY] receiver failed: %s", log_content[-500:])
            return web.json_response({"error": f"receiver failed: {log_content[-200:]}"}, status=500)

        logger.info("[DISPLAY] started pid=%d sid=%s", _display_process.pid, sid)
        return web.json_response({"status": "started", "pid": _display_process.pid, "sid": sid})
    except FileNotFoundError as e:
        return web.json_response({"error": f"{e.strerror}: python3 or hdmi_receiver.py not found"}, status=500)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


async def _stop_display():
    """停止 HDMI 显示进程"""
    global _display_process, _display_room_id

    if _display_process and _display_process.poll() is None:
        pid = _display_process.pid
        try:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            _display_process.terminate()
        try:
            _display_process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(os.getpgid(pid), signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                _display_process.kill()
            _display_process.wait()
        logger.info("[DISPLAY] stopped pid=%d room=%s", pid, _display_room_id)
    _display_process = None
    _display_room_id = None


async def _auto_start_display(sid):
    """Auto-start HDMI display when sender begins sharing."""
    global _display_process, _display_room_id

    if _display_process and _display_process.poll() is None:
        logger.info("[DISPLAY] stopping old display for new session %s", sid)
        await _stop_display()

    ws_url = f"ws://localhost:{config.ws_port}/ws"
    script = str(Path(__file__).resolve().parent / "hdmi_receiver.py")
    try:
        log_file = open("/tmp/hdmi_receiver.log", "w")
        _display_process = subprocess.Popen(
            ["python3", script, sid, ws_url],
            stdout=log_file, stderr=log_file,
            preexec_fn=os.setpgrp,
        )
        _display_room_id = sid
        logger.info("[DISPLAY] auto-started pid=%d room=%s", _display_process.pid, sid)
    except Exception as e:
        logger.error("[DISPLAY] auto-start failed: %s", e)


async def api_display_stop(request):
    """DELETE /api/display/stop - 停止 HDMI 显示"""
    await _stop_display()
    return web.json_response({"status": "stopped"})


async def api_display_status(request):
    """GET /api/display/status - 查询 HDMI 显示状态"""
    global _display_process
    if _display_process and _display_process.poll() is None:
        return web.json_response({"running": True, "pid": _display_process.pid})
    _display_process = None
    return web.json_response({"running": False})


async def p2p_view_handler(request):
    """P2P 观看端 (minimal)"""
    path = FRONTEND_DIR / "p2p-view.html"
    if path.exists():
        return web.FileResponse(path)
    return web.Response(text="P2P view not found", status=404)


async def dashboard_html_handler(request):
    """控制面板界面 (直接访问 dashboard.html)"""
    dash_path = FRONTEND_DIR / "dashboard.html"
    if dash_path.exists():
        return web.FileResponse(dash_path)
    return web.Response(text="Dashboard page not found", status=404)


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
    app.router.add_get("/api/discover", api_discover_devices)

    # 健康检查
    app.router.add_get("/health", health_check)
    app.router.add_get("/info", server_info)

    # WebSocket
    app.router.add_get("/ws", ws_handler)
    app.router.add_get("/ws/terminal", terminal_ws_handler)

    # 页面
    app.router.add_get("/", index_handler)
    app.router.add_get("/dashboard", dashboard_handler)
    app.router.add_get("/view.html", view_handler)
    app.router.add_get("/sender.html", sender_html_handler)
    app.router.add_get("/dashboard.html", dashboard_html_handler)
    app.router.add_get("/terminal-view.html", terminal_view_handler)
    app.router.add_get("/p2p-sender.html", p2p_sender_handler)
    app.router.add_get("/p2p-view.html", p2p_view_handler)
    app.router.add_get("/display.html", display_handler)

    # HDMI 显示管理
    app.router.add_post("/api/display/start", api_display_start)
    app.router.add_delete("/api/display/stop", api_display_stop)
    app.router.add_get("/api/display/status", api_display_status)

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

    # 启动 mDNS 服务广播
    logger.info("启动 mDNS 服务广播...")
    try:
        start_mdns()
    except Exception as e:
        logger.warning(f"[mDNS] 启动失败: {e}")


async def on_cleanup(app):
    logger.info("关闭所有会话...")
    await receiver_manager.stop_all()

    # 停止 HDMI 显示
    await _stop_display()

    # 停止 mDNS 服务
    try:
        stop_mdns()
    except Exception:
        pass


# ========================================
# 主函数
# ========================================
async def main():
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
    print(f"  WebSocket:      ws://{local_ip}:{http_port}/ws")
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
    ssl_ctx = None
    ssl_crt = Path(__file__).resolve().parent / "cert.pem"
    ssl_key = Path(__file__).resolve().parent / "key.pem"
    if ssl_crt.exists() and ssl_key.exists():
        import ssl
        ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ssl_ctx.load_cert_chain(str(ssl_crt), str(ssl_key))
        print("[SSL] HTTPS 已启用")
        print("")

    # 同时监听 HTTP 端口 (config.ws_port) 供本地 HDMI 显示使用
    runner = web.AppRunner(app)
    await runner.setup()
    sites = []
    sites.append(web.TCPSite(runner, config.server_host, http_port, ssl_context=ssl_ctx))
    sites.append(web.TCPSite(runner, config.server_host, config.ws_port, ssl_context=None))
    print(f"[HTTP] 本地显示端口: http://localhost:{config.ws_port}")
    for site in sites:
        await site.start()
    print("")
    try:
        await asyncio.Event().wait()
    finally:
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
