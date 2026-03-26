# 自我进化训练系统 V2.0
# 解决过拟合、搜索空间爆炸、策略淘汰等问题

import os
import json
import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Set
from pathlib import Path
from dataclasses import dataclass, field, asdict
from abc import ABC, abstractmethod
from copy import deepcopy
import random

logger = logging.getLogger(__name__)


@dataclass
class StrategyParams:
    """策略参数"""
    name: str
    strategy_type: str
    ma_periods: List[int] = field(default_factory=list)
    rsi_period: int = 14
    rsi_oversold: float = 30.0
    rsi_overbought: float = 70.0
    stop_loss_pips: float = 50.0
    take_profit_pips: float = 100.0
    position_size: float = 0.02
    max_positions: int = 3
    trailing_stop_pips: float = 30.0
    trailing_start_pips: float = 50.0
    confidence_threshold: float = 0.6
    risk_per_trade: float = 0.02
    lookback_period: int = 20
    volume_multiplier: float = 2.0
    correlation_threshold: float = 0.7

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> "StrategyParams":
        return cls(**data)


@dataclass
class BacktestResult:
    """回测结果"""
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    total_profit: float = 0.0
    total_loss: float = 0.0
    profit_factor: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    avg_profit_per_trade: float = 0.0
    avg_holding_period: float = 0.0
    in_sample_score: float = 0.0
    out_of_sample_score: float = 0.0
    overfitting_penalty: float = 0.0
    logic_score: float = 0.0
    final_score: float = 0.0


class BaseStrategy(ABC):
    """策略基类"""
    
    def __init__(self, params: StrategyParams):
        self.params = params
    
    @abstractmethod
    def generate_signal(self, data: pd.DataFrame, index: int) -> Dict:
        pass
    
    @abstractmethod
    def get_strategy_type(self) -> str:
        pass


class TrendStrategy(BaseStrategy):
    """趋势策略"""
    
    def get_strategy_type(self) -> str:
        return "trend"
    
    def generate_signal(self, data: pd.DataFrame, index: int) -> Dict:
        if index < max(self.params.ma_periods or [50]) + self.params.rsi_period:
            return {"action": "hold", "confidence": 0}
        
        ma1 = data['close'].iloc[index - self.params.ma_periods[0]:index].mean()
        ma2 = data['close'].iloc[index - self.params.ma_periods[1]:index].mean() if len(self.params.ma_periods) > 1 else ma1
        ma3 = data['close'].iloc[index - self.params.ma_periods[2]:index].mean() if len(self.params.ma_periods) > 2 else ma2
        
        rsi = self._calc_rsi(data['close'], index, self.params.rsi_period)
        
        signal = {"action": "hold", "confidence": 0}
        
        if ma1 > ma2 > ma3 and rsi < self.params.rsi_oversold:
            signal = {
                "action": "buy",
                "confidence": min((self.params.rsi_oversold - rsi) / 30 + 0.5, 0.95),
                "stop_loss": data['close'].iloc[index] * (1 - self.params.stop_loss_pips * 0.0001),
                "take_profit": data['close'].iloc[index] * (1 + self.params.take_profit_pips * 0.0001)
            }
        elif ma1 < ma2 < ma3 and rsi > self.params.rsi_overbought:
            signal = {
                "action": "sell",
                "confidence": min((rsi - self.params.rsi_overbought) / 30 + 0.5, 0.95),
                "stop_loss": data['close'].iloc[index] * (1 + self.params.stop_loss_pips * 0.0001),
                "take_profit": data['close'].iloc[index] * (1 - self.params.take_profit_pips * 0.0001)
            }
        
        return signal
    
    def _calc_rsi(self, prices: pd.Series, index: int, period: int) -> float:
        if index < period:
            return 50.0
        deltas = prices.diff()
        gains = deltas.where(deltas > 0, 0).iloc[index - period:index].mean()
        losses = -deltas.where(deltas < 0, 0).iloc[index - period:index].mean()
        if losses == 0:
            return 100.0
        rs = gains / losses
        return 100 - (100 / (1 + rs))


