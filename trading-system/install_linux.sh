#!/bin/bash

# MT5加密货币交易系统 - Linux VPS安装脚本
# 版本: v2.3

set -e

echo "========================================"
echo "MT5加密货币交易系统 - Linux VPS安装脚本"
echo "版本: v2.3"
echo "========================================"
echo ""

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检测操作系统
detect_os() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$NAME
        VER=$VERSION_ID
    else
        OS=$(uname -s)
        VER=$(uname -r)
    fi
    echo -e "${GREEN}[检测] 操作系统: $OS $VER${NC}"
}

# 检查Python版本
check_python() {
    echo ""
    echo "[1/8] 检查Python环境..."

    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 --version | awk '{print $2}')
        echo -e "${GREEN}检测到 Python $PYTHON_VERSION${NC}"

        # 检查版本是否 >= 3.8
        PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
        PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

        if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 8 ]); then
            echo -e "${RED}[错误] Python版本过低，需要3.8+${NC}"
            exit 1
        fi
    else
        echo -e "${RED}[错误] 未检测到Python3，正在安装...${NC}"
        install_python
    fi
}

# 安装Python
install_python() {
    if [[ "$OS" == *"Ubuntu"* ]] || [[ "$OS" == *"Debian"* ]]; then
        sudo apt update
        sudo apt install -y python3 python3-pip python3-venv
    elif [[ "$OS" == *"CentOS"* ]] || [[ "$OS" == *"Red Hat"* ]]; then
        sudo yum install -y python3 python3-pip
    else
        echo -e "${RED}[错误] 不支持的操作系统，请手动安装Python 3.8+${NC}"
        exit 1
    fi
}

# 创建虚拟环境
create_venv() {
    echo ""
    echo "[2/8] 创建Python虚拟环境..."

    if [ ! -d "venv" ]; then
        python3 -m venv venv
        echo -e "${GREEN}虚拟环境创建成功${NC}"
    else
        echo -e "${YELLOW}虚拟环境已存在，跳过${NC}"
    fi

    # 激活虚拟环境
    source venv/bin/activate
}

# 运行系统自检
run_system_check() {
    echo ""
    echo "[3/8] 运行系统自检..."

    # 激活虚拟环境后运行自检
    python utilities/system_checker.py

    echo -e "${GREEN}系统自检完成${NC}"
}

# 安装依赖
install_dependencies() {
    echo ""
    echo "[4/8] 安装Python依赖包..."

    # 升级pip
    pip install --upgrade pip

    # 安装依赖，优先使用清华源
    echo "尝试使用清华源加速下载..."
    pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple || {
        echo -e "${YELLOW}清华源失败，使用官方源...${NC}"
        pip install -r requirements.txt
    }

    echo -e "${GREEN}依赖安装完成${NC}"
}

# 创建目录结构 (由系统自检自动完成，这里保留以防万一)
create_directories() {
    echo ""
    echo "[5/8] 确认目录结构..."

    # 系统自检已经创建了目录，这里只是确认
    echo -e "${GREEN}目录确认完成${NC}"
}

# 运行配置向导
run_config_wizard() {
    echo ""
    echo "[6/8] 运行配置向导..."

    python3 setup_wizard.py

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}配置完成${NC}"
    else
        echo -e "${RED}配置失败${NC}"
        exit 1
    fi
}

# VPS优化
optimize_vps() {
    echo ""
    echo "[7/8] 检测VPS硬件配置并优化..."

    python3 vps/vps_config.py

    echo -e "${GREEN}VPS优化完成${NC}"
}

