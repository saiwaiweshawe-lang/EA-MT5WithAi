# 分批建仓策略
# 将计划仓位分成3批入场：40%首仓，30%加仓，30%确认仓
# 确认信号后再加剩余仓位

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ScaleStatus(Enum):
    """分批状态"""
    PENDING = "pending"           # 等待入场
    FIRST_ENTERED = "first_entered"    # 首仓已入
    SECOND_ENTERED = "second_entered"  # 加仓已入
    ALL_ENTERED = "all_entered"        # 全部入场
    CANCELLED = "cancelled"            # 已取消


@dataclass
class ScaleInLevel:
    """分批入场层级"""
    level: int                   # 层级 1, 2, 3
    size_pct: float             # 占总仓位的百分比
    price_pct: float           # 价格触发条件（相对于入场价）
    entry_condition: str       # 入场条件描述
    entered: bool = False     # 是否已入场
    entry_time: Optional[datetime] = None  # 入场时间
    entry_price: Optional[float] = None    # 实际入场价格


@dataclass
class ScaleInPlan:
    """分批建仓计划"""
    symbol: str
    direction: str            # "buy" 或 "sell"
    base_price: float         # 基准价格
    total_size: float        # 总目标仓位
    status: ScaleStatus = ScaleStatus.PENDING
    levels: List[ScaleInLevel] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


class ScaleInStrategy:
    """分批建仓策略"""

    def __init__(self, config: Dict = None):
        self.config = config or {}

        # 分批配置
        self.scale_in_levels = self.config.get("scale_in_levels", [
            {"level": 1, "size_pct": 0.40, "price_pct": 0.00, "condition": "首仓立即入场"},
            {"level": 2, "size_pct": 0.30, "price_pct": 0.002, "condition": "价格向有利方向移动0.2%加仓"},
            {"level": 3, "size_pct": 0.30, "price_pct": 0.004, "condition": "确认信号后加仓"}
        ])

        # 价格确认阈值
        self.confirmation_threshold = self.config.get("confirmation_threshold", 0.005)

        # 最大持仓时间（小时）
        self.max_hold_time_hours = self.config.get("max_hold_time_hours", 24)

        # 活跃的建仓计划
        self.active_plans: List[ScaleInPlan] = []

    def create_scale_in_plan(self, symbol: str, direction: str,
                            base_price: float, total_size: float) -> ScaleInPlan:
        """
        创建分批建仓计划

        参数:
            symbol: 交易品种
            direction: 方向 "buy" 或 "sell"
            base_price: 基准价格
            total_size: 总目标仓位

        返回:
            ScaleInPlan
        """
        levels = []
        for level_config in self.scale_in_levels:
            level = ScaleInLevel(
                level=level_config["level"],
                size_pct=level_config["size_pct"],
                price_pct=level_config["price_pct"],
                entry_condition=level_config["condition"]
            )
            levels.append(level)

        plan = ScaleInPlan(
            symbol=symbol,
            direction=direction,
            base_price=base_price,
            total_size=total_size,
            levels=levels
        )

        self.active_plans.append(plan)
        logger.info(f"创建分批建仓计划: {symbol} {direction} 总仓位={total_size}")

        return plan

    def get_entry_size(self, plan: ScaleInPlan, current_price: float,
                     signal_confirmed: bool = False) -> Tuple[float, Optional[int]]:
        """
        获取当前应该入场的大小

        参数:
            plan: 建仓计划
            current_price: 当前价格
            signal_confirmed: 信号是否确认

        返回:
            (size, level_index) 或 (0, None)
        """
        if plan.status == ScaleStatus.ALL_ENTERED:
            return 0.0, None

        # 遍历层级，找到应该入场的层级
        for i, level in enumerate(plan.levels):
            if level.entered:
                continue

            # 检查是否应该入场
            should_enter = False

            if level.level == 1:
                # 第一层：立即入场
                should_enter = True
            elif signal_confirmed and level.level == 3:
                # 第三层：信号确认后入场
                should_enter = True
            else:
                # 其他层级：价格条件触发
                should_enter = self._check_price_condition(
                    plan.direction, plan.base_price, current_price, level.price_pct
                )

            if should_enter:
                size = plan.total_size * level.size_pct
                return size, level.level

        return 0.0, None

    def execute_entry(self, plan: ScaleInPlan, level_index: int,
                    actual_price: float, actual_size: float):
        """
        执行入场

        参数:
            plan: 建仓计划
            level_index: 层级索引
            actual_price: 实际入场价格
            actual_size: 实际入场大小
        """
        level = plan.levels[level_index - 1]
        level.entered = True
        level.entry_price = actual_price
        level.entry_time = datetime.now()

        plan.updated_at = datetime.now()

        # 更新状态
        entered_count = sum(1 for l in plan.levels if l.entered)
        if entered_count == len(plan.levels):
            plan.status = ScaleStatus.ALL_ENTERED
        elif entered_count == 1:
            plan.status = ScaleStatus.FIRST_ENTERED
        elif entered_count == 2:
            plan.status = ScaleStatus.SECOND_ENTERED

        logger.info(f"执行{plan.symbol}分批入场: 层级{level_index}, 价格={actual_price}, 大小={actual_size}")

    def _check_price_condition(self, direction: str, base_price: float,
                             current_price: float, price_pct: float) -> bool:
        """检查价格条件"""
        target_price = base_price * (1 + price_pct) if direction == "buy" else base_price * (1 - price_pct)

        if direction == "buy":
            # 做多：当前价格达到目标价
            return current_price >= target_price
        else:
            # 做空：当前价格达到目标价
            return current_price <= target_price

    def should_add_position(self, plan: ScaleInPlan, current_price: float,
                          signal_confirmed: bool = False) -> bool:
        """
        判断是否应该加仓

        参数:
            plan: 建仓计划
            current_price: 当前价格
            signal_confirmed: 信号是否确认

        返回:
            是否应该加仓
        """
        if plan.status == ScaleStatus.ALL_ENTERED:
            return False

        size, level = self.get_entry_size(plan, current_price, signal_confirmed)
        return size > 0 and level is not None

    def get_position_summary(self, plan: ScaleInPlan) -> Dict:
        """
        获取建仓进度摘要

        参数:
            plan: 建仓计划

        返回:
            摘要信息
        """
        entered_levels = [l for l in plan.levels if l.entered]
        entered_size = sum(plan.total_size * l.size_pct for l in entered_levels)
        total_entered_size = sum(l.entry_price * plan.total_size * l.size_pct
                                for l in entered_levels if l.entry_price)

        return {
            "symbol": plan.symbol,
            "direction": plan.direction,
            "total_size": plan.total_size,
            "entered_size": entered_size,
            "entered_pct": entered_size / plan.total_size if plan.total_size > 0 else 0,
            "status": plan.status.value,
            "levels_entered": len(entered_levels),
            "total_levels": len(plan.levels),
            "avg_entry_price": total_entered_size / entered_size if entered_size > 0 else 0,
            "levels_details": [
                {
                    "level": l.level,
                    "size_pct": l.size_pct,
                    "entered": l.entered,
                    "entry_price": l.entry_price
                }
                for l in plan.levels
            ]
        }

    def cancel_plan(self, plan: ScaleInPlan):
        """取消建仓计划"""
        plan.status = ScaleStatus.CANCELLED
        plan.updated_at = datetime.now()
        if plan in self.active_plans:
            self.active_plans.remove(plan)
        logger.info(f"取消分批建仓计划: {plan.symbol}")

    def get_active_plan(self, symbol: str) -> Optional[ScaleInPlan]:
        """获取指定品种的活跃建仓计划"""
        for plan in self.active_plans:
            if plan.symbol == symbol and plan.status not in [ScaleStatus.ALL_ENTERED, ScaleStatus.CANCELLED]:
                return plan
        return None

    def cleanup_expired_plans(self):
        """清理过期的建仓计划"""
        now = datetime.now()
        self.active_plans = [
            p for p in self.active_plans
            if (now - p.created_at).total_seconds() < self.max_hold_time_hours * 3600
            and p.status != ScaleStatus.CANCELLED
        ]


