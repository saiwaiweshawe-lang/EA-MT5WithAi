# Dynamic Take Profit Adjustment Module
# Dynamically adjust risk-reward ratio based on volatility and trend strength

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import logging
import numpy as np

logger = logging.getLogger(__name__)


class RRRAdjustmentMode(Enum):
    """Risk-Reward Ratio adjustment mode"""
    FIXED = "fixed"                   # Fixed ratio
    VOLATILITY_ADAPTIVE = "volatility_adaptive"     # Based on volatility
    TREND_STRENGTH_ADAPTIVE = "trend_strength_adaptive"  # Based on trend strength
    COMPOSITE = "composite"            # Combined approach


@dataclass
class MarketCondition:
    """Market condition for TP adjustment"""
    volatility_level: str        # low/normal/high
    trend_strength: float        # 0-1
    atr_pct: float               # ATR as percentage of price
    confidence: float            # Signal confidence 0-1


@dataclass
class TPAdjustmentResult:
    """Take profit adjustment result"""
    base_tp_price: float           # Base take profit price
    adjusted_tp_price: float       # Adjusted take profit price
    risk_reward_ratio: float       # Final R:R ratio
    tp_distance_pct: float         # TP distance as percentage
    adjustment_mode: str
    reason: str
    recommendations: List[str]


