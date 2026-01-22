@echo off
chcp 65001 >nul
echo ========================================
echo 启动MT5加密货币交易系统
echo ========================================
echo.

REM 检查虚拟环境
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
    echo [1] 虚拟环境已激活
) else (
    echo [警告] 未检测到虚拟环境，使用系统Python
)
echo.

echo [2] 运行快速系统自检...
python utilities\system_checker.py
if errorlevel 1 (
    echo [警告] 系统自检发现问题，但将继续启动
)
echo.

echo [3] 检测服务器角色...
python -c "from utilities.server_role_manager import ServerRoleManager; m = ServerRoleManager(); print(f'服务器角色: {m.current_role}'); print(f'组件数量: {len(m.components)}')"
echo.

echo [4] 根据服务器角色启动组件...
python component_launcher.py
echo.

echo.
echo ========================================
echo 系统启动完成！
echo ========================================
echo.
echo 组件已根据服务器角色启动
echo.
echo 查看组件状态:
echo   python component_launcher.py --status
echo.
echo 查看日志:
echo   - logs\bot.log (如运行在此服务器)
echo   - logs\api.log (如运行在此服务器)
echo   - logs\performance\performance_*.jsonl
echo.
echo 访问API控制台:
echo   - http://localhost:5000 (如运行在此服务器)
echo.
echo 按任意键退出此窗口(不会关闭交易系统)
pause >nul
