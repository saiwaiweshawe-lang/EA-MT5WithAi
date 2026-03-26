import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class Signal:
    symbol: str
    direction: str
    strength: float
    confidence: float
    strategy: str
    timestamp: datetime
    metadata: Dict = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class MarketData:
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    metadata: Dict = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class BaseStrategy:
    def __init__(self, name: str, config: Dict = None):
        self.name = name
        self.config = config or {}
        self.weight = self.config.get("weight", 1.0)

    def analyze(self, market_data: MarketData) -> Optional[Signal]:
        raise NotImplementedError

    def get_required_data_count(self) -> int:
        return 20


class TrendStrategy(BaseStrategy):
    def __init__(self, config: Dict = None):
        super().__init__("Trend", config)
        self.ma_short = self.config.get("ma_short", 10)
        self.ma_long = self.config.get("ma_long", 50)
        self.rsi_period = self.config.get("rsi_period", 14)
        self.rsi_oversold = self.config.get("rsi_oversold", 30)
        self.rsi_overbought = self.config.get("rsi_overbought", 70)

    def analyze(self, market_data: MarketData) -> Optional[Signal]:
        history = market_data.metadata.get("history", [])
        if len(history) < max(self.ma_long, self.rsi_period) + 1:
            return None

        closes = [h.close for h in history[-(self.ma_long + 1):]]
        ma_short_val = np.mean(closes[-self.ma_short:])
        ma_long_val = np.mean(closes[-self.ma_long:])

        rsi = self._calculate_rsi([h.close for h in history[-self.rsi_period:]])

        prev_ma_short = np.mean(closes[-(self.ma_short + 1):-1])
        prev_ma_long = np.mean(closes[-(self.ma_long + 1):-1])

        ma_cross_up = prev_ma_short <= prev_ma_long and ma_short_val > ma_long_val
        ma_cross_down = prev_ma_short >= prev_ma_long and ma_short_val < ma_long_val

        strength = 0.0
        direction = "neutral"

        if ma_cross_up and rsi < self.rsi_overbought:
            direction = "buy"
            strength = min((ma_short_val - ma_long_val) / ma_long_val * 100, 5.0)
        elif ma_cross_down and rsi > self.rsi_oversold:
            direction = "sell"
            strength = min((ma_long_val - ma_short_val) / ma_long_val * 100, 5.0)
        elif ma_short_val > ma_long_val and rsi < 50:
            direction = "buy"
            strength = 2.0
        elif ma_short_val < ma_long_val and rsi > 50:
            direction = "sell"
            strength = 2.0

        if direction == "neutral":
            return None

        confidence = min(strength / 5.0, 1.0) * (0.7 if rsi < 70 and rsi > 30 else 0.5)

        return Signal(
            symbol=market_data.symbol,
            direction=direction,
            strength=strength,
            confidence=confidence,
            strategy=self.name,
            timestamp=market_data.timestamp,
            metadata={
                "ma_short": ma_short_val,
                "ma_long": ma_long_val,
                "rsi": rsi,
                "crossover": "up" if ma_cross_up else ("down" if ma_cross_down else "none")
            }
        )

    def _calculate_rsi(self, prices: List[float]) -> float:
        if len(prices) < 2:
            return 50.0

        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)

        avg_gain = np.mean(gains)
        avg_loss = np.mean(losses)

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def get_required_data_count(self) -> int:
        return max(self.ma_long, self.rsi_period) + 1


class ArbitrageStrategy(BaseStrategy):
    def __init__(self, config: Dict = None):
        super().__init__("Arbitrage", config)
        self.correlation_threshold = self.config.get("correlation_threshold", 0.7)

    def analyze(self, market_data: MarketData) -> Optional[Signal]:
        history = market_data.metadata.get("history", [])
        if len(history) < 20:
            return None

        recent_prices = [h.close for h in history[-20:]]
        volatility = np.std(recent_prices) / np.mean(recent_prices)

        if volatility > 0.02:
            strength = min(volatility * 100, 5.0)
            return Signal(
                symbol=market_data.symbol,
                direction="buy" if volatility > 0.01 else "sell",
                strength=strength,
                confidence=0.6,
                strategy=self.name,
                timestamp=market_data.timestamp,
                metadata={"volatility": volatility}
            )

        return None


class BreakoutStrategy(BaseStrategy):
    def __init__(self, config: Dict = None):
        super().__init__("Breakout", config)
        self.lookback = self.config.get("lookback", 20)
        self.volume_multiplier = self.config.get("volume_multiplier", 2.0)

    def analyze(self, market_data: MarketData) -> Optional[Signal]:
        history = market_data.metadata.get("history", [])
        if len(history) < self.lookback + 1:
            return None

        recent = history[-self.lookback:]
        highs = [h.high for h in recent]
        lows = [h.low for h in recent]
        volumes = [h.volume for h in recent]

        highest_high = max(highs[:-1])
        lowest_low = min(lows[:-1])
        avg_volume = np.mean(volumes[:-1])

        current = history[-1]
        current_volume = current.volume

        strength = 0.0
        direction = "neutral"

        if current.close > highest_high and current_volume > avg_volume * self.volume_multiplier:
            direction = "buy"
            strength = min((current.close - highest_high) / highest_high * 100, 5.0)
        elif current.close < lowest_low and current_volume > avg_volume * self.volume_multiplier:
            direction = "sell"
            strength = min((lowest_low - current.close) / lowest_low * 100, 5.0)

        if direction == "neutral":
            return None

        return Signal(
            symbol=market_data.symbol,
            direction=direction,
            strength=strength,
            confidence=min(strength / 5.0, 1.0) * 0.8,
            strategy=self.name,
            timestamp=current.timestamp,
            metadata={
                "highest_high": highest_high,
                "lowest_low": lowest_low,
                "volume_ratio": current_volume / avg_volume if avg_volume > 0 else 0
            }
        )
