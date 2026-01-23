# Funding Rate Impact Filter Module
# Filter or reduce positions when funding rate is unfavorable to avoid PnL erosion

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class FundingDirection(Enum):
    """Funding rate direction"""
    POSITIVE_LONG = "positive_long"      # Longs pay shorts (good for longs)
    NEUTRAL = "neutral"                # Near zero funding
    NEGATIVE_SHORT = "negative_short"    # Shorts pay longs (good for shorts)
    EXTREME_NEGATIVE = "extreme_negative"  # Strong negative - avoid longs
    EXTREME_POSITIVE = "extreme_positive"    # Strong positive - avoid shorts


@dataclass
class FundingData:
    """Funding rate data"""
    symbol: str
    rate: float                    # Funding rate (e.g., 0.0001 for 0.01%)
    direction: FundingDirection
    next_funding_time: datetime
    estimated_cost_pct: float        # 8-hour funding cost as percentage
    is_extreme: bool              # True if rate is extreme


@dataclass
class FundingFilterResult:
    """Funding filter result"""
    should_trade: bool
    recommended_side: Optional[str]     # "buy"/"sell"/None
    size_multiplier: float          # 0-1, adjustment to position size
    expected_funding_cost_pct: float
    reason: str
    funding_data: FundingData


class FundingRateFilter:
    """Funding rate impact filter"""

    def __init__(self, config: Dict = None):
        self.config = config or {}

        # Funding rate thresholds (8-hour rates)
        self.extreme_positive_threshold = self.config.get("extreme_positive_threshold", 0.0002)  # 0.02% / 8h
        self.extreme_negative_threshold = self.config.get("extreme_negative_threshold", -0.0002)  # -0.02% / 8h
        self.warning_threshold = self.config.get("warning_threshold", 0.0001)  # 0.01% / 8h

        # Position size adjustment based on funding
        self.unfavorable_multiplier = self.config.get("unfavorable_multiplier", 0.5)  # 50% size
        self.moderately_unfavorable = self.config.get("moderately_unfavorable", 0.75)  # 75% size

        # Enable/disable filtering
        self.enable_filtering = self.config.get("enable_filtering", True)
        self.allow_directional_filtering = self.config.get("allow_directional_filtering", True)

        # Funding history for trend analysis
        self.funding_history: Dict[str, List[FundingData]] = {}
        self.max_history_length = self.config.get("max_history_length", 50)

        # Funding rate source
        self.funding_source = self.config.get("funding_source", "exchange_api")  # exchange_api / manual / third_party

    def update_funding_rate(self, symbol: str, rate: float,
                          next_time: datetime = None):
        """
        Update funding rate for a symbol

        Args:
            symbol: Trading symbol (e.g., BTCUSDT)
            rate: Funding rate (e.g., 0.0001 for 0.01% per 8 hours)
            next_time: Next funding time (optional)
        """
        if next_time is None:
            next_time = datetime.now() + timedelta(hours=8)

        direction = self._classify_funding_direction(rate)
        estimated_cost_pct = abs(rate) * 3  # 3 funding periods per day

        is_extreme = (rate > self.extreme_positive_threshold or
                      rate < self.extreme_negative_threshold)

        funding = FundingData(
            symbol=symbol,
            rate=rate,
            direction=direction,
            next_funding_time=next_time,
            estimated_cost_pct=estimated_cost_pct,
            is_extreme=is_extreme
        )

        # Update history
        if symbol not in self.funding_history:
            self.funding_history[symbol] = []

        self.funding_history[symbol].append(funding)
        if len(self.funding_history[symbol]) > self.max_history_length:
            self.funding_history[symbol].pop(0)

        logger.info(
            f"更新资金费率: {symbol} 费率={rate:.6f} "
            f"方向={direction.value} 每日成本={estimated_cost_pct:.4%}"
        )

    def _classify_funding_direction(self, rate: float) -> FundingDirection:
        """Classify funding rate direction"""
        if rate > self.extreme_positive_threshold:
            return FundingDirection.EXTREME_POSITIVE
        elif rate > self.warning_threshold:
            return FundingDirection.POSITIVE_LONG
        elif rate < self.extreme_negative_threshold:
            return FundingDirection.EXTREME_NEGATIVE
        elif rate < -self.warning_threshold:
            return FundingDirection.NEGATIVE_SHORT
        else:
            return FundingDirection.NEUTRAL

    def should_trade(self, symbol: str, signal_direction: str) -> FundingFilterResult:
        """
        Determine if trading is allowed based on funding rate

        Args:
            symbol: Trading symbol
            signal_direction: Desired trade direction (buy/sell)

        Returns:
            FundingFilterResult
        """
        if symbol not in self.funding_history or not self.funding_history[symbol]:
            # No funding data, allow trading
            return FundingFilterResult(
                should_trade=True,
                recommended_side=None,
                size_multiplier=1.0,
                expected_funding_cost_pct=0.0,
                reason="无资金费率数据，允许交易"
            )

        funding = self.funding_history[symbol][-1]

        # Check if filtering is enabled
        if not self.enable_filtering:
            return FundingFilterResult(
                should_trade=True,
                recommended_side=None,
                size_multiplier=1.0,
                expected_funding_cost_pct=funding.estimated_cost_pct,
                reason=f"资金费率过滤已禁用，当前费率={funding.rate:.6f}"
            )

        # Check for extreme funding that prohibits trading
        if funding.is_extreme:
            if funding.direction == FundingDirection.EXTREME_POSITIVE and signal_direction == "sell":
                # Extreme positive funding - avoid shorts (longs pay too much)
                return FundingFilterResult(
                    should_trade=False,
                    recommended_side="buy",
                    size_multiplier=0.0,
                    expected_funding_cost_pct=funding.estimated_cost_pct,
                    reason=f"资金费率极高正值({funding.rate:.6f})，避免做空，建议做多"
                )
            elif funding.direction == FundingDirection.EXTREME_NEGATIVE and signal_direction == "buy":
                # Extreme negative funding - avoid longs (shorts pay too much)
                return FundingFilterResult(
                    should_trade=False,
                    recommended_side="sell",
                    size_multiplier=0.0,
                    expected_funding_cost_pct=funding.estimated_cost_pct,
                    reason=f"资金费率极高负值({funding.rate:.6f})，避免做多，建议做空"
                )

        # Directional filtering - recommend favorable side
        if self.allow_directional_filtering:
            if funding.direction == FundingDirection.POSITIVE_LONG:
                if signal_direction == "buy":
                    return FundingFilterResult(
                        should_trade=True,
                        recommended_side="buy",
                        size_multiplier=1.0,
                        expected_funding_cost_pct=funding.estimated_cost_pct,
                        reason=f"资金费率正值，做多方向有利（成本{funding.estimated_cost_pct:.4%}/天）"
                    )
                else:  # signal_direction == "sell"
                    # Shorts pay funding - reduce size
                    return FundingFilterResult(
                        should_trade=True,
                        recommended_side="sell",
                        size_multiplier=self.moderately_unfavorable,
                        expected_funding_cost_pct=funding.estimated_cost_pct,
                        reason=f"资金费率正值，做空方向不利，仓位缩减至{self.moderately_unfavorable:.0%}"
                    )
            elif funding.direction == FundingDirection.NEGATIVE_SHORT:
                if signal_direction == "sell":
                    return FundingFilterResult(
                        should_trade=True,
                        recommended_side="sell",
                        size_multiplier=1.0,
                        expected_funding_cost_pct=funding.estimated_cost_pct,
                        reason=f"资金费率负值，做空方向有利（成本{funding.estimated_cost_pct:.4%}/天）"
                    )
                else:  # signal_direction == "buy"
                    # Longs pay funding - reduce size
                    return FundingFilterResult(
                        should_trade=True,
                        recommended_side="buy",
                        size_multiplier=self.moderately_unfavorable,
                        expected_funding_cost_pct=funding.estimated_cost_pct,
                        reason=f"资金费率负值，做多方向不利，仓位缩减至{self.moderately_unfavorable:.0%}"
                    )

        # Neutral funding - allow both directions with some caution
        if funding.direction == FundingDirection.NEUTRAL:
            return FundingFilterResult(
                should_trade=True,
                recommended_side=None,
                size_multiplier=1.0,
                expected_funding_cost_pct=funding.estimated_cost_pct,
                reason="资金费率中性，交易无额外成本"
            )

        return FundingFilterResult(
            should_trade=True,
            recommended_side=None,
            size_multiplier=1.0,
            expected_funding_cost_pct=funding.estimated_cost_pct,
            reason=f"正常交易，资金费率={funding.rate:.6f}"
        )

    def get_funding_summary(self) -> Dict:
        """Get funding rate summary for all symbols"""
        summary = {
            "symbols": {},
            "total_symbols": len(self.funding_history),
            "update_time": datetime.now().isoformat()
        }

        for symbol, history in self.funding_history.items():
            if history:
                latest = history[-1]
                summary["symbols"][symbol] = {
                    "current_rate": latest.rate,
                    "direction": latest.direction.value,
                    "next_funding_time": latest.next_funding_time.isoformat() if latest.next_funding_time else None,
                    "estimated_daily_cost_pct": latest.estimated_cost_pct,
                    "is_extreme": latest.is_extreme,
                    "history_length": len(history)
                }

        return summary

    def get_funding_trend(self, symbol: str, window: int = 10) -> Dict:
        """
        Get funding rate trend analysis

        Args:
            symbol: Trading symbol
            window: Lookback window for trend

        Returns:
            Trend analysis
        """
        if symbol not in self.funding_history or len(self.funding_history[symbol]) < 2:
            return {"symbol": symbol, "trend": "insufficient_data"}

        history = self.funding_history[symbol][-window:]
        rates = [f.rate for f in history]

        return {
            "symbol": symbol,
            "current_rate": rates[-1],
            "average_rate": sum(rates) / len(rates),
            "trend": "increasing" if rates[-1] > rates[0] else ("decreasing" if rates[-1] < rates[0] else "stable"),
            "change_pct": ((rates[-1] - rates[0]) / rates[0] * 100) if rates[0] != 0 else 0,
            "volatility": max(rates) - min(rates) - min(rates[rates[1:]), 0) if len(rates) > 1 else 0
        }


