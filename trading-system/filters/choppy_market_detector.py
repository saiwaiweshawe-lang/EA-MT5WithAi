# 无序震荡市场检测模块
# 当ADX<15时，市场处于无序震荡状态，暂停所有交易
# 检查多个时间框架的ADX，都不符合条件时才入场

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import logging
import pandas as pd

logger = logging.getLogger(__name__)


class MarketState(Enum):
    """市场状态"""
    STRONG_TREND = "strong_trend"      # 强趋势
    MODERATE_TREND = "moderate_trend"  # 中等趋势
    WEAK_TREND = "weak_trend"         # 弱趋势
    CHOPPY = "choppy"                 # 无序震荡
    QUIET = "quiet"                   # 平静


@dataclass
class MarketCondition:
    """市场条件"""
    state: MarketState
    adx_value: float
    plus_di: float
    minus_di: float
    timeframe: str
    tradeable: bool
    confidence: float
    reason: str


class ChoppyMarketDetector:
    """无序震荡市场检测器"""

    def __init__(self, config: Dict = None):
        self.config = config or {}

        # ADX参数
        self.adx_period = self.config.get("adx_period", 14)

        # ADX阈值
        self.adx_thresholds = self.config.get("adx_thresholds", {
            "strong_trend": 30,      # 强趋势
            "moderate_trend": 25,    # 中等趋势
            "weak_trend": 20,        # 弱趋势
            "choppy": 15,            # 无序震荡
            "quiet": 10              # 平静
        })

        # 多时间框架检查
        self.check_timeframes = self.config.get("check_timeframes", ["1h", "4h", "1d"])

        # 一致性要求（需要多少时间框架符合条件）
        self.consensus_required = self.config.get("consensus_required", 0.6)

        # 权重配置（高级时间框架权重更高）
        self.timeframe_weights = self.config.get("timeframe_weights", {
            "1d": 0.4,
            "4h": 0.35,
            "1h": 0.25
        })

    def calculate_adx(self, highs: List[float], lows: List[float],
                     closes: List[float]) -> Tuple[float, float, float]:
        """
        计算ADX指标

        参数:
            highs: 最高价列表
            lows: 最低价列表
            closes: 收盘价列表

        返回:
            (adx, plus_di, minus_di)
        """
        if len(closes) < self.adx_period + 1:
            return 0.0, 0.0, 0.0

        df = pd.DataFrame({
            'high': highs,
            'low': lows,
            'close': closes
        })

        # 计算价格变化
        prev_high = df['high'].shift(1)
        prev_low = df['low'].shift(1)
        prev_close = df['close'].shift(1)

        up_move = df['high'] - prev_high
        down_move = prev_low - df['low']

        # 计算DM (Directional Movement)
        plus_dm = pd.Series([0] * len(df))
        minus_dm = pd.Series([0] * len(df))

        for i in range(1, len(df)):
            if up_move[i] > down_move[i] and up_move[i] > 0:
                plus_dm[i] = up_move[i]
            if down_move[i] > up_move[i] and down_move[i] > 0:
                minus_dm[i] = down_move[i]

        # 计算TR (True Range)
        tr1 = df['high'] - df['low']
        tr2 = abs(df['high'] - prev_close)
        tr3 = abs(df['low'] - prev_close)
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        # 平滑TR和DM
        smoothed_tr = tr.rolling(window=self.adx_period).mean()
        smoothed_plus_dm = plus_dm.rolling(window=self.adx_period).mean()
        smoothed_minus_dm = minus_dm.rolling(window=self.adx_period).mean()

        # 计算DI (Directional Indicator)
        plus_di = 100 * smoothed_plus_dm / smoothed_tr
        minus_di = 100 * smoothed_minus_dm / smoothed_tr

        # 计算DX
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)

        # 计算ADX
        adx = dx.rolling(window=self.adx_period).mean()

        return adx.iloc[-1], plus_di.iloc[-1], minus_di.iloc[-1]

    def analyze_single_timeframe(self, highs: List[float], lows: List[float],
                              closes: List[float], timeframe: str) -> MarketCondition:
        """
        分析单个时间框架的市场条件

        参数:
            highs: 最高价列表
            lows: 最低价列表
            closes: 收盘价列表
            timeframe: 时间框架

        返回:
            MarketCondition
        """
        if len(closes) < self.adx_period + 1:
            return MarketCondition(
                state=MarketState.QUIET,
                adx_value=0.0,
                plus_di=0.0,
                minus_di=0.0,
                timeframe=timeframe,
                tradeable=False,
                confidence=0.0,
                reason="数据不足"
            )

        adx, plus_di, minus_di = self.calculate_adx(highs, lows, closes)

        # 确定市场状态
        thresholds = self.adx_thresholds
        if adx >= thresholds["strong_trend"]:
            state = MarketState.STRONG_TREND
            tradeable = True
            confidence = 0.9
            reason = f"强趋势 (ADX={adx:.1f})"
        elif adx >= thresholds["moderate_trend"]:
            state = MarketState.MODERATE_TREND
            tradeable = True
            confidence = 0.75
            reason = f"中等趋势 (ADX={adx:.1f})"
        elif adx >= thresholds["weak_trend"]:
            state = MarketState.WEAK_TREND
            tradeable = True
            confidence = 0.55
            reason = f"弱趋势 (ADX={adx:.1f})"
        elif adx >= thresholds["choppy"]:
            state = MarketState.CHOPPY
            tradeable = False
            confidence = 0.7
            reason = f"无序震荡 (ADX={adx:.1f})"
        else:
            state = MarketState.QUIET
            tradeable = False
            confidence = 0.8
            reason = f"市场平静 (ADX={adx:.1f})"

        return MarketCondition(
            state=state,
            adx_value=adx,
            plus_di=plus_di,
            minus_di=minus_di,
            timeframe=timeframe,
            tradeable=tradeable,
            confidence=confidence,
            reason=reason
        )

    def analyze_multi_timeframe(self, timeframe_data: Dict[str, Dict]) -> Dict:
        """
        分析多时间框架的市场条件

        参数:
            timeframe_data: 各时间框架的数据
                {"1h": {"highs": [...], "lows": [...], "closes": [...]}, ...}

        返回:
            综合分析结果
        """
        results = {}
        tradeable_count = 0
        total_weight = 0
        tradeable_weight = 0

        for tf in self.check_timeframes:
            if tf in timeframe_data:
                data = timeframe_data[tf]
                result = self.analyze_single_timeframe(
                    data["highs"], data["lows"], data["closes"], tf
                )
                results[tf] = result

                weight = self.timeframe_weights.get(tf, 0.1)
                total_weight += weight

                if result.tradeable:
                    tradeable_count += 1
                    tradeable_weight += weight

        # 计算总体可交易性
        overall_tradeable = False
        overall_reason = ""
        overall_state = MarketState.QUIET
        overall_confidence = 0.0

        if total_weight > 0:
            tradeable_pct = tradeable_weight / total_weight

            if tradeable_pct >= self.consensus_required:
                overall_tradeable = True

            # 确定总体状态
            strong_trend_count = sum(1 for r in results.values()
                                    if r.state == MarketState.STRONG_TREND)
            moderate_trend_count = sum(1 for r in results.values()
                                      if r.state == MarketState.MODERATE_TREND)
            choppy_count = sum(1 for r in results.values()
                              if r.state == MarketState.CHOPPY)

            if choppy_count >= len(results) * 0.5:
                overall_state = MarketState.CHOPPY
                overall_reason = "多时间框架均显示无序震荡"
                overall_confidence = 0.85
            elif strong_trend_count > 0:
                overall_state = MarketState.STRONG_TREND
                overall_reason = f"{strong_trend_count}个时间框架显示强趋势"
                overall_confidence = 0.8
            elif moderate_trend_count > 0:
                overall_state = MarketState.MODERATE_TREND
                overall_reason = f"{moderate_trend_count}个时间框架显示中等趋势"
                overall_confidence = 0.7
            else:
                overall_state = MarketState.WEAK_TREND
                overall_reason = "各时间框架趋势较弱"
                overall_confidence = 0.5

        return {
            "tradeable": overall_tradeable,
            "state": overall_state,
            "confidence": overall_confidence,
            "reason": overall_reason,
            "tradeable_pct": tradeable_weight / total_weight if total_weight > 0 else 0,
            "timeframe_results": results
        }

    def should_trade(self, highs: List[float], lows: List[float],
                   closes: List[float]) -> Tuple[bool, str, float]:
        """
        判断是否应该交易

        参数:
            highs: 最高价列表
            lows: 最低价列表
            closes: 收盘价列表

        返回:
            (should_trade: bool, reason: str, confidence: float)
        """
        condition = self.analyze_single_timeframe(highs, lows, closes, "1h")
        return condition.tradeable, condition.reason, condition.confidence

    def get_tradeable_timeframes(self, timeframe_data: Dict[str, Dict]) -> List[str]:
        """
        获取可交易的时间框架

        参数:
            timeframe_data: 各时间框架的数据

        返回:
            可交易的时间框架列表
        """
        tradeable_tfs = []
        for tf in self.check_timeframes:
            if tf in timeframe_data:
                data = timeframe_data[tf]
                condition = self.analyze_single_timeframe(
                    data["highs"], data["lows"], data["closes"], tf
                )
                if condition.tradeable:
                    tradeable_tfs.append(tf)
        return tradeable_tfs


