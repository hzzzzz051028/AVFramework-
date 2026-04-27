#!/usr/bin/env python3
"""测试终端 WebSocket 连接"""

import asyncio
import json
import websockets

async def test_terminal_ws():
    uri = "ws://localhost:8080/ws/terminal"
    print(f"连接到 {uri}...")

    try:
        async with websockets.connect(uri) as ws:
            print("已连接!")

            # 接收欢迎消息
            msg = await ws.recv()
            print(f"收到: {msg}")

            # 发送测试消息
            test_msg = {
                "type": "output",
                "content": "Hello from test client!",
                "timestamp": "2024-01-01T00:00:00"
            }
            await ws.send(json.dumps(test_msg))
            print("已发送测试消息")

            # 等待响应
            for i in range(3):
                msg = await ws.recv()
                print(f"收到: {msg}")

            print("测试完成!")

    except Exception as e:
        print(f"错误: {e}")

if __name__ == "__main__":
    asyncio.run(test_terminal_ws())
