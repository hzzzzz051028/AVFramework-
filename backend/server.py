#!/usr/bin/env python3
"""
屏幕共享信令服务器 - Python 版本
支持 HTTP 静态文件服务和 WebSocket 信令
"""

import asyncio
import json
import logging
import os
import socket
import time
from datetime import datetime
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import threading

# 尝试导入 websockets
try:
    import websockets
    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False
    print("警告: websockets 库未安装，请运行: pip install websockets")

# ========================================
# 配置
# ========================================
HTTP_PORT = 8080
WS_PORT = 8081
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"

# ========================================
# 日志配置
# ========================================
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# ========================================
# 获取本机局域网 IP
# ========================================
def get_local_ip():
    """获取本机局域网 IP 地址"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "localhost"

# ========================================
# 会话管理
# ========================================
class SessionManager:
    """管理屏幕共享会话"""

    def __init__(self):
        self.sessions = {}  # session_id -> session_info
        self.clients = {}   # client_id -> client_info
        self.lock = threading.Lock()

    def create_session(self, session_id, host_ws, offer=None):
        """创建新会话"""
        with self.lock:
            self.sessions[session_id] = {
                'session_id': session_id,
                'host_ws': host_ws,
                'guest_ws': None,
                'offer': offer,
                'created_at': datetime.now().isoformat()
            }
            logger.info(f"[SESSION] Created: {session_id}")

    def join_session(self, session_id, guest_ws):
        """加入会话"""
        with self.lock:
            if session_id not in self.sessions:
                return False

            self.sessions[session_id]['guest_ws'] = guest_ws
            logger.info(f"[SESSION] Guest joined: {session_id}")
            return True

    def get_session(self, session_id):
        """获取会话"""
        return self.sessions.get(session_id)

    def remove_session(self, session_id):
        """删除会话"""
        with self.lock:
            if session_id in self.sessions:
                del self.sessions[session_id]
                logger.info(f"[SESSION] Removed: {session_id}")

    def disconnect_guest(self, session_id):
        """断开观看者"""
        with self.lock:
            if session_id in self.sessions:
                self.sessions[session_id]['guest_ws'] = None
                logger.info(f"[SESSION] Guest disconnected: {session_id}")

# 全局会话管理器
session_manager = SessionManager()

# ========================================
# HTTP 请求处理器
# ========================================
class HTTPRequestHandler(SimpleHTTPRequestHandler):
    """自定义 HTTP 请求处理器"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(FRONTEND_DIR), **kwargs)

    def log_message(self, format, *args):
        """自定义日志格式"""
        logger.info(f"[HTTP] {self.address_string()} - {format % args}")

    def do_GET(self):
        """处理 GET 请求"""
        parsed_path = urlparse(self.path)

        # API 端点
        if parsed_path.path == '/health':
            self.send_health_check()
            return

        if parsed_path.path == '/info':
            self.send_server_info()
            return

        # 根路径返回 screenshare.html
        if parsed_path.path == '/' or parsed_path.path == '':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()

            html_path = FRONTEND_DIR / 'screenshare.html'
            if html_path.exists():
                with open(html_path, 'rb') as f:
                    self.wfile.write(f.read())
                logger.info(f"[HTTP] Serving screenshare.html")
            else:
                self.send_error(404, 'File Not Found')
            return

        # 静态文件服务
        super().do_GET()

    def send_health_check(self):
        """发送健康检查响应"""
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

        data = {
            'status': 'ok',
            'timestamp': datetime.now().isoformat(),
            'sessions': len(session_manager.sessions),
            'clients': len(session_manager.clients)
        }
        self.wfile.write(json.dumps(data, indent=2).encode())

    def send_server_info(self):
        """发送服务器信息"""
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

        data = {
            'server': 'Screen Share Signaling Server',
            'version': '2.0.0 (Python)',
            'ws_port': WS_PORT,
            'http_port': HTTP_PORT,
            'local_ip': get_local_ip(),
            'sessions': [
                {
                    'session_id': s['session_id'],
                    'host_connected': s['host_ws'] is not None,
                    'guest_connected': s['guest_ws'] is not None,
                    'created_at': s['created_at']
                }
                for s in session_manager.sessions.values()
            ]
        }
        self.wfile.write(json.dumps(data, indent=2).encode())

    def end_headers(self):
        """添加 CORS 头"""
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()

# ========================================
# WebSocket 消息处理
# ========================================
async def handle_websocket(websocket):
    """处理 WebSocket 连接"""
    client_id = id(websocket)
    client_ip = websocket.remote_address[0] if websocket.remote_address else "unknown"

    logger.info(f"[WS] Client connected: {client_id} from {client_ip}")

    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                logger.info(f"[WS] {client_id}: {data.get('type')}")

                await handle_message(websocket, client_id, data)

            except json.JSONDecodeError:
                logger.error(f"[WS] Invalid JSON from {client_id}")
            except Exception as e:
                logger.error(f"[WS] Error handling message: {e}")

    except websockets.exceptions.ConnectionClosed:
        logger.info(f"[WS] Client disconnected: {client_id}")
    except Exception as e:
        logger.error(f"[WS] Error: {e}")
    finally:
        handle_disconnect(client_id)

