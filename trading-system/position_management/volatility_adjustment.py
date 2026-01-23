# 波动率调仓模块
# 高波动市场(ATR>平均值的1.5倍)使用50%标准仓位
# 低波动市场(ATR<平均值的0.7倍)使用120%标准仓位

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import logging
import pandas as pd
from collections import deque

logger = logging.getLogger(__name__)


class VolatilityLevel(Enum):
    """波动率等级"""
    EXTREME_LOW = "extreme_low"      # 极低
    LOW = "low"                       # 低
    NORMAL = "normal"                 # 正常
    HIGH = "high"                     # 高
    EXTREME_HIGH = "extreme_high"    # 极高


@dataclass
class VolatilityState:
    """波动率状态"""
    level: VolatilityLevel
    current_atr: float
    atr_pct: float                  # ATR占价格的百分比
    average_atr: float              # 平均ATR
    adjustment_factor: float         # 调整因子
    recommended_position_multiplier: float


class VolatilityAdjustment:
    """波动率调仓策略"""

    def __init__(self, config: Dict = None):
        self.config = config or {}

        # ATR参数
        self.atr_period = self.config.get("atr_period", 14)
        self.atr_ma_period = self.config.get("atr_ma_period", 50)

        # 波动率阈值
        self.volatility_thresholds = self.config.get("volatility_thresholds", {
            "extreme_low": 0.002,     # 0.2%
            "low": 0.005,            # 0.5%
            "normal": 0.015,          # 1.5%
            "high": 0.025             # 2.5%
        })

        # 仓位调整因子
        self.position_adjustments = self.config.get("position_adjustments", {
            "extreme_low": 1.2,       # 极低波动时增加仓位
            "low": 1.1,              # 低波动时小幅增加
            "normal": 1.0,            # 正常波动时标准仓位
            "high": 0.7,              # 高波动时减少仓位
            "extreme_high": 0.5       # 极高波动时大幅减少
        })

        # ATR历史记录（用于计算平均值）
        self.atr_history: deque = deque(maxlen=self.atr_ma_period)

        # 最小和最大调整因子
        self.min_multiplier = self.config.get("min_multiplier", 0.3)
        self.max_multiplier = self.config.get("max_multiplier", 1.5)

        # 平滑调整
        self.smoothing_factor = self.config.get("smoothing_factor", 0.3)
        self.current_multiplier = 1.0

    def calculate_atr(self, highs: List[float], lows: List[float],
                     closes: List[float]) -> float:
        """
        计算ATR（平均真实波幅）

        参数:
            highs: 最高价列表
            lows: 最低价列表
            closes: 收盘价列表

        返回:
            ATR值
        """
        if len(closes) < self.atr_period + 1:
            if len(closes) >= 2:
                return sum(abs(closes[i] - closes[i-1]) for i in range(1, len(closes))) / (len(closes) - 1)
            return 0

        df = pd.DataFrame({
            'high': highs,
            'low': lows,
            'close': closes
        })

        prev_close = df['close'].shift(1)
        tr1 = df['high'] - df['low']
        tr2 = abs(df['high'] - prev_close)
        tr3 = abs(df['low'] - prev_close)
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        atr = tr.rolling(window=self.atr_period).mean()

        return atr.iloc[-1]

    def get_average_atr(self) -> Optional[float]:
        """获取平均ATR"""
        if len(self.atr_history) < 10:
            return None
        return sum(self.atr_history) / len(self.atr_history)

    def classify_volatility(self, atr: float, current_price: float) -> VolatilityLevel:
        """
        分类波动率等级

        参数:
            atr: ATR值
            current_price: 当前价格

        返回:
            VolatilityLevel
        """
        atr_pct = atr / current_price

        thresholds = self.volatility_thresholds

        if atr_pct < thresholds["extreme_low"]:
            return VolatilityLevel.EXTREME_LOW
        elif atr_pct < thresholds["low"]:
            return VolatilityLevel.LOW
        elif atr_pct < thresholds["normal"]:
            return VolatilityLevel.NORMAL
        elif atr_pct < thresholds["high"]:
            return VolatilityLevel.HIGH
        else:
            return VolatilityLevel.EXTREME_HIGH

    def analyze_volatility(self, highs: List[float], lows: List[float],
                         closes: List[float]) -> VolatilityState:
        """
        分析波动率状态

        参数:
            highs: 最高价列表
            lows: 最低价列表
            closes: 收盘价列表

        返回:
            VolatilityState
        """
        current_price = closes[-1]
        current_atr = self.calculate_atr(highs, lows, closes)

        # 更新ATR历史
        self.atr_history.append(current_atr)

        # 获取平均ATR
        average_atr = self.get_average_atr()
        if average_atr is None:
            average_atr = current_atr

        # 计算ATR百分比
        atr_pct = current_atr / current_price

        # 分类波动率
        volatility_level = self.classify_volatility(current_atr, current_price)

        # 获取调整因子
        adjustment_factor = self.position_adjustments.get(volatility_level.value, 1.0)

        # 计算相对于平均值的调整
        if average_atr > 0:
            relative_atr = current_atr / average_atr
            if relative_atr > 1.5:
                # 波动率是平均的1.5倍以上
                adjustment_factor = min(adjustment_factor, 0.6)
            elif relative_atr < 0.7:
                # 波动率是平均的0.7倍以下
                adjustment_factor = max(adjustment_factor, 1.1)

        # 应用平滑调整
        target_multiplier = adjustment_factor
        self.current_multiplier = (
            self.current_multiplier * (1 - self.smoothing_factor) +
            target_multiplier * self.smoothing_factor
        )

        # 限制在合理范围
        self.current_multiplier = max(
            self.min_multiplier,
            min(self.max_multiplier, self.current_multiplier)
        )

        return VolatilityState(
            level=volatility_level,
            current_atr=current_atr,
            atr_pct=atr_pct,
            average_atr=average_atr,
            adjustment_factor=self.current_multiplier,
            recommended_position_multiplier=self.current_multiplier
        )

    def get_adjusted_position_size(self, base_size: float, highs: List[float],
                                lows: List[float], closes: List[float]) -> float:
        """
        获取调整后的仓位大小

        参数:
            base_size: 基础仓位大小
            highs: 最高价列表
            lows: 最低价列表
            closes: 收盘价列表

        返回:
            调整后的仓位大小
        """
        state = self.analyze_volatility(highs, lows, closes)
        adjusted_size = base_size * state.recommended_position_multiplier

        logger.info(
            f"波动率调仓: {state.level.value} ATR={state.current_atr:.2f} "
            f"因子={state.recommended_position_multiplier:.2f} "
            f"基础仓位={base_size} 调整后={adjusted_size:.4f}"
        )

        return adjusted_size

    def get_adjusted_risk_per_trade(self, base_risk: float, highs: List[float],
                                   lows: List[float], closes: List[float]) -> float:
        """
        获取调整后的单笔风险

        参数:
            base_risk: 基础单笔风险（百分比）
            highs: 最高价列表
            lows: 最低价列表
            closes: 收盘价列表

        返回:
            调整后的单笔风险
        """
        state = self.analyze_volatility(highs, lows, closes)
        adjusted_risk = base_risk * state.recommended_position_multiplier

        # 限制在合理范围
        adjusted_risk = max(0.005, min(0.10, adjusted_risk))

        logger.info(
            f"风险调整: {state.level.value} "
            f"基础风险={base_risk:.2%} 调整后={adjusted_risk:.2%}"
        )

        return adjusted_risk

    def get_volatility_summary(self, highs: List[float], lows: List[float],
                            closes: List[float]) -> Dict:
        """
        获取波动率摘要

        参数:
            highs: 最高价列表
            lows: 最低价列表
            closes: 收盘价列表

        返回:
            摘要信息
        """
        state = self.analyze_volatility(highs, lows, closes)

        return {
            "volatility_level": state.level.value,
            "current_atr": state.current_atr,
            "atr_pct": f"{state.atr_pct:.2%}",
            "average_atr": state.average_atr,
            "relative_atr": state.current_atr / state.average_atr if state.average_atr > 0 else 1.0,
            "adjustment_factor": state.adjustment_factor,
            "recommended_multiplier": state.recommended_position_multiplier,
            "position_adjustment_pct": (state.recommended_position_multiplier - 1) * 100
        }

    def reset(self):
        """重置状态"""
        self.atr_history.clear()
        self.current_multiplier = 1.0


