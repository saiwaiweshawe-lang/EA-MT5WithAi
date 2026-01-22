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

# 运行快速系统自检
echo ""
echo "[2] 运行快速系统自检..."
python utilities/system_checker.py
if [ $? -ne 0 ]; then
    echo "[警告] 系统自检发现问题，但将继续启动"
fi
echo ""

# 检测服务器角色
echo "[3] 检测服务器角色..."
python -c "from utilities.server_role_manager import ServerRoleManager; m = ServerRoleManager(); print(f'服务器角色: {m.current_role}'); print(f'组件数量: {len(m.components)}')"
echo ""

# 根据服务器角色启动组件
echo "[4] 根据服务器角色启动组件..."
python component_launcher.py

echo ""
echo "========================================"
echo "系统启动完成！"
echo "========================================"
echo ""
echo "组件已根据服务器角色启动"
echo ""
echo "管理命令:"
echo "  查看组件状态: python component_launcher.py --status"
echo "  停止所有: ./stop_system.sh"
echo ""
echo "查看日志:"
echo "  tail -f logs/bot.log (如运行在此服务器)"
echo "  tail -f logs/api.log (如运行在此服务器)"
echo "  tail -f logs/performance/performance_*.jsonl"
echo ""
echo "访问API控制台:"
echo "  http://YOUR_VPS_IP:5000 (如运行在此服务器)"
echo ""
