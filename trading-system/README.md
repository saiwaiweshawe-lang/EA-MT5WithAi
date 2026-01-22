# MT5加密货币交易系统 (AI增强版)

一个功能完整的智能交易系统，支持MetaTrader 5外汇黄金EA和币圈交易所交易，集成多个AI模型、自动复盘、自我进化、影子训练等高级功能。

## 系统架构

```
trading-system/
├── mt5-ea/                  # MT5 EA文件
│   └── GoldTradingEA.mq5
├── bots/                     # 交易机器人模块
│   ├── telegram_bot.py        # Telegram机器人
│   ├── mt5_bridge.py        # MT5桥接
│   └── exchange_trader.py    # 交易所交易
├── api/                      # 远程控制API
│   └── server.py             # Flask API服务器
├── ai_models/                # AI模型集成
│   └── ai_ensemble.py       # AI集成器
├── news/                     # 新闻聚合
│   └── news_aggregator.py   # 新闻聚合器
├── dynamic_indicators/        # 动态指标系统
│   └── dynamic_system.py     # 动态指标
├── training/                 # 训练与进化
│   └── self_evolution.py    # 自我进化
├── shadow_trading/           # 影子训练场
│   └── shadow_engine.py     # 影子交易引擎
├── logs/                     # 日志系统
│   └── review_system.py     # 复盘系统
├── vps/                      # VPS配置
│   └── vps_config.py       # VPS自动配置
├── utilitities/              # 工具模块
│   └── cleaner.py          # 垃圾清理
├── config/                   # 配置文件
│   ├── bot_config.json      # 机器人配置
│   ├── server_config.json   # 服务器配置
│   ├── ea_config.json       # EA配置
│   ├── vps_config.json     # VPS配置
│   └── ai_config.json      # AI配置
└── requirements.txt          # Python依赖
```

## 功能特性

### AI集成
- 支持OpenAI GPT-4
- 支持Anthropic Claude
- 支持DeepSeek（免费）
- 支持本地模型
- 多模型投票决策
- 情绪分析

### MT5外汇黄金EA
- 支持黄金(XAUUSD)、外汇交易
- 动态指标系统
- AI辅助决策
- 移动止损功能
- 远程命令执行
- 实时状态上报

### 币圈交易所
- 支持Binance、OKX、Bybit、Huobi
- 现货和合约交易
- 多交易对支持
- 自动策略执行
- AI决策集成

### Telegram机器人
- 实时交易通知
- 手动下单/平仓
- 查看账户状态
- 查看待持仓位
- 策略控制
- AI分析报告

### 域名远程控制
- RESTful API接口
- 安全验证（API Key + IP白名单）
- 命令队列机制
- 状态同步

### 动态指标系统
- 动态移动平均线（SMA/EMA/VWMA/HMA/TMA）
- 动态RSI（自动调整超买超卖）
- 动态布林带（根据波动率调整）
- 动态MACD（根据趋势强度调整）
- 动态ATR（波动率分类）
- 动态成交量指标
- 市场状态识别
- 综合信号生成

### 新闻聚合
- CryptoCompare新闻API
- NewsAPI.org
- RSS新闻源（免费）
- Finnhub API
- Twitter/X消息
- 情绪分析
- 相关性评分

### 影子训练场
- 虚拟交易环境
- 策略回测
- 不影响实盘
- 性能评估
- 参数优化

### 自我进化
- 遗传算法优化参数
- 在线学习
- 性能反馈调整
- 多代进化
- 最优参数保存

### 复盘日志系统
- SQLite数据库存储
- 每日/每周复盘
- AI分析报告
- 交易统计
- CSV导出

### VPS自动配置
- 硬件自动检测
- 性能配置文件
- 自动调整参数
- 系统优化
- 资源分配建议
- 性能监控报警

### 垃圾清理
- 自动清理日志
- 缓存清理
- 临时文件清理
- 数据库优化
- Python缓存清理
- 磁盘空间检查
- 内存使用监控

## 安装步骤

### 1. 环境要求
- Python 3.8+
- MetaTrader 5
- Telegram Bot Token
- 可选：OpenAI/Anthropic API Key

### 2. 安装Python依赖

```bash
pip install -r requirements.txt
```