def create_funding_rate_filter(config: Dict = None) -> FundingRateFilter:
    """Create funding rate filter"""
    return FundingRateFilter(config)


if __name__ == "__main__":
    # Test code
    filter = FundingRateFilter()

    print("\n=== Testing Funding Rate Impact Filter ===")

    # Test different funding rate scenarios
    from datetime import datetime, timedelta

    base_time = datetime.now()

    scenarios = [
        ("Positive funding - buy favorable", 0.0001, "buy"),
        ("Positive funding - sell unfavorable", 0.0001, "sell"),
        ("Negative funding - sell favorable", -0.0001, "sell"),
        ("Negative funding - buy unfavorable", -0.0001, "buy"),
        ("Extreme positive funding", 0.0003, "sell"),
        ("Extreme negative funding", -0.0003, "buy"),
        ("Neutral funding", 0.0000, "buy"),
    ]

    for name, rate, direction in scenarios:
        print(f"\n{name}:")
        next_time = base_time + timedelta(hours=8)

        filter.update_funding_rate("BTCUSDT", rate, next_time)

        # Test trading decision
        result = filter.should_trade("BTCUSDT", direction)

        print(f"  Rate: {rate:.6f} ({rate*100:.4f}%)")
        print(f"  Direction: {direction}")
        print(f"  Should trade: {result.should_trade}")
        print(f"  Recommended side: {result.recommended_side}")
        print(f"  Size multiplier: {result.size_multiplier:.2f}")
        print(f"  Daily cost: {result.expected_funding_cost_pct:.4f}%")
        print(f"  Reason: {result.reason}")

    # Get summary
    print("\nFunding Summary:")
    summary = filter.get_funding_summary()
    print(f"  Total symbols: {summary['total_symbols']}")
    for symbol, data in summary["symbols"].items():
        print(f"  {symbol}: Rate={data['current_rate']:.6f} Direction={data['direction']}")
