#!/bin/bash

# 停止MT5加密货币交易系统

echo "停止MT5加密货币交易系统..."
echo ""

# 获取脚本所在目录
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# 检查是否使用了systemd服务
if systemctl is-active --quiet trading-bot || systemctl is-active --quiet trading-api 2>/dev/null; then
    echo "[1] 检测到systemd服务，停止服务..."

    if systemctl is-active --quiet trading-bot 2>/dev/null; then
        sudo systemctl stop trading-bot
        echo "  - trading-bot 服务已停止"
    fi

    if systemctl is-active --quiet trading-api 2>/dev/null; then
        sudo systemctl stop trading-api
        echo "  - trading-api 服务已停止"
    fi

    echo ""
    echo "系统已停止"
    exit 0
fi

# 使用统一的组件启动器停止所有组件
echo "[1] 使用组件启动器停止所有组件..."
python component_launcher.py --stop

echo ""
echo "========================================"
echo "系统已停止"
echo "========================================"
echo ""
echo "如需重新启动:"
echo "  ./start_system.sh"
echo ""
