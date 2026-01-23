# 分批止盈和移动止损模块
# 到达第一止盈位平40%仓位，到达第二止盈位平30%仓位
# 剩余30%使用移动止损跟踪趋势

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class TakeProfitStatus(Enum):
    """止盈状态"""
    PENDING = "pending"
    TP1_HIT = "tp1_hit"           # 第一止盈位已触发
    TP2_HIT = "tp2_hit"           # 第二止盈位已触发
    ALL_CLOSED = "all_closed"       # 全部平仓
    STOPPED_OUT = "stopped_out"     # 止损


@dataclass
class TakeProfitLevel:
    """止盈层级"""
    level: int                   # 层级 1, 2
    price: float                 # 止盈价格
    close_pct: float            # 平仓比例 (0-1)
    executed: bool = False      # 是否已执行
    executed_time: Optional[datetime] = None
    executed_price: Optional[float] = None


@dataclass
class ExitPlan:
    """退出计划"""
    symbol: str
    direction: str            # "buy" 或 "sell"
    entry_price: float
    stop_loss: float
    current_price: float
    status: TakeProfitStatus = TakeProfitStatus.PENDING
    tp_levels: List[TakeProfitLevel] = field(default_factory=list)
    trailing_stop: Optional[float] = None
    created_at: datetime = field(default_factory=datetime.now)
    highest_price: float = 0.0
    lowest_price: float = 0.0


