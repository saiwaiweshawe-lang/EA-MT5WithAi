# Cross-Exchange Spread Monitor Module
# Monitor price spreads across multiple exchanges and trigger arbitrage opportunities

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class SpreadLevel(Enum):
    """Spread level classification"""
    MINIMAL = "minimal"           # < 0.05%
    LOW = "low"                   # 0.05% - 0.1%
    NORMAL = "normal"             # 0.1% - 0.2%
    HIGH = "high"                 # 0.2% - 0.5%
    EXTREME = "extreme"           # > 0.5%


@dataclass
class ExchangePrice:
    """Price from an exchange"""
    exchange: str
    symbol: str
    price: float
    timestamp: datetime
    bid: float = 0.0
    ask: float = 0.0
    spread: float = 0.0


@dataclass
class SpreadAnalysis:
    """Spread analysis result"""
    best_exchange: str           # Exchange with lowest price
    best_price: float           # Best price
    worst_exchange: str          # Exchange with highest price
    worst_price: float          # Worst price
    spread_pct: float          # Spread as percentage
    spread_level: SpreadLevel
    arbitrage_profit_pct: float  # Potential arbitrage profit
    action: str                # trade_arb/hold/warn
    confidence: float           # 0-1
    reason: str


@dataclass
class ArbitrageOpportunity:
    """Arbitrage opportunity"""
    symbol: str
    buy_exchange: str          # Buy from this exchange
    sell_exchange: str         # Sell on this exchange
    buy_price: float
    sell_price: float
    spread_pct: float
    estimated_profit_pct: float
    confidence: float
    timestamp: datetime


