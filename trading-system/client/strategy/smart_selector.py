import logging
import re
from typing import List, Dict, Set, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class SymbolScore:
    symbol: str
    news_score: float
    strategy_score: float
    volatility_score: float
    total_score: float
    sentiment: str
    reasons: List[str]


class SmartSymbolSelector:
    CRYPTO_KEYWORDS = {
        "BTC", "BITCOIN", "比特币": "BTCUSDT",
        "ETH", "ETHEREUM", "以太坊": "ETHUSDT",
        "BNB", "BINANCE": "BNBUSDT",
        "SOL", "SOLANA": "SOLUSDT",
        "XRP": "XRPUSDT",
        "ADA", "CARDANO": "ADAUSDT",
        "DOGE", "DOGECOIN": "DOGEUSDT",
        "DOT", "POLKADOT": "DOTUSDT",
        "LINK": "CHAINLINK": "LINKUSDT",
        "AVAX", "AVALANCHE": "AVAXUSDT",
        "MATIC", "POLYGON": "MATICUSDT",
        "LTC", "LITECOIN": "LTCUSDT",
        "ATOM", "COSMOS": "ATOMUSDT",
        "UNI", "UNISWAP": "UNIUSDT",
        "XLM", "STELLAR": "XLMUSDT",
        "ALGO", "ALGORAND": "ALGOUSDT",
        "VET", "VECHAIN": "VETUSDT",
        "FIL", "FILECOIN": "FILUSDT",
        "TRX", "TRON": "TRXUSDT",
        "EOS": "EOSUSDT",
    }

    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.min_volatility = self.config.get("min_volatility", 0.005)
        self.max_volatility = self.config.get("max_volatility", 0.10)
        self.news_weight = self.config.get("news_weight", 0.4)
        self.strategy_weight = self.config.get("strategy_weight", 0.4)
        self.volatility_weight = self.config.get("volatility_weight", 0.2)

    def select_by_news(self, news_items: List, limit: int = 10) -> List[Tuple[str, float, str]]:
        symbol_mentions: Dict[str, Dict] = {}

        for news in news_items:
            text = f"{news.title} {news.description}".upper()
            sentiment = news.sentiment if hasattr(news, 'sentiment') else "neutral"
            relevance = getattr(news, 'relevance_score', 0.5)

            for keyword, symbol in self.CRYPTO_KEYWORDS.items():
                if keyword.upper() in text:
                    if symbol not in symbol_mentions:
                        symbol_mentions[symbol] = {
                            "count": 0,
                            "positive": 0,
                            "negative": 0,
                            "neutral": 0,
                            "relevance_sum": 0
                        }

                    symbol_mentions[symbol]["count"] += 1
                    symbol_mentions[symbol]["sentiment_" + sentiment] += 1
                    symbol_mentions[symbol]["relevance_sum"] += relevance

        results = []
        for symbol, data in symbol_mentions.items():
            avg_relevance = data["relevance_sum"] / data["count"] if data["count"] > 0 else 0.5

            sentiment_score = 0.5
            if data["positive"] > data["negative"]:
                sentiment_score = 0.7 + min(data["positive"] / 10, 0.3)
            elif data["negative"] > data["positive"]:
                sentiment_score = 0.3 - min(data["negative"] / 10, 0.3)

            score = (data["count"] * 0.2 + avg_relevance * 0.5 + sentiment_score * 0.3)

            direction = "buy" if sentiment_score > 0.55 else ("sell" if sentiment_score < 0.45 else "neutral")

            results.append((symbol, min(score, 1.0), direction))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:limit]

    def select_by_strategy(self, signals: List, limit: int = 5) -> List[Tuple[str, float, str]]:
        symbol_scores: Dict[str, Dict] = {}

        for signal in signals:
            symbol = signal.symbol
            if symbol not in symbol_scores:
                symbol_scores[symbol] = {
                    "signals": [],
                    "total_strength": 0,
                    "avg_confidence": 0
                }

            symbol_scores[symbol]["signals"].append(signal)
            symbol_scores[symbol]["total_strength"] += signal.strength
            symbol_scores[symbol]["avg_confidence"] += signal.confidence

        results = []
        for symbol, data in symbol_scores.items():
            avg_strength = data["total_strength"] / len(data["signals"]) if data["signals"] else 0
            avg_confidence = data["avg_confidence"] / len(data["signals"]) if data["signals"] else 0

            buy_count = sum(1 for s in data["signals"] if s.direction == "buy")
            sell_count = sum(1 for s in data["signals"] if s.direction == "sell")

            if buy_count > sell_count:
                direction = "buy"
                score = (avg_strength * 0.6 + avg_confidence * 0.4) * (1 + buy_count * 0.1)
            elif sell_count > buy_count:
                direction = "sell"
                score = (avg_strength * 0.6 + avg_confidence * 0.4) * (1 + sell_count * 0.1)
            else:
                direction = "neutral"
                score = avg_strength * avg_confidence * 0.5

            results.append((symbol, min(score, 1.0), direction))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:limit]

    def select_by_volatility(self, volatility_data: Dict[str, float], 
                            min_vol: float = None, 
                            max_vol: float = None) -> List[Tuple[str, float]]:
        min_vol = min_vol or self.min_volatility
        max_vol = max_vol or self.max_volatility

        results = []
        for symbol, volatility in volatility_data.items():
            if min_vol <= volatility <= max_vol:
                normalized_vol = (volatility - min_vol) / (max_vol - min_vol) if max_vol > min_vol else 0.5
                results.append((symbol, normalized_vol))

        results.sort(key=lambda x: x[1], reverse=True)
        return results

    def get_final_candidates(self,
                           news_items: List,
                           strategy_signals: List,
                           volatility_data: Dict[str, float],
                           limit: int = 5) -> List[SymbolScore]:
        news_ranked = self.select_by_news(news_items, limit=limit * 2)
        strategy_ranked = self.select_by_strategy(strategy_signals, limit=limit * 2)
        volatility_ranked = self.select_by_volatility(volatility_data, limit=limit * 2)

        all_symbols = set()
        for symbol, _, _ in news_ranked:
            all_symbols.add(symbol)
        for symbol, _, _ in strategy_ranked:
            all_symbols.add(symbol)
        for symbol, _ in volatility_ranked:
            all_symbols.add(symbol)

        symbol_scores: Dict[str, SymbolScore] = {}

        for symbol in all_symbols:
            news_score = 0.0
            news_sentiment = "neutral"
            for s, score, sentiment in news_ranked:
                if s == symbol:
                    news_score = score
                    news_sentiment = sentiment
                    break

            strategy_score = 0.0
            strategy_direction = "neutral"
            for s, score, direction in strategy_ranked:
                if s == symbol:
                    strategy_score = score
                    strategy_direction = direction
                    break

            volatility_score = 0.0
            for s, score in volatility_ranked:
                if s == symbol:
                    volatility_score = score
                    break

            total_score = (
                news_score * self.news_weight +
                strategy_score * self.strategy_weight +
                volatility_score * self.volatility_weight
            )

            reasons = []
            if news_score > 0.5:
                reasons.append(f"新闻关注度高 ({news_score:.2f})")
            if strategy_score > 0.5:
                reasons.append(f"策略信号强 ({strategy_score:.2f})")
            if volatility_score > 0.5:
                reasons.append(f"波动率适中 ({volatility_score:.2f})")

            final_direction = strategy_direction if strategy_score > news_score else news_sentiment

            symbol_scores[symbol] = SymbolScore(
                symbol=symbol,
                news_score=news_score,
                strategy_score=strategy_score,
                volatility_score=volatility_score,
                total_score=total_score,
                sentiment=final_direction,
                reasons=reasons
            )

        results = sorted(symbol_scores.values(), key=lambda x: x.total_score, reverse=True)
        return results[:limit]

    def filter_by_available_symbols(self, candidates: List[SymbolScore],
                                   available_symbols: List[str]) -> List[SymbolScore]:
        available_set = set(s.upper() for s in available_symbols)
        return [c for c in candidates if c.symbol.upper() in available_set]

    def get_trading_recommendation(self, symbol_score: SymbolScore) -> Dict:
        action = "hold"
        if symbol_score.sentiment == "buy" and symbol_score.total_score > 0.6:
            action = "buy"
        elif symbol_score.sentiment == "sell" and symbol_score.total_score > 0.6:
            action = "sell"

        return {
            "symbol": symbol_score.symbol,
            "action": action,
            "confidence": symbol_score.total_score,
            "sentiment": symbol_score.sentiment,
            "reasons": symbol_score.reasons,
            "news_score": symbol_score.news_score,
            "strategy_score": symbol_score.strategy_score,
            "volatility_score": symbol_score.volatility_score
        }
