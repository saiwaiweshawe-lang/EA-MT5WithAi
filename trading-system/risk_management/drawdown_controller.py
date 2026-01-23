# 回撤控制和仓位递减机制
# 监控账户回撤并在达到阈值时自动减小仓位或停止交易

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import logging
import json
import os

logger = logging.getLogger(__name__)


class DrawdownLevel(Enum):
    """回撤级别"""
    NORMAL = "normal"           # 正常
    WARNING = "warning"         # 警告
    MODERATE = "moderate"      # 中等
    SEVERE = "severe"          # 严重
    CRITICAL = "critical"      # 危险
    EMERGENCY = "emergency"    # 紧急


class ActionLevel(Enum):
    """行动级别"""
    NONE = "none"                          # 无操作
    REDUCE_POSITION = "reduce_position"      # 减小仓位
    CLOSE_NEW_POSITIONS = "close_new"       # 不开新仓
    CLOSE_ALL_POSITIONS = "close_all"       # 平所有仓
    EMERGENCY_STOP = "emergency_stop"       # 紧急停止


@dataclass
class DrawdownState:
    """回撤状态"""
    current_equity: float
    peak_equity: float
    current_drawdown: float
    current_drawdown_pct: float
    max_drawdown: float
    max_drawdown_pct: float
    level: DrawdownLevel
    daily_loss: float
    daily_loss_pct: float
    consecutive_losses: int
    recovery_trades: int = 0
    last_peak_date: Optional[datetime] = None
    last_drawdown_update: datetime = field(default_factory=datetime.now)


@dataclass
class RiskControlAction:
    """风险控制行动"""
    action: ActionLevel
    reason: str
    position_reduction_factor: float = 1.0
    new_risk_per_trade: Optional[float] = None
    stop_trading: bool = False
    close_all_positions: bool = False
    duration_minutes: Optional[int] = None
    timestamp: datetime = field(default_factory=datetime.now)


