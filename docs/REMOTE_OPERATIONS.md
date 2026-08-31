# 远程部署与运维

统一入口是 `scripts/remote_service.sh`，默认目标为 `orangepi@192.168.1.109`，默认安装目录为 `/opt/screencast`。

## 首次连接

建议先配置 SSH 公钥，避免把密码写入脚本：

```bash
ssh-copy-id orangepi@192.168.1.109
scripts/remote_service.sh check
```

也可以通过环境变量覆盖目标：

```bash
RK_HOST=192.168.1.109 RK_USER=orangepi scripts/remote_service.sh check
```

## 部署

板子首次安装系统依赖、GStreamer、服务用户和 systemd：

```bash
scripts/remote_service.sh install
```

上传当前 `backend/`、`frontend/` 和 `scripts/`，保留板端 `receiver_config.json`，然后重启服务：

```bash
scripts/remote_service.sh deploy
```

## 日常操作

```bash
scripts/remote_service.sh status
scripts/remote_service.sh start
scripts/remote_service.sh stop
scripts/remote_service.sh restart
scripts/remote_service.sh logs
scripts/remote_service.sh shell
```

`status` 会同时检查 systemd 状态和板端 `http://127.0.0.1:8080/health`。`logs` 持续跟踪 `screencast` 服务日志，使用 Ctrl-C 返回本机。

## RK3588 独立投屏局域网

当前板端已启用 NetworkManager AP：

```text
SSID: RK-Screencast
密码: RKcast2026
网关: 192.168.50.1
DHCP: 192.168.50.10 - 192.168.50.254
```

电脑连接该 Wi-Fi 后，可访问 `https://192.168.50.1:8080`（管理/发送页）或使用本地发送端连接 `ws://192.168.50.1:8081/ws`。有线地址 `192.168.1.109` 保留用于 SSH 调试。密码仅为当前开发默认值，产品化前必须更换并移出文档。
