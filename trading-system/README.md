# 量化交易系统 V1.0.0

**开源量化交易平台 | 免登录 | 下载即用 | 支持 Windows EXE**

集新闻情报分析、量化策略进化、实盘交易于一体的智能交易系统。

## 核心定位

```
┌─────────────────────────────────────────────────────────────────┐
│                        信息面                                      │
│   新闻 → 情绪分析 → 热点品种 → 策略信号 → 智能选品              │
│   Twitter/X | 加密货币 | 金融 | 社群 RSS | RSI/MA 信号              │
├─────────────────────────────────────────────────────────────────┤
│                        技术面                                      │
│   遗传算法进化 → 多策略竞争 → Walk Forward 验证 → 实盘执行         │
│   过拟合检验 | 逻辑检验 | 淘汰机制 | 自适应权重                      │
└─────────────────────────────────────────────────────────────────┘
```

## 快速开始

```bash
# 克隆项目
git clone https://github.com/saiwaiweshawe-lang/EA-MT5WithAi.git
cd EA-MT5WithAi

# 安装依赖
pip install -r requirements.txt

# 运行（Python）
python main.py --gui        # GUI客户端
python main.py --api         # API服务器
python main.py --crawler    # 新闻爬虫
python main.py --evolution   # 策略进化

# Docker 部署
docker-compose up -d
```

## 信息面功能

### 新闻爬虫系统

| 类型 | 来源 | 功能 |
|------|------|------|
| Twitter/X | Nitter + API | 实时舆情 |
| 加密货币 | CoinDesk, Cointelegraph, CryptoSlate, The Block, Decrypt, Bitcoinist, CCN | 快讯 |
| 金融 | Yahoo Finance, Bloomberg, Reuters, CNBC, FXStreet, Investing.com | 宏观分析 |
| 社群 | Reddit, Telegram RSS | 社区热点 |

**特性**：
- 定时爬取（可配置间隔）
- 事件驱动（市场波动时自动触发）
- IP 保护（代理轮换、智能延迟）
- 情绪分析（正面/负面/中性）
- 相关性评分

### 智能选品

综合以下因素选择最佳交易品种：
```
新闻情绪分析 → 品种热度排名 → 策略信号 → 波动率 → 综合评分
```

## 技术面功能

### 进化算法 V2

解决遗传算法三大核心问题：

| 问题 | 解决方案 |
|------|----------|
| **过拟合** | Walk Forward Analysis + 多重交叉验证 + 过拟合惩罚 |
| **进化效率低** | 早停机制 + 精英保留 |
| **搜索空间爆炸** | 定义搜索空间边界 + 自适应参数范围 |

### 适应度函数设计

多目标优化，综合评分：

```python
final_score = (
    利润 × 0.3 +
    胜率 × 0.2 +
    风险调整收益 × 0.2 +
    夏普比率 × 0.15 +
    收益一致性 × 0.1 +
    逻辑检验 × 0.05
)
```

### 策略淘汰机制

**Arena Battle 竞技场**：
- 多策略竞争
- 底部 30% 淘汰
- 记录淘汰历史
- 幸存者进入下一代

### 策略逻辑检验

8 条验证规则：
- RSI 超买超卖逻辑检查
- MA 周期排序验证
- 止损止盈关系验证
- 参数合理范围检查

### 支持的策略

| 策略 | 最佳市场 | 核心指标 |
|------|----------|----------|
| 趋势策略 | 趋势市场 | MA 交叉 + RSI |
| 突破策略 | 盘整突破 | 支撑阻力 + 成交量 |
| 套利策略 | 高波动市场 | 波动率分析 |

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                      量化交易系统 V1.0.0                              │
├─────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐  │
│  │  仪表盘    │  │  MT5     │  │  交易所  │  │  新闻爬虫 │  │
│  │  状态总览  │  │  动态品种  │  │  动态品种  │  │  情绪分析 │  │
│  └───────────┘  └───────────┘  └───────────┘  └───────────┘  │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐  │
│  │  进化引擎  │  │  竞技场   │  │  风控熔断  │  │  回测验证  │  │
│  │  V2      │  │  策略淘汰  │  │  自动保护  │  │  WalkFW   │  │
│  └───────────┘  └───────────┘  └───────────┘  └───────────┘  │
│                                                                      │
└─────────────────────────────────────────────────────────────┘
```

## 目录结构

```
trading-system/
├── client/                    # PyQt6 客户端
│   ├── main.py                # 客户端入口
│   ├── config_manager.py       # 配置管理
│   ├── connectors/            # 连接器
│   │   ├── mt5_connector.py   # MT5 连接
│   │   └── exchange_base.py   # 交易所连接
│   └── strategy/              # 策略引擎
│       ├── engine.py          # 量化引擎
│       ├── strategies.py       # 策略实现
│       └── smart_selector.py  # 智能选品
├── news/                      # 新闻爬虫
│   ├── spiders/               # 爬虫实现
│   ├── storage/              # 数据存储
│   ├── cache/                # 缓存
│   └── scheduler/            # 调度器
├── training/                  # 策略训练
│   ├── self_evolution.py     # 旧版进化
│   └── self_evolution_v2.py  # V2 进化引擎
├── bots/                      # 交易机器人
├── utilities/                 # 工具模块
│   └── config_center.py        # 配置中心
├── main.py                    # 统一入口
├── Dockerfile                 # Docker 容器
└── docker-compose.yml         # 服务编排
```

## 安装

### 环境要求
- Windows 10/11 或 Linux/macOS
- Python 3.8+
- 4GB RAM
- 网络连接

### 安装依赖

```bash
pip install -r requirements.txt
```

**主要依赖**：
- PyQt6 - 图形界面
- MetaTrader5 - MT5 API
- ccxt - 交易所 API
- numpy/pandas - 数据分析
- feedparser - RSS 解析
- requests - HTTP 请求

### Docker 部署

```bash
# 构建并启动
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

## 使用方法

### 命令行启动

```bash
python main.py --gui          # 启动 GUI 客户端
python main.py --api          # 启动 API 服务器
python main.py --crawler     # 启动新闻爬虫
python main.py --evolution    # 运行策略进化
python main.py --backtest     # 运行回测
python main.py --status       # 查看系统状态
python main.py --check        # 系统检查
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

### 进化引擎 V2
```json
{
  "population_size": 30,
  "elite_ratio": 0.1,
  "mutation_rate": 0.1,
  "early_stop_patience": 15
}
```

## 常见问题

| 问题 | 解决方法 |
|------|----------|
| MT5 连接失败 | 确认终端已打开并登录 |
| 交易所 API 无效 | 检查 Key 和 Secret 是否正确 |
| 新闻爬虫失败 | 检查网络或配置代理 |
| 进化效果不佳 | 调整 population_size 和 mutation_rate |

详细帮助：[HELP.md](HELP.md)

## 技术支持

- GitHub Issues: https://github.com/saiwaiweshawe-lang/EA-MT5WithAi/issues
- 邮箱: saiweiweshawe@gmail.com

## 免责声明

交易有风险，投资需谨慎！

本系统仅供学习研究使用，不构成任何投资建议。使用本系统进行实盘交易造成的任何损失，开发者不承担任何责任。

## 许可证

MIT License
