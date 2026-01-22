# 动态指标系统
# 像人一样智能，指标不写死，根据市场情况动态调整

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class DynamicIndicator:
    """动态指标基类"""

    def __init__(self, config: Dict):
        self.config = config
        self.auto_tune = config.get("auto_tune", True)
        self.adaptation_rate = config.get("adaptation_rate", 0.1)
        self.min_period = config.get("min_period", 5)
        self.max_period = config.get("max_period", 100)

        self.current_params = {}
        self.performance_history = []

    def calculate(self, data: pd.Series, **kwargs) -> Dict:
        """计算指标"""
        raise NotImplementedError

    def adapt_parameters(self, performance: float):
        """根据性能调整参数"""
        if not self.auto_tune:
            return

        # 记录性能历史
        self.performance_history.append(performance)
        if len(self.performance_history) > 50:
            self.performance_history.pop(0)

        # 计算性能趋势
        if len(self.performance_history) >= 10:
            recent_avg = np.mean(self.performance_history[-10:])
            overall_avg = np.mean(self.performance_history)

            if recent_avg > overall_avg:
                # 性能提升，保持当前参数
                return
            else:
                # 性能下降，调整参数
                self._adjust_parameters_based_on_market()


class DynamicMA(DynamicIndicator):
    """动态移动平均线"""

    def __init__(self, config: Dict):
        super().__init__(config)
        self.short_period = config.get("short_period", 20)
        self.long_period = config.get("long_period", 50)
        self.ma_type = config.get("ma_type", "EMA")  # SMA, EMA, VWMA, HMA, TMA

        # 市场状态跟踪
        self.market_regime = "trending"  # trending, ranging, volatile
        self.volatility_window = 20

    def calculate(self, data: pd.Series, periods: Optional[List[int]] = None) -> Dict:
        """计算移动平均线"""
        if periods is None:
            periods = [self.short_period, self.long_period]

        result = {}

        for period in periods:
            ma_value = self._calculate_ma(data, period)
            result[f"MA{self.ma_type}_{period}"] = ma_value

        # 添加趋势信号
        result["trend"] = self._detect_trend(data)
        result["market_regime"] = self._detect_market_regime(data)

        return result

    def _calculate_ma(self, data: pd.Series, period: int) -> float:
        """根据类型计算MA"""
        if self.ma_type == "SMA":
            return data.rolling(window=period).mean().iloc[-1]
        elif self.ma_type == "EMA":
            return data.ewm(span=period, adjust=False).mean().iloc[-1]
        elif self.ma_type == "VWMA":
            # 成交量加权移动平均（需要成交量数据）
            if len(data.shape) == 2 and 'volume' in data.columns:
                return (data['close'] * data['volume']).rolling(period).sum() / data['volume'].rolling(period).sum()
            return data.rolling(window=period).mean().iloc[-1]
        elif self.ma_type == "HMA":
            # Hull移动平均
            half = int(period / 2)
            wma_half = self._wma(data, half)
            wma_full = self._wma(data, period)
            return self._wma(2 * wma_half - wma_full, int(np.sqrt(period)))
        elif self.ma_type == "TMA":
            # 三角移动平均
            return data.rolling(window=period).mean().rolling(window=int(period/2)).mean().iloc[-1]
        else:
            return data.rolling(window=period).mean().iloc[-1]

    def _wma(self, data: pd.Series, period: int) -> float:
        """加权移动平均"""
        weights = np.arange(1, period + 1)
        return (data.tail(period) * weights).sum() / weights.sum()

    def _detect_trend(self, data: pd.Series) -> str:
        """检测趋势"""
        if len(data) < self.long_period:
            return "neutral"

        short_ma = self._calculate_ma(data, self.short_period)
        long_ma = self._calculate_ma(data, self.long_period)

        if short_ma > long_ma:
            slope = (short_ma - self._calculate_ma(data, self.long_period + 5))
            if slope > 0:
                return "bullish"
        else:
            slope = (long_ma - short_ma)
            if slope > 0:
                return "bearish"

        return "neutral"

    def _detect_market_regime(self, data: pd.Series) -> str:
        """检测市场状态"""
        if len(data) < self.volatility_window:
            return "unknown"

        # 计算波动率
        returns = data.pct_change().dropna()
        volatility = returns.tail(self.volatility_window).std()

        # 计算价格范围
        price_range = (data.max() - data.min()) / data.mean()

        # 根据波动率和范围判断
        if volatility > 0.02:  # 2%以上的波动率
            return "volatile"
        elif price_range < 0.01:  # 1%以内的范围
            return "ranging"
        else:
            return "trending"

    def _adjust_parameters_based_on_market(self):
        """根据市场状态调整参数"""
        if self.market_regime == "volatile":
            # 高波动市场：缩短周期
            self.short_period = max(self.min_period, int(self.short_period * 0.8))
            self.long_period = max(self.short_period * 2, int(self.long_period * 0.9))
        elif self.market_regime == "ranging":
            # 震荡市场：延长周期
            self.short_period = min(self.max_period // 3, int(self.short_period * 1.2))
            self.long_period = min(self.max_period, int(self.long_period * 1.1))
        else:
            # 趋势市场：保持标准比例
            pass

        logger.debug(f"MA参数已调整: short={self.short_period}, long={self.long_period}")


class DynamicRSI(DynamicIndicator):
    """动态RSI"""

    def __init__(self, config: Dict):
        super().__init__(config)
        self.period = config.get("period", 14)
        self.overbought = config.get("overbought", 70)
        self.oversold = config.get("oversold", 30)

    def calculate(self, data: pd.Series, period: Optional[int] = None) -> Dict:
        """计算动态RSI"""
        if period is None:
            period = self.period

        # 计算标准RSI
        delta = data.diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)

        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        rsi_value = rsi.iloc[-1]

        # 动态调整超买超卖阈值
        dynamic_ob, dynamic_os = self._dynamic_thresholds(rsi.tail(period * 2))

        result = {
            "RSI": rsi_value,
            "overbought": dynamic_ob,
            "oversold": dynamic_os,
            "signal": self._generate_signal(rsi_value, dynamic_ob, dynamic_os)
        }

        return result

    def _dynamic_thresholds(self, rsi_series: pd.Series) -> Tuple[float, float]:
        """动态计算超买超卖阈值"""
        rsi_values = rsi_series.dropna()

        if len(rsi_values) < period := 10:
            return self.overbought, self.oversold

        # 根据RSI分布动态调整
        p75 = np.percentile(rsi_values, 75)
        p25 = np.percentile(rsi_values, 25)

        # 如果市场波动大，扩展阈值
        if rsi_values.std() > 15:
            return min(p75 + 5, 80), max(p25 - 5, 20)
        else:
            # 收缩阈值
            return max(p75 - 5, 65), min(p25 + 5, 35)


