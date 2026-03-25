@echo off
chcp 65001 >nul
echo ========================================
echo   MT5加密货币交易系统 - EXE打包工具
echo ========================================
echo.

:: 检查Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到Python，请先安装 Python 3.8+
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

:: 检查pip
pip --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到pip，请重新安装Python
    pause
    exit /b 1
)

:: 安装依赖
echo [1/4] 安装依赖包...
pip install -r requirements.txt
if errorlevel 1 (
    echo [错误] 依赖安装失败
    pause
    exit /b 1
)

:: 安装PyInstaller
echo [2/4] 安装PyInstaller...
pip install pyinstaller
if errorlevel 1 (
    echo [错误] PyInstaller安装失败
    pause
    exit /b 1
)

:: 创建图标目录（如果不存在）
if not exist "icon" mkdir icon

:: 打包
echo [3/4] 正在打包，请稍候...
echo 注意：首次打包可能需要几分钟时间
pyinstaller trading_system.spec --clean

if errorlevel 1 (
    echo [错误] 打包失败
    pause
    exit /b 1
)

:: 完成
echo [4/4] 打包完成！
echo.
echo ========================================
echo   打包完成！
echo ========================================
echo.
echo EXE文件位置: dist\TradingSystem\TradingSystem.exe
echo.
echo 运行前请：
echo 1. 编辑 config\ 下的配置文件填入您的API密钥
echo 2. 确保 logs 和 data 目录存在
echo.
pause
