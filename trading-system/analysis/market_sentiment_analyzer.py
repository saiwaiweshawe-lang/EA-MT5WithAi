# Market Sentiment Index Integration Module
# Integrate Fear & Greed Index, PCR (Put-Call Ratio) as entry confirmation or contrarian indicators

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class SentimentLevel(Enum):
    """Market sentiment level"""
    EXTREME_FEAR = "extreme_fear"       # 0-20: Panic, capitulation
    FEAR = "fear"                      # 20-40: Concern
    NEUTRAL = "neutral"                  # 40-60: Neither fear nor greed
    GREED = "greed"                    # 60-80: Optimism
    EXTREME_GREED = "extreme_greed"   # 80-100: Euphoria, bubble


@dataclass
class SentimentData:
    """Market sentiment data"""
    fng_index: float                # Fear & Greed Index (0-100)
    fng_level: SentimentLevel
    pcr_ratio: Optional[float]        # Put-Call Ratio
    pcr_level: Optional[str]           # bearish/bullish/neutral
    timestamp: datetime
    source: str


@dataclass
class SentimentSignal:
    """Sentiment-based trading signal"""
    signal: str                      # buy/sell/hold
    strength: float                # 0-1, signal strength
    direction: str                 # contrarian/follow
    confidence: float              # 0-1, signal confidence
    reason: str
    indicators: Dict[str, str]