class DynamicBollingerBands(DynamicIndicator):
    """动态布林带"""

    def __init__(self, config: Dict):
        super().__init__(config)
        self.period = config.get("period", 20)
        self.std_multiplier = config.get("std_multiplier", 2.0)

    def calculate(self, data: pd.Series,
                period: Optional[int] = None,
                std_multiplier: Optional[float] = None) -> Dict:
        """计算动态布林带"""
        if period is None:
            period = self.period
        if std_multiplier is None:
            std_multiplier = self.std_multiplier

        # 动态调整周期
        volatility = data.pct_change().tail(period).std()
        dynamic_period = int(period * (1 / (1 + volatility * 10)))
        dynamic_period = max(self.min_period, min(self.max_period, dynamic_period))

        # 计算布林带
        ma = data.rolling(window=dynamic_period).mean()
        std = data.rolling(window=dynamic_period).std()

        upper = ma + std_multiplier * std
        lower = ma - std_multiplier * std

        current_ma = ma.iloc[-1]
        current_upper = upper.iloc[-1]
        current_lower = lower.iloc[-1]
        current_price = data.iloc[-1]

        # 动态调整标准差倍数
        position = (current_price - current_lower) / (current_upper - current_lower)
        dynamic_std = self._adjust_std_multiplier(position, volatility)

        result = {
            "middle": current_ma,
            "upper": current_upper,
            "lower": current_lower,
            "bandwidth": (current_upper - current_lower) / current_ma * 100,
            "position": position,
            "dynamic_std_multiplier": dynamic_std,
            "squeeze": (current_upper - current_lower) / current_ma < 0.01  # 布林带收缩
        }

        return result

    def _adjust_std_multiplier(self, position: float, volatility: float) -> float:
        """动态调整标准差倍数"""
        # 高波动时扩大带宽
        if volatility > 0.02:
            return self.std_multiplier * 1.5
        # 价格接近边界时也扩大
        elif position > 0.9 or position < 0.1:
            return self.std_multiplier * 1.2
        else:
            return self.std_multiplier