### 3. 配置文件

编辑以下配置文件：

```bash
# AI配置
config/ai_config.json

# Telegram机器人配置
config/bot_config.json

# API服务器配置
config/server_config.json

# EA配置
config/ea_config.json
```

### 4. VPS自动配置

```bash
python vps/vps_config.py
```

系统将自动检测VPS配置并优化设置。

## 使用说明

### 启动AI增强交易系统

```bash
# 1. 启动VPS配置（首次运行）
python vps/vps_config.py

# 2. 启动API服务器
python api/server.py

# 3. 启动Telegram机器人
python bots/telegram_bot.py

# 4. 安装并运行MT5 EA
# 将mt5-ea/GoldTradingEA.mq5复制到MT5目录
```

### 自我进化训练

```bash
python training/self_evolution.py
```

### 影子训练场测试

```bash
python shadow_trading/shadow_engine.py
```

### 生成复盘报告

```bash
python logs/review_system.py
```

### 清理系统垃圾

```bash
python utilitities/cleaner.py
```

## 配置说明

### AI配置 (config/ai_config.json)

```json
{
  "ai": {
    "models": {
      "openai": {
        "enabled": false,
        "api_key": ""
      },
      "deepseek": {
        "enabled": true,
        "api_key": "your-api-key"
      }
    },
    "voting_method": "weighted"
  }
}
```

### 新闻源配置

支持的免费新闻源：
- RSS源（完全免费）
- CryptoCompare（部分免费）
- NewsAPI.org（需要API Key）
- Finnhub（需要API Key）

### 动态指标配置

所有指标支持：
- 自动参数调整
- 市场状态识别
- 自适应周期

### VPS配置文件

系统自动识别以下配置：

| 配置 | CPU | 内存 | 磁盘 | MT5实例 | AI模型 |
|------|------|------|--------|----------|---------|
| high_performance | 8核 | 16G | 100G | 4 | 3 |
| medium_performance | 8核 | 8G | 20G | 2 | 2 |

## API接口

### AI分析

```bash
POST /api/ai/analyze
{
  "api_key": "your-key",
  "market_data": {...},
  "indicators": {...},
  "news": [...]
}
```

### 获取AI决策

```bash
POST /api/ai/decision
{
  "api_key": "your-key",
  "symbol": "XAUUSD",
  "timeframe": "H1"
}
```

### 影子交易

```bash
POST /api/shadow/trade
{
  "api_key": "your-key",
  "symbol": "XAUUSD",
  "action": "buy",
  "price": 2025.50,
  "parameters": {...}
}
```

### 获取复盘报告

```bash
GET /api/reports/daily?date=2024-01-22
GET /api/reports/weekly?start=2024-01-15
```

## 交易策略

### AI增强策略

系统整合以下因素：

1. **技术面**
   - 动态指标信号
   - 趋势识别
   - 波动率分析
   - 价量关系

2. **信息面**
   - 新闻情绪
   - 社交媒体情绪
   - 相关性评分
   - 影响权重

3. **AI决策**
   - 多模型投票
   - 置信度评估
   - 风险评估
   - 止损止盈建议

### 自适应规则

- 高波动市场：扩大止损止盈，降低仓位
- 震荡市场：延长周期，减少交易频率
- 趋势市场：缩短周期，跟随趋势

## 免责声明

交易有风险，投资需谨慎！

本系统仅供学习研究使用，不构成任何投资建议。使用本系统进行实盘交易造成的任何损失，开发者不承担任何责任。

请确保：
1. 充分理解市场风险
2. 只使用您能承受损失的资金
3. 先在影子训练场充分测试
4. 设置合理的风险管理策略
5. 不要将所有资金投入单一交易

## 许可证

MIT License

## 技术支持

如有问题或建议，请通过以下方式联系：
- 提交Issue
- 发送邮件

## 更新日志

### v2.0.0 (AI增强版)
- 集成多个AI模型
- 动态指标系统
- 新闻聚合与情绪分析
- 影子训练场功能
- 自我进化训练
- 自动复盘系统
- VPS自动配置
- 垃圾清理功能

### v1.0.0 (基础版)
- 初始版本发布
- MT5 EA支持
- 币圈交易所支持
- Telegram机器人
- RESTful API
