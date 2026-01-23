# 相关性风险控制模块
# 检测和管理多个品种之间的相关性风险

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class CorrelationLevel(Enum):
    """相关性级别"""
    VERY_HIGH = "very_high"      # 极高相关 >0.9
    HIGH = "high"                # 高相关 0.7-0.9
    MODERATE = "moderate"        # 中等相关 0.5-0.7
    LOW = "low"                  # 低相关 0.3-0.5
    VERY_LOW = "very_low"        # 极低相关 <0.3
    NONE = "none"                # 无相关
    NEGATIVE_HIGH = "neg_high"   # 高负相关 <-0.7


@dataclass
class CorrelationPair:
    """相关性配对"""
    symbol1: str
    symbol2: str
    correlation: float
    correlation_level: CorrelationLevel
    p_value: float = 0.0
    sample_size: int = 0
    last_updated: datetime = field(default_factory=datetime.now)


@dataclass
class ExposureSummary:
    """风险暴露摘要"""
    symbol: str
    position_type: str  # long/short/neutral
    exposure_amount: float
    exposure_pct: float
    correlated_exposure: float
    correlated_exposure_pct: float
    risk_level: str
    warnings: List[str] = field(default_factory=list)


@dataclass
class CorrelationRiskReport:
    """相关性风险报告"""
    timestamp: datetime
    total_positions: int
    total_exposure: float
    correlated_positions: List[str]
    correlation_matrix: Dict[str, Dict[str, float]]
    exposure_summaries: List[ExposureSummary]
    overall_risk_level: str
    recommendations: List[str]
    actions_required: List[str]


class CorrelationCalculator:
    """相关性计算器"""

    def __init__(self, min_samples: int = 30, max_history: int = 500):
        self.min_samples = min_samples
        self.max_history = max_history
        self.price_history: Dict[str, List[float]] = {}
        self.timestamp_history: Dict[str, List[datetime]] = {}

    def update_price(self, symbol: str, price: float, timestamp: datetime = None):
        """更新价格历史"""
        if timestamp is None:
            timestamp = datetime.now()

        if symbol not in self.price_history:
            self.price_history[symbol] = []
            self.timestamp_history[symbol] = []

        self.price_history[symbol].append(price)
        self.timestamp_history[symbol].append(timestamp)

        # 限制历史长度
        if len(self.price_history[symbol]) > self.max_history:
            self.price_history[symbol].pop(0)
            self.timestamp_history[symbol].pop(0)

    def calculate_correlation(self, symbol1: str,
                             symbol2: str,
                             lookback: int = None) -> Optional[CorrelationPair]:
        """计算两个品种的相关性"""
        if symbol1 not in self.price_history or symbol2 not in self.price_history:
            return None

        prices1 = np.array(self.price_history[symbol1])
        prices2 = np.array(self.price_history[symbol2])

        if lookback is None:
            lookback = min(len(prices1), len(prices2))

        if lookback < self.min_samples:
            return None

        prices1 = prices1[-lookback:]
        prices2 = prices2[-lookback:]

        # 计算收益率
        returns1 = np.diff(np.log(prices1))
        returns2 = np.diff(np.log(prices2))

        if len(returns1) < 2 or len(returns2) < 2:
            return None

        # 确保长度一致
        min_len = min(len(returns1), len(returns2))
        returns1 = returns1[-min_len:]
        returns2 = returns2[-min_len:]

        # 计算Pearson相关系数
        correlation = np.corrcoef(returns1, returns2)[0, 1]

        # 处理NaN
        if np.isnan(correlation):
            correlation = 0

        # 确定相关性级别
        correlation_level = self._classify_correlation(correlation)

        return CorrelationPair(
            symbol1=symbol1,
            symbol2=symbol2,
            correlation=correlation,
            correlation_level=correlation_level,
            sample_size=min_len,
            last_updated=datetime.now()
        )

    def _classify_correlation(self, correlation: float) -> CorrelationLevel:
        """分类相关性"""
        if correlation > 0.9:
            return CorrelationLevel.VERY_HIGH
        elif correlation > 0.7:
            return CorrelationLevel.HIGH
        elif correlation > 0.5:
            return CorrelationLevel.MODERATE
        elif correlation > 0.3:
            return CorrelationLevel.LOW
        elif correlation > -0.3:
            return CorrelationLevel.VERY_LOW
        elif correlation > -0.7:
            return CorrelationLevel.NEGATIVE_HIGH
        else:
            return CorrelationLevel.NEGATIVE_HIGH

    def calculate_all_correlations(self,
                                 symbols: List[str],
                                 lookback: int = None) -> Dict[str, CorrelationPair]:
        """计算所有品种对的相关性"""
        correlations = {}

        for i in range(len(symbols)):
            for j in range(i + 1, len(symbols)):
                symbol1 = symbols[i]
                symbol2 = symbols[j]
                pair = self.calculate_correlation(symbol1, symbol2, lookback)
                if pair:
                    key = f"{symbol1}-{symbol2}"
                    correlations[key] = pair

        return correlations

    def get_correlation_matrix(self,
                              symbols: List[str],
                              lookback: int = None) -> pd.DataFrame:
        """获取相关性矩阵"""
        if len(symbols) < 2:
            return pd.DataFrame()

        matrix = pd.DataFrame(index=symbols, columns=symbols)

        for i, symbol1 in enumerate(symbols):
            for j, symbol2 in enumerate(symbols):
                if i == j:
                    matrix.loc[symbol1, symbol2] = 1.0
                else:
                    pair = self.calculate_correlation(symbol1, symbol2, lookback)
                    if pair:
                        matrix.loc[symbol1, symbol2] = pair.correlation
                    else:
                        matrix.loc[symbol1, symbol2] = 0.0

        return matrix


