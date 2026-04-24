#!/usr/bin/env python3
"""
WebRTC 屏幕共享信令服务器 v2
优化的传输框架，包含详细日志
"""

import asyncio
import json
import logging
import socket
from pathlib import Path
from datetime import datetime
from collections import defaultdict

import websockets

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
)
logger = logging.getLogger(__name__)


def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "localhost"


# 会话存储 - 优化的数据结构
class SessionManager:
    def __init__(self):
        self.sessions = {}  # session_id -> Session
        self.client_to_session = {}  # client_id -> session_id
        self.message_stats = defaultdict(int)

    def create_session(self, session_id, host_ws):
        """创建新会话"""
        self.sessions[session_id] = {
            "host": host_ws,
            "viewers": [],
            "host_offer": None,
            "created_at": datetime.now(),
            "stats": {"offers": 0, "answers": 0, "ice": 0}
        }
        self.client_to_session[id(host_ws)] = session_id
        logger.info(f"[Session] 创建会话 {session_id}")

    def get_session(self, session_id):
        """获取会话"""
        return self.sessions.get(session_id)

    def add_viewer(self, session_id, viewer_ws):
        """添加观看端"""
        if session_id in self.sessions:
            self.sessions[session_id]["viewers"].append(viewer_ws)
            self.client_to_session[id(viewer_ws)] = session_id
            logger.info(f"[Session] 观看端加入 {session_id}, 总计: {len(self.sessions[session_id]['viewers'])}")

    def remove_client(self, client_ws):
        """移除客户端"""
        client_id = id(client_ws)
        if client_id in self.client_to_session:
            session_id = self.client_to_session[client_id]
            if session_id in self.sessions:
                session = self.sessions[session_id]
                if session["host"] == client_ws:
                    # 主机断开，删除整个会话
                    logger.info(f"[Session] 主机断开，删除会话 {session_id}")
                    del self.sessions[session_id]
                elif client_ws in session["viewers"]:
                    # 观看端断开
                    session["viewers"].remove(client_ws)
                    logger.info(f"[Session] 观看端断开 {session_id}, 剩余: {len(session['viewers'])}")
            del self.client_to_session[client_id]

    def track_message(self, msg_type):
        """跟踪消息统计"""
        self.message_stats[msg_type] += 1


# 全局会话管理器
manager = SessionManager()


