"""
mDNS 设备发现服务
让发送端自动发现局域网内的投屏器
"""

import asyncio
import logging
import socket
import traceback
from typing import Dict, Optional

# 尝试导入 zeroconf
try:
    from zeroconf import ServiceInfo, Zeroconf
    HAS_ZEROCONF = True
except ImportError:
    HAS_ZEROCONF = False
    logging.warning("zeroconf 未安装，mDNS 服务不可用")

logger = logging.getLogger("mdns")


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

    def _start_sync(self):
        """在线程中同步启动 zeroconf (避免 EventLoopBlocked)"""
        try:
            local_ip = self.get_local_ip()
            hostname = socket.gethostname()
            logger.info(f"[mDNS-Adv] 准备广播: hostname={hostname}, local_ip={local_ip}, port={self.service_port}")

            type_ = "_screencast._tcp.local."
            name_ = f"{self.service_name}._screencast._tcp.local."
            self.info = ServiceInfo(
                type_,
                name_,
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

            logger.info(f"[mDNS-Adv] ServiceInfo 创建成功: type={type_}, name={name_}, addresses={local_ip}")
            self.zeroconf = Zeroconf()
            logger.info(f"[mDNS-Adv] Zeroconf 实例创建成功")
            self.zeroconf.register_service(self.info)
            logger.info(f"[mDNS-Adv] register_service 调用成功")

            # 注册后验证
            import time
            time.sleep(0.5)
            found = self.zeroconf.get_service_info(type_, name_)
            if found:
                ip = socket.inet_ntoa(found.addresses[0]) if found.addresses else found.parsed_addresses()[0]
                logger.info(f"[mDNS-Adv] 自查验证成功: {name_} -> {ip}:{found.port}")
            else:
                logger.warning(f"[mDNS-Adv] 自查验证失败: 立刻查询不到自己广播的服务")

            logger.info(f"[mDNS] 服务已广播: {name_}")
            return True

        except Exception as e:
            logger.error(f"[mDNS-Adv] 广播失败: {e}\n{traceback.format_exc()}")
            return False

    def start(self) -> bool:
        """启动 mDNS 广播"""
        if not HAS_ZEROCONF:
            logger.warning("[mDNS] zeroconf 不可用，跳过服务广播")
            return False

        import concurrent.futures
        pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        future = pool.submit(self._start_sync)
        try:
            return future.result(timeout=10)
        except Exception as e:
            logger.error(f"[mDNS-Adv] start 超时或失败: {e}")
            return False
        finally:
            pool.shutdown(wait=False)

    def stop(self):
        """停止 mDNS 广播"""
        if self.zeroconf and self.info:
            import concurrent.futures
            def _stop_sync():
                try:
                    self.zeroconf.unregister_service(self.info)
                    logger.info("[mDNS-Adv] unregister_service 调用成功")
                except Exception as e:
                    logger.error(f"[mDNS-Adv] unregister 失败: {e}")
                try:
                    self.zeroconf.close()
                    logger.info("[mDNS-Adv] close 调用成功")
                except Exception as e:
                    logger.error(f"[mDNS-Adv] close 失败: {e}")
                logger.info("[mDNS] 服务广播已停止")
            pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
            f = pool.submit(_stop_sync)
            try:
                f.result(timeout=5)
            except Exception as e:
                logger.error(f"[mDNS-Adv] stop 超时或失败: {e}")
            finally:
                pool.shutdown(wait=False)
            self.zeroconf = None
            self.info = None


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
            logger.warning("[mDNS-Disc] zeroconf 不可用，无法发现设备")
            return {}

        discovered = {}
        listener = DiscoveryListener(discovered)

        type_ = "_screencast._tcp.local."
        logger.info(f"[mDNS-Disc] 开始发现, timeout={timeout}s, type={type_}")

        try:
            self.zeroconf = Zeroconf()
            logger.info("[mDNS-Disc] Zeroconf 实例创建成功")
        except Exception as e:
            logger.error(f"[mDNS-Disc] Zeroconf 创建失败: {e}\n{traceback.format_exc()}")
            return {}

        try:
            browser = self.zeroconf.add_service_listener(type_, listener)
            logger.info(f"[mDNS-Disc] ServiceListener 已添加, listener={listener}")
        except Exception as e:
            logger.error(f"[mDNS-Disc] add_service_listener 失败: {e}\n{traceback.format_exc()}")
            return {}

        # 分段等待，记录中间状态
        elapsed = 0
        step = min(1.0, timeout)
        try:
            while elapsed < timeout:
                await asyncio.sleep(step)
                elapsed += step
                logger.info(f"[mDNS-Disc] 等待中... 已等待 {elapsed:.1f}s, 已发现 {len(discovered)} 个设备")
                if len(discovered) > 0 and elapsed >= 1.5:
                    # 已有结果且至少等了1.5秒，可以提前返回
                    logger.info(f"[mDNS-Disc] 已发现设备，提前结束等待")
                    break
        finally:
            try:
                self.zeroconf.remove_service_listener(browser)
                logger.info("[mDNS-Disc] ServiceListener 已移除")
            except Exception as e:
                logger.error(f"[mDNS-Disc] remove_service_listener 失败: {e}")
            try:
                self.zeroconf.close()
                logger.info("[mDNS-Disc] Zeroconf 已关闭")
            except Exception as e:
                logger.error(f"[mDNS-Disc] Zeroconf close 失败: {e}")

        if len(discovered) == 0:
            # 尝试用低层 API 查一下，看网络是否通
            try:
                logger.info("[mDNS-Disc] 未发现设备，尝试 browse_service 检查...")
                zc2 = Zeroconf()
                services = zc2.browse_services(type_, timeout=2000)
                logger.info(f"[mDNS-Disc] browse_services 返回: {services}")
                zc2.close()
            except Exception as e:
                logger.warning(f"[mDNS-Disc] browse_services 检查失败: {e}")

        logger.info(f"[mDNS-Disc] 发现结束, 共 {len(discovered)} 个设备: {list(discovered.keys())}")
        return discovered


if HAS_ZEROCONF:
    class DiscoveryListener:
        """服务发现监听器"""

        def __init__(self, services_dict: dict):
            self.services = services_dict

        def add_service(self, zc, type_: str, name: str) -> None:
            logger.info(f"[mDNS-Disc] add_service 回调触发: type={type_}, name={name}")
            try:
                info = zc.get_service_info(type_, name)
                logger.info(f"[mDNS-Disc] get_service_info 返回: {info}")
                if info:
                    if info.addresses:
                        ip = socket.inet_ntoa(info.addresses[0])
                    else:
                        ip = info.parsed_addresses()[0] if info.parsed_addresses() else "0.0.0.0"
                        logger.info(f"[mDNS-Disc] addresses 为空, 尝试 parsed_addresses: {info.parsed_addresses()}")
                    logger.info(f"[mDNS-Disc] 设备详情: name={name}, ip={ip}, port={info.port}, server={info.server}, properties={dict(info.properties.items())}")
                    self.services[name] = {
                        "name": name.replace("._screencast._tcp.local.", ""),
                        "host": ip,
                        "port": info.port,
                        "properties": dict(info.properties.items())
                    }
                    logger.info(f"[mDNS-Disc] 发现设备成功: {name} -> {ip}:{info.port}")
                else:
                    logger.warning(f"[mDNS-Disc] get_service_info 返回 None (type={type_}, name={name})")
            except Exception as e:
                logger.error(f"[mDNS-Disc] add_service 异常: {e}\n{traceback.format_exc()}")

        def remove_service(self, zc, type_: str, name: str) -> None:
            if name in self.services:
                del self.services[name]

        def update_service(self, zc, type_: str, name: str) -> None:
            logger.info(f"[mDNS-Disc] update_service 回调: type={type_}, name={name}")
            try:
                info = zc.get_service_info(type_, name)
                if info:
                    if info.addresses:
                        ip = socket.inet_ntoa(info.addresses[0])
                    else:
                        ip = info.parsed_addresses()[0] if info.parsed_addresses() else "0.0.0.0"
                    self.services[name] = {
                        "name": name.replace("._screencast._tcp.local.", ""),
                        "host": ip,
                        "port": info.port,
                        "properties": dict(info.properties.items())
                    }
                    logger.info(f"[mDNS-Disc] update_service 成功: {name} -> {ip}:{info.port}")
            except Exception as e:
                logger.error(f"[mDNS-Disc] update_service 异常: {e}\n{traceback.format_exc()}")


# 全局实例
mdns_advertiser = MDNSAdvertiser()


def start_mdns():
    """启动 mDNS 广播"""
    return mdns_advertiser.start()


def stop_mdns():
    """停止 mDNS 广播"""
    mdns_advertiser.stop()
