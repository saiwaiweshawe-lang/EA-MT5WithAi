#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
回测引擎单元测试
"""

import os
import sys
import unittest
import pandas as pd
import numpy as np
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from utilities.backtesting_engine import BacktestingEngine, simple_ma_crossover_strategy


class TestBacktestingEngine(unittest.TestCase):
    """回测引擎测试"""

    def setUp(self):
        """测试前准备"""
        self.engine = BacktestingEngine(initial_capital=100000.0)

    def test_initialization(self):
        """测试初始化"""
        self.assertEqual(self.engine.initial_capital, 100000.0)
        self.assertEqual(self.engine.capital, 100000.0)
        self.assertEqual(len(self.engine.trades), 0)
        self.assertEqual(len(self.engine.open_positions), 0)

    def test_generate_sample_data(self):
        """测试生成模拟数据"""
        df = self.engine._generate_sample_data(
            "BTCUSD",
            "2024-01-01",
            "2024-01-07"
        )

        # 检查数据格式
        self.assertIsInstance(df, pd.DataFrame)
        self.assertIn('time', df.columns)
        self.assertIn('open', df.columns)
        self.assertIn('high', df.columns)
        self.assertIn('low', df.columns)
        self.assertIn('close', df.columns)
        self.assertIn('volume', df.columns)

        # 检查OHLC逻辑
        for i in range(len(df)):
            row = df.iloc[i]
            self.assertGreaterEqual(row['high'], row['close'])
            self.assertGreaterEqual(row['high'], row['open'])
            self.assertGreaterEqual(row['high'], row['low'])
            self.assertLessEqual(row['low'], row['close'])
            self.assertLessEqual(row['low'], row['open'])

    def test_load_historical_data(self):
        """测试加载历史数据"""
        df = self.engine.load_historical_data(
            "BTCUSD",
            "2024-01-01",
            "2024-01-07"
        )

        self.assertIsInstance(df, pd.DataFrame)
        self.assertGreater(len(df), 0)

    def test_open_and_close_position(self):
        """测试开仓和平仓"""
        symbol = "BTCUSD"
        entry_price = 50000.0
        exit_price = 51000.0

        # 开仓
        self.engine._open_position(symbol, 'long', 1000.0, entry_price)
        self.assertEqual(len(self.engine.open_positions), 1)
        self.assertIn(symbol, self.engine.open_positions)

        # 平仓
        self.engine._close_position(symbol, 2000.0, exit_price)
        self.assertEqual(len(self.engine.open_positions), 0)
        self.assertEqual(len(self.engine.trades), 1)

        # 检查交易记录
        trade = self.engine.trades[0]
        self.assertEqual(trade.symbol, symbol)
        self.assertEqual(trade.direction, 'long')
        self.assertEqual(trade.entry_price, entry_price)
        self.assertEqual(trade.exit_price, exit_price)
        self.assertGreater(trade.profit, 0)  # 盈利交易

    def test_calculate_equity(self):
        """测试计算权益"""
        # 初始权益
        equity = self.engine._calculate_equity(50000.0)
        self.assertAlmostEqual(equity, 100000.0, places=2)

        # 开仓后
        self.engine._open_position("BTCUSD", 'long', 1000.0, 50000.0)
        equity = self.engine._calculate_equity(51000.0)  # 价格上涨
        self.assertGreater(equity, 100000.0)  # 应该有浮动盈利

        equity = self.engine._calculate_equity(49000.0)  # 价格下跌
        self.assertLess(equity, 100000.0)  # 应该有浮动亏损

    def test_ma_crossover_strategy(self):
        """测试移动平均线交叉策略"""
        # 生成测试数据
        df = pd.DataFrame({
            'close': [100, 102, 104, 103, 105, 107, 106, 108, 110, 112,
                     114, 113, 115, 117, 116, 118, 120, 119, 121, 123,
                     125, 124, 126, 128, 127, 129, 131, 130, 132, 134]
        })

        params = {'fast_period': 5, 'slow_period': 10}
        signals = simple_ma_crossover_strategy(df, params)

        self.assertEqual(len(signals), len(df))
        self.assertIn(1, signals)  # 应该有做多信号

    def test_run_backtest(self):
        """测试运行回测"""
        result = self.engine.run_backtest(
            simple_ma_crossover_strategy,
            symbol="BTCUSD",
            start_date="2024-01-01",
            end_date="2024-01-31",
            fast_period=10,
            slow_period=30
        )

        # 检查结果
        self.assertIsNotNone(result)
        self.assertEqual(result.symbol, "BTCUSD")
        self.assertEqual(result.initial_capital, 100000.0)
        self.assertIsInstance(result.total_trades, int)
        self.assertIsInstance(result.win_rate, float)

    def test_max_drawdown_calculation(self):
        """测试最大回撤计算"""
        equity_values = [100, 110, 105, 115, 95, 100, 90, 105]
        max_dd, max_dd_pct = self.engine._calculate_max_drawdown(equity_values)

        self.assertGreater(max_dd, 0)
        self.assertGreater(max_dd_pct, 0)

    def test_sharpe_ratio_calculation(self):
        """测试夏普比率计算"""
        # 稳定上涨的权益曲线
        equity_values = list(range(100, 200, 5))
        sharpe = self.engine._calculate_sharpe_ratio(equity_values)

        # 夏普比率应该是合理的数值
        self.assertIsInstance(sharpe, float)

    def test_consecutive_trades_calculation(self):
        """测试连续盈亏计算"""
        from utilities.backtesting_engine import Trade

        trades = [
            Trade("1", "BTC", "long", 1000, 50000, 1001, 51000, 1, 0, 1000, 2.0, "closed"),  # 盈利
            Trade("2", "BTC", "long", 1002, 51000, 1003, 52000, 1, 0, 1000, 2.0, "closed"),  # 盈利
            Trade("3", "BTC", "long", 1004, 52000, 1005, 51000, 1, 0, -1000, -2.0, "closed"),  # 亏损
            Trade("4", "BTC", "long", 1006, 51000, 1007, 50000, 1, 0, -1000, -2.0, "closed"),  # 亏损
            Trade("5", "BTC", "long", 1008, 50000, 1009, 51000, 1, 0, 1000, 2.0, "closed"),  # 盈利
        ]

        max_wins, max_losses = self.engine._calculate_consecutive_trades(trades)

        self.assertEqual(max_wins, 2)
        self.assertEqual(max_losses, 2)


if __name__ == "__main__":
    unittest.main()
