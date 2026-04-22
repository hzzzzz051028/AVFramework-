# Windows C++ 开发环境配置指南

## 自动安装脚本

以**管理员身份**运行 PowerShell，执行以下命令：

```powershell
# 设置脚本执行策略
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# 下载并运行配置脚本
irm https://raw.githubusercontent.com/Microsoft/vcpkg-tool/main/scripts/bootstrap.ps1 | iex
```

---

## 方法一：Visual Studio Build Tools（推荐）

### 1. 下载 Visual Studio Build Tools

访问 [visualstudio.microsoft.com/downloads](https://visualstudio.microsoft.com/downloads/)

下载 "Visual Studio 2022 Build Tools"（免费）

### 2. 安装组件

运行安装程序后，选择：

```
✅ 使用 C++ 的桌面开发
   - MSVC v143 - VS 2022 C++ x64/x86 生成工具
   - Windows 11 SDK（或 Windows 10 SDK）
   - CMake tools for Visual Studio
```

### 3. 验证安装

打开 **x64 Native Tools Command Prompt for VS 2022**：

```cmd
cl
cmake --version
```

---

## 方法二：MinGW-w64

### 1. 下载 MinGW-w64

访问 [github.com/niXman/mingw-builds-binaries/releases](https://github.com/niXman/mingw-builds-binaries/releases)

下载 `x86_64-posix-seh` 版本

### 2. 解压并配置

```powershell
# 解压到 C:\mingw64
# 添加到系统 PATH
[System.Environment]::SetEnvironmentVariable('Path', $env:Path + ';C:\mingw64\bin', 'User')
```

### 3. 验证

```cmd
gcc --version
g++ --version
```

---

## 安装 CMake

### Windows 安装包

1. 下载 [cmake.org/download](https://cmake.org/download/)
2. 安装时选择 "Add CMake to the system PATH"
3. 重启终端验证：`cmake --version`

### 或使用 Winget

```powershell
winget install Kitware.CMake
```

---

## 安装 vcpkg（C++ 包管理器）

vcpkg 用于安装 FFmpeg、OpenSSL 等依赖库。

### 1. 克隆 vcpkg

```powershell
cd C:\
git clone https://github.com/Microsoft/vcpkg.git
cd vcpkg
.\bootstrap-vcpkg.bat
```

### 2. 集成到系统

```powershell
.\vcpkg integrate install
```

### 3. 安装项目依赖

```powershell
# FFmpeg
.\vcpkg install ffmpeg:x64-windows

# OpenSSL
.\vcpkg install openssl:x64-windows

# nlohmann/json（JSON 库）
.\vcpkg install nlohmann-json:x64-windows
```

---

## 安装 Git

```powershell
winget install Git.Git
```

或访问 [git-scm.com](https://git-scm.com/)

---

## 项目构建配置

### 使用 Visual Studio (MSVC)

```cmd
cd backend
mkdir build
cd build
cmake .. -DCMAKE_TOOLCHAIN_FILE=C:/vcpkg/scripts/buildsystems/vcpkg.cmake
cmake --build . --config Release
```

### 使用 MinGW-w64

```cmd
cd backend
mkdir build
cd build
cmake .. -G "MinGW Makefiles"
cmake --build .
```

---

## 常见问题

### Q: cl 命令找不到？

**A:** 需要使用 VS 开发者命令提示符，或在常规终端中运行：

```cmd
"C:\Program Files\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat"
```

### Q: CMake 找不到编译器？

**A:** 指定生成器：

```cmd
# Visual Studio
cmake .. -G "Visual Studio 17 2022" -A x64

# MinGW
cmake .. -G "MinGW Makefiles"
```

### Q: vcpkg 安装失败？

**A:** 确保已安装 Git，并使用 PowerShell 运行：
```powershell
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process -Force
```

---

## 推荐的 IDE

| IDE | 特点 | 下载 |
|-----|------|------|
| Visual Studio Code | 轻量、插件丰富 | [code.visualstudio.com](https://code.visualstudio.com/) |
| Visual Studio 2022 | 功能全面、调试强大 | [visualstudio.microsoft.com](https://visualstudio.microsoft.com/) |
| CLion | JetBrains 出品 | [jetbrains.com/clion](https://www.jetbrains.com/clion/) |

### VS Code 配置

安装扩展：
- C/C++ (Microsoft)
- CMake Tools (Microsoft)
- vcpkg Configuration Helper

---

## 环境变量检查

```powershell
# 检查 PATH
echo $env:Path -split ';'

# 临时添加到 PATH
$env:Path += ";C:\mingw64\bin;C:\Program Files\CMake\bin"
```

---

## 下一步

环境配置完成后，可以运行项目构建脚本：

```cmd
cd C:\Users\1000003244\Desktop\video_test
scripts\build.bat
```
