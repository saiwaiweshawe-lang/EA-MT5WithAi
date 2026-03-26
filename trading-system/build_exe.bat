@echo off
chcp 65001 >nul
echo ============================================
echo   量化交易系统 v2.8 EXE 打包工具
echo ============================================
echo.

REM 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Python，请先安装 Python 3.8+
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)
echo [OK] Python 已安装

REM 检查 pip
pip --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 pip，请重新安装 Python
    pause
    exit /b 1
)
echo [OK] pip 已安装

REM 安装依赖
echo.
echo [步骤 1/4] 安装项目依赖...
pip install -r requirements.txt
if errorlevel 1 (
    echo [错误] 安装 requirements.txt 失败
    pause
    exit /b 1
)
echo [OK] 项目依赖安装完成

REM 安装 PyQt6
echo.
echo [步骤 2/4] 安装 PyQt6...
pip install PyQt6
if errorlevel 1 (
    echo [错误] 安装 PyQt6 失败
    pause
    exit /b 1
)
echo [OK] PyQt6 安装完成

REM 安装 PyInstaller
echo.
echo [步骤 3/4] 安装 PyInstaller...
pip install pyinstaller
if errorlevel 1 (
    echo [错误] 安装 PyInstaller 失败
    pause
    exit /b 1
)
echo [OK] PyInstaller 安装完成

REM 清理旧文件
echo.
echo [步骤 4/4] 清理旧构建文件...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist __pycache__ rmdir /s /q __pycache__
for /r %%i in (*.spec) do del "%%i"

REM 创建 spec 文件
echo.
echo [配置] 创建打包配置...
(
echo # -*- mode: python ; coding: utf-8 -*-
echo import sys
echo sys.setrecursionlimit(max(sys.getrecursionlimit(), 5000))
)> QuantTrader.spec

echo a = Analysis(['client/main.py']) >> QuantTrader.spec
echo a.scripts += [('client/*.py')] >> QuantTrader.spec

(
echo pyz = PYZ(a.pure, a.zipped_data, cipher=None^)
echo exe = EXE(
echo     pyz,
echo     a.scripts,
echo     a.binaries,
echo     a.zipfiles,
echo     a.datas,
echo     [],
echo     name='QuantTrader.exe',
echo     debug=False,
echo     bootloader_ignore_signals=False,
echo     strip=False,
echo     upx=True,
echo     console=False,
echo     disable_windowed_traceback=False,
echo     argv_emulation=False,
echo     target_arch=None,
echo     codesign_identity=None,
echo     entitlements_file=None,
echo     icon='icon.ico' if exist 'icon.ico' else None,
echo     distpath='dist',
echo     specpath='.',
echo     runtime_tmpdir=None,
echo     fullscreen=False,
echo     windowed=True,
echo ^)
) >> QuantTrader.spec

echo [OK] 打包配置已创建

REM 开始打包
echo.
echo ============================================
echo   开始打包，请稍候...
echo   首次打包可能需要 5-15 分钟
echo ============================================

pyinstaller QuantTrader.spec --clean

if errorlevel 1 (
    echo.
    echo [错误] 打包失败！
    pause
    exit /b 1
)

REM 复制配置文件
echo.
echo [完成] 复制配置文件...
if not exist "dist\config" mkdir "dist\config"
if exist "config\*.json" copy "config\*.json" "dist\config\"
if not exist "dist\news\config" mkdir "dist\news\config"
if exist "news\config\*.json" copy "news\config\*.json" "dist\news\config\"

REM 清理
del QuantTrader.spec >nul 2>&1

echo.
echo ============================================
echo   打包完成！
echo ============================================
echo.
echo EXE 文件位置: dist\QuantTrader.exe
echo.
echo 运行说明：
echo 1. 双击 QuantTrader.exe 启动
echo 2. 首次使用需要配置 MT5 和交易所 API
echo 3. 详细说明见 HELP.md
echo.
echo 配置文件已复制到 dist\config 目录
echo.
pause
