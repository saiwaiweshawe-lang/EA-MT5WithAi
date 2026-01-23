# Time-based Stop Loss Module
# Exit positions after maximum holding time to avoid low-efficiency positions

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class TimeStopAction(Enum):
    """Action when time stop is triggered"""
    FULL_CLOSE = "full_close"          # Close entire position
    PARTIAL_CLOSE = "partial_close"    # Close partial position
    EXTEND_TIME = "extend_time"       # Extend holding time
    WARNING_ONLY = "warning_only"        # Just warn, don't close


@dataclass
class TimeStopConfig:
    """Time stop configuration"""
    max_hold_time_minutes: int
    warning_time_minutes: int
    action: TimeStopAction
    partial_close_pct: float = 1.0


@dataclass
class TimeStopState:
    """Time stop tracking state"""
    symbol: str
    entry_time: datetime
    entry_price: float
    current_price: float
    pnl: float
    pnl_pct: float
    elapsed_minutes: float
    max_allowed_minutes: float
    warning_triggered: bool
    action_triggered: bool
    reason: str


@dataclass
class TimeStopCheck:
    """Time stop check result"""
    should_close: bool
    action: TimeStopAction
    close_pct: float              # Percentage to close (0-1)
    elapsed_minutes: float
    max_allowed_minutes: float
    reason: str


class TimeStopManager:
    """Time-based stop loss manager"""

    def __init__(self, config: Dict = None):
        self.config = config or {}

        # Default time limits (can be overridden per position)
        self.default_max_hold_time = self.config.get("max_hold_time_minutes", 240)  # 4 hours
        self.default_warning_time = self.config.get("warning_time_minutes", 180)  # 3 hours warning
        self.default_action = TimeStopAction(self.config.get("default_action", "full_close"))

        # Time-based adjustments
        self.enable_adaptive_time = self.config.get("enable_adaptive_time", True)
        self.volatility_time_multiplier = self.config.get("volatility_time_multiplier", 1.5)  # Extend time in high volatility

        # Trend-based adjustments
        self.trend_continue_time = self.config.get("trend_continue_time_minutes", 60)  # Add time if trend continues
        self.profitable_extension_time = self.config.get("profitable_extension_time_minutes", 30)  # Add time if profitable

        # Active time stop states
        self.active_stops: Dict[str, TimeStopState] = {}

        # Position-specific configurations
        self.position_configs: Dict[str, TimeStopConfig] = {}

    def set_position_config(self, symbol: str, config: TimeStopConfig):
        """
        Set custom time stop config for a specific position

        Args:
            symbol: Trading symbol
            config: Custom time stop configuration
        """
        self.position_configs[symbol] = config
        logger.info(f"设置{symbol}自定义时间止损配置: {config.max_hold_time_minutes}分钟")

    def enter_position(self, symbol: str, entry_price: float,
                    max_hold_minutes: Optional[int] = None):
        """
        Enter a new position and start time tracking

        Args:
            symbol: Trading symbol
            entry_price: Entry price
            max_hold_minutes: Custom max hold time (optional)
        """
        # Use position-specific config if available
        if symbol in self.position_configs:
            cfg = self.position_configs[symbol]
            max_time = cfg.max_hold_time_minutes
        else:
            max_time = max_hold_minutes or self.default_max_hold_time

        state = TimeStopState(
            symbol=symbol,
            entry_time=datetime.now(),
            entry_price=entry_price,
            current_price=entry_price,
            pnl=0.0,
            pnl_pct=0.0,
            elapsed_minutes=0.0,
            max_allowed_minutes=float(max_time),
            warning_triggered=False,
            action_triggered=False,
            reason="新持仓"
        )

        self.active_stops[symbol] = state
        logger.info(f"时间止损启动: {symbol} 入场价={entry_price:.2f} 最大时长={max_time}分钟")

    def update_position(self, symbol: str, current_price: float):
        """
        Update position state and check time stop

        Args:
            symbol: Trading symbol
            current_price: Current market price

        Returns:
            TimeStopCheck
        """
        if symbol not in self.active_stops:
            logger.warning(f"未找到{symbol}的时间止损状态")
            return TimeStopCheck(
                should_close=False,
                action=TimeStopAction.WARNING_ONLY,
                close_pct=0.0,
                elapsed_minutes=0.0,
                max_allowed_minutes=0.0,
                reason="未找到持仓状态"
            )

        state = self.active_stops[symbol]
        state.current_price = current_price

        # Calculate PnL
        if state.entry_price > 0:
            state.pnl = (current_price - state.entry_price)
            state.pnl_pct = state.pnl / state.entry_price

        # Calculate elapsed time
        elapsed = datetime.now() - state.entry_time
        elapsed_minutes = elapsed.total_seconds() / 60
        state.elapsed_minutes = elapsed_minutes

        # Check time stop conditions
        check = self._check_time_stop(state, symbol, current_price)
        state.warning_triggered = check.should_close or state.warning_triggered
        state.action_triggered = check.should_close
        state.reason = check.reason

        self.active_stops[symbol] = state
        return check

    def _check_time_stop(self, state: TimeStopState, symbol: str,
                       current_price: float) -> TimeStopCheck:
        """
        Check if time stop should be triggered

        Args:
            state: Time stop state
            symbol: Trading symbol
            current_price: Current price

        Returns:
            TimeStopCheck
        """
        max_allowed = state.max_allowed_minutes
        elapsed = state.elapsed_minutes

        # Get position-specific config if available
        if symbol in self.position_configs:
            cfg = self.position_configs[symbol]
            action = cfg.action
            close_pct = cfg.partial_close_pct
        else:
            action = self.default_action
            close_pct = 1.0

        # Check if over time limit
        if elapsed >= max_allowed:
            logger.warning(f"触发时间止损: {symbol} 已持有{elapsed:.0f}分钟，最大允许{max_allowed:.0f}分钟")
            return TimeStopCheck(
                should_close=True,
                action=action,
                close_pct=close_pct,
                elapsed_minutes=elapsed,
                max_allowed_minutes=max_allowed,
                reason=f"超过最大持有时间{max_allowed:.0f}分钟，执行{action.value}"
            )

        # Check warning threshold
        warning_time = self.default_warning_time
        if elapsed >= warning_time and not state.warning_triggered:
            logger.info(f"时间止损警告: {symbol} 已持有{elapsed:.0f}分钟，接近最大时间{max_allowed:.0f}分钟")

        # Check for extensions based on conditions
        extended_time = max_allowed

        if self.enable_adaptive_time:
            # Extend if profitable
            if state.pnl_pct > 0.005:  # Profitable > 0.5%
                extended_time += self.profitable_extension_time

            # Extend if trending (would need trend data)
            # This is simplified - in real use, integrate with trend analysis

        # Re-check with extended time
        if elapsed >= extended_time and extended_time > max_allowed:
            return TimeStopCheck(
                should_close=True,
                action=action,
                close_pct=close_pct,
                elapsed_minutes=elapsed,
                max_allowed_minutes=extended_time,
                reason=f"超过扩展时间{extended_time:.0f}分钟，执行{action.value}"
            )

        return TimeStopCheck(
            should_close=False,
            action=TimeStopAction.WARNING_ONLY,
            close_pct=0.0,
            elapsed_minutes=elapsed,
            max_allowed_minutes=extended_time,
            reason=f"正常持仓({elapsed:.0f}/{extended_time:.0f}分钟)"
        )

    def exit_position(self, symbol: str, reason: str = ""):
        """
        Exit a position and remove time stop tracking

        Args:
            symbol: Trading symbol
            reason: Exit reason
        """
        if symbol in self.active_stops:
            state = self.active_stops[symbol]
            logger.info(
                f"平仓{symbol}: 持有时间{state.elapsed_minutes:.0f}分钟 "
                f"盈亏{state.pnl:+.2f} ({state.pnl_pct:+.2%}) 原因: {reason}"
            )
            del self.active_stops[symbol]

    def get_active_positions_summary(self) -> List[Dict]:
        """Get summary of all active time stop positions"""
        summary = []

        for symbol, state in self.active_stops.items():
            summary.append({
                "symbol": symbol,
                "entry_time": state.entry_time.isoformat(),
                "elapsed_minutes": state.elapsed_minutes,
                "max_allowed_minutes": state.max_allowed_minutes,
                "pnl": state.pnl,
                "pnl_pct": state.pnl_pct,
                "time_remaining": max(0, state.max_allowed_minutes - state.elapsed_minutes),
                "warning_triggered": state.warning_triggered,
                "action_triggered": state.action_triggered
            })

        return summary

    def adjust_time_for_volatility(self, symbol: str, volatility_level: str):
        """
        Adjust time limits based on volatility

        Args:
            symbol: Trading symbol
            volatility_level: "low"/"normal"/"high"
        """
        if symbol not in self.active_stops:
            return

        state = self.active_stops[symbol]

        if volatility_level == "high":
            # Extend time in high volatility
            original_max = state.max_allowed_minutes / self.volatility_time_multiplier
            state.max_allowed_minutes = min(original_max * 1.5, 480)  # Max 8 hours
            logger.info(f"{symbol}高波动环境，延长持仓时间至{state.max_allowed_minutes:.0f}分钟")
        elif volatility_level == "low":
            # Reduce time in low volatility (expect faster moves)
            state.max_allowed_minutes = max(state.max_allowed_minutes * 0.7, 60)  # Min 1 hour
            logger.info(f"{symbol}低波动环境，缩短持仓时间至{state.max_allowed_minutes:.0f}分钟")