class CrossExchangeSpreadMonitor:
    """Cross-exchange spread monitor"""

    def __init__(self, config: Dict = None):
        self.config = config or {}

        # Supported exchanges
        self.supported_exchanges = self.config.get("supported_exchanges", [
            "binance", "okx", "bybit"
        ])

        # Spread thresholds
        self.minimal_spread_threshold = self.config.get("minimal_spread_threshold", 0.0005)  # 0.05%
        self.low_spread_threshold = self.config.get("low_spread_threshold", 0.001)      # 0.1%
        self.normal_spread_threshold = self.config.get("normal_spread_threshold", 0.002)     # 0.2%
        self.high_spread_threshold = self.config.get("high_spread_threshold", 0.005)      # 0.5%
        self.extreme_spread_threshold = self.config.get("extreme_spread_threshold", 0.005)  # > 0.5%

        # Arbitrage thresholds
        self.min_arb_profit_pct = self.config.get("min_arb_profit_pct", 0.001)  # 0.1%
        self.arb_threshold = self.config.get("arb_threshold", 0.002)          # 0.2%

        # Price history
        self.price_history: Dict[str, List[ExchangePrice]] = {ex: [] for ex in self.supported_exchanges}
        self.max_history_length = self.config.get("max_history_length", 100)

        # Active arbitrage opportunities
        self.active_opportunities: List[ArbitrageOpportunity] = []

        # Tracking
        self.last_arb_trigger = {}  # {symbol: datetime}

    def update_price(self, exchange: str, symbol: str, price: float,
                   bid: float = 0.0, ask: float = 0.0):
        """
        Update price from an exchange

        Args:
            exchange: Exchange name
            symbol: Trading symbol
            price: Current price
            bid: Best bid price (optional)
            ask: Best ask price (optional)
        """
        price_data = ExchangePrice(
            exchange=exchange,
            symbol=symbol,
            price=price,
            timestamp=datetime.now(),
            bid=bid,
            ask=ask,
            spread=(ask - bid) if bid > 0 and ask > 0 else 0.0
        )

        if exchange not in self.price_history:
            self.price_history[exchange] = []

        self.price_history[exchange].append(price_data)

        # Maintain history length
        if len(self.price_history[exchange]) > self.max_history_length:
            self.price_history[exchange].pop(0)

        logger.debug(f"价格更新: {exchange} {symbol} {price:.2f}")

    def analyze_spread(self, symbol: str) -> SpreadAnalysis:
        """
        Analyze current spread across exchanges

        Args:
            symbol: Trading symbol

        Returns:
            SpreadAnalysis
        """
        latest_prices = {}

        # Get latest price from each exchange
        for exchange in self.supported_exchanges:
            if self.price_history.get(exchange):
                history = self.price_history[exchange]
                # Find most recent price for this symbol
                for price_data in reversed(history):
                    if price_data.symbol == symbol:
                        latest_prices[exchange] = price_data
                        break

        if len(latest_prices) < 2:
            return SpreadAnalysis(
                best_exchange="",
                best_price=0.0,
                worst_exchange="",
                worst_price=0.0,
                spread_pct=0.0,
                spread_level=SpreadLevel.NORMAL,
                arbitrage_profit_pct=0.0,
                action="hold",
                confidence=0.0,
                reason="价格数据不足（需要至少2个交易所）"
            )

        # Find best and worst prices
        exch_list = list(latest_prices.keys())
        best_exchange = exch_list[0]
        worst_exchange = exch_list[0]
        best_price = latest_prices[best_exchange].price
        worst_price = latest_prices[best_exchange].price

        for exchange, price_data in latest_prices.items():
            if price_data.price < best_price:
                best_price = price_data.price
                best_exchange = exchange
            if price_data.price > worst_price:
                worst_price = price_data.price
                worst_exchange = exchange

        # Calculate spread percentage
        spread_pct = (worst_price - best_price) / best_price if best_price > 0 else 0

        # Classify spread level
        if spread_pct < self.minimal_spread_threshold:
            spread_level = SpreadLevel.MINIMAL
        elif spread_pct < self.low_spread_threshold:
            spread_level = SpreadLevel.LOW
        elif spread_pct < self.normal_spread_threshold:
            spread_level = SpreadLevel.NORMAL
        elif spread_pct < self.extreme_spread_threshold:
            spread_level = SpreadLevel.HIGH
        else:
            spread_level = SpreadLevel.EXTREME

        # Calculate potential arbitrage profit
        arb_profit_pct = spread_pct

        # Determine action and confidence
        confidence = 1.0
        action = "hold"

        if spread_level == SpreadLevel.MINIMAL or spread_level == SpreadLevel.LOW:
            # Minimal spread - good for arbitrage
            action = "trade_arb"
            confidence = 0.9
        elif spread_level == SpreadLevel.HIGH or spread_level == SpreadLevel.EXTREME:
            # High spread - warn
            action = "warn"
            confidence = 0.5

        # Check arbitrage threshold
        if arb_profit_pct >= self.arb_threshold:
            action = "trade_arb"
            confidence = 0.95

        return SpreadAnalysis(
            best_exchange=best_exchange,
            best_price=best_price,
            worst_exchange=worst_exchange,
            worst_price=worst_price,
            spread_pct=spread_pct,
            spread_level=spread_level,
            arbitrage_profit_pct=arb_profit_pct,
            action=action,
            confidence=confidence,
            reason=self._generate_reason(best_exchange, worst_exchange, spread_pct, spread_level)
        )

    def _generate_reason(self, best_ex: str, worst_ex: str, spread_pct: float,
                       spread_level: SpreadLevel) -> str:
        """Generate explanation for spread analysis"""
        return f"价差{spread_pct:.2%}({spread_level.value})，最低价{best_ex}，最高价{worst_ex}"

    def detect_arbitrage(self, symbol: str) -> Optional[ArbitrageOpportunity]:
        """
        Detect arbitrage opportunity

        Args:
            symbol: Trading symbol

        Returns:
            ArbitrageOpportunity or None
        """
        analysis = self.analyze_spread(symbol)

        # Only create opportunity for significant spreads
        if analysis.action != "trade_arb" or analysis.arbitrage_profit_pct < self.min_arb_profit_pct:
            return None

        # Check if recently triggered
        now = datetime.now()
        if symbol in self.last_arb_trigger:
            if (now - self.last_arb_trigger[symbol]).total_seconds() < 60:  # Cooldown 1 minute
                return None

        # Create opportunity
        opportunity = ArbitrageOpportunity(
            symbol=symbol,
            buy_exchange=analysis.best_exchange,
            sell_exchange=analysis.worst_exchange,
            buy_price=analysis.best_price,
            sell_price=analysis.worst_price,
            spread_pct=analysis.spread_pct,
            estimated_profit_pct=analysis.arbitrage_profit_pct,
            confidence=analysis.confidence,
            timestamp=now
        )

        self.last_arb_trigger[symbol] = now
        logger.info(f"发现套利机会: {symbol} {analysis.best_exchange}->{analysis.worst_exchange} 利润{analysis.arbitrage_profit_pct:.2%}")

        # Add to active opportunities
        self.active_opportunities.append(opportunity)

        return opportunity

    def get_spread_summary(self, symbol: Optional[str] = None) -> Dict:
        """Get spread analysis summary"""
        summary = {
            "timestamp": datetime.now().isoformat(),
            "exchanges": {ex: [] for ex in self.supported_exchanges},
            "opportunities": len(self.active_opportunities)
        }

        if symbol:
            analysis = self.analyze_spread(symbol)
            summary["symbol_analysis"] = {
                "symbol": symbol,
                "best_exchange": analysis.best_exchange,
                "worst_exchange": analysis.worst_exchange,
                "spread_pct": analysis.spread_pct,
                "spread_level": analysis.spread_level,
                "action": analysis.action
            }
        else:
            for exchange in self.supported_exchanges:
                if self.price_history.get(exchange):
                    latest = max(
                        [p for p in self.price_history[exchange] if p.symbol == symbol],
                        key=lambda x: x.timestamp
                    ) if self.price_history.get(exchange) else None
                    summary["exchanges"][exchange].append({
                        "latest_price": latest.price if latest else None,
                        "latest_time": latest.timestamp.isoformat() if latest else None
                    })

        return summary

    def get_price_diff_matrix(self) -> Dict[str, Dict[str, float]]:
        """
        Get price difference matrix between exchanges

        Returns:
            {symbol: {exchange1: {exchange2: diff_pct}}}
        """
        matrix = {}

        for symbol in set(
            [p.symbol for ex_prices in self.price_history.values() for p in ex_prices]
        ):
            matrix[symbol] = {}

            for ex1 in self.supported_exchanges:
                matrix[symbol][ex1] = {}

                price1 = None
                if self.price_history.get(ex1):
                    for p in self.price_history[ex1]:
                        if p.symbol == symbol:
                            price1 = p.price
                            break

                for ex2 in self.supported_exchanges:
                    price2 = None
                    if self.price_history.get(ex2):
                        for p in self.price_history[ex2]:
                            if p.symbol == symbol:
                                price2 = p.price
                                break

                    if price1 and price2 and price1 > 0:
                        diff_pct = (price2 - price1) / price1
                        matrix[symbol][ex1][ex2] = diff_pct

        return matrix

    def clear_opportunities(self):
        """Clear all active arbitrage opportunities"""
        self.active_opportunities.clear()
        logger.info("已清除所有套利机会记录")


