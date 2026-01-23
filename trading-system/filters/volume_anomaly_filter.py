# Volume Anomaly Detection Filter
# Filter signals with abnormally low volume to reduce false breakouts

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import logging
import numpy as np

logger = logging.getLogger(__name__)


class VolumeLevel(Enum):
    """Volume level classification"""
    EXTREMELY_LOW = "extremely_low"
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    EXTREMELY_HIGH = "extremely_high"


@dataclass
class VolumeAnalysis:
    """Volume analysis result"""
    current_volume: float
    avg_volume: float
    volume_ratio: float              # current / avg
    volume_level: VolumeLevel
    is_anomaly: bool               # True if volume is abnormally low/high
    anomaly_score: float            # 0-1, deviation from normal
    recommendation: str


class VolumeAnomalyFilter:
    """Volume anomaly detection filter"""

    def __init__(self, config: Dict = None):
        self.config = config or {}

        # Volume analysis period
        self.volume_period = self.config.get("volume_period", 20)

        # Anomaly thresholds
        self.low_volume_threshold = self.config.get("low_volume_threshold", 0.5)    # Below 50% of avg
        self.high_volume_threshold = self.config.get("high_volume_threshold", 2.0)   # Above 200% of avg

        # Volume history
        self.volume_history: List[float] = []

        # Trend confirmation - check if volume supports the move
        self.volume_trend_confirmation = self.config.get("volume_trend_confirmation", True)

        # Minimum absolute volume
        self.min_volume_threshold = self.config.get("min_volume_threshold", 0)

    def analyze_volume(self, volume: float, prices: Optional[List[float]] = None) -> VolumeAnalysis:
        """
        Analyze volume and detect anomalies

        Args:
            volume: Current volume
            prices: Price history for trend analysis (optional)

        Returns:
            VolumeAnalysis
        """
        # Update volume history
        self.volume_history.append(volume)
        if len(self.volume_history) > self.volume_period:
            self.volume_history.pop(0)

        # Calculate average volume
        if len(self.volume_history) < 5:
            # Not enough data yet
            avg_volume = volume
        else:
            avg_volume = np.mean(self.volume_history)

        # Calculate volume ratio
        volume_ratio = volume / avg_volume if avg_volume > 0 else 1.0

        # Classify volume level
        volume_level = self._classify_volume_level(volume_ratio)

        # Detect anomalies
        is_anomaly = self._detect_anomaly(volume_ratio)

        # Calculate anomaly score (deviation from normal)
        anomaly_score = self._calculate_anomaly_score(volume_ratio)

        # Generate recommendation
        recommendation = self._generate_recommendation(
            is_anomaly, volume_level, volume_ratio
        )

        return VolumeAnalysis(
            current_volume=volume,
            avg_volume=avg_volume,
            volume_ratio=volume_ratio,
            volume_level=volume_level,
            is_anomaly=is_anomaly,
            anomaly_score=anomaly_score,
            recommendation=recommendation
        )

    def should_trade(self, volume: float, signal_direction: str,
                  prices: Optional[List[float]] = None) -> Tuple[bool, str, float]:
        """
        Determine if trading is allowed based on volume

        Args:
            volume: Current volume
            signal_direction: buy/sell signal direction
            prices: Price history for trend confirmation

        Returns:
            (should_trade: bool, reason: str, confidence: float)
        """
        analysis = self.analyze_volume(volume, prices)

        # Check minimum volume threshold
        if self.min_volume_threshold > 0 and volume < self.min_volume_threshold:
            return False, f"成交量{volume:.2f}低于最低阈值{self.min_volume_threshold}", 0.1

        # Reject if volume is extremely low
        if analysis.is_anomaly and analysis.volume_level == VolumeLevel.EXTREMELY_LOW:
            return False, analysis.recommendation, 0.2

        # Warn if volume is low
        if analysis.is_anomaly and analysis.volume_level == VolumeLevel.LOW:
            confidence = 0.5
            return True, f"{analysis.recommendation}（谨慎入场）", confidence

        # Prefer high volume signals
        confidence = 1.0
        if analysis.volume_level == VolumeLevel.HIGH:
            confidence = 0.9
        elif analysis.volume_level == VolumeLevel.EXTREMELY_HIGH:
            confidence = 1.0

        return True, "成交量正常，允许交易", confidence

    def _classify_volume_level(self, volume_ratio: float) -> VolumeLevel:
        """Classify volume level based on ratio to average"""
        if volume_ratio < 0.3:
            return VolumeLevel.EXTREMELY_LOW
        elif volume_ratio < 0.6:
            return VolumeLevel.LOW
        elif volume_ratio < 1.5:
            return VolumeLevel.NORMAL
        elif volume_ratio < 2.5:
            return VolumeLevel.HIGH
        else:
            return VolumeLevel.EXTREMELY_HIGH

    def _detect_anomaly(self, volume_ratio: float) -> bool:
        """Detect if volume is anomalous"""
        return (volume_ratio < self.low_volume_threshold or
                volume_ratio > self.high_volume_threshold)

    def _calculate_anomaly_score(self, volume_ratio: float) -> float:
        """
        Calculate anomaly score (0 = normal, 1 = extreme anomaly)

        Score represents how far the current volume deviates from normal
        """
        if 0.8 <= volume_ratio <= 1.2:
            return 0.0  # Normal
        elif volume_ratio < 0.8:
            # Low volume - score based on how low
            return min(1.0, (0.8 - volume_ratio) / 0.5)
        else:
            # High volume - score based on how high
            return min(1.0, (volume_ratio - 1.2) / 1.0)

    def _generate_recommendation(self, is_anomaly: bool, volume_level: VolumeLevel,
                             volume_ratio: float) -> str:
        """Generate trading recommendation"""
        if not is_anomaly:
            return "成交量正常，符合入场条件"

        if volume_level == VolumeLevel.EXTREMELY_LOW:
            return f"成交量极低(仅为均值的{volume_ratio:.0%})，拒绝假突破信号"
        elif volume_level == VolumeLevel.LOW:
            return f"成交量偏低(为均值的{volume_ratio:.0%})，建议谨慎或等待放量"
        elif volume_level == VolumeLevel.HIGH:
            return f"成交量较高(为均值的{volume_ratio:.0%})，信号可信度增加"
        else:
            return f"成交量极高(为均值的{volume_ratio:.0%})，需警惕异常波动"

    def get_volume_summary(self) -> Dict:
        """Get volume filter summary"""
        if not self.volume_history:
            return {"status": "no_data"}

        current_volume = self.volume_history[-1]
        avg_volume = np.mean(self.volume_history)
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0

        return {
            "current_volume": current_volume,
            "avg_volume": avg_volume,
            "volume_ratio": volume_ratio,
            "volume_level": self._classify_volume_level(volume_ratio).value,
            "history_length": len(self.volume_history),
            "filter_status": "active" if len(self.volume_history) >= 5 else "warming_up"
        }


