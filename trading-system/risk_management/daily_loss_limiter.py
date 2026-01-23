# Daily Loss Limit Module
# Set maximum daily loss percentage to protect account from emotional trading

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, date, timedelta
import logging

logger = logging.getLogger(__name__)


class LimitAction(Enum):
    """Action when limit is reached"""
    CONTINUE = "continue"             # Continue trading normally
    REDUCE_SIZE = "reduce_size"      # Reduce position size
    PAUSE_TRADING = "pause_trading"   # Stop trading for today
    EMERGENCY_STOP = "emergency_stop"   # Emergency stop all trading


@dataclass
class DailyLossState:
    """Daily loss tracking state"""
    date: date
    starting_balance: float
    current_balance: float
    daily_pnl: float
    daily_pnl_pct: float
    loss_count: int
    max_drawdown: float
    action_taken: List[str]
    is_limit_reached: bool


@dataclass
class LimitCheckResult:
    """Result of limit check"""
    can_trade: bool
    action: LimitAction
    position_multiplier: float      # 0-1, adjustment to position size
    remaining_risk: float          # Remaining allowed loss for today
    reason: str


class DailyLossLimiter:
    """Daily loss limiter"""

    def __init__(self, config: Dict = None):
        self.config = config or {}

        # Loss limit configuration
        self.max_daily_loss_pct = self.config.get("max_daily_loss_pct", 0.05)  # 5% max daily loss
        self.warning_threshold_pct = self.config.get("warning_threshold_pct", 0.03)  # 3% warning
        self.emergency_threshold_pct = self.config.get("emergency_threshold_pct", 0.10)  # 10% emergency stop

        # Multi-level actions
        self.stage1_threshold = self.config.get("stage1_threshold", 0.02)    # 2% - reduce to 50%
        self.stage2_threshold = self.config.get("stage2_threshold", 0.04)    # 4% - reduce to 25%
        self.stage3_threshold = self.config.get("stage3_threshold", 0.05)    # 5% - stop trading

        # Multipliers for position size reduction
        self.stage1_multiplier = self.config.get("stage1_multiplier", 0.5)  # 50%
        self.stage2_multiplier = self.config.get("stage2_multiplier", 0.25)  # 25%

        # Daily state
        self.today = date.today()
        self.daily_state = DailyLossState(
            date=self.today,
            starting_balance=0.0,
            current_balance=0.0,
            daily_pnl=0.0,
            daily_pnl_pct=0.0,
            loss_count=0,
            max_drawdown=0.0,
            action_taken=[],
            is_limit_reached=False
        )

        # Trading history for analysis
        self.daily_trades: List[Dict] = []

        # Reset time (auto reset at midnight or reset day)
        self.reset_time = self.config.get("reset_time", "00:00")  # Reset at midnight

    def initialize_day(self, starting_balance: float):
        """
        Initialize a new trading day

        Args:
            starting_balance: Starting balance for the day
        """
        self.today = date.today()
        self.daily_state = DailyLossState(
            date=self.today,
            starting_balance=starting_balance,
            current_balance=starting_balance,
            daily_pnl=0.0,
            daily_pnl_pct=0.0,
            loss_count=0,
            max_drawdown=0.0,
            action_taken=[],
            is_limit_reached=False
        )
        self.daily_trades = []
        logger.info(f"新交易日初始化，起始余额: {starting_balance:.2f}")

    def update_balance(self, new_balance: float):
        """
        Update current balance and recalculate daily PnL

        Args:
            new_balance: New account balance
        """
        old_balance = self.daily_state.current_balance
        self.daily_state.current_balance = new_balance

        # Calculate daily PnL
        pnl = new_balance - self.daily_state.starting_balance
        self.daily_state.daily_pnl = pnl
        self.daily_state.daily_pnl_pct = pnl / self.daily_state.starting_balance

        # Track max drawdown
        if pnl < self.daily_state.max_drawdown:
            self.daily_state.max_drawdown = pnl

        logger.info(
            f"余额更新: {old_balance:.2f} -> {new_balance:.2f}, "
            f"当日PnL: {pnl:+.2f} ({self.daily_state.daily_pnl_pct:+.2%})"
        )

    def record_trade(self, pnl: float, symbol: str, entry_price: float,
                  exit_price: float, size: float):
        """
        Record a trade result

        Args:
            pnl: Trade PnL
            symbol: Trading symbol
            entry_price: Entry price
            exit_price: Exit price
            size: Position size
        """
        self.daily_trades.append({
            "timestamp": datetime.now(),
            "symbol": symbol,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "size": size,
            "pnl": pnl,
            "pnl_pct": pnl / (entry_price * size) if size > 0 else 0
        })

        if pnl < 0:
            self.daily_state.loss_count += 1

        # Update balance
        self.update_balance(self.daily_state.current_balance + pnl)

    def check_limit(self) -> LimitCheckResult:
        """
        Check if daily trading is allowed

        Returns:
            LimitCheckResult
        """
        current_loss_pct = abs(self.daily_state.daily_pnl_pct)

        # Check emergency stop
        if current_loss_pct >= self.emergency_threshold_pct:
            logger.warning(f"触发紧急停止: 亏损{current_loss_pct:.2%} >= {self.emergency_threshold_pct:.0%}")
            self.daily_state.action_taken.append("emergency_stop")
            self.daily_state.is_limit_reached = True

            return LimitCheckResult(
                can_trade=False,
                action=LimitAction.EMERGENCY_STOP,
                position_multiplier=0.0,
                remaining_risk=0.0,
                reason=f"触发紧急停止：当日亏损{current_loss_pct:.2%}达到{self.emergency_threshold_pct:.0%}"
            )

        # Check max daily loss (stop trading)
        if current_loss_pct >= self.stage3_threshold:
            logger.warning(f"触发阶段3限制: 亏损{current_loss_pct:.2%} >= {self.stage3_threshold:.0%}")
            self.daily_state.action_taken.append("pause_trading")
            self.daily_state.is_limit_reached = True

            remaining_risk = self.max_daily_loss_pct - current_loss_pct

            return LimitCheckResult(
                can_trade=False,
                action=LimitAction.PAUSE_TRADING,
                position_multiplier=0.0,
                remaining_risk=max(0, remaining_risk),
                reason=f"触发交易暂停：当日亏损{current_loss_pct:.2%}达到{self.stage3_threshold:.0%}"
            )

        # Check stage 2 (reduce to 25%)
        if current_loss_pct >= self.stage2_threshold:
            logger.info(f"触发阶段2限制: 亏损{current_loss_pct:.2%} >= {self.stage2_threshold:.0%}")
            if "stage2_reduction" not in self.daily_state.action_taken:
                self.daily_state.action_taken.append("stage2_reduction")

            remaining_risk = self.stage3_threshold - current_loss_pct

            return LimitCheckResult(
                can_trade=True,
                action=LimitAction.REDUCE_SIZE,
                position_multiplier=self.stage2_multiplier,
                remaining_risk=remaining_risk,
                reason=f"触发仓位缩减：当日亏损{current_loss_pct:.2%}，仓位缩减至{self.stage2_multiplier:.0%}"
            )

        # Check stage 1 (reduce to 50%)
        if current_loss_pct >= self.stage1_threshold:
            logger.info(f"触发阶段1限制: 亏损{current_loss_pct:.2%} >= {self.stage1_threshold:.0%}")
            if "stage1_reduction" not in self.daily_state.action_taken:
                self.daily_state.action_taken.append("stage1_reduction")

            remaining_risk = self.stage3_threshold - current_loss_pct

            return LimitCheckResult(
                can_trade=True,
                action=LimitAction.REDUCE_SIZE,
                position_multiplier=self.stage1_multiplier,
                remaining_risk=remaining_risk,
                reason=f"触发仓位缩减：当日亏损{current_loss_pct:.2%}，仓位缩减至{self.stage1_multiplier:.0%}"
            )

        # Warning threshold - log but continue trading
        if current_loss_pct >= self.warning_threshold_pct:
            if "warning" not in self.daily_state.action_taken:
                self.daily_state.action_taken.append("warning")
            logger.warning(f"达到警告阈值：当日亏损{current_loss_pct:.2%}")

        # Normal trading
        remaining_risk = self.max_daily_loss_pct - current_loss_pct

        return LimitCheckResult(
            can_trade=True,
            action=LimitAction.CONTINUE,
            position_multiplier=1.0,
            remaining_risk=remaining_risk,
            reason="正常交易，未达到限制"
        )

    def should_trade(self) -> Tuple[bool, str, float]:
        """
        Quick check if trading is allowed

        Returns:
            (should_trade: bool, reason: str, position_multiplier: float)
        """
        result = self.check_limit()

        return result.can_trade, result.reason, result.position_multiplier

    def get_adjusted_position_size(self, base_size: float) -> float:
        """
        Get position size adjusted for daily loss limit

        Args:
            base_size: Base position size

        Returns:
            Adjusted position size
        """
        check_result = self.check_limit()
        return base_size * check_result.position_multiplier

    def get_daily_summary(self) -> Dict:
        """Get daily trading summary"""
        return {
            "date": self.daily_state.date.isoformat(),
            "starting_balance": self.daily_state.starting_balance,
            "current_balance": self.daily_state.current_balance,
            "daily_pnl": self.daily_state.daily_pnl,
            "daily_pnl_pct": self.daily_state.daily_pnl_pct,
            "loss_count": self.daily_state.loss_count,
            "max_drawdown": self.daily_state.max_drawdown,
            "max_loss_limit_pct": self.max_daily_loss_pct,
            "actions_taken": self.daily_state.action_taken,
            "is_limit_reached": self.daily_state.is_limit_reached,
            "total_trades": len(self.daily_trades),
            "trade_summary": {
                "total_trades": len(self.daily_trades),
                "winning_trades": sum(1 for t in self.daily_trades if t["pnl"] > 0),
                "losing_trades": sum(1 for t in self.daily_trades if t["pnl"] < 0),
                "avg_pnl": sum(t["pnl"] for t in self.daily_trades) / len(self.daily_trades) if self.daily_trades else 0
            }
        }

    def reset_daily(self):
        """Reset daily tracking (call at start of new day)"""
        if self.today != date.today():
            logger.info("检测到新的一天，重置日亏损限制")
            self.initialize_day(self.daily_state.current_balance)
        else:
            logger.info("重置日亏损限制状态")
            self.initialize_day(self.daily_state.current_balance)

    def set_emergency_stop(self):
        """Manually set emergency stop (e.g., user intervention)"""
        logger.warning("手动设置紧急停止")
        self.daily_state.action_taken.append("manual_emergency")
        self.daily_state.is_limit_reached = True

    def clear_emergency_stop(self):
        """Clear emergency stop state"""
        if "manual_emergency" in self.daily_state.action_taken:
            self.daily_state.action_taken.remove("manual_emergency")
            logger.info("已清除手动紧急停止状态")
            self.check_limit()  # Re-evaluate