class PredefinedCorrelations:
    """预定义相关性映射"""

    # 加密货币相关性
    CRYPTO_CORRELATIONS = {
        # BTC相关
        ("BTCUSDT", "ETHUSDT"): 0.85,
        ("BTCUSDT", "BNBUSDT"): 0.75,
        ("BTCUSDT", "SOLUSDT"): 0.70,
        ("BTCUSDT", "XRPUSDT"): 0.65,
        ("BTCUSDT", "ADAUSDT"): 0.60,
        ("BTCUSDT", "DOGEUSDT"): 0.55,

        # ETH相关
        ("ETHUSDT", "BNBUSDT"): 0.70,
        ("ETHUSDT", "SOLUSDT"): 0.65,
        ("ETHUSDT", "MATICUSDT"): 0.60,

        # DeFi代币
        ("SOLUSDT", "MATICUSDT"): 0.75,
        ("SOLUSDT", "AVAXUSDT"): 0.70,
        ("UNIUSDT", "AAVEUSDT"): 0.80,

        # 层2代币
        ("MATICUSDT", "ARBUSDT"): 0.75,
        ("MATICUSDT", "OPUSDT"): 0.70,
    }

    # 外汇相关性
    FOREX_CORRELATIONS = {
        # 主要货币对
        ("EURUSD", "GBPUSD"): 0.85,
        ("EURUSD", "AUDUSD"): 0.70,
        ("EURUSD", "NZDUSD"): 0.65,

        ("EURUSD", "USDCHF"): -0.90,
        ("EURUSD", "USDJPY"): 0.50,

        ("GBPUSD", "USDCHF"): -0.80,
        ("GBPUSD", "USDJPY"): 0.55,

        # 商品货币
        ("AUDUSD", "NZDUSD"): 0.90,
        ("AUDUSD", "XAUUSD"): 0.50,
        ("NZDUSD", "XAUUSD"): 0.45,

        # 避险货币
        ("USDCHF", "USDJPY"): 0.60,
        ("USDCHF", "XAUUSD"): 0.50,
    }

    # 贵金属相关性
    COMMODITY_CORRELATIONS = {
        ("XAUUSD", "XAGUSD"): 0.75,
        ("XAUUSD", "XPTUSD"): 0.85,
        ("XAUUSD", "XPDUSD"): 0.70,
    }

    @classmethod
    def get_correlation(cls, symbol1: str, symbol2: str) -> Optional[float]:
        """获取预定义相关性"""
        # 尝试所有类别
        for correlations in [cls.CRYPTO_CORRELATIONS,
                           cls.FOREX_CORRELATIONS,
                           cls.COMMODITY_CORRELATIONS]:
            if (symbol1, symbol2) in correlations:
                return correlations[(symbol1, symbol2)]
            elif (symbol2, symbol1) in correlations:
                return correlations[(symbol2, symbol1)]

        return None


