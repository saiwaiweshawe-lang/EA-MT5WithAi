# 量化交易系统 V1.0.0

支持 MetaTrader 5 外汇黄金 EA 和数字货币交易所的量化交易平台。提供多模型决策引擎、持仓监控、动态止损、数据源集成、策略训练、盈亏分析、风险控制、交易复盘、回测系统、实盘数据采集、性能监控、CPU 资源管理、新闻爬虫、智能选品、定量策略等完整功能。

**开源免费 | 免登录 | 下载即用 | 支持 Windows EXE**

## 快速开始

```bash
# 克隆项目
git clone https://github.com/saiwaiweshawe-lang/EA-MT5WithAi.git
cd EA-MT5WithAi

# 安装依赖
pip install -r requirements.txt

# 运行（Python）
python client/main.py

# 或打包成 EXE（Windows）
build_exe.bat
```

## 系统架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                      量化交易系统 V1.0.0                                    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │
│  │  仪表盘    │  │  MT5      │  │  交易所   │  │  新闻爬虫  │  │
│  │  状态总览  │  │  动态品种  │  │  动态品种  │  │  情绪分析  │  │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │
│  │  量化策略  │  │  智能选品  │  │  风控熔断  │  │  回测系统  │  │
│  │  多策略   │  │  新闻+策略  │  │  自动保护  │  │  验证策略  │  │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘  │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

## 核心功能

### 1. MT5 管理（动态品种）
- 自动获取 MT5 所有可用品种
- 支持黄金(XAUUSD)、外汇、加密货币
- 实时价格监控
- 订单执行与管理

### 2. 交易所连接（动态品种）
| 交易所 | 支持品种 | 功能 |
|--------|----------|------|
| Binance | BTCUSDT, ETHUSDT, SOLUSDT... | 现货/合约 |
| OKX | BTC-USDT, ETH-USDT... | 现货/合约 |
| Bybit | BTCUSDT, ETHUSDT... | 现货/合约 |

### 3. 新闻爬虫系统
| 类型 | 来源 |
|------|------|
| Twitter/X | Nitter + API |
| 加密货币 | CoinDesk, Cointelegraph, CryptoSlate, The Block, Decrypt, Bitcoinist, CCN |
| 金融 | Yahoo Finance, Bloomberg, Reuters, CNBC, FXStreet, Investing.com |
| 社群 | Reddit, Telegram RSS |

**特性**：
- 定时爬取（可配置间隔）
- 事件驱动（市场波动时自动触发）
- IP 保护（代理轮换、智能延迟）
- 情绪分析（正面/负面/中性）
- 相关性评分

### 4. 量化策略引擎

| 策略 | 最佳市场 | 说明 |
|------|----------|------|
| 趋势策略 | 趋势市场 | MA 交叉 + RSI |
| 套利策略 | 高波动市场 | 波动率分析 |
| 突破策略 | 盘整突破 | 支撑阻力突破 |

**自适应机制**：根据市场状态自动调整策略权重

### 5. 智能选品

综合以下因素选择最佳交易品种：
- 新闻情绪分析
- 策略信号强度
- 市场波动率
- 账户余额

### 6. 风控系统
- 日亏损熔断
- 连盈连亏监控
- 最大回撤保护
- 自动恢复机制

## 目录结构

```
trading-system/
├── client/                    # PyQt6 客户端
│   ├── main.py                # 启动入口
│   ├── config_manager.py       # 配置管理
│   ├── connectors/            # 连接器
│   │   ├── mt5_connector.py   # MT5 连接
│   │   └── exchange_base.py   # 交易所连接
│   ├── strategy/              # 策略引擎
│   │   ├── engine.py          # 量化引擎
│   │   ├── strategies.py     # 策略实现
│   │   └── smart_selector.py  # 智能选品
│   └── ui/                    # 界面
│       └── main_window.py      # 主窗口
├── news/                      # 新闻爬虫
│   ├── spiders/               # 爬虫实现
│   │   ├── twitter_spider.py  # Twitter
│   │   ├── crypto_news.py     # 加密货币
│   │   ├── finance_news.py    # 金融新闻
│   │   └── social_news.py    # 社群
│   ├── storage/               # 数据存储
│   │   ├── postgres_storage.py
│   │   ├── mysql_storage.py
│   │   └── sqlite_storage.py
│   ├── cache/                 # 缓存
│   │   ├── memory_cache.py
│   │   └── redis_cache.py
│   └── scheduler/             # 调度器
├── bots/                      # 交易机器人
├── training/                  # 策略训练
├── mt5-ea/                    # MT5 EA
└── requirements.txt           # 依赖
```

## 安装

### 环境要求
- Windows 10/11 或 macOS 10.14+
- Python 3.8+
- 4GB RAM
- 网络连接

### 安装依赖

```bash
pip install -r requirements.txt
```

主要依赖：
- PyQt6 - 图形界面
- MetaTrader5 - MT5 API
- ccxt - 交易所 API
- numpy/pandas - 数据分析
- feedparser - RSS 解析
- requests - HTTP 请求

### 运行客户端

```bash
# 直接运行
python client/main.py
```

### 打包 EXE

```batch
# Windows
build_exe.bat

# EXE 生成在 dist/QuantTrader.exe
```

## 配置说明

### MT5 配置
```json
{
  "mt5": {
    "server": "MetaQuotes-Demo",
    "account": 12345678,
    "password": "your_password"
  }
}
```

### 交易所 API
```json
{
  "exchanges": {
    "binance": {
      "api_key": "your_key",
      "api_secret": "your_secret"
    }
  }
}
```

### 新闻爬虫
```json
{
  "news": {
    "enabled": true,
    "interval_minutes": 15,
    "keywords": ["bitcoin", "btc", "ethereum", "eth"]
  }
}
```

## 常见问题

### Q: MT5 连接失败？
- 确认 MT5 终端已打开并登录
- 检查服务器、账户、密码是否正确

### Q: 交易所 API 验证失败？
- 确认 API Key 已正确复制
- 检查 API 权限是否包含交易

### Q: 新闻爬虫获取失败？
- 检查网络连接
- 部分源可能需要代理

详见 [HELP.md](HELP.md)

## 技术支持

- GitHub Issues: https://github.com/saiwaiweshawe-lang/EA-MT5WithAi/issues
- 邮箱: saiweiweshawe@gmail.com

## 免责声明

交易有风险，投资需谨慎！

本系统仅供学习研究使用，不构成任何投资建议。使用本系统进行实盘交易造成的任何损失，开发者不承担任何责任。

## 许可证

MIT License
