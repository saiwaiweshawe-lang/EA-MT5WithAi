# 趋势一致性确认模块
# 多时间框架趋势一致性检查，确保大趋势方向一致才入场

from typing import Dict, List, Optional, Tuple
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class TrendDirection(Enum):
    """趋势方向"""
    UPTREND = "uptrend"
    DOWNTREND = "downtrend"
    NEUTRAL = "neutral"


class TrendAlignmentChecker:
    """趋势一致性检查器"""

    def __init__(self, config: Dict = None):
        self.config = config or {}

        # 需要检查的时间框架
        self.check_timeframes = self.config.get("check_timeframes", ["1d", "4h", "1h"])

        # 一致性阈值（需要多少比例一致）
        self.alignment_threshold = self.config.get("alignment_threshold", 0.7)

        # 权重配置（高级时间框架权重更高）
        self.timeframe_weights = self.config.get("timeframe_weights", {
            "1d": 0.4,
            "4h": 0.35,
            "1h": 0.25
        })

    def check_alignment(self, timeframe_trends: Dict[str, TrendDirection]) -> Dict:
        """
        检查趋势一致性

        参数:
            timeframe_trends: 各时间框架的趋势方向
                {"1d": TrendDirection.UPTREND, "4h": TrendDirection.UPTREND, "1h": TrendDirection.DOWNTREND}

        返回:
            {
                "aligned": bool,              # 是否对齐
                "dominant_trend": str,        # 主导趋势
                "alignment_score": float,     # 一致性得分 (0-1)
                "details": Dict,              # 详细信息
                "recommendation": str         # 建议
            }
        """
        # 统计各趋势方向
        trend_counts = {
            TrendDirection.UPTREND: {"count": 0, "weight": 0},
            TrendDirection.DOWNTREND: {"count": 0, "weight": 0},
            TrendDirection.NEUTRAL: {"count": 0, "weight": 0}
        }

        total_weight = 0

        for tf, trend in timeframe_trends.items():
            weight = self.timeframe_weights.get(tf, 0.1)
            trend_counts[trend]["count"] += 1
            trend_counts[trend]["weight"] += weight
            total_weight += weight

        # 计算加权一致性得分
        max_weight = max(trend_counts[TrendDirection.UPTREND]["weight"],
                         trend_counts[TrendDirection.DOWNTREND]["weight"])

        alignment_score = 0
        if total_weight > 0:
            alignment_score = max_weight / total_weight

        # 判断是否对齐
        aligned = alignment_score >= self.alignment_threshold

        # 确定主导趋势
        dominant_trend = "neutral"
        if trend_counts[TrendDirection.UPTREND]["weight"] > trend_counts[TrendDirection.DOWNTREND]["weight"]:
            dominant_trend = "uptrend"
        elif trend_counts[TrendDirection.DOWNTREND]["weight"] > trend_counts[TrendDirection.UPTREND]["weight"]:
            dominant_trend = "downtrend"

        # 生成建议
        recommendation = self._generate_recommendation(
            aligned, dominant_trend, alignment_score, timeframe_trends
        )

        # 详细信息
        details = {
            "timeframe_trends": {tf: t.value for tf, t in timeframe_trends.items()},
            "trend_counts": {
                "uptrend": trend_counts[TrendDirection.UPTREND],
                "downtrend": trend_counts[TrendDirection.DOWNTREND],
                "neutral": trend_counts[TrendDirection.NEUTRAL]
            },
            "alignment_threshold": self.alignment_threshold,
            "alignment_score": alignment_score
        }

        return {
            "aligned": aligned,
            "dominant_trend": dominant_trend,
            "alignment_score": alignment_score,
            "details": details,
            "recommendation": recommendation
        }

    def _generate_recommendation(self, aligned: bool, dominant_trend: str,
                               alignment_score: float, timeframe_trends: Dict) -> str:
        """生成交易建议"""
        if not aligned:
            conflicts = self._find_conflicts(timeframe_trends)
            return f"趋势不一致，等待确认。冲突: {conflicts}"

        if alignment_score > 0.8:
            return f"趋势高度一致({alignment_score:.0%})，建议顺势{dominant_trend}方向入场"
        elif alignment_score > 0.7:
            return f"趋势基本一致({alignment_score:.0%})，可以考虑{dominant_trend}方向入场"
        else:
            return f"趋势一致性较低({alignment_score:.0%})，建议观望"

    def _find_conflicts(self, timeframe_trends: Dict) -> str:
        """找出趋势冲突"""
        trends = {}
        for tf, trend in timeframe_trends.items():
            trends[tf] = trend.value

        uptrend_tfs = [tf for tf, t in trends.items() if t == "uptrend"]
        downtrend_tfs = [tf for tf, t in trends.items() if t == "downtrend"]

        conflicts = []
        if uptrend_tfs and downtrend_tfs:
            conflicts.append(f"上涨({','.join(uptrend_tfs)}) vs 下跌({','.join(downtrend_tfs)})")

        return "; ".join(conflicts) if conflicts else "无明显冲突"

    def should_trade(self, signal_direction: str, timeframe_trends: Dict[str, TrendDirection]) -> Tuple[bool, str]:
        """
        判断是否应该交易

        参数:
            signal_direction: 信号方向 ("buy" 或 "sell")
            timeframe_trends: 各时间框架趋势

        返回:
            (should_trade: bool, reason: str)
        """
        result = self.check_alignment(timeframe_trends)

        if not result["aligned"]:
            return False, result["recommendation"]

        # 检查信号方向是否与主导趋势一致
        if signal_direction == "buy" and result["dominant_trend"] == "downtrend":
            return False, f"做多信号与下降趋势不一致，建议观望或等待反转"

        if signal_direction == "sell" and result["dominant_trend"] == "uptrend":
            return False, f"做空信号与上升趋势不一致，建议观望或等待反转"

        return True, result["recommendation"]


