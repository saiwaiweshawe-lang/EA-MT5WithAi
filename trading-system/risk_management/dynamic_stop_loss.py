# 动态止损位计算模块
# 使用ATR的1.5-2倍作为止损距离
# 高波动时扩大止损，低波动时收紧止损

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import logging
import pandas as pd

logger = logging.getLogger(__name__)


class VolatilityLevel(Enum):
    """波动率等级"""
    EXTREME_LOW = "extreme_low"      # 极低
    LOW = "low"                       # 低
    NORMAL = "normal"                 # 正常
    HIGH = "high"                     # 高
    EXTREME_HIGH = "extreme_high"    # 极高


@dataclass
class StopLossLevel:
    """止损位"""
    price: float                      # 止损价格
    distance_pct: float               # 距离百分比
    atr_based: bool                  # 是否基于ATR
    volatility_level: VolatilityLevel
    reason: str


class DynamicStopLossCalculator:
    """动态止损计算器"""

    def __init__(self, config: Dict = None):
        self.config = config or {}

        # ATR参数
        self.atr_period = self.config.get("atr_period", 14)
        self.atr_multiplier_normal = self.config.get("atr_multiplier_normal", 2.0)
        self.atr_multiplier_high = self.config.get("atr_multiplier_high", 2.5)
        self.atr_multiplier_low = self.config.get("atr_multiplier_low", 1.5)

        # 基础止损百分比
        self.base_stop_loss_pct = self.config.get("base_stop_loss_pct", 0.02)

        # 波动率阈值
        self.volatility_thresholds = self.config.get("volatility_thresholds", {
            "extreme_low": 0.002,     # 0.2%
            "low": 0.005,            # 0.5%
            "normal": 0.015,          # 1.5%
            "high": 0.025             # 2.5%
        })

        # 止损调整因子
        self.volatility_adjustments = self.config.get("volatility_adjustments", {
            "extreme_low": 0.6,       # 低波动时缩小止损
            "low": 0.8,
            "normal": 1.0,
            "high": 1.3,              # 高波动时扩大止损
            "extreme_high": 1.6
        })

        # 支撑阻力位确认
        self.use_support_resistance = self.config.get("use_support_resistance", True)
        self.support_resistance_buffer_pct = self.config.get("support_resistance_buffer_pct", 0.002)

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
            # 如果数据不足，使用简单波动率估计
            if len(closes) >= 2:
                return sum(abs(closes[i] - closes[i-1]) for i in range(1, len(closes))) / (len(closes) - 1)
            return 0

        df = pd.DataFrame({
            'high': highs,
            'low': lows,
            'close': closes
        })

        # 计算真实波幅TR
        prev_close = df['close'].shift(1)
        tr1 = df['high'] - df['low']
        tr2 = abs(df['high'] - prev_close)
        tr3 = abs(df['low'] - prev_close)
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        # 计算ATR
        atr = tr.rolling(window=self.atr_period).mean()

        return atr.iloc[-1]

    def calculate_volatility_level(self, atr: float, current_price: float) -> VolatilityLevel:
        """
        计算波动率等级

        参数:
            atr: ATR值
            current_price: 当前价格

        返回:
            VolatilityLevel
        """
        atr_pct = atr / current_price

        if atr_pct < self.volatility_thresholds["extreme_low"]:
            return VolatilityLevel.EXTREME_LOW
        elif atr_pct < self.volatility_thresholds["low"]:
            return VolatilityLevel.LOW
        elif atr_pct < self.volatility_thresholds["normal"]:
            return VolatilityLevel.NORMAL
        elif atr_pct < self.volatility_thresholds["high"]:
            return VolatilityLevel.HIGH
        else:
            return VolatilityLevel.EXTREME_HIGH

    def calculate_stop_loss(self, entry_price: float, side: str,
                           highs: List[float], lows: List[float],
                           closes: List[float],
                           support_level: Optional[float] = None,
                           resistance_level: Optional[float] = None) -> StopLossLevel:
        """
        计算动态止损位

        参数:
            entry_price: 入场价格
            side: 方向 ("buy" 或 "sell")
            highs: 最高价列表
            lows: 最低价列表
            closes: 收盘价列表
            support_level: 支撑位（用于做多止损）
            resistance_level: 阻力位（用于做空止损）

        返回:
            StopLossLevel
        """
        current_price = closes[-1]
        atr = self.calculate_atr(highs, lows, closes)
        volatility_level = self.calculate_volatility_level(atr, current_price)

        # 获取波动率调整因子
        adjustment_factor = self.volatility_adjustments.get(volatility_level.value, 1.0)

        # 基于ATR计算止损
        if side.lower() in ["buy", "long"]:
            # 做多止损
            atr_multiplier = self.atr_multiplier_normal * adjustment_factor
            atr_stop_price = entry_price - atr * atr_multiplier

            # 考虑支撑位
            if self.use_support_resistance and support_level:
                support_stop_price = support_level * (1 - self.support_resistance_buffer_pct)
                # 选择更合理的止损位（较高的那个）
                sl_price = max(atr_stop_price, support_stop_price)
                if sl_price == support_stop_price:
                    reason = f"基于支撑位({support_level:.2f})的动态止损，ATR={atr:.2f}"
                else:
                    reason = f"基于ATR({atr:.2f} x {atr_multiplier:.2f})的动态止损，波动率={volatility_level.value}"
            else:
                sl_price = atr_stop_price
                reason = f"基于ATR({atr:.2f} x {atr_multiplier:.2f})的动态止损，波动率={volatility_level.value}"

        else:
            # 做空止损
            atr_multiplier = self.atr_multiplier_normal * adjustment_factor
            atr_stop_price = entry_price + atr * atr_multiplier

            # 考虑阻力位
            if self.use_support_resistance and resistance_level:
                resistance_stop_price = resistance_level * (1 + self.support_resistance_buffer_pct)
                # 选择更合理的止损位（较低的那个）
                sl_price = min(atr_stop_price, resistance_stop_price)
                if sl_price == resistance_stop_price:
                    reason = f"基于阻力位({resistance_level:.2f})的动态止损，ATR={atr:.2f}"
                else:
                    reason = f"基于ATR({atr:.2f} x {atr_multiplier:.2f})的动态止损，波动率={volatility_level.value}"
            else:
                sl_price = atr_stop_price
                reason = f"基于ATR({atr:.2f} x {atr_multiplier:.2f})的动态止损，波动率={volatility_level.value}"

        # 计算距离百分比
        if side.lower() in ["buy", "long"]:
            distance_pct = (entry_price - sl_price) / entry_price
        else:
            distance_pct = (sl_price - entry_price) / entry_price

        return StopLossLevel(
            price=sl_price,
            distance_pct=distance_pct,
            atr_based=True,
            volatility_level=volatility_level,
            reason=reason
        )

    def calculate_trailing_stop(self, entry_price: float, current_price: float,
                                side: str, highest_profit_pct: float,
                                highs: List[float], lows: List[float],
                                closes: List[float]) -> Optional[float]:
        """
        计算移动止损位

        参数:
            entry_price: 入场价格
            current_price: 当前价格
            side: 方向
            highest_profit_pct: 最高盈利百分比
            highs: 最高价列表
            lows: 最低价列表
            closes: 收盘价列表

        返回:
            移动止损价格 或 None
        """
        # 如果没有盈利，返回固定止损
        if highest_profit_pct <= 0:
            return None

        # 计算ATR
        atr = self.calculate_atr(highs, lows, closes)
        volatility_level = self.calculate_volatility_level(atr, current_price)

        # 移动止损激活阈值
        activation_threshold = self.config.get("trailing_activation_threshold_pct", 0.02)

        # 移动止损距离
        trailing_distance_pct = self.config.get("trailing_distance_pct", 0.01)

        # 根据波动率调整
        trailing_distance_pct *= self.volatility_adjustments.get(volatility_level.value, 1.0)

        if side.lower() in ["buy", "long"]:
            # 做多移动止损
            if highest_profit_pct < activation_threshold:
                return None
            trailing_stop = current_price * (1 - trailing_distance_pct)
            # 确保移动止损不低于入场价
            trailing_stop = max(trailing_stop, entry_price * (1 - self.base_stop_loss_pct))
            return trailing_stop
        else:
            # 做空移动止损
            if highest_profit_pct < activation_threshold:
                return None
            trailing_stop = current_price * (1 + trailing_distance_pct)
            # 确保移动止损不高于入场价
            trailing_stop = min(trailing_stop, entry_price * (1 + self.base_stop_loss_pct))
            return trailing_stop

    def adjust_stop_loss(self, current_stop: float, new_volatility: VolatilityLevel,
                       entry_price: float, side: str) -> Tuple[float, str]:
        """
        根据波动率变化调整止损

        参数:
            current_stop: 当前止损价格
            new_volatility: 新的波动率等级
            entry_price: 入场价格
            side: 方向

        返回:
            (new_stop: float, reason: str)
        """
        # 只向有利方向调整止损
        adjustment_factor = self.volatility_adjustments.get(new_volatility.value, 1.0)

        if side.lower() in ["buy", "long"]:
            # 做多：止损只能向上移动（远离当前价格）
            new_stop = max(current_stop, entry_price * (1 - self.base_stop_loss_pct * adjustment_factor))

            if new_stop > current_stop:
                return new_stop, f"波动率变化为{new_volatility.value}，止损向上调整"
            else:
                return current_stop, "止损保持不变"
        else:
            # 做空：止损只能向下移动（远离当前价格）
            new_stop = min(current_stop, entry_price * (1 + self.base_stop_loss_pct * adjustment_factor))

            if new_stop < current_stop:
                return new_stop, f"波动率变化为{new_volatility.value}，止损向下调整"
            else:
                return current_stop, "止损保持不变"


