#!/bin/bash

# 停止MT5加密货币交易系统

echo "停止MT5加密货币交易系统..."
echo ""

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

# 检查screen进程
if command -v screen &> /dev/null; then
    echo "[1] 停止screen进程..."

    # 停止trading-bot
    if screen -ls | grep -q "trading-bot"; then
        screen -S trading-bot -X quit
        echo "  - trading-bot 已停止"
    else
        echo "  - trading-bot 未运行"
    fi

    # 停止trading-api
    if screen -ls | grep -q "trading-api"; then
        screen -S trading-api -X quit
        echo "  - trading-api 已停止"
    else
        echo "  - trading-api 未运行"
    fi
else
    echo "[1] 未找到screen，尝试直接终止进程..."

    # 查找并终止Python进程
    pkill -f "python.*telegram_bot.py" && echo "  - Telegram Bot 已停止" || echo "  - Telegram Bot 未运行"
    pkill -f "python.*api/server.py" && echo "  - API Server 已停止" || echo "  - API Server 未运行"
fi

echo ""
echo "========================================"
echo "系统已停止"
echo "========================================"
echo ""
echo "如需重新启动:"
echo "  ./start_system.sh"
echo ""