class CorrelationRiskManager:
    """相关性风险控制器"""

    def __init__(self, config: Dict = None):
        self.config = config or {}

        # 风险参数
        self.max_correlated_exposure = self.config.get("max_correlated_exposure", 0.30)  # 30%
        self.max_total_correlation_exposure = self.config.get("max_total_correlation_exposure", 0.50)  # 50%
        self.high_correlation_threshold = self.config.get("high_correlation_threshold", 0.7)
        self.moderate_correlation_threshold = self.config.get("moderate_correlation_threshold", 0.5)

        # 当前持仓
        self.positions: Dict[str, Dict] = {}  # {symbol: {side, size, entry_price}}

        # 相关性计算器
        self.calculator = CorrelationCalculator(
            self.config.get("min_samples", 30),
            self.config.get("max_history", 500)
        )

        # 使用预定义相关性的标志
        self.use_predefined = self.config.get("use_predefined", True)

        # 相关性缓存
        self.correlation_cache: Dict[str, float] = {}
        self.cache_ttl = self.config.get("cache_ttl_minutes", 60) * 60
        self.last_cache_update: Dict[str, datetime] = {}

    def add_position(self, symbol: str, side: str, size: float,
                     entry_price: float, current_price: float):
        """添加持仓"""
        self.positions[symbol] = {
            "side": side,  # long/short
            "size": size,
            "entry_price": entry_price,
            "current_price": current_price,
            "timestamp": datetime.now()
        }

        # 更新价格历史
        self.calculator.update_price(symbol, current_price)

        logger.info(f"添加持仓: {symbol} {side} {size:.6f}")

    def remove_position(self, symbol: str):
        """移除持仓"""
        if symbol in self.positions:
            del self.positions[symbol]
            logger.info(f"移除持仓: {symbol}")

    def update_position_price(self, symbol: str, current_price: float):
        """更新持仓价格"""
        if symbol in self.positions:
            self.positions[symbol]["current_price"] = current_price
            self.calculator.update_price(symbol, current_price)

    def get_correlation(self, symbol1: str, symbol2: str) -> float:
        """获取两个品种的相关性"""
        # 检查缓存
        key1 = f"{symbol1}-{symbol2}"
        key2 = f"{symbol2}-{symbol1}"

        now = datetime.now()

        if key1 in self.last_cache_update:
            age = (now - self.last_cache_update[key1]).total_seconds()
            if age < self.cache_ttl:
                return self.correlation_cache.get(key1, 0)

        if key2 in self.last_cache_update:
            age = (now - self.last_cache_update[key2]).total_seconds()
            if age < self.cache_ttl:
                return self.correlation_cache.get(key2, 0)

        # 尝试预定义相关性
        if self.use_predefined:
            predefined = PredefinedCorrelations.get_correlation(symbol1, symbol2)
            if predefined is not None:
                self.correlation_cache[key1] = predefined
                self.last_cache_update[key1] = now
                return predefined

        # 计算相关性
        pair = self.calculator.calculate_correlation(symbol1, symbol2)
        if pair:
            correlation = pair.correlation
        else:
            correlation = 0

        # 缓存结果
        self.correlation_cache[key1] = correlation
        self.last_cache_update[key1] = now

        return correlation

    def can_open_position(self, symbol: str, side: str, size: float,
                        price: float, account_balance: float) -> Tuple[bool, str, float]:
        """
        检查是否可以开仓

        返回:
            (can_open, reason, max_allowed_size)
        """
        if not self.positions:
            return True, "无现有持仓", size

        # 计算新的风险暴露
        new_exposure = size * price / account_balance

        # 检查与现有持仓的相关性
        correlated_exposure = 0
        warnings = []

        for existing_symbol, existing_pos in self.positions.items():
            correlation = self.get_correlation(symbol, existing_symbol)

            if abs(correlation) >= self.high_correlation_threshold:
                # 高相关性
                existing_exposure = existing_pos["size"] * existing_pos["current_price"] / account_balance

                # 检查方向
                if existing_pos["side"] == side:
                    # 同方向,暴露叠加
                    correlated_exposure += existing_exposure * abs(correlation)
                else:
                    # 反方向,暴露抵消
                    correlated_exposure -= existing_exposure * abs(correlation)

                if abs(correlation) >= 0.85:
                    warnings.append(f"与{existing_symbol}相关性极高({correlation:.2f})")

            elif abs(correlation) >= self.moderate_correlation_threshold:
                # 中等相关性
                existing_exposure = existing_pos["size"] * existing_pos["current_price"] / account_balance
                correlated_exposure += existing_exposure * abs(correlation) * 0.5

        # 计算总相关暴露
        total_correlated_exposure = new_exposure + abs(correlated_exposure)

        # 检查限制
        if total_correlated_exposure > self.max_total_correlation_exposure:
            max_allowed = (self.max_total_correlation_exposure - abs(correlated_exposure)) * account_balance / price
            max_allowed = max(0, max_allowed)
            return False, f"超过相关暴露限制 ({total_correlated_exposure:.2%})", max_allowed

        if total_correlated_exposure > self.max_correlated_exposure:
            warnings.append(f"相关暴露较高 ({total_correlated_exposure:.2%})")

        # 检查同向高相关性品种数量
        high_corr_same_direction = 0
        for existing_symbol, existing_pos in self.positions.items():
            correlation = self.get_correlation(symbol, existing_symbol)
            if correlation >= self.high_correlation_threshold and existing_pos["side"] == side:
                high_corr_same_direction += 1

        if high_corr_same_direction >= 2:
            return False, f"已有{high_corr_same_direction}个高相关同向持仓", size * 0.5

        # 根据警告调整最大仓位
        max_allowed = size
        if warnings:
            max_allowed *= 0.7  # 有警告时减少70%
            reason = "; ".join(warnings)
            return True, reason, max_allowed

        return True, "可以开仓", size

    def get_risk_report(self, account_balance: float) -> CorrelationRiskReport:
        """生成风险报告"""
        if not self.positions:
            return CorrelationRiskReport(
                timestamp=datetime.now(),
                total_positions=0,
                total_exposure=0,
                correlated_positions=[],
                correlation_matrix={},
                exposure_summaries=[],
                overall_risk_level="low",
                recommendations=["当前无持仓"],
                actions_required=[]
            )

        # 计算相关性矩阵
        symbols = list(self.positions.keys())
        correlation_matrix = {}
        for symbol1 in symbols:
            correlation_matrix[symbol1] = {}
            for symbol2 in symbols:
                correlation_matrix[symbol1][symbol2] = self.get_correlation(symbol1, symbol2)

        # 计算各品种的风险暴露
        exposure_summaries = []
        correlated_positions_set = set()
        total_exposure = 0

        for symbol, position in self.positions.items():
            exposure = position["size"] * position["current_price"]
            exposure_pct = exposure / account_balance

            # 计算相关暴露
            correlated_exposure = 0
            warnings = []

            for other_symbol, other_position in self.positions.items():
                if other_symbol == symbol:
                    continue

                correlation = self.get_correlation(symbol, other_symbol)
                if abs(correlation) >= self.high_correlation_threshold:
                    other_exposure = other_position["size"] * other_position["current_price"]
                    if position["side"] == other_position["side"]:
                        correlated_exposure += other_exposure * correlation
                        correlated_positions_set.add(symbol)
                        correlated_positions_set.add(other_symbol)

            correlated_exposure_pct = correlated_exposure / account_balance

            # 风险等级
            if correlated_exposure_pct > 0.3:
                risk_level = "high"
            elif correlated_exposure_pct > 0.15:
                risk_level = "medium"
            else:
                risk_level = "low"

            # 生成警告
            if correlated_exposure_pct > 0.2:
                warnings.append(f"高相关暴露: {correlated_exposure_pct:.2%}")

            exposure_summaries.append(ExposureSummary(
                symbol=symbol,
                position_type=position["side"],
                exposure_amount=exposure,
                exposure_pct=exposure_pct,
                correlated_exposure=correlated_exposure,
                correlated_exposure_pct=correlated_exposure_pct,
                risk_level=risk_level,
                warnings=warnings
            ))

            total_exposure += exposure

        # 评估整体风险
        max_correlated_exposure = max(
            (es.correlated_exposure_pct for es in exposure_summaries),
            default=0
        )

        if max_correlated_exposure > 0.3 or len(correlated_positions_set) >= 3:
            overall_risk = "high"
        elif max_correlated_exposure > 0.15 or len(correlated_positions_set) >= 2:
            overall_risk = "medium"
        else:
            overall_risk = "low"

        # 生成建议
        recommendations = []
        actions_required = []

        if overall_risk == "high":
            recommendations.append("考虑减少高相关品种的持仓")
            actions_required.append("评估是否需要平掉部分高相关持仓")
        elif overall_risk == "medium":
            recommendations.append("注意高相关品种的风险累积")
            actions_required.append("监控相关品种的价格变动")

        return CorrelationRiskReport(
            timestamp=datetime.now(),
            total_positions=len(self.positions),
            total_exposure=total_exposure,
            correlated_positions=list(correlated_positions_set),
            correlation_matrix=correlation_matrix,
            exposure_summaries=exposure_summaries,
            overall_risk_level=overall_risk,
            recommendations=recommendations,
            actions_required=actions_required
        )

    def get_position_group(self, symbol: str) -> List[str]:
        """获取与指定品种相关的品种组"""
        group = [symbol]

        for other_symbol in self.positions.keys():
            if other_symbol == symbol:
                continue

            correlation = self.get_correlation(symbol, other_symbol)
            if correlation >= self.moderate_correlation_threshold:
                group.append(other_symbol)

        return group


