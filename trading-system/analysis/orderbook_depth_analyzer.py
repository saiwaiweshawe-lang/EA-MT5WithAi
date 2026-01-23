# Order Book Depth Analysis Module
# Analyze bid-ask spread, depth imbalance, support/resistance strength

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import logging
import numpy as np

logger = logging.getLogger(__name__)


class DepthImbalance(Enum):
    """Order book depth imbalance direction"""
    BID_DOMINANCE = "bid_dominance"      # Strong buying pressure
    ASK_DOMINANCE = "ask_dominance"      # Strong selling pressure
    BALANCED = "balanced"                # Balanced order book
    LIQUIDITY_POOR = "liquidity_poor"    # Low liquidity on both sides


@dataclass
class OrderBookLevel:
    """Single order book level"""
    price: float
    bid_size: float = 0.0
    ask_size: float = 0.0
    bid_volume: float = 0.0
    ask_volume: float = 0.0


@dataclass
class DepthAnalysis:
    """Order book depth analysis result"""
    best_bid: float
    best_ask: float
    spread: float                     # Absolute spread
    spread_pct: float                # Spread as percentage
    imbalance: DepthImbalance
    imbalance_score: float           # -1 (strong ask) to 1 (strong bid)
    bid_depth_score: float          # Bid liquidity score
    ask_depth_score: float          # Ask liquidity score
    total_depth_score: float         # Overall liquidity score (0-1)
    support_strength: float          # Support strength at best bid
    resistance_strength: float       # Resistance strength at best ask
    liquidity_regime: str
    signal: str                    # buy/sell/hold
    confidence: float               # 0-1
    reason: str
    entry_zone: Tuple[float, float] = (0.0, 0.0)