def create_time_stop_manager(config: Dict = None) -> TimeStopManager:
    """Create time stop manager"""
    return TimeStopManager(config)


if __name__ == "__main__":
    # Test code
    manager = TimeStopManager()

    print("\n=== Testing Time Stop Manager ===")

    # Enter a position
    manager.enter_position("BTCUSDT", 40000.0, max_hold_minutes=120)

    print("\nSimulating price movement over time:")
    import time
    from datetime import timedelta

    # Simulate 4 hours of trading
    base_price = 40000.0

    for i in range(1, 13):
        # Simulate time passing (10 minute intervals)
        elapsed = i * 10

        # Update price with random movement
        import random
        random.seed(i)
        price_change = random.uniform(-50, 50)
        current_price = base_price + price_change

        # Update position
        check = manager.update_position("BTCUSDT", current_price)

        status = "CLOSE" if check.should_close else "HOLD"
        print(f"  {elapsed:3d}m: Price={current_price:.2f} PnL={check.reason.split('盈亏')[1] if '盈亏' in check.reason else '0':.2f}%} Status={status}")

        # If should close, simulate exit
        if check.should_close:
            print(f"    Action: {check.action.value}, Close {check.close_pct:.0%}")
            manager.exit_position("BTCUSDT", check.reason)
            break
    else:
        manager.exit_position("BTCUSDT", "测试结束")

    # Final summary
    print("\nActive positions summary:")
    summary = manager.get_active_positions_summary()
    for pos in summary:
        print(f"  {pos['symbol']}: {pos['elapsed_minutes']:.0f}/{pos['max_allowed_minutes']:.0f}m, PnL={pos['pnl_pct']:+.2%}")
