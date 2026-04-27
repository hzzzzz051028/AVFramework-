#!/usr/bin/env python3
"""
PC 端终端转发服务
将本地 shell 终端通过 WebSocket 转发到 RK3588
保底方案：当视频投屏不可用时使用
"""

import asyncio
import json
import logging
import os
import subprocess
import websockets
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
)
logger = logging.getLogger(__name__)


class TerminalForwarder:
    """终端转发器 - 捕获 shell 输出并转发"""

    def __init__(self, ws_url):
        self.ws_url = ws_url
        self.ws = None
        self.running = False
        self.process = None
        self.message_queue = asyncio.Queue()

    async def connect(self):
        """连接到 RK3588 WebSocket 服务"""
        while self.running:
            try:
                logger.info(f"[WS] Connecting to {self.ws_url}")
                self.ws = await websockets.connect(self.ws_url)
                logger.info("[WS] Connected")

                # 启动终端进程和消息发送任务
                self.start_terminal()
                sender_task = asyncio.create_task(self.send_messages())

                # 接收消息循环
                async for message in self.ws:
                    await self.handle_message(message)

                # 清理
                sender_task.cancel()

            except Exception as e:
                logger.error(f"[WS] Connection error: {e}")
                if self.running:
                    logger.info("[WS] Reconnecting in 3 seconds...")
                    await asyncio.sleep(3)

    def start_terminal(self):
        """启动终端进程"""
        try:
            # Windows: PowerShell
            if os.name == 'nt':
                self.process = subprocess.Popen(
                    ['powershell.exe', '-NoExit', '-Command', '-'],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1
                )
            # Linux/Mac: bash
            else:
                self.process = subprocess.Popen(
                    ['bash', '-i'],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1
                )

            logger.info(f"[Terminal] Started: PID {self.process.pid}")

            # 启动输出读取任务
            asyncio.create_task(self.read_output())

        except Exception as e:
            logger.error(f"[Terminal] Failed to start: {e}")

    async def read_output(self):
        """读取终端输出并发送到队列"""
        while self.process and self.process.poll() is None:
            try:
                # 读取 stdout
                line = self.process.stdout.readline()
                if line:
                    await self.message_queue.put({
                        'type': 'output',
                        'content': line.strip(),
                        'timestamp': datetime.now().isoformat()
                    })

                # 读取 stderr
                err_line = self.process.stderr.readline()
                if err_line:
                    await self.message_queue.put({
                        'type': 'error',
                        'content': err_line.strip(),
                        'timestamp': datetime.now().isoformat()
                    })

            except Exception as e:
                logger.error(f"[Terminal] Read error: {e}")
                break

    async def send_messages(self):
        """从队列发送消息到 WebSocket"""
        while self.running and self.ws:
            try:
                msg = await asyncio.wait_for(self.message_queue.get(), timeout=1.0)
                await self.ws.send(json.dumps(msg))
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.debug(f"[WS] Send failed: {e}")
                break

    async def handle_message(self, message):
        """处理来自 RK3588 的消息"""
        try:
            data = json.loads(message)

            if data['type'] == 'command':
                # 执行命令
                if self.process and self.process.stdin:
                    self.process.stdin.write(data['command'] + '\n')
                    self.process.stdin.flush()

            elif data['type'] == 'ping':
                # 心跳响应
                await self.ws.send(json.dumps({'type': 'pong'}))

        except Exception as e:
            logger.error(f"[WS] Message handling error: {e}")

    def stop(self):
        """停止转发"""
        self.running = False
        if self.process:
            self.process.terminate()


async def main():
    """主函数"""
    import sys

    # RK3588 地址
    if len(sys.argv) > 1:
        rk_ip = sys.argv[1]
    else:
        rk_ip = input("Enter RK3588 IP address: ").strip()

    ws_url = f"ws://{rk_ip}:8080/ws/terminal"

    forwarder = TerminalForwarder(ws_url)
    forwarder.running = True

    print("")
    print("=" * 50)
    print("  Terminal Forwarder")
    print("=" * 50)
    print(f"Target: {rk_ip}")
    print(f"WebSocket: {ws_url}")
    print("")
    print("Usage:")
    print("1. Ensure RK3588 service is running")
    print("2. Terminal will appear on RK3588 display")
    print("3. Press Ctrl+C to exit")
    print("=" * 50)
    print("")

    try:
        await forwarder.connect()
    except KeyboardInterrupt:
        print("\nStopping...")
        forwarder.stop()


if __name__ == "__main__":
    asyncio.run(main())
