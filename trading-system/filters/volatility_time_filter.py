# 高波动时段过滤器
# 避免在重要数据发布前后1小时交易
# 避免在亚洲/欧美市场交接时段开仓

from typing import Dict, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
import logging

logger = logging.getLogger(__name__)


@dataclass
class EconomicEvent:
    """经济数据发布事件"""
    name: str
    impact: str                # high/medium/low
    time: datetime
    timezone: str = "UTC"


@dataclass
class TimeWindow:
    """时间窗口"""
    name: str
    reason: str
    start_hour: int
    start_minute: int
    end_hour: int
    end_minute: int
    timezone: str = "UTC"


class VolatilityTimeFilter:
    """高波动时段过滤器"""

    def __init__(self, config: Dict = None):
        self.config = config or {}

        # 预定义的高波动时间窗口
        self.high_volatility_windows = self.config.get("high_volatility_windows", [
            TimeWindow(
                name="市场开盘",
                reason="亚洲市场开盘时段，波动较大",
                start_hour=0, start_minute=0,
                end_hour=1, end_minute=30,
                timezone="UTC"
            ),
            TimeWindow(
                name="欧美交接",
                reason="欧美市场交接时段，波动较大",
                start_hour=12, start_minute=0,
                end_hour=14, end_minute=0,
                timezone="UTC"
            ),
            TimeWindow(
                name="美股开盘",
                reason="美股开盘，波动较大",
                start_hour=13, start_minute=30,
                end_hour=14, end_minute=30,
                timezone="UTC"
            ),
            TimeWindow(
                name="重要数据发布",
                reason="非农数据/CPI等发布时段",
                start_hour=13, start_minute=30,
                end_hour=14, end_minute=0,
                timezone="UTC"
            )
        ])

        # 经济数据发布事件（可动态更新）
        self.economic_events: List[EconomicEvent] = []

        # 数据发布前后缓冲时间（分钟）
        self.event_buffer_minutes = self.config.get("event_buffer_minutes", 60)

        # 时区配置
        self.timezone = self.config.get("timezone", "UTC")

    def add_economic_event(self, name: str, impact: str, event_time: datetime):
        """
        添加经济数据发布事件

        参数:
            name: 事件名称
            impact: 影响级别 (high/medium/low)
            event_time: 事件时间
        """
        event = EconomicEvent(
            name=name,
            impact=impact,
            time=event_time
        )
        self.economic_events.append(event)
        logger.info(f"添加经济事件: {name} {impact} {event_time}")

    def remove_past_events(self):
        """移除过去的经济事件"""
        now = datetime.now()
        self.economic_events = [
            e for e in self.economic_events
            if e.time > now - timedelta(hours=2)
        ]

    def is_high_volatility_time(self, check_time: datetime = None) -> Tuple[bool, str]:
        """
        检查是否为高波动时段

        参数:
            check_time: 检查时间，默认为当前时间

        返回:
            (is_high_volatility: bool, reason: str)
        """
        if check_time is None:
            check_time = datetime.now()

        # 清理过期事件
        self.remove_past_events()

        # 检查高波动时间窗口
        for window in self.high_volatility_windows:
            if self._is_in_time_window(check_time, window):
                return True, f"{window.reason} ({window.name})"

        # 检查经济数据发布事件
        for event in self.economic_events:
            if event.impact == "high":
                buffer_start = event.time - timedelta(minutes=self.event_buffer_minutes)
                buffer_end = event.time + timedelta(minutes=self.event_buffer_minutes)

                if buffer_start <= check_time <= buffer_end:
                    return True, f"接近重要数据发布({event.name})"

        return False, "当前时段适合交易"

    def should_trade(self, check_time: datetime = None) -> Tuple[bool, str]:
        """
        判断是否应该交易

        参数:
            check_time: 检查时间

        返回:
            (should_trade: bool, reason: str)
        """
        is_high_vol, reason = self.is_high_volatility_time(check_time)

        if is_high_vol:
            return False, f"高波动时段，建议避免交易: {reason}"
        else:
            return True, reason

    def get_safe_trading_hours(self) -> List[Tuple[time, time]]:
        """
        获取安全交易时段

        返回:
            [(start_time, end_time), ...]
        """
        safe_hours = []

        # 定义一天的小时段
        all_hours = [(h, 0) for h in range(24)]

        # 移除高波动时段
        for window in self.high_volatility_windows:
            start_idx = window.start_hour
            end_idx = window.end_hour
            all_hours = [(h, m) for (h, m) in all_hours
                         if not (start_idx <= h < end_idx)]

        # 合并相邻时段
        if not all_hours:
            return []

        current_start = all_hours[0]
        current_end = all_hours[0]

        for h, m in all_hours[1:]:
            if (h == current_end[0] and m == current_end[1]) or \
               (h == current_end[0] + 1 and m == 0):
                current_end = (h, m)
            else:
                safe_hours.append((time(*current_start), time(*current_end)))
                current_start = (h, m)
                current_end = (h, m)

        safe_hours.append((time(*current_start), time(*current_end)))

        return safe_hours

    def get_next_safe_window(self, check_time: datetime = None) -> Tuple[datetime, datetime]:
        """
        获取下一个安全交易窗口

        参数:
            check_time: 检查时间

        返回:
            (start_time, end_time)
        """
        if check_time is None:
            check_time = datetime.now()

        # 检查当前是否在安全时段
        current_safe, _ = self.should_trade(check_time)
        if current_safe:
            # 当前安全，查找下一个高波动时段
            return self._find_next_high_volatility_end(check_time)

        # 查找下一个安全时段
        return self._find_next_safe_window(check_time)

    def _is_in_time_window(self, check_time: datetime, window: TimeWindow) -> bool:
        """检查时间是否在窗口内"""
        current_hour = check_time.hour
        current_minute = check_time.minute

        # 简单的小时范围检查
        start_total = window.start_hour * 60 + window.start_minute
        end_total = window.end_hour * 60 + window.end_minute
        current_total = current_hour * 60 + current_minute

        return start_total <= current_total < end_total

    def _find_next_high_volatility_end(self, check_time: datetime) -> Tuple[datetime, datetime]:
        """查找下一个高波动时段结束时间"""
        for window in self.high_volatility_windows:
            start_time = check_time.replace(
                hour=window.start_hour,
                minute=window.start_minute,
                second=0,
                microsecond=0
            )
            end_time = check_time.replace(
                hour=window.end_hour,
                minute=window.end_minute,
                second=0,
                microsecond=0
            )

            if check_time < end_time:
                return check_time, end_time

        # 如果今天没有找到，返回明天的第一个安全时段
        tomorrow = check_time + timedelta(days=1)
        return tomorrow, tomorrow.replace(hour=1, minute=30, second=0)

    def _find_next_safe_window(self, check_time: datetime) -> Tuple[datetime, datetime]:
        """查找下一个安全时段"""
        # 检查剩余的今天时段
        for hour in range(check_time.hour, 24):
            test_time = check_time.replace(hour=hour, minute=0, second=0, microsecond=0)
            is_safe, _ = self.should_trade(test_time)
            if is_safe:
                # 找到安全时段的开始，查找结束
                for end_hour in range(hour + 1, 25):
                    test_end_time = test_time.replace(hour=end_hour, minute=0)
                    is_end_safe, _ = self.should_trade(test_end_time)
                    if not is_end_safe:
                        return test_time, test_end_time
                return test_time, test_time.replace(hour=23, minute=59)

        # 检查明天的时段
        tomorrow = check_time + timedelta(days=1)
        for hour in range(24):
            test_time = tomorrow.replace(hour=hour, minute=0, second=0, microsecond=0)
            is_safe, _ = self.should_trade(test_time)
            if is_safe:
                for end_hour in range(hour + 1, 25):
                    test_end_time = test_time.replace(hour=end_hour, minute=0)
                    is_end_safe, _ = self.should_trade(test_end_time)
                    if not is_end_safe:
                        return test_time, test_end_time
                return test_time, test_time.replace(hour=23, minute=59)

        # 默认返回明天早上
        return tomorrow, tomorrow.replace(hour=2, minute=0)


