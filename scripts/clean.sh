#!/bin/bash

echo "========================================"
echo "   Cleaning Project - Removing Redundant Files"
echo "========================================"
echo ""

PROJECT_DIR="/c/Users/1000003244/Desktop/video_test"

# 删除构建产物
echo "[1/6] Removing build artifacts..."
rm -rf "$PROJECT_DIR/backend/build"
rm -rf "$PROJECT_DIR/backend/test_build"
rm -rf "$PROJECT_DIR/frontend/node_modules"
rm -rf "$PROJECT_DIR/frontend/dist"
echo "  ✓ Build artifacts removed"

# 删除临时文件
echo "[2/6] Removing temporary files..."
rm -rf "$PROJECT_DIR/backend/temp"
rm -rf "$PROJECT_DIR/backend/hls"
find "$PROJECT_DIR" -type f -name "*.log" -delete 2>/dev/null
find "$PROJECT_DIR" -type f -name "*.tmp" -delete 2>/dev/null
echo "  ✓ Temporary files removed"

# 删除测试文件
echo "[3/6] Removing test files..."
rm -f "$PROJECT_DIR/backend/src/demo_main.cpp"
rm -f "$PROJECT_DIR/backend/test_main.cpp"
rm -f "$PROJECT_DIR/backend/CMakeLists.test.txt"
echo "  ✓ Test files removed"

# 删除可执行文件和 DLL
echo "[4/6] Removing executables and DLLs..."
find "$PROJECT_DIR/backend" -type f -name "*.exe" -delete 2>/dev/null
find "$PROJECT_DIR/backend" -type f -name "*.dll" -delete 2>/dev/null
find "$PROJECT_DIR/backend" -type f -name "*.obj" -delete 2>/dev/null
find "$PROJECT_DIR/backend" -type f -name "*.o" -delete 2>/dev/null
echo "  ✓ Executables and DLLs removed"

# 删除编辑器临时文件
echo "[5/6] Removing editor temporary files..."
find "$PROJECT_DIR" -type f -name "*.swp" -delete 2>/dev/null
find "$PROJECT_DIR" -type f -name "*.swo" -delete 2>/dev/null
find "$PROJECT_DIR" -type f -name "*~" -delete 2>/dev/null
find "$PROJECT_DIR" -type f -name ".DS_Store" -delete 2>/dev/null
echo "  ✓ Editor files removed"

# 删除空的 .claude 目录（如果存在）
echo "[6/6] Cleaning Claude Code workspace..."
rm -rf "$PROJECT_DIR/.claude" 2>/dev/null
echo "  ✓ Workspace cleaned"

echo ""
echo "========================================"
echo "   Cleanup Complete!"
echo "========================================"
echo ""
echo "Remaining directories:"
echo "  • backend/src/     - Source code"
echo "  • backend/include/ - Header files"
echo "  • frontend/src/    - Frontend source"
echo "  • scripts/         - Build scripts"
echo "  • docs/            - Documentation"
echo ""