class BreakoutStrategy(BaseStrategy):
    """突破策略"""
    
    def get_strategy_type(self) -> str:
        return "breakout"
    
    def generate_signal(self, data: pd.DataFrame, index: int) -> Dict:
        if index < self.params.lookback_period:
            return {"action": "hold", "confidence": 0}
        
        lookback = data.iloc[index - self.params.lookback_period:index]
        highest_high = lookback['high'].max()
        lowest_low = lookback['low'].min()
        avg_volume = lookback['volume'].mean()
        current_volume = data['volume'].iloc[index]
        
        current_price = data['close'].iloc[index]
        
        signal = {"action": "hold", "confidence": 0}
        
        if current_price > highest_high and current_volume > avg_volume * self.params.volume_multiplier:
            signal = {
                "action": "buy",
                "confidence": min((current_price - highest_high) / highest_high * 10 + 0.5, 0.9),
                "stop_loss": lowest_low,
                "take_profit": current_price + (highest_high - lowest_low) * 2
            }
        elif current_price < lowest_low and current_volume > avg_volume * self.params.volume_multiplier:
            signal = {
                "action": "sell",
                "confidence": min((lowest_low - current_price) / lowest_low * 10 + 0.5, 0.9),
                "stop_loss": highest_high,
                "take_profit": current_price - (highest_high - lowest_low) * 2
            }
        
        return signal


class ArbitrageStrategy(BaseStrategy):
    """套利策略"""
    
    def get_strategy_type(self) -> str:
        return "arbitrage"
    
    def generate_signal(self, data: pd.DataFrame, index: int) -> Dict:
        if index < 20:
            return {"action": "hold", "confidence": 0}
        
        recent = data['close'].iloc[index - 20:index]
        volatility = recent.std() / recent.mean()
        
        signal = {"action": "hold", "confidence": 0}
        
        if volatility > 0.02:
            momentum = data['close'].iloc[index] - recent.iloc[0]
            if momentum > 0:
                signal = {"action": "buy", "confidence": min(volatility * 20, 0.85)}
            else:
                signal = {"action": "sell", "confidence": min(volatility * 20, 0.85)}
        
        return signal


class StrategyFactory:
    """策略工厂"""
    
    _strategies = {
        "trend": TrendStrategy,
        "breakout": BreakoutStrategy,
        "arbitrage": ArbitrageStrategy,
    }
    
    @classmethod
    def create(cls, params: StrategyParams) -> BaseStrategy:
        strategy_class = cls._strategies.get(params.strategy_type, TrendStrategy)
        return strategy_class(params)
    
    @classmethod
    def register(cls, name: str, strategy_class: type):
        cls._strategies[name] = strategy_class


class LogicValidator:
    """策略逻辑验证器"""
    
    RULES = [
        ("rsi_oversold_lt_overbought", lambda p: p.rsi_oversold < p.rsi_overbought),
        ("ma_periods_ascending", lambda p: p.ma_periods == sorted(p.ma_periods)),
        ("stop_lt_take_profit", lambda p: p.stop_loss_pips < p.take_profit_pips),
        ("reasonable_ma_range", lambda p: all(5 <= m <= 200 for m in p.ma_periods)),
        ("reasonable_rsi_range", lambda p: 20 <= p.rsi_oversold < 50 and 50 < p.rsi_overbought <= 80),
        ("reasonable_position_size", lambda p: 0.001 <= p.position_size <= 0.2),
        ("trailing_start_gt_stop", lambda p: p.trailing_start_pips > p.trailing_stop_pips),
    ]
    
    @classmethod
    def validate(cls, params: StrategyParams) -> Tuple[bool, float]:
        passed = 0
        for rule_name, rule_fn in cls.RULES:
            try:
                if rule_fn(params):
                    passed += 1
            except Exception:
                pass
        
        score = passed / len(cls.RULES)
        is_valid = score >= 0.6
        
        return is_valid, score


