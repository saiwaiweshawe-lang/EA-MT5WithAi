# MACD背离确认模块
# 价格创新低但MACD不创新低时，等待底背离完成做多反转
# 价格创新高但MACD不创新高时，等待顶背离完成做多反转

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import logging
import pandas as pd

logger = logging.getLogger(__name__)


class DivergenceType(Enum):
    """背离类型"""
    BULLISH_DIVERGENCE = "bullish_divergence"      # 底背离（看涨）
    BEARISH_DIVERGENCE = "bearish_divergence"      # 顶背离（看跌）
    NO_DIVERGENCE = "no_divergence"                # 无背离


@dataclass
class DivergenceEvent:
    """背离事件"""
    type: DivergenceType                  # 背离类型
    strength: float                      # 强度 0-1
    start_index: int                     # 起始索引
    end_index: int                       # 结束索引
    price_low: float                     # 价格低点（底背离）
    price_high: float                    # 价格高点（顶背离）
    macd_low: float                     # MACD低点（底背离）
    macd_high: float                    # MACD高点（顶背离）
    confirmed: bool = False             # 是否确认


@dataclass
class DivergenceSignal:
    """背离信号"""
    signal: str                         # buy/sell/hold
    divergence_type: Optional[DivergenceType]
    confidence: float                   # 置信度 0-1
    reason: str
    price: float
    expected_move: str                  # 预期走势
    risk_level: str


