@echo off
chcp 65001 >nul
echo ========================================
echo MT5加密货币交易系统 - Windows VPS安装脚本
echo 版本: v2.3
echo ========================================
echo.

REM 检查Python是否安装
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到Python，请先安装Python 3.8+
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [1/6] 检测到Python版本:
python --version
echo.

REM 检查pip
pip --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到pip，请重新安装Python并勾选pip选项
    pause
    exit /b 1
)

echo [2/6] 安装Python依赖包...
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
if errorlevel 1 (
    echo [警告] 使用清华源安装失败，尝试官方源...
    pip install -r requirements.txt
)
echo.

echo [3/6] 创建必要的目录...
if not exist "logs" mkdir logs
if not exist "logs\trades" mkdir logs\trades
if not exist "cache" mkdir cache
if not exist "temp" mkdir temp
if not exist "data" mkdir data
if not exist "training\models" mkdir training\models
if not exist "training\models\proprietary" mkdir training\models\proprietary
if not exist "training\history" mkdir training\history
if not exist "shadow_trading" mkdir shadow_trading
echo 目录创建完成
echo.

echo [4/6] 运行配置向导...
python setup_wizard.py
if errorlevel 1 (
    echo [错误] 配置向导执行失败
    pause
    exit /b 1
)
echo.

echo [5/6] 检测VPS硬件配置并优化...
python vps\vps_config.py
echo.

echo [6/6] 安装Windows服务（可选）
echo.
choice /C YN /M "是否将交易系统安装为Windows服务自动启动"
if errorlevel 2 goto skip_service
if errorlevel 1 goto install_service

:install_service
echo 安装Windows服务...
pip install pywin32
python install_service.py
goto done

:skip_service
echo 跳过服务安装
echo.

:done
echo.
echo ========================================
echo 安装完成！
echo ========================================
echo.
echo 后续步骤:
echo 1. 安装MetaTrader 5 (如果交易外汇/黄金)
echo    下载: https://www.metatrader5.com/
echo.
echo 2. 将 mt5-ea/GoldTradingEA.mq5 复制到MT5的Experts目录
echo    通常路径: C:\Program Files\MetaTrader 5\MQL5\Experts\
echo.
echo 3. 启动交易系统:
echo    方式1: 双击 start_system.bat
echo    方式2: 运行 python bots/telegram_bot.py
echo.
echo 4. 查看日志:
echo    logs\ 目录下查看运行日志
echo.
echo 5. 访问API控制台:
echo    http://localhost:5000
echo.
pause