class WalkForwardValidator:
    """Walk Forward 分析 - 防止过拟合"""
    
    def __init__(self, train_ratio: float = 0.7, n_folds: int = 3):
        self.train_ratio = train_ratio
        self.n_folds = n_folds
    
    def validate(self, params: StrategyParams, data: pd.DataFrame) -> BacktestResult:
        n = len(data)
        fold_size = n // (self.n_folds + 1)
        
        in_sample_scores = []
        out_of_sample_scores = []
        
        for fold in range(self.n_folds):
            train_end = fold_size * (fold + 1) + fold_size
            test_start = train_end
            test_end = min(test_start + fold_size, n)
            
            train_data = data.iloc[:train_end]
            test_data = data.iloc[test_start:test_end]
            
            in_score = self._backtest(params, train_data)
            in_sample_scores.append(in_score)
            
            out_score = self._backtest(params, test_data)
            out_of_sample_scores.append(out_score)
        
        result = BacktestResult()
        result.in_sample_score = np.mean(in_sample_scores)
        result.out_of_sample_score = np.mean(out_of_sample_scores)
        
        ratio = result.out_of_sample_score / (result.in_sample_score + 1e-10)
        result.overfitting_penalty = max(0, 1 - ratio)
        result.final_score = result.out_of_sample_score * (1 - result.overfitting_penalty * 0.5)
        
        return result
    
    def _backtest(self, params: StrategyParams, data: pd.DataFrame) -> float:
        strategy = StrategyFactory.create(params)
        
        trades = []
        balance = 10000
        peak = balance
        
        for i in range(len(data)):
            signal = strategy.generate_signal(data, i)
            
            if signal["action"] == "hold" or signal["confidence"] < params.confidence_threshold:
                continue
            
            entry_price = data['close'].iloc[i]
            stop_loss = signal.get("stop_loss", entry_price * 0.99)
            take_profit = signal.get("take_profit", entry_price * 1.01)
            
            for j in range(i + 1, len(data)):
                exit_price = data['close'].iloc[j]
                
                if signal["action"] == "buy":
                    if exit_price <= stop_loss:
                        trades.append(-abs(entry_price - stop_loss) * 1000)
                        break
                    elif exit_price >= take_profit:
                        trades.append(abs(take_profit - entry_price) * 1000)
                        break
                else:
                    if exit_price >= stop_loss:
                        trades.append(-abs(stop_loss - entry_price) * 1000)
                        break
                    elif exit_price <= take_profit:
                        trades.append(abs(entry_price - take_profit) * 1000)
                        break
        
        if not trades:
            return 0.0
        
        winning = sum(1 for t in trades if t > 0)
        total = sum(trades)
        win_rate = winning / len(trades) if trades else 0
        
        return total * 0.1 + win_rate * 100


class MultiObjectiveFitness:
    """多目标适应度函数"""
    
    @staticmethod
    def calculate(result: BacktestResult, 
                 trades: List[Dict],
                 logic_score: float) -> Dict[str, float]:
        
        if not trades:
            return {
                "profit": 0,
                "win_rate": 0,
                "risk_adjusted": 0,
                "consistency": 0,
                "final": 0
            }
        
        total_profit = result.total_profit
        win_rate = result.win_rate
        sharpe = result.sharpe_ratio
        drawdown = result.max_drawdown
        
        risk_adjusted = total_profit / (drawdown + 100) if drawdown > 0 else total_profit
        
        profit_consistency = 1.0 - np.std([t.get('profit', 0) for t in trades]) / (abs(np.mean([t.get('profit', 0) for t in trades])) + 1e-10)
        
        final = (
            total_profit * 0.3 +
            win_rate * 0.2 +
            risk_adjusted * 0.2 +
            sharpe * 0.15 +
            profit_consistency * 0.1 +
            logic_score * 0.05
        )
        
        return {
            "profit": total_profit,
            "win_rate": win_rate,
            "risk_adjusted": risk_adjusted,
            "consistency": profit_consistency,
            "final": final
        }