def create_scale_in_strategy(config: Dict = None) -> ScaleInStrategy:
    """创建分批建仓策略"""
    return ScaleInStrategy(config)


if __name__ == "__main__":
    # 测试代码
    strategy = ScaleInStrategy()

    print("\n=== 测试分批建仓策略 ===")

    # 创建建仓计划
    plan = strategy.create_scale_in_plan(
        symbol="BTCUSDT",
        direction="buy",
        base_price=40000,
        total_size=0.1
    )

    print("\n建仓计划:")
    summary = strategy.get_position_summary(plan)
    print(f"  品种: {summary['symbol']}")
    print(f"  方向: {summary['direction']}")
    print(f"  总仓位: {summary['total_size']}")
    print(f"  状态: {summary['status']}")

    # 模拟入场过程
    print("\n模拟入场过程:")

    # 第一层入场
    print("\n1. 首仓入场:")
    size, level = strategy.get_entry_size(plan, 40000)
    if size > 0:
        print(f"   入场大小: {size}")
        strategy.execute_entry(plan, level, 40000, size)
        summary = strategy.get_position_summary(plan)
        print(f"   进度: {summary['entered_pct']:.0%}")

    # 第二层入场（价格上涨）
    print("\n2. 加仓入场:")
    size, level = strategy.get_entry_size(plan, 40100)
    if size > 0:
        print(f"   入场大小: {size}")
        strategy.execute_entry(plan, level, 40100, size)
        summary = strategy.get_position_summary(plan)
        print(f"   进度: {summary['entered_pct']:.0%}")

    # 第三层入场（确认信号）
    print("\n3. 确认仓入场:")
    size, level = strategy.get_entry_size(plan, 40200, signal_confirmed=True)
    if size > 0:
        print(f"   入场大小: {size}")
        strategy.execute_entry(plan, level, 40200, size)
        summary = strategy.get_position_summary(plan)
        print(f"   进度: {summary['entered_pct']:.0%}")

    # 最终摘要
    print("\n最终建仓摘要:")
    summary = strategy.get_position_summary(plan)
    print(f"  总入场: {summary['entered_size']}")
    print(f"  平均入场价: {summary['avg_entry_price']:.2f}")
    print(f"  状态: {summary['status']}")

    print("\n各层级详情:")
    for level_detail in summary['levels_details']:
        status = "已入场" if level_detail['entered'] else "未入场"
        entry_price = f"入场价={level_detail['entry_price']:.2f}" if level_detail['entry_price'] else "未入场"
        print(f"  层级{level_detail['level']}: {status}, 占比={level_detail['size_pct']:.0%}, {entry_price}")