async def handler(websocket):
    """处理 WebSocket 连接 - 优化的处理器"""
    client_id = id(websocket)
    peer = websocket.remote_address
    logger.info(f"[Connect] {client_id} from {peer}")

    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                msg_type = data.get("type")
                manager.track_message(msg_type)

                logger.debug(f"[Msg {client_id}] {msg_type}")

                # 心跳
                if msg_type == "ping":
                    await websocket.send(json.dumps({"type": "pong"}))
                    continue

                # 加入会话（观看端）
                if msg_type == "join_session":
                    session_id = data.get("session_id")
                    session = manager.get_session(session_id)

                    if not session:
                        logger.warning(f"[Join] 会话不存在: {session_id}")
                        await websocket.send(json.dumps({
                            "type": "error",
                            "message": f"会话 {session_id} 不存在"
                        }))
                        continue

                    manager.add_viewer(session_id, websocket)

                    # 如果有缓存的 offer，立即转发
                    if session["host_offer"]:
                        logger.info(f"[Offer] 转发缓存的 Offer 给 {client_id}")
                        await websocket.send(session["host_offer"])
                    continue

                # SDP Offer（从共享端）
                if msg_type == "offer":
                    session_id = data.get("session_id")
                    if not session_id:
                        logger.warning(f"[Offer] 缺少 session_id")
                        continue

                    # 自动创建会话
                    if not manager.get_session(session_id):
                        manager.create_session(session_id, websocket)

                    session = manager.get_session(session_id)
                    offer_msg = json.dumps(data)
                    session["host_offer"] = offer_msg
                    session["stats"]["offers"] += 1

                    logger.info(f"[Offer] {session_id} -> 转发给 {len(session['viewers'])} 个观看端")

                    # 转发给所有观看端
                    failed_viewers = []
                    for viewer in session["viewers"]:
                        try:
                            await viewer.send(offer_msg)
                            logger.debug(f"[Offer] 已发送给观看端")
                        except Exception as e:
                            logger.error(f"[Offer] 发送失败: {e}")
                            failed_viewers.append(viewer)

                    # 清理失败的观看端
                    for v in failed_viewers:
                        session["viewers"].remove(v)
                        manager.remove_client(v)
                    continue

                # SDP Answer（从观看端）
                if msg_type == "answer":
                    session_id = data.get("session_id")
                    session = manager.get_session(session_id)

                    if not session:
                        logger.warning(f"[Answer] 会话不存在: {session_id}")
                        continue

                    session["stats"]["answers"] += 1
                    logger.info(f"[Answer] {session_id} -> 转发给主机")

                    try:
                        await session["host"].send(json.dumps(data))
                        logger.debug(f"[Answer] 已发送给主机")
                    except Exception as e:
                        logger.error(f"[Answer] 发送失败: {e}")
                    continue

                # ICE Candidate（双向）
                if msg_type == "ice_candidate":
                    session_id = data.get("session_id")
                    session = manager.get_session(session_id)

                    if not session:
                        logger.debug(f"[ICE] 会话不存在: {session_id}")
                        continue

                    session["stats"]["ice"] += 1

                    # 判断转发方向
                    if websocket == session["host"]:
                        # 从 host -> viewers
                        targets = session["viewers"]
                        direction = "主机->观看端"
                    else:
                        # 从 viewer -> host
                        targets = [session["host"]]
                        direction = "观看端->主机"

                    logger.debug(f"[ICE] {session_id} {direction}")

                    ice_msg = json.dumps(data)
                    for target in targets:
                        try:
                            await target.send(ice_msg)
                        except Exception as e:
                            logger.debug(f"[ICE] 发送失败: {e}")
                    continue

                logger.warning(f"[Unknown] 消息类型: {msg_type}")

            except json.JSONDecodeError as e:
                logger.error(f"[JSON] 解析失败: {e}")
            except Exception as e:
                logger.error(f"[Error] 处理消息: {e}")

    except websockets.exceptions.ConnectionClosed:
        logger.info(f"[Disconnect] {client_id}")
    finally:
        manager.remove_client(websocket)


async def stats_reporter():
    """定期报告统计信息"""
    while True:
        await asyncio.sleep(10)
        active_sessions = len(manager.sessions)
        total_messages = sum(manager.message_stats.values())
        logger.info(f"[Stats] 活跃会话: {active_sessions}, 消息总数: {total_messages}")
        if manager.message_stats:
            logger.info(f"[Stats] 消息分布: {dict(manager.message_stats)}")


async def main():
    """启动服务器"""
    local_ip = get_local_ip()
    port = 8081

    print("")
    print("=" * 55)
    print("   WebRTC 屏幕共享信令服务器 v2")
    print("   优化的传输框架 + 详细日志")
    print("=" * 55)
    print("")
    print(f"[接入方式]")
    print(f"  本机 IP:     {local_ip}")
    print(f"  WebSocket:   ws://{local_ip}:{port}")
    print(f"  共享端:      http://{local_ip}:8080/sender.html")
    print(f"  观看端:      http://{local_ip}:8080/view.html")
    print("")
    print("[功能特性]")
    print(f"  - 自动会话管理")
    print(f"  - 消息转发统计")
    print(f"  - 详细日志追踪")
    print(f"  - 错误恢复机制")
    print("")
    print("按 Ctrl+C 停止")
    print("=" * 55)
    print("")

    # 启动统计报告任务
    asyncio.create_task(stats_reporter())

    async with websockets.serve(handler, "0.0.0.0", port, ping_interval=30, ping_timeout=20):
        await asyncio.Future()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n服务器已停止")
