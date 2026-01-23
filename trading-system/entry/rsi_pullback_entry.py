# RSI回调确认入场点
# 上升趋势中等待RSI回调到40-50区间做多，下降趋势中等待RSI反弹到50-60区间做空

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import logging
import pandas as pd

logger = logging.getLogger(__name__)


class TrendDirection(Enum):
    """趋势方向"""
    UPTREND = "uptrend"
    DOWNTREND = "downtrend"
    NEUTRAL = "neutral"


@dataclass
class RSIEntrySignal:
    """RSI入场信号"""
    signal: str                    # buy/sell/hold
    confidence: float              # 置信度 0-1
    rsi_value: float               # RSI值
    current_price: float           # 当前价格
    entry_zone: Tuple[float, float]  # 入场区间
    reason: str                    # 原因
    risk_level: str               # low/medium/high


class RSIPullbackEntry:
    """RSI回调入场策略"""

    def __init__(self, config: Dict = None):
        self.config = config or {}

        # RSI周期
        self.rsi_period = self.config.get("rsi_period", 14)

        # 入场区间配置
        self.uptrend_entry_zone = self.config.get("uptrend_entry_zone", (40, 50))    # 上升趋势做多区间
        self.downtrend_entry_zone = self.config.get("downtrend_entry_zone", (50, 60))  # 下降趋势做空区间

        # RSI阈值
        self.rsi_overbought = self.config.get("rsi_overbought", 70)
        self.rsi_oversold = self.config.get("rsi_oversold", 30)
        self.rsi_extreme_overbought = self.config.get("rsi_extreme_overbought", 80)
        self.rsi_extreme_oversold = self.config.get("rsi_extreme_oversold", 20)

        # 确认条件
        self.require_candle_close = self.config.get("require_candle_close", True)
        self.confirmation_candles = self.config.get("confirmation_candles", 1)

    def calculate_rsi(self, prices: List[float]) -> float:
        """计算RSI值"""
        if len(prices) < self.rsi_period + 1:
            return 50.0

        gains = []
        losses = []

        for i in range(1, len(prices)):
            change = prices[i] - prices[i - 1]
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))

        avg_gain = sum(gains[-self.rsi_period:]) / self.rsi_period
        avg_loss = sum(losses[-self.rsi_period:]) / self.rsi_period

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return rsi

    def analyze(self, prices: List[float], trend_direction: TrendDirection,
                current_price: float) -> RSIEntrySignal:
        """
        分析RSI入场信号

        参数:
            prices: 价格列表（用于计算RSI）
            trend_direction: 趋势方向
            current_price: 当前价格

        返回:
            RSIEntrySignal
        """
        if len(prices) < self.rsi_period + 1:
            return RSIEntrySignal(
                signal="hold",
                confidence=0.0,
                rsi_value=50.0,
                current_price=current_price,
                entry_zone=(0, 0),
                reason="数据不足，无法计算RSI",
                risk_level="none"
            )

        rsi = self.calculate_rsi(prices)

        if trend_direction == TrendDirection.UPTREND:
            return self._analyze_uptrend(rsi, current_price)
        elif trend_direction == TrendDirection.DOWNTREND:
            return self._analyze_downtrend(rsi, current_price)
        else:
            return RSIEntrySignal(
                signal="hold",
                confidence=0.3,
                rsi_value=rsi,
                current_price=current_price,
                entry_zone=(0, 0),
                reason=f"趋势中性(RSI={rsi:.1f})，建议观望",
                risk_level="none"
            )

    def _analyze_uptrend(self, rsi: float, current_price: float) -> RSIEntrySignal:
        """分析上升趋势中的RSI信号"""
        lower, upper = self.uptrend_entry_zone

        # 极度超卖 - 强烈做多信号
        if rsi < self.rsi_extreme_oversold:
            return RSIEntrySignal(
                signal="buy",
                confidence=0.85,
                rsi_value=rsi,
                current_price=current_price,
                entry_zone=(current_price * 0.998, current_price * 1.002),
                reason=f"RSI极度超卖({rsi:.1f})，强烈做多机会",
                risk_level="low"
            )

        # RSI回调到做多区间 - 做多信号
        elif lower <= rsi <= upper:
            confidence = 0.75 + (upper - rsi) / (upper - lower) * 0.15
            return RSIEntrySignal(
                signal="buy",
                confidence=confidence,
                rsi_value=rsi,
                current_price=current_price,
                entry_zone=(current_price * 0.998, current_price * 1.002),
                reason=f"上升趋势中RSI回调到做多区间({rsi:.1f})，考虑入场",
                risk_level="low"
            )

        # RSI刚从做多区间向上 - 追多信号（谨慎）
        elif upper < rsi < upper + 5:
            return RSIEntrySignal(
                signal="buy",
                confidence=0.50,
                rsi_value=rsi,
                current_price=current_price,
                entry_zone=(current_price * 0.998, current_price * 1.002),
                reason=f"RSI刚离开做多区间({rsi:.1f})，可考虑追多但需谨慎",
                risk_level="medium"
            )

        # RSI超买 - 观望或准备做空
        elif rsi > self.rsi_overbought:
            if rsi > self.rsi_extreme_overbought:
                return RSIEntrySignal(
                    signal="hold",
                    confidence=0.70,
                    rsi_value=rsi,
                    current_price=current_price,
                    entry_zone=(0, 0),
                    reason=f"RSI极度超买({rsi:.1f})，等待回调",
                    risk_level="high"
                )
            else:
                return RSIEntrySignal(
                    signal="hold",
                    confidence=0.50,
                    rsi_value=rsi,
                    current_price=current_price,
                    entry_zone=(0, 0),
                    reason=f"RSI超买({rsi:.1f})，不建议做多，等待回调",
                    risk_level="medium"
                )

        # 其他情况 - 观望
        else:
            return RSIEntrySignal(
                signal="hold",
                confidence=0.30,
                rsi_value=rsi,
                current_price=current_price,
                entry_zone=(0, 0),
                reason=f"RSI={rsi:.1f}，等待回调到做多区间({lower}-{upper})",
                risk_level="none"
            )

    def _analyze_downtrend(self, rsi: float, current_price: float) -> RSIEntrySignal:
        """分析下降趋势中的RSI信号"""
        lower, upper = self.downtrend_entry_zone

        # 极度超买 - 强烈做空信号
        if rsi > self.rsi_extreme_overbought:
            return RSIEntrySignal(
                signal="sell",
                confidence=0.85,
                rsi_value=rsi,
                current_price=current_price,
                entry_zone=(current_price * 0.998, current_price * 1.002),
                reason=f"RSI极度超买({rsi:.1f})，强烈做空机会",
                risk_level="low"
            )

        # RSI反弹到做空区间 - 做空信号
        elif lower <= rsi <= upper:
            confidence = 0.75 + (rsi - lower) / (upper - lower) * 0.15
            return RSIEntrySignal(
                signal="sell",
                confidence=confidence,
                rsi_value=rsi,
                current_price=current_price,
                entry_zone=(current_price * 0.998, current_price * 1.002),
                reason=f"下降趋势中RSI反弹到做空区间({rsi:.1f})，考虑入场",
                risk_level="low"
            )

        # RSI刚从做空区间向下 - 追空信号（谨慎）
        elif lower - 5 < rsi < lower:
            return RSIEntrySignal(
                signal="sell",
                confidence=0.50,
                rsi_value=rsi,
                current_price=current_price,
                entry_zone=(current_price * 0.998, current_price * 1.002),
                reason=f"RSI刚离开做空区间({rsi:.1f})，可考虑追空但需谨慎",
                risk_level="medium"
            )

        # RSI超卖 - 观望或准备做多
        elif rsi < self.rsi_oversold:
            if rsi < self.rsi_extreme_oversold:
                return RSIEntrySignal(
                    signal="hold",
                    confidence=0.70,
                    rsi_value=rsi,
                    current_price=current_price,
                    entry_zone=(0, 0),
                    reason=f"RSI极度超卖({rsi:.1f})，等待反弹",
                    risk_level="high"
                )
            else:
                return RSIEntrySignal(
                    signal="hold",
                    confidence=0.50,
                    rsi_value=rsi,
                    current_price=current_price,
                    entry_zone=(0, 0),
                    reason=f"RSI超卖({rsi:.1f})，不建议做空，等待反弹",
                    risk_level="medium"
                )

        # 其他情况 - 观望
        else:
            return RSIEntrySignal(
                signal="hold",
                confidence=0.30,
                rsi_value=rsi,
                current_price=current_price,
                entry_zone=(0, 0),
                reason=f"RSI={rsi:.1f}，等待反弹到做空区间({lower}-{upper})",
                risk_level="none"
            )

    def should_trade(self, signal_direction: str, prices: List[float],
                    trend_direction: TrendDirection, current_price: float) -> Tuple[bool, str, float]:
        """
        判断是否应该交易

        参数:
            signal_direction: 信号方向 ("buy" 或 "sell")
            prices: 价格列表
            trend_direction: 趋势方向
            current_price: 当前价格

        返回:
            (should_trade: bool, reason: str, confidence: float)
        """
        rsi_signal = self.analyze(prices, trend_direction, current_price)

        # 检查信号方向是否匹配
        if signal_direction == "buy" and rsi_signal.signal == "buy":
            return True, rsi_signal.reason, rsi_signal.confidence
        elif signal_direction == "sell" and rsi_signal.signal == "sell":
            return True, rsi_signal.reason, rsi_signal.confidence
        elif signal_direction == "buy" and rsi_signal.signal == "hold":
            return False, rsi_signal.reason, rsi_signal.confidence
        elif signal_direction == "sell" and rsi_signal.signal == "hold":
            return False, rsi_signal.reason, rsi_signal.confidence
        else:
            # 信号方向冲突
            if signal_direction == "buy" and rsi_signal.signal == "sell":
                return False, f"RSI显示做空信号({rsi_signal.reason})，与做多方向冲突", 0.1
            elif signal_direction == "sell" and rsi_signal.signal == "buy":
                return False, f"RSI显示做多信号({rsi_signal.reason})，与做空方向冲突", 0.1
            else:
                return False, f"RSI不确认交易信号 (RSI={rsi_signal.rsi_value:.1f})", 0.2

    def get_entry_zone(self, rsi: float, trend_direction: TrendDirection,
                       current_price: float) -> Optional[Tuple[float, float]]:
        """
        获取RSI入场区间

        参数:
            rsi: RSI值
            trend_direction: 趋势方向
            current_price: 当前价格

        返回:
            (low, high) 或 None
        """
        if trend_direction == TrendDirection.UPTREND:
            lower, upper = self.uptrend_entry_zone
            if lower <= rsi <= upper:
                # 入场区间基于当前价格
                return (current_price * 0.998, current_price * 1.002)
        elif trend_direction == TrendDirection.DOWNTREND:
            lower, upper = self.downtrend_entry_zone
            if lower <= rsi <= upper:
                return (current_price * 0.998, current_price * 1.002)

        return None