class ArenaBattle:
    """策略竞技场 - 多策略竞争淘汰"""
    
    def __init__(self, population_size: int = 20):
        self.population_size = population_size
        self.strategies: List[StrategyParams] = []
        self.scores: Dict[str, float] = {}
        self.battle_history: List[Dict] = []
    
    def add_strategy(self, strategy: StrategyParams):
        self.strategies.append(strategy)
    
    def battle(self, market_data: pd.DataFrame) -> Dict:
        if len(self.strategies) < 2:
            return {"淘汰": None, "幸存": self.strategies}
        
        results = {}
        for strategy in self.strategies:
            validator = WalkForwardValidator()
            result = validator.validate(strategy, market_data)
            logic_valid, logic_score = LogicValidator.validate(strategy)
            result.logic_score = logic_score
            results[strategy.name] = result
        
        sorted_strategies = sorted(
            self.strategies,
            key=lambda s: results[s.name].final_score,
            reverse=True
        )
        
        eliminated = []
        survivors = []
        
        for i, strategy in enumerate(sorted_strategies):
            if i < len(sorted_strategies) * 0.3:
                eliminated.append(strategy)
            else:
                survivors.append(strategy)
        
        self.battle_history.append({
            "timestamp": datetime.now().isoformat(),
            "eliminated": [s.name for s in eliminated],
            "survivors": [s.name for s in survivors],
            "scores": {s.name: results[s.name].final_score for s in self.strategies}
        })
        
        self.strategies = survivors
        return {"淘汰": eliminated, "幸存": survivors}
    
    def get_top_strategies(self, n: int = 3) -> List[StrategyParams]:
        if not self.scores:
            return []
        
        return sorted(
            self.strategies,
            key=lambda s: self.scores.get(s.name, 0),
            reverse=True
        )[:n]


