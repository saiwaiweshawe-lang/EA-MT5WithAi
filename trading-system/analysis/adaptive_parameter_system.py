# 参数自适应系统
# 根据市场状况和交易表现自动调整策略参数

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import json
import logging

logger = logging.getLogger(__name__)


class ParameterCategory(Enum):
    """参数类别"""
    RISK = "risk"                    # 风险参数
    ENTRY = "entry"                  # 入场参数
    EXIT = "exit"                    # 出场参数
    STOP_LOSS = "stop_loss"          # 止损参数
    TAKE_PROFIT = "take_profit"      # 止盈参数
    POSITION = "position"             # 仓位参数


class AdaptationMode(Enum):
    """自适应模式"""
    VOLATILITY_BASED = "volatility_based"      # 基于波动率
    TREND_BASED = "trend_based"               # 基于趋势
    PERFORMANCE_BASED = "performance_based"      # 基于表现
    HYBRID = "hybrid"                         # 混合模式


@dataclass
class ParameterAdjustment:
    """参数调整"""
    parameter_name: str
    category: ParameterCategory
    old_value: float
    new_value: float
    adjustment_reason: str
    timestamp: datetime
    confidence: float


@dataclass
class ParameterState:
    """参数状态"""
    parameters: Dict[str, float]
    adjustments: List[ParameterAdjustment] = field(default_factory=list)
    last_updated: Optional[datetime] = None
    performance_metrics: Dict[str, float] = field(default_factory=dict)


class PerformanceTracker:
    """表现跟踪器"""

    def __init__(self, max_history: int = 100):
        self.max_history = max_history
        self.trades = []  # 交易历史
        self.metrics_history = []

    def add_trade(self, pnl: float, duration_minutes: float,
                  entry_price: float, exit_price: float):
        """添加交易记录"""
        self.trades.append({
            "pnl": pnl,
            "duration_minutes": duration_minutes,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "timestamp": datetime.now()
        })

        if len(self.trades) > self.max_history:
            self.trades.pop(0)

    def calculate_metrics(self, lookback: int = None) -> Dict[str, float]:
        """计算表现指标"""
        if lookback is None:
            lookback = len(self.trades)
        else:
            lookback = min(lookback, len(self.trades))

        if lookback < 5:
            return {}

        recent_trades = self.trades[-lookback:]

        wins = [t for t in recent_trades if t["pnl"] > 0]
        losses = [t for t in recent_trades if t["pnl"] <= 0]

        win_rate = len(wins) / len(recent_trades)
        avg_win = np.mean([t["pnl"] for t in wins]) if wins else 0
        avg_loss = np.mean([abs(t["pnl"]) for t in losses]) if losses else 0

        total_pnl = sum(t["pnl"] for t in recent_trades)
        avg_duration = np.mean([t["duration_minutes"] for t in recent_trades])

        profit_factor = avg_win / avg_loss if avg_loss > 0 else float('inf')

        # 计算夏普比率 (简化版)
        returns = [t["pnl"] for t in recent_trades]
        sharpe = np.mean(returns) / np.std(returns) if np.std(returns) > 0 else 0

        # 连续统计
        consecutive_losses = 0
        max_consecutive_losses = 0
        current_streak = 0

        for trade in recent_trades:
            if trade["pnl"] < 0:
                consecutive_losses += 1
                current_streak = 0
                max_consecutive_losses = max(max_consecutive_losses, consecutive_losses)
            else:
                consecutive_losses = 0
                current_streak += 1

        metrics = {
            "win_rate": win_rate,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "total_pnl": total_pnl,
            "profit_factor": profit_factor,
            "sharpe_ratio": sharpe,
            "avg_duration_minutes": avg_duration,
            "consecutive_losses": consecutive_losses,
            "max_consecutive_losses": max_consecutive_losses,
            "trade_count": len(recent_trades)
        }

        self.metrics_history.append({
            "timestamp": datetime.now(),
            "metrics": metrics
        })

        return metrics

    def get_recent_trend(self, metric: str, periods: int = 10) -> float:
        """获取指标最近趋势"""
        if len(self.metrics_history) < periods:
            return 0

        recent = self.metrics_history[-periods:]
        values = [m["metrics"].get(metric, 0) for m in recent]

        if len(values) < 2:
            return 0

        # 计算线性趋势
        x = np.arange(len(values))
        y = np.array(values)

        if np.std(y) == 0:
            return 0

        slope = np.polyfit(x, y, 1)[0]

        # 归一化
        return np.clip(slope / np.std(y), -1, 1)