class DrawdownController:
    """回撤控制器"""

    def __init__(self, config: Dict = None):
        self.config = config or {}

        # 账户设置
        self.initial_equity = self.config.get("initial_equity", 10000.0)
        self.current_equity = self.initial_equity
        self.peak_equity = self.initial_equity
        self.max_equity = self.initial_equity

        # 回撤阈值配置
        self.drawdown_thresholds = self.config.get("drawdown_thresholds", {
            "warning": 0.03,        # 3% 警告
            "moderate": 0.05,       # 5% 中等
            "severe": 0.08,         # 8% 严重
            "critical": 0.12,        # 12% 危险
            "emergency": 0.15        # 15% 紧急
        })

        # 每日亏损限制
        self.daily_loss_limit_pct = self.config.get("daily_loss_limit_pct", 0.05)  # 5%
        self.daily_loss_limit_absolute = self.config.get("daily_loss_limit_absolute", 500.0)

        # 连续亏损控制
        self.max_consecutive_losses = self.config.get("max_consecutive_losses", 3)
        self.consecutive_loss_reduction = self.config.get("consecutive_loss_reduction", 0.5)

        # 仓位递减配置
        self.position_reduction_levels = self.config.get("position_reduction_levels", {
            3: 0.8,    # 连续3次亏损，仓位减至80%
            4: 0.6,    # 连续4次亏损，仓位减至60%
            5: 0.4,    # 连续5次亏损，仓位减至40%
            6: 0.2     # 连续6次亏损，仓位减至20%
        })

        # 恢复设置
        self.recovery_trades_threshold = self.config.get("recovery_trades_threshold", 3)
        self.recovery_increase_factor = self.config.get("recovery_increase_factor", 1.25)
        self.auto_recovery_enabled = self.config.get("auto_recovery_enabled", True)

        # 冷却期配置
        self.cooling_periods = self.config.get("cooling_periods", {
            "moderate": 60,       # 中等回撤后冷却60分钟
            "severe": 180,       # 严重回撤后冷却3小时
            "critical": 480,      # 危险回撤后冷却8小时
            "emergency": 1440    # 紧急回撤后冷却24小时
        })

        # 状态跟踪
        self.drawdown_state = self._init_drawdown_state()
        self.consecutive_losses = 0
        self.recovery_streak = 0
        self.is_in_cooling_period = False
        self.cooling_end_time: Optional[datetime] = None

        # 行动历史
        self.action_history: List[RiskControlAction] = []

        # 每日跟踪
        self.daily_start_equity = self.initial_equity
        self.daily_start_date = datetime.now().date()

        # 持久化配置
        self.state_file = self.config.get("state_file", "logs/drawdown_state.json")

        # 加载之前的状态
        self._load_state()

    def _init_drawdown_state(self) -> DrawdownState:
        """初始化回撤状态"""
        return DrawdownState(
            current_equity=self.current_equity,
            peak_equity=self.peak_equity,
            current_drawdown=0,
            current_drawdown_pct=0,
            max_drawdown=0,
            max_drawdown_pct=0,
            level=DrawdownLevel.NORMAL,
            daily_loss=0,
            daily_loss_pct=0,
            consecutive_losses=0,
            last_peak_date=datetime.now()
        )

    def update_equity(self, new_equity: float,
                     trade_pnl: float = 0,
                     is_daily_reset: bool = False):
        """
        更新账户权益

        参数:
            new_equity: 新的权益值
            trade_pnl: 本次交易盈亏
            is_daily_reset: 是否是每日重置
        """
        self.current_equity = new_equity

        # 更新历史最高权益
        if new_equity > self.max_equity:
            self.max_equity = new_equity
            self.drawdown_state.peak_equity = new_equity
            self.drawdown_state.last_peak_date = datetime.now()

        # 每日重置
        if is_daily_reset:
            self.daily_start_equity = new_equity
            self.daily_start_date = datetime.now().date()
            self.consecutive_losses = 0
            logger.info(f"每日重置: 起始权益 = {new_equity:.2f}")

        # 更新盈亏统计
        if trade_pnl < 0:
            self.consecutive_losses += 1
            self.recovery_streak = 0
        elif trade_pnl > 0:
            self.recovery_streak += 1
            if self.recovery_streak >= self.recovery_trades_threshold:
                self.consecutive_losses = max(0, self.consecutive_losses - 1)

        # 更新回撤状态
        self._update_drawdown_state()

        # 检查冷却期
        self._check_cooling_period()

        # 保存状态
        self._save_state()

    def _update_drawdown_state(self):
        """更新回撤状态"""
        state = self.drawdown_state
        state.current_equity = self.current_equity

        # 计算当前回撤
        if state.peak_equity > 0:
            state.current_drawdown = state.peak_equity - self.current_equity
            state.current_drawdown_pct = state.current_drawdown / state.peak_equity

        # 更新最大回撤
        if state.current_drawdown > state.max_drawdown:
            state.max_drawdown = state.current_drawdown
            state.max_drawdown_pct = state.max_drawdown / self.max_equity

        # 计算每日亏损
        state.daily_loss = self.daily_start_equity - self.current_equity
        if self.daily_start_equity > 0:
            state.daily_loss_pct = state.daily_loss / self.daily_start_equity

        state.consecutive_losses = self.consecutive_losses
        state.recovery_trades = self.recovery_streak
        state.last_drawdown_update = datetime.now()

        # 确定回撤级别
        state.level = self._determine_drawdown_level(
            state.current_drawdown_pct, state.daily_loss_pct, self.consecutive_losses
        )

        logger.debug(
            f"回撤状态: {state.level.value}, "
            f"当前回撤: {state.current_drawdown_pct:.2%}, "
            f"连续亏损: {self.consecutive_losses}"
        )

    def _determine_drawdown_level(self, drawdown_pct: float,
                                  daily_loss_pct: float,
                                  consecutive_losses: int) -> DrawdownLevel:
        """确定回撤级别"""
        thresholds = self.drawdown_thresholds

        # 检查紧急情况
        if (drawdown_pct >= thresholds["emergency"] or
            daily_loss_pct >= self.daily_loss_limit_pct * 2 or
            consecutive_losses >= 6):
            return DrawdownLevel.EMERGENCY

        # 检查危险情况
        if (drawdown_pct >= thresholds["critical"] or
            daily_loss_pct >= self.daily_loss_limit_pct * 1.5 or
            consecutive_losses >= 5):
            return DrawdownLevel.CRITICAL

        # 检查严重情况
        if (drawdown_pct >= thresholds["severe"] or
            daily_loss_pct >= self.daily_loss_limit_pct * 1.2 or
            consecutive_losses >= 4):
            return DrawdownLevel.SEVERE

        # 检查中等情况
        if (drawdown_pct >= thresholds["moderate"] or
            daily_loss_pct >= self.daily_loss_limit_pct or
            consecutive_losses >= 3):
            return DrawdownLevel.MODERATE

        # 检查警告情况
        if drawdown_pct >= thresholds["warning"]:
            return DrawdownLevel.WARNING

        return DrawdownLevel.NORMAL

    def check_action_required(self) -> Optional[RiskControlAction]:
        """检查是否需要采取行动"""
        state = self.drawdown_state

        # 检查冷却期
        if self.is_in_cooling_period:
            if datetime.now() < self.cooling_end_time:
                return RiskControlAction(
                    action=ActionLevel.NONE,
                    reason=f"处于冷却期，剩余 {(self.cooling_end_time - datetime.now()).total_seconds()/60:.0f} 分钟"
                )
            else:
                # 冷却期结束
                self.is_in_cooling_period = False
                self.cooling_end_time = None

        # 检查紧急情况
        if state.level == DrawdownLevel.EMERGENCY:
            return self._emergency_action()

        # 检查危险情况
        if state.level == DrawdownLevel.CRITICAL:
            return self._critical_action()

        # 检查严重情况
        if state.level == DrawdownLevel.SEVERE:
            return self._severe_action()

        # 检查中等情况
        if state.level == DrawdownLevel.MODERATE:
            return self._moderate_action()

        # 检查警告情况
        if state.level == DrawdownLevel.WARNING:
            return self._warning_action()

        # 检查恢复
        if self.auto_recovery_enabled and state.recovery_trades >= self.recovery_trades_threshold:
            if state.level != DrawdownLevel.NORMAL:
                return self._recovery_action()

        return None

    def _emergency_action(self) -> RiskControlAction:
        """紧急行动"""
        action = RiskControlAction(
            action=ActionLevel.EMERGENCY_STOP,
            reason=f"紧急情况: 当前回撤{self.drawdown_state.current_drawdown_pct:.2%}, "
                   f"连续亏损{self.consecutive_losses}次",
            close_all_positions=True,
            stop_trading=True,
            duration_minutes=self.cooling_periods["emergency"]
        )

        self._start_cooling_period(self.cooling_periods["emergency"])
        self._record_action(action)

        logger.critical(f"启动紧急停止: {action.reason}")
        return action

    def _critical_action(self) -> RiskControlAction:
        """危险行动"""
        # 启动冷却期
        self._start_cooling_period(self.cooling_periods["critical"])

        # 大幅减小仓位
        reduction_factor = 0.2
        new_risk = 0.005  # 0.5%

        action = RiskControlAction(
            action=ActionLevel.REDUCE_POSITION,
            reason=f"危险情况: 当前回撤{self.drawdown_state.current_drawdown_pct:.2%}",
            position_reduction_factor=reduction_factor,
            new_risk_per_trade=new_risk,
            stop_trading=True,
            duration_minutes=self.cooling_periods["critical"]
        )

        self._record_action(action)

        logger.error(f"启动危险响应: {action.reason}")
        return action

    def _severe_action(self) -> RiskControlAction:
        """严重行动"""
        # 启动冷却期
        self._start_cooling_period(self.cooling_periods["severe"])

        # 减小仓位
        reduction_factor = 0.4
        new_risk = 0.01  # 1%

        action = RiskControlAction(
            action=ActionLevel.REDUCE_POSITION,
            reason=f"严重情况: 当前回撤{self.drawdown_state.current_drawdown_pct:.2%}",
            position_reduction_factor=reduction_factor,
            new_risk_per_trade=new_risk,
            stop_trading=False,
            duration_minutes=self.cooling_periods["severe"]
        )

        self._record_action(action)

        logger.warning(f"启动严重响应: {action.reason}")
        return action

    def _moderate_action(self) -> RiskControlAction:
        """中等行动"""
        # 减小仓位
        reduction_factor = 0.6

        action = RiskControlAction(
            action=ActionLevel.REDUCE_POSITION,
            reason=f"中等回撤: 当前回撤{self.drawdown_state.current_drawdown_pct:.2%}",
            position_reduction_factor=reduction_factor
        )

        self._record_action(action)

        logger.warning(f"启动中等响应: {action.reason}")
        return action

    def _warning_action(self) -> RiskControlAction:
        """警告行动"""
        action = RiskControlAction(
            action=ActionLevel.NONE,
            reason=f"回撤警告: 当前回撤{self.drawdown_state.current_drawdown_pct:.2%}"
        )

        self._record_action(action)

        logger.info(f"回撤警告: {action.reason}")
        return action

    def _recovery_action(self) -> RiskControlAction:
        """恢复行动"""
        # 增加仓位
        increase_factor = self.recovery_increase_factor

        action = RiskControlAction(
            action=ActionLevel.NONE,
            reason=f"恢复中: 连续盈利{self.drawdown_state.recovery_trades}次",
            position_reduction_factor=min(increase_factor, 1.0)
        )

        logger.info(f"恢复响应: {action.reason}")
        return action

    def _start_cooling_period(self, duration_minutes: int):
        """启动冷却期"""
        self.is_in_cooling_period = True
        self.cooling_end_time = datetime.now() + timedelta(minutes=duration_minutes)
        logger.info(f"启动冷却期: {duration_minutes}分钟")

    def _check_cooling_period(self):
        """检查冷却期"""
        if self.is_in_cooling_period and self.cooling_end_time:
            if datetime.now() >= self.cooling_end_time:
                self.is_in_cooling_period = False
                self.cooling_end_time = None
                logger.info("冷却期结束，可以恢复交易")

    def get_position_reduction_factor(self) -> float:
        """获取仓位缩减因子"""
        # 基于连续亏损
        if self.consecutive_losses in self.position_reduction_levels:
            return self.position_reduction_levels[self.consecutive_losses]

        # 基于回撤级别
        level = self.drawdown_state.level
        if level == DrawdownLevel.SEVERE:
            return 0.5
        elif level == DrawdownLevel.CRITICAL:
            return 0.2
        elif level == DrawdownLevel.EMERGENCY:
            return 0.0  # 停止交易

        return 1.0

    def can_open_position(self) -> Tuple[bool, str]:
        """
        检查是否可以开仓

        返回:
            (can_open, reason)
        """
        # 检查冷却期
        if self.is_in_cooling_period:
            return False, f"处于冷却期，剩余 {(self.cooling_end_time - datetime.now()).total_seconds()/60:.0f} 分钟"

        # 检查紧急状态
        if self.drawdown_state.level == DrawdownLevel.EMERGENCY:
            return False, "紧急状态，禁止开仓"

        # 检查危险状态
        if self.drawdown_state.level == DrawdownLevel.CRITICAL:
            return False, "危险状态，禁止开仓"

        # 检查每日亏损限制
        daily_loss_pct = self.drawdown_state.daily_loss_pct
        if daily_loss_pct >= self.daily_loss_limit_pct:
            return False, f"已达到每日亏损限制: {daily_loss_pct:.2%}"

        # 检查连续亏损
        if self.consecutive_losses >= 6:
            return False, f"连续亏损过多: {self.consecutive_losses}次"

        return True, "可以开仓"

    def get_risk_report(self) -> Dict:
        """获取风险报告"""
        can_open, reason = self.can_open_position()
        last_action = self.action_history[-1] if self.action_history else None

        return {
            "current_equity": self.current_equity,
            "peak_equity": self.peak_equity,
            "max_equity": self.max_equity,
            "current_drawdown": self.drawdown_state.current_drawdown,
            "current_drawdown_pct": self.drawdown_state.current_drawdown_pct,
            "max_drawdown": self.drawdown_state.max_drawdown,
            "max_drawdown_pct": self.drawdown_state.max_drawdown_pct,
            "drawdown_level": self.drawdown_state.level.value,
            "daily_loss": self.drawdown_state.daily_loss,
            "daily_loss_pct": self.drawdown_state.daily_loss_pct,
            "consecutive_losses": self.consecutive_losses,
            "recovery_streak": self.drawdown_state.recovery_trades,
            "can_open_position": can_open,
            "cannot_open_reason": reason if not can_open else None,
            "is_in_cooling_period": self.is_in_cooling_period,
            "cooling_end_time": (
                self.cooling_end_time.isoformat() if self.cooling_end_time else None
            ),
            "position_reduction_factor": self.get_position_reduction_factor(),
            "last_action": {
                "action": last_action.action.value,
                "reason": last_action.reason,
                "timestamp": last_action.timestamp.isoformat()
            } if last_action else None,
            "action_count": len(self.action_history)
        }

    def _record_action(self, action: RiskControlAction):
        """记录行动"""
        self.action_history.append(action)

        # 保持最近100条记录
        if len(self.action_history) > 100:
            self.action_history.pop(0)

    def _save_state(self):
        """保存状态"""
        try:
            state = {
                "current_equity": self.current_equity,
                "max_equity": self.max_equity,
                "consecutive_losses": self.consecutive_losses,
                "recovery_streak": self.recovery_streak,
                "is_in_cooling_period": self.is_in_cooling_period,
                "cooling_end_time": (
                    self.cooling_end_time.isoformat() if self.cooling_end_time else None
                ),
                "daily_start_equity": self.daily_start_equity,
                "daily_start_date": self.daily_start_date.isoformat(),
                "drawdown_state": {
                    "current_drawdown_pct": self.drawdown_state.current_drawdown_pct,
                    "max_drawdown_pct": self.drawdown_state.max_drawdown_pct,
                    "level": self.drawdown_state.level.value
                }
            }

            os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)

        except Exception as e:
            logger.error(f"保存状态失败: {e}")

    def _load_state(self):
        """加载状态"""
        try:
            if not os.path.exists(self.state_file):
                return

            with open(self.state_file, 'r') as f:
                state = json.load(f)

            self.current_equity = state.get("current_equity", self.initial_equity)
            self.max_equity = state.get("max_equity", self.initial_equity)
            self.consecutive_losses = state.get("consecutive_losses", 0)
            self.recovery_streak = state.get("recovery_streak", 0)
            self.is_in_cooling_period = state.get("is_in_cooling_period", False)

            cooling_time = state.get("cooling_end_time")
            if cooling_time:
                self.cooling_end_time = datetime.fromisoformat(cooling_time)

            self.daily_start_equity = state.get("daily_start_equity", self.initial_equity)
            self.daily_start_date = datetime.fromisoformat(
                state.get("daily_start_date", datetime.now().date().isoformat())
            )

            # 更新回撤状态
            self.drawdown_state.current_equity = self.current_equity
            self.drawdown_state.peak_equity = self.max_equity

            if "drawdown_state" in state:
                ds = state["drawdown_state"]
                self.drawdown_state.current_drawdown_pct = ds.get("current_drawdown_pct", 0)
                self.drawdown_state.max_drawdown_pct = ds.get("max_drawdown_pct", 0)
                self.drawdown_state.level = DrawdownLevel(ds.get("level", "normal"))

            logger.info("回撤控制器状态已加载")

        except Exception as e:
            logger.error(f"加载状态失败: {e}")

    def reset_daily(self):
        """每日重置"""
        self.daily_start_equity = self.current_equity
        self.daily_start_date = datetime.now().date()
        logger.info(f"每日重置完成, 起始权益: {self.current_equity:.2f}")

    def full_reset(self):
        """完全重置"""
        self.current_equity = self.initial_equity
        self.peak_equity = self.initial_equity
        self.max_equity = self.initial_equity
        self.consecutive_losses = 0
        self.recovery_streak = 0
        self.is_in_cooling_period = False
        self.cooling_end_time = None
        self.action_history = []
        self.daily_start_equity = self.initial_equity
        self.daily_start_date = datetime.now().date()
        self.drawdown_state = self._init_drawdown_state()

        logger.warning("回撤控制器已完全重置")