class DynamicTPManager:
    """Dynamic take profit adjustment manager"""

    def __init__(self, config: Dict = None):
        self.config = config or {}

        # Base R:R configuration
        self.base_rr_ratio = self.config.get("base_rr_ratio", 2.0)

        # Volatility-based R:R ranges
        self.low_volatility_rr = self.config.get("low_volatility_rr", 3.0)      # 3:1 in low volatility
        self.normal_volatility_rr = self.config.get("normal_volatility_rr", 2.0)  # 2:1 in normal
        self.high_volatility_rr = self.config.get("high_volatility_rr", 1.5)     # 1.5:1 in high

        # Volatility thresholds (based on ATR)
        self.volatility_low_threshold = self.config.get("volatility_low_threshold", 0.005)  # 0.5%
        self.volatility_normal_threshold = self.config.get("volatility_normal_threshold", 0.015)  # 1.5%
        self.volatility_high_threshold = self.config.get("volatility_high_threshold", 0.025)  # 2.5%

        # Trend strength thresholds
        self.weak_trend_threshold = self.config.get("weak_trend_threshold", 0.4)
        self.strong_trend_threshold = self.config.get("strong_trend_threshold", 0.8)

        # Trend-based R:R multipliers
        self.weak_trend_multiplier = self.config.get("weak_trend_multiplier", 0.8)
        self.strong_trend_multiplier = self.config.get("strong_trend_multiplier", 1.3)

        # Confidence adjustment
        self.confidence_weight = self.config.get("confidence_weight", 0.3)

        # TP range for multi-level exits
        self.enable_multi_tp = self.config.get("enable_multi_tp", True)
        self.tp_levels = self.config.get("tp_levels", [0.8, 1.0, 1.5])  # Multiple R:R options

        # Adjustment mode
        self.adjustment_mode = RRRAdjustmentMode(
            self.config.get("adjustment_mode", "volatility_adaptive")
        )

    def calculate_adjusted_tp(self, entry_price: float, stop_loss_price: float,
                           market_condition: MarketCondition,
                           confidence: float = 0.5) -> TPAdjustmentResult:
        """
        Calculate dynamically adjusted take profit

        Args:
            entry_price: Entry price
            stop_loss_price: Stop loss price
            market_condition: Current market condition
            confidence: Signal confidence (0-1)

        Returns:
            TPAdjustmentResult
        """
        # Calculate base risk distance
        risk_distance = abs(entry_price - stop_loss_price)
        risk_pct = risk_distance / entry_price

        # Determine R:R ratio based on mode
        if self.adjustment_mode == RRRAdjustmentMode.FIXED:
            rr_ratio = self.base_rr_ratio
        elif self.adjustment_mode == RRRAdjustmentMode.VOLATILITY_ADAPTIVE:
            rr_ratio = self._volatility_adjusted_rr(market_condition)
        elif self.adjustment_mode == RRRAdjustmentMode.TREND_STRENGTH_ADAPTIVE:
            rr_ratio = self._trend_adjusted_rr(market_condition)
        else:  # COMPOSITE
            rr_ratio = self._composite_adjusted_rr(market_condition, confidence)

        # Apply confidence weighting
        rr_ratio = rr_ratio * (1 + self.confidence_weight * (confidence - 0.5))

        # Calculate TP price
        base_tp_distance = risk_distance * self.base_rr_ratio
        base_tp_price = self._calculate_tp_price(entry_price, stop_loss_price, base_tp_distance)

        adjusted_tp_distance = risk_distance * rr_ratio
        adjusted_tp_price = self._calculate_tp_price(entry_price, stop_loss_price, adjusted_tp_distance)

        # Generate recommendations
        recommendations = self._generate_recommendations(
            market_condition, rr_ratio, risk_distance
        )

        return TPAdjustmentResult(
            base_tp_price=base_tp_price,
            adjusted_tp_price=adjusted_tp_price,
            risk_reward_ratio=rr_ratio,
            tp_distance_pct=(adjusted_tp_distance / entry_price),
            adjustment_mode=self.adjustment_mode.value,
            reason=self._generate_reason(market_condition, rr_ratio),
            recommendations=recommendations
        )

    def _calculate_tp_price(self, entry_price: float, stop_loss_price: float,
                           tp_distance: float) -> float:
        """Calculate TP price based on direction"""
        if entry_price > stop_loss_price:  # Long position
            return entry_price + tp_distance
        else:  # Short position
            return entry_price - tp_distance

    def _volatility_adjusted_rr(self, condition: MarketCondition) -> float:
        """Calculate volatility-adjusted R:R ratio"""
        volatility_level = condition.volatility_level

        if volatility_level == "low":
            return self.low_volatility_rr
        elif volatility_level == "normal":
            return self.normal_volatility_rr
        else:  # high
            return self.high_volatility_rr

    def _trend_adjusted_rr(self, condition: MarketCondition) -> float:
        """Calculate trend-strength-adjusted R:R ratio"""
        trend_strength = condition.trend_strength

        if trend_strength < self.weak_trend_threshold:
            return self.base_rr_ratio * self.weak_trend_multiplier
        elif trend_strength > self.strong_trend_threshold:
            return self.base_rr_ratio * self.strong_trend_multiplier
        else:
            return self.base_rr_ratio

    def _composite_adjusted_rr(self, condition: MarketCondition,
                                confidence: float) -> float:
        """Calculate composite-adjusted R:R ratio"""
        vol_rr = self._volatility_adjusted_rr(condition)
        trend_rr = self._trend_adjusted_rr(condition)

        # Weighted average (favor better conditions)
        if condition.volatility_level == "low" and condition.trend_strength > self.strong_trend_threshold:
            # Best conditions - maximize R:R
            rr_ratio = max(vol_rr, trend_rr) * 1.2
        elif condition.volatility_level == "high" and condition.trend_strength < self.weak_trend_threshold:
            # Worst conditions - minimize R:R
            rr_ratio = min(vol_rr, trend_rr) * 0.8
        else:
            # Mixed conditions - use average
            rr_ratio = (vol_rr + trend_rr) / 2

        # Confidence boost
        if confidence > 0.7:
            rr_ratio *= 1.1

        return rr_ratio

    def _generate_reason(self, condition: MarketCondition, rr_ratio: float) -> str:
        """Generate explanation for TP adjustment"""
        reasons = []

        if condition.volatility_level == "low":
            reasons.append(f"低波动({condition.atr_pct:.2%})，提升盈亏比至{rr_ratio:.1f}:1")
        elif condition.volatility_level == "high":
            reasons.append(f"高波动({condition.atr_pct:.2%})，降低盈亏比至{rr_ratio:.1f}:1以控制风险")

        if condition.trend_strength > self.strong_trend_threshold:
            reasons.append(f"强趋势(强度{condition.trend_strength:.2f})，延长盈亏比至{rr_ratio:.1f}:1")
        elif condition.trend_strength < self.weak_trend_threshold:
            reasons.append(f"弱趋势(强度{condition.trend_strength:.2f})，缩短盈亏比至{rr_ratio:.1f}:1")

        return "; ".join(reasons) if reasons else "正常市场条件"

    def _generate_recommendations(self, condition: MarketCondition, rr_ratio: float,
                              risk_distance: float) -> float:
        """Generate trading recommendations"""
        recommendations = []

        # TP level recommendations
        if self.enable_multi_tp:
            for i, tp_mult in enumerate(self.tp_levels, 1):
                tp_distance = risk_distance * rr_ratio * tp_mult
                recommendations.append(
                    f"TP{i}: {tp_mult:.1f}倍距离，目标价约{tp_distance:.0f}"
                )

        # Volatility-based recommendations
        if condition.volatility_level == "low":
            recommendations.append("低波动环境，考虑扩大盈利目标")
            recommendations.append("可用追踪止损锁定更多利润")
        elif condition.volatility_level == "high":
            recommendations.append("高波动环境，快速获利了结")
            recommendations.append("设置较紧的止损")

        # Trend-based recommendations
        if condition.trend_strength > 0.8:
            recommendations.append("强趋势延续，考虑分批止盈")
        elif condition.trend_strength < 0.4:
            recommendations.append("弱趋势，快速获利")

        return recommendations

    def analyze_market_condition(self, highs: List[float], lows: List[float],
                             closes: List[float]) -> MarketCondition:
        """
        Analyze current market condition for TP adjustment

        Args:
            highs: High prices
            lows: Low prices
            closes: Close prices

        Returns:
            MarketCondition
        """
        if len(closes) < 20:
            # Not enough data
            return MarketCondition(
                volatility_level="normal",
                trend_strength=0.5,
                atr_pct=0.015,
                confidence=0.5
            )

        # Calculate ATR for volatility
        atr = self._calculate_atr(highs, lows, closes, 14)
        current_price = closes[-1]
        atr_pct = atr / current_price

        # Determine volatility level
        if atr_pct < self.volatility_low_threshold:
            volatility_level = "low"
        elif atr_pct > self.volatility_high_threshold:
            volatility_level = "high"
        else:
            volatility_level = "normal"

        # Calculate trend strength (price change over period)
        if len(closes) >= 20:
            recent_change = (closes[-1] - closes[-20]) / closes[-20]
            # Normalize to 0-1 (assuming +/-10% is max)
            trend_strength = (recent_change / 0.10 + 1) / 2
            trend_strength = max(0, min(1, trend_strength))
        else:
            trend_strength = 0.5

        return MarketCondition(
            volatility_level=volatility_level,
            trend_strength=trend_strength,
            atr_pct=atr_pct,
            confidence=0.5
        )

    def _calculate_atr(self, highs: List[float], lows: List[float],
                       closes: List[float], period: int = 14) -> float:
        """Calculate Average True Range"""
        if len(closes) < period + 1:
            return 0.0

        tr_values = []
        for i in range(1, len(closes)):
            high = highs[i]
            low = lows[i]
            prev_close = closes[i - 1]

            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            tr_values.append(tr)

        return np.mean(tr_values[-period:])

    def get_multi_tp_levels(self, entry_price: float, stop_loss_price: float,
                         market_condition: MarketCondition) -> List[Dict]:
        """
        Get multiple TP level options

        Args:
            entry_price: Entry price
            stop_loss_price: Stop loss price
            market_condition: Market condition

        Returns:
            List of TP level dictionaries
        """
        risk_distance = abs(entry_price - stop_loss_price)

        tp_levels = []
        for i, tp_mult in enumerate(self.tp_levels, 1):
            tp_price = self._calculate_tp_price(entry_price, stop_loss_price, risk_distance * tp_mult)

            tp_levels.append({
                "level": i,
                "multiplier": tp_mult,
                "price": tp_price,
                "distance_pct": (risk_distance * tp_mult / entry_price) * 100
            })

        return tp_levels