def create_volume_anomaly_filter(config: Dict = None) -> VolumeAnomalyFilter:
    """Create volume anomaly filter"""
    return VolumeAnomalyFilter(config)


if __name__ == "__main__":
    # Test code
    filter = VolumeAnomalyFilter()

    print("\n=== Testing Volume Anomaly Detection ===")

    # Simulate volume data
    import random
    random.seed(42)

    base_volume = 1000
    volumes = []

    test_cases = [
        ("Normal volume", base_volume),
        ("Low volume", base_volume * 0.4),
        ("Extremely low volume", base_volume * 0.2),
        ("High volume", base_volume * 1.8),
        ("Extremely high volume", base_volume * 3.5),
    ]

    for name, vol in test_cases:
        print(f"\n{name}:")
        analysis = filter.analyze_volume(vol)

        print(f"  Current: {analysis.current_volume:.0f}")
        print(f"  Average: {analysis.avg_volume:.0f}")
        print(f"  Ratio: {analysis.volume_ratio:.0%}")
        print(f"  Level: {analysis.volume_level.value}")
        print(f"  Anomaly: {analysis.is_anomaly}")
        print(f"  Score: {analysis.anomaly_score:.2f}")
        print(f"  Rec: {analysis.recommendation}")

        should_trade, reason, conf = filter.should_trade(vol, "buy")
        status = "OK" if should_trade else "REJECT"
        print(f"  Decision: {status} - {reason} (conf: {conf:.2f})")
