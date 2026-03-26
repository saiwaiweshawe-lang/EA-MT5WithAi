import logging
from typing import List, Dict, Optional
from datetime import datetime
from dataclasses import dataclass

from .strategies import BaseStrategy, Signal, MarketData, TrendStrategy, ArbitrageStrategy, BreakoutStrategy

logger = logging.getLogger(__name__)


@dataclass
class StrategyPerformance:
    strategy_name: str
    total_signals: int
    winning_signals: int
    win_rate: float
    avg_strength: float
    avg_confidence: float


class QuantitativeEngine:
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.strategies: List[BaseStrategy] = []
        self.strategy_weights: Dict[str, float] = {}
        self.performance_history: Dict[str, List[StrategyPerformance]] = {}
        self.market_state = "neutral"
        
        self._init_strategies()

    def _init_strategies(self):
        self.strategies = [
            TrendStrategy(self.config.get("trend", {})),
            ArbitrageStrategy(self.config.get("arbitrage", {})),
            BreakoutStrategy(self.config.get("breakout", {})),
        ]
        
        for strategy in self.strategies:
            self.strategy_weights[strategy.name] = strategy.weight

    def set_strategy_weight(self, strategy_name: str, weight: float):
        if strategy_name in self.strategy_weights:
            self.strategy_weights[strategy_name] = weight
            logger.info(f"Strategy {strategy_name} weight set to {weight}")

    def analyze_symbol(self, symbol: str, market_data: MarketData) -> List[Signal]:
        signals = []
        
        for strategy in self.strategies:
            try:
                signal = strategy.analyze(market_data)
                if signal:
                    signal.strength *= self.strategy_weights.get(strategy.name, 1.0)
                    signals.append(signal)
            except Exception as e:
                logger.error(f"Strategy {strategy.name} failed: {e}")
        
        signals.sort(key=lambda s: s.strength * s.confidence, reverse=True)
        return signals

    def analyze_portfolio(self, symbols_data: Dict[str, MarketData]) -> Dict[str, List[Signal]]:
        results = {}
        
        for symbol, data in symbols_data.items():
            signals = self.analyze_symbol(symbol, data)
            if signals:
                results[symbol] = signals
        
        return results

    def get_aggregate_signal(self, signals: List[Signal]) -> Optional[Signal]:
        if not signals:
            return None

        buy_signals = [s for s in signals if s.direction == "buy"]
        sell_signals = [s for s in signals if s.direction == "sell"]

        if not buy_signals and not sell_signals:
            return None

        avg_buy_strength = sum(s.strength for s in buy_signals) / len(buy_signals) if buy_signals else 0
        avg_sell_strength = sum(s.strength for s in sell_signals) / len(sell_signals) if sell_signals else 0

        if avg_buy_strength > avg_sell_strength * 1.2:
            total_strength = avg_buy_strength
            direction = "buy"
        elif avg_sell_strength > avg_buy_strength * 1.2:
            total_strength = avg_sell_strength
            direction = "sell"
        else:
            return None

        avg_confidence = sum(s.confidence for s in signals) / len(signals)
        best_signal = max(signals, key=lambda s: s.strength * s.confidence)

        return Signal(
            symbol=best_signal.symbol,
            direction=direction,
            strength=total_strength,
            confidence=avg_confidence,
            strategy="Multi-Strategy",
            timestamp=datetime.now(),
            metadata={
                "signals_count": len(signals),
                "buy_signals": len(buy_signals),
                "sell_signals": len(sell_signals),
                "individual_signals": [s.strategy for s in signals]
            }
        )

    def update_market_state(self, volatility: float, trend_strength: float):
        if volatility > 0.03:
            self.market_state = "high_volatility"
        elif trend_strength > 3.0:
            self.market_state = "trend"
        elif volatility < 0.01:
            self.market_state = "low_volatility"
        else:
            self.market_state = "neutral"
        
        self._adjust_strategy_weights()

    def _adjust_strategy_weights(self):
        if self.market_state == "trend":
            self.set_strategy_weight("Trend", 1.5)
            self.set_strategy_weight("Breakout", 0.8)
            self.set_strategy_weight("Arbitrage", 0.5)
        elif self.market_state == "high_volatility":
            self.set_strategy_weight("Breakout", 1.5)
            self.set_strategy_weight("Arbitrage", 1.2)
            self.set_strategy_weight("Trend", 0.5)
        elif self.market_state == "low_volatility":
            self.set_strategy_weight("Arbitrage", 1.5)
            self.set_strategy_weight("Trend", 0.8)
            self.set_strategy_weight("Breakout", 0.5)
        else:
            self.set_strategy_weight("Trend", 1.0)
            self.set_strategy_weight("Breakout", 1.0)
            self.set_strategy_weight("Arbitrage", 1.0)

    def record_signal_result(self, signal: Signal, profit: float):
        strategy_name = signal.strategy
        if strategy_name not in self.performance_history:
            self.performance_history[strategy_name] = []

        history = self.performance_history[strategy_name]
        
        if len(history) >= 100:
            history.pop(0)
        
        history.append(StrategyPerformance(
            strategy_name=strategy_name,
            total_signals=len(history) + 1,
            winning_signals=sum(1 for p in history if p.win_rate > 0.5) + (1 if profit > 0 else 0),
            win_rate=0.0,
            avg_strength=signal.strength,
            avg_confidence=signal.confidence
        ))

    def get_strategy_performance(self, strategy_name: str) -> Optional[StrategyPerformance]:
        history = self.performance_history.get(strategy_name, [])
        if not history:
            return None
        return history[-1]

    def get_all_performances(self) -> Dict[str, StrategyPerformance]:
        return {
            name: self.get_strategy_performance(name)
            for name in self.strategy_weights.keys()
        }
