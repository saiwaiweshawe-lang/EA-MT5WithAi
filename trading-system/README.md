# MT5加密货币交易系统 v2.6

支持MetaTrader 5外汇黄金EA和数字货币交易所的量化交易平台。提供多模型决策引擎、持仓监控、动态止损、数据源集成、策略训练、盈亏分析、风险控制、交易复盘、回测系统、实盘数据采集、性能监控、CPU资源管理、双服务器部署等完整功能。

## 系统架构

```
trading-system/
├── mt5-ea/                  # MT5 EA文件
│   └── GoldTradingEA.mq5
├── bots/                     # 交易机器人模块
│   ├── telegram_bot.py        # Telegram机器人
│   ├── mt5_bridge.py         # MT5桥接
│   └── exchange_trader.py     # 交易所交易
├── api/                      # 远程控制API
│   └── server.py             # Flask API服务器
├── ai_models/                # 模型集成
│   └── ai_ensemble.py        # 模型集成器
├── news/                     # 新闻聚合
│   └── news_aggregator.py    # 新闻聚合器
├── dynamic_indicators/        # 动态指标系统
│   └── dynamic_system.py      # 动态指标
├── training/                 # 训练与进化
│   ├── self_evolution.py      # 参数优化
│   └── proprietary_model_trainer.py  # 模型训练 (v2.3)
├── shadow_trading/           # 回测环境
│   └── shadow_engine.py       # 回测引擎
├── logs/                     # 日志系统
│   ├── review_system.py       # 复盘系统
│   ├── daily_analyzer.py      # 盈亏分析
│   └── circuit_breaker.py    # 风险控制
├── market_data/              # 实盘数据模块
│   └── real_data_provider.py  # 数据提供者
├── position_management/       # 持仓管理模块 (v2.3)
│   ├── smart_position_monitor.py  # 持仓监控
│   └── trailing_stop_engine.py    # 移动止损引擎
├── data_sources/             # 数据源集成 (v2.3)
│   └── free_premium_sources.py   # 数据源
├── vps/                      # VPS配置
│   └── vps_config.py         # 自动配置
├── utilities/                # 工具模块
│   ├── cleaner.py             # 清理工具
│   ├── system_checker.py      # 系统检查 (v2.3)
│   ├── performance_monitor.py  # 性能监控 (v2.4)
│   ├── logger.py              # 日志工具 (v2.4)
│   ├── cpu_limiter.py         # CPU限制器 (v2.5)
│   ├── server_role_manager.py  # 角色管理 (v2.5)
│   ├── cpu_integration_example.py  # 集成示例 (v2.5)
│   ├── backup_manager.py      # 备份管理 (v2.6)
│   ├── config_encryption.py   # 配置加密 (v2.6)
│   ├── process_manager.py     # 进程管理 (v2.6)
│   ├── monitoring.py          # 监控告警 (v2.6)
│   ├── config_manager.py      # 配置管理 (v2.6)
│   ├── log_aggregator.py      # 日志聚合 (v2.6)
│   ├── backtesting_engine.py  # 回测引擎 (v2.6)
│   ├── api_security.py        # API安全 (v2.6)
│   └── server_sync.py         # 服务器同步 (v2.6)
├── config/                   # 配置文件
│   ├── bot_config.json        # 机器人配置
│   ├── server_config.json     # 服务器配置
│   ├── ea_config.json         # EA配置
│   ├── vps_config.json       # VPS配置
│   ├── ai_config.json        # 模型配置
│   ├── position_management_config.json  # 持仓管理 (v2.3)
│   ├── cpu_limiter_config.json  # CPU限制 (v2.5)
│   ├── deployment_config.json   # 双服务器部署 (v2.5)
│   └── server_local.json     # 本地角色配置 (v2.5)
├── component_launcher.py      # 组件启动器 (v2.5)
└── requirements.txt           # Python依赖
```

## 功能特性

### CPU资源管理 (v2.5)
- 实时CPU使用率监控
- 时间窗口限制机制
- 自动节流操作
- 可配置阈值和冷却时间
- 持久化状态管理
- 告警通知功能

