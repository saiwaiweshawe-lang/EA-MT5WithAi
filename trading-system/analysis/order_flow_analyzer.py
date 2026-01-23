# Order Flow / Money Flow Analysis Module
# Track large orders, buying/selling pressure, and CVD (Cumulative Volume Delta)

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import logging
import numpy as np

logger = logging.getLogger(__name__)


class FlowDirection(Enum):
    """Order flow direction"""
    STRONG_BUYING = "strong_buying"
    BUYING = "buying"
    NEUTRAL = "neutral"
    SELLING = "selling"
    STRONG_SELLING = "strong_selling"


@dataclass
class OrderBookSnapshot:
    """Order book snapshot"""
    timestamp: datetime
    best_bid: float
    best_ask: float
    bid_size: float
    ask_size: float
    bid_volume: float = 0.0      # Total volume at bid levels
    ask_volume: float = 0.0      # Total volume at ask levels
    mid_price: float = 0.0


@dataclass
class OrderFlowSignal:
    """Order flow trading signal"""
    direction: FlowDirection
    strength: float              # 0-1, strength of the flow
    pressure: float              # Imbalance between buy and sell (-1 to 1)
    cvd: float                  # Cumulative Volume Delta
    delta_ema: float            # Smoothed delta
    signal: str                  # buy/sell/hold
    confidence: float            # 0-1
    reason: str
    large_order_detected: bool = False


