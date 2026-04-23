# 屏幕共享系统 - 局域网快速使用指南

## 一句话说明

在主机上运行服务器，局域网内其他设备直接在浏览器输入 `http://主机IP:8080` 即可访问。

---

## 使用步骤

### 1. 启动服务器（在主机上）

```powershell
cd C:\Users\1000003244\Desktop\video_test
scripts\run-screenshare.bat
```

服务器窗口会显示：
```
========================================
   Screen Share Signaling Server v2.0
========================================

[LAN Access]
  Your IP:         10.10.30.213
  Web Interface:   http://10.10.30.213:8080
  WebSocket:       ws://10.10.30.213:8081
```

### 2. 共享屏幕（在主机上）

1. 主机浏览器自动打开，或手动访问：`http://10.10.30.213:8080`
2. 点击"🎬 开始共享"
3. 选择屏幕/窗口
4. 复制会话 ID（例如：`sess_abc123`）

### 3. 观看屏幕（在其他设备上）

1. 其他设备的浏览器访问：`http://10.10.30.213:8080`
2. 切换到"📥 观看屏幕"模式
3. 输入会话 ID：`sess_abc123`
4. 点击"🔗 连接"

---

## 完成！

就这么简单。不需要复制文件，不需要手动配置，打开网页就能用。

---

## 防火墙问题

如果其他设备无法访问，运行：

```powershell
New-NetFirewallRule -DisplayName "Screen Share" -Direction Inbound -Protocol TCP -LocalPort 8080,8081 -Action Allow
```

（以管理员身份运行 PowerShell）

---

## 查看本机 IP

```powershell
ipconfig
```

找到"IPv4 地址"，例如：`10.10.30.213`
