# 快速开始指南

本指南将帮助您在 15 分钟内快速部署和运行交易系统。

## 前置要求

- Linux 服务器 (Ubuntu 20.04+ 推荐)
- Python 3.8+
- 至少 4GB 内存
- 至少 20GB 可用磁盘空间

## 一键安装脚本

### 1. 下载项目

```bash
git clone https://github.com/your-org/trading-system.git
cd trading-system
```

### 2. 运行安装脚本

```bash
chmod +x scripts/quick_install.sh
./scripts/quick_install.sh
```

安装脚本将自动完成:
- 安装系统依赖
- 安装 Python 依赖
- 创建默认配置
- 初始化数据库
- 生成加密密钥

### 3. 配置关键参数

编辑配置文件 `config/trading_config.json`:

```json
{
  "database": {
    "url": "sqlite:///data/trading.db",
    "echo": false
  },
  "redis": {
    "host": "localhost",
    "port": 6379
  },
  "mt5": {
    "login": "YOUR_MT5_LOGIN",
    "password": "YOUR_MT5_PASSWORD",
    "server": "YOUR_MT5_SERVER"
  }
}
```

### 4. 启动系统

```bash
# 启动主服务
python3 main.py --role primary

# 或使用进程管理器
python3 utilities/process_manager.py --start-all
```

### 5. 验证安装

```bash
# 检查系统状态
curl http://localhost:5000/api/health

# 查看进程状态
python3 utilities/process_manager.py --list

# 查看日志
tail -f logs/system.log
```

## 手动安装步骤

如果您更喜欢手动控制安装过程:

### 步骤 1: 安装依赖

#### Ubuntu/Debian

```bash
sudo apt update
sudo apt install -y python3.8 python3-pip python3-venv
sudo apt install -y redis-server
sudo apt install -y build-essential libssl-dev libffi-dev
```

#### CentOS/RHEL

```bash
sudo yum install -y python38 python38-pip
sudo yum install -y redis
sudo yum install -y gcc openssl-devel libffi-devel
```

### 步骤 2: 创建虚拟环境

```bash
python3 -m venv venv
source venv/bin/activate
```

### 步骤 3: 安装 Python 依赖

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 步骤 4: 创建必要的目录

```bash
mkdir -p data logs backups reports/tests reports/backtests
```

### 步骤 5: 配置系统

```bash
# 复制配置模板
for file in config/example_*.json; do
  cp "$file" "${file/example_/}"
done

# 生成加密密钥
python3 -c "from utilities.encryption_manager import EncryptionManager; EncryptionManager().generate_key()"
```

### 步骤 6: 初始化数据库

```bash
python3 scripts/init_database.py
```

### 步骤 7: 启动服务

```bash
python3 main.py
```

## 首次运行检查清单

完成安装后,请验证以下项目:

### 1. 系统健康检查

```bash
# API 健康检查
curl http://localhost:5000/api/health

# 预期响应
{
  "status": "healthy",
  "version": "2.6",
  "uptime": 123.45
}
```

### 2. 数据库连接

```bash
# 测试数据库
python3 -c "from sqlalchemy import create_engine; engine = create_engine('sqlite:///data/trading.db'); print('数据库连接成功' if engine else '失败')"
```

### 3. Redis 连接

```bash
# 测试 Redis
redis-cli ping

# 预期响应: PONG
```

### 4. MT5 连接(如果配置)

```bash
# 测试 MT5 连接
python3 scripts/test_mt5_connection.py
```

### 5. 进程状态

```bash
# 查看所有进程
python3 utilities/process_manager.py --list

# 所有进程应该显示为 "running"
```

## 运行第一个回测

### 1. 准备测试数据

```bash
# 如果使用 MT5,从 MT5 下载数据
python3 scripts/download_mt5_data.py --symbol BTCUSD --start 2024-01-01 --end 2024-12-31

# 或使用示例数据
cp tests/sample_data.csv data/backtest/BTCUSD.csv
```

### 2. 运行回测