def create_choppy_market_detector(config: Dict = None) -> ChoppyMarketDetector:
    """创建无序震荡市场检测器"""
    return ChoppyMarketDetector(config)


if __name__ == "__main__":
    # 测试代码
    detector = ChoppyMarketDetector()

    print("\n=== 测试无序震荡市场检测 ===")

    # 生成测试数据
    import random
    import numpy as np

    random.seed(42)
    np.random.seed(42)

    def generate_klines(count, base_price, trend=0):
        """生成测试K线数据"""
        highs = []
        lows = []
        closes = []

        price = base_price
        for _ in range(count):
            if trend > 0:
                # 趋势性数据
                change = base_price * trend
                noise = base_price * random.uniform(-0.005, 0.015)
            elif trend < 0:
                # 下降趋势
                change = base_price * trend
                noise = base_price * random.uniform(-0.015, 0.005)
            else:
                # 震荡数据
                change = base_price * random.uniform(-0.01, 0.01)
                noise = 0

            new_price = price + change + noise
            high = new_price * 1.005
            low = new_price * 0.995

            highs.append(high)
            lows.append(low)
            closes.append(new_price)
            price = new_price

        return highs, lows, closes

    # 测试1: 强趋势
    print("\n测试1: 强上升趋势")
    highs, lows, closes = generate_klines(50, 40000, trend=0.003)
    condition = detector.analyze_single_timeframe(highs, lows, closes, "1h")
    print(f"  状态: {condition.state.value}")
    print(f"  ADX: {condition.adx_value:.1f}")
    print(f"  可交易: {condition.tradeable}")
    print(f"  置信度: {condition.confidence:.2%}")
    print(f"  原因: {condition.reason}")

    # 测试2: 弱趋势
    print("\n测试2: 弱趋势")
    highs, lows, closes = generate_klines(50, 40000, trend=0.0005)
    condition = detector.analyze_single_timeframe(highs, lows, closes, "1h")
    print(f"  状态: {condition.state.value}")
    print(f"  ADX: {condition.adx_value:.1f}")
    print(f"  可交易: {condition.tradeable}")
    print(f"  置信度: {condition.confidence:.2%}")
    print(f"  原因: {condition.reason}")

    # 测试3: 无序震荡
    print("\n测试3: 无序震荡")
    highs, lows, closes = generate_klines(50, 40000, trend=0)
    condition = detector.analyze_single_timeframe(highs, lows, closes, "1h")
    print(f"  状态: {condition.state.value}")
    print(f"  ADX: {condition.adx_value:.1f}")
    print(f"  可交易: {condition.tradeable}")
    print(f"  置信度: {condition.confidence:.2%}")
    print(f"  原因: {condition.reason}")

    # 测试4: 多时间框架分析
    print("\n测试4: 多时间框架分析")
    timeframe_data = {
        "1h": {
            "highs": generate_klines(50, 40000, trend=0.003)[0],
            "lows": generate_klines(50, 40000, trend=0.003)[1],
            "closes": generate_klines(50, 40000, trend=0.003)[2]
        },
        "4h": {
            "highs": generate_klines(50, 40000, trend=0.002)[0],
            "lows": generate_klines(50, 40000, trend=0.002)[1],
            "closes": generate_klines(50, 40000, trend=0.002)[2]
        },
        "1d": {
            "highs": generate_klines(50, 40000, trend=0.001)[0],
            "lows": generate_klines(50, 40000, trend=0.001)[1],
            "closes": generate_klines(50, 40000, trend=0.001)[2]
        }
    }
    result = detector.analyze_multi_timeframe(timeframe_data)
    print(f"  可交易: {result['tradeable']}")
    print(f"  总体状态: {result['state'].value}")
    print(f"  可交易比例: {result['tradeable_pct']:.1%}")
    print(f"  原因: {result['reason']}")

    print("\n各时间框架详情:")
    for tf, cond in result['timeframe_results'].items():
        print(f"  {tf}: {cond.state.value} (ADX={cond.adx_value:.1f}, 可交易={cond.tradeable})")