def create_volatility_adjustment(config: Dict = None) -> VolatilityAdjustment:
    """创建波动率调仓策略"""
    return VolatilityAdjustment(config)


if __name__ == "__main__":
    # 测试代码
    adjuster = VolatilityAdjustment()

    print("\n=== 测试波动率调仓 ===")

    # 生成测试数据
    import random
    import numpy as np

    random.seed(42)
    np.random.seed(42)

    def generate_klines(count, base_price, volatility=0.01):
        """生成测试K线数据"""
        highs = []
        lows = []
        closes = []

        price = base_price
        for _ in range(count):
            change = price * random.uniform(-volatility, volatility)
            high = price * (1 + random.uniform(0, volatility))
            low = price * (1 - random.uniform(0, volatility))
            close = price * (1 + random.uniform(-volatility/2, volatility/2))

            highs.append(high)
            lows.append(low)
            closes.append(close)
            price = close

        return highs, lows, closes

    # 测试1: 正常波动
    print("\n测试1: 正常波动市场")
    highs, lows, closes = generate_klines(50, 40000, 0.01)
    summary = adjuster.get_volatility_summary(highs, lows, closes)
    print(f"  波动率等级: {summary['volatility_level']}")
    print(f"  当前ATR: {summary['current_atr']:.2f}")
    print(f"  ATR占比: {summary['atr_pct']}")
    print(f"  相对ATR: {summary['relative_atr']:.2f}x")
    print(f"  调整因子: {summary['recommended_multiplier']:.2f}")
    print(f"  仓位调整: {summary['position_adjustment_pct']:.0f}%")

    # 测试仓位调整
    base_size = 0.1
    adjusted_size = adjuster.get_adjusted_position_size(base_size, highs, lows, closes)
    print(f"  基础仓位: {base_size}")
    print(f"  调整后仓位: {adjusted_size:.4f}")

    # 测试2: 高波动
    print("\n测试2: 高波动市场")
    adjuster.reset()
    highs, lows, closes = generate_klines(50, 40000, 0.03)
    summary = adjuster.get_volatility_summary(highs, lows, closes)
    print(f"  波动率等级: {summary['volatility_level']}")
    print(f"  当前ATR: {summary['current_atr']:.2f}")
    print(f"  ATR占比: {summary['atr_pct']}")
    print(f"  调整因子: {summary['recommended_multiplier']:.2f}")
    print(f"  仓位调整: {summary['position_adjustment_pct']:.0f}%")

    adjusted_size = adjuster.get_adjusted_position_size(base_size, highs, lows, closes)
    print(f"  基础仓位: {base_size}")
    print(f"  调整后仓位: {adjusted_size:.4f}")

    # 测试3: 低波动
    print("\n测试3: 低波动市场")
    adjuster.reset()
    highs, lows, closes = generate_klines(50, 40000, 0.003)
    summary = adjuster.get_volatility_summary(highs, lows, closes)
    print(f"  波动率等级: {summary['volatility_level']}")
    print(f"  当前ATR: {summary['current_atr']:.2f}")
    print(f"  ATR占比: {summary['atr_pct']}")
    print(f"  调整因子: {summary['recommended_multiplier']:.2f}")
    print(f"  仓位调整: {summary['position_adjustment_pct']:.0f}%")

    adjusted_size = adjuster.get_adjusted_position_size(base_size, highs, lows, closes)
    print(f"  基础仓位: {base_size}")
    print(f"  调整后仓位: {adjusted_size:.4f}")

    # 测试风险调整
    print("\n测试4: 风险调整")
    base_risk = 0.02
    adjusted_risk = adjuster.get_adjusted_risk_per_trade(base_risk, highs, lows, closes)
    print(f"  基础风险: {base_risk:.2%}")
    print(f"  调整后风险: {adjusted_risk:.2%}")