def create_daily_loss_limiter(config: Dict = None) -> DailyLossLimiter:
    """Create daily loss limiter"""
    return DailyLossLimiter(config)


if __name__ == "__main__":
    # Test code
    limiter = DailyLossLimiter()

    print("\n=== Testing Daily Loss Limiter ===")

    # Initialize with starting balance
    limiter.initialize_day(10000.0)

    print("\nInitial state:")
    summary = limiter.get_daily_summary()
    print(f"  Starting: ${summary['starting_balance']:.2f}")
    print(f"  Max loss limit: {summary['max_loss_limit_pct']:.0%}")

    # Simulate trading with losses
    test_trades = [
        (150, "BTCUSDT", 40000, 39800, 0.1),   # Win
        (-80, "BTCUSDT", 39800, 39680, 0.1),   # Loss
        (-120, "BTCUSDT", 39680, 39480, 0.15), # Loss
        (200, "BTCUSDT", 39480, 39800, 0.12), # Win
        (-180, "BTCUSDT", 39800, 39580, 0.12), # Loss
    ]

    print("\nSimulating trades:")
    for i, (pnl, symbol, entry, exit_price, size) in enumerate(test_trades, 1):
        print(f"\nTrade {i}:")
        limiter.record_trade(pnl, symbol, entry, exit_price, size)

        # Check if can trade
        can_trade, reason, multiplier = limiter.should_trade()
        print(f"  PnL: {pnl:+.2f}")
        print(f"  Can trade: {can_trade}")
        print(f"  Reason: {reason}")
        print(f"  Position multiplier: {multiplier:.2f}")

        # Test position size adjustment
        base_size = 0.1
        adjusted_size = limiter.get_adjusted_position_size(base_size)
        if multiplier < 1.0:
            print(f"  Adjusted size: {base_size} -> {adjusted_size:.4f}")

    # Final summary
    print("\nFinal daily summary:")
    summary = limiter.get_daily_summary()
    print(f"  Daily PnL: {summary['daily_pnl']:+.2f} ({summary['daily_pnl_pct']:+.2%})")
    print(f"  Max drawdown: {summary['max_drawdown']:.2f}")
    print(f"  Loss count: {summary['loss_count']}")
    print(f"  Actions: {summary['actions_taken']}")
    print(f"  Total trades: {summary['trade_summary']['total_trades']}")
    print(f"  Win rate: {summary['trade_summary']['winning_trades']}/{summary['trade_summary']['total_trades']}")