def create_correlation_risk_manager(config: Dict = None) -> CorrelationRiskManager:
    """创建相关性风险控制器"""
    return CorrelationRiskManager(config)


if __name__ == "__main__":
    # 测试代码
    config = {
        "max_correlated_exposure": 0.30,
        "max_total_correlation_exposure": 0.50,
        "high_correlation_threshold": 0.7,
        "moderate_correlation_threshold": 0.5,
        "use_predefined": True
    }

    manager = CorrelationRiskManager(config)

    print("\n=== 相关性风险控制测试 ===\n")

    # 添加一些持仓
    test_positions = [
        ("BTCUSDT", "long", 0.5, 40000, 40500),
        ("ETHUSDT", "long", 2.0, 3000, 3050),
        ("BNBUSDT", "short", 10.0, 400, 395),
    ]

    account_balance = 10000

    for symbol, side, size, entry_price, current_price in test_positions:
        manager.add_position(symbol, side, size, entry_price, current_price)

    # 测试相关性
    print("预定义相关性:")
    pairs = [
        ("BTCUSDT", "ETHUSDT"),
        ("BTCUSDT", "SOLUSDT"),
        ("ETHUSDT", "BNBUSDT"),
        ("EURUSD", "GBPUSD"),
        ("XAUUSD", "XAGUSD")
    ]

    for sym1, sym2 in pairs:
        corr = manager.get_correlation(sym1, sym2)
        level = manager.calculator._classify_correlation(corr)
        print(f"  {sym1} - {sym2}: {corr:.3f} ({level.value})")

    # 检查能否开新仓
    print("\n\n检查新仓:")
    new_symbol = "SOLUSDT"
    can_open, reason, max_size = manager.can_open_position(
        new_symbol, "long", 1.5, 120, account_balance
    )
    print(f"  {new_symbol} 做多: {can_open} - {reason}")
    print(f"    最大允许仓位: {max_size:.6f}")

    # 生成风险报告
    print("\n\n风险报告:")
    report = manager.get_risk_report(account_balance)

    print(f"\n  持仓数量: {report.total_positions}")
    print(f"  总暴露: ${report.total_exposure:.2f}")
    print(f"  高相关品种: {', '.join(report.correlated_positions) or '无'}")
    print(f"  整体风险: {report.overall_risk_level}")

    print(f"\n  各品种暴露:")
    for summary in report.exposure_summaries:
        print(f"    {summary.symbol} ({summary.position_type}):")
        print(f"      暴露: {summary.exposure_pct:.2%}")
        print(f"      相关暴露: {summary.correlated_exposure_pct:.2%}")
        print(f"      风险: {summary.risk_level}")
        if summary.warnings:
            print(f"      警告: {', '.join(summary.warnings)}")

    print(f"\n  相关性矩阵:")
    for symbol1 in report.correlation_matrix:
        row = []
        for symbol2 in report.correlation_matrix[symbol1]:
            corr = report.correlation_matrix[symbol1][symbol2]
            row.append(f"{corr:6.3f}")
        print(f"    {symbol1}: {'  '.join(row)}")

    print(f"\n  建议:")
    for rec in report.recommendations:
        print(f"    - {rec}")

    if report.actions_required:
        print(f"\n  需要采取的行动:")
        for action in report.actions_required:
            print(f"    - {action}")
