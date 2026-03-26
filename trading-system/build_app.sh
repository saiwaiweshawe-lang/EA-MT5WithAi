#!/bin/bash

echo "============================================"
echo "  量化交易系统 v2.8 打包工具"
echo "============================================"
echo ""

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "[错误] 未检测到 Python，请先安装 Python 3.8+"
    echo "下载地址: https://www.python.org/downloads/"
    exit 1
fi

echo "[OK] Python 已安装: $(python3 --version)"

# 检查 pip
if ! command -v pip3 &> /dev/null; then
    echo "[错误] 未检测到 pip，请重新安装 Python"
    exit 1
fi

echo "[OK] pip 已安装"

# 安装依赖
echo ""
echo "[步骤 1/4] 安装项目依赖..."
pip3 install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "[错误] 安装 requirements.txt 失败"
    exit 1
fi
echo "[OK] 项目依赖安装完成"

# 安装 PyQt6
echo ""
echo "[步骤 2/4] 安装 PyQt6..."
pip3 install PyQt6
if [ $? -ne 0 ]; then
    echo "[错误] 安装 PyQt6 失败"
    exit 1
fi
echo "[OK] PyQt6 安装完成"

# 安装 PyInstaller
echo ""
echo "[步骤 3/4] 安装 PyInstaller..."
pip3 install pyinstaller
if [ $? -ne 0 ]; then
    echo "[错误] 安装 PyInstaller 失败"
    exit 1
fi
echo "[OK] PyInstaller 安装完成"

# 清理旧文件
echo ""
echo "[步骤 4/4] 清理旧构建文件..."
rm -rf build dist __pycache__ *.spec
rm -rf client/__pycache__ client/*/__pycache__
rm -rf news/__pycache__ news/*/__pycache__

# 开始打包
echo ""
echo "============================================"
echo "  开始打包，请稍候..."
echo "  首次打包可能需要 5-15 分钟"
echo "============================================"
echo ""

pyinstaller --windowed --name QuantTrader client/main.py

if [ $? -ne 0 ]; then
    echo ""
    echo "[错误] 打包失败！"
    exit 1
fi

# 复制配置文件
echo ""
echo "[完成] 复制配置文件..."
mkdir -p dist/config
mkdir -p dist/news/config
cp -n config/*.json dist/config/ 2>/dev/null || true
cp -n news/config/*.json dist/news/config/ 2>/dev/null || true

echo ""
echo "============================================"
echo "  打包完成！"
echo "============================================"
echo ""
echo "APP 文件位置: dist/QuantTrader.app"
echo ""
echo "运行说明："
echo "1. 双击 QuantTrader.app 启动"
echo "2. 首次使用需要配置 MT5 和交易所 API"
echo "3. 详细说明见 HELP.md"
echo ""