def create_dynamic_stop_loss_calculator(config: Dict = None) -> DynamicStopLossCalculator:
    """创建动态止损计算器"""
    return DynamicStopLossCalculator(config)


if __name__ == "__main__":
    # 测试代码
    calculator = DynamicStopLossCalculator()

    print("\n=== 测试动态止损计算 ===")

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
            high = price * (1 + random.uniform(0, volatility))
            low = price * (1 - random.uniform(0, volatility))
            close = price * (1 + random.uniform(-volatility/2, volatility/2))
            highs.append(high)
            lows.append(low)
            closes.append(close)
            price = close

        return highs, lows, closes

    # 测试1: 正常波动
    print("\n测试1: 正常波动市场的止损")
    highs, lows, closes = generate_klines(50, 40000, 0.01)
    sl = calculator.calculate_stop_loss(40000, "buy", highs, lows, closes)
    print(f"  入场价格: 40000")
    print(f"  止损价格: {sl.price:.2f}")
    print(f"  止损距离: {sl.distance_pct:.2%}")
    print(f"  波动率等级: {sl.volatility_level.value}")
    print(f"  原因: {sl.reason}")

    # 测试2: 高波动
    print("\n测试2: 高波动市场的止损")
    highs, lows, closes = generate_klines(50, 40000, 0.03)
    sl = calculator.calculate_stop_loss(40000, "buy", highs, lows, closes)
    print(f"  入场价格: 40000")
    print(f"  止损价格: {sl.price:.2f}")
    print(f"  止损距离: {sl.distance_pct:.2%}")
    print(f"  波动率等级: {sl.volatility_level.value}")
    print(f"  原因: {sl.reason}")

    # 测试3: 低波动
    print("\n测试3: 低波动市场的止损")
    highs, lows, closes = generate_klines(50, 40000, 0.003)
    sl = calculator.calculate_stop_loss(40000, "buy", highs, lows, closes)
    print(f"  入场价格: 40000")
    print(f"  止损价格: {sl.price:.2f}")
    print(f"  止损距离: {sl.distance_pct:.2%}")
    print(f"  波动率等级: {sl.volatility_level.value}")
    print(f"  原因: {sl.reason}")

    # 测试4: 做空止损
    print("\n测试4: 做空止损")
    highs, lows, closes = generate_klines(50, 40000, 0.015)
    sl = calculator.calculate_stop_loss(40000, "sell", highs, lows, closes)
    print(f"  入场价格: 40000")
    print(f"  止损价格: {sl.price:.2f}")
    print(f"  止损距离: {sl.distance_pct:.2%}")
    print(f"  波动率等级: {sl.volatility_level.value}")
    print(f"  原因: {sl.reason}")

    # 测试5: 移动止损
    print("\n测试5: 移动止损")
    highs, lows, closes = generate_klines(50, 40000, 0.01)
    trailing_stop = calculator.calculate_trailing_stop(
        40000, 40500, "buy", 0.025, highs, lows, closes
    )
    print(f"  入场价格: 40000")
    print(f"  当前价格: 40500")
    print(f"  最高盈利: 2.5%")
    print(f"  移动止损: {trailing_stop:.2f}" if trailing_stop else "移动止损未激活")
