# 多时间框架分析模块
# 整合多个时间框架的信号,确认交易方向和入场时机

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import logging
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class TrendDirection(Enum):
    """趋势方向"""
    STRONG_UPTREND = "strong_uptrend"
    UPTREND = "uptrend"
    WEAK_UPTREND = "weak_uptrend"
    NEUTRAL = "neutral"
    WEAK_DOWNTREND = "weak_downtrend"
    DOWNTREND = "downtrend"
    STRONG_DOWNTREND = "strong_downtrend"


class SignalStrength(Enum):
    """信号强度"""
    VERY_STRONG = 5
    STRONG = 4
    MODERATE = 3
    WEAK = 2
    VERY_WEAK = 1


@dataclass
class TimeframeSignal:
    """单个时间框架的信号"""
    timeframe: str
    trend: TrendDirection
    signal: str  # buy/sell/hold
    strength: SignalStrength
    indicators: Dict[str, float]
    confidence: float
    reasons: List[str] = field(default_factory=list)


@dataclass
class MultiTimeframeResult:
    """多时间框架分析结果"""
    symbol: str
    timeframe_signals: Dict[str, TimeframeSignal]
    composite_signal: str  # buy/sell/hold
    composite_strength: SignalStrength
    composite_confidence: float
    trend_alignment: bool  # 各时间框架趋势是否一致
    entry_signal: str  # 入场信号
    entry_strength: SignalStrength
    entry_confidence: float
    support_levels: List[float] = field(default_factory=list)
    resistance_levels: List[float] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


class TechnicalIndicators:
    """技术指标计算"""

    @staticmethod
    def sma(data: pd.Series, period: int) -> pd.Series:
        """简单移动平均"""
        return data.rolling(window=period).mean()

    @staticmethod
    def ema(data: pd.Series, period: int) -> pd.Series:
        """指数移动平均"""
        return data.ewm(span=period, adjust=False).mean()

    @staticmethod
    def rsi(data: pd.Series, period: int = 14) -> pd.Series:
        """RSI指标"""
        delta = data.diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)

        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    @staticmethod
    def macd(data: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, pd.Series]:
        """MACD指标"""
        ema_fast = TechnicalIndicators.ema(data, fast)
        ema_slow = TechnicalIndicators.ema(data, slow)
        macd_line = ema_fast - ema_slow
        signal_line = TechnicalIndicators.ema(macd_line, signal)
        histogram = macd_line - signal_line

        return {
            "macd": macd_line,
            "signal": signal_line,
            "histogram": histogram
        }

    @staticmethod
    def bollinger_bands(data: pd.Series, period: int = 20, std_dev: float = 2.0) -> Dict[str, pd.Series]:
        """布林带"""
        middle = data.rolling(window=period).mean()
        std = data.rolling(window=period).std()

        upper = middle + std_dev * std
        lower = middle - std_dev * std

        return {
            "middle": middle,
            "upper": upper,
            "lower": lower,
            "width": (upper - lower) / middle
        }

    @staticmethod
    def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
        """ATR指标"""
        prev_close = close.shift(1)
        tr1 = high - low
        tr2 = abs(high - prev_close)
        tr3 = abs(low - prev_close)

        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()

        return atr

    @staticmethod
    def adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> Dict[str, pd.Series]:
        """ADX指标"""
        plus_dm = high.diff()
        minus_dm = low.diff()

        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm > 0] = 0
        minus_dm = -minus_dm

        atr = TechnicalIndicators.atr(high, low, close, period)

        plus_di = 100 * (plus_dm.rolling(window=period).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(window=period).mean() / atr)

        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.rolling(window=period).mean()

        return {
            "adx": adx,
            "plus_di": plus_di,
            "minus_di": minus_di
        }

    @staticmethod
    def support_resistance(data: pd.Series, window: int = 20) -> Tuple[List[float], List[float]]:
        """支撑阻力位"""
        supports = []
        resistances = []

        for i in range(window, len(data) - window):
            is_support = True
            is_resistance = True

            # 检查是否是局部低点
            for j in range(i - window, i):
                if data.iloc[j] <= data.iloc[i]:
                    is_support = False
                if data.iloc[j] >= data.iloc[i]:
                    is_resistance = False

            for j in range(i + 1, i + window + 1):
                if data.iloc[j] <= data.iloc[i]:
                    is_support = False
                if data.iloc[j] >= data.iloc[i]:
                    is_resistance = False

            if is_support:
                supports.append(data.iloc[i])
            if is_resistance:
                resistances.append(data.iloc[i])

        # 合并相近的价格水平
        supports = TechnicalIndicators._merge_levels(supports)
        resistances = TechnicalIndicators._merge_levels(resistances)

        return supports[-5:], resistances[-5:]  # 返回最近的5个水平

    @staticmethod
    def _merge_levels(levels: List[float], threshold: float = 0.01) -> List[float]:
        """合并相近的支撑/阻力位"""
        if not levels:
            return []

        merged = []
        sorted_levels = sorted(levels)

        current = sorted_levels[0]
        for level in sorted_levels[1:]:
            if abs(level - current) / current < threshold:
                current = (current + level) / 2
            else:
                merged.append(current)
                current = level

        merged.append(current)
        return merged


