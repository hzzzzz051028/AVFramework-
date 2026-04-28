"""
mDNS 设备发现服务
让发送端自动发现局域网内的投屏器
"""

import asyncio
import logging
import socket
from typing import Dict, Optional

# 尝试导入 zeroconf
try:
    from zeroconf import ServiceInfo, Zeroconf
    HAS_ZEROCONF = True
except ImportError:
    HAS_ZEROCONF = False
    logging.warning("zeroconf 未安装，mDNS 服务不可用")

logger = logging.getLogger(__name__)


class MDNSAdvertiser:
    """mDNS 服务广播 - 在接收端（RK3588）运行"""

    def __init__(self, service_name: str = "screencast", service_port: int = 8080):
        self.service_name = service_name
        self.service_port = service_port
        self.zeroconf = None
        self.info = None

    def get_local_ip(self) -> str:
        """获取本机 IP 地址"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    def start(self) -> bool:
        """启动 mDNS 广播"""
        if not HAS_ZEROCONF:
            logger.warning("[mDNS] zeroconf 不可用，跳过服务广播")
            return False

        try:
            local_ip = self.get_local_ip()
            hostname = socket.gethostname()

            # 创建服务信息
            self.info = ServiceInfo(
                "_screencast._tcp.local.",
                f"{self.service_name}._screencast._tcp.local.",
                addresses=[socket.inet_aton(local_ip)],
                port=self.service_port,
                properties={
                    "version": "3.0.0",
                    "hostname": hostname,
                    "platform": "RK3588",
                    "max_sessions": "4"
                },
                server=f"{hostname}.local."
            )

            self.zeroconf = Zeroconf()
            self.zeroconf.register_service(self.info)

            logger.info(f"[mDNS] 服务已广播: {self.service_name}._screencast._tcp.local.")
            logger.info(f"[mDNS] 本机地址: {local_ip}:{self.service_port}")
            return True

        except Exception as e:
            logger.error(f"[mDNS] 广播失败: {e}")
            return False

    def stop(self):
        """停止 mDNS 广播"""
        if self.zeroconf and self.info:
            self.zeroconf.unregister_service(self.info)
            self.zeroconf.close()
            logger.info("[mDNS] 服务广播已停止")


class MDNSDiscovery:
    """mDNS 服务发现 - 在发送端（浏览器）运行"""

    def __init__(self):
        self.zeroconf = None
        self.services = {}

    async def discover(self, timeout: float = 3.0) -> Dict[str, dict]:
        """发现局域网内的投屏器 (async, 不阻塞事件循环)

        返回: {service_name: {name, host, port, properties}}
        """
        if not HAS_ZEROCONF:
            return {}

        discovered = {}
        listener = DiscoveryListener(discovered)

        self.zeroconf = Zeroconf()
        browser = self.zeroconf.add_service_listener("_screencast._tcp.local.", listener)

        try:
            await asyncio.sleep(timeout)
        finally:
            self.zeroconf.remove_service_listener(browser)
            self.zeroconf.close()

        logger.info(f"[mDNS] 发现 {len(discovered)} 个设备")
        return discovered


if HAS_ZEROCONF:
    class DiscoveryListener:
        """服务发现监听器"""

        def __init__(self, services_dict: dict):
            self.services = services_dict

        def add_service(self, zc, type_: str, name: str) -> None:
            info = zc.get_service_info(type_, name)
            if info:
                self.services[name] = {
                    "name": name.replace("._screencast._tcp.local.", ""),
                    "host": socket.inet_ntoa(info.addresses[0]),
                    "port": info.port,
                    "properties": dict(info.properties.items())
                }
                logger.info(f"[mDNS] 发现设备: {name}")

        def remove_service(self, zc, type_: str, name: str) -> None:
            if name in self.services:
                del self.services[name]

        def update_service(self, zc, type_: str, name: str) -> None:
            info = zc.get_service_info(type_, name)
            if info:
                self.services[name] = {
                    "name": name.replace("._screencast._tcp.local.", ""),
                    "host": socket.inet_ntoa(info.addresses[0]),
                    "port": info.port,
                    "properties": dict(info.properties.items())
                }
                logger.info(f"[mDNS] 发现设备: {name}")


# 全局实例
mdns_advertiser = MDNSAdvertiser()


def start_mdns():
    """启动 mDNS 广播"""
    return mdns_advertiser.start()


def stop_mdns():
    """停止 mDNS 广播"""
    mdns_advertiser.stop()
