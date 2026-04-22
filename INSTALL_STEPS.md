# C++ 开发环境安装 - 分步指南

## 当前状态检查

根据检查，你的系统已安装：
- ✅ Git 2.53.0

还需要安装：
- ❌ CMake
- ❌ Visual Studio Build Tools
- ❌ vcpkg
- ❌ FFmpeg/OpenSSL 依赖

---

## 方式一：一键安装（推荐）

### 步骤 1：右键点击开始菜单，选择 **Windows PowerShell (管理员)**

### 步骤 2：复制粘贴以下命令并按回车

```powershell
Set-ExecutionPolicy Bypass -Scope Process -Force
cd C:\Users\1000003244\Desktop\video_test\scripts
.\setup-cpp-env.ps1
```

### 步骤 3：按提示操作

脚本会自动检测并安装：
- CMake
- vcpkg
- FFmpeg、OpenSSL、nlohmann-json

如果提示需要 Visual Studio Build Tools，会自动打开下载页面。

---

## 方式二：手动安装

### 1. 安装 CMake

**方法 A - 使用脚本（推荐）：**

```cmd
C:\Users\1000003244\Desktop\video_test\scripts\install-cmake-simple.bat
```

**方法 B - 手动下载：**

1. 访问：https://github.com/Kitware/CMake/releases/download/v3.28.1/cmake-3.28.1-windows-x86_64.msi
2. 下载并运行安装程序
3. 安装时选择 **"Add CMake to the system PATH"**

---

### 2. 安装 Visual Studio Build Tools

1. 下载：https://aka.ms/vs/17/release/vs_BuildTools.exe
2. 运行安装程序
3. 选择 **"使用 C++ 的桌面开发"**
4. 确保勾选：
   - MSVC v143 生成工具
   - Windows 11 SDK (或 Windows 10 SDK)
   - CMake 工具

---

### 3. 安装 vcpkg

在 **PowerShell** 中运行：

```powershell
cd C:\
git clone https://github.com/Microsoft/vcpkg.git
cd vcpkg
.\bootstrap-vcpkg.bat
.\vcpkg integrate install
```

---

### 4. 安装项目依赖

```powershell
C:\vcpkg\vcpkg install ffmpeg:x64-windows openssl:x64-windows nlohmann-json:x64-windows
```

---

## 验证安装

打开新的命令提示符，运行：

```cmd
git --version
cmake --version
C:\vcpkg\vcpkg version
```

如果都显示版本信息，说明安装成功！

---

## 下一步

环境配置完成后，构建项目：

```cmd
cd C:\Users\1000003244\Desktop\video_test
scripts\build.bat
```
