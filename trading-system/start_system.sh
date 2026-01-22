#!/bin/bash

# 启动MT5加密货币交易系统

echo "启动MT5加密货币交易系统..."
echo ""

# 激活虚拟环境
if [ -d "venv" ]; then
    source venv/bin/activate
    echo "[1] 虚拟环境已激活"
else
    echo "[警告] 未检测到虚拟环境，使用系统Python"
fi

# 检查screen是否安装
if ! command -v screen &> /dev/null; then
    echo "[警告] 未安装screen，建议安装: sudo apt install screen"
    echo "将在前台运行..."
    echo ""
    python bots/telegram_bot.py
    exit 0
fi

# 使用screen在后台运行
echo "[2] 在screen中启动Telegram机器人..."
screen -dmS trading-bot bash -c "source venv/bin/activate 2>/dev/null; python bots/telegram_bot.py"

sleep 2

echo "[3] 在screen中启动API服务器..."
screen -dmS trading-api bash -c "source venv/bin/activate 2>/dev/null; python api/server.py"

echo ""
echo "========================================"
echo "系统启动完成！"
echo "========================================"
echo ""
echo "后台进程:"
echo "  - trading-bot (Telegram机器人)"
echo "  - trading-api (API服务器)"
echo ""
echo "管理命令:"
echo "  查看进程: screen -ls"
echo "  进入bot: screen -r trading-bot"
echo "  进入api: screen -r trading-api"
echo "  离开screen: Ctrl+A+D"
echo "  停止所有: ./stop_system.sh"
echo ""
echo "查看日志:"
echo "  tail -f logs/bot.log"
echo "  tail -f logs/api.log"
echo ""
echo "访问API控制台:"
echo "  http://YOUR_VPS_IP:5000"
echo ""