def create_cross_exchange_spread_monitor(config: Dict = None) -> CrossExchangeSpreadMonitor:
    """Create cross-exchange spread monitor"""
    return CrossExchangeSpreadMonitor(config)


if __name__ == "__main__":
    # Test code
    monitor = CrossExchangeSpreadMonitor()

    print("\n=== Testing Cross-Exchange Spread Monitor ===")

    # Simulate prices from multiple exchanges
    base_time = datetime.now()
    symbol = "BTCUSDT"
    base_price = 40000.0

    # Scenario 1: Minimal spread
    print("\nScenario 1: Minimal spread (good)")
    monitor.update_price("binance", symbol, base_price)
    monitor.update_price("okx", symbol, base_price * 1.0003)  # 0.03% spread
    monitor.update_price("bybit", symbol, base_price * 1.0005)

    analysis = monitor.analyze_spread(symbol)
    print(f"  Spread: {analysis.spread_pct:.3f}%")
    print(f"  Level: {analysis.spread_level.value}")
    print(f"  Action: {analysis.action}")
    print(f"  Reason: {analysis.reason}")

    # Test arbitrage detection
    arb = monitor.detect_arbitrage(symbol)
    if arb:
        print(f"  Arbitrage: {arb.buy_exchange} -> {arb.sell_exchange}")
        print(f"  Profit: {arb.estimated_profit_pct:.2f}%")

    # Scenario 2: High spread (poor for arbitrage)
    print("\nScenario 2: High spread")
    monitor.update_price("binance", symbol, base_price)
    monitor.update_price("okx", symbol, base_price * 1.006)  # 0.6% spread
    monitor.update_price("bybit", symbol, base_price * 1.008)

    analysis = monitor.analyze_spread(symbol)
    print(f"  Spread: {analysis.spread_pct:.3f}%")
    print(f"  Level: {analysis.spread_level.value}")
    print(f"  Action: {analysis.action}")
    print(f"  Reason: {analysis.reason}")

    # Get spread summary
    print("\nSpread Summary:")
    summary = monitor.get_spread_summary(symbol)
    print(f"  Best exchange: {summary['symbol_analysis']['best_exchange']}")
    print(f"  Worst exchange: {summary['symbol_analysis']['worst_exchange']}")
    print(f"  Spread: {summary['symbol_analysis']['spread_pct']:.3f}%")