class MACDDivergenceDetector:
    """MACD背离检测器"""

    def __init__(self, config: Dict = None):
        self.config = config or {}

        # MACD参数
        self.fast_period = self.config.get("fast_period", 12)
        self.slow_period = self.config.get("slow_period", 26)
        self.signal_period = self.config.get("signal_period", 9)

        # 检测参数
        self.lookback_period = self.config.get("lookback_period", 50)   # 回看K线数
        self.pivot_window = self.config.get("pivot_window", 5)         # 极值窗口
        self.min_divergence_strength = self.config.get("min_divergence_strength", 0.3)

        # 确认条件
        self.require_price_action = self.config.get("require_price_action", True)
        self.confirmation_candles = self.config.get("confirmation_candles", 2)

    def calculate_macd(self, prices: List[float]) -> Dict[str, List[float]]:
        """计算MACD指标"""
        df = pd.DataFrame({'close': prices})

        # 计算EMA
        ema_fast = df['close'].ewm(span=self.fast_period, adjust=False).mean()
        ema_slow = df['close'].ewm(span=self.slow_period, adjust=False).mean()

        # MACD线
        macd_line = ema_fast - ema_slow

        # 信号线
        signal_line = macd_line.ewm(span=self.signal_period, adjust=False).mean()

        # 柱状图
        histogram = macd_line - signal_line

        return {
            'macd': macd_line.tolist(),
            'signal': signal_line.tolist(),
            'histogram': histogram.tolist()
        }

    def detect_divergence(self, prices: List[float], highs: List[float],
                         lows: List[float]) -> Optional[DivergenceSignal]:
        """
        检测MACD背离

        参数:
            prices: 收盘价列表
            highs: 最高价列表
            lows: 最低价列表

        返回:
            DivergenceSignal 或 None
        """
        if len(prices) < max(self.fast_period + self.slow_period, self.lookback_period):
            return DivergenceSignal(
                signal="hold",
                divergence_type=None,
                confidence=0.0,
                reason="数据不足，无法检测背离",
                price=prices[-1] if prices else 0,
                expected_move="",
                risk_level="none"
            )

        # 计算MACD
        macd_data = self.calculate_macd(prices)
        macd_values = macd_data['macd']
        histogram_values = macd_data['histogram']

        # 检测底背离（看涨）
        bullish_divergence = self._detect_bullish_divergence(prices, lows, macd_values, histogram_values)

        # 检测顶背离（看跌）
        bearish_divergence = self._detect_bearish_divergence(prices, highs, macd_values, histogram_values)

        # 选择更强的背离信号
        if bullish_divergence and bearish_divergence:
            if bullish_divergence.confidence > bearish_divergence.confidence:
                return bullish_divergence
            else:
                return bearish_divergence
        elif bullish_divergence:
            return bullish_divergence
        elif bearish_divergence:
            return bearish_divergence

        return DivergenceSignal(
            signal="hold",
            divergence_type=None,
            confidence=0.0,
            reason="未检测到背离信号",
            price=prices[-1],
            expected_move="",
            risk_level="none"
        )

    def _detect_bullish_divergence(self, prices: List[float], lows: List[float],
                                  macd_values: List[float],
                                  histogram_values: List[float]) -> Optional[DivergenceSignal]:
        """检测底背离（看涨）"""
        if len(lows) < self.lookback_period:
            return None

        # 找出最近的价格低点
        price_pivots = self._find_low_pivots(lows, self.pivot_window)
        if len(price_pivots) < 2:
            return None

        # 获取最近的两个价格低点
        recent_low = price_pivots[-1]
        previous_low = price_pivots[-2]

        # 价格创新低
        if lows[recent_low] >= lows[previous_low]:
            return None  # 价格没有创新低，没有底背离

        # 找出对应的MACD低点
        macd_pivots = self._find_low_pivots(macd_values, self.pivot_window)
        if len(macd_pivots) < 2:
            return None

        # 找到与价格低点对应的MACD低点
        macd_recent = self._find_matching_pivot(macd_pivots, recent_low)
        macd_previous = self._find_matching_pivot(macd_pivots, previous_low)

        if macd_recent is None or macd_previous is None:
            return None

        # MACD没有创新低（形成底背离）
        if macd_values[macd_recent] < macd_values[macd_previous]:
            return None  # MACD也创新低了，没有背离

        # 计算背离强度
        price_diff_pct = abs(lows[recent_low] - lows[previous_low]) / lows[previous_low]
        macd_diff = abs(macd_values[macd_previous] - macd_values[macd_recent])

        strength = min(1.0, (price_diff_pct * 10 + macd_diff * 0.5))

        if strength < self.min_divergence_strength:
            return None

        # 检查确认条件
        confirmed = self._check_divergence_confirmation(
            prices, lows, macd_values, recent_low, DivergenceType.BULLISH_DIVERGENCE
        )

        if not confirmed and self.require_price_action:
            return None

        # 生成信号
        return DivergenceSignal(
            signal="buy",
            divergence_type=DivergenceType.BULLISH_DIVERGENCE,
            confidence=0.65 + strength * 0.25,
            reason=f"检测到底背离：价格创新低({lows[recent_low]:.2f})但MACD未创新低({macd_values[macd_recent]:.2f})",
            price=prices[-1],
            expected_move="预期向上反弹",
            risk_level="medium"
        )

    def _detect_bearish_divergence(self, prices: List[float], highs: List[float],
                                  macd_values: List[float],
                                  histogram_values: List[float]) -> Optional[DivergenceSignal]:
        """检测顶背离（看跌）"""
        if len(highs) < self.lookback_period:
            return None

        # 找出最近的价格高点
        price_pivots = self._find_high_pivots(highs, self.pivot_window)
        if len(price_pivots) < 2:
            return None

        # 获取最近的两个价格高点
        recent_high = price_pivots[-1]
        previous_high = price_pivots[-2]

        # 价格创新高
        if highs[recent_high] <= highs[previous_high]:
            return None  # 价格没有创新高，没有顶背离

        # 找出对应的MACD高点
        macd_pivots = self._find_high_pivots(macd_values, self.pivot_window)
        if len(macd_pivots) < 2:
            return None

        # 找到与价格高点对应的MACD高点
        macd_recent = self._find_matching_pivot(macd_pivots, recent_high)
        macd_previous = self._find_matching_pivot(macd_pivots, previous_high)

        if macd_recent is None or macd_previous is None:
            return None

        # MACD没有创新高（形成顶背离）
        if macd_values[macd_recent] > macd_values[macd_previous]:
            return None  # MACD也创新高了，没有背离

        # 计算背离强度
        price_diff_pct = abs(highs[recent_high] - highs[previous_high]) / highs[previous_high]
        macd_diff = abs(macd_values[macd_previous] - macd_values[macd_recent])

        strength = min(1.0, (price_diff_pct * 10 + macd_diff * 0.5))

        if strength < self.min_divergence_strength:
            return None

        # 检查确认条件
        confirmed = self._check_divergence_confirmation(
            prices, highs, macd_values, recent_high, DivergenceType.BEARISH_DIVERGENCE
        )

        if not confirmed and self.require_price_action:
            return None

        # 生成信号
        return DivergenceSignal(
            signal="sell",
            divergence_type=DivergenceType.BEARISH_DIVERGENCE,
            confidence=0.65 + strength * 0.25,
            reason=f"检测到顶背离：价格创新高({highs[recent_high]:.2f})但MACD未创新高({macd_values[macd_recent]:.2f})",
            price=prices[-1],
            expected_move="预期向下回调",
            risk_level="medium"
        )

    def _find_low_pivots(self, values: List[float], window: int) -> List[int]:
        """找出低点索引"""
        pivots = []
        for i in range(window, len(values) - window):
            is_low = True
            for j in range(i - window, i + window + 1):
                if i != j and values[j] <= values[i]:
                    is_low = False
                    break
            if is_low:
                pivots.append(i)
        return pivots

    def _find_high_pivots(self, values: List[float], window: int) -> List[int]:
        """找出高点索引"""
        pivots = []
        for i in range(window, len(values) - window):
            is_high = True
            for j in range(i - window, i + window + 1):
                if i != j and values[j] >= values[i]:
                    is_high = False
                    break
            if is_high:
                pivots.append(i)
        return pivots

    def _find_matching_pivot(self, pivot_indices: List[int], price_index: int) -> Optional[int]:
        """找到与价格极值匹配的MACD极值"""
        if not pivot_indices:
            return None

        # 找到最接近但早于价格极值的MACD极值
        for pivot in reversed(pivot_indices):
            if pivot < price_index:
                return pivot

        # 如果没有找到，返回最近的
        return pivot_indices[-1]

    def _check_divergence_confirmation(self, prices: List[float], extremes: List[float],
                                     macd_values: List[float], extreme_index: int,
                                     divergence_type: DivergenceType) -> bool:
        """检查背离是否确认"""
        if len(prices) <= extreme_index + self.confirmation_candles:
            return False

        if divergence_type == DivergenceType.BULLISH_DIVERGENCE:
            # 底背离确认：价格需要开始上涨
            for i in range(extreme_index, min(extreme_index + self.confirmation_candles, len(prices))):
                if prices[i] > prices[i - 1]:
                    return True
        else:
            # 顶背离确认：价格需要开始下跌
            for i in range(extreme_index, min(extreme_index + self.confirmation_candles, len(prices))):
                if prices[i] < prices[i - 1]:
                    return True

        return False

    def should_trade_with_divergence(self, signal_direction: str, prices: List[float],
                                    highs: List[float], lows: List[float]) -> Tuple[bool, str, float]:
        """
        使用背离确认交易

        参数:
            signal_direction: 原始信号方向
            prices: 收盘价列表
            highs: 最高价列表
            lows: 最低价列表

        返回:
            (should_trade: bool, reason: str, confidence: float)
        """
        divergence = self.detect_divergence(prices, highs, lows)

        if divergence.signal == "hold":
            return False, divergence.reason, divergence.confidence

        # 检查背离方向是否与信号方向一致
        if signal_direction == "buy" and divergence.signal == "buy":
            return True, divergence.reason, divergence.confidence
        elif signal_direction == "sell" and divergence.signal == "sell":
            return True, divergence.reason, divergence.confidence
        elif signal_direction == "buy" and divergence.signal == "sell":
            return False, f"检测到顶背离({divergence.reason})，与做多方向冲突", 0.1
        elif signal_direction == "sell" and divergence.signal == "buy":
            return False, f"检测到底背离({divergence.reason})，与做空方向冲突", 0.1
        else:
            return False, divergence.reason, divergence.confidence