### 双服务器部署 (v2.5)
- 主服务器: 交易、用户交互、实时服务
- 计算服务器: 模型推理、数据分析、策略训练
- 组件分布式部署
- 服务器间HTTP通信
- 角色检测与配置
- 资源使用限制

### 性能监控 (v2.4)
- 系统资源监控
- 进程级性能追踪
- 可配置阈值告警
- 历史告警记录
- 线程化持续监控

### 统一日志系统 (v2.4)
- 颜色化日志输出
- 多级别日志支持
- 自动日志轮转
- 统一日志格式
- 日志归档功能

### 系统检查 (v2.3)
- 依赖包检测与安装
- 配置文件完整性验证
- 目录结构完整性验证
- 系统工具可用性检查
- 外部资源状态检查

### 实盘数据获取 (v2.2)
- 交易品种列表获取
- 实时市场深度数据
- 买卖压力分析
- 流动性评分
- 本金管理
- 风险仓位计算
- 多交易所统一接口
- 资金费率获取
- 链上数据监控支持
- 大额钱包活动监控

### MT5实盘数据 (v2.2)
- 支持20+外汇/黄金品种
- 实时深度数据获取
- 市场压力分析
- 点差计算
- 风险仓位计算
- 流动性评分

### 币圈实盘数据 (v2.2)
- 支持Binance、OKX、Bybit、Huobi
- 实时订单簿深度
- 资金费率监控
- 多交易所套利机会识别
- 交易信号生成

### 每日盈亏分析
- 交易表现分析
- 最佳交易时段识别
- 改进建议生成
- 多维度统计（平台/品种/时段）
- 连盈连亏分析
- 简洁/详细双版报告

### 风险控制
- 日亏损阈值触发
- 连续亏损暂停交易
- 最大回撤保护
- 过度交易限制
- 定时恢复机制
- 实时通知
- 手动重置功能

### Telegram机器人
- 每日定时报告
- 分析推送
- 状态查询
- 实时风险警报
- 大额交易通知
- 目标达成提醒

### 模型集成
- 支持OpenAI GPT-4
- 支持Anthropic Claude
- 支持DeepSeek
- 支持本地模型
- 多模型投票决策
- 情绪分析

### MT5外汇黄金EA
- 支持黄金(XAUUSD)、外汇交易
- 动态指标系统
- 辅助决策
- 移动止损功能
- 远程命令执行
- 实时状态上报

### 币圈交易所
- 支持Binance、OKX、Bybit、Huobi
- 现货和合约交易
- 多交易对支持
- 策略执行引擎

### 远程控制
- RESTful API接口
- 安全验证（API Key + IP白名单）
- 命令队列机制
- 状态同步

### 动态指标系统
- 自适应移动平均线（SMA/EMA/VWMA/HMA/TMA）
- 自适应RSI
- 自适应布林带
- 自适应MACD
- 自适应ATR
- 自适应成交量指标
- 市场状态识别
- 综合信号生成

### 新闻聚合 (v2.7)
- Twitter/X 爬虫（Nitter + API）
- 加密货币新闻（CoinDesk, Cointelegraph, CryptoSlate, The Block）
- 金融新闻（Yahoo Finance, Bloomberg, Reuters, CNBC）
- 社群新闻（Reddit, Telegram）
- RSS 聚合订阅源
- 多数据库支持（PostgreSQL, MySQL, SQLite）
- 缓存机制（Memory, Redis）
- 定时抓取调度
- Elasticsearch 搜索
- 情绪分析
- 相关性评分

### 回测系统
- 虚拟交易环境
- 策略回测
- 不影响实盘
- 性能评估
- 参数优化

### 参数优化
- 遗传算法优化参数
- 在线学习
- 性能反馈调整
- 多代进化
- 最优参数保存

### 复盘日志系统
- SQLite数据库存储
- 每日/每周复盘
- 分析报告
- 交易统计
- CSV导出

### VPS配置
- 硬件检测
- 性能配置文件
- 参数调整
- 系统优化
- 资源分配建议
- 性能监控报警