def create_dynamic_tp_manager(config: Dict = None) -> DynamicTPManager:
    """Create dynamic TP manager"""
    return DynamicTPManager(config)


if __name__ == "__main__":
    # Test code
    manager = DynamicTPManager()

    print("\n=== Testing Dynamic Take Profit Adjustment ===")

    import random
    random.seed(42)

    # Test different market conditions
    test_conditions = [
        ("Low volatility", MarketCondition("low", 0.7, 0.004, 0.6)),
        ("Normal volatility", MarketCondition("normal", 0.5, 0.015, 0.5)),
        ("High volatility", MarketCondition("high", 0.3, 0.03, 0.5)),
        ("Strong trend", MarketCondition("normal", 0.9, 0.02, 0.8)),
        ("Weak trend", MarketCondition("normal", 0.3, 0.02, 0.5)),
    ]

    for name, condition in test_conditions:
        print(f"\n{name}:")
        print(f"  Volatility: {condition.volatility_level}, Trend: {condition.trend_strength:.2f}")

        # Calculate adjusted TP
        result = manager.calculate_adjusted_tp(40000, 39200, condition, confidence=0.7)
        print(f"  Base TP: {result.base_tp_price:.2f} (R:R {manager.base_rr_ratio:.1f}:1)")
        print(f"  Adjusted TP: {result.adjusted_tp_price:.2f}")
        print(f"  Final R:R: {result.risk_reward_ratio:.1f}:1")
        print(f"  TP distance: {result.tp_distance_pct:.2f}%")
        print(f"  Reason: {result.reason}")

        # Get multi TP levels
        tp_levels = manager.get_multi_tp_levels(40000, 39200, condition)
        print(f"  TP Levels: {len(tp_levels)} levels")
        for level in tp_levels:
            print(f"    TP{level['level']}: {level['multiplier']:.1f}x = {level['price']:.2f} ({level['distance_pct']:.2f}%)")