class OrderBookDepthAnalyzer:
    """Order book depth analyzer"""

    def __init__(self, config: Dict = None):
        self.config = config or {}

        # Depth levels to analyze
        self.depth_levels = self.config.get("depth_levels", 10)

        # Spread thresholds
        self.max_spread_pct = self.config.get("max_spread_pct", 0.001)  # 0.1%
        self.warning_spread_pct = self.config.get("warning_spread_pct", 0.0005)  # 0.05%

        # Imbalance thresholds
        self.imbalance_threshold_strong = self.config.get("imbalance_threshold_strong", 0.6)
        self.imbalance_threshold_moderate = self.config.get("imbalance_threshold_moderate", 0.4)

        # Liquidity thresholds
        self.min_total_depth = self.config.get("min_total_depth", 1000)
        self.liquidity_window = self.config.get("liquidity_window", 5)

        # Order book history
        self.order_book: List[OrderBookLevel] = []

        # Depth history for trend analysis
        self.bid_depth_history: List[float] = []
        self.ask_depth_history: List[float] = []

    def update_order_book(self, levels: List[OrderBookLevel]):
        """
        Update order book with new levels

        Args:
            levels: List of order book levels from best price outward
        """
        # Store levels (sorted by price)
        self.order_book = sorted(levels, key=lambda x: x.price)

        # Calculate best bid/ask
        best_bid, best_ask = self._find_best_prices()

        # Update depth history
        if best_bid > 0:
            self.bid_depth_history.append(self._calculate_bid_depth(best_bid))
        if best_ask > 0:
            self.ask_depth_history.append(self._calculate_ask_depth(best_ask))

        # Maintain history length
        max_history = self.liquidity_window
        if len(self.bid_depth_history) > max_history:
            self.bid_depth_history.pop(0)
        if len(self.ask_depth_history) > max_history:
            self.ask_depth_history.pop(0)

    def analyze_depth(self, current_price: Optional[float] = None) -> DepthAnalysis:
        """
        Analyze current order book depth

        Args:
            current_price: Current market price (optional)

        Returns:
            DepthAnalysis
        """
        if not self.order_book:
            return self._create_default_analysis("订单簿数据为空")

        # Find best prices
        best_bid, best_ask = self._find_best_prices()

        # Calculate spread
        spread = best_ask - best_bid
        spread_pct = spread / best_bid if best_bid > 0 else 0

        # Calculate depth scores
        bid_depth_score = self._calculate_bid_depth(best_bid)
        ask_depth_score = self._calculate_ask_depth(best_ask)
        total_depth_score = self._calculate_total_depth_score(bid_depth_score, ask_depth_score)

        # Determine imbalance
        imbalance, imbalance_score = self._determine_imbalance(bid_depth_score, ask_depth_score)

        # Determine liquidity regime
        liquidity_regime = self._classify_liquidity_regime(total_depth_score)

        # Calculate support/resistance strength
        support_strength = self._calculate_support_strength(best_bid, bid_depth_score)
        resistance_strength = self._calculate_resistance_strength(best_ask, ask_depth_score)

        # Generate trading signal
        signal, confidence, reason = self._generate_trading_signal(
            imbalance, total_depth_score, spread_pct,
            support_strength, resistance_strength
        )

        # Calculate entry zone (price range around current price)
        if current_price:
            entry_zone = self._calculate_entry_zone(
                current_price, best_bid, best_ask, imbalance
            )
        else:
            entry_zone = (best_bid, best_ask)

        return DepthAnalysis(
            best_bid=best_bid,
            best_ask=best_ask,
            spread=spread,
            spread_pct=spread_pct,
            imbalance=imbalance,
            imbalance_score=imbalance_score,
            bid_depth_score=bid_depth_score,
            ask_depth_score=ask_depth_score,
            total_depth_score=total_depth_score,
            support_strength=support_strength,
            resistance_strength=resistance_strength,
            liquidity_regime=liquidity_regime,
            signal=signal,
            confidence=confidence,
            reason=reason,
            entry_zone=entry_zone
        )

    def _find_best_prices(self) -> Tuple[float, float]:
        """Find best bid and ask prices"""
        best_bid = 0.0
        best_ask = float('inf')

        for level in self.order_book:
            if level.bid_size > 0 and level.price > best_bid:
                best_bid = level.price
            if level.ask_size > 0 and level.price < best_ask:
                best_ask = level.price

        return best_bid, best_ask

    def _calculate_bid_depth(self, best_bid: float) -> float:
        """Calculate bid side depth score"""
        bid_volume = 0.0
        for level in self.order_book:
            if level.price <= best_bid:
                bid_volume += level.bid_volume

        # Normalize score (0-1)
        return min(1.0, bid_volume / self.min_total_depth)

    def _calculate_ask_depth(self, best_ask: float) -> float:
        """Calculate ask side depth score"""
        ask_volume = 0.0
        for level in self.order_book:
            if level.price >= best_ask:
                ask_volume += level.ask_volume

        # Normalize score (0-1)
        return min(1.0, ask_volume / self.min_total_depth)

    def _calculate_total_depth_score(self, bid_score: float, ask_score: float) -> float:
        """Calculate overall liquidity score"""
        return (bid_score + ask_score) / 2

    def _determine_imbalance(self, bid_score: float,
                           ask_score: float) -> Tuple[DepthImbalance, float]:
        """Determine order book imbalance"""
        total = bid_score + ask_score
        if total == 0:
            return DepthImbalance.BALANCED, 0.0

        # Imbalance score: -1 (ask dominance) to 1 (bid dominance)
        imbalance_score = (bid_score - ask_score) / total

        # Classify
        if imbalance_score > self.imbalance_threshold_strong:
            return DepthImbalance.BID_DOMINANCE, imbalance_score
        elif imbalance_score > self.imbalance_threshold_moderate:
            return DepthImbalance.BID_DOMINANCE, imbalance_score
        elif imbalance_score < -self.imbalance_threshold_strong:
            return DepthImbalance.ASK_DOMINANCE, imbalance_score
        elif imbalance_score < -self.imbalance_threshold_moderate:
            return DepthImbalance.ASK_DOMINANCE, imbalance_score
        else:
            return DepthImbalance.BALANCED, imbalance_score

    def _classify_liquidity_regime(self, total_score: float) -> str:
        """Classify liquidity regime"""
        if total_score < 0.2:
            return "extremely_low"
        elif total_score < 0.4:
            return "low"
        elif total_score < 0.7:
            return "normal"
        elif total_score < 0.9:
            return "high"
        else:
            return "extremely_high"

    def _calculate_support_strength(self, best_bid: float, bid_score: float) -> float:
        """Calculate support strength at best bid"""
        # Support strength based on bid depth and concentration
        return bid_score * 0.7 + (1.0 if best_bid > 0 else 0.0) * 0.3

    def _calculate_resistance_strength(self, best_ask: float, ask_score: float) -> float:
        """Calculate resistance strength at best ask"""
        # Resistance strength based on ask depth and concentration
        return ask_score * 0.7 + (1.0 if best_ask < float('inf') else 0.0) * 0.3

    def _generate_trading_signal(self, imbalance: DepthImbalance, depth_score: float,
                              spread_pct: float, support_strength: float,
                              resistance_strength: float) -> Tuple[str, float, str]:
        """Generate trading signal based on order book analysis"""
        # Check if spread is too wide
        if spread_pct > self.max_spread_pct:
            return "hold", 0.1, f"价差过大({spread_pct:.2%})，流动性不足"

        # Check liquidity
        if depth_score < 0.3:
            return "hold", 0.2, "订单簿深度不足，观望"

        # Generate signal based on imbalance
        if imbalance == DepthImbalance.BID_DOMINANCE:
            confidence = min(0.9, depth_score + 0.2)
            return "buy", confidence, f"买单主导（强度{depth_score:.2f}），在最佳买价附近入场"
        elif imbalance == DepthImbalance.ASK_DOMINANCE:
            confidence = min(0.9, depth_score + 0.2)
            return "sell", confidence, f"卖单主导（强度{depth_score:.2f}），在最佳卖价附近入场"
        else:
            return "hold", 0.3, "订单簿平衡，等待方向确认"

    def _calculate_entry_zone(self, current_price: float, best_bid: float,
                           best_ask: float, imbalance: DepthImbalance) -> Tuple[float, float]:
        """Calculate optimal entry price range"""
        if imbalance == DepthImbalance.BID_DOMINANCE:
            # Strong buying pressure - enter near bid
            lower = best_bid * 0.9995
            upper = best_bid * 1.0005
        elif imbalance == DepthImbalance.ASK_DOMINANCE:
            # Strong selling pressure - enter near ask
            lower = best_ask * 0.9995
            upper = best_ask * 1.0005
        else:
            # Balanced - enter near current/mid price
            mid = (best_bid + best_ask) / 2
            lower = mid * 0.9995
            upper = mid * 1.0005

        return (lower, upper)

    def _create_default_analysis(self, reason: str) -> DepthAnalysis:
        """Create default analysis when data is insufficient"""
        return DepthAnalysis(
            best_bid=0.0,
            best_ask=0.0,
            spread=0.0,
            spread_pct=0.0,
            imbalance=DepthImbalance.LIQUIDITY_POOR,
            imbalance_score=0.0,
            bid_depth_score=0.0,
            ask_depth_score=0.0,
            total_depth_score=0.0,
            support_strength=0.0,
            resistance_strength=0.0,
            liquidity_regime="none",
            signal="hold",
            confidence=0.0,
            reason=reason
        )

    def should_trade(self, signal_direction: str) -> Tuple[bool, str, float]:
        """
        Determine if trading is allowed based on order book depth

        Args:
            signal_direction: Expected direction (buy/sell)

        Returns:
            (should_trade: bool, reason: str, confidence: float)
        """
        analysis = self.analyze_depth()

        # Check if signal direction matches imbalance
        if signal_direction == "buy":
            if analysis.imbalance in [DepthImbalance.ASK_DOMINANCE]:
                return False, f"卖单主导，不适合做多（强度:{analysis.ask_depth_score:.2f}）", 0.2
            elif analysis.imbalance in [DepthImbalance.BID_DOMINANCE]:
                return True, analysis.reason, analysis.confidence
            else:
                return False, "订单簿平衡，观望", 0.3

        elif signal_direction == "sell":
            if analysis.imbalance in [DepthImbalance.BID_DOMINANCE]:
                return False, f"买单主导，不适合做空（强度:{analysis.bid_depth_score:.2f}）", 0.2
            elif analysis.imbalance in [DepthImbalance.ASK_DOMINANCE]:
                return True, analysis.reason, analysis.confidence
            else:
                return False, "订单簿平衡，观望", 0.3

        return False, "未知信号方向", 0.0

    def get_depth_summary(self) -> Dict:
        """Get order book depth summary"""
        if not self.order_book:
            return {"status": "no_data"}

        best_bid, best_ask = self._find_best_prices()
        spread = best_ask - best_bid

        return {
            "best_bid": best_bid,
            "best_ask": best_ask,
            "spread": spread,
            "spread_pct": (spread / best_bid * 100) if best_bid > 0 else 0,
            "bid_depth": self._calculate_bid_depth(best_bid),
            "ask_depth": self._calculate_ask_depth(best_ask),
            "imbalance_score": (self._calculate_bid_depth(best_bid) - self._calculate_ask_depth(best_ask)) / 2,
            "liquidity_regime": self._classify_liquidity_regime(
                (self._calculate_bid_depth(best_bid) + self._calculate_ask_depth(best_ask)) / 2
            )
        }


