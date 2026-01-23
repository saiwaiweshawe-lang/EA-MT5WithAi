# 连续亏损降仓机制
# 连续亏损2笔后，下一笔仓位减半
# 连续亏损3笔后，当天停止交易
# 恢复盈利后逐步恢复仓位

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, date
import logging

logger = logging.getLogger(__name__)


class TradeStatus(Enum):
    """交易状态"""
    WIN = "win"
    LOSS = "loss"
    BREAKEVEN = "breakeven"


@dataclass
class TradeRecord:
    """交易记录"""
    symbol: str
    entry_price: float
    exit_price: float
    side: str
    size: float
    pnl: float
    pnl_pct: float
    status: TradeStatus
    timestamp: datetime
    notes: str = ""


@dataclass
class LossStreakState:
    """连续亏损状态"""
    current_streak: int                # 当前连续亏损次数
    max_streak: int                   # 历史最大连续亏损
    streak_start_time: Optional[datetime]
    daily_losses: int                   # 当日亏损次数
    last_win_date: Optional[date]        # 最后盈利日期


class LossStreakManager:
    """连续亏损管理器"""

    def __init__(self, config: Dict = None):
        self.config = config or {}

        # 亏损阈值配置
        self.consecutive_loss_threshold = self.config.get("consecutive_loss_threshold", 2)
        self.max_consecutive_losses = self.config.get("max_consecutive_losses", 3)
        self.daily_max_losses = self.config.get("daily_max_losses", 3)

        # 仓位调整因子
        self.loss_reduction_factor = self.config.get("loss_reduction_factor", 0.5)
        self.recovery_increase_factor = self.config.get("recovery_increase_factor", 1.2)
        self.base_multiplier = 1.0
        self.current_multiplier = 1.0
        self.min_multiplier = self.config.get("min_multiplier", 0.25)
        self.max_multiplier = self.config.get("max_multiplier", 1.0)

        # 冷却期配置（分钟）
        self.cooling_periods = self.config.get("cooling_periods", {
            2: 60,        # 连亏2笔，冷却1小时
            3: 180,       # 连亏3笔，冷却3小时
            4: 360        # 连亏4笔，冷却6小时
        })

        # 交易记录
        self.trade_records: List[TradeRecord] = []
        self.state = LossStreakState(
            current_streak=0,
            max_streak=0,
            streak_start_time=None,
            daily_losses=0,
            last_win_date=None
        )

        # 冷却期
        self.cooling_until: Optional[datetime] = None

    def add_trade(self, trade: TradeRecord):
        """
        添加交易记录

        参数:
            trade: 交易记录
        """
        self.trade_records.append(trade)

        today = date.today()
        is_today = trade.timestamp.date() == today

        if trade.status == TradeStatus.WIN:
            # 盈利，重置连续亏损
            self.state.current_streak = 0
            self.state.streak_start_time = None
            if is_today:
                self.state.daily_losses = 0
            self.state.last_win_date = today

            # 恢复仓位乘数
            self.current_multiplier = min(
                self.base_multiplier,
                self.current_multiplier * self.recovery_increase_factor
            )

            logger.info(
                f"交易盈利: {trade.symbol} 盈利{trade.pnl_pct:.2%} "
                f"连续亏损重置，当前乘数={self.current_multiplier:.2f}"
            )

        elif trade.status == TradeStatus.LOSS:
            # 亏损，增加连续计数
            self.state.current_streak += 1

            if self.state.streak_start_time is None:
                self.state.streak_start_time = trade.timestamp

            # 更新最大连续亏损
            if self.state.current_streak > self.state.max_streak:
                self.state.max_streak = self.state.current_streak

            # 当日亏损计数
            if is_today:
                self.state.daily_losses += 1

            # 调整仓位乘数
            if self.state.current_streak >= self.consecutive_loss_threshold:
                self.current_multiplier = max(
                    self.min_multiplier,
                    self.current_multiplier * self.loss_reduction_factor
                )

                # 设置冷却期
                cooling_minutes = self.cooling_periods.get(
                    min(self.state.current_streak, 4),
                    60
                )
                self.cooling_until = datetime.now() + timedelta(minutes=cooling_minutes)

            logger.info(
                f"交易亏损: {trade.symbol} 亏损{trade.pnl_pct:.2%} "
                f"连续{self.state.current_streak}笔，当前乘数={self.current_multiplier:.2f}"
            )

        # 限制乘数范围
        self.current_multiplier = max(
            self.min_multiplier,
            min(self.max_multiplier, self.current_multiplier)
        )

    def get_position_multiplier(self) -> float:
        """
        获取当前仓位乘数

        返回:
            仓位乘数 (0-1)
        """
        # 检查冷却期
        if self.cooling_until and datetime.now() < self.cooling_until:
            return 0.0

        return self.current_multiplier

    def should_trade(self) -> Tuple[bool, str]:
        """
        判断是否应该交易

        返回:
            (should_trade: bool, reason: str)
        """
        # 检查冷却期
        if self.cooling_until and datetime.now() < self.cooling_until:
            remaining = (self.cooling_until - datetime.now()).total_seconds() / 60
            return False, f"冷却期中，剩余{remaining:.0f}分钟"

        # 检查连续亏损限制
        if self.state.current_streak >= self.max_consecutive_losses:
            return False, f"连续亏损{self.state.current_streak}笔，达到当日上限"

        # 检查当日亏损限制
        today = date.today()
        is_today_loss_count = sum(
            1 for t in self.trade_records
            if t.status == TradeStatus.LOSS and t.timestamp.date() == today
        )
        if is_today_loss_count >= self.daily_max_losses:
            return False, f"今日已亏损{is_today_loss_count}笔，达到上限"

        return True, "允许交易"

    def get_adjusted_position_size(self, base_size: float) -> float:
        """
        获取调整后的仓位大小

        参数:
            base_size: 基础仓位大小

        返回:
            调整后的仓位大小
        """
        multiplier = self.get_position_multiplier()
        adjusted_size = base_size * multiplier

        logger.info(
            f"仓位调整: 基础={base_size:.4f} "
            f"乘数={multiplier:.2f} 调整后={adjusted_size:.4f}"
        )

        return adjusted_size

    def get_streak_summary(self) -> Dict:
        """获取连续亏损摘要"""
        return {
            "current_streak": self.state.current_streak,
            "max_streak": self.state.max_streak,
            "streak_duration_minutes": (
                (datetime.now() - self.state.streak_start_time).total_seconds() / 60
                if self.state.streak_start_time else 0
            ),
            "daily_losses": self.state.daily_losses,
            "last_win_date": self.state.last_win_date.isoformat() if self.state.last_win_date else None,
            "current_multiplier": self.current_multiplier,
            "base_multiplier": self.base_multiplier,
            "cooling_until": self.cooling_until.isoformat() if self.cooling_until else None
        }

    def reset_daily(self):
        """重置每日统计"""
        self.state.daily_losses = 0

    def reset_streak(self):
        """重置连续亏损"""
        self.state.current_streak = 0
        self.state.streak_start_time = None
        self.current_multiplier = self.base_multiplier
        self.cooling_until = None
        logger.info("连续亏损已重置")

    def get_recent_trades(self, count: int = 10) -> List[TradeRecord]:
        """获取最近的交易记录"""
        return self.trade_records[-count:]