async def handle_message(websocket, client_id, data):
    """处理收到的消息"""

    msg_type = data.get('type')

    # 心跳
    if msg_type == 'ping':
        await websocket.send(json.dumps({'type': 'pong'}))
        return

    # 创建会话
    if msg_type == 'create_session':
        session_id = f"sess_{generate_id()}"
        offer = data.get('offer')

        session_manager.create_session(session_id, websocket, offer)

        await websocket.send(json.dumps({
            'type': 'session_created',
            'session_id': session_id
        }))

        # 如果有 offer，广播给观看者
        if offer:
            await broadcast_offer(session_id)
        return

    # 加入会话
    if msg_type == 'join_session':
        session_id = data.get('session_id')

        if not session_manager.join_session(session_id, websocket):
            await websocket.send(json.dumps({
                'type': 'error',
                'message': 'Session not found'
            }))
            return

        # 发送 offer
        session = session_manager.get_session(session_id)
        if session and session['offer']:
            await websocket.send(json.dumps({
                'type': 'offer',
                'offer': session['offer']
            }))
        return

    # 处理 Offer
    if msg_type == 'offer':
        session_id = data.get('session_id')
        if not session_id:
            return

        session = session_manager.get_session(session_id)
        if not session:
            return

        session['offer'] = data.get('offer')
        session['host_ws'] = websocket

        # 转发给观看者
        if session['guest_ws']:
            await session['guest_ws'].send(json.dumps({
                'type': 'offer',
                'offer': data.get('offer')
            }))
            logger.info(f"[SESSION] Offer sent to guest")
        return

    # 处理 Answer
    if msg_type == 'answer':
        session_id = data.get('session_id')
        if not session_id:
            return

        session = session_manager.get_session(session_id)
        if not session:
            return

        if session['host_ws']:
            await session['host_ws'].send(json.dumps({
                'type': 'answer',
                'sdp': data.get('sdp')
            }))
            logger.info(f"[SESSION] Answer sent to host")
        return

    # 处理 ICE 候选
    if msg_type == 'ice_candidate':
        session_id = data.get('session_id')
        if not session_id:
            return

        session = session_manager.get_session(session_id)
        if not session:
            return

        # 确定目标客户端
        target_ws = None
        if session['host_ws'] == websocket:
            target_ws = session['guest_ws']
        else:
            target_ws = session['host_ws']

        if target_ws:
            await target_ws.send(json.dumps({
                'type': 'ice',
                'candidate': data.get('candidate')
            }))
            logger.info(f"[SESSION] ICE candidate forwarded")
        return

    # 重连
    if msg_type == 'reconnect':
        session_id = data.get('session_id')
        if not session_id:
            return

        session = session_manager.get_session(session_id)
        if not session:
            await websocket.send(json.dumps({
                'type': 'error',
                'message': 'Session not found for reconnection'
            }))
            return

        session['guest_ws'] = websocket
        logger.info(f"[SESSION] Reconnected: {client_id} to {session_id}")

        await websocket.send(json.dumps({
            'type': 'reconnected',
            'session_id': session_id
        }))
        return

    logger.warning(f"[WS] Unknown message type: {msg_type}")

async def broadcast_offer(session_id):
    """广播 offer"""
    session = session_manager.get_session(session_id)
    if session and session['offer']:
        logger.info(f"[SESSION] Broadcasting offer for {session_id}")

def handle_disconnect(client_id):
    """处理客户端断开"""
    # 查找并清理相关会话
    to_remove = []
    for session_id, session in session_manager.sessions.items():
        if session['host_ws'] and id(session['host_ws']) == client_id:
            to_remove.append(session_id)
        elif session['guest_ws'] and id(session['guest_ws']) == client_id:
            session_manager.disconnect_guest(session_id)

    for session_id in to_remove:
        session_manager.remove_session(session_id)

def generate_id():
    """生成随机 ID"""
    import random
    import string
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))

# ========================================
# 启动 HTTP 服务器
# ========================================
def start_http_server():
    """启动 HTTP 服务器"""
    server = HTTPServer(('0.0.0.0', HTTP_PORT), HTTPRequestHandler)
    logger.info(f"[HTTP] Server started on port {HTTP_PORT}")
    server.serve_forever()

# ========================================
# 启动 WebSocket 服务器
# ========================================
async def start_websocket_server():
    """启动 WebSocket 服务器"""
    async with websockets.serve(handle_websocket, '0.0.0.0', WS_PORT):
        logger.info(f"[WS] Server started on port {WS_PORT}")
        await asyncio.Future()  # 永远运行

# ========================================
# 主函数
# ========================================
def main():
    """主函数"""
    local_ip = get_local_ip()

    print("")
    print("=" * 50)
    print("   Screen Share Signaling Server v2.0")
    print("   (Python Edition)")
    print("=" * 50)
    print("")
    print("[LAN Access]")
    print(f"  Your IP:         {local_ip}")
    print(f"  Web Interface:   http://{local_ip}:{HTTP_PORT}")
    print(f"  WebSocket:       ws://{local_ip}:{WS_PORT}")
    print("")
    print("[Info]")
    print(f"  Other devices can open: http://{local_ip}:{HTTP_PORT}")
    print(f"  in their browser to access the system.")
    print("")
    print("[Endpoints]")
    print("  /               - Screen share web interface")
    print("  /health         - Health check")
    print("  /info           - Server information")
    print("")
    print("Press Ctrl+C to stop")
    print("=" * 50)
    print("")

    if not HAS_WEBSOCKETS:
        print("错误: 请先安装 websockets 库")
        print("运行: pip install websockets")
        return

    # 在单独线程中启动 HTTP 服务器
    http_thread = threading.Thread(target=start_http_server, daemon=True)
    http_thread.start()

    # 启动 WebSocket 服务器
    try:
        asyncio.run(start_websocket_server())
    except KeyboardInterrupt:
        logger.info("[SERVER] Shutting down...")
        print("\nServer stopped.")

if __name__ == '__main__':
    main()