def create_trend_alignment_checker(config: Dict = None) -> TrendAlignmentChecker:
    """创建趋势一致性检查器"""
    return TrendAlignmentChecker(config)


if __name__ == "__main__":
    # 测试代码
    checker = TrendAlignmentChecker()

    # 测试1: 完全一致
    print("\n=== 测试1: 完全一致的上升趋势 ===")
    result = checker.check_alignment({
        "1d": TrendDirection.UPTREND,
        "4h": TrendDirection.UPTREND,
        "1h": TrendDirection.UPTREND
    })
    print(f"  对齐: {result['aligned']}")
    print(f"  主导趋势: {result['dominant_trend']}")
    print(f"  一致性得分: {result['alignment_score']:.2%}")
    print(f"  建议: {result['recommendation']}")

    # 测试2: 基本一致
    print("\n=== 测试2: 基本一致的上升趋势 ===")
    result = checker.check_alignment({
        "1d": TrendDirection.UPTREND,
        "4h": TrendDirection.UPTREND,
        "1h": TrendDirection.NEUTRAL
    })
    print(f"  对齐: {result['aligned']}")
    print(f"  主导趋势: {result['dominant_trend']}")
    print(f"  一致性得分: {result['alignment_score']:.2%}")
    print(f"  建议: {result['recommendation']}")

    # 测试3: 趋势冲突
    print("\n=== 测试3: 趋势冲突 ===")
    result = checker.check_alignment({
        "1d": TrendDirection.UPTREND,
        "4h": TrendDirection.DOWNTREND,
        "1h": TrendDirection.DOWNTREND
    })
    print(f"  对齐: {result['aligned']}")
    print(f"  主导趋势: {result['dominant_trend']}")
    print(f"  一致性得分: {result['alignment_score']:.2%}")
    print(f"  建议: {result['recommendation']}")

    # 测试4: 交易决策
    print("\n=== 测试4: 交易决策 ===")
    should_trade, reason = checker.should_trade("buy", {
        "1d": TrendDirection.UPTREND,
        "4h": TrendDirection.UPTREND,
        "1h": TrendDirection.UPTREND
    })
    print(f"  做多决策: {should_trade} - {reason}")

    should_trade, reason = checker.should_trade("sell", {
        "1d": TrendDirection.UPTREND,
        "4h": TrendDirection.UPTREND,
        "1h": TrendDirection.UPTREND
    })
    print(f"  做空决策: {should_trade} - {reason}")