class EvolutionaryEngineV2:
    """进化引擎 V2 - 解决过拟合和效率问题"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.population_size = config.get("population_size", 30)
        self.elite_ratio = config.get("elite_ratio", 0.1)
        self.mutation_rate = config.get("mutation_rate", 0.1)
        self.crossover_rate = config.get("crossover_rate", 0.7)
        
        self.search_space = self._init_search_space()
        self.population: List[StrategyParams] = []
        self.arena = ArenaBattle()
        
        self.generation = 0
        self.best_score = float('-inf')
        self.early_stop_patience = config.get("early_stop_patience", 10)
        self.no_improve_count = 0
        
        self.models_dir = Path(config.get("models_dir", "training/models"))
        self.history_dir = Path(config.get("history_dir", "training/history"))
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.history_dir.mkdir(parents=True, exist_ok=True)
    
    def _init_search_space(self) -> Dict:
        return {
            "ma_periods": {
                "type": "list_int",
                "min": [5, 10, 20],
                "max": [30, 100, 200],
                "sorted": True
            },
            "rsi_period": {"type": "int", "min": 7, "max": 28},
            "rsi_oversold": {"type": "float", "min": 20, "max": 35},
            "rsi_overbought": {"type": "float", "min": 65, "max": 80},
            "stop_loss_pips": {"type": "float", "min": 20, "max": 200},
            "take_profit_pips": {"type": "float", "min": 50, "max": 500},
            "position_size": {"type": "float", "min": 0.01, "max": 0.1},
            "max_positions": {"type": "int", "min": 1, "max": 5},
            "trailing_stop_pips": {"type": "float", "min": 20, "max": 100},
            "trailing_start_pips": {"type": "float", "min": 30, "max": 150},
            "confidence_threshold": {"type": "float", "min": 0.5, "max": 0.9},
            "risk_per_trade": {"type": "float", "min": 0.01, "max": 0.05},
            "lookback_period": {"type": "int", "min": 10, "max": 50},
            "volume_multiplier": {"type": "float", "min": 1.5, "max": 3.0},
        }
    
    def create_initial_population(self) -> List[StrategyParams]:
        self.population = []
        
        for i in range(self.population_size):
            strategy_type = random.choice(["trend", "breakout", "arbitrage"])
            params = self._random_params(strategy_type)
            params.name = f"strategy_{i:03d}"
            self.population.append(params)
        
        return self.population
    
    def _random_params(self, strategy_type: str) -> StrategyParams:
        space = self.search_space
        
        ma1 = random.randint(space["ma_periods"]["min"][0], space["ma_periods"]["max"][0])
        ma2 = random.randint(space["ma_periods"]["min"][1], space["ma_periods"]["max"][1])
        ma3 = random.randint(space["ma_periods"]["min"][2], space["ma_periods"]["max"][2])
        
        return StrategyParams(
            name="temp",
            strategy_type=strategy_type,
            ma_periods=sorted([ma1, ma2, ma3]),
            rsi_period=random.randint(space["rsi_period"]["min"], space["rsi_period"]["max"]),
            rsi_oversold=random.uniform(space["rsi_oversold"]["min"], space["rsi_oversold"]["max"]),
            rsi_overbought=random.uniform(space["rsi_overbought"]["min"], space["rsi_overbought"]["max"]),
            stop_loss_pips=random.uniform(space["stop_loss_pips"]["min"], space["stop_loss_pips"]["max"]),
            take_profit_pips=random.uniform(space["take_profit_pips"]["min"], space["take_profit_pips"]["max"]),
            position_size=random.uniform(space["position_size"]["min"], space["position_size"]["max"]),
            max_positions=random.randint(space["max_positions"]["min"], space["max_positions"]["max"]),
            trailing_stop_pips=random.uniform(space["trailing_stop_pips"]["min"], space["trailing_stop_pips"]["max"]),
            trailing_start_pips=random.uniform(space["trailing_start_pips"]["min"], space["trailing_start_pips"]["max"]),
            confidence_threshold=random.uniform(space["confidence_threshold"]["min"], space["confidence_threshold"]["max"]),
            risk_per_trade=random.uniform(space["risk_per_trade"]["min"], space["risk_per_trade"]["max"]),
            lookback_period=random.randint(space["lookback_period"]["min"], space["lookback_period"]["max"]),
            volume_multiplier=random.uniform(space["volume_multiplier"]["min"], space["volume_multiplier"]["max"]),
        )
    
    def evolve(self, market_data: pd.DataFrame) -> List[StrategyParams]:
        self._evaluate_population(market_data)
        
        self.arena.battle(market_data)
        
        elite_count = int(self.population_size * self.elite_ratio)
        elites = sorted(
            self.population,
            key=lambda s: self.arena.scores.get(s.name, 0),
            reverse=True
        )[:elite_count]
        
        new_population = deepcopy(elites)
        
        while len(new_population) < self.population_size:
            parent1, parent2 = random.sample(self.population, 2)
            child = self._crossover(parent1, parent2)
            if random.random() < self.mutation_rate:
                child = self._mutate(child)
            
            is_valid, logic_score = LogicValidator.validate(child)
            if is_valid:
                child.name = f"strategy_{len(new_population):03d}"
                new_population.append(child)
        
        self.population = new_population[:self.population_size]
        
        current_best = max(self.arena.scores.values(), default=0)
        if current_best > self.best_score:
            self.best_score = current_best
            self.no_improve_count = 0
        else:
            self.no_improve_count += 1
        
        self.generation += 1
        
        return self.population
    
    def _evaluate_population(self, market_data: pd.DataFrame):
        for strategy in self.population:
            validator = WalkForwardValidator()
            result = validator.validate(strategy, market_data)
            
            is_valid, logic_score = LogicValidator.validate(strategy)
            result.logic_score = logic_score
            
            self.arena.scores[strategy.name] = result.final_score
    
    def _crossover(self, parent1: StrategyParams, parent2: StrategyParams) -> StrategyParams:
        child1_data = asdict(parent1)
        child2_data = asdict(parent2)
        
        if random.random() > self.crossover_rate:
            return StrategyParams(**child1_data)
        
        for key in child1_data.keys():
            if key in ["name", "strategy_type"]:
                continue
            
            if random.random() < 0.5:
                child1_data[key] = child2_data[key]
        
        return StrategyParams(**child1_data)
    
    def _mutate(self, strategy: StrategyParams) -> StrategyParams:
        data = asdict(strategy)
        space = self.search_space
        
        param_to_mutate = random.choice(list(space.keys()))
        param_space = space[param_to_mutate]
        
        if param_space["type"] == "int":
            data[param_to_mutate] = random.randint(param_space["min"], param_space["max"])
        elif param_space["type"] == "float":
            data[param_to_mutate] = random.uniform(param_space["min"], param_space["max"])
        elif param_space["type"] == "list_int":
            new_list = []
            for i, (mn, mx) in enumerate(zip(param_space["min"], param_space["max"])):
                val = random.randint(mn, mx)
                new_list.append(val)
            data[param_to_mutate] = sorted(new_list)
        
        return StrategyParams(**data)
    
    def should_early_stop(self) -> bool:
        return self.no_improve_count >= self.early_stop_patience
    
    def run(self, market_data: pd.DataFrame, max_generations: int = 100) -> StrategyParams:
        logger.info(f"开始进化，最大代数: {max_generations}")
        
        self.create_initial_population()
        
        for gen in range(max_generations):
            if self.should_early_stop():
                logger.info(f"早停于第 {gen} 代")
                break
            
            self.evolve(market_data)
            
            best_score = max(self.arena.scores.values(), default=0)
            avg_score = np.mean(list(self.arena.scores.values()))
            
            logger.info(f"代数 {gen}: 最佳={best_score:.2f}, 平均={avg_score:.2f}")
            
            self._save_generation(gen)
        
        top_strategies = self.arena.get_top_strategies(3)
        if top_strategies:
            self._save_best_model(top_strategies[0])
        
        return top_strategies[0] if top_strategies else None
    
    def _save_generation(self, generation: int):
        data = {
            "generation": generation,
            "timestamp": datetime.now().isoformat(),
            "best_score": self.best_score,
            "strategies": [
                {
                    "name": s.name,
                    "type": s.strategy_type,
                    "score": self.arena.scores.get(s.name, 0),
                    "params": s.to_dict()
                }
                for s in self.population
            ]
        }
        
        filepath = self.history_dir / f"generation_{generation:04d}.json"
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def _save_best_model(self, strategy: StrategyParams):
        filepath = self.models_dir / "best_strategy.json"
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(strategy.to_dict(), f, indent=2, ensure_ascii=False)
        logger.info(f"最佳策略已保存: {strategy.name}, 分数: {self.best_score:.2f}")
    
    def load_best_model(self) -> Optional[StrategyParams]:
        filepath = self.models_dir / "best_strategy.json"
        if filepath.exists():
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return StrategyParams.from_dict(data)
        return None


def create_evolution_engine(config: Dict) -> EvolutionaryEngineV2:
    return EvolutionaryEngineV2(config)


if __name__ == "__main__":
    config = {
        "population_size": 20,
        "elite_ratio": 0.1,
        "mutation_rate": 0.15,
        "crossover_rate": 0.7,
        "early_stop_patience": 15,
    }
    
    engine = create_evolution_engine(config)
    
    np.random.seed(42)
    n_points = 2000
    prices = 2000 + np.cumsum(np.random.randn(n_points) * 10)
    market_data = pd.DataFrame({
        'close': prices,
        'open': np.roll(prices, 1) + np.random.randn(n_points) * 2,
        'high': prices + np.random.rand(n_points) * 20,
        'low': prices - np.random.rand(n_points) * 20,
        'volume': np.random.randint(1000, 10000, n_points)
    })
    
    best_strategy = engine.run(market_data, max_generations=30)
    
    if best_strategy:
        print(f"最佳策略: {best_strategy.name}")
        print(f"类型: {best_strategy.strategy_type}")
        print(f"参数: {best_strategy.to_dict()}")
