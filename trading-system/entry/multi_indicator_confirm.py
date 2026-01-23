# 多指标入场确认模块
# 要求至少3个技术指标同时给出同向信号才入场
# 例如：MA排列 + MACD金叉 + RSI<70

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import logging
import pandas as pd

logger = logging.getLogger(__name__)


class SignalType(Enum):
    """信号类型"""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


class IndicatorType(Enum):
    """指标类型"""
    MA_ALIGNMENT = "ma_alignment"           # MA排列
    MACD = "macd"                         # MACD
    RSI = "rsi"                           # RSI
    BOLLINGER_BANDS = "bollinger_bands"    # 布林带
    ADX = "adx"                           # ADX趋势强度
    VOLUME = "volume"                      # 成交量
    STOCHASTIC = "stochastic"             # KDJ


@dataclass
class IndicatorSignal:
    """单个指标信号"""
    indicator: IndicatorType
    signal: SignalType
    confidence: float              # 置信度 0-1
    value: float                 # 指标值
    reason: str


@dataclass
class ConfirmationResult:
    """确认结果"""
    overall_signal: SignalType
    confidence: float
    buy_count: int
    sell_count: int
    hold_count: int
    total_indicators: int
    consensus_reached: bool        # 是否达到共识
    indicator_signals: List[IndicatorSignal]
    reason: str


