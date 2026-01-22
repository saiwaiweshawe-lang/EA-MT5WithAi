# MT5加密货币交易系统

一个功能完整的交易系统，支持MetaTrader 5外汇黄金EA和币圈交易所交易，可通过Telegram机器人和域名远程控制。

## 系统架构

```
trading-system/
├── mt5-ea/              # MT5 EA文件
│   └── GoldTradingEA.mq5
├── bots/                # 交易机器人模块
│   ├── telegram_bot.py  # Telegram机器人
│   ├── mt5_bridge.py    # MT5桥接
│   └── exchange_trader.py  # 交易所交易
├── api/                 # 远程控制API
│   └── server.py        # Flask API服务器
├── config/              # 配置文件
│   ├── bot_config.json
│   ├── server_config.json
│   └── ea_config.json
└── requirements.txt     # Python依赖
```

## 功能特性

### MT5外汇黄金EA
- 支持黄金(XAUUSD)、外汇交易
- 自动交易策略（RSI + 移动平均线）
- 移动止损功能
- 远程命令执行
- 实时状态上报

### 币圈交易所
- 支持Binance、OKX、Bybit、Huobi
- 现货和合约交易
- 多交易对支持
- 自动策略执行

### Telegram机器人
- 实时交易通知
- 手动下单/平仓
- 查看账户状态
- 查看待持仓位
- 策略控制

### 域名远程控制
- RESTful API接口
- 安全验证（API Key + IP白名单）
- 命令队列机制
- 状态同步

## 安装步骤

### 1. 环境要求
- Python 3.8+
- MetaTrader 5
- Telegram Bot Token

### 2. 安装Python依赖

```bash
pip install -r requirements.txt
```

### 3. 配置文件

编辑配置文件：

```bash
# Telegram机器人配置
config/bot_config.json

# API服务器配置
config/server_config.json

# EA配置
config/ea_config.json
```

### 4. 获取Telegram Bot Token

1. 与 @BotFather 对话
2. 创建新机器人
3. 获取API Token
4. 获取你的Chat ID（与 @userinfobot 对话）

## 使用说明

### 启动Telegram机器人

```bash
python bots/telegram_bot.py
```

### 启动API服务器

```bash
python api/server.py
```

### 安装MT5 EA

1. 将 `mt5-ea/GoldTradingEA.mq5` 复制到MT5的MQL5/Experts目录
2. 在MT5中编译EA
3. 将EA拖到图表上
4. 设置参数：
   - `InpServerURL`: 你的API服务器地址
   - `InpMagicNumber`: EA幻数
   - `InpLotSize`: 交易手数

### Telegram命令

| 命令 | 说明 |
|------|------|
| /start | 启动机器人 |
| /help | 显示帮助 |
| /status | 查看系统状态 |
| /balance | 查看余额 |
| /positions | 查看待持仓位 |
| /trade | 开始交易 |
| /close | 平仓 |
| /settings | 查看设置 |

### API接口

#### 健康检查
```
GET /api/health
```

#### MT5交易
```
POST /api/mt5/trade
Content-Type: application/json

{
  "api_key": "your-secret-key",
  "symbol": "XAUUSD",
  "action": "buy",
  "lot_size": 0.01,
  "price": null
}
```

#### 获取MT5持仓
```
GET /api/mt5/positions?api_key=your-key&symbol=XAUUSD
```

#### 平MT5持仓
```
POST /api/mt5/close
Content-Type: application/json

{
  "api_key": "your-secret-key",
  "symbol": "XAUUSD"
}
```

#### 发送命令到EA
```
POST /api/send-command
Content-Type: application/json

{
  "api_key": "your-secret-key",
  "symbol": "XAUUSD",
  "command": "BUY:0.01"
}
```

命令格式：
- `BUY:0.01` - 买入0.01手
- `SELL:0.01` - 卖出0.01手
- `CLOSE_ALL` - 平所有仓
- `CLOSE_PROFIT` - 平盈利仓
- `SET_LOT:0.02` - 设置手数
- `ENABLE_AUTO` - 启用自动交易
- `DISABLE_AUTO` - 禁用自动交易

#### 交易所交易
```
POST /api/exchange/trade
Content-Type: application/json

{
  "api_key": "your-secret-key",
  "symbol": "BTCUSDT",
  "side": "buy",
  "amount": 0.001,
  "price": null
}
```

#### 获取交易所持仓
```
GET /api/exchange/positions?api_key=your-key
```

#### 系统概览
```
GET /api/overview?api_key=your-key
```

## 支持的交易所

| 交易所 | 现货 | 合约 | 测试网 |
|--------|------|------|--------|
| Binance | 支持 | 支持 | 支持 |
| OKX | 支持 | 支持 | 部分支持 |
| Bybit | 支持 | 支持 | 支持 |
| Huobi | 支持 | 支持 | 支持 |

## 交易策略

### MT5黄金EA策略

- **指标**: RSI(14) + MA(10/20)
- **买入条件**: RSI < 30 AND MA10 > MA20
- **卖出条件**: RSI > 70 AND MA10 < MA20
- **止损**: 默认2000点
- **止盈**: 默认4000点
- **移动止损**: 盈利500点后启动，步长200点

### 币圈策略

- **指标**: MA(7/25) + RSI(14)
- **买入条件**: MA7 > MA25 AND RSI < 70
- **卖出条件**: MA7 < MA25 AND RSI > 30
- **止损**: 2%
- **止盈**: 4%

## 安全建议

1. **API Key管理**
   - 使用强随机字符串作为API Key
   - 定期更换API Key
   - 不要将API Key提交到版本控制

2. **IP白名单**
   - 在生产环境中使用IP白名单
   - 限制访问来源

3. **测试网优先**
   - 先在测试网测试所有功能
   - 确认无误后再切换到实盘

4. **风险管理**
   - 设置合理的止损
   - 控制仓位大小
   - 不要全仓交易

## 常见问题

### MT5连接失败
- 确认MT5已正确安装
- 检查登录信息是否正确
- 确认MT5终端已登录到账户

### Telegram机器人无响应
- 检查Bot Token是否正确
- 检查Chat ID是否在授权列表中
- 确认机器人已启动

### 交易所API错误
- 检查API Key权限是否正确
- 确认API Key有交易权限
- 检查IP白名单设置

## 免责声明

交易有风险，投资需谨慎！

本系统仅供学习研究使用，不构成任何投资建议。使用本系统进行实盘交易造成的任何损失，开发者不承担任何责任。

请确保：
1. 充分理解市场风险
2. 只使用您能承受损失的资金
3. 先在模拟账户充分测试
4. 设置合理的风险管理策略

## 许可证

MIT License

## 技术支持

如有问题或建议，请通过以下方式联系：
- 提交Issue
- 发送邮件

## 更新日志

### v1.0.0
- 初始版本发布
- MT5 EA支持
- 币圈交易所支持
- Telegram机器人
- RESTful API