def create_macd_divergence_detector(config: Dict = None) -> MACDDivergenceDetector:
    """创建MACD背离检测器"""
    return MACDDivergenceDetector(config)


if __name__ == "__main__":
    # 测试代码
    detector = MACDDivergenceDetector()

    print("\n=== 测试MACD背离检测 ===")

    # 生成测试数据
    import random
    import numpy as np

    random.seed(42)
    np.random.seed(42)

    def generate_klines_with_divergence(divergence_type="bullish"):
        """生成包含背离的测试数据"""
        base_price = 40000
        prices = []
        highs = []
        lows = []

        if divergence_type == "bullish":
            # 生成底背离：价格创新低但MACD不创新低
            trend = -0.002  # 下降趋势
            for i in range(60):
                change = base_price * trend
                noise = base_price * random.uniform(-0.01, 0.01)
                # 让后期变化幅度减小，MACD不会创新低
                if i > 40:
                    change *= 0.5
                new_price = base_price + change + noise
                prices.append(new_price)
                highs.append(new_price * 1.01)
                lows.append(new_price * 0.99)
                base_price = new_price
        else:
            # 生成顶背离：价格创新高但MACD不创新高
            trend = 0.002  # 上升趋势
            for i in range(60):
                change = base_price * trend
                noise = base_price * random.uniform(-0.01, 0.01)
                # 让后期变化幅度减小，MACD不会创新高
                if i > 40:
                    change *= 0.5
                new_price = base_price + change + noise
                prices.append(new_price)
                highs.append(new_price * 1.01)
                lows.append(new_price * 0.99)
                base_price = new_price

        return prices, highs, lows

    # 测试底背离
    print("\n测试1: 底背离（看涨）")
    prices, highs, lows = generate_klines_with_divergence("bullish")
    signal = detector.detect_divergence(prices, highs, lows)
    print(f"  信号: {signal.signal}")
    print(f"  置信度: {signal.confidence:.2%}")
    print(f"  原因: {signal.reason}")
    print(f"  预期走势: {signal.expected_move}")
    print(f"  风险等级: {signal.risk_level}")

    # 测试顶背离
    print("\n测试2: 顶背离（看跌）")
    prices, highs, lows = generate_klines_with_divergence("bearish")
    signal = detector.detect_divergence(prices, highs, lows)
    print(f"  信号: {signal.signal}")
    print(f"  置信度: {signal.confidence:.2%}")
    print(f"  原因: {signal.reason}")
    print(f"  预期走势: {signal.expected_move}")
    print(f"  风险等级: {signal.risk_level}")

    # 测试交易决策
    print("\n测试3: 交易决策")
    should_trade, reason, confidence = detector.should_trade_with_divergence(
        "buy", prices, highs, lows
    )
    print(f"  应该做多: {should_trade}")
    print(f"  原因: {reason}")
    print(f"  置信度: {confidence:.2%}")