class DynamicMACD(DynamicIndicator):
    """动态MACD"""

    def __init__(self, config: Dict):
        super().__init__(config)
        self.fast_period = config.get("fast_period", 12)
        self.slow_period = config.get("slow_period", 26)
        self.signal_period = config.get("signal_period", 9)

    def calculate(self, data: pd.Series,
                fast_period: Optional[int] = None,
                slow_period: Optional[int] = None) -> Dict:
        """计算动态MACD"""
        if fast_period is None:
            fast_period = self.fast_period
        if slow_period is None:
            slow_period = self.slow_period

        # 动态调整周期
        trend_strength = self._calculate_trend_strength(data)

        if trend_strength > 0.8:
            # 强趋势：加快信号
            fast_period = max(5, int(fast_period * 0.8))
            slow_period = max(fast_period + 5, int(slow_period * 0.9))
        elif trend_strength < 0.3:
            # 弱趋势：减慢信号
            fast_period = min(20, int(fast_period * 1.2))
            slow_period = min(40, int(slow_period * 1.1))

        # 计算EMA
        ema_fast = data.ewm(span=fast_period, adjust=False).mean()
        ema_slow = data.ewm(span=slow_period, adjust=False).mean()

        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=self.signal_period, adjust=False).mean()
        histogram = macd_line - signal_line

        result = {
            "MACD": macd_line.iloc[-1],
            "signal": signal_line.iloc[-1],
            "histogram": histogram.iloc[-1],
            "crossover": self._detect_crossover(histogram),
            "trend_strength": trend_strength,
            "dynamic_fast_period": fast_period,
            "dynamic_slow_period": slow_period
        }

        return result

    def _calculate_trend_strength(self, data: pd.Series) -> float:
        """计算趋势强度"""
        # 使用ADX类似的计算
        high = data
        low = data
        close = data

        # 简化版本：使用价格与MA的偏离
        ma50 = data.rolling(window=50).mean()
        deviation = abs(data - ma50) / ma50

        # 趋势强度为偏离度的平均值
        return min(deviation.tail(20).mean() * 100, 1.0)

    def _detect_crossover(self, histogram: pd.Series) -> str:
        """检测交叉"""
        if len(histogram) < 2:
            return "none"

        prev_hist = histogram.iloc[-2]
        curr_hist = histogram.iloc[-1]

        if prev_hist < 0 and curr_hist > 0:
            return "bullish"
        elif prev_hist > 0 and curr_hist < 0:
            return "bearish"
        else:
            return "none"


class DynamicATR(DynamicIndicator):
    """动态ATR"""

    def __init__(self, config: Dict):
        super().__init__(config)
        self.period = config.get("period", 14)
        self.multiplier = config.get("multiplier", 1.5)

    def calculate(self, data: pd.DataFrame,
                period: Optional[int] = None) -> Dict:
        """计算动态ATR"""
        if period is None:
            period = self.period

        high = data['high'] if 'high' in data.columns else data
        low = data['low'] if 'low' in data.columns else data
        close = data['close'] if 'close' in data.columns else data

        # 计算真实波幅
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())

        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        # 计算ATR
        atr = tr.rolling(window=period).mean()

        current_atr = atr.iloc[-1]

        # 动态调整倍数
        atr_ratio = atr.tail(period).std() / atr.tail(period).mean()
        dynamic_multiplier = self.multiplier * (1 + atr_ratio)

        result = {
            "ATR": current_atr,
            "ATR_percent": current_atr / close.iloc[-1] * 100 if close.iloc[-1] > 0 else 0,
            "dynamic_multiplier": dynamic_multiplier,
            "volatility_state": self._classify_volatility(atr_ratio)
        }

        return result

    def _classify_volatility(self, ratio: float) -> str:
        """分类波动状态"""
        if ratio < 0.3:
            return "low"
        elif ratio < 0.6:
            return "normal"
        else:
            return "high"