```python
# 创建文件 run_backtest.py
from utilities.backtesting_engine import BacktestingEngine, simple_ma_crossover_strategy

engine = BacktestingEngine(initial_capital=100000.0)

result = engine.run_backtest(
    simple_ma_crossover_strategy,
    symbol="BTCUSD",
    start_date="2024-01-01",
    end_date="2024-12-31",
    fast_period=10,
    slow_period=30
)

print(f"总收益: {result.total_return:.2f}%")
print(f"夏普比率: {result.sharpe_ratio:.2f}")
print(f"最大回撤: {result.max_drawdown:.2f}%")
print(f"胜率: {result.win_rate:.2f}%")
```

```bash
# 执行回测
python3 run_backtest.py
```

### 3. 查看回测报告

```bash
# 生成详细报告
python3 utilities/backtesting_engine.py --backtest \
  --symbol BTCUSD \
  --start 2024-01-01 \
  --end 2024-12-31 \
  --strategy ma_crossover \
  --export
```

报告将保存在 `reports/backtests/` 目录。

## 配置监控和告警

### 1. 启动监控系统

```bash
python3 utilities/monitoring.py --start
```

### 2. 配置告警渠道

编辑 `config/monitoring_config.json`:

```json
{
  "alerts": {
    "email": {
      "enabled": true,
      "smtp_server": "smtp.gmail.com",
      "smtp_port": 587,
      "from_email": "alerts@yourdomain.com",
      "to_emails": ["admin@yourdomain.com"]
    },
    "webhook": {
      "enabled": true,
      "url": "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
    }
  }
}
```

### 3. 测试告警

```bash
python3 utilities/monitoring.py --test-alert
```

## 配置高可用(可选)

如果您有两台服务器,可以配置高可用:

### 主服务器配置

编辑 `config/server_sync_config.json`:

```json
{
  "server_id": "primary-server",
  "role": "primary",
  "peer_server": {
    "url": "http://BACKUP_SERVER_IP:5001",
    "auth_token": "your-secure-token-here"
  },
  "heartbeat_interval": 5,
  "failover_threshold": 3
}
```

### 备份服务器配置

```json
{
  "server_id": "backup-server",
  "role": "backup",
  "peer_server": {
    "url": "http://PRIMARY_SERVER_IP:5000",
    "auth_token": "your-secure-token-here"
  },
  "heartbeat_interval": 5,
  "failover_threshold": 3
}
```

### 启动双服务器

```bash
# 主服务器
python3 main.py --role primary --port 5000

# 备份服务器
python3 main.py --role backup --port 5001
```

## 开启自动备份

```bash
# 启动备份管理器
python3 utilities/backup_manager.py --start

# 手动创建备份
python3 utilities/backup_manager.py --backup --type full
```

## 常见问题

### Q: 端口 5000 已被占用

```bash
# 查看占用端口的进程
sudo netstat -tunlp | grep 5000

# 使用其他端口
python3 main.py --port 5001
```

### Q: Redis 连接失败

```bash
# 启动 Redis
sudo systemctl start redis

# 检查状态
sudo systemctl status redis

# 设置开机自启
sudo systemctl enable redis
```

### Q: 权限错误

```bash
# 修复目录权限
sudo chown -R $USER:$USER .
chmod -R 755 .
```

### Q: Python 依赖安装失败

```bash
# 升级 pip
pip install --upgrade pip setuptools wheel

# 如果还是失败,尝试使用系统包
sudo apt install -y python3-flask python3-sqlalchemy
```

## 下一步

现在您已经成功安装了交易系统,可以:

1. 阅读 [完整文档](README.md)
2. 学习 [策略开发指南](strategy_development.md)
3. 配置 [实盘交易](live_trading.md)
4. 设置 [监控面板](monitoring.md)

## 获取帮助

- 📖 查看完整文档: [docs/README.md](README.md)
- 🐛 报告问题: [GitHub Issues](https://github.com/your-org/trading-system/issues)
- 💬 社区讨论: [Discord](https://discord.gg/your-invite)
- 📧 技术支持: support@example.com

## 卸载

如果您需要完全卸载系统:

```bash
# 停止所有进程
python3 utilities/process_manager.py --stop-all

# 删除虚拟环境
deactivate
rm -rf venv

# 删除数据(可选,谨慎操作!)
rm -rf data logs backups

# 删除项目目录
cd ..
rm -rf trading-system
```

---

祝您使用愉快! 🚀
