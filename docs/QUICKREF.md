# C++ 开发环境快速参考

## 🚀 快速安装（推荐）

### 自动安装脚本

```powershell
# 以管理员身份运行 PowerShell
cd C:\Users\1000003244\Desktop\video_test\scripts
.\install-dev-env.ps1
```

---

## 📦 手动安装清单

| 工具 | 用途 | 安装方式 |
|------|------|----------|
| Git | 版本控制 | `winget install Git.Git` |
| CMake | 构建工具 | `winget install Kitware.CMake` |
| VS Build Tools | C++ 编译器 | [下载](https://aka.ms/vs/17/release/vs_BuildTools.exe) |
| vcpkg | 包管理器 | `git clone https://github.com/Microsoft/vcpkg.git C:\vcpkg` |

---

## 🔧 安装命令汇总

```powershell
# 一行安装所有工具（需 winget）
winget install Git.Git Kitware.CMake --accept-source-agreements

# 安装 vcpkg
git clone https://github.com/Microsoft/vcpkg.git C:\vcpkg
cd C:\vcpkg
.\bootstrap-vcpkg.bat
.\vcpkg integrate install

# 安装 FFmpeg 等依赖
.\vcpkg install ffmpeg:x64-windows openssl:x64-windows nlohmann-json:x64-windows
```

---

## 🎯 验证安装

```powershell
# 检查版本
git --version
cmake --version

# 检查 vcpkg
C:\vcpkg\vcpkg version

# 检查编译器 (VS 开发者命令提示符)
cl
```

---

## 📝 常用命令

### 项目构建

```cmd
# Visual Studio (推荐)
cd backend\build
cmake .. -DCMAKE_TOOLCHAIN_FILE=C:/vcpkg/scripts/buildsystems/vcpkg.cmake
cmake --build . --config Release

# 或使用项目脚本
scripts\build.bat
```

### 依赖管理

```cmd
# 搜索包
C:\vcpkg\vcpkg search ffmpeg

# 安装包
C:\vcpkg\vcpkg install ffmpeg:x64-windows

# 列出已安装
C:\vcpkg\vcpkg list
```

---

## ⚠️ 常见问题

| 问题 | 解决方案 |
|------|----------|
| `cl` 命令找不到 | 使用 VS 开发者命令提示符 |
| CMake 找不到编译器 | `-G "Visual Studio 17 2022" -A x64` |
| vcpkg 构建失败 | 确保已安装 Visual Studio 2022 |
| 环境变量未生效 | 重启终端或运行 `cpp-dev-env.cmd` |

---

## 📚 有用的链接

- [vcpkg 包搜索](https://vcpkg.link/)
- [CMake 文档](https://cmake.org/documentation/)
- [MSVC 文档](https://docs.microsoft.com/cpp/)
