# 市场状态过滤器
# 识别市场状态(趋势/震荡/高波动)并根据状态过滤交易信号

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class MarketState(Enum):
    """市场状态类型"""
    STRONG_UPTREND = "strong_uptrend"      # 强上升趋势
    UPTREND = "uptrend"                    # 上升趋势
    WEAK_UPTREND = "weak_uptrend"          # 弱上升趋势
    RANGING = "ranging"                     # 震荡
    CHOPPY = "choppy"                      # 无序震荡
    WEAK_DOWNTREND = "weak_downtrend"      # 弱下降趋势
    DOWNTREND = "downtrend"                # 下降趋势
    STRONG_DOWNTREND = "strong_downtrend"    # 强下降趋势


class VolatilityLevel(Enum):
    """波动率水平"""
    EXTREME_LOW = "extreme_low"
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    EXTREME_HIGH = "extreme_high"


class TradingCondition(Enum):
    """交易条件"""
    EXCELLENT = "excellent"    # 优秀
    GOOD = "good"              # 良好
    ACCEPTABLE = "acceptable"    # 可接受
    POOR = "poor"              # 较差
    AVOID = "avoid"             # 避免


@dataclass
class MarketStateAnalysis:
    """市场状态分析结果"""
    symbol: str
    timestamp: datetime
    market_state: MarketState
    volatility_level: VolatilityLevel
    trend_strength: float  # 0-1
    trend_direction: str  # up/down/neutral
    volatility_score: float  # 0-1
    momentum: float  # 0-1
    liquidity_score: float  # 0-1
    trading_condition: TradingCondition
    recommended_strategies: List[str]
    forbidden_strategies: List[str]
    position_bias: float  # -1(全空) 到 1(全多)
    confidence: float
    indicators: Dict[str, float]
    warnings: List[str] = field(default_factory=list)