class OrderFlowAnalyzer:
    """Order flow and money flow analyzer"""

    def __init__(self, config: Dict = None):
        self.config = config or {}

        # Analysis window
        self.lookback_period = self.config.get("lookback_period", 50)
        self.cvd_window = self.config.get("cvd_window", 20)
        self.ema_period = self.config.get("ema_period", 10)

        # Order book history
        self.order_book_history: List[OrderBookSnapshot] = []

        # CVD (Cumulative Volume Delta) history
        self.cvd_history: List[float] = []
        self.delta_history: List[float] = []

        # Large order detection
        self.large_order_threshold = self.config.get("large_order_threshold", 2.0)  # 2x avg
        self.large_order_window = self.config.get("large_order_window", 5)

        # Pressure thresholds
        self.pressure_threshold_buy = self.config.get("pressure_threshold_buy", 0.6)
        self.pressure_threshold_sell = self.config.get("pressure_threshold_sell", -0.6)

        # Signal thresholds
        self.min_signal_strength = self.config.get("min_signal_strength", 0.6)
        self.confirmation_bars = self.config.get("confirmation_bars", 2)

        # Running signal confirmation
        self.consecutive_buy_signals = 0
        self.consecutive_sell_signals = 0

    def update_order_book(self, best_bid: float, best_ask: float,
                      bid_size: float, ask_size: float,
                      bid_volume: float = 0.0, ask_volume: float = 0.0) -> OrderBookSnapshot:
        """
        Update order book and create snapshot

        Args:
            best_bid: Best bid price
            best_ask: Best ask price
            bid_size: Size at best bid
            ask_size: Size at best ask
            bid_volume: Total volume across bid levels
            ask_volume: Total volume across ask levels

        Returns:
            OrderBookSnapshot
        """
        snapshot = OrderBookSnapshot(
            timestamp=datetime.now(),
            best_bid=best_bid,
            best_ask=best_ask,
            bid_size=bid_size,
            ask_size=ask_size,
            bid_volume=bid_volume,
            ask_volume=ask_volume,
            mid_price=(best_bid + best_ask) / 2
        )

        self.order_book_history.append(snapshot)

        # Maintain history length
        max_history = self.lookback_period
        if len(self.order_book_history) > max_history:
            self.order_book_history.pop(0)

        return snapshot

    def analyze_flow(self) -> OrderFlowSignal:
        """
        Analyze current order flow and generate signal

        Returns:
            OrderFlowSignal
        """
        if len(self.order_book_history) < self.large_order_window:
            return self._create_default_signal("订单簿数据不足")

        # Calculate pressure and delta
        pressure, delta, cvd = self._calculate_pressure_metrics()

        # Calculate smoothed delta (EMA)
        delta_ema = self._calculate_delta_ema()

        # Detect large orders
        large_order_detected = self._detect_large_orders()

        # Determine flow direction
        direction = self._determine_flow_direction(pressure, cvd, delta_ema)

        # Calculate signal strength
        strength = self._calculate_strength(direction, pressure, cvd, delta_ema)

        # Generate trading signal
        signal, confidence, reason = self._generate_trading_signal(
            direction, strength, large_order_detected
        )

        return OrderFlowSignal(
            direction=direction,
            strength=strength,
            pressure=pressure,
            cvd=cvd,
            delta_ema=delta_ema,
            signal=signal,
            confidence=confidence,
            reason=reason,
            large_order_detected=large_order_detected
        )

    def _calculate_pressure_metrics(self) -> Tuple[float, float, float]:
        """Calculate buying/selling pressure metrics"""
        if len(self.order_book_history) < 2:
            return 0.0, 0.0, 0.0

        recent = self.order_book_history[-1]
        prev = self.order_book_history[-2]

        # Calculate delta (bid - ask size)
        delta = (recent.bid_size - recent.ask_size)

        # Calculate pressure (-1 = selling, 1 = buying, 0 = balanced)
        total_size = recent.bid_size + recent.ask_size
        if total_size > 0:
            pressure = (recent.bid_size - recent.ask_size) / total_size
        else:
            pressure = 0.0

        # Calculate CVD (Cumulative Volume Delta)
        self.delta_history.append(delta)
        if len(self.delta_history) > self.cvd_window:
            self.delta_history.pop(0)

        cvd = sum(self.delta_history)

        return pressure, delta, cvd

    def _calculate_delta_ema(self) -> float:
        """Calculate EMA of delta for smoothing"""
        if not self.delta_history:
            return 0.0

        delta_ema = self.delta_history[-1]
        alpha = 2 / (self.ema_period + 1)

        for d in self.delta_history:
            delta_ema = alpha * d + (1 - alpha) * delta_ema

        return delta_ema

    def _detect_large_orders(self) -> bool:
        """Detect large order flow spikes"""
        if len(self.delta_history) < self.large_order_window:
            return False

        recent_deltas = list(self.delta_history[-self.large_order_window:])
        avg_delta = abs(np.mean(recent_deltas))

        if avg_delta == 0:
            return False

        current_delta = abs(self.delta_history[-1])
        threshold = self.large_order_threshold * avg_delta

        return current_delta > threshold

    def _determine_flow_direction(self, pressure: float, cvd: float,
                               delta_ema: float) -> FlowDirection:
        """Determine overall flow direction"""
        # Combined score from multiple metrics
        pressure_score = pressure * 0.4
        cvd_score = np.tanh(cvd / 1000) * 0.4  # Normalize CVD
        delta_score = np.tanh(delta_ema / 100) * 0.2

        combined_score = pressure_score + cvd_score + delta_score

        # Classify direction
        if combined_score > 0.5:
            return FlowDirection.STRONG_BUYING
        elif combined_score > 0.2:
            return FlowDirection.BUYING
        elif combined_score < -0.5:
            return FlowDirection.STRONG_SELLING
        elif combined_score < -0.2:
            return FlowDirection.SELLING
        else:
            return FlowDirection.NEUTRAL

    def _calculate_strength(self, direction: FlowDirection, pressure: float,
                        cvd: float, delta_ema: float) -> float:
        """Calculate signal strength (0-1)"""
        if direction == FlowDirection.NEUTRAL:
            return 0.3

        # Strength based on pressure alignment
        pressure_strength = abs(pressure) * 0.5

        # CVD strength
        cvd_strength = min(1.0, abs(cvd) / 500) * 0.3

        # Delta strength
        delta_strength = min(1.0, abs(delta_ema) / 50) * 0.2

        total_strength = pressure_strength + cvd_strength + delta_strength

        return min(1.0, total_strength)

    def _generate_trading_signal(self, direction: FlowDirection, strength: float,
                              large_order_detected: bool) -> Tuple[str, float, str]:
        """Generate final trading signal"""
        # Need minimum strength
        if strength < self.min_signal_strength:
            return "hold", strength, "订单流强度不足，观望"

        # Large order overrides direction
        if large_order_detected:
            if direction == FlowDirection.STRONG_BUYING:
                return "buy", min(1.0, strength * 1.2), "检测到大额买单，强烈做多信号"
            elif direction == FlowDirection.STRONG_SELLING:
                return "sell", min(1.0, strength * 1.2), "检测到大额卖单，强烈做空信号"

        # Update confirmation counters
        if direction == FlowDirection.BUYING or direction == FlowDirection.STRONG_BUYING:
            self.consecutive_buy_signals += 1
            self.consecutive_sell_signals = 0
        elif direction == FlowDirection.SELLING or direction == FlowDirection.STRONG_SELLING:
            self.consecutive_sell_signals += 1
            self.consecutive_buy_signals = 0
        else:
            self.consecutive_buy_signals = 0
            self.consecutive_sell_signals = 0

        # Need confirmation
        min_confirmation = self.confirmation_bars
        if self.consecutive_buy_signals >= min_confirmation:
            return "buy", min(0.95, strength * 0.9), f"订单流确认买入信号（{self.consecutive_buy_signals}次连续）"
        elif self.consecutive_sell_signals >= min_confirmation:
            return "sell", min(0.95, strength * 0.9), f"订单流确认卖出信号（{self.consecutive_sell_signals}次连续）"
        else:
            return "hold", strength, f"订单流方向待确认（买入:{self.consecutive_buy_signals}，卖出:{self.consecutive_sell_signals}）"

    def _create_default_signal(self, reason: str) -> OrderFlowSignal:
        """Create default signal when data is insufficient"""
        return OrderFlowSignal(
            direction=FlowDirection.NEUTRAL,
            strength=0.0,
            pressure=0.0,
            cvd=0.0,
            delta_ema=0.0,
            signal="hold",
            confidence=0.0,
            reason=reason
        )

    def should_trade(self, signal_direction: str) -> Tuple[bool, str, float]:
        """
        Determine if trading is allowed based on order flow

        Args:
            signal_direction: Expected direction (buy/sell)

        Returns:
            (should_trade: bool, reason: str, confidence: float)
        """
        flow = self.analyze_flow()

        # Check if signal matches flow direction
        if signal_direction == "buy":
            if flow.direction in [FlowDirection.SELLING, FlowDirection.STRONG_SELLING]:
                return False, f"订单流显示卖压，不适合做多（强度:{flow.strength:.2f}）", 0.2
        elif flow.direction in [FlowDirection.BUYING, FlowDirection.STRONG_BUYING]:
            return True, flow.reason, flow.confidence
            else:
                return False, "订单流中性，观望", 0.3

        elif signal_direction == "sell":
            if flow.direction in [FlowDirection.BUYING, FlowDirection.STRONG_BUYING]:
                return False, f"订单流显示买压，不适合做空（强度:{flow.strength:.2f}）", 0.2
            elif flow.direction in [FlowDirection.SELLING, FlowDirection.STRONG_SELLING]:
                return True, flow.reason, flow.confidence
            else:
                return False, "订单流中性，观望", 0.3

        return False, "未知信号方向", 0.0

    def get_flow_summary(self) -> Dict:
        """Get order flow analysis summary"""
        if not self.order_book_history:
            return {"status": "no_data"}

        current = self.order_book_history[-1]
        pressure, delta, cvd = self._calculate_pressure_metrics()

        return {
            "timestamp": current.timestamp.isoformat(),
            "best_bid": current.best_bid,
            "best_ask": current.best_ask,
            "spread": current.best_ask - current.best_bid,
            "bid_size": current.bid_size,
            "ask_size": current.ask_size,
            "pressure": pressure,
            "delta": delta,
            "cvd": cvd,
            "pressure_direction": "buying" if pressure > 0 else ("selling" if pressure < 0 else "neutral"),
            "cvd_trend": "bullish" if cvd > 0 else ("bearish" if cvd < 0 else "neutral")
        }


