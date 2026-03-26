#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
进化引擎 V2 单元测试
"""

import unittest
import sys
import os
import json
import tempfile
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from training.self_evolution_v2 import (
    StrategyParams,
    WalkForwardValidator,
    LogicValidator,
    ArenaBattle,
    EvolutionaryEngineV2,
    TrendStrategy,
    BreakoutStrategy,
    ArbitrageStrategy,
    StrategyFactory
)


class TestLogicValidator(unittest.TestCase):
    """逻辑验证器测试"""
    
    def test_valid_params(self):
        params = StrategyParams(
            name="test",
            strategy_type="trend",
            ma_periods=[10, 20, 50],
            rsi_period=14,
            rsi_oversold=30.0,
            rsi_overbought=70.0,
            stop_loss_pips=50.0,
            take_profit_pips=100.0,
            position_size=0.02,
            max_positions=3,
            trailing_stop_pips=30.0,
            trailing_start_pips=50.0,
            confidence_threshold=0.6,
            risk_per_trade=0.02
        )
        
        is_valid, score = LogicValidator.validate(params)
        self.assertTrue(is_valid)
        self.assertGreater(score, 0.6)
    
    def test_invalid_rsi_order(self):
        params = StrategyParams(
            name="test",
            strategy_type="trend",
            ma_periods=[10, 20, 50],
            rsi_period=14,
            rsi_oversold=70.0,
            rsi_overbought=30.0,
            stop_loss_pips=50.0,
            take_profit_pips=100.0,
            position_size=0.02,
            max_positions=3,
            trailing_stop_pips=30.0,
            trailing_start_pips=50.0,
            confidence_threshold=0.6,
            risk_per_trade=0.02
        )
        
        is_valid, score = LogicValidator.validate(params)
        self.assertFalse(is_valid)
    
    def test_invalid_ma_periods(self):
        params = StrategyParams(
            name="test",
            strategy_type="trend",
            ma_periods=[100, 50, 10],
            rsi_period=14,
            rsi_oversold=30.0,
            rsi_overbought=70.0,
            stop_loss_pips=50.0,
            take_profit_pips=100.0,
            position_size=0.02,
            max_positions=3,
            trailing_stop_pips=30.0,
            trailing_start_pips=50.0,
            confidence_threshold=0.6,
            risk_per_trade=0.02
        )
        
        is_valid, score = LogicValidator.validate(params)
        self.assertFalse(is_valid)


class TestStrategyFactory(unittest.TestCase):
    """策略工厂测试"""
    
    def test_create_trend_strategy(self):
        params = StrategyParams(
            name="test",
            strategy_type="trend",
            ma_periods=[10, 20, 50],
            rsi_period=14,
            rsi_oversold=30.0,
            rsi_overbought=70.0,
            stop_loss_pips=50.0,
            take_profit_pips=100.0,
            position_size=0.02,
            max_positions=3,
            trailing_stop_pips=30.0,
            trailing_start_pips=50.0,
            confidence_threshold=0.6,
            risk_per_trade=0.02
        )
        
        strategy = StrategyFactory.create(params)
        self.assertIsInstance(strategy, TrendStrategy)
    
    def test_create_breakout_strategy(self):
        params = StrategyParams(
            name="test",
            strategy_type="breakout",
            ma_periods=[10, 20, 50],
            rsi_period=14,
            rsi_oversold=30.0,
            rsi_overbought=70.0,
            stop_loss_pips=50.0,
            take_profit_pips=100.0,
            position_size=0.02,
            max_positions=3,
            trailing_stop_pips=30.0,
            trailing_start_pips=50.0,
            confidence_threshold=0.6,
            risk_per_trade=0.02
        )
        
        strategy = StrategyFactory.create(params)
        self.assertIsInstance(strategy, BreakoutStrategy)


class TestArenaBattle(unittest.TestCase):
    """策略竞技场测试"""
    
    def setUp(self):
        self.arena = ArenaBattle(population_size=10)
    
    def test_add_strategy(self):
        params = StrategyParams(
            name="test_1",
            strategy_type="trend",
            ma_periods=[10, 20, 50],
            rsi_period=14,
            rsi_oversold=30.0,
            rsi_overbought=70.0,
            stop_loss_pips=50.0,
            take_profit_pips=100.0,
            position_size=0.02,
            max_positions=3,
            trailing_stop_pips=30.0,
            trailing_start_pips=50.0,
            confidence_threshold=0.6,
            risk_per_trade=0.02
        )
        
        self.arena.add_strategy(params)
        self.assertEqual(len(self.arena.strategies), 1)
    
    def test_elimination(self):
        for i in range(10):
            params = StrategyParams(
                name=f"test_{i}",
                strategy_type="trend",
                ma_periods=[10 + i, 20 + i, 50 + i],
                rsi_period=14,
                rsi_oversold=30.0,
                rsi_overbought=70.0,
                stop_loss_pips=50.0,
                take_profit_pips=100.0,
                position_size=0.02,
                max_positions=3,
                trailing_stop_pips=30.0,
                trailing_start_pips=50.0,
                confidence_threshold=0.6,
                risk_per_trade=0.02
            )
            self.arena.add_strategy(params)
        
        self.assertEqual(len(self.arena.strategies), 10)


class TestEvolutionaryEngine(unittest.TestCase):
    """进化引擎测试"""
    
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.config = {
            "population_size": 10,
            "elite_ratio": 0.2,
            "mutation_rate": 0.2,
            "crossover_rate": 0.7,
            "early_stop_patience": 3,
            "models_dir": os.path.join(self.test_dir, "models"),
            "history_dir": os.path.join(self.test_dir, "history")
        }
    
    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_initialization(self):
        engine = EvolutionaryEngineV2(self.config)
        self.assertEqual(engine.population_size, 10)
        self.assertEqual(engine.elite_ratio, 0.2)
        self.assertEqual(engine.mutation_rate, 0.2)
    
    def test_create_population(self):
        engine = EvolutionaryEngineV2(self.config)
        population = engine.create_initial_population()
        self.assertEqual(len(population), 10)
    
    def test_search_space_bounds(self):
        engine = EvolutionaryEngineV2(self.config)
        params = engine._random_params("trend")
        
        self.assertGreaterEqual(params.rsi_oversold, 20)
        self.assertLessEqual(params.rsi_oversold, 35)
        self.assertGreaterEqual(params.rsi_overbought, 65)
        self.assertLessEqual(params.rsi_overbought, 80)


class TestWalkForwardValidator(unittest.TestCase):
    """Walk Forward 验证测试"""
    
    def setUp(self):
        import numpy as np
        np.random.seed(42)
        
        n_points = 500
        prices = 2000 + np.cumsum(np.random.randn(n_points) * 10)
        
        import pandas as pd
        self.market_data = pd.DataFrame({
            'close': prices,
            'open': np.roll(prices, 1) + np.random.randn(n_points) * 2,
            'high': prices + np.random.rand(n_points) * 20,
            'low': prices - np.random.rand(n_points) * 20,
            'volume': np.random.randint(1000, 10000, n_points)
        })
    
    def test_validator_initialization(self):
        validator = WalkForwardValidator(train_ratio=0.7, n_folds=3)
        self.assertEqual(validator.train_ratio, 0.7)
        self.assertEqual(validator.n_folds, 3)


if __name__ == '__main__':
    unittest.main()
