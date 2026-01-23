# 突破回踩入场策略
# 等待突破后价格回踩到突破位再入场，避免在突破高点直接追涨

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class BreakoutType(Enum):
    """突破类型"""
    RESISTANCE_BREAKOUT = "resistance_breakout"
    SUPPORT_BREAKDOWN = "support_breakdown"


class BreakoutStatus(Enum):
    """突破状态"""
    PENDING = "pending"           # 等待突破
    BREAKOUT_OCCURRED = "breakout_occurred"  # 已突破，等待回踩
    PULLBACK_OCCURRED = "pullback_occurred"  # 已回踩，可以入场
    FAILED = "failed"              # 突破失败


@dataclass
class BreakoutEvent:
    """突破事件"""
    level: float                   # 突破位
    breakout_price: float          # 突破价格
    breakout_time: datetime        # 突破时间
    breakout_type: BreakoutType    # 突破类型
    status: BreakoutStatus = BreakoutStatus.BREAKOUT_OCCURRED
    pullback_price: Optional[float] = None  # 回踩价格
    pullback_time: Optional[datetime] = None  # 回踩时间


class PullbackEntryStrategy:
    """突破回踩入场策略"""

    def __init__(self, config: Dict = None):
        self.config = config or {}

        # 回踩容忍度（距离突破位的百分比）
        self.pullback_tolerance_pct = self.config.get("pullback_tolerance_pct", 0.005)

        # 突破确认阈值（收盘价要超过/低于突破位多少）
        self.breakout_threshold_pct = self.config.get("breakout_threshold_pct", 0.002)

        # 回踩入场区（突破位附近的百分比区间）
        self.entry_zone_pct = self.config.get("entry_zone_pct", 0.008)

        # 有效回踩时间窗口（小时内）
        self.pullback_window_hours = self.config.get("pullback_window_hours", 24)

        # 突破失效时间（小时内）
        self.breakout_expiry_hours = self.config.get("breakout_expiry_hours", 48)

        # 存储突破事件
        self.active_breakouts: List[BreakoutEvent] = []

    def detect_breakout(self, symbol: str, current_price: float,
                      resistance_levels: List[float],
                      support_levels: List[float],
                      timeframe: str = "1h") -> Optional[BreakoutEvent]:
        """
        检测突破

        参数:
            symbol: 交易品种
            current_price: 当前价格
            resistance_levels: 阻力位列表
            support_levels: 支撑位列表
            timeframe: 时间框架

        返回:
            BreakoutEvent 或 None
        """
        # 清理过期的突破事件
        self._clean_expired_events()

        # 检查是否有未完成的突破事件
        for event in self.active_breakouts:
            if event.symbol == symbol and event.status == BreakoutStatus.BREAKOUT_OCCURRED:
                # 检查是否回踩
                pullback = self._check_pullback(event, current_price)
                if pullback:
                    return pullback

        # 检测新的突破
        # 检查向上突破阻力
        for level in resistance_levels:
            if current_price > level * (1 + self.breakout_threshold_pct):
                # 检查是否已经有这个突破位的事件
                if not any(e.level == level for e in self.active_breakouts):
                    event = BreakoutEvent(
                        symbol=symbol,
                        level=level,
                        breakout_price=current_price,
                        breakout_time=datetime.now(),
                        breakout_type=BreakoutType.RESISTANCE_BREAKOUT
                    )
                    self.active_breakouts.append(event)
                    logger.info(f"检测到向上突破阻力位: {level}, 当前价格: {current_price}")
                    return event

        # 检查向下突破支撑
        for level in support_levels:
            if current_price < level * (1 - self.breakout_threshold_pct):
                if not any(e.level == level for e in self.active_breakouts):
                    event = BreakoutEvent(
                        symbol=symbol,
                        level=level,
                        breakout_price=current_price,
                        breakout_time=datetime.now(),
                        breakout_type=BreakoutType.SUPPORT_BREAKDOWN
                    )
                    self.active_breakouts.append(event)
                    logger.info(f"检测到向下突破支撑位: {level}, 当前价格: {current_price}")
                    return event

        return None

    def _check_pullback(self, event: BreakoutEvent, current_price: float) -> Optional[BreakoutEvent]:
        """
        检查是否回踩

        参数:
            event: 突破事件
            current_price: 当前价格

        返回:
            已回踩的 BreakoutEvent 或 None
        """
        now = datetime.now()

        # 检查是否在时间窗口内
        time_since_breakout = (now - event.breakout_time).total_seconds() / 3600
        if time_since_breakout > self.pullback_window_hours:
            event.status = BreakoutStatus.FAILED
            return None

        # 检查是否回踩
        if event.breakout_type == BreakoutType.RESISTANCE_BREAKOUT:
            # 向上突破后，价格回落到突破位附近
            lower_bound = event.level * (1 - self.entry_zone_pct)
            upper_bound = event.level * (1 + self.entry_zone_pct)

            if lower_bound <= current_price <= upper_bound:
                event.status = BreakoutStatus.PULLBACK_OCCURRED
                event.pullback_price = current_price
                event.pullback_time = now
                logger.info(f"向上突破后回踩到: {current_price}, 突破位: {event.level}")
                return event

        elif event.breakout_type == BreakoutType.SUPPORT_BREAKDOWN:
            # 向下突破后，价格反弹到突破位附近
            lower_bound = event.level * (1 - self.entry_zone_pct)
            upper_bound = event.level * (1 + self.entry_zone_pct)

            if lower_bound <= current_price <= upper_bound:
                event.status = BreakoutStatus.PULLBACK_OCCURRED
                event.pullback_price = current_price
                event.pullback_time = now
                logger.info(f"向下突破后反弹到: {current_price}, 突破位: {event.level}")
                return event

        return None

    def should_entry(self, symbol: str, current_price: float) -> Tuple[bool, Optional[BreakoutEvent], str]:
        """
        判断是否应该入场

        参数:
            symbol: 交易品种
            current_price: 当前价格

        返回:
            (should_entry: bool, event: BreakoutEvent or None, reason: str)
        """
        for event in self.active_breakouts:
            if event.symbol != symbol or event.status != BreakoutStatus.PULLBACK_OCCURRED:
                continue

            # 检查是否仍在入场区
            if event.breakout_type == BreakoutType.RESISTANCE_BREAKOUT:
                # 做多入场区
                lower_bound = event.level * (1 - self.entry_zone_pct)
                upper_bound = event.level * (1 + self.entry_zone_pct)

                if lower_bound <= current_price <= upper_bound:
                    return True, event, f"向上突破后回踩入场，突破位: {event.level}"
                elif current_price < lower_bound:
                    # 回踩过深，突破失败
                    event.status = BreakoutStatus.FAILED
                    return False, None, f"回踩过深({current_price} < {lower_bound:.2f})，突破失败"
                else:
                    # 价格已经上涨，可能错过
                    return False, None, f"价格已超过入场区上限({upper_bound:.2f})"

            elif event.breakout_type == BreakoutType.SUPPORT_BREAKDOWN:
                # 做空入场区
                lower_bound = event.level * (1 - self.entry_zone_pct)
                upper_bound = event.level * (1 + self.entry_zone_pct)

                if lower_bound <= current_price <= upper_bound:
                    return True, event, f"向下突破后反弹做空，突破位: {event.level}"
                elif current_price > upper_bound:
                    # 反弹过高，突破失败
                    event.status = BreakoutStatus.FAILED
                    return False, None, f"反弹过高({current_price} > {upper_bound:.2f})，突破失败"
                else:
                    # 价格已经下跌，可能错过
                    return False, None, f"价格已低于入场区下限({lower_bound:.2f})"

        return False, None, "没有可用的回踩入场信号"

    def get_entry_zone(self, symbol: str, signal_direction: str) -> Optional[Tuple[float, float]]:
        """
        获取入场区间

        参数:
            symbol: 交易品种
            signal_direction: 信号方向 ("buy" 或 "sell")

        返回:
            (low, high) 或 None
        """
        for event in self.active_breakouts:
            if event.symbol != symbol or event.status != BreakoutStatus.PULLBACK_OCCURRED:
                continue

            if signal_direction == "buy" and event.breakout_type == BreakoutType.RESISTANCE_BREAKOUT:
                return (
                    event.level * (1 - self.entry_zone_pct),
                    event.level * (1 + self.entry_zone_pct)
                )
            elif signal_direction == "sell" and event.breakout_type == BreakoutType.SUPPORT_BREAKDOWN:
                return (
                    event.level * (1 - self.entry_zone_pct),
                    event.level * (1 + self.entry_zone_pct)
                )

        return None

    def _clean_expired_events(self):
        """清理过期的事件"""
        now = datetime.now()
        self.active_breakouts = [
            e for e in self.active_breakouts
            if (now - e.breakout_time).total_seconds() / 3600 < self.breakout_expiry_hours
            and e.status != BreakoutStatus.FAILED
        ]

    def remove_event(self, event: BreakoutEvent):
        """移除已完成的突破事件"""
        if event in self.active_breakouts:
            self.active_breakouts.remove(event)

    def get_active_events(self, symbol: str = None) -> List[BreakoutEvent]:
        """获取活跃的突破事件"""
        events = self.active_breakouts
        if symbol:
            events = [e for e in events if e.symbol == symbol]
        return events

    def reset(self):
        """重置所有状态"""
        self.active_breakouts = []