def create_volatility_time_filter(config: Dict = None) -> VolatilityTimeFilter:
    """创建高波动时段过滤器"""
    return VolatilityTimeFilter(config)


if __name__ == "__main__":
    # 测试代码
    filter = VolatilityTimeFilter()

    print("\n=== 测试高波动时段过滤器 ===")

    # 添加一些重要经济事件
    now = datetime.now()
    filter.add_economic_event("非农数据", "high", now + timedelta(minutes=30))
    filter.add_economic_event("CPI数据", "high", now + timedelta(hours=2))
    filter.add_economic_event("美联储决议", "high", now + timedelta(hours=5))

    # 测试不同时间点
    test_times = [
        now,  # 现在
        now + timedelta(minutes=30),  # 非农数据前
        now + timedelta(hours=1),  # 非农数据后
        now.replace(hour=13, minute=30),  # 美股开盘
        now.replace(hour=2, minute=0),  # 亚洲开盘
        now.replace(hour=5, minute=0),  # 相对安静时段
    ]

    print("\n检查不同时间点:")
    for test_time in test_times:
        should_trade, reason = filter.should_trade(test_time)
        status = "✓" if should_trade else "✗"
        print(f"  {status} {test_time.strftime('%H:%M')} - {reason}")

    # 获取安全交易时段
    print("\n安全交易时段:")
    safe_hours = filter.get_safe_trading_hours()
    for start, end in safe_hours:
        print(f"  {start.strftime('%H:%M')} - {end.strftime('%H:%M')}")

    # 获取下一个安全窗口
    print("\n下一个安全交易窗口:")
    next_start, next_end = filter.get_next_safe_window()
    print(f"  {next_start.strftime('%Y-%m-%d %H:%M')} - {next_end.strftime('%H:%M')}")
