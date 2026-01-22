# 自我进化训练系统
# 让交易模型通过历史数据和实时反馈不断进化

import os
import json
import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import sqlite3
from dataclasses import dataclass, asdict
import pickle

logger = logging.getLogger(__name__)


@dataclass
class ModelParameters:
    """模型参数"""
    ma_periods: List[int]
    rsi_period: int
    rsi_oversold: float
    rsi_overbought: float
    stop_loss_pips: int
    take_profit_pips: int
    position_size: float
    max_positions: int
    trailing_stop_pips: int
    trailing_start_pips: int
    confidence_threshold: float
    risk_per_trade: float


@dataclass
class PerformanceMetrics:
    """性能指标"""
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_profit: float
    total_loss: float
    profit_factor: float
    max_drawdown: float
    sharpe_ratio: float
    avg_profit_per_trade: float
    avg_holding_period: float


class EvolutionEngine:
    """进化引擎"""

    def __init__(self, config: Dict):
        self.config = config
        self.models_dir = config.get("models_dir", "training/models")
        self.history_dir = config.get("history_dir", "training/history")
        self.generation_size = config.get("generation_size", 20)
        self.elitism_rate = config.get("elitism_rate", 0.1)
        self.mutation_rate = config.get("mutation_rate", 0.15)
        self.crossover_rate = config.get("crossover_rate", 0.7)

        Path(self.models_dir).mkdir(parents=True, exist_ok=True)
        Path(self.history_dir).mkdir(parents=True, exist_ok=True)

        self.current_generation = 0
        self.best_fitness = float('-inf')

    def create_initial_population(self) -> List[ModelParameters]:
        """创建初始种群"""
        population = []

        for _ in range(self.generation_size):
            params = self._random_parameters()
            population.append(params)

        return population

    def _random_parameters(self) -> ModelParameters:
        """生成随机参数"""
        ma_periods = sorted([
            np.random.randint(5, 30),
            np.random.randint(10, 50),
            np.random.randint(20, 100)
        ])

        return ModelParameters(
            ma_periods=ma_periods,
            rsi_period=np.random.randint(7, 25),
            rsi_oversold=np.random.uniform(20, 35),
            rsi_overbought=np.random.uniform(65, 80),
            stop_loss_pips=np.random.randint(50, 500),
            take_profit_pips=np.random.randint(100, 1000),
            position_size=np.random.uniform(0.01, 0.1),
            max_positions=np.random.randint(1, 10),
            trailing_stop_pips=np.random.randint(50, 200),
            trailing_start_pips=np.random.randint(50, 300),
            confidence_threshold=np.random.uniform(0.5, 0.9),
            risk_per_trade=np.random.uniform(0.01, 0.05)
        )

    def evaluate_fitness(self,
                       params: ModelParameters,
                       price_data: pd.DataFrame) -> float:
        """评估参数适应度"""
        try:
            # 使用参数进行回测
            results = self._backtest(params, price_data)

            # 计算适应度（结合多个指标）
            fitness = self._calculate_fitness_score(results)

            return fitness

        except Exception as e:
            logger.error(f"评估适应度失败: {e}")
            return float('-inf')

    def _backtest(self,
                  params: ModelParameters,
                  price_data: pd.DataFrame) -> Dict:
        """回测"""
        trades = []
        balance = 10000
        position = None

        for i in range(len(price_data)):
            current_data = price_data.iloc[i]
            price = current_data['close']

            # 计算指标
            if i < max(params.ma_periods):
                continue

            indicators = self._calculate_indicators(price_data, params, i)

            # 交易信号
            signal = self._generate_signal(indicators, params)

            # 执行交易
            if position is None:
                if signal['action'] != 'hold':
                    position = {
                        'entry_price': price,
                        'action': signal['action'],
                        'stop_loss': signal.get('stop_loss'),
                        'take_profit': signal.get('take_profit'),
                        'entry_time': current_data.get('time', i)
                    }
            else:
                # 检查止损止盈
                if position['action'] == 'buy':
                    if price <= position['stop_loss'] or price >= position['take_profit']:
                        profit = (price - position['entry_price']) * params.position_size * 100000
                        trades.append({
                            'type': 'buy',
                            'entry': position['entry_price'],
                            'exit': price,
                            'profit': profit
                        })
                        position = None
                else:
                    if price >= position['stop_loss'] or price <= position['take_profit']:
                        profit = (position['entry_price'] - price) * params.position_size * 100000
                        trades.append({
                            'type': 'sell',
                            'entry': position['entry_price'],
                            'exit': price,
                            'profit': profit
                        })
                        position = None

        return {"trades": trades, "balance": balance + sum(t['profit'] for t in trades)}

    def _calculate_indicators(self,
                           price_data: pd.DataFrame,
                           params: ModelParameters,
                           index: int) -> Dict:
        """计算技术指标"""
        indicators = {}

        # 移动平均线
        for period in params.ma_periods:
            ma_key = f"MA{period}"
            indicators[ma_key] = price_data['close'].iloc[index - period + 1:index + 1].mean()

        # RSI
        indicators['RSI'] = self._calculate_rsi(price_data['close'], params.rsi_period, index)

        return indicators

    def _calculate_rsi(self, prices: pd.Series, period: int, index: int) -> float:
        """计算RSI"""
        if index < period:
            return 50

        deltas = prices.diff()
        gains = deltas.where(deltas > 0, 0)
        losses = -deltas.where(deltas < 0, 0)

        avg_gain = gains.iloc[index - period + 1:index + 1].mean()
        avg_loss = losses.iloc[index - period + 1:index + 1].mean()

        if avg_loss == 0:
            return 100

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return rsi

    def _generate_signal(self,
                       indicators: Dict,
                       params: ModelParameters) -> Dict:
        """生成交易信号"""
        ma_short = indicators[f"MA{params.ma_periods[0]}"]
        ma_mid = indicators[f"MA{params.ma_periods[1]}"]
        ma_long = indicators[f"MA{params.ma_periods[2]}"]
        rsi = indicators['RSI']
        current_price = ma_short

        signal = {"action": "hold"}

        # 判断MA趋势
        ma_bullish = ma_short > ma_mid > ma_long
        ma_bearish = ma_short < ma_mid < ma_long

        # 生成信号
        if ma_bullish and rsi < params.rsi_oversold:
            signal = {
                "action": "buy",
                "confidence": 0.7 + (params.rsi_oversold - rsi) * 0.01,
                "stop_loss": current_price - params.stop_loss_pips * 0.0001,
                "take_profit": current_price + params.take_profit_pips * 0.0001
            }
        elif ma_bearish and rsi > params.rsi_overbought:
            signal = {
                "action": "sell",
                "confidence": 0.7 + (rsi - params.rsi_overbought) * 0.01,
                "stop_loss": current_price + params.stop_loss_pips * 0.0001,
                "take_profit": current_price - params.take_profit_pips * 0.0001
            }

        return signal

    def _calculate_fitness_score(self, results: Dict) -> float:
        """计算适应度得分"""
        trades = results.get("trades", [])
        final_balance = results.get("balance", 10000)

        if not trades:
            return 0

        # 计算各项指标
        total_profit = sum(t['profit'] for t in trades)
        winning_trades = sum(1 for t in trades if t['profit'] > 0)
        losing_trades = sum(1 for t in trades if t['profit'] < 0)
        win_rate = winning_trades / len(trades) if trades else 0

        profit_factor = (
            sum(t['profit'] for t in trades if t['profit'] > 0) /
            abs(sum(t['profit'] for t in trades if t['profit'] < 0))
            if losing_trades > 0 else float('inf')
        )

        # 综合评分（可调整权重）
        score = (
            total_profit * 1.0 +
            win_rate * 5000 +
            profit_factor * 2000 -
            max(0, -total_profit) * 2  # 惩罚亏损
        )

        return score

    def selection(self,
                population: List[ModelParameters],
                fitness_scores: List[float]) -> List[ModelParameters]:
        """选择（锦标赛选择）"""
        tournament_size = 3
        selected = []

        for _ in range(len(population)):
            # 随机选择几个个体
            tournament_indices = np.random.choice(
                len(population),
                min(tournament_size, len(population)),
                replace=False
            )

            # 选择适应度最高的
            best_idx = tournament_indices[np.argmax([fitness_scores[i] for i in tournament_indices])]
            selected.append(population[best_idx])

        return selected

    def crossover(self,
                 parent1: ModelParameters,
                 parent2: ModelParameters) -> Tuple[ModelParameters, ModelParameters]:
        """交叉（单点交叉）"""
        if np.random.random() > self.crossover_rate:
            return parent1, parent2

        # MA周期交叉
        crossover_point = np.random.randint(1, len(parent1.ma_periods) - 1)

        child1_ma = parent1.ma_periods[:crossover_point] + parent2.ma_periods[crossover_point:]
        child2_ma = parent2.ma_periods[:crossover_point] + parent1.ma_periods[crossover_point:]

        # 其他参数交叉
        if np.random.random() > 0.5:
            child1 = ModelParameters(
                ma_periods=sorted(child1_ma),
                rsi_period=parent1.rsi_period,
                rsi_oversold=parent1.rsi_oversold,
                rsi_overbought=parent2.rsi_overbought,
                stop_loss_pips=parent2.stop_loss_pips,
                take_profit_pips=parent1.take_profit_pips,
                position_size=parent1.position_size,
                max_positions=parent2.max_positions,
                trailing_stop_pips=parent2.trailing_stop_pips,
                trailing_start_pips=parent1.trailing_start_pips,
                confidence_threshold=parent2.confidence_threshold,
                risk_per_trade=parent1.risk_per_trade
            )
            child2 = ModelParameters(
                ma_periods=sorted(child2_ma),
                rsi_period=parent2.rsi_period,
                rsi_oversold=parent2.rsi_oversold,
                rsi_overbought=parent1.rsi_overbought,
                stop_loss_pips=parent1.stop_loss_pips,
                take_profit_pips=parent2.take_profit_pips,
                position_size=parent2.position_size,
                max_positions=parent1.max_positions,
                trailing_stop_pips=parent1.trailing_stop_pips,
                trailing_start_pips=parent2.trailing_start_pips,
                confidence_threshold=parent1.confidence_threshold,
                risk_per_trade=parent2.risk_per_trade
            )
        else:
            child1, child2 = parent1, parent2

        return child1, child2

    def mutate(self, individual: ModelParameters) -> ModelParameters:
        """变异"""
        if np.random.random() > self.mutation_rate:
            return individual

        params_dict = asdict(individual)

        # 随机选择一个参数进行变异
        param_to_mutate = np.random.choice(list(params_dict.keys()))

        if param_to_mutate == "ma_periods":
            idx = np.random.randint(0, len(params_dict["ma_periods"]))
            params_dict["ma_periods"][idx] = np.clip(
                params_dict["ma_periods"][idx] + np.random.randint(-5, 5),
                5, 100
            )
            params_dict["ma_periods"] = sorted(params_dict["ma_periods"])
        elif param_to_mutate == "rsi_period":
            params_dict["rsi_period"] = np.clip(
                params_dict["rsi_period"] + np.random.randint(-3, 3),
                7, 25
            )
        elif param_to_mutate == "rsi_oversold":
            params_dict["rsi_oversold"] = np.clip(
                params_dict["rsi_oversold"] + np.random.uniform(-5, 5),
                20, 35
            )
        elif param_to_mutate == "rsi_overbought":
            params_dict["rsi_overbought"] = np.clip(
                params_dict["rsi_overbought"] + np.random.uniform(-5, 5),
                65, 80
            )
        elif param_to_mutate in ["stop_loss_pips", "take_profit_pips"]:
            params_dict[param_to_mutate] = np.clip(
                params_dict[param_to_mutate] + np.random.randint(-50, 50),
                50, 1000
            )
        elif param_to_mutate == "position_size":
            params_dict["position_size"] = np.clip(
                params_dict["position_size"] + np.random.uniform(-0.01, 0.01),
                0.01, 0.1
            )
        elif param_to_mutate in ["max_positions", "trailing_stop_pips", "trailing_start_pips"]:
            params_dict[param_to_mutate] = np.clip(
                params_dict[param_to_mutate] + np.random.randint(-10, 10),
                1, 50
            )
        elif param_to_mutate in ["confidence_threshold", "risk_per_trade"]:
            params_dict[param_to_mutate] = np.clip(
                params_dict[param_to_mutate] + np.random.uniform(-0.05, 0.05),
                0.01, 1.0
            )

        return ModelParameters(**params_dict)

    def evolve(self,
               population: List[ModelParameters],
               fitness_scores: List[float]) -> List[ModelParameters]:
        """进化一代"""
        # 精英保留
        elite_size = int(self.generation_size * self.elitism_rate)
        elite_indices = np.argsort(fitness_scores)[-elite_size:]
        elite = [population[i] for i in elite_indices]

        # 选择
        selected = self.selection(population, fitness_scores)

        # 交叉和变异
        new_population = elite.copy()

        while len(new_population) < self.generation_size:
            parent1, parent2 = np.random.choice(selected, 2, replace=False)
            child1, child2 = self.crossover(parent1, parent2)
            child1 = self.mutate(child1)
            child2 = self.mutate(child2)

            new_population.extend([child1, child2])

        new_population = new_population[:self.generation_size]

        # 更新最优适应度
        new_best_fitness = max(fitness_scores)
        if new_best_fitness > self.best_fitness:
            self.best_fitness = new_best_fitness
            self._save_best_model(elite[-1])

        return new_population

    def _save_best_model(self, params: ModelParameters):
        """保存最佳模型"""
        filepath = os.path.join(self.models_dir, "best_model.pkl")
        with open(filepath, 'wb') as f:
            pickle.dump(params, f)
        logger.info(f"最佳模型已保存，适应度: {self.best_fitness:.2f}")

    def load_best_model(self) -> Optional[ModelParameters]:
        """加载最佳模型"""
        filepath = os.path.join(self.models_dir, "best_model.pkl")
        if os.path.exists(filepath):
            with open(filepath, 'rb') as f:
                return pickle.load(f)
        return None

    def save_generation(self,
                      generation: int,
                      population: List[ModelParameters],
                      fitness_scores: List[float]):
        """保存一代"""
        data = {
            "generation": generation,
            "timestamp": datetime.now().isoformat(),
            "best_fitness": max(fitness_scores),
            "avg_fitness": np.mean(fitness_scores),
            "best_params": asdict(population[np.argmax(fitness_scores)])
        }

        filepath = os.path.join(self.history_dir, f"generation_{generation:04d}.json")
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def run_evolution(self,
                     price_data: pd.DataFrame,
                     max_generations: int = 100,
                     convergence_threshold: float = 0.001) -> ModelParameters:
        """运行进化算法"""
        logger.info(f"开始进化算法，最大代数: {max_generations}")

        population = self.create_initial_population()

        for gen in range(max_generations):
            self.current_generation = gen

            # 评估适应度
            fitness_scores = [
                self.evaluate_fitness(params, price_data)
                for params in population
            ]

            best_fitness = max(fitness_scores)
            avg_fitness = np.mean(fitness_scores)

            logger.info(f"代数 {gen}: 最佳适应度={best_fitness:.2f}, 平均={avg_fitness:.2f}")

            # 保存这一代
            self.save_generation(gen, population, fitness_scores)

            # 检查收敛
            if gen > 10:
                recent_best = [
                    self._load_generation_info(g)["best_fitness"]
                    for g in range(gen - 10, gen + 1)
                ]
                if np.std(recent_best) < convergence_threshold * np.mean(recent_best):
                    logger.info(f"算法收敛于第 {gen} 代")
                    break

            # 进化
            population = self.evolve(population, fitness_scores)

        best_model = population[np.argmax(fitness_scores)]
        logger.info(f"进化完成，最佳适应度: {self.best_fitness:.2f}")

        return best_model

    def _load_generation_info(self, generation: int) -> Dict:
        """加载代信息"""
        filepath = os.path.join(self.history_dir, f"generation_{generation:04d}.json")
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def get_evolution_history(self) -> List[Dict]:
        """获取进化历史"""
        history = []

        for filepath in sorted(Path(self.history_dir).glob("generation_*.json")):
            with open(filepath, 'r', encoding='utf-8') as f:
                history.append(json.load(f))

        return history