def create_loss_streak_manager(config: Dict = None) -> LossStreakManager:
    """创建连续亏损管理器"""
    return LossStreakManager(config)


# 添加 timedelta 导入
from datetime import timedelta


if __name__ == "__main__":
    # 测试代码
    manager = LossStreakManager()

    print("\n=== 测试连续亏损降仓机制 ===")

    # 模拟交易
    trades = [
        ("BTCUSDT", 40000, 40400, "buy", 0.1, 0.01),
        ("BTCUSDT", 40000, 39700, "buy", 0.1, -0.0075),
        ("BTCUSDT", 40000, 39600, "buy", 0.1, -0.01),
        ("BTCUSDT", 40000, 39500, "buy", 0.1, -0.0125),
        ("BTCUSDT", 40000, 40200, "buy", 0.1, 0.005),
        ("BTCUSDT", 40000, 40300, "buy", 0.1, 0.0075),
    ]

    base_size = 0.1

    print("\n模拟交易过程:")
    for i, (symbol, entry, exit_price, side, size, pnl_pct) in enumerate(trades, 1):
        print(f"\n交易 {i}:")
        print(f"  品种: {symbol}")
        print(f"  方向: {side}")
        print(f"  入场: {entry}")
        print(f"  离场: {exit_price}")
        print(f"  盈亏: {pnl_pct:.2%}")

        # 创建交易记录
        if pnl_pct > 0:
            status = TradeStatus.WIN
        elif pnl_pct < 0:
            status = TradeStatus.LOSS
        else:
            status = TradeStatus.BREAKEVEN

        trade = TradeRecord(
            symbol=symbol,
            entry_price=entry,
            exit_price=exit_price,
            side=side,
            size=size,
            pnl=entry * pnl_pct,
            pnl_pct=pnl_pct,
            status=status,
            timestamp=datetime.now()
        )

        manager.add_trade(trade)

        # 检查是否应该交易
        should_trade, reason = manager.should_trade()
        print(f"  允许交易: {should_trade} - {reason}")

        # 获取调整后的仓位
        adjusted_size = manager.get_adjusted_position_size(base_size)
        print(f"  基础仓位: {base_size}")
        print(f"  调整后仓位: {adjusted_size:.4f}")

    # 最终摘要
    print("\n最终摘要:")
    summary = manager.get_streak_summary()
    print(f"  当前连续亏损: {summary['current_streak']}")
    print(f"  历史最大连续: {summary['max_streak']}")
    print(f"  当前仓位乘数: {summary['current_multiplier']:.2f}")
    print(f"  冷却期: {summary['cooling_until']}")

    print("\n最近交易:")
    recent_trades = manager.get_recent_trades(5)
    for trade in recent_trades:
        status_icon = "✓" if trade.status == TradeStatus.WIN else ("✗" if trade.status == TradeStatus.LOSS else "•")
        print(f"  {status_icon} {trade.symbol} {trade.pnl_pct:+.2%}")