class TimeframeAnalyzer:
    """单个时间框架分析器"""

    def __init__(self, timeframe: str, config: Dict = None):
        self.timeframe = timeframe
        self.config = config or {}

        # MA周期配置
        self.ma_periods = self.config.get("ma_periods", {
            "fast": 7,
            "medium": 25,
            "slow": 50,
            "long": 200
        })

        # 指标配置
        self.rsi_period = self.config.get("rsi_period", 14)
        self.macd_params = self.config.get("macd_params", {"fast": 12, "slow": 26, "signal": 9})
        self.bb_period = self.config.get("bb_period", 20)
        self.bb_std = self.config.get("bb_std", 2.0)
        self.adx_period = self.config.get("adx_period", 14)

        # 阈值配置
        self.rsi_overbought = self.config.get("rsi_overbought", 70)
        self.rsi_oversold = self.config.get("rsi_oversold", 30)
        self.adx_strong_trend = self.config.get("adx_strong_trend", 25)
        self.adx_weak_trend = self.config.get("adx_weak_trend", 20)

    def analyze(self, klines: List[Dict]) -> TimeframeSignal:
        """分析单个时间框架"""
        if len(klines) < max(self.ma_periods["long"], self.bb_period, self.adx_period) + 10:
            return self._create_insufficient_data_signal()

        # 准备数据
        df = pd.DataFrame(klines)
        closes = df["close"]
        highs = df["high"]
        lows = df["low"]

        # 计算指标
        indicators = self._calculate_all_indicators(df)

        # 分析趋势
        trend = self._analyze_trend(indicators)

        # 生成信号
        signal, strength, confidence, reasons = self._generate_signal(indicators, trend)

        return TimeframeSignal(
            timeframe=self.timeframe,
            trend=trend,
            signal=signal,
            strength=strength,
            indicators=indicators,
            confidence=confidence,
            reasons=reasons
        )

    def _calculate_all_indicators(self, df: pd.DataFrame) -> Dict[str, float]:
        """计算所有指标"""
        closes = df["close"]
        highs = df["high"]
        lows = df["low"]

        indicators = {}

        # 移动平均线
        fast_ma = TechnicalIndicators.ema(closes, self.ma_periods["fast"]).iloc[-1]
        medium_ma = TechnicalIndicators.ema(closes, self.ma_periods["medium"]).iloc[-1]
        slow_ma = TechnicalIndicators.ema(closes, self.ma_periods["slow"]).iloc[-1]
        long_ma = TechnicalIndicators.ema(closes, self.ma_periods["long"]).iloc[-1]

        indicators.update({
            "ma_fast": fast_ma,
            "ma_medium": medium_ma,
            "ma_slow": slow_ma,
            "ma_long": long_ma
        })

        # RSI
        rsi = TechnicalIndicators.rsi(closes, self.rsi_period).iloc[-1]
        indicators["rsi"] = rsi

        # MACD
        macd_result = TechnicalIndicators.macd(closes, **self.macd_params)
        indicators.update({
            "macd": macd_result["macd"].iloc[-1],
            "macd_signal": macd_result["signal"].iloc[-1],
            "macd_histogram": macd_result["histogram"].iloc[-1],
            "macd_histogram_prev": macd_result["histogram"].iloc[-2]
        })

        # 布林带
        bb_result = TechnicalIndicators.bollinger_bands(closes, self.bb_period, self.bb_std)
        indicators.update({
            "bb_upper": bb_result["upper"].iloc[-1],
            "bb_middle": bb_result["middle"].iloc[-1],
            "bb_lower": bb_result["lower"].iloc[-1],
            "bb_width": bb_result["width"].iloc[-1]
        })

        # ADX
        adx_result = TechnicalIndicators.adx(highs, lows, closes, self.adx_period)
        indicators.update({
            "adx": adx_result["adx"].iloc[-1],
            "plus_di": adx_result["plus_di"].iloc[-1],
            "minus_di": adx_result["minus_di"].iloc[-1]
        })

        # 当前价格
        indicators["price"] = closes.iloc[-1]

        # MA排列
        indicators["ma_alignment"] = self._check_ma_alignment(
            fast_ma, medium_ma, slow_ma, long_ma
        )

        return indicators

    def _analyze_trend(self, indicators: Dict[str, float]) -> TrendDirection:
        """分析趋势方向"""
        price = indicators["price"]
        fast_ma = indicators["ma_fast"]
        medium_ma = indicators["ma_medium"]
        slow_ma = indicators["ma_slow"]
        long_ma = indicators["ma_long"]
        adx = indicators["adx"]
        ma_alignment = indicators["ma_alignment"]

        # 判断趋势强度
        if adx > self.adx_strong_trend:
            strength = "strong"
        elif adx > self.adx_weak_trend:
            strength = ""
        else:
            return TrendDirection.NEUTRAL

        # 基于MA排列判断方向
        if ma_alignment == "bullish":
            # 完全多头排列
            if strength == "strong":
                return TrendDirection.STRONG_UPTREND
            else:
                # 检查回调程度
                if price > medium_ma:
                    return TrendDirection.UPTREND
                elif price > slow_ma:
                    return TrendDirection.WEAK_UPTREND
                else:
                    return TrendDirection.NEUTRAL

        elif ma_alignment == "bearish":
            # 完全空头排列
            if strength == "strong":
                return TrendDirection.STRONG_DOWNTREND
            else:
                if price < medium_ma:
                    return TrendDirection.DOWNTREND
                elif price < slow_ma:
                    return TrendDirection.WEAK_DOWNTREND
                else:
                    return TrendDirection.NEUTRAL

        else:
            # MA混乱,可能是震荡
            # 检查价格相对于长期MA的位置
            if price > long_ma and adx > self.adx_weak_trend:
                return TrendDirection.WEAK_UPTREND
            elif price < long_ma and adx > self.adx_weak_trend:
                return TrendDirection.WEAK_DOWNTREND
            else:
                return TrendDirection.NEUTRAL

    def _generate_signal(self, indicators: Dict[str, float],
                       trend: TrendDirection) -> Tuple[str, SignalStrength, float, List[str]]:
        """生成交易信号"""
        reasons = []
        bullish_score = 0
        bearish_score = 0

        # 1. MA交叉信号
        ma_alignment = indicators["ma_alignment"]
        if ma_alignment == "bullish":
            bullish_score += 2
            reasons.append("多头排列")
        elif ma_alignment == "bearish":
            bearish_score += 2
            reasons.append("空头排列")

        # 2. RSI信号
        rsi = indicators["rsi"]
        if rsi < self.rsi_oversold:
            bullish_score += 2
            reasons.append(f"RSI超卖({rsi:.1f})")
        elif rsi > self.rsi_overbought:
            bearish_score += 2
            reasons.append(f"RSI超买({rsi:.1f})")
        elif rsi < 50 and trend in [TrendDirection.UPTREND, TrendDirection.STRONG_UPTREND]:
            bullish_score += 1
            reasons.append("RSI回调")
        elif rsi > 50 and trend in [TrendDirection.DOWNTREND, TrendDirection.STRONG_DOWNTREND]:
            bearish_score += 1
            reasons.append("RSI回调")

        # 3. MACD信号
        macd_hist = indicators["macd_histogram"]
        macd_hist_prev = indicators["macd_histogram_prev"]

        if macd_hist > 0 and macd_hist_prev <= 0:
            bullish_score += 3
            reasons.append("MACD金叉")
        elif macd_hist < 0 and macd_hist_prev >= 0:
            bearish_score += 3
            reasons.append("MACD死叉")
        elif macd_hist > 0:
            bullish_score += 1
        elif macd_hist < 0:
            bearish_score += 1

        # 4. 布林带信号
        bb_upper = indicators["bb_upper"]
        bb_lower = indicators["bb_lower"]
        price = indicators["price"]

        if price < bb_lower:
            bullish_score += 2
            reasons.append("触及下轨")
        elif price > bb_upper:
            bearish_score += 2
            reasons.append("触及上轨")

        # 5. ADX确认
        adx = indicators["adx"]
        if adx > self.adx_strong_trend:
            # 强趋势,确认方向
            if trend in [TrendDirection.UPTREND, TrendDirection.STRONG_UPTREND]:
                bullish_score += 1
                reasons.append(f"强上升趋势(ADX={adx:.1f})")
            elif trend in [TrendDirection.DOWNTREND, TrendDirection.STRONG_DOWNTREND]:
                bearish_score += 1
                reasons.append(f"强下降趋势(ADX={adx:.1f})")
        elif adx < self.adx_weak_trend:
            reasons.append(f"趋势不明确(ADX={adx:.1f})")

        # 生成最终信号
        total_score = bullish_score + bearish_score
        if total_score == 0:
            signal = "hold"
            strength = SignalStrength.VERY_WEAK
            confidence = 0.3
        elif bullish_score > bearish_score:
            signal = "buy"
            strength = self._calculate_strength(bullish_score - bearish_score, total_score)
            confidence = bullish_score / total_score
        elif bearish_score > bullish_score:
            signal = "sell"
            strength = self._calculate_strength(bearish_score - bullish_score, total_score)
            confidence = bearish_score / total_score
        else:
            signal = "hold"
            strength = SignalStrength.VERY_WEAK
            confidence = 0.4

        return signal, strength, confidence, reasons

    def _check_ma_alignment(self, fast: float, medium: float,
                           slow: float, long: float) -> str:
        """检查MA排列"""
        if fast > medium > slow > long:
            return "bullish"
        elif fast < medium < slow < long:
            return "bearish"
        else:
            return "mixed"

    def _calculate_strength(self, net_score: int, total_score: int) -> SignalStrength:
        """计算信号强度"""
        if total_score == 0:
            return SignalStrength.VERY_WEAK

        margin = abs(net_score) / total_score

        if margin > 0.6:
            return SignalStrength.VERY_STRONG
        elif margin > 0.4:
            return SignalStrength.STRONG
        elif margin > 0.2:
            return SignalStrength.MODERATE
        else:
            return SignalStrength.MODERATE

    def _create_insufficient_data_signal(self) -> TimeframeSignal:
        """创建数据不足信号"""
        return TimeframeSignal(
            timeframe=self.timeframe,
            trend=TrendDirection.NEUTRAL,
            signal="hold",
            strength=SignalStrength.VERY_WEAK,
            indicators={},
            confidence=0.0,
            reasons=["数据不足"]
        )