class OnlineLearner:
    """在线学习器 - 使用实时数据持续优化"""

    def __init__(self, config: Dict, trade_logger):
        self.config = config
        self.trade_logger = trade_logger
        self.learning_rate = config.get("learning_rate", 0.01)
        self.window_size = config.get("window_size", 100)
        self.min_trades_for_update = config.get("min_trades_for_update", 10)

        self.params = self._load_or_init_params()
        self.trade_history = []

    def _load_or_init_params(self) -> Dict:
        """加载或初始化参数"""
        params_path = os.path.join(self.models_dir, "online_params.json")
        if os.path.exists(params_path):
            with open(params_path, 'r', encoding='utf-8') as f:
                return json.load(f)

        return self._init_params()

    def _init_params(self) -> Dict:
        """初始化参数"""
        return {
            "rsi_threshold": 70,
            "ma_weight": 0.5,
            "news_weight": 0.3,
            "volume_weight": 0.2,
            "stop_loss_multiplier": 1.5,
            "take_profit_multiplier": 2.0
        }

    def add_trade_result(self, trade: Dict):
        """添加交易结果"""
        self.trade_history.append(trade)

        # 保持历史窗口
        if len(self.trade_history) > self.window_size:
            self.trade_history = self.trade_history[-self.window_size:]

        # 当有足够交易时更新参数
        if len(self.trade_history) >= self.min_trades_for_update:
            self.update_params()

    def update_params(self):
        """更新参数"""
        logger.info("开始在线学习更新参数...")

        # 计算各指标的有效性
        rsi_effectiveness = self._calculate_rsi_effectiveness()
        ma_effectiveness = self._calculate_ma_effectiveness()
        news_effectiveness = self._calculate_news_effectiveness()

        # 根据有效性调整权重
        total = rsi_effectiveness + ma_effectiveness + news_effectiveness

        if total > 0:
            self.params["ma_weight"] = (self.params["ma_weight"] * (1 - self.learning_rate) +
                                      (ma_effectiveness / total) * self.learning_rate)
            self.params["news_weight"] = (self.params["news_weight"] * (1 - self.learning_rate) +
                                        (news_effectiveness / total) * self.learning_rate)
            self.params["volume_weight"] = 1 - self.params["ma_weight"] - self.params["news_weight"]

        # 调整止损止盈倍数
        profit_loss_ratio = self._calculate_profit_loss_ratio()
        if profit_loss_ratio < 1.5:
            self.params["stop_loss_multiplier"] *= 1.05
        elif profit_loss_ratio > 3:
            self.params["take_profit_multiplier"] *= 1.02

        self._save_params()
        logger.info("参数更新完成")

    def _calculate_rsi_effectiveness(self) -> float:
        """计算RSI指标有效性"""
        success_count = 0
        total_count = 0

        for trade in self.trade_history:
            indicators = trade.get("indicators", {})
            if "RSI" in indicators:
                rsi = indicators["RSI"]
                profit = trade.get("profit", 0)

                if (rsi > 70 and profit < 0) or (rsi < 30 and profit > 0):
                    success_count += 1
                total_count += 1

        return success_count / total_count if total_count > 0 else 0.5

    def _calculate_ma_effectiveness(self) -> float:
        """计算MA指标有效性"""
        # 简化实现
        return 0.5 + np.random.uniform(-0.1, 0.1)

    def _calculate_news_effectiveness(self) -> float:
        """计算新闻情绪有效性"""
        success_count = 0
        total_count = 0

        for trade in self.trade_history:
            sentiment = trade.get("news_sentiment")
            if sentiment:
                profit = trade.get("profit", 0)

                if (sentiment == "positive" and profit > 0) or \
                   (sentiment == "negative" and profit < 0):
                    success_count += 1
                total_count += 1

        return success_count / total_count if total_count > 0 else 0.5

    def _calculate_profit_loss_ratio(self) -> float:
        """计算盈亏比"""
        winning_profit = sum(t["profit"] for t in self.trade_history if t["profit"] > 0)
        losing_loss = abs(sum(t["profit"] for t in self.trade_history if t["profit"] < 0))

        return winning_profit / losing_loss if losing_loss > 0 else 1.0

    def _save_params(self):
        """保存参数"""
        params_path = os.path.join(self.models_dir, "online_params.json")
        with open(params_path, 'w', encoding='utf-8') as f:
            json.dump(self.params, f, indent=2, ensure_ascii=False)

    def get_params(self) -> Dict:
        """获取当前参数"""
        return self.params.copy()


def create_evolution_engine(config: Dict) -> EvolutionEngine:
    """创建进化引擎"""
    return EvolutionEngine(config)


def create_online_learner(config: Dict, trade_logger) -> OnlineLearner:
    """创建在线学习器"""
    return OnlineLearner(config, trade_logger)


if __name__ == "__main__":
    # 测试代码
    config = {
        "models_dir": "training/models",
        "history_dir": "training/history",
        "generation_size": 10,
        "elitism_rate": 0.1,
        "mutation_rate": 0.15,
        "crossover_rate": 0.7
    }

    engine = EvolutionEngine(config)

    # 生成模拟价格数据
    np.random.seed(42)
    n_points = 1000
    prices = 2000 + np.cumsum(np.random.randn(n_points) * 10)
    price_data = pd.DataFrame({
        'close': prices,
        'open': np.roll(prices, 1) + np.random.randn(n_points) * 2,
        'high': prices + np.random.rand(n_points) * 20,
        'low': prices - np.random.rand(n_points) * 20
    })

    # 运行进化
    best_model = engine.run_evolution(price_data, max_generations=5)

    print(f"最佳参数: {asdict(best_model)}")
