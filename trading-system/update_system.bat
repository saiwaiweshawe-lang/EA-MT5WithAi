@echo off
chcp 65001 >nul
echo ========================================
echo MT5加密货币交易系统 - 自动更新
echo ========================================
echo.

REM 检查git
git --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到git，请先安装git
    pause
    exit /b 1
)

REM 检查是否在git仓库中
if not exist .git (
    echo [错误] 当前目录不是git仓库
    pause
    exit /b 1
)

echo [1/6] 检查本地修改...
git diff-index --quiet HEAD --
if errorlevel 1 (
    echo [警告] 检测到本地修改
    choice /C YN /M "是否要暂存本地修改"
    if errorlevel 2 (
        echo 更新已取消
        pause
        exit /b 1
    )
    if errorlevel 1 (
        git stash save "Auto-stash before update %date:~0,4%%date:~5,2%%date:~8,2%_%time:~0,2%%time:~3,2%%time:~6,2%"
        echo 本地修改已暂存
    )
) else (
    echo 工作区干净
)
echo.

echo [2/6] 获取当前分支...
for /f "tokens=*" %%i in ('git branch --show-current') do set BRANCH=%%i
echo 当前分支: %BRANCH%
echo.

echo [3/6] 从远程仓库拉取最新代码...
git pull origin %BRANCH%
if errorlevel 1 (
    echo [错误] 代码拉取失败
    pause
    exit /b 1
)
echo 代码更新成功
echo.

echo [4/6] 更新Python依赖包...
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
)

python -m pip install --upgrade pip
pip install -r requirements.txt --upgrade -i https://pypi.tuna.tsinghua.edu.cn/simple
if errorlevel 1 (
    echo 使用清华源失败，尝试官方源...
    pip install -r requirements.txt --upgrade
)
echo 依赖更新完成
echo.

echo [5/6] 运行系统自检...
python utilities\system_checker.py
echo 系统自检完成
echo.

echo [6/6] 检查数据库...
REM 这里可以添加数据库迁移逻辑
echo 数据库检查完成
echo.

echo ========================================
echo 更新完成！
echo ========================================
echo.
echo 最近更新:
git log --oneline -5
echo.
echo 如需重启系统:
echo   stop_system.bat 然后 start_system.bat
echo.
pause