def create_drawdown_controller(config: Dict = None) -> DrawdownController:
    """创建回撤控制器"""
    return DrawdownController(config)


if __name__ == "__main__":
    # 测试代码
    config = {
        "initial_equity": 10000.0,
        "drawdown_thresholds": {
            "warning": 0.03,
            "moderate": 0.05,
            "severe": 0.08,
            "critical": 0.12,
            "emergency": 0.15
        },
        "daily_loss_limit_pct": 0.05,
        "max_consecutive_losses": 3,
        "auto_recovery_enabled": True
    }

    controller = DrawdownController(config)

    print("\n=== 回撤控制器测试 ===\n")

    # 测试场景1: 逐步亏损
    print("场景1: 逐步亏损")
    equity = 10000
    for i in range(1, 6):
        equity -= 200 * i  # 累积亏损
        controller.update_equity(equity, trade_pnl=-200 * i)

        action = controller.check_action_required()
        can_open, reason = controller.can_open_position()

        print(f"\n第{i}次亏损后:")
        print(f"  权益: {equity:.2f}")
        print(f"  回撤: {controller.drawdown_state.current_drawdown_pct:.2%}")
        print(f"  级别: {controller.drawdown_state.level.value}")
        print(f"  可开仓: {can_open} ({reason})")
        if action:
            print(f"  建议行动: {action.action.value} - {action.reason}")

    # 测试场景2: 恢复
    print("\n\n场景2: 逐步恢复")
    equity = 9000
    for i in range(1, 5):
        equity += 300
        controller.update_equity(equity, trade_pnl=300)

        action = controller.check_action_required()
        can_open, reason = controller.can_open_position()

        print(f"\n第{i}次盈利后:")
        print(f"  权益: {equity:.2f}")
        print(f"  回撤: {controller.drawdown_state.current_drawdown_pct:.2%}")
        print(f"  级别: {controller.drawdown_state.level.value}")
        print(f"  可开仓: {can_open} ({reason})")
        if action:
            print(f"  建议行动: {action.action.value} - {action.reason}")

    # 测试场景3: 风险报告
    print("\n\n风险报告:")
    report = controller.get_risk_report()
    for key, value in report.items():
        print(f"  {key}: {value}")