class MultiTimeframeAnalyzer:
    """多时间框架综合分析器"""

    def __init__(self, config: Dict = None):
        self.config = config or {}

        # 时间框架层次
        self.timeframes = self.config.get("timeframes", {
            "trend": ["1d", "4h"],      # 主趋势
            "entry": ["1h"],              # 入场方向
            "timing": ["15m", "5m"]      # 入场时机
        })

        self.all_timeframes = []
        for tf_list in self.timeframes.values():
            self.all_timeframes.extend(tf_list)

        # 确认阈值
        self.confirmation_threshold = self.config.get("confirmation_threshold", 2)
        self.trend_alignment_required = self.config.get("trend_alignment_required", True)

        # 创建各时间框架分析器
        self.analyzers = {}
        for tf in self.all_timeframes:
            self.analyzers[tf] = TimeframeAnalyzer(tf, self.config.get(tf, {}))

    def analyze(self, symbol: str,
                klines_data: Dict[str, List[Dict]]) -> MultiTimeframeResult:
        """
        综合分析多个时间框架

        参数:
            symbol: 交易品种
            klines_data: 各时间框架的K线数据
                        {"1d": [...], "4h": [...], "1h": [...], "15m": [...], "5m": [...]}

        返回:
            MultiTimeframeResult
        """
        timeframe_signals = {}
        warnings = []

        # 分析每个时间框架
        for tf in self.all_timeframes:
            if tf in klines_data:
                signal = self.analyzers[tf].analyze(klines_data[tf])
                timeframe_signals[tf] = signal

        # 检查数据完整性
        if len(timeframe_signals) < 3:
            warnings.append(f"时间框架数据不足,仅{len(timeframe_signals)}个")

        # 分析趋势一致性
        trend_alignment = self._check_trend_alignment(timeframe_signals)

        # 生成综合信号
        composite_signal, composite_strength, composite_confidence = \
            self._generate_composite_signal(timeframe_signals, trend_alignment)

        # 生成入场信号
        entry_signal, entry_strength, entry_confidence = \
            self._generate_entry_signal(timeframe_signals)

        # 获取支撑阻力位
        support_levels, resistance_levels = self._get_support_resistance_levels(klines_data)

        # 生成建议
        recommendations = self._generate_recommendations(
            timeframe_signals, composite_signal, trend_alignment
        )

        # 额外警告
        warnings.extend(self._generate_warnings(timeframe_signals, trend_alignment))

        return MultiTimeframeResult(
            symbol=symbol,
            timeframe_signals=timeframe_signals,
            composite_signal=composite_signal,
            composite_strength=composite_strength,
            composite_confidence=composite_confidence,
            trend_alignment=trend_alignment,
            entry_signal=entry_signal,
            entry_strength=entry_strength,
            entry_confidence=entry_confidence,
            support_levels=support_levels,
            resistance_levels=resistance_levels,
            warnings=warnings,
            recommendations=recommendations
        )

    def _check_trend_alignment(self,
                              timeframe_signals: Dict[str, TimeframeSignal]) -> bool:
        """检查各时间框架趋势是否一致"""
        if len(timeframe_signals) < 2:
            return False

        # 提取趋势方向
        trend_directions = []
        for signal in timeframe_signals.values():
            if signal.trend not in [TrendDirection.NEUTRAL]:
                trend_directions.append(signal.trend)

        if len(trend_directions) < 2:
            return True

        # 检查一致性
        bullish_trends = sum(1 for t in trend_directions
                           if t in [TrendDirection.UPTREND, TrendDirection.STRONG_UPTREND])
        bearish_trends = sum(1 for t in trend_directions
                           if t in [TrendDirection.DOWNTREND, TrendDirection.STRONG_DOWNTREND])

        total = len(trend_directions)

        # 如果70%以上趋势一致,认为对齐
        if bullish_trends >= total * 0.7 or bearish_trends >= total * 0.7:
            return True

        return False

    def _generate_composite_signal(self,
                                  timeframe_signals: Dict[str, TimeframeSignal],
                                  trend_alignment: bool) -> Tuple[str, SignalStrength, float]:
        """生成综合信号"""
        # 权重配置
        weights = {
            "1d": 0.3,
            "4h": 0.25,
            "1h": 0.2,
            "15m": 0.15,
            "5m": 0.1
        }

        # 计算加权信号
        weighted_bullish = 0
        weighted_bearish = 0
        total_weight = 0

        for tf, signal in timeframe_signals.items():
            weight = weights.get(tf, 0.1)

            if signal.signal == "buy":
                strength_weight = signal.strength.value / 5.0
                weighted_bullish += weight * strength_weight * signal.confidence
            elif signal.signal == "sell":
                strength_weight = signal.strength.value / 5.0
                weighted_bearish += weight * strength_weight * signal.confidence

            total_weight += weight

        # 如果需要趋势对齐但未对齐,降低置信度
        if self.trend_alignment_required and not trend_alignment:
            weighted_bullish *= 0.5
            weighted_bearish *= 0.5

        # 生成最终信号
        if weighted_bullish > weighted_bearish and weighted_bullish > 0.15:
            signal = "buy"
            strength = self._map_to_strength((weighted_bullish - weighted_bearish) / weighted_bullish)
            confidence = min(weighted_bullish / total_weight, 0.95)
        elif weighted_bearish > weighted_bullish and weighted_bearish > 0.15:
            signal = "sell"
            strength = self._map_to_strength((weighted_bearish - weighted_bullish) / weighted_bearish)
            confidence = min(weighted_bearish / total_weight, 0.95)
        else:
            signal = "hold"
            strength = SignalStrength.VERY_WEAK
            confidence = 0.3

        return signal, strength, confidence

    def _generate_entry_signal(self,
                              timeframe_signals: Dict[str, TimeframeSignal]) -> Tuple[str, SignalStrength, float]:
        """生成入场信号(基于较低时间框架)"""
        # 优先使用15m和5m的信号
        entry_tfs = ["15m", "5m", "1h"]

        for tf in entry_tfs:
            if tf in timeframe_signals:
                signal = timeframe_signals[tf]
                if signal.signal != "hold" and signal.confidence > 0.5:
                    return signal.signal, signal.strength, signal.confidence

        return "hold", SignalStrength.VERY_WEAK, 0.3

    def _get_support_resistance_levels(self,
                                      klines_data: Dict[str, List[Dict]]) -> Tuple[List[float], List[float]]:
        """获取支撑阻力位"""
        # 使用1h时间框架计算
        tf = "1h"
        if tf not in klines_data or len(klines_data[tf]) < 50:
            return [], []

        df = pd.DataFrame(klines_data[tf])
        supports, resistances = TechnicalIndicators.support_resistance(df["close"], 20)

        return supports, resistances

    def _generate_recommendations(self,
                                 timeframe_signals: Dict[str, TimeframeSignal],
                                 composite_signal: str,
                                 trend_alignment: bool) -> List[str]:
        """生成交易建议"""
        recommendations = []

        # 趋势对齐建议
        if not trend_alignment and composite_signal != "hold":
            recommendations.append("各时间框架趋势不一致,建议等待确认")

        # 信号强度建议
        if composite_signal != "hold":
            entry_tf = "15m" if "15m" in timeframe_signals else "5m"
            if entry_tf in timeframe_signals:
                entry_signal = timeframe_signals[entry_tf]
                if entry_signal.signal == composite_signal:
                    recommendations.append(
                        f"{entry_tf}时间框架已确认入场信号,可以考虑入场"
                    )
                else:
                    recommendations.append(
                        f"等待{entry_tf}时间框架确认入场时机"
                    )

        # RSI建议
        if "1h" in timeframe_signals:
            rsi = timeframe_signals["1h"].indicators.get("rsi", 50)
            if rsi > 70:
                recommendations.append("RSI超买,注意回调风险")
            elif rsi < 30:
                recommendations.append("RSI超卖,注意反弹机会")

        return recommendations

    def _generate_warnings(self,
                          timeframe_signals: Dict[str, TimeframeSignal],
                          trend_alignment: bool) -> List[str]:
        """生成警告"""
        warnings = []

        # ADX警告
        for tf, signal in timeframe_signals.items():
            adx = signal.indicators.get("adx", 0)
            if adx < 15:
                warnings.append(f"{tf}时间框架趋势不明确(ADX={adx:.1f})")

        # 趋势冲突警告
        if not trend_alignment:
            trends = {}
            for tf, signal in timeframe_signals.items():
                trends[tf] = signal.trend.value
            warnings.append(f"趋势冲突: {trends}")

        return warnings

    def _map_to_strength(self, margin: float) -> SignalStrength:
        """映射到信号强度"""
        if margin > 0.6:
            return SignalStrength.VERY_STRONG
        elif margin > 0.4:
            return SignalStrength.STRONG
        elif margin > 0.2:
            return SignalStrength.MODERATE
        else:
            return SignalStrength.WEAK

    def get_trend_summary(self, timeframe_signals: Dict[str, TimeframeSignal]) -> Dict:
        """获取趋势摘要"""
        summary = {
            "dominant_trend": "neutral",
            "trend_strength": "weak",
            "timeframe_details": {}
        }

        bullish_count = 0
        bearish_count = 0

        for tf, signal in timeframe_signals.items():
            trend = signal.trend
            trend_strength = signal.indicators.get("adx", 0)

            summary["timeframe_details"][tf] = {
                "trend": trend.value,
                "signal": signal.signal,
                "strength": signal.strength.value,
                "confidence": signal.confidence,
                "adx": trend_strength
            }

            if trend in [TrendDirection.UPTREND, TrendDirection.STRONG_UPTREND]:
                bullish_count += 1
            elif trend in [TrendDirection.DOWNTREND, TrendDirection.STRONG_DOWNTREND]:
                bearish_count += 1

        # 确定主导趋势
        total = len(timeframe_signals)
        if bullish_count > bearish_count and bullish_count > total * 0.6:
            summary["dominant_trend"] = "uptrend"
        elif bearish_count > bullish_count and bearish_count > total * 0.6:
            summary["dominant_trend"] = "downtrend"

        # 确定趋势强度
        avg_adx = np.mean([
            s.indicators.get("adx", 0)
            for s in timeframe_signals.values()
        ])
        if avg_adx > 30:
            summary["trend_strength"] = "strong"
        elif avg_adx > 20:
            summary["trend_strength"] = "moderate"
        else:
            summary["trend_strength"] = "weak"

        return summary


