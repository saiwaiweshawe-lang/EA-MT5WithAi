# 高级移动止盈止损引擎
# 支持多种移动止损策略,动态调整止盈止损

import logging
import time
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class TrailingStopStrategy(Enum):
    """移动止损策略类型"""
    PERCENTAGE = "percentage"  # 百分比移动
    ATR = "atr"  # 基于ATR
    SUPPORT_RESISTANCE = "support_resistance"  # 基于支撑阻力
    CHANDELIER = "chandelier"  # 吊灯止损
    PARABOLIC_SAR = "parabolic_sar"  # 抛物线SAR
    DYNAMIC = "dynamic"  # 动态综合


@dataclass
class TrailingStopConfig:
    """移动止损配置"""
    strategy: TrailingStopStrategy
    activation_profit_pct: float = 2.0  # 激活移动止损的盈利百分比
    trailing_distance_pct: float = 1.0  # 跟踪距离百分比
    step_size_pct: float = 0.5  # 移动步长百分比
    atr_multiplier: float = 2.0  # ATR倍数
    lock_profit_pct: float = 50.0  # 锁定利润百分比(保护已有利润的百分比)
    max_trailing_distance_pct: float = 5.0  # 最大跟踪距离
    min_trailing_distance_pct: float = 0.3  # 最小跟踪距离


@dataclass
class TrailingStopState:
    """移动止损状态"""
    symbol: str
    side: str
    entry_price: float
    current_price: float
    highest_price: float  # 多头最高价
    lowest_price: float  # 空头最低价
    current_sl: Optional[float] = None
    current_tp: Optional[float] = None
    trailing_sl: Optional[float] = None  # 移动止损价
    is_activated: bool = False  # 是否已激活移动止损
    locked_profit_pct: float = 0  # 已锁定利润百分比
    last_update_time: Optional[datetime] = None
    update_count: int = 0