class PartialTakeProfitStrategy:
    """分批止盈策略"""

    def __init__(self, config: Dict = None):
        self.config = config or {}

        # 止盈配置
        self.take_profit_levels = self.config.get("take_profit_levels", [
            {"level": 1, "profit_pct": 0.04, "close_pct": 0.40, "description": "第一止盈位 - 平仓40%"},
            {"level": 2, "profit_pct": 0.08, "close_pct": 0.30, "description": "第二止盈位 - 平仓30%"}
        ])

        # 移动止损配置
        self.trailing_stop_enabled = self.config.get("trailing_stop_enabled", True)
        self.trailing_activation_pct = self.config.get("trailing_activation_pct", 0.02)
        self.trailing_distance_pct = self.config.get("trailing_distance_pct", 0.015)
        self.breakeven_enabled = self.config.get("breakeven_enabled", True)
        self.breakeven_pct = self.config.get("breakeven_pct", 0.01)

        # 剩余仓位管理
        self.final_stop_pct = self.config.get("final_stop_pct", 0.005)

        # 活跃的退出计划
        self.active_plans: List[ExitPlan] = []

    def create_exit_plan(self, symbol: str, direction: str,
                      entry_price: float, stop_loss: float) -> ExitPlan:
        """
        创建退出计划

        参数:
            symbol: 交易品种
            direction: 方向
            entry_price: 入场价格
            stop_loss: 止损价格

        返回:
            ExitPlan
        """
        # 计算止盈价格
        tp_levels = []
        for level_config in self.take_profit_levels:
            if direction == "buy":
                tp_price = entry_price * (1 + level_config["profit_pct"])
            else:
                tp_price = entry_price * (1 - level_config["profit_pct"])

            tp_levels.append(TakeProfitLevel(
                level=level_config["level"],
                price=tp_price,
                close_pct=level_config["close_pct"]
            ))

        plan = ExitPlan(
            symbol=symbol,
            direction=direction,
            entry_price=entry_price,
            stop_loss=stop_loss,
            current_price=entry_price,
            tp_levels=tp_levels
        )

        # 初始化最高/最低价
        if direction == "buy":
            plan.highest_price = entry_price
        else:
            plan.lowest_price = entry_price

        self.active_plans.append(plan)
        logger.info(f"创建退出计划: {symbol} 入场={entry_price} 止损={stop_loss}")

        return plan

    def update_price(self, plan: ExitPlan, current_price: float) -> Dict:
        """
        更新价格并检查退出条件

        参数:
            plan: 退出计划
            current_price: 当前价格

        返回:
            {
                "action": "hold/take_profit/stop_loss/trailing_stop",
                "close_pct": float,  # 需要平仓的比例
                "new_stop_loss": float or None,
                "reason": str
            }
        """
        plan.current_price = current_price
        result = {
            "action": "hold",
            "close_pct": 0.0,
            "new_stop_loss": None,
            "reason": ""
        }

        # 更新最高/最低价
        if plan.direction == "buy":
            if current_price > plan.highest_price:
                plan.highest_price = current_price
        else:
            if current_price < plan.lowest_price:
                plan.lowest_price = current_price

        # 检查止盈
        for tp_level in plan.tp_levels:
            if tp_level.executed:
                continue

            should_tp = False
            if plan.direction == "buy" and current_price >= tp_level.price:
                should_tp = True
            elif plan.direction == "sell" and current_price <= tp_level.price:
                should_tp = True

            if should_tp:
                tp_level.executed = True
                tp_level.executed_time = datetime.now()
                tp_level.executed_price = current_price

                result["action"] = "take_profit"
                result["close_pct"] = tp_level.close_pct
                result["reason"] = f"第{tp_level.level}止盈位触发 ({current_price:.2f})"

                # 更新状态
                if tp_level.level == 1:
                    plan.status = TakeProfitStatus.TP1_HIT
                elif tp_level.level == 2:
                    plan.status = TakeProfitStatus.TP2_HIT

                logger.info(f"止盈触发: {plan.symbol} TP{tp_level.level} 价格={current_price:.2f}")
                break

        # 检查止损
        should_sl = False
        if plan.direction == "buy" and current_price <= plan.stop_loss:
            should_sl = True
        elif plan.direction == "sell" and current_price >= plan.stop_loss:
            should_sl = True

        if should_sl:
            result["action"] = "stop_loss"
            result["close_pct"] = self._get_remaining_pct(plan)
            result["reason"] = f"止损触发 ({current_price:.2f})"
            plan.status = TakeProfitStatus.STOPPED_OUT
            logger.info(f"止损触发: {plan.symbol} 价格={current_price:.2f}")
            return result

        # 移动止损逻辑
        if self.trailing_stop_enabled and plan.status == TakeProfitStatus.TP2_HIT:
            new_trailing_stop = self._calculate_trailing_stop(plan)

            if new_trailing_stop is not None:
                plan.trailing_stop = new_trailing_stop
                result["new_stop_loss"] = new_trailing_stop
                result["action"] = "trailing_stop"
                result["reason"] = f"移动止损更新为 {new_trailing_stop:.2f}"

                # 检查是否触发移动止损
                should_trailing_sl = False
                if plan.direction == "buy" and current_price <= new_trailing_stop:
                    should_trailing_sl = True
                elif plan.direction == "sell" and current_price >= new_trailing_stop:
                    should_trailing_sl = True

                if should_trailing_sl:
                    result["action"] = "stop_loss"
                    result["close_pct"] = self._get_remaining_pct(plan)
                    result["reason"] = f"移动止损触发 ({current_price:.2f})"
                    plan.status = TakeProfitStatus.STOPPED_OUT
                    logger.info(f"移动止损触发: {plan.symbol} 价格={current_price:.2f}")

        # 保本止损逻辑
        if self.breakeven_enabled:
            new_stop = self._calculate_breakeven_stop(plan)
            if new_stop is not None and new_stop != plan.stop_loss:
                plan.stop_loss = new_stop
                result["new_stop_loss"] = new_stop
                result["reason"] = f"保本止损激活 ({new_stop:.2f})"

        return result

    def _calculate_trailing_stop(self, plan: ExitPlan) -> Optional[float]:
        """计算移动止损"""
        if plan.direction == "buy":
            profit_pct = (plan.highest_price - plan.entry_price) / plan.entry_price

            if profit_pct >= self.trailing_activation_pct:
                trailing_stop = plan.highest_price * (1 - self.trailing_distance_pct)
                # 确保移动止损不低于入场价
                trailing_stop = max(trailing_stop, plan.entry_price * (1 - self.final_stop_pct))

                # 只向有利方向调整
                if plan.trailing_stop is None or trailing_stop > plan.trailing_stop:
                    return trailing_stop
        else:
            profit_pct = (plan.entry_price - plan.lowest_price) / plan.entry_price

            if profit_pct >= self.trailing_activation_pct:
                trailing_stop = plan.lowest_price * (1 + self.trailing_distance_pct)
                # 确保移动止损不高于入场价
                trailing_stop = min(trailing_stop, plan.entry_price * (1 + self.final_stop_pct))

                # 只向有利方向调整
                if plan.trailing_stop is None or trailing_stop < plan.trailing_stop:
                    return trailing_stop

        return None

    def _calculate_breakeven_stop(self, plan: ExitPlan) -> Optional[float]:
        """计算保本止损"""
        if plan.direction == "buy":
            profit_pct = (plan.highest_price - plan.entry_price) / plan.entry_price
            if profit_pct >= self.breakeven_pct:
                breakeven_stop = plan.entry_price * (1 + 0.001)  # 略高于入场价
                if breakeven_stop > plan.stop_loss:
                    return breakeven_stop
        else:
            profit_pct = (plan.entry_price - plan.lowest_price) / plan.entry_price
            if profit_pct >= self.breakeven_pct:
                breakeven_stop = plan.entry_price * (1 - 0.001)  # 略低于入场价
                if breakeven_stop < plan.stop_loss:
                    return breakeven_stop

        return None

    def _get_remaining_pct(self, plan: ExitPlan) -> float:
        """获取剩余仓位比例"""
        closed_pct = sum(l.close_pct for l in plan.tp_levels if l.executed)
        return 1.0 - closed_pct

    def get_plan_summary(self, plan: ExitPlan) -> Dict:
        """获取计划摘要"""
        remaining_pct = self._get_remaining_pct(plan)
        total_profit_pct = 0.0

        if plan.direction == "buy":
            total_profit_pct = (plan.current_price - plan.entry_price) / plan.entry_price
        else:
            total_profit_pct = (plan.entry_price - plan.current_price) / plan.entry_price

        return {
            "symbol": plan.symbol,
            "direction": plan.direction,
            "entry_price": plan.entry_price,
            "current_price": plan.current_price,
            "stop_loss": plan.stop_loss,
            "trailing_stop": plan.trailing_stop,
            "status": plan.status.value,
            "remaining_pct": remaining_pct,
            "total_profit_pct": total_profit_pct,
            "tp_levels": [
                {
                    "level": l.level,
                    "price": l.price,
                    "close_pct": l.close_pct,
                    "executed": l.executed
                }
                for l in plan.tp_levels
            ]
        }

    def close_plan(self, plan: ExitPlan, reason: str = ""):
        """关闭退出计划"""
        plan.status = TakeProfitStatus.ALL_CLOSED if reason != "stopped_out" else TakeProfitStatus.STOPPED_OUT
        if plan in self.active_plans:
            self.active_plans.remove(plan)
        logger.info(f"关闭退出计划: {plan.symbol} 原因={reason}")

    def get_active_plan(self, symbol: str) -> Optional[ExitPlan]:
        """获取指定品种的活跃退出计划"""
        for plan in self.active_plans:
            if plan.symbol == symbol and plan.status not in [
                TakeProfitStatus.ALL_CLOSED, TakeProfitStatus.STOPPED_OUT
            ]:
                return plan
        return None