### 垃圾清理
- 日志清理
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
# 模型配置
config/ai_config.json

# Telegram机器人配置
config/bot_config.json

# API服务器配置
config/server_config.json

# EA配置
config/ea_config.json
```

### 4. VPS配置

```bash
python vps/vps_config.py
```

系统将检测VPS配置并优化设置。

## 使用说明

### 启动交易系统

**单服务器模式(默认)**

推荐方式（使用启动脚本，包含系统检查）

```bash
# Linux系统
./start_system.sh

# Windows系统
start_system.bat
```

**双服务器模式 (v2.5)**

详细说明见 [双服务器部署指南](docs/DUAL_SERVER_DEPLOYMENT.md)

快速部署:

```bash
# Server1 (主服务器)
git clone <your-repo> trading-system
cd trading-system
python utilities/server_role_manager.py server1
# 编辑 config/deployment_config.json 配置IP和API密钥
./start_system.sh

# Server2 (计算服务器)
git clone <your-repo> trading-system
cd trading-system
python utilities/server_role_manager.py server2
# 编辑 config/deployment_config.json 配置IP和API密钥
./start_system.sh
```

查看组件状态:
```bash
python component_launcher.py --status
```

**手动启动方式**

```bash
# 1. 启动VPS配置（首次运行）
python vps/vps_config.py

# 2. 运行系统检查
python utilities/system_checker.py

# 3. 启动API服务器
python api/server.py

# 4. 启动Telegram机器人
python bots/telegram_bot.py

# 5. 安装并运行MT5 EA
# 将mt5-ea/GoldTradingEA.mq5复制到MT5目录
```

### 停止交易系统

```bash
# Linux系统
./stop_system.sh

# Windows系统
stop_system.bat
```

### 更新系统

```bash
# Linux系统
./update_system.sh

