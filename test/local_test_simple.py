"""
简化版本地功能测试
避免编码问题，专注核心功能验证
"""

import asyncio
import requests
import websockets
import json


async def test_http_apis():
    """测试 HTTP API"""
    print("=" * 60)
    print("HTTP API 测试")
    print("=" * 60)

    tests_passed = []
    tests_failed = []

    # 1. 健康检查
    try:
        response = requests.get("http://localhost:8080/health", timeout=5)
        assert response.status_code == 200
        data = response.json()
        print(f"[PASS] Health check: GST={data.get('gst_available')}, Sessions={data.get('sessions')}")
        tests_passed.append("health")
    except Exception as e:
        print(f"[FAIL] Health check: {e}")
        tests_failed.append("health")

    # 2. 服务器信息
    try:
        response = requests.get("http://localhost:8080/info", timeout=5)
        assert response.status_code == 200
        data = response.json()
        print(f"[PASS] Server info: {data.get('server')}, IP={data.get('local_ip')}")
        tests_passed.append("info")
    except Exception as e:
        print(f"[FAIL] Server info: {e}")
        tests_failed.append("info")

    # 3. 设备发现
    try:
        response = requests.get("http://localhost:8080/api/discover", timeout=5)
        assert response.status_code == 200
        data = response.json()
        device_count = len(data.get("devices", []))
        print(f"[PASS] Device discovery: found {device_count} devices")
        tests_passed.append("discover")
    except Exception as e:
        print(f"[FAIL] Device discovery: {e}")
        tests_failed.append("discover")

    # 4. 状态查询
    try:
        response = requests.get("http://localhost:8080/api/status", timeout=5)
        assert response.status_code == 200
        data = response.json()
        platform = data.get("hardware", {}).get("platform", "Unknown")
        print(f"[PASS] Status API: platform={platform}")
        tests_passed.append("status")
    except Exception as e:
        print(f"[FAIL] Status API: {e}")
        tests_failed.append("status")

    # 5. 静态文件
    files_to_test = ["/sender.html", "/view.html", "/dashboard.html", "/terminal-view.html"]
    all_ok = True
    for file in files_to_test:
        try:
            response = requests.get(f"http://localhost:8080{file}", timeout=5)
            if response.status_code == 200:
                print(f"[PASS] Static file: {file}")
                tests_passed.append(f"static{file}")
            else:
                print(f"[FAIL] Static file: {file} returned {response.status_code}")
                tests_failed.append(f"static{file}")
                all_ok = False
        except Exception as e:
            print(f"[FAIL] Static file: {file} error: {e}")
            tests_failed.append(f"static{file}")
            all_ok = False

    print(f"\nHTTP API: {len(tests_passed)} passed, {len(tests_failed)} failed")
    return tests_passed, tests_failed


async def test_websocket():
    """测试 WebSocket 连接"""
    print("\n" + "=" * 60)
    print("WebSocket 测试")
    print("=" * 60)

    tests_passed = []
    tests_failed = []

    # 1. 主 WebSocket
    try:
        async with websockets.connect("ws://localhost:8080/ws") as ws:
            await ws.send(json.dumps({"type": "ping"}))
            response = await asyncio.wait_for(ws.recv(), timeout=5.0)
            data = json.loads(response)
            assert data.get("type") == "pong"
            print(f"[PASS] Main WebSocket: ping/pong working")
            tests_passed.append("ws_main")
    except Exception as e:
        print(f"[FAIL] Main WebSocket: {e}")
        tests_failed.append("ws_main")

    # 2. 终端 WebSocket
    try:
        async with websockets.connect("ws://localhost:8080/ws/terminal") as ws:
            response = await asyncio.wait_for(ws.recv(), timeout=5.0)
            data = json.loads(response)
            assert data.get("type") == "connected"
            print(f"[PASS] Terminal WebSocket: connected message received")
            tests_passed.append("ws_terminal")
    except Exception as e:
        print(f"[FAIL] Terminal WebSocket: {e}")
        tests_failed.append("ws_terminal")

    print(f"\nWebSocket: {len(tests_passed)} passed, {len(tests_failed)} failed")
    return tests_passed, tests_failed


async def main():
    print("=" * 60)
    print("  Local Functionality Test")
    print("=" * 60)
    print(f"Target: http://localhost:8080")
    print(f"Time: {asyncio.get_event_loop().time()}")
    print()

    http_passed, http_failed = await test_http_apis()
    ws_passed, ws_failed = await test_websocket()

    total_passed = len(http_passed) + len(ws_passed)
    total_failed = len(http_failed) + len(ws_failed)

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total Passed: {total_passed}")
    print(f"Total Failed: {total_failed}")

    if total_failed > 0:
        print(f"\nFailed tests:")
        for test in http_failed + ws_failed:
            print(f"  - {test}")

    success = total_failed == 0
    if success:
        print("\n[SUCCESS] All tests passed!")
    else:
        print("\n[WARNING] Some tests failed. Check output above.")

    return success


if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n[Test interrupted]")
        exit(1)
    except Exception as e:
        print(f"\n[ERROR] Test error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
