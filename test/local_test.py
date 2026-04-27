"""
本地完整功能测试脚本
在本地验证所有功能是否正常工作
"""

import asyncio
import requests
import websockets
import json
import time
from datetime import datetime

BASE_URL = "http://localhost:8080"
WS_URL = "ws://localhost:8080/ws"


class LocalTester:
    """本地功能测试器"""

    def __init__(self):
        self.results = []
        self.errors = []

    async def test(self, name, func):
        """运行单个测试"""
        print(f"\n{'='*60}")
        print(f"测试: {name}")
        print(f"{'='*60}")
        try:
            # 如果测试函数是异步的，直接 await
            if asyncio.iscoroutinefunction(func):
                result = await func()
            else:
                result = func()
            self.results.append((name, True, result))
            print(f"[PASS] {result}")
            return True
        except Exception as e:
            self.results.append((name, False, str(e)))
            self.errors.append((name, str(e)))
            print(f"[FAIL] {e}")
            return False

    def summary(self):
        """测试总结"""
        print(f"\n{'='*60}")
        print(f"测试总结")
        print(f"{'='*60}")
        passed = sum(1 for _, success, _ in self.results if success)
        total = len(self.results)
        print(f"通过: {passed}/{total}")

        if self.errors:
            print(f"\n失败的测试:")
            for name, error in self.errors:
                print(f"  - {name}: {error}")

        return passed == total


def test_health_check():
    """测试健康检查"""
    response = requests.get(f"{BASE_URL}/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "gst_available" in data
    return f"GST可用: {data['gst_available']}, 会话数: {data['sessions']}"


def test_server_info():
    """测试服务器信息"""
    response = requests.get(f"{BASE_URL}/info")
    assert response.status_code == 200
    data = response.json()
    assert "server" in data
    assert "local_ip" in data
    return f"服务器: {data['server']}, IP: {data['local_ip']}"


def test_device_discovery():
    """测试设备发现 API"""
    response = requests.get(f"{BASE_URL}/api/discover")
    assert response.status_code == 200
    data = response.json()
    assert "devices" in data
    return f"发现 {len(data['devices'])} 个设备"


def test_api_status():
    """测试状态 API"""
    response = requests.get(f"{BASE_URL}/api/status")
    assert response.status_code == 200
    data = response.json()
    assert "hardware" in data
    assert "sessions" in data
    return f"硬件平台: {data['hardware'].get('platform')}"


async def test_websocket_connection():
    """测试 WebSocket 连接"""
    async with websockets.connect(WS_URL) as ws:
        # 发送 ping
        await ws.send(json.dumps({"type": "ping"}))

        # 接收 pong
        response = await asyncio.wait_for(ws.recv(), timeout=2.0)
        data = json.loads(response)
        assert data["type"] == "pong"

    return "WebSocket 连接正常，ping/pong 工作正常"


async def test_websocket_terminal():
    """测试终端 WebSocket"""
    term_url = "ws://localhost:8080/ws/terminal"
    async with websockets.connect(term_url) as ws:
        # 接收欢迎消息
        response = await asyncio.wait_for(ws.recv(), timeout=2.0)
        data = json.loads(response)
        assert data["type"] == "connected"

        # 发送测试消息
        await ws.send(json.dumps({
            "type": "output",
            "content": "Test message",
            "timestamp": datetime.now().isoformat()
        }))

    return "终端 WebSocket 连接正常"


def test_static_files():
    """测试静态文件服务"""
    files = [
        "/sender.html",
        "/view.html",
        "/dashboard.html",
        "/terminal-view.html"
    ]

    for file in files:
        response = requests.get(f"{BASE_URL}{file}")
        if response.status_code != 200:
            return f"文件 {file} 返回 {response.status_code}"

    return "所有静态文件可访问"


def test_favicon():
    """测试图标加载"""
    response = requests.get(f"{BASE_URL}/favicon.ico")
    # favicon.ico 可能不存在，这是正常的
    return f"图标状态: {response.status_code}"


def test_main_page():
    """测试主页面"""
    response = requests.get(f"{BASE_URL}/")
    assert response.status_code == 200
    # 检查是否包含关键内容
    content = response.text
    assert "投屏" in content or "屏幕" in content
    return "主页面包含预期内容"


async def run_all_tests():
    """运行所有测试"""
    tester = LocalTester()

    # HTTP API 测试
    await tester.test("健康检查", test_health_check)
    await tester.test("服务器信息", test_server_info)
    await tester.test("设备发现", test_device_discovery)
    await tester.test("状态查询", test_api_status)
    await tester.test("静态文件", test_static_files)
    await tester.test("主页面", test_main_page)
    await tester.test("图标加载", test_favicon)

    # WebSocket 测试
    await tester.test("WebSocket连接", test_websocket_connection)
    await tester.test("终端WebSocket", test_websocket_terminal)

    # 输出总结
    success = tester.summary()

    if success:
        print("\n[SUCCESS] 所有测试通过！系统运行正常。")
    else:
        print("\n[WARNING] 有测试失败，需要修复。")

    return success


if __name__ == "__main__":
    print("=" * 60)
    print("  本地功能测试")
    print("=" * 60)
    print(f"测试目标: {BASE_URL}")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    try:
        success = asyncio.run(run_all_tests())
        exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n测试被中断")
        exit(1)
    except Exception as e:
        print(f"\n\n测试出错: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