# Windows系统
update_system.bat
```

### Telegram命令

| 命令 | 说明 |
|------|------|
| /start | 启动机器人 |
| /help | 显示帮助信息 |
| /status | 查看系统状态 |
| /balance | 查看账户余额 |
| /positions | 查看待持仓位 |
| /trade | 执行交易 |
| /close | 平仓 |
| /settings | 查看设置 |
| /report | 生成分析报告 |
| /daily [date] | 每日盈亏分析 |
| /daily detailed | 详细版每日报告 |
| /circuit | 查看风险控制状态 |
| /reset_circuit | 手动重置风险控制 |

### 风险控制

风险控制会在以下情况触发：

1. 日亏损达到阈值
2. 连续亏损次数超过设定值
3. 最大回撤超过设定百分比
4. 过度交易（超过50笔且亏损）

触发后：
- 停止新开仓
- 发送通知
- 24小时后恢复

手动操作：
- /circuit - 查看状态
- /reset_circuit - 手动重置

## 配置说明

### 风险控制配置 (config/bot_config.json)

```json
{
  "circuit_breaker": {
    "enabled": true,
    "max_loss_per_day": -1000,
    "max_consecutive_losses": 5,
    "max_drawdown_pct": 10,
    "auto_stop_trading": true,
    "notify_on_trigger": true,
    "auto_recover_after_hours": 24,
    "state_file": "logs/circuit_state.json"
  }
}
```

### 每日分析配置

```json
{
  "daily_analysis": {
    "enabled": true,
    "report_time": "23:30",
    "daily_loss_threshold": -500,
    "daily_profit_target": 200
  }
}
```

### 警报配置

```json
{
  "alerts": {
    "large_loss_threshold": -200,
    "large_profit_threshold": 200,
    "high_risk_consecutive_losses": 3,
    "daily_target_bonus_threshold": 500
  }
}
```

### VPS配置文件

系统识别以下配置：

| 配置 | CPU | 内存 | 磁盘 | MT5实例 | 模型 |
|------|------|------|--------|----------|---------|
| high_performance | 8核 | 16G | 100G | 4 | 3 |
| medium_performance | 8核 | 8G | 20G | 2 | 2 |

## API接口

### 健康检查 (v2.4)

```bash
GET /api/health
```

返回系统健康状态，包括：
- 服务运行状态（MT5、交易所、EA管理器）
- 系统资源（CPU、内存、磁盘、网络）
- 进程信息（内存使用、线程数）
- 命令队列状态

响应示例：
```json
{
  "status": "ok",
  "timestamp": "2024-01-22T10:30:00",
  "services": {
    "mt5": true,
    "exchange": true,
    "ea_manager": true
  },
  "system": {
    "platform": "Linux",
    "cpu_percent": 25.5,
    "memory": {
      "total_mb": 16384,
      "available_mb": 8192,
      "used_percent": 50.0
    },
    "disk": {
      "total_gb": 100,
      "free_gb": 60,
      "used_percent": 40.0
    }
  }
}
```

### 风险控制状态

```bash
GET /api/circuit/status
```

### 每日报告

```bash
GET /api/reports/daily?date=2024-01-22
GET /api/reports/weekly?start=2024-01-15
```

### 风险控制手动控制

```bash
POST /api/circuit/reset
{
  "api_key": "your-key"
}
```

## 交易策略

### 策略引擎

系统整合以下因素：

1. **技术面**
   - 自适应指标信号
   - 趋势识别
   - 波动率分析
   - 价量关系

2. **信息面**
   - 新闻情绪
   - 社交媒体情绪
   - 相关性评分
   - 影响权重

3. **决策引擎**
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
3. 先在回测环境充分测试
4. 设置合理的风险管理策略
5. 不要将所有资金投入单一交易

## 许可证

MIT License

## 技术支持

如有问题或建议，请通过以下方式联系：
- 提交Issue
- 发送邮件

## 更新日志

### v2.5.0 (双服务器部署与CPU限制版)
- 添加CPU资源管理功能
  - 实时CPU监控与时间窗口限制
  - 节流机制
  - 可配置阈值和冷却时间
  - 持久化状态管理
- 双服务器部署架构
  - 主服务器: 交易、用户交互
  - 计算服务器: 模型、训练、分析
  - 组件分配系统
  - 服务器角色检测
  - 服务器间HTTP通信
  - 资源密集任务时间调度
- 组件启动器
  - 基于服务器角色启动组件
  - 按优先级排序启动
  - 组件状态查看
- CPU限制集成示例
- 完整双服务器部署文档
- 更新启动/停止脚本支持双服务器

### v2.4.0 (性能监控版)
- 添加实时性能监控模块
- 统一日志系统（彩色输出、滚动文件、JSON格式）
- 增强健康检查API端点
- 更新脚本（Linux/Windows）
- 统一停止脚本（支持多种停止方式）
- 启动脚本集成系统检查
- 全局异常处理器
- 异常处理装饰器
- 安全执行函数包装
- 交易专用日志记录
- 性能阈值告警
- 历史告警记录

### v2.3.0 (系统检查版)
- 添加系统检查功能
- 检测并安装Python依赖
- 配置文件完整性检查
- 目录结构完整性检查
- 持仓监控
- 移动止损引擎
- 免费数据源集成
- 交易模型训练

### v2.2.0 (实盘数据版)
- 添加实盘数据获取模块
- 实现本金判断与管理
- 添加市场深度数据分析
- 支持MT5外汇/黄金20+品种
- 支持币圈多交易所深度数据
- 资金费率实时获取与历史分析
- 链上数据监控框架
- 大额钱包活动监控
- 买卖压力分析
- 流动性评分
- 风险仓位计算
- 统一数据接口

### v2.1.0 (风险控制与分析版)
- 添加每日盈亏分析功能
- 实现TG文本推送
- 开发风险保护
- 多维度交易统计
- 连盈连亏分析
- 定时报告
- 风险等级评估
- 分析建议生成

### v2.0.0 (模型增强版)
- 集成多个模型
- 自适应指标系统
- 新闻聚合与情绪分析
- 回测系统功能
- 参数优化训练
- 复盘系统
- VPS配置
- 清理功能

### v1.0.0 (基础版)
- 初始版本发布
- MT5 EA支持
- 币圈交易所支持
- Telegram机器人
- RESTful API
