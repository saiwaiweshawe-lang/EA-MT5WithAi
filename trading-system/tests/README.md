# 测试和回测系统

本目录包含系统的单元测试和回测功能。

## 目录结构

```
tests/
├── test_runner.py              # 统一测试运行器
├── test_config_manager.py      # 配置管理器测试
├── test_backtesting_engine.py  # 回测引擎测试
└── README.md                   # 本文件

utilities/
└── backtesting_engine.py       # 回测引擎实现
```

## 运行单元测试

### 运行所有测试

```bash
cd /workspace/trading-system
python tests/test_runner.py
```

### 运行特定测试

```bash
# 只运行配置管理器测试
python tests/test_runner.py --pattern "test_config_manager.py"

# 只运行回测引擎测试
python tests/test_runner.py --pattern "test_backtesting_engine.py"
```

### 导出测试结果

```bash
python tests/test_runner.py --export
```

测试结果会保存到 `reports/tests/` 目录。

## 运行策略回测

### 基本用法

```bash
cd /workspace/trading-system
python utilities/backtesting_engine.py \
  --symbol BTCUSD \
  --start 2024-01-01 \
  --end 2024-12-31 \
  --capital 100000
```

### 自定义参数

```bash
python utilities/backtesting_engine.py \
  --symbol BTCUSD \
  --start 2024-01-01 \
  --end 2024-12-31 \
  --capital 100000 \
  --fast-period 10 \
  --slow-period 30 \
  --output reports/backtest_result.txt
```

### 参数说明

- `--symbol`: 交易品种 (默认: BTCUSD)
- `--start`: 回测开始日期 (格式: YYYY-MM-DD)
- `--end`: 回测结束日期 (格式: YYYY-MM-DD)
- `--capital`: 初始资金 (默认: 100000)
- `--fast-period`: 快速均线周期 (默认: 10)
- `--slow-period`: 慢速均线周期 (默认: 30)
- `--output`: 报告输出路径 (可选)

## 编写自定义策略

### 策略函数签名

```python
def my_strategy(df: pd.DataFrame, params: Dict) -> List[int]:
    """
    自定义策略函数

    Args:
        df: 历史数据DataFrame (包含 time, open, high, low, close, volume)
        params: 策略参数字典

    Returns:
        信号列表:
        - 1: 做多信号
        - -1: 做空信号
        - 0: 平仓/不操作
    """
    signals = []

    # 策略逻辑
    for i in range(len(df)):
        # 根据指标生成信号
        if should_buy:
            signals.append(1)
        elif should_sell:
            signals.append(-1)
        else:
            signals.append(0)

    return signals
```

### 使用自定义策略

```python
from utilities.backtesting_engine import BacktestingEngine

# 创建回测引擎
engine = BacktestingEngine(initial_capital=100000.0)

# 运行回测
result = engine.run_backtest(
    my_strategy,
    symbol="BTCUSD",
    start_date="2024-01-01",
    end_date="2024-12-31",
    # 策略参数
    param1=value1,
    param2=value2
)

# 生成报告
if result:
    report = engine.generate_report(result)
    print(report)

    # 导出结果
    engine.export_results(result, "reports/backtests")
```

## 回测结果指标

回测结果包含以下指标:

### 收益指标
- **总收益**: 最终资金 - 初始资金
- **收益率**: 总收益 / 初始资金 × 100%
- **最大回撤**: 从峰值到谷底的最大跌幅
- **夏普比率**: 风险调整后的收益率

### 交易统计
- **总交易次数**: 完成的交易总数
- **盈利交易**: 盈利的交易数量和占比
- **亏损交易**: 亏损的交易数量
- **胜率**: 盈利交易 / 总交易 × 100%
- **盈利因子**: 总盈利 / 总亏损

### 交易表现
- **平均每笔交易**: 所有交易的平均盈亏
- **平均盈利交易**: 盈利交易的平均盈利
- **平均亏损交易**: 亏损交易的平均亏损
- **最大连续盈利**: 连续盈利的最大次数
- **最大连续亏损**: 连续亏损的最大次数

## 测试数据

### 使用历史数据

将历史数据文件放在 `data/backtest/` 目录,格式为CSV:

```csv
time,open,high,low,close,volume
2024-01-01 00:00:00,50000.0,50100.0,49900.0,50050.0,1000
2024-01-01 01:00:00,50050.0,50200.0,50000.0,50150.0,1200
...
```

### 自动生成模拟数据

如果历史数据文件不存在,回测引擎会自动生成模拟数据用于测试。

## 示例策略

### 移动平均线交叉策略

内置的简单移动平均线交叉策略 (`simple_ma_crossover_strategy`):

- **金叉**: 快线上穿慢线,做多
- **死叉**: 快线下穿慢线,平仓

```python
from utilities.backtesting_engine import simple_ma_crossover_strategy

# 使用示例
result = engine.run_backtest(
    simple_ma_crossover_strategy,
    symbol="BTCUSD",
    start_date="2024-01-01",
    end_date="2024-12-31",
    fast_period=10,
    slow_period=30
)
```

## 最佳实践

1. **测试驱动开发**: 在编写新功能之前先编写测试用例
2. **回测验证**: 所有交易策略都应该先进行充分的回测
3. **参数优化**: 使用网格搜索或遗传算法优化策略参数
4. **样本外测试**: 使用未参与回测的数据进行验证
5. **风险控制**: 设置合理的止损和仓位管理
6. **定期更新**: 定期使用最新数据重新回测策略

## 注意事项

1. 回测结果不代表实盘表现
2. 考虑滑点、手续费等交易成本
3. 注意过度拟合问题
4. 考虑市场状况变化
5. 模拟数据仅用于测试,实盘需使用真实历史数据