def create_multi_timeframe_analyzer(config: Dict = None) -> MultiTimeframeAnalyzer:
    """创建多时间框架分析器"""
    return MultiTimeframeAnalyzer(config)


if __name__ == "__main__":
    # 测试代码
    config = {
        "timeframes": {
            "trend": ["1d", "4h"],
            "entry": ["1h"],
            "timing": ["15m", "5m"]
        },
        "confirmation_threshold": 2,
        "trend_alignment_required": True
    }

    analyzer = MultiTimeframeAnalyzer(config)

    # 生成测试数据
    import random
    np.random.seed(42)

    def generate_klines(count, base_price):
        klines = []
        price = base_price
        for _ in range(count):
            high = price * (1 + random.uniform(-0.02, 0.02))
            low = price * (1 + random.uniform(-0.02, 0.02))
            close = price * (1 + random.uniform(-0.01, 0.01))
            klines.append({
                "open": price,
                "high": high,
                "low": low,
                "close": close,
                "volume": random.randint(100, 1000)
            })
            price = close
        return klines

    klines_data = {
        "1d": generate_klines(200, 40000),
        "4h": generate_klines(300, 40000),
        "1h": generate_klines(500, 40000),
        "15m": generate_klines(400, 40000),
        "5m": generate_klines(500, 40000)
    }

    result = analyzer.analyze("BTCUSDT", klines_data)

    print("\n多时间框架分析结果:")
    print(f"  综合信号: {result.composite_signal}")
    print(f"  信号强度: {result.composite_strength.value}")
    print(f"  综合置信度: {result.composite_confidence:.2%}")
    print(f"  趋势对齐: {result.trend_alignment}")
    print(f"  入场信号: {result.entry_signal}")
    print(f"  入场强度: {result.entry_strength.value}")
    print(f"  入场置信度: {result.entry_confidence:.2%}")

    print(f"\n各时间框架信号:")
    for tf, signal in result.timeframe_signals.items():
        print(f"  {tf}: {signal.signal} ({signal.trend.value}) - "
              f"强度{signal.strength.value}, 置信度{signal.confidence:.2%}")
        if signal.reasons:
            print(f"    原因: {', '.join(signal.reasons)}")

    print(f"\n支撑位: {result.support_levels}")
    print(f"阻力位: {result.resistance_levels}")

    if result.warnings:
        print(f"\n警告:")
        for warning in result.warnings:
            print(f"  {warning}")

    if result.recommendations:
        print(f"\n建议:")
        for rec in result.recommendations:
            print(f"  {rec}")
