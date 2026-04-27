#!/usr/bin/env python3
"""模拟终端输出并转发到 RK3588"""

import asyncio
import json
import random
import websockets
from datetime import datetime

async def simulate_terminal():
    """模拟终端输出"""
    uri = "ws://localhost:8080/ws/terminal"
    print(f"Connecting to {uri}...")

    async with websockets.connect(uri) as ws:
        print("Connected!")

        # 接收欢迎消息
        msg = await ws.recv()
        print(f"Server: {msg}")

        # 模拟终端会话
        commands = [
            "ls -la",
            "pwd",
            "whoami",
            "top -n 1",
            "df -h",
            "free -h",
            "ps aux | head -10"
        ]

        outputs = {
            "ls -la": """total 48
drwxr-xr-x  5 user user 4096 Apr 27 10:00 .
drwxr-xr-x  3 root root 4096 Apr 27 09:00 ..
-rw-r--r--  1 user user  220 Apr 27 09:00 .bash_logout
-rw-r--r--  1 user user 3771 Apr 27 09:00 .bashrc""",
            "pwd": "/home/user/project",
            "whoami": "user",
            "top -n 1": """top - 10:49:23 up 1 day,  2:15,  2 users,  load average: 0.15, 0.10, 0.08
Tasks: 123 total,   1 running, 122 sleeping,   0 stopped,   0 zombie
%Cpu(s):  5.2 us,  2.1 sy,  0.0 ni, 92.1 id,  0.0 wa,  0.0 hi,  0.7 si,  0.0 st""",
            "df -h": """Filesystem      Size  Used Avail Use% Mounted on
/dev/root        50G   15G   33G  31% /
/dev/sda1       100G   45G   51G  47% /data""",
            "free -h": """              total        used        free      shared  buff/cache   available
Mem:           7.5G        2.3G        3.8G        150M        1.4G        4.8G
Swap:          2.0G          0B        2.0G""",
            "ps aux | head -10": """USER       PID %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND
root         1  0.0  0.1  21536  6120 ?        Ss   09:00   0:02 /sbin/init
root         2  0.0  0.0      0     0 ?        S    09:00   0:00 [kthreadd]"""
        }

        # 模拟终端会话
        await asyncio.sleep(1)

        for cmd in commands:
            # 发送命令提示符
            prompt = f"$ {cmd}"
            await ws.send(json.dumps({
                'type': 'output',
                'content': prompt,
                'timestamp': datetime.now().isoformat()
            }))
            print(f"Sent: {prompt}")

            await asyncio.sleep(0.5)

            # 发送输出
            output = outputs.get(cmd, f"Output for {cmd}")
            for line in output.split('\n'):
                await ws.send(json.dumps({
                    'type': 'output',
                    'content': line,
                    'timestamp': datetime.now().isoformat()
                }))
                await asyncio.sleep(0.1)

            await asyncio.sleep(0.5)

        # 发送完成消息
        await ws.send(json.dumps({
            'type': 'output',
            'content': '',
            'timestamp': datetime.now().isoformat()
        }))

        print("\nSimulation complete! Check the browser terminal page.")

        # 保持连接以接收响应
        try:
            while True:
                msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
                print(f"Received: {msg[:100]}...")
        except asyncio.TimeoutError:
            print("No more messages, closing...")

if __name__ == "__main__":
    asyncio.run(simulate_terminal())