class MarketStateDetector:
    """市场状态检测器"""

    def __init__(self, config: Dict = None):
        self.config = config or {}

        # 检测参数
        self.lookback_period = self.config.get("lookback_period", 100)
        self.trend_period = self.config.get("trend_period", 50)
        self.volatility_period = self.config.get("volatility_period", 20)
        self.momentum_period = self.config.get("momentum_period", 14)

        # 阈值配置
        self.strong_trend_threshold = self.config.get("strong_trend_threshold", 0.7)
        self.weak_trend_threshold = self.config.get("weak_trend_threshold", 0.3)
        self.high_volatility_threshold = self.config.get("high_volatility_threshold", 0.02)
        self.low_volatility_threshold = self.config.get("low_volatility_threshold", 0.005)
        self.choppy_threshold = self.config.get("choppy_threshold", 0.3)

        # 状态历史
        self.state_history: List[Dict] = []
        self.max_history = 100

    def detect(self, symbol: str, klines: List[Dict],
              additional_data: Dict = None) -> MarketStateAnalysis:
        """
        检测市场状态

        参数:
            symbol: 交易品种
            klines: K线数据
            additional_data: 额外数据(成交量、订单簿等)

        返回:
            MarketStateAnalysis
        """
        if len(klines) < self.lookback_period:
            return self._create_insufficient_data_result(symbol)

        df = pd.DataFrame(klines)

        # 计算各项指标
        indicators = self._calculate_indicators(df)

        # 检测市场状态
        market_state, trend_strength, trend_direction = \
            self._detect_market_state(indicators)

        # 检测波动率
        volatility_level, volatility_score = \
            self._detect_volatility(indicators)

        # 检测动量
        momentum = self._detect_momentum(indicators)

        # 检测流动性
        liquidity_score = self._detect_liquidity(df, additional_data)

        # 评估交易条件
        trading_condition, recommended_strategies, forbidden_strategies = \
            self._evaluate_trading_conditions(
                market_state, volatility_level, trend_strength, liquidity_score
            )

        # 计算仓位偏差
        position_bias = self._calculate_position_bias(trend_direction, trend_strength)

        # 生成警告
        warnings = self._generate_warnings(
            market_state, volatility_level, liquidity_score
        )

        # 计算置信度
        confidence = self._calculate_confidence(
            trend_strength, volatility_level, liquidity_score
        )

        result = MarketStateAnalysis(
            symbol=symbol,
            timestamp=datetime.now(),
            market_state=market_state,
            volatility_level=volatility_level,
            trend_strength=trend_strength,
            trend_direction=trend_direction,
            volatility_score=volatility_score,
            momentum=momentum,
            liquidity_score=liquidity_score,
            trading_condition=trading_condition,
            recommended_strategies=recommended_strategies,
            forbidden_strategies=forbidden_strategies,
            position_bias=position_bias,
            confidence=confidence,
            indicators=indicators,
            warnings=warnings
        )

        # 记录历史
        self._record_state(result)

        return result

    def _calculate_indicators(self, df: pd.DataFrame) -> Dict[str, float]:
        """计算所有指标"""
        closes = df["close"]
        highs = df["high"]
        lows = df["low"]

        indicators = {}

        # 移动平均线
        ma_short = closes.rolling(window=20).mean()
        ma_medium = closes.rolling(window=50).mean()
        ma_long = closes.rolling(window=200).mean()

        indicators["ma_short"] = ma_short.iloc[-1]
        indicators["ma_medium"] = ma_medium.iloc[-1]
        indicators["ma_long"] = ma_long.iloc[-1]

        # RSI
        delta = closes.diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)

        avg_gain = gain.rolling(window=14).mean()
        avg_loss = loss.rolling(window=14).mean()

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        indicators["rsi"] = rsi.iloc[-1]

        # MACD
        ema_12 = closes.ewm(span=12).mean()
        ema_26 = closes.ewm(span=26).mean()
        macd = ema_12 - ema_26
        macd_signal = macd.ewm(span=9).mean()

        indicators["macd"] = macd.iloc[-1]
        indicators["macd_signal"] = macd_signal.iloc[-1]
        indicators["macd_histogram"] = (macd - macd_signal).iloc[-1]

        # ATR
        prev_close = closes.shift(1)
        tr1 = highs - lows
        tr2 = abs(highs - prev_close)
        tr3 = abs(lows - prev_close)

        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=14).mean()

        indicators["atr"] = atr.iloc[-1]
        indicators["atr_pct"] = (atr.iloc[-1] / closes.iloc[-1]) * 100

        # ADX
        plus_dm = highs.diff()
        minus_dm = lows.diff()

        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm > 0] = 0
        minus_dm = -minus_dm

        plus_di = 100 * (plus_dm.rolling(window=14).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(window=14).mean() / atr)

        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.rolling(window=14).mean()

        indicators["adx"] = adx.iloc[-1]
        indicators["plus_di"] = plus_di.iloc[-1]
        indicators["minus_di"] = minus_di.iloc[-1]

        # 布林带
        bb_middle = closes.rolling(window=20).mean()
        bb_std = closes.rolling(window=20).std()
        bb_upper = bb_middle + 2 * bb_std
        bb_lower = bb_middle - 2 * bb_std

        indicators["bb_upper"] = bb_upper.iloc[-1]
        indicators["bb_middle"] = bb_middle.iloc[-1]
        indicators["bb_lower"] = bb_lower.iloc[-1]
        indicators["bb_width"] = (bb_upper - bb_lower) / bb_middle
        indicators["bb_position"] = (closes.iloc[-1] - bb_lower.iloc[-1]) / (bb_upper.iloc[-1] - bb_lower.iloc[-1])

        # 价格变化
        indicators["price_change_1d"] = (closes.iloc[-1] - closes.iloc[-24]) / closes.iloc[-24] if len(closes) >= 24 else 0
        indicators["price_change_5d"] = (closes.iloc[-1] - closes.iloc[-120]) / closes.iloc[-120] if len(closes) >= 120 else 0

        # 波动率
        returns = closes.pct_change().dropna()
        indicators["volatility_1d"] = returns.tail(24).std() if len(returns) >= 24 else 0
        indicators["volatility_5d"] = returns.tail(120).std() if len(returns) >= 120 else 0
        indicators["volatility_20d"] = returns.tail(self.volatility_period).std()

        # 当前价格
        indicators["current_price"] = closes.iloc[-1]

        return indicators

    def _detect_market_state(self,
                             indicators: Dict[str, float]) -> Tuple[MarketState, float, str]:
        """检测市场状态"""
        ma_short = indicators["ma_short"]
        ma_medium = indicators["ma_medium"]
        ma_long = indicators["ma_long"]
        current_price = indicators["current_price"]
        adx = indicators["adx"]

        # 趋势强度 (0-1)
        trend_strength = min(adx / 50, 1.0)

        # 趋势方向
        if ma_short > ma_medium > ma_long:
            trend_direction = "up"
            if trend_strength > self.strong_trend_threshold:
                state = MarketState.STRONG_UPTREND
            elif trend_strength > self.weak_trend_threshold:
                state = MarketState.UPTREND
            else:
                state = MarketState.WEAK_UPTREND
        elif ma_short < ma_medium < ma_long:
            trend_direction = "down"
            if trend_strength > self.strong_trend_threshold:
                state = MarketState.STRONG_DOWNTREND
            elif trend_strength > self.weak_trend_threshold:
                state = MarketState.DOWNTREND
            else:
                state = MarketState.WEAK_DOWNTREND
        else:
            # MA交叉或混乱
            if trend_strength < self.choppy_threshold:
                state = MarketState.CHOPPY
                trend_direction = "neutral"
            else:
                state = MarketState.RANGING
                trend_direction = "neutral"

        return state, trend_strength, trend_direction

    def _detect_volatility(self,
                           indicators: Dict[str, float]) -> Tuple[VolatilityLevel, float]:
        """检测波动率"""
        atr_pct = indicators["atr_pct"]
        volatility_20d = indicators["volatility_20d"]

        # 综合判断
        volatility_score = min((atr_pct / 3.0) + (volatility_20d / 0.03), 1.0)

        if atr_pct < 0.3 and volatility_20d < 0.005:
            level = VolatilityLevel.EXTREME_LOW
        elif atr_pct < 0.5 and volatility_20d < 0.01:
            level = VolatilityLevel.LOW
        elif atr_pct < 1.5 and volatility_20d < 0.02:
            level = VolatilityLevel.NORMAL
        elif atr_pct < 3.0 and volatility_20d < 0.04:
            level = VolatilityLevel.HIGH
        else:
            level = VolatilityLevel.EXTREME_HIGH

        return level, volatility_score

    def _detect_momentum(self, indicators: Dict[str, float]) -> float:
        """检测动量 (0-1)"""
        macd_histogram = indicators["macd_histogram"]
        price_change_5d = indicators["price_change_5d"]
        rsi = indicators["rsi"]

        # 综合动量评分
        momentum = 0.5

        # MACD动量
        if abs(macd_histogram) > 0:
            momentum += (macd_histogram / abs(macd_histogram)) * 0.25

        # 价格变化动量
        momentum += price_change_5d * 2.0

        # RSI动量
        if rsi > 50:
            momentum += (rsi - 50) / 100.0
        else:
            momentum -= (50 - rsi) / 100.0

        return max(0, min(1, momentum))

    def _detect_liquidity(self, df: pd.DataFrame,
                          additional_data: Optional[Dict]) -> float:
        """检测流动性 (0-1)"""
        liquidity_score = 0.5

        # 基于成交量的流动性
        if "volume" in df.columns:
            volumes = df["volume"].tail(20)
            avg_volume = volumes.mean()
            current_volume = volumes.iloc[-1]

            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1

            # 成交量适中表示流动性好
            if 0.5 <= volume_ratio <= 2:
                liquidity_score += 0.3
            elif volume_ratio > 2:
                liquidity_score += 0.2  # 高成交量
            else:
                liquidity_score -= 0.1  # 低成交量

        # 基于订单簿的流动性
        if additional_data and "order_book" in additional_data:
            orderbook = additional_data["order_book"]
            bid_volume = sum(v for _, v in orderbook.get("bids", []))
            ask_volume = sum(v for _, v in orderbook.get("asks", []))
            total_volume = bid_volume + ask_volume

            if total_volume > 0:
                depth_score = min(total_volume / 1000, 1.0)
                liquidity_score = liquidity_score * 0.7 + depth_score * 0.3

        # 基于价格跳动的流动性
        if "high" in df.columns and "low" in df.columns:
            recent_klines = df.tail(20)
            price_ranges = (recent_klines["high"] - recent_klines["low"]) / recent_klines["close"]
            avg_range = price_ranges.mean()

            # 价格跳动小表示流动性好
            liquidity_score -= (avg_range - 0.01) * 10

        return max(0, min(1, liquidity_score))

    def _evaluate_trading_conditions(self,
                                    market_state: MarketState,
                                    volatility_level: VolatilityLevel,
                                    trend_strength: float,
                                    liquidity_score: float) -> Tuple[TradingCondition, List[str], List[str]]:
        """评估交易条件"""
        # 策略映射
        strategy_map = {
            MarketState.STRONG_UPTREND: {
                "recommended": ["trend_follow", "breakout", "momentum", "pullback_entry"],
                "forbidden": ["mean_reversion", "counter_trend"]
            },
            MarketState.UPTREND: {
                "recommended": ["trend_follow", "pullback_entry"],
                "forbidden": ["mean_reversion"]
            },
            MarketState.WEAK_UPTREND: {
                "recommended": ["selective_trend", "position_trading"],
                "forbidden": ["aggressive_counter_trend"]
            },
            MarketState.RANGING: {
                "recommended": ["mean_reversion", "range_trade", "breakout_fade"],
                "forbidden": ["trend_follow", "momentum"]
            },
            MarketState.CHOPPY: {
                "recommended": [],  # 不建议交易
                "forbidden": ["all"]
            },
            MarketState.WEAK_DOWNTREND: {
                "recommended": ["selective_trend_short", "position_trading_short"],
                "forbidden": ["aggressive_counter_trend"]
            },
            MarketState.DOWNTREND: {
                "recommended": ["trend_follow_short", "pullback_entry_short"],
                "forbidden": ["mean_reversion"]
            },
            MarketState.STRONG_DOWNTREND: {
                "recommended": ["trend_follow_short", "breakout_short", "momentum_short", "pullback_entry_short"],
                "forbidden": ["mean_reversion", "counter_trend"]
            }
        }

        # 波动率影响
        volatility_penalties = {
            VolatilityLevel.EXTREME_LOW: {"momentum": -0.5, "breakout": -0.5},
            VolatilityLevel.EXTREME_HIGH: {"position_trading": -0.5, "selective_trend": -0.5}
        }

        recommended = strategy_map[market_state]["recommended"].copy()
        forbidden = strategy_map[market_state]["forbidden"].copy()

        # 波动率调整
        for strategy, penalty in volatility_penalties.get(volatility_level, {}).items():
            if strategy in recommended:
                recommended.remove(strategy)

        # 流动性调整
        if liquidity_score < 0.3:
            forbidden.append("scalping")  # 流动性差不适合剥头皮
        elif liquidity_score > 0.7:
            if liquidity_score not in recommended:
                recommended.append("scalping")

        # 评估交易条件
        if market_state == MarketState.CHOPPY:
            condition = TradingCondition.AVOID
        elif volatility_level == VolatilityLevel.EXTREME_HIGH:
            condition = TradingCondition.POOR
        elif volatility_level == VolatilityLevel.EXTREME_LOW:
            condition = TradingCondition.POOR
        elif liquidity_score < 0.3:
            condition = TradingCondition.POOR
        elif trend_strength > self.strong_trend_threshold and liquidity_score > 0.6:
            condition = TradingCondition.EXCELLENT
        elif trend_strength > self.weak_trend_threshold and liquidity_score > 0.5:
            condition = TradingCondition.GOOD
        else:
            condition = TradingCondition.ACCEPTABLE

        return condition, recommended, forbidden

    def _calculate_position_bias(self, trend_direction: str,
                                   trend_strength: float) -> float:
        """计算仓位偏差 (-1到1)"""
        if trend_direction == "up":
            return trend_strength
        elif trend_direction == "down":
            return -trend_strength
        else:
            return 0

    def _generate_warnings(self, market_state: MarketState,
                          volatility_level: VolatilityLevel,
                          liquidity_score: float) -> List[str]:
        """生成警告"""
        warnings = []

        if market_state == MarketState.CHOPPY:
            warnings.append("市场处于无序震荡状态,建议暂停交易")

        elif market_state == MarketState.RANGING:
            warnings.append("市场处于震荡状态,仅建议均值回归策略")

        if volatility_level == VolatilityLevel.EXTREME_HIGH:
            warnings.append("市场波动率极高,风险大幅增加,建议减小仓位或观望")

        elif volatility_level == VolatilityLevel.EXTREME_LOW:
            warnings.append("市场波动率极低,可能即将突破或流动性枯竭")

        if liquidity_score < 0.3:
            warnings.append("市场流动性较低,注意滑点风险")

        return warnings

    def _calculate_confidence(self, trend_strength: float,
                               volatility_level: VolatilityLevel,
                               liquidity_score: float) -> float:
        """计算置信度"""
        confidence = 0.5

        # 趋势强度影响
        confidence += (trend_strength - 0.5) * 0.3

        # 波动率影响
        if volatility_level == VolatilityLevel.NORMAL:
            confidence += 0.1
        elif volatility_level in [VolatilityLevel.EXTREME_LOW, VolatilityLevel.EXTREME_HIGH]:
            confidence -= 0.2

        # 流动性影响
        confidence += (liquidity_score - 0.5) * 0.2

        return max(0, min(1, confidence))

    def _record_state(self, state: MarketStateAnalysis):
        """记录状态历史"""
        record = {
            "timestamp": state.timestamp,
            "market_state": state.market_state.value,
            "volatility_level": state.volatility_level.value,
            "trend_strength": state.trend_strength,
            "trading_condition": state.trading_condition.value
        }
        self.state_history.append(record)

        if len(self.state_history) > self.max_history:
            self.state_history.pop(0)

    def _create_insufficient_data_result(self, symbol: str) -> MarketStateAnalysis:
        """创建数据不足结果"""
        return MarketStateAnalysis(
            symbol=symbol,
            timestamp=datetime.now(),
            market_state=MarketState.RANGING,
            volatility_level=VolatilityLevel.NORMAL,
            trend_strength=0.5,
            trend_direction="neutral",
            volatility_score=0.5,
            momentum=0.5,
            liquidity_score=0.5,
            trading_condition=TradingCondition.ACCEPTABLE,
            recommended_strategies=[],
            forbidden_strategies=[],
            position_bias=0,
            confidence=0,
            indicators={},
            warnings=["数据不足,无法准确分析市场状态"]
        )

    def get_state_transitions(self, lookback: int = 10) -> List[Dict]:
        """获取状态转换历史"""
        if len(self.state_history) < 2:
            return []

        transitions = []
        recent_states = self.state_history[-lookback:]

        for i in range(1, len(recent_states)):
            transition = {
                "from": recent_states[i - 1]["market_state"],
                "to": recent_states[i]["market_state"],
                "timestamp": recent_states[i]["timestamp"],
                "duration_minutes": (
                    recent_states[i]["timestamp"] - recent_states[i - 1]["timestamp"]
                ).total_seconds() / 60
            }
            transitions.append(transition)

        return transitions

    def get_state_duration(self) -> Dict[str, float]:
        """获取各状态持续时间(小时)"""
        if len(self.state_history) < 2:
            return {}

        durations = {}
        current_state = None
        state_start = None

        for record in self.state_history:
            state = record["market_state"]

            if current_state != state:
                if current_state and state_start:
                    duration = (record["timestamp"] - state_start).total_seconds() / 3600
                    durations[current_state] = durations.get(current_state, 0) + duration

                current_state = state
                state_start = record["timestamp"]

        # 计算当前状态持续时间
        if current_state and state_start:
            duration = (datetime.now() - state_start).total_seconds() / 3600
            durations[current_state] = durations.get(current_state, 0) + duration

        return durations


