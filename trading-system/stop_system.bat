@echo off
chcp 65001 >nul
echo ========================================
echo 停止MT5加密货币交易系统
echo ========================================
echo.

echo [1] 停止运行中的进程...

REM 停止Telegram Bot
taskkill /FI "WINDOWTITLE eq Trading Bot*" /F >nul 2>&1
if %errorlevel% == 0 (
    echo   - Trading Bot 已停止
) else (
    echo   - Trading Bot 未运行
)

REM 停止API Server
taskkill /FI "WINDOWTITLE eq Trading API*" /F >nul 2>&1
if %errorlevel% == 0 (
    echo   - API Server 已停止
) else (
    echo   - API Server 未运行
)

REM 备选方案：直接终止Python进程（如果窗口标题不匹配）
taskkill /FI "IMAGENAME eq python.exe" /FI "WINDOWTITLE eq *telegram_bot*" /F >nul 2>&1
taskkill /FI "IMAGENAME eq python.exe" /FI "WINDOWTITLE eq *server*" /F >nul 2>&1

echo.
echo ========================================
echo 系统已停止
echo ========================================
echo.
echo 如需重新启动:
echo   start_system.bat
echo.
pause