class DynamicVolume(DynamicIndicator):
    """动态成交量指标"""

    def __init__(self, config: Dict):
        super().__init__(config)
        self.period = config.get("period", 20)

    def calculate(self, volume: pd.Series, price: pd.Series) -> Dict:
        """计算动态成交量指标"""
        if len(volume) < self.period:
            return {"volume_ratio": 1.0, "volume_trend": "neutral"}

        # 成交量移动平均
        vol_ma = volume.rolling(window=self.period).mean()

        # 成交量比率
        vol_ratio = volume.iloc[-1] / vol_ma.iloc[-1]

        # OBV (能量潮)
        obv = (np.sign(price.diff()) * volume).cumsum()
        obv_ma = obv.rolling(window=self.period).mean()

        # 价量关系
        price_change = price.pct_change().iloc[-1]
        vol_change = (volume.iloc[-1] - volume.iloc[-2]) / volume.iloc[-2]

        # 判断价量关系
        if price_change > 0 and vol_change > 0:
            pv_relation = "confirming"
        elif price_change > 0 and vol_change < 0:
            pv_relation = "diverging_up"
        elif price_change < 0 and vol_change > 0:
            pv_relation = "diverging_down"
        else:
            pv_relation = "confirming"

        result = {
            "current_volume": volume.iloc[-1],
            "avg_volume": vol_ma.iloc[-1],
            "volume_ratio": vol_ratio,
            "volume_spike": vol_ratio > 2.0,
            "obv": obv.iloc[-1],
            "obv_trend": "up" if obv.iloc[-1] > obv_ma.iloc[-1] else "down",
            "price_volume_relation": pv_relation
        }

        return result


class DynamicIndicatorSystem:
    """动态指标系统 - 整合所有动态指标"""

    def __init__(self, config: Dict):
        self.config = config
        self.indicators = {}
        self.auto_optimize = config.get("auto_optimize", True)

        self._init_indicators()

    def _init_indicators(self):
        """初始化所有指标"""
        indicator_configs = self.config.get("indicators", {})

        # 移动平均线
        if indicator_configs.get("ma", {}).get("enabled", True):
            self.indicators["MA"] = DynamicMA(indicator_configs["ma"])

        # RSI
        if indicator_configs.get("rsi", {}).get("enabled", True):
            self.indicators["RSI"] = DynamicRSI(indicator_configs["rsi"])

        # 布林带
        if indicator_configs.get("bollinger", {}).get("enabled", True):
            self.indicators["BB"] = DynamicBollingerBands(indicator_configs["bollinger"])

        # MACD
        if indicator_configs.get("macd", {}).get("enabled", True):
            self.indicators["MACD"] = DynamicMACD(indicator_configs["macd"])

        # ATR
        if indicator_configs.get("atr", {}).get("enabled", True):
            self.indicators["ATR"] = DynamicATR(indicator_configs["atr"])

        # 成交量
        if indicator_configs.get("volume", {}).get("enabled", True):
            self.indicators["Volume"] = DynamicVolume(indicator_configs["volume"])

    def calculate_all(self, data: pd.DataFrame) -> Dict:
        """计算所有指标"""
        result = {
            "timestamp": datetime.now().isoformat(),
            "indicators": {}
        }

        close = data['close'] if 'close' in data.columns else data.iloc[:, 0]

        # 计算每个指标
        if "MA" in self.indicators:
            result["indicators"]["MA"] = self.indicators["MA"].calculate(close)

        if "RSI" in self.indicators:
            result["indicators"]["RSI"] = self.indicators["RSI"].calculate(close)

        if "BB" in self.indicators:
            result["indicators"]["BB"] = self.indicators["BB"].calculate(close)

        if "MACD" in self.indicators:
            result["indicators"]["MACD"] = self.indicators["MACD"].calculate(close)

        if "ATR" in self.indicators:
            result["indicators"]["ATR"] = self.indicators["ATR"].calculate(data)

        if "Volume" in self.indicators:
            volume = data['volume'] if 'volume' in data.columns else pd.Series([10000] * len(data))
            result["indicators"]["Volume"] = self.indicators["Volume"].calculate(volume, close)

        # 计算综合信号
        result["composite_signal"] = self._generate_composite_signal(
            result["indicators"]
        )

        # 市场状态
        result["market_state"] = self._assess_market_state(result["indicators"])

        return result

    def _generate_composite_signal(self, indicators: Dict) -> Dict:
        """生成综合信号"""
        bullish_signals = 0
        bearish_signals = 0
        confidence = 0.0

        # MA信号
        if "MA" in indicators:
            trend = indicators["MA"].get("trend", "neutral")
            if trend == "bullish":
                bullish_signals += 1
            elif trend == "bearish":
                bearish_signals += 1

        # RSI信号
        if "RSI" in indicators:
            signal = indicators["RSI"].get("signal", "hold")
            if signal == "buy":
                bullish_signals += 1
            elif signal == "sell":
                bearish_signals += 1

        # MACD信号
        if "MACD" in indicators:
            crossover = indicators["MACD"].get("crossover", "none")
            if crossover == "bullish":
                bullish_signals += 2  # MACD交叉权重更高
            elif crossover == "bearish":
                bearish_signals += 2

        # 布林带信号
        if "BB" in indicators:
            position = indicators["BB"].get("position", 0.5)
            if position < 0.2:  # 接近下轨
                bullish_signals += 1
            elif position > 0.8:  # 接近上轨
                bearish_signals += 1

        # 生成最终信号
        total = bullish_signals + bearish_signals

        if total == 0:
            action = "hold"
            confidence = 0.5
        elif bullish_signals > bearish_signals:
            action = "buy"
            confidence = bullish_signals / total
        else:
            action = "sell"
            confidence = bearish_signals / total

        return {
            "action": action,
            "confidence": confidence,
            "bullish_count": bullish_signals,
            "bearish_count": bearish_signals
        }

    def _assess_market_state(self, indicators: Dict) -> Dict:
        """评估市场状态"""
        state = {
            "regime": "neutral",
            "volatility": "normal",
            "strength": 0.5
        }

        # 从MA获取市场状态
        if "MA" in indicators:
            state["regime"] = indicators["MA"].get("market_regime", "neutral")

        # 从ATR获取波动率
        if "ATR" in indicators:
            state["volatility"] = indicators["ATR"].get("volatility_state", "normal")

        # 从MACD获取趋势强度
        if "MACD" in indicators:
            state["strength"] = indicators["MACD"].get("trend_strength", 0.5)

        return state

    def optimize_parameters(self, performance_feedback: Dict):
        """优化参数"""
        if not self.auto_optimize:
            return

        # 根据反馈调整各个指标的参数
        for name, indicator in self.indicators.items():
            feedback = performance_feedback.get(name, 0.5)
            indicator.adapt_parameters(feedback)

    def get_current_parameters(self) -> Dict:
        """获取当前参数"""
        params = {}
        for name, indicator in self.indicators.items():
            if hasattr(indicator, 'short_period'):
                params[name] = {
                    "type": indicator.__class__.__name__,
                    "params": {
                        "short_period": indicator.short_period,
                        "long_period": indicator.long_period
                    }
                }
        return params


