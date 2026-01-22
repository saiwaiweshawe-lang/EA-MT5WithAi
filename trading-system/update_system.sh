#!/bin/bash

# 自动更新MT5加密货币交易系统

set -e

echo "========================================"
echo "MT5加密货币交易系统 - 自动更新"
echo "========================================"
echo ""

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 检查是否在git仓库中
if [ ! -d ".git" ]; then
    echo -e "${RED}[错误] 当前目录不是git仓库${NC}"
    exit 1
fi

# 保存当前工作状态
echo "[1/6] 检查本地修改..."
if ! git diff-index --quiet HEAD --; then
    echo -e "${YELLOW}[警告] 检测到本地修改${NC}"
    read -p "是否要暂存(stash)本地修改? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        git stash save "Auto-stash before update $(date +%Y%m%d_%H%M%S)"
        echo -e "${GREEN}本地修改已暂存${NC}"
    else
        echo -e "${RED}更新已取消${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}工作区干净${NC}"
fi

# 获取当前分支
CURRENT_BRANCH=$(git branch --show-current)
echo ""
echo "[2/6] 当前分支: $CURRENT_BRANCH"

# 从远程拉取最新代码
echo ""
echo "[3/6] 从远程仓库拉取最新代码..."
if git pull origin $CURRENT_BRANCH; then
    echo -e "${GREEN}代码更新成功${NC}"
else
    echo -e "${RED}[错误] 代码拉取失败${NC}"
    exit 1
fi

# 更新Python依赖
echo ""
echo "[4/6] 更新Python依赖包..."
if [ -d "venv" ]; then
    source venv/bin/activate
fi

pip install --upgrade pip
pip install -r requirements.txt --upgrade -i https://pypi.tuna.tsinghua.edu.cn/simple || \
    pip install -r requirements.txt --upgrade

echo -e "${GREEN}依赖更新完成${NC}"

# 运行系统自检
echo ""
echo "[5/6] 运行系统自检..."
python utilities/system_checker.py
echo -e "${GREEN}系统自检完成${NC}"

# 数据库迁移（如果需要）
echo ""
echo "[6/6] 检查数据库..."
# 这里可以添加数据库迁移逻辑

echo ""
echo "========================================"
echo "更新完成！"
echo "========================================"
echo ""
echo "更新内容:"
git log --oneline -5
echo ""
echo "如需重启系统:"
echo "  ./stop_system.sh && ./start_system.sh"
echo ""
echo "或使用systemd:"
echo "  sudo systemctl restart trading-bot"
echo "  sudo systemctl restart trading-api"
echo ""