class MarketSentimentAnalyzer:
    """Market sentiment analyzer"""

    def __init__(self, config: Dict = None):
        self.config = config or {}

        # Sentiment thresholds
        self.extreme_fear_threshold = self.config.get("extreme_fear_threshold", 20)
        self.extreme_greed_threshold = self.config.get("extreme_greed_threshold", 80)

        # PCR thresholds
        self.pcr_extreme_bearish = self.config.get("pcr_extreme_bearish", 1.2)  # > 1.2
        self.pcr_bearish = self.config.get("pcr_bearish", 1.0)
        self.pcr_bullish = self.config.get("pcr_bullish", 0.8)
        self.pcr_extreme_bullish = self.config.get("pcr_extreme_bullish", 0.6)

        # Signal thresholds
        self.min_sentiment_strength = self.config.get("min_sentiment_strength", 0.6)

        # Contrarian mode (follow or fade sentiment)
        self.contrarian_mode = self.config.get("contrarian_mode", True)

        # Sentiment weighting
        self.fng_weight = self.config.get("fng_weight", 0.7)
        self.pcr_weight = self.config.get("pcr_weight", 0.3)

        # History for trend analysis
        self.fng_history: List[Tuple[datetime, float]] = []
        self.max_history_length = self.config.get("max_history_length", 100)

    def update_sentiment(self, fng_index: float, pcr_ratio: Optional[float] = None,
                        source: str = "api", timestamp: Optional[datetime] = None):
        """
        Update market sentiment data

        Args:
            fng_index: Fear & Greed Index (0-100)
            pcr_ratio: Put-Call Ratio (optional)
            source: Data source
            timestamp: Data timestamp
        """
        fng_level = self._classify_fng_level(fng_index)

        # Determine PCR level if available
        pcr_level = None
        if pcr_ratio is not None:
            pcr_level = self._classify_pcr_level(pcr_ratio)

        sentiment = SentimentData(
            fng_index=fng_index,
            fng_level=fng_level,
            pcr_ratio=pcr_ratio,
            pcr_level=pcr_level,
            timestamp=timestamp or datetime.now(),
            source=source
        )

        # Update FNG history
        self.fng_history.append((sentiment.timestamp, fng_index))
        if len(self.fng_history) > self.max_history_length:
            self.fng_history.pop(0)

        logger.info(
            f"情绪更新: FNG={fng_index} ({fng_level.value}) "
            f"PCR={pcr_ratio if pcr_ratio else 'N/A'} "
            f"PCR水平={pcr_level if pcr_level else 'N/A'}"
        )

    def _classify_fng_level(self, fng_index: float) -> SentimentLevel:
        """Classify Fear & Greed Index level"""
        if fng_index < self.extreme_fear_threshold:
            return SentimentLevel.EXTREME_FEAR
        elif fng_index < 40:
            return SentimentLevel.FEAR
        elif fng_index < 60:
            return SentimentLevel.NEUTRAL
        elif fng_index < self.extreme_greed_threshold:
            return SentimentLevel.GREED
        else:
            return SentimentLevel.EXTREME_GREED

    def _classify_pcr_level(self, pcr_ratio: float) -> str:
        """Classify PCR level"""
        if pcr_ratio > self.pcr_extreme_bearish:
            return "extreme_bearish"
        elif pcr_ratio > self.pcr_bearish:
            return "bearish"
        elif pcr_ratio < self.pcr_extreme_bullish:
            return "extreme_bullish"
        elif pcr_ratio < self.pcr_bullish:
            return "bullish"
        else:
            return "neutral"

    def analyze_sentiment(self) -> SentimentSignal:
        """
        Analyze sentiment and generate trading signal

        Returns:
            SentimentSignal
        """
        if not self.fng_history:
            return SentimentSignal(
                signal="hold",
                strength=0.0,
                direction="neutral",
                confidence=0.0,
                reason="情绪数据不足",
                indicators={}
            )

        sentiment = SentimentData(
            fng_index=self.fng_history[-1][1],
            fng_level=self._classify_fng_level(self.fng_history[-1][1]),
            pcr_ratio=None,  # Would need separate PCR tracking
            pcr_level=None,
            timestamp=self.fng_history[-1][0],
            source="history"
        )

        return self._generate_signal(sentiment)

    def _generate_signal(self, sentiment: SentimentData) -> SentimentSignal:
        """Generate trading signal based on sentiment"""
        indicators = {}
        fng_score = 0.0
        pcr_score = 0.0

        # Process FNG
        if sentiment.fng_level == SentimentLevel.EXTREME_FEAR:
            # Extreme fear - strong contrarian buy signal (capitulation)
            fng_score = -1.0
            if self.contrarian_mode:
                indicators["fng"] = "极度恐慌，考虑反向做多机会（可能底部）"
                signal = "buy"
                direction = "contrarian"
            else:
                indicators["fng"] = "极度恐慌，观望或减少仓位"
                signal = "hold"
                direction = "neutral"
            strength = 0.9

        elif sentiment.fng_level == SentimentLevel.FEAR:
            # Fear - moderate contrarian signal
            fng_score = -0.5
            if self.contrarian_mode:
                indicators["fng"] = "恐慌，考虑反向买入"
                signal = "buy"
                direction = "contrarian"
            else:
                indicators["fng"] = "恐慌，谨慎交易"
                signal = "hold"
                direction = "neutral"
            strength = 0.7

        elif sentiment.fng_level == SentimentLevel.NEUTRAL:
            # Neutral - no clear signal
            fng_score = 0.0
            indicators["fng"] = "情绪中性，跟随其他信号"
            signal = "hold"
            direction = "neutral"
            strength = 0.3

        elif sentiment.fng_level == SentimentLevel.GREED:
            # Greed - possible top signal
            fng_score = 0.5
            if self.contrarian_mode:
                indicators["fng"] = "贪婪，考虑反向做空或快速止盈"
                signal = "sell"
                direction = "contrarian"
            else:
                indicators["fng"] = "贪婪，注意顶部风险"
                signal = "hold"
                direction = "neutral"
            strength = 0.7

        else:  # EXTREME_GREED
            # Extreme greed - strong contrarian sell signal
            fng_score = 1.0
            if self.contrarian_mode:
                indicators["fng"] = "极度贪婪，考虑反向做空（可能顶部）"
                signal = "sell"
                direction = "contrarian"
            else:
                indicators["fng"] = "极度贪婪，避免做多"
                signal = "hold"
                direction = "neutral"
            strength = 0.9

        # Process PCR (if available)
        # This would need separate PCR data tracking
        # For now, focus on FNG

        # Combine scores
        combined_score = fng_score * self.fng_weight + pcr_score * self.pcr_weight

        # Determine final signal
        if abs(combined_score) < 0.2:
            # Weak signal - hold
            signal = "hold"
            confidence = 0.3
        elif abs(combined_score) >= self.min_sentiment_strength:
            # Strong signal
            signal = indicators.get("signal", "hold")
            confidence = strength
        else:
            # Medium signal
            signal = "hold"
            confidence = 0.5

        return SentimentSignal(
            signal=signal,
            strength=strength,
            direction=direction,
            confidence=confidence,
            reason=indicators.get("fng", f"FNG={sentiment.fng_index} {sentiment.fng_level.value}"),
            indicators=indicators
        )

    def should_trade(self, signal_direction: str) -> Tuple[bool, str, float]:
        """
        Check if trading is allowed based on sentiment

        Args:
            signal_direction: Expected direction (buy/sell)

        Returns:
            (should_trade: bool, reason: str, confidence: float)
        """
        sentiment_signal = self.analyze_sentiment()

        # Check if sentiment supports the direction
        if signal_direction == "buy":
            if sentiment_signal.signal == "sell":
                return False, f"市场情绪做空({sentiment_signal.reason})，不适合做多", sentiment_signal.confidence * 0.5
            elif sentiment_signal.signal == "buy":
                return True, sentiment_signal.reason, sentiment_signal.confidence
            else:
                return True, "情绪中性，按其他信号交易", 0.4
        elif signal_direction == "sell":
            if sentiment_signal.signal == "buy":
                return False, f"市场情绪做多({sentiment_signal.reason})，不适合做空", sentiment_signal.confidence * 0.5
            elif sentiment_signal.signal == "sell":
                return True, sentiment_signal.reason, sentiment_signal.confidence
            else:
                return True, "情绪中性，按其他信号交易", 0.4

        return False, "未知信号方向", 0.0

    def get_sentiment_summary(self) -> Dict:
        """Get sentiment analysis summary"""
        if not self.fng_history:
            return {"status": "no_data"}

        current_fng = self.fng_history[-1][1]
        current_level = self._classify_fng_level(current_fng)

        # Calculate trend
        fng_values = [f[1] for f in self.fng_history]
        if len(fng_values) > 1:
            trend = "rising" if fng_values[-1] > fng_values[0] else "falling"
        else:
            trend = "neutral"

        return {
            "current_fng": current_fng,
            "current_level": current_level.value,
            "trend": trend,
            "history_length": len(self.fng_history),
            "avg_fng": sum(fng_values) / len(fng_values),
            "min_fng": min(fng_values) if fng_values else 50),
            "max_fng": max(fng_values) if fng_values else 50),
            "update_time": self.fng_history[-1][0].isoformat()
        }

    def get_sentiment_alert(self) -> Optional[str]:
        """Get alert if extreme sentiment detected"""
        if not self.fng_history:
            return None

        current_fng = self.fng_history[-1][1]
        current_level = self._classify_fng_level(current_fng)

        # Check for extreme levels
        if current_level == SentimentLevel.EXTREME_FEAR:
            return f"市场极度恐慌(FNG={current_fng})，可能存在抄底机会"
        elif current_level == SentimentLevel.EXTREME_GREED:
            return f"市场极度贪婪(FNG={current_fng})，注意顶部风险"

        return None


