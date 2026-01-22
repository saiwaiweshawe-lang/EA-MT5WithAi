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

echo [3] 启动Telegram机器人...
start "Trading Bot" python bots\telegram_bot.py

timeout /t 3 >nul

echo [4] 启动API服务器...
start "Trading API" python api\server.py

echo.
echo ========================================
echo 系统启动完成！
echo ========================================
echo.
echo Telegram机器人和API服务器已在后台运行
echo.
echo 查看日志:
echo   - logs\bot.log
echo   - logs\api.log
echo.
echo 访问API控制台:
echo   - http://localhost:5000
echo.
echo 按任意键退出此窗口(不会关闭交易系统)
pause >nul
