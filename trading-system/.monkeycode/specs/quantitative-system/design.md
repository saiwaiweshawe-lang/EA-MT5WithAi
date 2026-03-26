# 量化交易系统 V1.0.0 设计规格

## 概述

开源量化交易系统，用户下载 EXE 后即可直接使用，无需登录。

## 核心设计原则

1. **免登录** - 本地直接使用，数据本地存储
2. **动态品种** - MT5 和交易所品种不写死，API 动态获取
3. **智能选择** - 根据新闻和策略自动选择交易品种

## 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    Windows EXE (PyQt6)                                  │
├─────────────────────────────────────────────────────────────────┤
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐      │
│  │  仪表盘       │  │  MT5 管理     │  │  交易所管理   │      │
│  │  (状态总览)   │  │  (动态品种)   │  │  (动态品种)   │      │
│  └───────────────┘  └───────────────┘  └───────────────┘      │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐      │
│  │  新闻爬虫     │  │  量化策略     │  │  智能选品     │      │
│  │  (情绪分析)   │  │  (多策略)    │  │  (新闻+策略)  │      │
│  └───────────────┘  └───────────────┘  └───────────────┘      │
└─────────────────────────────────────────────────────────────────┘
```

## 功能模块

### 1. 启动向导

首次使用时引导用户配置：
1. MT5 账户（服务器、账户、密码）
2. 交易所 API（可选 Binance/OKX/Bybit）
3. 基本参数设置

### 2. MT5 管理

```python
class MT5Connector:
    def connect(self, server: str, account: int, password: str) -> bool:
        """连接 MT5"""
    
    def get_available_symbols(self) -> List[str]:
        """动态获取 MT5 可用品种"""
        # 返回如 ['XAUUSD', 'EURUSD', 'GBPUSD', 'BTCUSD', ...]
    
    def get_account_info(self) -> dict:
        """获取账户信息"""
    
    def get_symbol_info(self, symbol: str) -> dict:
        """获取品种详细信息"""
```

### 3. 交易所管理

```python
class ExchangeConnector:
    def __init__(self, exchange: str):
        self.exchange = exchange  # binance/okx/bybit
    
    def connect(self, api_key: str, api_secret: str) -> bool:
        """连接交易所"""
    
    def get_available_symbols(self) -> List[str]:
        """动态获取可交易对"""
        # Binance 返回如 ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', ...]
    
    def get_balance(self) -> dict:
        """获取账户余额"""
    
    def place_order(self, symbol: str, side: str, quantity: float) -> dict:
        """下单"""
```

### 4. 新闻爬虫与策略联动

```
新闻获取 → 情绪分析 → 相关品种识别 → 策略信号生成
    │                                    │
    └────────── 品种热点排名 ───────────┘
```

### 5. 智能品种选择

```python
class SmartSymbolSelector:
    def select_by_news(self, news_items: List[NewsItem]) -> List[str]:
        """根据新闻选择品种"""
        # 分析新闻中的币种提及 → 按情绪排序
    
    def select_by_strategy(self, signals: List[Signal]) -> List[str]:
        """根据策略选择品种"""
        # 选择信号强度最高的品种
    
    def select_by_volatility(self, min_volatility: float) -> List[str]:
        """根据波动率选择"""
        # 选择近期波动率超过阈值的品种
    
    def get_final_candidates(self) -> List[str]:
        """综合选择最终候选品种"""
        # 合并新闻 + 策略 + 波动率
```

### 6. 量化策略引擎 v2.0

```python
class QuantitativeEngine:
    def __init__(self, config: dict):
        self.strategies = []  # 多策略
    
    def add_strategy(self, strategy):
        self.strategies.append(strategy)
    
    def generate_signals(self, market_data: dict) -> List[Signal]:
        """生成交易信号"""
        signals = []
        for strategy in self.strategies:
            sig = strategy.analyze(market_data)
            signals.append(sig)
        return signals
    
    def select_best_symbols(self, signals: List[Signal], 
                          news_candidates: List[str],
                          limit: int = 5) -> List[str]:
        """选择最佳交易品种"""
        # 综合信号强度、新闻相关性、波动率
```

## 界面设计

### 主界面布局

```
┌────────────────────────────────────────────────────────────────────┐
│  量化交易系统 V1.0.0                                            [_][□][X]│
├────────────────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │ [仪表盘] [MT5] [交易所] [新闻] [策略] [设置]               │ │
│  └───────────────────────────────────────────────────────────-──┘ │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │  连接状态                                                       │ │
│  │  MT5: ● 已连接 (服务器: MetaQuotes-Demo)                     │ │
│  │  交易所: ● Binance ● OKX ● Bybit                              │ │
│  │  新闻爬虫: ● 运行中 (最后爬取: 10:23:45)                      │ │
│  └───────────────────────────────────────────────────────────────┘ │
│                                                                     │
│  ┌─────────────────────────┐  ┌───────────────────────────────────┐ │
│  │  动态品种列表            │  │  新闻与信号                       │ │
│  │  ─────────────────────  │  │  ─────────────────────────────    │ │
│  │  [搜索品种...]          │  │  BTC  新闻: 正面  信号: 买入     │ │
│  │                         │  │  ETH  新闻: 中性  信号: 观望     │ │
│  │  ☑ XAUUSD (黄金)      │  │  BNB  新闻: 负面  信号: 卖出     │ │
│  │  ☑ EURUSD             │  │                                   │ │
│  │  ☑ BTCUSD             │  │  建议交易品种: BTC, ETH           │ │
│  │  ☐ ETHUSD             │  │  ─────────────────────────────    │ │
│  │                         │  │  [自动交易]  [手动确认]          │ │
│  └─────────────────────────┘  └───────────────────────────────────┘ │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │  今日交易: 5 笔  |  盈利: +$234  |  胜率: 68%              │ │
│  └───────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────┘
```

## 配置存储

本地 JSON 文件存储（无云端）：

```json
{
  "mt5": {
    "server": "MetaQuotes-Demo",
    "account": 12345678,
    "password_encrypted": "xxx",
    "symbols": ["XAUUSD", "EURUSD", "BTCUSD"]
  },
  "exchanges": {
    "binance": {
      "api_key_encrypted": "xxx",
      "api_secret_encrypted": "xxx",
      "enabled": true,
      "symbols": ["BTCUSDT", "ETHUSDT"]
    },
    "okx": {...},
    "bybit": {...}
  },
  "trading": {
    "auto_trade": false,
    "max_positions": 3,
    "risk_per_trade": 0.02
  },
  "news": {
    "enabled": true,
    "interval_minutes": 15,
    "keywords": ["bitcoin", "btc", "ethereum", "eth"]
  }
}
```

## 数据流

```
1. 新闻爬虫定时获取新闻
       ↓
2. 情绪分析 → 相关币种排名
       ↓
3. 策略引擎分析市场数据
       ↓
4. 智能选品 → 综合新闻 + 策略 + 波动率
       ↓
5. 生成交易信号
       ↓
6. 用户确认/自动执行
       ↓
7. MT5/交易所下单
       ↓
8. 记录交易 → 更新策略权重
```

## 安全考虑

- API 密钥本地加密存储
- 不上传任何数据到云端
- 所有操作本地执行