def create_market_sentiment_analyzer(config: Dict = None) -> MarketSentimentAnalyzer:
    """Create market sentiment analyzer"""
    return MarketSentimentAnalyzer(config)


if __name__ == "__main__":
    # Test code
    analyzer = MarketSentimentAnalyzer()

    print("\n=== Testing Market Sentiment Analysis ===")

    from datetime import datetime, timedelta

    # Simulate FNG history over time
    base_time = datetime.now() - timedelta(days=30)

    # Simulate different market conditions
    scenarios = [
        ("Bullish - rising FNG", range(25, 45, 5)),   # Fear to Neutral
        ("Bearish - falling FNG", range(75, 55, -5)), # Greed to Neutral
        ("Extreme fear - capitulation", range(15, 20, 2)),
        ("Extreme greed - bubble", range(90, 95, 2)),
    ]

    for name, fng_values in scenarios:
        print(f"\n{name}:")
        analyzer.fng_history = []

        for fng in fng_values:
            analyzer.update_sentiment(fng)
            # Simulate some time passing
            base_time += timedelta(hours=6)

        # Analyze current sentiment
        signal = analyzer.analyze_sentiment()
        print(f"  Current FNG: {signal.indicators.get('fng', 'N/A')}")
        print(f"  Signal: {signal.signal}")
        print(f"  Direction: {signal.direction}")
        print(f"  Strength: {signal.strength:.2f}")

        # Test trading decision
        for direction in ["buy", "sell"]:
            should_trade, reason, conf = analyzer.should_trade(direction)
            print(f"  {direction} trade: {should_trade} - {reason}")

    # Get summary
    print("\nSentiment Summary:")
    summary = analyzer.get_sentiment_summary()
    print(f"  Current FNG: {summary['current_fng']}")
    print(f"  Level: {summary['current_level']}")
    print(f"  Trend: {summary['trend']}")
    print(f"  Range: {summary['min_fng']}-{summary['max_fng']}")

    # Check alerts
    alert = analyzer.get_sentiment_alert()
    if alert:
        print(f"\nALERT: {alert}")