class StrategyFilter:
    """策略过滤器 - 根据市场状态过滤交易信号"""

    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.detector = MarketStateDetector(config)

        # 策略到信号映射
        self.strategy_signal_map = self.config.get("strategy_signal_map", {
            "trend_follow": {"buy": ["buy"], "sell": ["sell"]},
            "trend_follow_short": {"buy": [], "sell": ["sell"]},
            "mean_reversion": {"buy": ["buy"], "sell": ["sell"]},
            "breakout": {"buy": ["buy"], "sell": ["sell"]},
            "momentum": {"buy": ["buy"], "sell": ["sell"]},
            "pullback_entry": {"buy": ["buy"], "sell": []}
        })

    def filter_signal(self, symbol: str, signal: str,
                     klines: List[Dict],
                     strategy: str,
                     additional_data: Dict = None) -> Tuple[str, float, List[str]]:
        """
        过滤交易信号

        参数:
            symbol: 交易品种
            signal: 原始信号 (buy/sell/hold)
            klines: K线数据
            strategy: 使用的策略
            additional_data: 额外数据

        返回:
            (filtered_signal, confidence, reasons)
        """
        # 检测市场状态
        market_analysis = self.detector.detect(symbol, klines, additional_data)

        reasons = []
        filtered_signal = "hold"
        confidence = 0

        # 检查策略是否被禁止
        if strategy in market_analysis.forbidden_strategies:
            reasons.append(f"策略 '{strategy}' 在当前市场状态 '{market_analysis.market_state.value}' 下被禁止")
            return "hold", 0, reasons

        # 检查策略是否被推荐
        if strategy not in market_analysis.recommended_strategies:
            reasons.append(f"策略 '{strategy}' 在当前市场状态下非最佳选择")
            confidence *= 0.5

        # 检查交易条件
        if market_analysis.trading_condition == TradingCondition.AVOID:
            reasons.append(f"当前交易条件不佳: {market_analysis.trading_condition.value}")
            return "hold", 0, reasons

        # 检查信号方向与市场趋势是否一致
        if signal == "buy":
            if market_analysis.position_bias < -0.3:
                reasons.append("信号方向与市场趋势相反")
                return "hold", 0, reasons
            elif market_analysis.position_bias < 0:
                confidence *= 0.7
            else:
                confidence += 0.2

        elif signal == "sell":
            if market_analysis.position_bias > 0.3:
                reasons.append("信号方向与市场趋势相反")
                return "hold", 0, reasons
            elif market_analysis.position_bias > 0:
                confidence *= 0.7
            else:
                confidence += 0.2

        # 基于流动性调整置信度
        if market_analysis.liquidity_score < 0.5:
            reasons.append("流动性较低,建议减小仓位")
            confidence *= 0.8

        # 基于波动率调整置信度
        if market_analysis.volatility_level == VolatilityLevel.EXTREME_HIGH:
            reasons.append("波动率极高,建议减小仓位或观望")
            confidence *= 0.6
        elif market_analysis.volatility_level == VolatilityLevel.EXTREME_LOW:
            reasons.append("波动率极低,可能需要更大耐心")
            confidence *= 0.7

        # 检查策略与信号的兼容性
        if strategy in self.strategy_signal_map:
            allowed_signals = self.strategy_signal_map[strategy].get(signal, [])
            if signal in allowed_signals:
                confidence += 0.1

        # 最终置信度
        if confidence > 0.6:
            filtered_signal = signal
        else:
            filtered_signal = "hold"
            reasons.append(f"置信度不足: {confidence:.2f}")

        # 添加市场分析信息
        if market_analysis.trading_condition == TradingCondition.EXCELLENT:
            reasons.append("当前交易条件优秀")
        elif market_analysis.trading_condition == TradingCondition.GOOD:
            reasons.append("当前交易条件良好")

        return filtered_signal, min(confidence, 0.95), reasons


