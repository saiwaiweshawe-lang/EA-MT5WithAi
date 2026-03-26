# 量化交易系统 V1.0.0 帮助指南

## 目录

1. [快速开始](#快速开始)
2. [MT5 配置](#mt5-配置)
3. [交易所 API 配置](#交易所-api-配置)
4. [新闻爬虫](#新闻爬虫)
5. [量化策略](#量化策略)
6. [常见问题](#常见问题)
7. [故障排除](#故障排除)

---

## 快速开始

### 系统要求

- Windows 10/11 或 macOS 10.14+
- Python 3.8+
- 4GB RAM
- 网络连接

### 安装步骤

```bash
# 1. 克隆或下载项目
git clone https://github.com/saiwaiweshawe-lang/EA-MT5WithAi.git
cd EA-MT5WithAi

# 2. 安装依赖
pip install -r requirements.txt

# 3. 运行客户端
python client/main.py
```

### 首次配置向导

首次运行时会显示配置向导：

1. **MT5 配置** - 输入服务器、账户、密码
2. **交易所 API** - 配置 Binance/OKX/Bybit
3. **完成设置**

---

## MT5 配置

### 获取 MT5 账户

1. 下载 MetaTrader 5: https://www.metatrader5.com/
2. 注册模拟账户或真实账户
3. 记录服务器名称、账户号码、密码

### 连接 MT5

```
┌─────────────────────────────────────┐
│ MT5 连接管理                         │
├─────────────────────────────────────┤
│ 服务器: MetaQuotes-Demo             │
│ 账户:   12345678                   │
│ 密码:   ********                    │
│                                     │
│ [连接]  [断开]                      │
└─────────────────────────────────────┘
```

### 支持的交易品种

系统会自动获取 MT5 支持的所有品种，包括：

| 类型 | 示例 |
|------|------|
| 黄金 | XAUUSD, XAUUSD.m |
| 外汇 | EURUSD, GBPUSD, USDJPY |
| 加密货币 | BTCUSD, ETHUSD |

---

## 交易所 API 配置

### Binance API

1. 登录 Binance: https://www.binance.com/
2. 进入 API 管理
3. 创建新的 API Key
4. 勾选"允许现货和合约交易"
5. 填写到系统配置

```
API Key:    ************************************
API Secret: ************************************
```

### OKX API

1. 登录 OKX: https://www.okx.com/
2. 进入 API 管理
3. 创建 API Key（需要设置 Passphrase）
4. 复制 API Key, Secret, Passphrase

### Bybit API

1. 登录 Bybit: https://www.bybit.com/
2. 进入 API 管理
3. 创建新的 API Key
4. 确保启用"合约交易"权限

---

## 新闻爬虫

### 支持的新闻源

| 类型 | 来源 |
|------|------|
| Twitter/X | Nitter 实例 |
| 加密货币 | CoinDesk, Cointelegraph, CryptoSlate, The Block |
| 金融 | Yahoo Finance, Bloomberg, Reuters, CNBC |
| 社群 | Reddit, Telegram |

### 爬取模式

```
┌─────────────────────────────────────┐
│ 爬取模式                             │
├─────────────────────────────────────┤
│ ☑ 定时爬取 (每 15 分钟)             │
│ ☑ 事件驱动 (波动 > 5%)              │
│ ☐ 手动爬取                          │
└─────────────────────────────────────┘
```

### IP 保护机制

系统内置智能 IP 保护：

- **延迟控制**: 请求间隔 2-5 秒
- **代理轮换**: 自动切换可用代理
- **指数退避**: 失败后延迟递增
- **来源伪装**: 随机 User-Agent

---

## 量化策略

### 策略类型

| 策略 | 说明 | 最佳市场 |
|------|------|----------|
| 趋势策略 | MA 交叉 + RSI | 趋势市场 |
| 套利策略 | 波动率分析 | 高波动市场 |
| 突破策略 | 支撑阻力突破 | 盘整突破 |

### 策略参数

```python
{
    "trend": {
        "ma_short": 10,
        "ma_long": 50,
        "rsi_period": 14,
        "rsi_oversold": 30,
        "rsi_overbought": 70
    },
    "breakout": {
        "lookback": 20,
        "volume_multiplier": 2.0
    }
}
```

### 市场自适应

系统会根据市场状态自动调整策略权重：

- **趋势市场**: 趋势策略权重 1.5x
- **高波动市场**: 突破策略权重 1.5x
- **低波动市场**: 套利策略权重 1.5x

---

## 常见问题

### Q1: MT5 连接失败

**症状**: 无法连接到 MT5 终端

**解决方法**:
1. 确认 MT5 终端已打开并登录
2. 检查服务器、账户、密码是否正确
3. 确认防火墙未阻止连接
4. 尝试使用模拟账户测试

### Q2: 交易所 API 验证失败

**症状**: API Key 或 Secret 无效

**解决方法**:
1. 确认 API Key 已正确复制（无多余空格）
2. 检查 API 权限是否包含所需交易类型
3. 确认 API 未过期或被禁用
4. 重新生成新的 API Key

### Q3: 新闻爬虫获取失败

**症状**: 无法获取新闻

**解决方法**:
1. 检查网络连接
2. 可能是源站暂时不可用，等待几分钟后重试
3. 某些新闻源可能需要代理
4. 检查配置中的 Nitter 实例是否可用

### Q4: 策略无信号

**症状**: 长时间没有交易信号

**解决方法**:
1. 确认市场品种已加载
2. 检查历史数据是否足够（需要 50+ 根 K 线）
3. 可能当前市场不适合该策略
4. 尝试调整策略参数

### Q5: 自动交易未执行

**症状**: 策略有信号但不下单

**解决方法**:
1. 检查"自动交易"是否已启用
2. 确认账户余额充足
3. 检查持仓数量是否已达上限
4. 确认风险限制未触发

### Q6: 打包 EXE 失败

**症状**: PyInstaller 打包失败

**解决方法**:
```bash
# 使用 pip 安装所有依赖到 EXE
pip install pyinstaller
pyinstaller --onedfile --windowed client/main.py

# 如果缺少依赖，手动添加
pyinstaller --onedfile --windowed --add-binary "path/to/dll" client/main.py
```

---

## 故障排除

### 日志位置

日志文件保存在：
- Windows: `%USERPROFILE%\.quant_trader\logs\`
- macOS: `~/.quant_trader/logs/`

### 重置配置

如果需要重置所有配置：

```bash
# 删除配置文件
rm -rf ~/.quant_trader/

# 重新运行
python client/main.py
```

### 网络问题

如果处于中国大陆等地区：

1. **新闻爬虫**: 可能需要配置代理
2. **交易所 API**: 确保网络可以访问对应交易所
3. **MT5**: 确保可以连接到 MT5 服务器

### 性能优化

1. **减少历史数据**: 减少加载的 K 线数量
2. **降低更新频率**: 增加定时器间隔
3. **关闭不需要的新闻源**: 在配置中禁用

---

## 联系与支持

- GitHub Issues: https://github.com/saiwaiweshawe-lang/EA-MT5WithAi/issues
- 邮箱: saiweiweshawe@gmail.com
- 项目文档: 查看项目 README.md

---

**免责声明**: 本系统仅供学习和研究使用。使用自动交易存在风险，请谨慎操作。