def create_orderbook_depth_analyzer(config: Dict = None) -> OrderBookDepthAnalyzer:
    """Create order book depth analyzer"""
    return OrderBookDepthAnalyzer(config)


if __name__ == "__main__":
    # Test code
    analyzer = OrderBookDepthAnalyzer()

    print("\n=== Testing Order Book Depth Analysis ===")

    import random
    random.seed(42)

    base_price = 40000

    # Test 1: Bid dominance (strong buying pressure)
    print("\nScenario 1: Strong bid dominance")
    levels = []
    for i in range(10):
        price = base_price + i * 2
        bid_size = 500 + (10 - i) * 80  # Higher bid size at lower prices
        ask_size = 200 + i * 30
        levels.append(OrderBookLevel(
            price=price,
            bid_size=bid_size,
            ask_size=ask_size,
            bid_volume=bid_size * random.randint(5, 10),
            ask_volume=ask_size * random.randint(2, 6)
        ))
    analyzer.update_order_book(levels)

    analysis = analyzer.analyze_depth(base_price)
    print(f"  Signal: {analysis.signal}, Imbalance: {analysis.imbalance.value}")
    print(f"  Spread: {analysis.spread_pct:.3f}%, Depth: {analysis.total_depth_score:.2f}")
    print(f"  Confidence: {analysis.confidence:.2f}, Reason: {analysis.reason}")

    should_trade, reason, conf = analyzer.should_trade("buy")
    print(f"  Trade decision: {should_trade} - {reason} (conf: {conf:.2f})")

    # Test 2: Ask dominance (strong selling pressure)
    print("\nScenario 2: Strong ask dominance")
    levels = []
    for i in range(10):
        price = base_price + i * 2
        bid_size = 200 + i * 30
        ask_size = 500 + (10 - i) * 80  # Higher ask size at lower prices
        levels.append(OrderBookLevel(
            price=price,
            bid_size=bid_size,
            ask_size=ask_size,
            bid_volume=bid_size * random.randint(2, 6),
            ask_volume=ask_size * random.randint(5, 10)
        ))
    analyzer.update_order_book(levels)

    analysis = analyzer.analyze_depth(base_price)
    print(f"  Signal: {analysis.signal}, Imbalance: {analysis.imbalance.value}")
    print(f"  Spread: {analysis.spread_pct:.3f}%, Depth: {analysis.total_depth_score:.2f}")
    print(f"  Confidence: {analysis.confidence:.2f}, Reason: {analysis.reason}")

    should_trade, reason, conf = analyzer.should_trade("sell")
    print(f"  Trade decision: {should_trade} - {reason} (conf: {conf:.2f})")