def create_pullback_entry_strategy(config: Dict = None) -> PullbackEntryStrategy:
    """创建突破回踩入场策略"""
    return PullbackEntryStrategy(config)


# 添加 symbol 属性到 BreakoutEvent
def fix_breakout_event():
    """修复 BreakoutEvent 的 symbol 属性问题"""
    import types

    original_init = BreakoutEvent.__init__

    def new_init(self, symbol: str, level: float, breakout_price: float,
                breakout_time: datetime, breakout_type: BreakoutType,
                status: BreakoutStatus = BreakoutStatus.BREAKOUT_OCCURRED,
                pullback_price: Optional[float] = None,
                pullback_time: Optional[datetime] = None):
        self.symbol = symbol
        self.level = level
        self.breakout_price = breakout_price
        self.breakout_time = breakout_time
        self.breakout_type = breakout_type
        self.status = status
        self.pullback_price = pullback_price
        self.pullback_time = pullback_time

    BreakoutEvent.__init__ = new_init
    return BreakoutEvent


# 修复 BreakoutEvent
fix_breakout_event()


if __name__ == "__main__":
    # 测试代码
    strategy = PullbackEntryStrategy()

    # 测试突破回踩
    print("\n=== 测试突破回踩策略 ===")

    resistance_levels = [42000, 42500, 43000]
    support_levels = [40000, 39500, 39000]

    # 场景1: 向上突破阻力
    print("\n场景1: 向上突破阻力位 42000")
    event = strategy.detect_breakout("BTCUSDT", 42200, resistance_levels, support_levels)
    if event:
        print(f"  突破类型: {event.breakout_type.value}")
        print(f"  突破位: {event.level}")
        print(f"  突破价格: {event.breakout_price}")
        print(f"  状态: {event.status.value}")

    # 场景2: 回踩入场
    print("\n场景2: 价格回踩到突破位附近")
    should_entry, event, reason = strategy.should_entry("BTCUSDT", 42050)
    print(f"  应该入场: {should_entry}")
    print(f"  原因: {reason}")

    if should_entry and event:
        entry_zone = strategy.get_entry_zone("BTCUSDT", "buy")
        print(f"  入场区间: {entry_zone}")

    # 场景3: 向下突破支撑
    print("\n场景3: 向下突破支撑位 40000")
    event = strategy.detect_breakout("BTCUSDT", 39800, resistance_levels, support_levels)
    if event:
        print(f"  突破类型: {event.breakout_type.value}")
        print(f"  突破位: {event.level}")
        print(f"  突破价格: {event.breakout_price}")
        print(f"  状态: {event.status.value}")

    # 场景4: 反弹入场
    print("\n场景4: 价格反弹到突破位附近")
    should_entry, event, reason = strategy.should_entry("BTCUSDT", 39950)
    print(f"  应该入场: {should_entry}")
    print(f"  原因: {reason}")

    if should_entry and event:
        entry_zone = strategy.get_entry_zone("BTCUSDT", "sell")
        print(f"  入场区间: {entry_zone}")