def create_market_state_filter(config: Dict = None) -> StrategyFilter:
    """创建市场状态过滤器"""
    return StrategyFilter(config)


if __name__ == "__main__":
    # 测试代码
    config = {
        "lookback_period": 100,
        "trend_period": 50,
        "strong_trend_threshold": 0.7,
        "weak_trend_threshold": 0.3
    }

    filter = StrategyFilter(config)

    # 生成测试数据
    import random
    np.random.seed(42)

    def generate_klines(count, base_price, trend=0):
        klines = []
        price = base_price
        for _ in range(count):
            price = price * (1 + random.uniform(-0.01, 0.01) + trend * 0.001)
            high = price * (1 + random.uniform(0, 0.005))
            low = price * (1 - random.uniform(0, 0.005))
            close = price * (1 + random.uniform(-0.002, 0.002))
            klines.append({
                "open": price,
                "high": high,
                "low": low,
                "close": close,
                "volume": random.randint(100, 1000)
            })
        return klines

    # 测试不同市场状态
    test_cases = [
        ("上升趋势", generate_klines(150, 40000, trend=1)),
        ("下降趋势", generate_klines(150, 40000, trend=-1)),
        ("震荡市场", generate_klines(150, 40000, trend=0))
    ]

    for name, klines in test_cases:
        print(f"\n{'='*60}")
        print(f"测试场景: {name}")
        print(f"{'='*60}")

        # 获取市场状态分析
        analysis = filter.detector.detect("BTCUSDT", klines)

        print(f"\n市场状态分析:")
        print(f"  状态: {analysis.market_state.value}")
        print(f"  趋势方向: {analysis.trend_direction}")
        print(f"  趋势强度: {analysis.trend_strength:.2f}")
        print(f"  波动率: {analysis.volatility_level.value} (得分: {analysis.volatility_score:.2f})")
        print(f"  流动性: {analysis.liquidity_score:.2f}")
        print(f"  仓位偏差: {analysis.position_bias:.2f}")
        print(f"  交易条件: {analysis.trading_condition.value}")
        print(f"  置信度: {analysis.confidence:.2%}")

        print(f"\n推荐策略: {', '.join(analysis.recommended_strategies) or '无'}")
        print(f"禁止策略: {', '.join(analysis.forbidden_strategies) or '无'}")

        if analysis.warnings:
            print(f"\n警告:")
            for warning in analysis.warnings:
                print(f"  - {warning}")

        # 测试信号过滤
        print(f"\n信号过滤测试:")
        for signal in ["buy", "sell", "hold"]:
            for strategy in ["trend_follow", "mean_reversion", "breakout"]:
                filtered, conf, reasons = filter.filter_signal(
                    "BTCUSDT", signal, klines, strategy
                )
                print(f"  {signal} [{strategy}]: {filtered} (置信度: {conf:.2f})")