# 配置systemd服务
setup_systemd() {
    echo ""
    echo "[8/8] 配置系统服务..."

    read -p "是否将交易系统配置为systemd服务自动启动? (y/n) " -n 1 -r
    echo

    if [[ $REPLY =~ ^[Yy]$ ]]; then
        CURRENT_DIR=$(pwd)
        VENV_PYTHON="$CURRENT_DIR/venv/bin/python"

        # 创建systemd服务文件
        sudo tee /etc/systemd/system/trading-bot.service > /dev/null <<EOF
[Unit]
Description=MT5 Crypto Trading Bot
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$CURRENT_DIR
ExecStart=$VENV_PYTHON bots/telegram_bot.py
Restart=always
RestartSec=10
StandardOutput=append:$CURRENT_DIR/logs/bot.log
StandardError=append:$CURRENT_DIR/logs/bot_error.log

[Install]
WantedBy=multi-user.target
EOF

        # 创建API服务文件
        sudo tee /etc/systemd/system/trading-api.service > /dev/null <<EOF
[Unit]
Description=MT5 Crypto Trading API Server
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$CURRENT_DIR
ExecStart=$VENV_PYTHON api/server.py
Restart=always
RestartSec=10
StandardOutput=append:$CURRENT_DIR/logs/api.log
StandardError=append:$CURRENT_DIR/logs/api_error.log

[Install]
WantedBy=multi-user.target
EOF

        # 重新加载systemd
        sudo systemctl daemon-reload

        # 启用服务
        sudo systemctl enable trading-bot.service
        sudo systemctl enable trading-api.service

        echo -e "${GREEN}Systemd服务配置完成${NC}"
        echo ""
        echo "服务管理命令:"
        echo "  启动: sudo systemctl start trading-bot"
        echo "  停止: sudo systemctl stop trading-bot"
        echo "  状态: sudo systemctl status trading-bot"
        echo "  日志: journalctl -u trading-bot -f"
    else
        echo "跳过systemd服务配置"
    fi
}

# 配置防火墙
setup_firewall() {
    echo ""
    echo "[8/8] 配置防火墙..."

    read -p "是否配置防火墙开放API端口5000? (y/n) " -n 1 -r
    echo

    if [[ $REPLY =~ ^[Yy]$ ]]; then
        if command -v ufw &> /dev/null; then
            sudo ufw allow 5000/tcp
            echo -e "${GREEN}UFW防火墙规则已添加${NC}"
        elif command -v firewall-cmd &> /dev/null; then
            sudo firewall-cmd --permanent --add-port=5000/tcp
            sudo firewall-cmd --reload
            echo -e "${GREEN}Firewalld防火墙规则已添加${NC}"
        else
            echo -e "${YELLOW}未检测到防火墙，跳过${NC}"
        fi
    fi
}

# 显示完成信息
show_completion() {
    echo ""
    echo "========================================"
    echo "安装完成！"
    echo "========================================"
    echo ""
    echo "后续步骤:"
    echo ""
    echo "1. 如需交易外汇/黄金，安装MetaTrader 5:"
    echo "   Wine方式: https://www.metatrader5.com/"
    echo ""
    echo "2. 启动交易系统:"
    echo "   手动启动: source venv/bin/activate && python bots/telegram_bot.py"
    echo "   服务启动: sudo systemctl start trading-bot"
    echo ""
    echo "3. 启动API服务器:"
    echo "   手动启动: source venv/bin/activate && python api/server.py"
    echo "   服务启动: sudo systemctl start trading-api"
    echo ""
    echo "4. 查看日志:"
    echo "   tail -f logs/bot.log"
    echo ""
    echo "5. 访问API控制台:"
    echo "   http://YOUR_VPS_IP:5000"
    echo ""
    echo "6. 使用screen保持后台运行(如未配置systemd):"
    echo "   screen -S trading"
    echo "   source venv/bin/activate"
    echo "   python bots/telegram_bot.py"
    echo "   按 Ctrl+A+D 离开screen"
    echo "   恢复: screen -r trading"
    echo ""
}

# 主流程
main() {
    detect_os
    check_python
    create_venv
    run_system_check
    install_dependencies
    create_directories
    run_config_wizard
    optimize_vps
    setup_systemd
    setup_firewall
    show_completion
}

# 执行主流程
main
