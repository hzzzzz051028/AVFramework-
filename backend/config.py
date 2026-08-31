"""无线投屏接收器 - 配置管理"""

import json
import os
from pathlib import Path

CONFIG_DIR = Path(__file__).parent
CONFIG_FILE = CONFIG_DIR / "receiver_config.json"

# 默认配置
DEFAULTS = {
    "server": {
        "host": "0.0.0.0",
        "http_port": 8080,
        "ws_port": 8081,
    },
    "display": {
        "width": 1920,
        "height": 1080,
        "framerate": 30,
        "rotation": 0,
        "layout": "auto",
    },
    "webrtc": {
        "max_sessions": 4,
        "preferred_codec": "H264",
        "ice_servers": [],
    },
    "audio": {
        "enabled": True,
        "master_volume": 80,
        "output_device": "auto",
    },
    "hardware": {
        "hw_decode": True,
        "hw_scale": True,
        "drm_connector": "auto",
    },
    "network": {
        "device_name": "RK Wireless Display",
        "ap_ssid": "RK-Screencast",
        "ap_password": "RKcast2026",
        "ap_address": "192.168.50.1",
    },
}


class Config:
    def __init__(self):
        self._data = dict(DEFAULTS)
        self._load()

    def _load(self):
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                self._deep_merge(self._data, saved)
            except Exception:
                pass

    def _deep_merge(self, base, override):
        for k, v in override.items():
            if k in base and isinstance(base[k], dict) and isinstance(v, dict):
                self._deep_merge(base[k], v)
            else:
                base[k] = v

    def save(self):
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)

    def get(self, *keys, default=None):
        node = self._data
        for k in keys:
            if isinstance(node, dict) and k in node:
                node = node[k]
            else:
                return default
        return node

    def set(self, *keys_and_value):
        if len(keys_and_value) < 2:
            return
        *keys, value = keys_and_value
        node = self._data
        for k in keys[:-1]:
            if k not in node or not isinstance(node[k], dict):
                node[k] = {}
            node = node[k]
        node[keys[-1]] = value

    @property
    def server_host(self):
        return self.get("server", "host")

    @property
    def http_port(self):
        return self.get("server", "http_port")

    @property
    def ws_port(self):
        return self.get("server", "ws_port")

    @property
    def display_width(self):
        return self.get("display", "width")

    @property
    def display_height(self):
        return self.get("display", "height")

    @property
    def framerate(self):
        return self.get("display", "framerate")

    @property
    def layout(self):
        return self.get("display", "layout")

    @property
    def max_sessions(self):
        return self.get("webrtc", "max_sessions")

    @property
    def preferred_codec(self):
        return self.get("webrtc", "preferred_codec")

    @property
    def ice_servers(self):
        return self.get("webrtc", "ice_servers")

    @property
    def audio_enabled(self):
        return self.get("audio", "enabled")

    @property
    def master_volume(self):
        return self.get("audio", "master_volume")

    @property
    def hw_decode(self):
        return self.get("hardware", "hw_decode")

    @property
    def hw_scale(self):
        return self.get("hardware", "hw_scale")

    @property
    def drm_connector(self):
        return self.get("hardware", "drm_connector")

    @property
    def device_name(self):
        return self.get("network", "device_name")

    @property
    def ap_ssid(self):
        return self.get("network", "ap_ssid")

    @property
    def ap_password(self):
        return self.get("network", "ap_password")

    @property
    def ap_address(self):
        return self.get("network", "ap_address")


config = Config()