def create_order_flow_analyzer(config: Dict = None) -> OrderFlowAnalyzer:
    """Create order flow analyzer"""
    return OrderFlowAnalyzer(config)


if __name__ == "__main__":
    # Test code
    analyzer = OrderFlowAnalyzer()

    print("\n=== Testing Order Flow Analysis ===")

    # Simulate order book updates
    import random
    random.seed(42)

    base_price = 40000
    spread = 10

    # Simulate 10 order book updates with buying pressure
    print("\nScenario 1: Accumulating buy pressure")
    for i in range(10):
        bid = base_price - spread // 2 + random.randint(-2, 2)
        ask = bid + spread + random.randint(0, 5)
        bid_size = 500 + i * 150  # Increasing bid pressure
        ask_size = 300 + random.randint(-50, 100)

        analyzer.update_order_book(bid, ask, bid_size, ask_size)

    flow = analyzer.analyze_flow()
    print(f"  Signal: {flow.signal}, Direction: {flow.direction.value}")
    print(f"  Strength: {flow.strength:.2f}, Pressure: {flow.pressure:.2f}")
    print(f"  CVD: {flow.cvd}, Reason: {flow.reason}")

    # Test trading decision
    should_trade, reason, conf = analyzer.should_trade("buy")
    print(f"  Trade decision: {should_trade} - {reason} (conf: {conf:.2f})")

    # Simulate 10 order book updates with selling pressure
    print("\nScenario 2: Accumulating sell pressure")
    for i in range(10):
        bid = base_price - spread // 2 + random.randint(0, 5)
        ask = bid + spread + random.randint(-2, 2)
        bid_size = 300 + random.randint(-50, 100)
        ask_size = 500 + i * 150  # Increasing ask pressure

        analyzer.update_order_book(bid, ask, bid_size, ask_size)

    flow = analyzer.analyze_flow()
    print(f"  Signal: {flow.signal}, Direction: {flow.direction.value}")
    print(f"  Strength: {flow.strength:.2f}, Pressure: {flow.pressure:.2f}")
    print(f"  CVD: {flow.cvd}, Reason: {flow.reason}")

    should_trade, reason, conf = analyzer.should_trade("sell")
    print(f"  Trade decision: {should_trade} - {reason} (conf: {conf:.2f})")
