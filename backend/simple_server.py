#!/usr/bin/env python3
"""
WebRTC 屏幕共享信令服务器
用于在浏览器之间转发 SDP 和 ICE candidate
"""

import asyncio
import json
import logging
import socket
from pathlib import Path
from datetime import datetime

import websockets

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(message)s',
    datefmt='%H:%M:%S',
)
logger = logging.getLogger(__name__)

# 前端目录
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"


def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "localhost"


# 会话存储
# sessions[session_id] = {"host": ws, "viewers": [ws1, ws2, ...]}
sessions = {}


async def handler(websocket):
    """处理 WebSocket 连接"""
    client_id = id(websocket)
    peer = websocket.remote_address
    logger.info(f"[{client_id}] 连接来自 {peer}")

    current_session = None
    is_host = False

    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                msg_type = data.get("type")

                # 心跳
                if msg_type == "ping":
                    await websocket.send(json.dumps({"type": "pong"}))
                    continue

                # 创建会话（共享端）
                if msg_type == "create_session":
                    session_id = data.get("session_id")
                    if not session_id:
                        session_id = f"sess_{datetime.now().strftime('%Y%m%d%H%M%S')}"

                    sessions[session_id] = {
                        "host": websocket,
                        "viewers": [],
                        "host_offer": None,
                    }
                    current_session = session_id
                    is_host = True

                    logger.info(f"[{client_id}] 创建会话: {session_id}")
                    await websocket.send(json.dumps({
                        "type": "session_created",
                        "session_id": session_id,
                    }))
                    continue

                # 加入会话（观看端）
                if msg_type == "join_session":
                    session_id = data.get("session_id")
                    if session_id not in sessions:
                        await websocket.send(json.dumps({
                            "type": "error",
                            "message": "会话不存在"
                        }))
                        continue

                    session = sessions[session_id]
                    session["viewers"].append(websocket)
                    current_session = session_id

                    # 如果有 host offer，转发给观看端
                    if session["host_offer"]:
                        await websocket.send(session["host_offer"])

                    logger.info(f"[{client_id}] 加入会话: {session_id}")
                    continue

                # SDP Offer（从共享端）
                if msg_type == "offer":
                    session_id = data.get("session_id")
                    if not session_id:
                        continue

                    # 如果会话不存在，自动创建（隐式创建会话）
                    if session_id not in sessions:
                        sessions[session_id] = {
                            "host": websocket,
                            "viewers": [],
                            "host_offer": None,
                        }
                        current_session = session_id
                        is_host = True
                        logger.info(f"[{client_id}] 自动创建会话: {session_id}")

                    # 标记此连接为会话的主机
                    if sessions[session_id]["host"] == websocket:
                        is_host = True
                        current_session = session_id

                    offer_msg = json.dumps(data)
                    sessions[session_id]["host_offer"] = offer_msg

                    # 转发给所有观看端
                    for viewer in list(sessions[session_id]["viewers"]):
                        try:
                            await viewer.send(offer_msg)
                        except Exception:
                            sessions[session_id]["viewers"].remove(viewer)
                    logger.info(f"[{session_id}] Offer 已转发给 {len(sessions[session_id]['viewers'])} 个观看端")
                    continue

                # SDP Answer（从观看端）
                if msg_type == "answer":
                    session_id = data.get("session_id")
                    if session_id in sessions:
                        host = sessions[session_id]["host"]
                        try:
                            await host.send(json.dumps(data))
                            logger.info(f"[{session_id}] Answer 已转发")
                        except Exception:
                            logger.warning(f"转发 answer 失败: host 可能已断开")
                    continue

                # ICE Candidate（双向）
                if msg_type == "ice_candidate":
                    session_id = data.get("session_id")
                    if session_id not in sessions:
                        continue

                    session = sessions[session_id]
                    target = None

                    # 判断转发方向
                    if websocket == session["host"]:
                        # 从 host 转发给 viewers
                        targets = session["viewers"]
                    else:
                        # 从 viewer 转发给 host
                        targets = [session["host"]]

                    ice_msg = json.dumps(data)
                    for target_ws in targets:
                        try:
                            await target_ws.send(ice_msg)
                        except Exception:
                            pass
                    continue

                logger.warning(f"[{client_id}] 未知消息类型: {msg_type}")

            except json.JSONDecodeError:
                logger.warning(f"[{client_id}] 无效的 JSON")
            except Exception as e:
                logger.error(f"[{client_id}] 处理消息错误: {e}")

    except websockets.exceptions.ConnectionClosed:
        logger.info(f"[{client_id}] 连接关闭")
    finally:
        # 清理会话
        if current_session and current_session in sessions:
            session = sessions[current_session]

            if is_host:
                # 主机断开，清理整个会话
                logger.info(f"[{current_session}] 会话结束（主机断开）")
                for viewer in session["viewers"]:
                    try:
                        await viewer.send(json.dumps({
                            "type": "session_ended",
                            "message": "主机已断开连接"
                        }))
                    except Exception:
                        pass
                del sessions[current_session]
            else:
                # 观看端断开，从列表中移除
                try:
                    session["viewers"].remove(websocket)
                except ValueError:
                    pass
                logger.info(f"[{current_session}] 观看端断开，剩余 {len(session['viewers'])} 人")


async def main():
    """启动服务器"""
    local_ip = get_local_ip()
    port = 8081

    print("")
    print("=" * 55)
    print("   WebRTC 屏幕共享信令服务器")
    print("=" * 55)
    print("")
    print(f"[接入方式]")
    print(f"  本机 IP:     {local_ip}")
    print(f"  WebSocket:   ws://{local_ip}:{port}")
    print(f"  共享端:      http://{local_ip}:8080/screenshare.html")
    print(f"  观看端:      http://{local_ip}:8080/view.html")
    print("")
    print("按 Ctrl+C 停止")
    print("=" * 55)
    print("")

    async with websockets.serve(handler, "0.0.0.0", port, ping_interval=30):
        await asyncio.Future()  # 永久运行


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n服务器已停止")