class MultiIndicatorConfirm:
    """多指标入场确认"""

    def __init__(self, config: Dict = None):
        self.config = config or {}

        # 启用的指标
        self.enabled_indicators = self.config.get("enabled_indicators", [
            IndicatorType.MA_ALIGNMENT,
            IndicatorType.MACD,
            IndicatorType.RSI,
            IndicatorType.BOLLINGER_BANDS,
            IndicatorType.ADX
        ])

        # 确认要求
        self.min_confirmations = self.config.get("min_confirmations", 3)
        self.consensus_threshold = self.config.get("consensus_threshold", 0.6)

        # 各指标权重
        self.indicator_weights = self.config.get("indicator_weights", {
            IndicatorType.MA_ALIGNMENT: 1.5,
            IndicatorType.MACD: 1.3,
            IndicatorType.RSI: 1.0,
            IndicatorType.BOLLINGER_BANDS: 0.8,
            IndicatorType.ADX: 1.0
        })

        # 指标阈值配置
        self.rsi_overbought = self.config.get("rsi_overbought", 70)
        self.rsi_oversold = self.config.get("rsi_oversold", 30)
        self.adx_strong_trend = self.config.get("adx_strong_trend", 25)
        self.bb_std = self.config.get("bb_std", 2.0)
        self.bb_period = self.config.get("bb_period", 20)

        # MA周期
        self.ma_periods = self.config.get("ma_periods", {
            "fast": 7,
            "medium": 25,
            "slow": 50,
            "long": 200
        })

    def calculate_ma(self, prices: List[float], period: int) -> float:
        """计算移动平均"""
        if len(prices) < period:
            return prices[-1] if prices else 0
        return sum(prices[-period:]) / period

    def calculate_rsi(self, prices: List[float], period: int = 14) -> float:
        """计算RSI"""
        if len(prices) < period + 1:
            return 50.0

        gains = []
        losses = []

        for i in range(1, len(prices)):
            change = prices[i] - prices[i - 1]
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))

        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return rsi

    def calculate_macd(self, prices: List[float]) -> Dict[str, float]:
        """计算MACD"""
        if len(prices) < 26:
            return {"macd": 0, "signal": 0, "histogram": 0}

        df = pd.DataFrame({'close': prices})
        ema_fast = df['close'].ewm(span=12, adjust=False).mean()
        ema_slow = df['close'].ewm(span=26, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        histogram = macd_line - signal_line

        return {
            "macd": macd_line.iloc[-1],
            "signal": signal_line.iloc[-1],
            "histogram": histogram.iloc[-1],
            "histogram_prev": histogram.iloc[-2] if len(histogram) > 1 else 0
        }

    def calculate_bollinger_bands(self, prices: List[float]) -> Dict[str, float]:
        """计算布林带"""
        if len(prices) < self.bb_period:
            current_price = prices[-1] if prices else 0
            return {"upper": current_price, "middle": current_price, "lower": current_price}

        df = pd.DataFrame({'close': prices})
        middle = df['close'].rolling(window=self.bb_period).mean()
        std = df['close'].rolling(window=self.bb_period).std()

        return {
            "upper": middle.iloc[-1] + self.bb_std * std.iloc[-1],
            "middle": middle.iloc[-1],
            "lower": middle.iloc[-1] - self.bb_std * std.iloc[-1]
        }

    def calculate_adx(self, highs: List[float], lows: List[float],
                     closes: List[float], period: int = 14) -> float:
        """计算ADX"""
        if len(closes) < period + 1:
            return 0.0

        df = pd.DataFrame({
            'high': highs,
            'low': lows,
            'close': closes
        })

        prev_high = df['high'].shift(1)
        prev_low = df['low'].shift(1)
        prev_close = df['close'].shift(1)

        up_move = df['high'] - prev_high
        down_move = prev_low - df['low']

        plus_dm = pd.Series([0] * len(df))
        minus_dm = pd.Series([0] * len(df))

        for i in range(1, len(df)):
            if up_move[i] > down_move[i] and up_move[i] > 0:
                plus_dm[i] = up_move[i]
            if down_move[i] > up_move[i] and down_move[i] > 0:
                minus_dm[i] = down_move[i]

        tr1 = df['high'] - df['low']
        tr2 = abs(df['high'] - prev_close)
        tr3 = abs(df['low'] - prev_close)
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        smoothed_tr = tr.rolling(window=period).mean()
        smoothed_plus_dm = plus_dm.rolling(window=period).mean()
        smoothed_minus_dm = minus_dm.rolling(window=period).mean()

        plus_di = 100 * smoothed_plus_dm / smoothed_tr
        minus_di = 100 * smoothed_minus_dm / smoothed_tr

        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.rolling(window=period).mean()

        return adx.iloc[-1]

    def check_ma_alignment(self, prices: List[float], current_price: float) -> IndicatorSignal:
        """检查MA排列"""
        fast_ma = self.calculate_ma(prices, self.ma_periods["fast"])
        medium_ma = self.calculate_ma(prices, self.ma_periods["medium"])
        slow_ma = self.calculate_ma(prices, self.ma_periods["slow"])
        long_ma = self.calculate_ma(prices, self.ma_periods["long"])

        # 检查多头排列
        bullish = fast_ma > medium_ma > slow_ma > long_ma
        bearish = fast_ma < medium_ma < slow_ma < long_ma

        if bullish and current_price > medium_ma:
            return IndicatorSignal(
                indicator=IndicatorType.MA_ALIGNMENT,
                signal=SignalType.BUY,
                confidence=0.85,
                value=current_price,
                reason=f"MA多头排列 (快={fast_ma:.2f} > 中={medium_ma:.2f} > 慢={slow_ma:.2f})"
            )
        elif bearish and current_price < medium_ma:
            return IndicatorSignal(
                indicator=IndicatorType.MA_ALIGNMENT,
                signal=SignalType.SELL,
                confidence=0.85,
                value=current_price,
                reason=f"MA空头排列 (快={fast_ma:.2f} < 中={medium_ma:.2f} < 慢={slow_ma:.2f})"
            )
        elif bullish:
            return IndicatorSignal(
                indicator=IndicatorType.MA_ALIGNMENT,
                signal=SignalType.BUY,
                confidence=0.60,
                value=current_price,
                reason=f"MA多头排列但价格低于中均线"
            )
        elif bearish:
            return IndicatorSignal(
                indicator=IndicatorType.MA_ALIGNMENT,
                signal=SignalType.SELL,
                confidence=0.60,
                value=current_price,
                reason=f"MA空头排列但价格高于中均线"
            )
        else:
            return IndicatorSignal(
                indicator=IndicatorType.MA_ALIGNMENT,
                signal=SignalType.HOLD,
                confidence=0.30,
                value=current_price,
                reason="MA排列混乱"
            )

    def check_macd(self, prices: List[float]) -> IndicatorSignal:
        """检查MACD"""
        macd_data = self.calculate_macd(prices)
        macd = macd_data["macd"]
        signal = macd_data["signal"]
        histogram = macd_data["histogram"]
        histogram_prev = macd_data["histogram_prev"]

        # MACD金叉
        if histogram > 0 and histogram_prev <= 0:
            return IndicatorSignal(
                indicator=IndicatorType.MACD,
                signal=SignalType.BUY,
                confidence=0.80,
                value=histogram,
                reason=f"MACD金叉 (MACD={macd:.2f}, 信号={signal:.2f})"
            )
        # MACD死叉
        elif histogram < 0 and histogram_prev >= 0:
            return IndicatorSignal(
                indicator=IndicatorType.MACD,
                signal=SignalType.SELL,
                confidence=0.80,
                value=histogram,
                reason=f"MACD死叉 (MACD={macd:.2f}, 信号={signal:.2f})"
            )
        # MACD在零轴上方
        elif histogram > 0:
            return IndicatorSignal(
                indicator=IndicatorType.MACD,
                signal=SignalType.BUY,
                confidence=0.55,
                value=histogram,
                reason=f"MACD在零轴上方 (柱={histogram:.2f})"
            )
        # MACD在零轴下方
        elif histogram < 0:
            return IndicatorSignal(
                indicator=IndicatorType.MACD,
                signal=SignalType.SELL,
                confidence=0.55,
                value=histogram,
                reason=f"MACD在零轴下方 (柱={histogram:.2f})"
            )
        else:
            return IndicatorSignal(
                indicator=IndicatorType.MACD,
                signal=SignalType.HOLD,
                confidence=0.30,
                value=0,
                reason="MACD无明确方向"
            )

    def check_rsi(self, prices: List[float], current_price: float) -> IndicatorSignal:
        """检查RSI"""
        rsi = self.calculate_rsi(prices)

        if rsi < self.rsi_oversold:
            return IndicatorSignal(
                indicator=IndicatorType.RSI,
                signal=SignalType.BUY,
                confidence=0.75,
                value=rsi,
                reason=f"RSI超卖 ({rsi:.1f} < {self.rsi_oversold})"
            )
        elif rsi < 50:
            return IndicatorSignal(
                indicator=IndicatorType.RSI,
                signal=SignalType.BUY,
                confidence=0.60,
                value=rsi,
                reason=f"RSI在超卖区域 ({rsi:.1f})"
            )
        elif rsi > self.rsi_overbought:
            return IndicatorSignal(
                indicator=IndicatorType.RSI,
                signal=SignalType.SELL,
                confidence=0.75,
                value=rsi,
                reason=f"RSI超买 ({rsi:.1f} > {self.rsi_overbought})"
            )
        elif rsi > 50:
            return IndicatorSignal(
                indicator=IndicatorType.RSI,
                signal=SignalType.SELL,
                confidence=0.60,
                value=rsi,
                reason=f"RSI在超买区域 ({rsi:.1f})"
            )
        else:
            return IndicatorSignal(
                indicator=IndicatorType.RSI,
                signal=SignalType.HOLD,
                confidence=0.40,
                value=rsi,
                reason=f"RSI中性 ({rsi:.1f})"
            )

    def check_bollinger_bands(self, prices: List[float], current_price: float) -> IndicatorSignal:
        """检查布林带"""
        bb = self.calculate_bollinger_bands(prices)

        if current_price < bb["lower"]:
            return IndicatorSignal(
                indicator=IndicatorType.BOLLINGER_BANDS,
                signal=SignalType.BUY,
                confidence=0.70,
                value=current_price,
                reason=f"价格触及下轨 ({current_price:.2f} < {bb['lower']:.2f})"
            )
        elif current_price > bb["upper"]:
            return IndicatorSignal(
                indicator=IndicatorType.BOLLINGER_BANDS,
                signal=SignalType.SELL,
                confidence=0.70,
                value=current_price,
                reason=f"价格触及上轨 ({current_price:.2f} > {bb['upper']:.2f})"
            )
        elif current_price < bb["middle"]:
            return IndicatorSignal(
                indicator=IndicatorType.BOLLINGER_BANDS,
                signal=SignalType.BUY,
                confidence=0.50,
                value=current_price,
                reason=f"价格在下轨与中轨之间"
            )
        elif current_price > bb["middle"]:
            return IndicatorSignal(
                indicator=IndicatorType.BOLLINGER_BANDS,
                signal=SignalType.SELL,
                confidence=0.50,
                value=current_price,
                reason=f"价格在中轨与上轨之间"
            )
        else:
            return IndicatorSignal(
                indicator=IndicatorType.BOLLINGER_BANDS,
                signal=SignalType.HOLD,
                confidence=0.30,
                value=current_price,
                reason="价格在中轨附近"
            )

    def check_adx(self, highs: List[float], lows: List[float],
                  closes: List[float]) -> IndicatorSignal:
        """检查ADX趋势强度"""
        adx = self.calculate_adx(highs, lows, closes)

        if adx >= self.adx_strong_trend:
            # 检查方向
            plus_di = self.calculate_adx_direction(highs, lows, closes, "plus")
            minus_di = self.calculate_adx_direction(highs, lows, closes, "minus")

            if plus_di > minus_di:
                return IndicatorSignal(
                    indicator=IndicatorType.ADX,
                    signal=SignalType.BUY,
                    confidence=0.75,
                    value=adx,
                    reason=f"ADX强上升趋势 (ADX={adx:.1f}, +DI={plus_di:.1f} > -DI={minus_di:.1f})"
                )
            else:
                return IndicatorSignal(
                    indicator=IndicatorType.ADX,
                    signal=SignalType.SELL,
                    confidence=0.75,
                    value=adx,
                    reason=f"ADX强下降趋势 (ADX={adx:.1f}, +DI={plus_di:.1f} < -DI={minus_di:.1f})"
                )
        else:
            return IndicatorSignal(
                indicator=IndicatorType.ADX,
                signal=SignalType.HOLD,
                confidence=0.30,
                value=adx,
                reason=f"ADX趋势强度不足 (ADX={adx:.1f})"
            )

    def calculate_adx_direction(self, highs: List[float], lows: List[float],
                               closes: List[float], di_type: str) -> float:
        """计算DI方向"""
        period = 14
        if len(closes) < period + 1:
            return 0.0

        df = pd.DataFrame({
            'high': highs,
            'low': lows,
            'close': closes
        })

        prev_high = df['high'].shift(1)
        prev_low = df['low'].shift(1)

        up_move = df['high'] - prev_high
        down_move = prev_low - df['low']

        if di_type == "plus":
            dm = pd.Series([0] * len(df))
            for i in range(1, len(df)):
                if up_move[i] > down_move[i] and up_move[i] > 0:
                    dm[i] = up_move[i]
        else:
            dm = pd.Series([0] * len(df))
            for i in range(1, len(df)):
                if down_move[i] > up_move[i] and down_move[i] > 0:
                    dm[i] = down_move[i]

        tr1 = df['high'] - df['low']
        tr2 = abs(df['high'] - df['close'].shift(1))
        tr3 = abs(df['low'] - df['close'].shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        smoothed_dm = dm.rolling(window=period).mean()
        smoothed_tr = tr.rolling(window=period).mean()

        return (100 * smoothed_dm / smoothed_tr).iloc[-1]

    def confirm_entry(self, prices: List[float], highs: List[float],
                    lows: List[float], current_price: float,
                    signal_direction: str = None) -> ConfirmationResult:
        """
        确认入场信号

        参数:
            prices: 收盘价列表
            highs: 最高价列表
            lows: 最低价列表
            current_price: 当前价格
            signal_direction: 原始信号方向

        返回:
            ConfirmationResult
        """
        indicator_signals = []

        # 检查各指标
        if IndicatorType.MA_ALIGNMENT in self.enabled_indicators:
            indicator_signals.append(self.check_ma_alignment(prices, current_price))

        if IndicatorType.MACD in self.enabled_indicators:
            indicator_signals.append(self.check_macd(prices))

        if IndicatorType.RSI in self.enabled_indicators:
            indicator_signals.append(self.check_rsi(prices, current_price))

        if IndicatorType.BOLLINGER_BANDS in self.enabled_indicators:
            indicator_signals.append(self.check_bollinger_bands(prices, current_price))

        if IndicatorType.ADX in self.enabled_indicators:
            indicator_signals.append(self.check_adx(highs, lows, prices))

        # 统计信号
        buy_count = sum(1 for s in indicator_signals if s.signal == SignalType.BUY)
        sell_count = sum(1 for s in indicator_signals if s.signal == SignalType.SELL)
        hold_count = sum(1 for s in indicator_signals if s.signal == SignalType.HOLD)

        # 计算加权得分
        buy_score = sum(s.confidence * self.indicator_weights.get(s.indicator, 1.0)
                       for s in indicator_signals if s.signal == SignalType.BUY)
        sell_score = sum(s.confidence * self.indicator_weights.get(s.indicator, 1.0)
                        for s in indicator_signals if s.signal == SignalType.SELL)

        # 确定整体信号
        total_indicators = len(indicator_signals)
        consensus_reached = False

        if buy_score > sell_score and buy_score > 0:
            # 检查是否达到最小确认数
            if buy_count >= self.min_confirmations:
                consensus_reached = True
            overall_signal = SignalType.BUY
        elif sell_score > buy_score and sell_score > 0:
            if sell_count >= self.min_confirmations:
                consensus_reached = True
            overall_signal = SignalType.SELL
        else:
            overall_signal = SignalType.HOLD

        # 如果指定了信号方向，检查是否一致
        if signal_direction:
            if signal_direction == "buy" and overall_signal != SignalType.BUY:
                return ConfirmationResult(
                    overall_signal=SignalType.HOLD,
                    confidence=0.2,
                    buy_count=0,
                    sell_count=0,
                    hold_count=total_indicators,
                    total_indicators=total_indicators,
                    consensus_reached=False,
                    indicator_signals=indicator_signals,
                    reason="指标信号与期望方向不一致"
                )
            elif signal_direction == "sell" and overall_signal != SignalType.SELL:
                return ConfirmationResult(
                    overall_signal=SignalType.HOLD,
                    confidence=0.2,
                    buy_count=0,
                    sell_count=0,
                    hold_count=total_indicators,
                    total_indicators=total_indicators,
                    consensus_reached=False,
                    indicator_signals=indicator_signals,
                    reason="指标信号与期望方向不一致"
                )

        # 计算置信度
        if consensus_reached:
            max_score = max(buy_score, sell_score)
            confidence = min(0.9, max_score / sum(s.confidence * self.indicator_weights.get(s.indicator, 1.0)
                                                     for s in indicator_signals))
        else:
            confidence = 0.4

        # 生成原因
        if consensus_reached:
            active_signals = [s for s in indicator_signals
                           if s.signal == overall_signal and s.signal != SignalType.HOLD]
            reasons = [s.reason for s in active_signals]
            reason = f"{len(active_signals)}/{total_indicators}指标确认: {', '.join(reasons)}"
        else:
            reason = f"未达到确认阈值 (买入:{buy_count}, 卖出:{sell_count}, 持有:{hold_count})"

        return ConfirmationResult(
            overall_signal=overall_signal,
            confidence=confidence,
            buy_count=buy_count,
            sell_count=sell_count,
            hold_count=hold_count,
            total_indicators=total_indicators,
            consensus_reached=consensus_reached,
            indicator_signals=indicator_signals,
            reason=reason
        )

    def should_trade(self, prices: List[float], highs: List[float],
                    lows: List[float], current_price: float,
                    signal_direction: str) -> Tuple[bool, str, float]:
        """
        判断是否应该交易

        参数:
            prices: 收盘价列表
            highs: 最高价列表
            lows: 最低价列表
            current_price: 当前价格
            signal_direction: 信号方向

        返回:
            (should_trade: bool, reason: str, confidence: float)
        """
        result = self.confirm_entry(prices, highs, lows, current_price, signal_direction)
        return result.consensus_reached, result.reason, result.confidence


def create_multi_indicator_confirm(config: Dict = None) -> MultiIndicatorConfirm:
    """创建多指标确认器"""
    return MultiIndicatorConfirm(config)


if __name__ == "__main__":
    # 测试代码
    confirm = MultiIndicatorConfirm()

    print("\n=== 测试多指标入场确认 ===")

    # 生成测试数据
    import random
    import numpy as np

    random.seed(42)
    np.random.seed(42)

    def generate_klines(count, base_price, trend=0.002):
        """生成测试K线数据"""
        highs = []
        lows = []
        closes = []
        prices = []

        price = base_price
        for _ in range(count):
            change = base_price * (trend + random.uniform(-0.01, 0.01))
            price = max(price + change, base_price * 0.8)

            high = price * (1 + random.uniform(0, 0.01))
            low = price * (1 - random.uniform(0, 0.01))

            highs.append(high)
            lows.append(low)
            closes.append(price)
            prices.append(price)

        return prices, highs, lows

    # 测试上升趋势
    print("\n测试1: 上升趋势")
    prices, highs, lows = generate_klines(50, 40000, trend=0.002)
    current_price = prices[-1]
    result = confirm.confirm_entry(prices, highs, lows, current_price)
    print(f"  整体信号: {result.overall_signal.value}")
    print(f"  置信度: {result.confidence:.2%}")
    print(f"  买入指标: {result.buy_count}/{result.total_indicators}")
    print(f"  卖出指标: {result.sell_count}/{result.total_indicators}")
    print(f"  达到共识: {result.consensus_reached}")
    print(f"  原因: {result.reason}")

    print("\n各指标信号:")
    for signal in result.indicator_signals:
        icon = "↑" if signal.signal == SignalType.BUY else ("↓" if signal.signal == SignalType.SELL else "•")
        print(f"  {icon} {signal.indicator.value}: {signal.reason} (置信度={signal.confidence:.2%})")

    # 测试做多确认
    print("\n测试2: 做多信号确认")
    should_trade, reason, confidence = confirm.should_trade(
        prices, highs, lows, current_price, "buy"
    )
    print(f"  应该做多: {should_trade}")
    print(f"  置信度: {confidence:.2%}")
    print(f"  原因: {reason}")

    # 测试下降趋势
    print("\n测试3: 下降趋势")
    prices, highs, lows = generate_klines(50, 40000, trend=-0.002)
    current_price = prices[-1]
    result = confirm.confirm_entry(prices, highs, lows, current_price)
    print(f"  整体信号: {result.overall_signal.value}")
    print(f"  置信度: {result.confidence:.2%}")
    print(f"  买入指标: {result.buy_count}/{result.total_indicators}")
    print(f"  卖出指标: {result.sell_count}/{result.total_indicators}")
    print(f"  达到共识: {result.consensus_reached}")
    print(f"  原因: {result.reason}")