class AdaptiveParameterSystem:
    """自适应参数系统"""

    def __init__(self, config: Dict = None):
        self.config = config or {}

        # 基础参数配置
        self.base_parameters = self.config.get("base_parameters", {
            # 风险参数
            "risk_per_trade": 0.02,
            "max_total_risk": 0.10,

            # 止损参数
            "stop_loss_pct": 0.02,
            "atr_multiplier": 2.0,

            # 止盈参数
            "take_profit_pct": 0.04,
            "risk_reward_ratio": 2.0,

            # 入场参数
            "rsi_entry_threshold": 30,
            "macd_confirmation": True,
            "min_confidence": 0.6,

            # 出场参数
            "trailing_stop_activation": 0.02,
            "trailing_stop_distance": 0.01,

            # 仓位参数
            "max_positions": 3,
            "position_sizing_method": "risk_based"
        })

        # 参数范围限制
        self.parameter_ranges = self.config.get("parameter_ranges", {
            "risk_per_trade": (0.005, 0.10),
            "stop_loss_pct": (0.005, 0.10),
            "take_profit_pct": (0.01, 0.20),
            "atr_multiplier": (1.0, 4.0),
            "trailing_stop_activation": (0.01, 0.05),
            "trailing_stop_distance": (0.005, 0.03)
        })

        # 自适应模式
        self.adaptation_mode = AdaptationMode(
            self.config.get("adaptation_mode", "hybrid")
        )

        # 表现跟踪
        self.performance_tracker = PerformanceTracker(
            self.config.get("max_trades_history", 100)
        )

        # 当前参数状态
        self.parameter_state = ParameterState(
            parameters=self.base_parameters.copy()
        )

        # 调整历史
        self.adjustment_history = []

        # 参数稳定性阈值
        self.min_stable_periods = self.config.get("min_stable_periods", 5)
        self.current_stable_periods = 0

    def get_parameters(self) -> Dict[str, float]:
        """获取当前参数"""
        return self.parameter_state.parameters.copy()

    def update_market_conditions(self, market_analysis: Dict):
        """更新市场条件并调整参数"""
        if self.adaptation_mode in [AdaptationMode.VOLATILITY_BASED,
                                      AdaptationMode.HYBRID]:
            self._adapt_to_volatility(market_analysis)

        if self.adaptation_mode in [AdaptationMode.TREND_BASED,
                                      AdaptationMode.HYBRID]:
            self._adapt_to_trend(market_analysis)

    def record_trade_result(self, pnl: float, duration_minutes: float,
                           entry_price: float, exit_price: float,
                           parameters_used: Dict[str, float]):
        """记录交易结果"""
        self.performance_tracker.add_trade(
            pnl, duration_minutes, entry_price, exit_price
        )

        # 基于表现调整参数
        if self.adaptation_mode in [AdaptationMode.PERFORMANCE_BASED,
                                      AdaptationMode.HYBRID]:
            self._adapt_to_performance(parameters_used)

    def _adapt_to_volatility(self, market_analysis: Dict):
        """根据波动率调整参数"""
        volatility_level = market_analysis.get("volatility_level", "normal")
        volatility_score = market_analysis.get("volatility_score", 0.5)

        adjustments = []

        # 高波动率调整
        if volatility_level == "high":
            adjustments.extend([
                ("stop_loss_pct", 1.5, "扩大止损以适应高波动"),
                ("take_profit_pct", 1.5, "扩大止盈目标"),
                ("atr_multiplier", 1.2, "增加ATR倍数"),
                ("risk_per_trade", 0.7, "降低单笔风险"),
                ("trailing_stop_distance", 1.5, "扩大移动止损距离")
            ])

        elif volatility_level == "extreme_high":
            adjustments.extend([
                ("stop_loss_pct", 2.0, "大幅扩大止损以适应极高波动"),
                ("take_profit_pct", 2.0, "大幅扩大止盈目标"),
                ("atr_multiplier", 1.5, "大幅增加ATR倍数"),
                ("risk_per_trade", 0.5, "大幅降低单笔风险"),
                ("max_positions", 0.5, "减少持仓数量")
            ])

        # 低波动率调整
        elif volatility_level == "low":
            adjustments.extend([
                ("stop_loss_pct", 0.8, "收紧止损"),
                ("take_profit_pct", 0.8, "收紧止盈目标"),
                ("atr_multiplier", 0.9, "减少ATR倍数"),
                ("risk_per_trade", 1.1, "适度增加单笔风险"),
                ("trailing_stop_distance", 0.8, "收紧移动止损距离")
            ])

        elif volatility_level == "extreme_low":
            adjustments.extend([
                ("stop_loss_pct", 0.7, "大幅收紧止损"),
                ("take_profit_pct", 0.7, "大幅收紧止盈目标"),
                ("risk_per_trade", 1.2, "适度增加单笔风险"),
                ("min_confidence", 1.2, "提高入场置信度要求")
            ])

        # 应用调整
        for param_name, multiplier, reason in adjustments:
            self._apply_parameter_adjustment(
                param_name, multiplier, reason, "volatility"
            )

    def _adapt_to_trend(self, market_analysis: Dict):
        """根据趋势调整参数"""
        trend_strength = market_analysis.get("trend_strength", 0.5)
        trend_direction = market_analysis.get("trend_direction", "neutral")
        momentum = market_analysis.get("momentum", 0.5)

        adjustments = []

        # 强趋势调整
        if trend_strength > 0.7:
            adjustments.extend([
                ("trailing_stop_activation", 0.7, "强趋势下更快激活移动止损"),
                ("take_profit_pct", 1.3, "扩大止盈以获得更大利润"),
                ("risk_reward_ratio", 1.2, "增加盈亏比")
            ])

        # 弱趋势调整
        elif trend_strength < 0.3:
            adjustments.extend([
                ("min_confidence", 1.3, "弱趋势下提高入场要求"),
                ("take_profit_pct", 0.7, "收紧止盈目标"),
                ("max_positions", 0.7, "减少持仓数量")
            ])

        # 动量调整
        if momentum > 0.7:
            adjustments.append(
                ("risk_per_trade", 1.2, "强动量下适度增加风险")
            )
        elif momentum < 0.3:
            adjustments.append(
                ("risk_per_trade", 0.8, "弱动量下降低风险")
            )

        # 应用调整
        for param_name, multiplier, reason in adjustments:
            self._apply_parameter_adjustment(
                param_name, multiplier, reason, "trend"
            )

    def _adapt_to_performance(self, parameters_used: Dict[str, float]):
        """根据交易表现调整参数"""
        metrics = self.performance_tracker.calculate_metrics(20)

        if not metrics:
            return

        adjustments = []

        # 胜率调整
        if metrics["win_rate"] > 0.65:
            # 高胜率，可以更激进
            adjustments.extend([
                ("risk_per_trade", 1.1, "高胜率下增加风险暴露"),
                ("stop_loss_pct", 0.9, "高胜率下可以收紧止损")
            ])
        elif metrics["win_rate"] < 0.35:
            # 低胜率，需要更保守
            adjustments.extend([
                ("risk_per_trade", 0.8, "低胜率下降低风险暴露"),
                ("min_confidence", 1.2, "低胜率下提高入场要求")
            ])

        # 盈亏比调整
        if metrics["profit_factor"] > 2.0:
            adjustments.append(
                ("risk_reward_ratio", 1.2, "高盈亏比下可以承担更多风险")
            )
        elif metrics["profit_factor"] < 1.2:
            adjustments.append(
                ("risk_reward_ratio", 0.8, "低盈亏比下需要更保守的盈亏比")
            )

        # 连续亏损调整
        if metrics["consecutive_losses"] >= 3:
            adjustments.extend([
                ("risk_per_trade", 0.5 ** metrics["consecutive_losses"],
                 f"连续{metrics['consecutive_losses']}次亏损后大幅降低风险"),
                ("max_positions", 0.5, "连续亏损后减少持仓数量")
            ])

        # 表现趋势调整
        sharpe_trend = self.performance_tracker.get_recent_trend("sharpe_ratio", 10)
        if sharpe_trend > 0.3:
            # 表现上升趋势
            adjustments.append(
                ("risk_per_trade", 1.1, "表现持续改善时适度增加风险")
            )
        elif sharpe_trend < -0.3:
            # 表现下降趋势
            adjustments.append(
                ("risk_per_trade", 0.8, "表现持续下降时降低风险")
            )

        # 应用调整
        for param_name, multiplier, reason in adjustments:
            self._apply_parameter_adjustment(
                param_name, multiplier, reason, "performance"
            )

    def _apply_parameter_adjustment(self, param_name: str, multiplier: float,
                                    reason: str, source: str):
        """应用参数调整"""
        if param_name not in self.parameter_state.parameters:
            return

        base_value = self.base_parameters.get(param_name, 0)
        current_value = self.parameter_state.parameters[param_name]

        # 计算新值
        new_value = current_value * multiplier

        # 确保在范围内
        if param_name in self.parameter_ranges:
            min_val, max_val = self.parameter_ranges[param_name]
            new_value = max(min_val, min(new_value, max_val))

        # 检查是否有显著变化
        if abs(new_value - current_value) / current_value < 0.05:
            return  # 变化太小，忽略

        # 累积调整次数
        self.current_stable_periods += 1

        # 如果不是性能自适应，需要等待稳定期
        if source != "performance" and self.current_stable_periods < self.min_stable_periods:
            return

        # 应用调整
        old_value = current_value
        self.parameter_state.parameters[param_name] = new_value
        self.parameter_state.last_updated = datetime.now()

        # 记录调整
        adjustment = ParameterAdjustment(
            parameter_name=param_name,
            category=self._get_parameter_category(param_name),
            old_value=old_value,
            new_value=new_value,
            adjustment_reason=reason,
            timestamp=datetime.now(),
            confidence=0.7
        )

        self.parameter_state.adjustments.append(adjustment)
        self.adjustment_history.append(adjustment)

        logger.info(
            f"参数调整: {param_name} {old_value:.4f} -> {new_value:.4f} "
            f"({reason}), 来源: {source}"
        )

    def _get_parameter_category(self, param_name: str) -> ParameterCategory:
        """获取参数类别"""
        risk_params = ["risk_per_trade", "max_total_risk"]
        stop_loss_params = ["stop_loss_pct", "atr_multiplier", "trailing_stop_distance"]
        take_profit_params = ["take_profit_pct", "risk_reward_ratio", "trailing_stop_activation"]
        entry_params = ["rsi_entry_threshold", "macd_confirmation", "min_confidence"]
        position_params = ["max_positions", "position_sizing_method"]

        if param_name in risk_params:
            return ParameterCategory.RISK
        elif param_name in stop_loss_params:
            return ParameterCategory.STOP_LOSS
        elif param_name in take_profit_params:
            return ParameterCategory.TAKE_PROFIT
        elif param_name in entry_params:
            return ParameterCategory.ENTRY
        elif param_name in position_params:
            return ParameterCategory.POSITION
        else:
            return ParameterCategory.EXIT

    def get_parameter_report(self) -> Dict:
        """获取参数报告"""
        return {
            "current_parameters": self.parameter_state.parameters,
            "base_parameters": self.base_parameters,
            "adjustment_count": len(self.parameter_state.adjustments),
            "last_adjustment": (
                self.parameter_state.adjustments[-1].timestamp.isoformat()
                if self.parameter_state.adjustments else None
            ),
            "performance_metrics": self.performance_tracker.calculate_metrics(30),
            "adjustment_history": [
                {
                    "parameter": adj.parameter_name,
                    "from": adj.old_value,
                    "to": adj.new_value,
                    "reason": adj.adjustment_reason,
                    "timestamp": adj.timestamp.isoformat()
                }
                for adj in self.parameter_state.adjustments[-10:]  # 最近10次
            ]
        }

    def reset_to_base(self):
        """重置为基础参数"""
        self.parameter_state.parameters = self.base_parameters.copy()
        self.parameter_state.adjustments = []
        self.parameter_state.last_updated = datetime.now()
        self.current_stable_periods = 0
        logger.info("参数已重置为基础值")

    def save_state(self, filepath: str):
        """保存状态到文件"""
        state = {
            "current_parameters": self.parameter_state.parameters,
            "base_parameters": self.base_parameters,
            "adjustments": [
                {
                    "parameter_name": adj.parameter_name,
                    "category": adj.category.value,
                    "old_value": adj.old_value,
                    "new_value": adj.new_value,
                    "adjustment_reason": adj.adjustment_reason,
                    "timestamp": adj.timestamp.isoformat(),
                    "confidence": adj.confidence
                }
                for adj in self.parameter_state.adjustments
            ],
            "last_updated": (
                self.parameter_state.last_updated.isoformat()
                if self.parameter_state.last_updated else None
            ),
            "trades": self.performance_tracker.trades
        }

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2, ensure_ascii=False)

        logger.info(f"参数状态已保存到 {filepath}")

    def load_state(self, filepath: str):
        """从文件加载状态"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                state = json.load(f)

            self.parameter_state.parameters = state.get("current_parameters", self.base_parameters.copy())
            self.base_parameters = state.get("base_parameters", self.base_parameters)

            # 加载调整历史
            self.parameter_state.adjustments = [
                ParameterAdjustment(
                    parameter_name=adj["parameter_name"],
                    category=ParameterCategory(adj["category"]),
                    old_value=adj["old_value"],
                    new_value=adj["new_value"],
                    adjustment_reason=adj["adjustment_reason"],
                    timestamp=datetime.fromisoformat(adj["timestamp"]),
                    confidence=adj.get("confidence", 0.7)
                )
                for adj in state.get("adjustments", [])
            ]

            # 加载交易历史
            self.performance_tracker.trades = state.get("trades", [])

            if "last_updated" in state:
                self.parameter_state.last_updated = datetime.fromisoformat(state["last_updated"])

            logger.info(f"参数状态已从 {filepath} 加载")

        except Exception as e:
            logger.error(f"加载参数状态失败: {e}")


class MultiParameterOptimizer:
    """多参数优化器 - 基于贝叶斯优化或遗传算法"""

    def __init__(self, config: Dict = None):
        self.config = config or {}

        # 参数搜索空间
        self.search_space = self.config.get("search_space", {})

        # 历史记录
        self.history = []

    def optimize(self, objective_function: Callable,
                 iterations: int = 50) -> Tuple[Dict[str, float], float]:
        """
        优化参数

        参数:
            objective_function: 目标函数,接受参数字典,返回评分
            iterations: 迭代次数

        返回:
            (best_parameters, best_score)
        """
        best_params = {}
        best_score = float('-inf')

        # 简化的网格搜索 (实际项目中可以使用贝叶斯优化)
        for _ in range(iterations):
            # 生成随机参数
            params = self._generate_random_params()

            # 评估
            try:
                score = objective_function(params)
            except Exception as e:
                logger.error(f"参数评估失败: {e}")
                continue

            # 记录历史
            self.history.append({
                "parameters": params,
                "score": score,
                "timestamp": datetime.now()
            })

            # 更新最佳
            if score > best_score:
                best_score = score
                best_params = params

        logger.info(f"参数优化完成, 最佳评分: {best_score:.4f}")
        return best_params, best_score

    def _generate_random_params(self) -> Dict[str, float]:
        """生成随机参数"""
        params = {}
        for param_name, (min_val, max_val) in self.search_space.items():
            params[param_name] = np.random.uniform(min_val, max_val)
        return params


def create_adaptive_parameter_system(config: Dict = None) -> AdaptiveParameterSystem:
    """创建自适应参数系统"""
    return AdaptiveParameterSystem(config)


if __name__ == "__main__":
    # 测试代码
    config = {
        "adaptation_mode": "hybrid",
        "base_parameters": {
            "risk_per_trade": 0.02,
            "stop_loss_pct": 0.02,
            "take_profit_pct": 0.04,
            "atr_multiplier": 2.0,
            "min_confidence": 0.6
        },
        "parameter_ranges": {
            "risk_per_trade": (0.005, 0.10),
            "stop_loss_pct": (0.005, 0.10),
            "take_profit_pct": (0.01, 0.20)
        }
    }

    system = AdaptiveParameterSystem(config)

    print("\n=== 参数自适应系统测试 ===")

    # 测试1: 高波动率调整
    print("\n1. 高波动率市场调整:")
    system.update_market_conditions({
        "volatility_level": "high",
        "volatility_score": 0.8,
        "trend_strength": 0.5,
        "trend_direction": "neutral",
        "momentum": 0.5
    })
    print("当前参数:", system.get_parameters())

    # 测试2: 强趋势调整
    print("\n2. 强上升趋势调整:")
    system.update_market_conditions({
        "volatility_level": "normal",
        "volatility_score": 0.4,
        "trend_strength": 0.8,
        "trend_direction": "up",
        "momentum": 0.7
    })
    print("当前参数:", system.get_parameters())

    # 测试3: 记录交易结果并调整
    print("\n3. 记录交易并调整参数:")
    for i in range(30):
        pnl = np.random.choice([100, -50, 150, -80, 200, -30, 120])
        system.record_trade_result(pnl, 120, 40000, 40200, system.get_parameters())

    print("调整后参数:", system.get_parameters())
    print("\n参数报告:")
    report = system.get_parameter_report()
    for key, value in report.items():
        if key == "adjustment_history" and value:
            print(f"\n  {key}:")
            for adj in value[-5:]:  # 显示最近5次
                print(f"    {adj['parameter']}: {adj['from']:.4f} -> {adj['to']:.4f}")
        elif key == "performance_metrics" and value:
            print(f"\n  {key}:")
            for k, v in value.items():
                print(f"    {k}: {v:.4f}" if isinstance(v, float) else f"    {k}: {v}")
        else:
            print(f"  {key}: {value}")