class AdvancedTrailingStopEngine:
    """高级移动止盈止损引擎"""

    def __init__(self, config: Dict):
        self.config = config
        self.enabled = config.get("enabled", True)

        # 策略配置
        default_strategy = config.get("default_strategy", "dynamic")
        self.default_strategy = TrailingStopStrategy(default_strategy)

        self.default_config = TrailingStopConfig(
            strategy=self.default_strategy,
            activation_profit_pct=config.get("activation_profit_pct", 2.0),
            trailing_distance_pct=config.get("trailing_distance_pct", 1.0),
            step_size_pct=config.get("step_size_pct", 0.5),
            atr_multiplier=config.get("atr_multiplier", 2.0),
            lock_profit_pct=config.get("lock_profit_pct", 50.0),
            max_trailing_distance_pct=config.get("max_trailing_distance_pct", 5.0),
            min_trailing_distance_pct=config.get("min_trailing_distance_pct", 0.3)
        )

        # 持仓状态跟踪
        self.trailing_states: Dict[str, TrailingStopState] = {}

        # 指标系统(外部注入)
        self.indicator_system = None

    def set_indicator_system(self, indicator_system):
        """设置指标系统"""
        self.indicator_system = indicator_system

    def update_position(self, symbol: str, side: str, entry_price: float,
                       current_price: float, current_sl: Optional[float] = None,
                       current_tp: Optional[float] = None,
                       position_key: Optional[str] = None) -> Tuple[Optional[float], Optional[float]]:
        """
        更新持仓并计算新的止损止盈

        返回: (new_sl, new_tp)
        """
        if not self.enabled:
            return current_sl, current_tp

        # 生成唯一键
        key = position_key or f"{symbol}_{side}"

        # 获取或创建跟踪状态
        if key not in self.trailing_states:
            self.trailing_states[key] = TrailingStopState(
                symbol=symbol,
                side=side,
                entry_price=entry_price,
                current_price=current_price,
                highest_price=current_price if side == "long" else entry_price,
                lowest_price=current_price if side == "short" else entry_price,
                current_sl=current_sl,
                current_tp=current_tp
            )

        state = self.trailing_states[key]

        # 更新当前价格和极值
        state.current_price = current_price
        if side == "long":
            state.highest_price = max(state.highest_price, current_price)
        else:
            state.lowest_price = min(state.lowest_price, current_price)

        # 计算当前盈亏百分比
        if side == "long":
            profit_pct = ((current_price - entry_price) / entry_price) * 100
        else:
            profit_pct = ((entry_price - current_price) / entry_price) * 100

        # 检查是否激活移动止损
        if not state.is_activated:
            if profit_pct >= self.default_config.activation_profit_pct:
                state.is_activated = True
                logger.info(
                    f"✅ 移动止损已激活: {symbol} {side} "
                    f"(盈利{profit_pct:.2f}%)"
                )

        # 计算新的止损止盈
        new_sl, new_tp = self._calculate_trailing_stops(state, profit_pct)

        # 更新状态
        state.current_sl = new_sl
        state.current_tp = new_tp
        state.trailing_sl = new_sl
        state.last_update_time = datetime.now()
        state.update_count += 1

        # 计算已锁定利润
        if new_sl:
            if side == "long":
                state.locked_profit_pct = ((new_sl - entry_price) / entry_price) * 100
            else:
                state.locked_profit_pct = ((entry_price - new_sl) / entry_price) * 100

        return new_sl, new_tp

    def _calculate_trailing_stops(self, state: TrailingStopState,
                                  profit_pct: float) -> Tuple[Optional[float], Optional[float]]:
        """根据策略计算移动止损止盈"""

        strategy = self.default_config.strategy

        if strategy == TrailingStopStrategy.PERCENTAGE:
            return self._percentage_trailing(state, profit_pct)
        elif strategy == TrailingStopStrategy.ATR:
            return self._atr_trailing(state, profit_pct)
        elif strategy == TrailingStopStrategy.SUPPORT_RESISTANCE:
            return self._sr_trailing(state, profit_pct)
        elif strategy == TrailingStopStrategy.CHANDELIER:
            return self._chandelier_trailing(state, profit_pct)
        elif strategy == TrailingStopStrategy.PARABOLIC_SAR:
            return self._parabolic_sar_trailing(state, profit_pct)
        elif strategy == TrailingStopStrategy.DYNAMIC:
            return self._dynamic_trailing(state, profit_pct)
        else:
            return state.current_sl, state.current_tp

    def _percentage_trailing(self, state: TrailingStopState,
                           profit_pct: float) -> Tuple[Optional[float], Optional[float]]:
        """百分比移动止损"""
        if not state.is_activated:
            return state.current_sl, state.current_tp

        trailing_distance = self.default_config.trailing_distance_pct

        if state.side == "long":
            # 多头:止损跟随最高价下移
            new_sl = state.highest_price * (1 - trailing_distance / 100)

            # 确保止损只能上移,不能下移
            if state.current_sl:
                new_sl = max(new_sl, state.current_sl)

            # 保护利润:至少锁定X%已有利润
            min_protected_sl = state.entry_price * (
                1 + (profit_pct * self.default_config.lock_profit_pct / 100) / 100
            )
            new_sl = max(new_sl, min_protected_sl)

            # 止盈:保持当前或基于高点
            new_tp = state.current_tp or state.highest_price * 1.05

        else:  # short
            # 空头:止损跟随最低价上移
            new_sl = state.lowest_price * (1 + trailing_distance / 100)

            # 确保止损只能下移,不能上移
            if state.current_sl:
                new_sl = min(new_sl, state.current_sl)

            # 保护利润
            max_protected_sl = state.entry_price * (
                1 - (profit_pct * self.default_config.lock_profit_pct / 100) / 100
            )
            new_sl = min(new_sl, max_protected_sl)

            # 止盈
            new_tp = state.current_tp or state.lowest_price * 0.95

        return new_sl, new_tp

    def _atr_trailing(self, state: TrailingStopState,
                     profit_pct: float) -> Tuple[Optional[float], Optional[float]]:
        """基于ATR的移动止损"""
        if not state.is_activated or not self.indicator_system:
            return state.current_sl, state.current_tp

        try:
            # 获取ATR值
            indicators = self.indicator_system.get_signals(state.symbol)
            atr = indicators.get("atr", 0)

            if atr == 0:
                # 回退到百分比方法
                return self._percentage_trailing(state, profit_pct)

            atr_distance = atr * self.default_config.atr_multiplier

            if state.side == "long":
                new_sl = state.highest_price - atr_distance
                if state.current_sl:
                    new_sl = max(new_sl, state.current_sl)

                # 利润保护
                min_protected_sl = state.entry_price * (
                    1 + (profit_pct * self.default_config.lock_profit_pct / 100) / 100
                )
                new_sl = max(new_sl, min_protected_sl)

                new_tp = state.current_tp or (state.highest_price + atr_distance * 2)

            else:  # short
                new_sl = state.lowest_price + atr_distance
                if state.current_sl:
                    new_sl = min(new_sl, state.current_sl)

                max_protected_sl = state.entry_price * (
                    1 - (profit_pct * self.default_config.lock_profit_pct / 100) / 100
                )
                new_sl = min(new_sl, max_protected_sl)

                new_tp = state.current_tp or (state.lowest_price - atr_distance * 2)

            return new_sl, new_tp

        except Exception as e:
            logger.error(f"ATR移动止损计算失败: {e}")
            return self._percentage_trailing(state, profit_pct)

    def _sr_trailing(self, state: TrailingStopState,
                    profit_pct: float) -> Tuple[Optional[float], Optional[float]]:
        """基于支撑阻力的移动止损"""
        if not state.is_activated or not self.indicator_system:
            return state.current_sl, state.current_tp

        try:
            indicators = self.indicator_system.get_signals(state.symbol)
            support_levels = indicators.get("support_levels", [])
            resistance_levels = indicators.get("resistance_levels", [])

            if state.side == "long":
                # 多头:止损设在最近支撑位下方
                valid_supports = [s for s in support_levels
                                if s < state.current_price and s > state.entry_price]
                if valid_supports:
                    nearest_support = max(valid_supports)
                    new_sl = nearest_support * 0.995  # 支撑位下方0.5%
                else:
                    # 无有效支撑位,使用百分比方法
                    return self._percentage_trailing(state, profit_pct)

                # 确保止损只升不降
                if state.current_sl:
                    new_sl = max(new_sl, state.current_sl)

                # 止盈:最近阻力位
                valid_resistances = [r for r in resistance_levels
                                   if r > state.current_price]
                if valid_resistances:
                    new_tp = min(valid_resistances)
                else:
                    new_tp = state.current_tp

            else:  # short
                # 空头:止损设在最近阻力位上方
                valid_resistances = [r for r in resistance_levels
                                   if r > state.current_price and r < state.entry_price]
                if valid_resistances:
                    nearest_resistance = min(valid_resistances)
                    new_sl = nearest_resistance * 1.005  # 阻力位上方0.5%
                else:
                    return self._percentage_trailing(state, profit_pct)

                if state.current_sl:
                    new_sl = min(new_sl, state.current_sl)

                # 止盈:最近支撑位
                valid_supports = [s for s in support_levels
                                if s < state.current_price]
                if valid_supports:
                    new_tp = max(valid_supports)
                else:
                    new_tp = state.current_tp

            return new_sl, new_tp

        except Exception as e:
            logger.error(f"支撑阻力移动止损计算失败: {e}")
            return self._percentage_trailing(state, profit_pct)

    def _chandelier_trailing(self, state: TrailingStopState,
                           profit_pct: float) -> Tuple[Optional[float], Optional[float]]:
        """吊灯止损(Chandelier Exit)"""
        # 吊灯止损 = 最高价(或最低价) - ATR * 倍数
        return self._atr_trailing(state, profit_pct)

    def _parabolic_sar_trailing(self, state: TrailingStopState,
                               profit_pct: float) -> Tuple[Optional[float], Optional[float]]:
        """抛物线SAR移动止损"""
        if not state.is_activated or not self.indicator_system:
            return state.current_sl, state.current_tp

        try:
            # TODO: 实现真正的抛物线SAR计算
            # 这里简化为加速因子方法
            af_start = 0.02  # 起始加速因子
            af_increment = 0.02
            af_max = 0.2

            # 计算加速因子
            af = min(af_start + (state.update_count * af_increment), af_max)

            if state.side == "long":
                if state.current_sl:
                    # SAR上移
                    sar_movement = (state.highest_price - state.current_sl) * af
                    new_sl = state.current_sl + sar_movement
                else:
                    new_sl = state.entry_price * (1 - self.default_config.trailing_distance_pct / 100)

                new_sl = min(new_sl, state.current_price * 0.99)  # 不能太接近当前价
                new_tp = state.current_tp or state.highest_price * 1.05

            else:  # short
                if state.current_sl:
                    sar_movement = (state.current_sl - state.lowest_price) * af
                    new_sl = state.current_sl - sar_movement
                else:
                    new_sl = state.entry_price * (1 + self.default_config.trailing_distance_pct / 100)

                new_sl = max(new_sl, state.current_price * 1.01)
                new_tp = state.current_tp or state.lowest_price * 0.95

            return new_sl, new_tp

        except Exception as e:
            logger.error(f"抛物线SAR移动止损计算失败: {e}")
            return self._percentage_trailing(state, profit_pct)

    def _dynamic_trailing(self, state: TrailingStopState,
                         profit_pct: float) -> Tuple[Optional[float], Optional[float]]:
        """
        动态综合移动止损
        根据市场波动性和持仓状态选择最佳策略
        """
        if not state.is_activated:
            return state.current_sl, state.current_tp

        # 获取市场波动性
        volatility = "medium"
        if self.indicator_system:
            try:
                indicators = self.indicator_system.get_signals(state.symbol)
                volatility = indicators.get("volatility_level", "medium")
            except Exception as e:
                pass

        # 根据波动性选择策略
        if volatility == "high":
            # 高波动:使用ATR,给予更大空间
            sl_atr, tp_atr = self._atr_trailing(state, profit_pct)

            # 同时考虑百分比
            sl_pct, tp_pct = self._percentage_trailing(state, profit_pct)

            # 取较宽松的止损(给予更多空间)
            if state.side == "long":
                new_sl = min(sl_atr or float('inf'), sl_pct or float('inf'))
            else:
                new_sl = max(sl_atr or 0, sl_pct or 0)

            new_tp = tp_atr or tp_pct

        elif volatility == "low":
            # 低波动:使用支撑阻力,更精确
            sl_sr, tp_sr = self._sr_trailing(state, profit_pct)
            if sl_sr:
                new_sl, new_tp = sl_sr, tp_sr
            else:
                # 回退到百分比,但使用更小距离
                new_sl, new_tp = self._percentage_trailing(state, profit_pct)

        else:  # medium
            # 中等波动:综合多个策略
            sl_pct, tp_pct = self._percentage_trailing(state, profit_pct)
            sl_atr, tp_atr = self._atr_trailing(state, profit_pct)

            # 平均两者
            if sl_pct and sl_atr:
                if state.side == "long":
                    new_sl = (sl_pct + sl_atr) / 2
                    new_tp = max(tp_pct or 0, tp_atr or 0)
                else:
                    new_sl = (sl_pct + sl_atr) / 2
                    new_tp = min(tp_pct or float('inf'), tp_atr or float('inf'))
            else:
                new_sl, new_tp = sl_pct or sl_atr, tp_pct or tp_atr

        # 根据盈利阶段调整
        if profit_pct >= 10:
            # 大幅盈利:收紧止损,锁定更多利润
            if state.side == "long":
                new_sl = max(new_sl or 0, state.entry_price * (1 + profit_pct * 0.7 / 100))
            else:
                new_sl = min(new_sl or float('inf'),
                           state.entry_price * (1 - profit_pct * 0.7 / 100))
        elif profit_pct >= 5:
            # 中等盈利:锁定50%利润
            if state.side == "long":
                new_sl = max(new_sl or 0, state.entry_price * (1 + profit_pct * 0.5 / 100))
            else:
                new_sl = min(new_sl or float('inf'),
                           state.entry_price * (1 - profit_pct * 0.5 / 100))

        return new_sl, new_tp

    def remove_position(self, symbol: str, side: str, position_key: Optional[str] = None):
        """移除持仓跟踪"""
        key = position_key or f"{symbol}_{side}"
        if key in self.trailing_states:
            del self.trailing_states[key]
            logger.info(f"移除持仓跟踪: {key}")

    def get_position_state(self, symbol: str, side: str,
                          position_key: Optional[str] = None) -> Optional[TrailingStopState]:
        """获取持仓状态"""
        key = position_key or f"{symbol}_{side}"
        return self.trailing_states.get(key)

    def get_all_states(self) -> Dict[str, TrailingStopState]:
        """获取所有跟踪状态"""
        return self.trailing_states.copy()

    def get_summary(self) -> Dict:
        """获取引擎摘要"""
        active_positions = len(self.trailing_states)
        activated_count = sum(1 for s in self.trailing_states.values() if s.is_activated)

        return {
            "enabled": self.enabled,
            "default_strategy": self.default_strategy.value,
            "active_positions": active_positions,
            "activated_trailing_count": activated_count,
            "config": {
                "activation_profit_pct": self.default_config.activation_profit_pct,
                "trailing_distance_pct": self.default_config.trailing_distance_pct,
                "lock_profit_pct": self.default_config.lock_profit_pct
            }
        }