def create_dynamic_indicator_system(config: Dict) -> DynamicIndicatorSystem:
    """创建动态指标系统"""
    return DynamicIndicatorSystem(config)


if __name__ == "__main__":
    # 测试代码
    config = {
        "auto_optimize": True,
        "indicators": {
            "ma": {"enabled": True, "auto_tune": True, "short_period": 20, "long_period": 50},
            "rsi": {"enabled": True, "auto_tune": True, "period": 14},
            "bollinger": {"enabled": True, "auto_tune": True, "period": 20},
            "macd": {"enabled": True, "auto_tune": True},
            "atr": {"enabled": True, "auto_tune": True},
            "volume": {"enabled": True}
        }
    }

    system = DynamicIndicatorSystem(config)

    # 生成测试数据
    np.random.seed(42)
    n_points = 200
    price = 2000 + np.cumsum(np.random.randn(n_points) * 10)
    volume = 10000 + np.random.rand(n_points) * 5000

    data = pd.DataFrame({
        "open": price,
        "high": price + np.random.rand(n_points) * 20,
        "low": price - np.random.rand(n_points) * 20,
        "close": price + np.random.randn(n_points) * 5,
        "volume": volume
    })

    # 计算指标
    results = system.calculate_all(data)

    print("\n动态指标系统结果:")
    print(f"综合信号: {results['composite_signal']}")
    print(f"市场状态: {results['market_state']}")
    print(f"\n各指标详情:")
    for name, value in results['indicators'].items():
        print(f"\n{name}:")
        for k, v in value.items():
            print(f"  {k}: {v}")