def create_partial_take_profit_strategy(config: Dict = None) -> PartialTakeProfitStrategy:
    """创建分批止盈策略"""
    return PartialTakeProfitStrategy(config)


if __name__ == "__main__":
    # 测试代码
    strategy = PartialTakeProfitStrategy()

    print("\n=== 测试分批止盈策略 ===")

    # 创建退出计划
    plan = strategy.create_exit_plan(
        symbol="BTCUSDT",
        direction="buy",
        entry_price=40000,
        stop_loss=39200  # 2%止损
    )

    print("\n退出计划:")
    summary = strategy.get_plan_summary(plan)
    print(f"  品种: {summary['symbol']}")
    print(f"  方向: {summary['direction']}")
    print(f"  入场价: {summary['entry_price']}")
    print(f"  止损价: {summary['stop_loss']}")
    print(f"  状态: {summary['status']}")

    print("\n止盈层级:")
    for tp_level in summary['tp_levels']:
        status = "已触发" if tp_level['executed'] else "未触发"
        print(f"  TP{tp_level['level']}: 价格={tp_level['price']:.2f}, 平仓={tp_level['close_pct']:.0%}, {status}")

    # 模拟价格上涨过程
    print("\n模拟价格上涨过程:")

    prices = [40000, 40100, 40200, 40300, 40400, 41600, 42500, 43200, 43900, 43500]
    for price in prices:
        result = strategy.update_price(plan, price)
        status_icon = "✓" if result["action"] != "hold" else "•"

        if result["action"] == "take_profit":
            print(f"  {status_icon} 价格={price:.2f}: {result['reason']} 平仓{result['close_pct']:.0%}")
        elif result["action"] == "stop_loss":
            print(f"  {status_icon} 价格={price:.2f}: {result['reason']} 平仓{result['close_pct']:.0%}")
            break
        elif result["action"] == "trailing_stop":
            print(f"  {status_icon} 价格={price:.2f}: {result['reason']}")
        else:
            profit_pct = (price - 40000) / 40000
            print(f"  {status_icon} 价格={price:.2f}: 盈利{profit_pct:.1%}")

    # 最终摘要
    print("\n最终状态:")
    summary = strategy.get_plan_summary(plan)
    print(f"  剩余仓位: {summary['remaining_pct']:.0%}")
    print(f"  总盈利: {summary['total_profit_pct']:.1%}")
    print(f"  移动止损: {summary['trailing_stop']:.2f}" if summary['trailing_stop'] else "  移动止损: 未激活")
