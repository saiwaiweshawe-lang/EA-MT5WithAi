@echo off
chcp 65001 >nul
echo ========================================
echo 停止MT5加密货币交易系统
echo ========================================
echo.

echo [1] 使用组件启动器停止所有组件...
python component_launcher.py --stop

echo.
echo ========================================
echo 系统已停止
echo ========================================
echo.
echo 如需重新启动:
echo   start_system.bat
echo.
pause