def create_rsi_pullback_entry(config: Dict = None) -> RSIPullbackEntry:
    """创建RSI回调入场策略"""
    return RSIPullbackEntry(config)


if __name__ == "__main__":
    # 测试代码
    strategy = RSIPullbackEntry()

    print("\n=== 测试RSI回调入场策略 ===")

    # 生成测试价格数据
    import random
    random.seed(42)

    def generate_prices(count, base_price, trend=0.001):
        prices = [base_price]
        price = base_price
        for _ in range(count - 1):
            change = price * random.uniform(-0.02, 0.02)
            if trend > 0:
                change += price * trend
            elif trend < 0:
                change += price * trend
            price += change
            prices.append(price)
        return prices

    # 测试上升趋势
    print("\n测试1: 上升趋势")
    prices = generate_prices(50, 40000, trend=0.002)
    rsi_signal = strategy.analyze(prices, TrendDirection.UPTREND, 40000)
    print(f"  RSI: {rsi_signal.rsi_value:.1f}")
    print(f"  信号: {rsi_signal.signal}")
    print(f"  置信度: {rsi_signal.confidence:.2%}")
    print(f"  原因: {rsi_signal.reason}")
    print(f"  风险等级: {rsi_signal.risk_level}")

    # 测试下降趋势
    print("\n测试2: 下降趋势")
    prices = generate_prices(50, 40000, trend=-0.002)
    rsi_signal = strategy.analyze(prices, TrendDirection.DOWNTREND, 40000)
    print(f"  RSI: {rsi_signal.rsi_value:.1f}")
    print(f"  信号: {rsi_signal.signal}")
    print(f"  置信度: {rsi_signal.confidence:.2%}")
    print(f"  原因: {rsi_signal.reason}")
    print(f"  风险等级: {rsi_signal.risk_level}")

    # 测试交易决策
    print("\n测试3: 交易决策")
    prices = generate_prices(50, 40000, trend=0.002)
    should_trade, reason, confidence = strategy.should_trade(
        "buy", prices, TrendDirection.UPTREND, 40000
    )
    print(f"  应该做多: {should_trade}")
    print(f"  原因: {reason}")
    print(f"  置信度: {confidence:.2%}")
