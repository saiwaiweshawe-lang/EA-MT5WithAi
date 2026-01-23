# 动态仓位管理系统
# 基于Kelly准则、ATR波动率、账户余额等多维度计算最优仓位

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import logging
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class RiskModel(Enum):
    """风险模型类型"""
    FIXED_PERCENTAGE = "fixed_percentage"      # 固定百分比
    FIXED_RISK = "fixed_risk"                  # 固定风险金额
    KELLY = "kelly"                            # Kelly准则
    OPTIMAL_F = "optimal_f"                    # 最优f分数
    VOLATILITY_ADJUSTED = "volatility_adjusted"  # 波动率调整
    COMPOSITE = "composite"                     # 综合模型


class VolatilityRegime(Enum):
    """波动率状态"""
    EXTREME_LOW = "extreme_low"      # 极低波动
    LOW = "low"                       # 低波动
    NORMAL = "normal"                 # 正常波动
    HIGH = "high"                     # 高波动
    EXTREME_HIGH = "extreme_high"     # 极高波动


@dataclass
class PositionSizeResult:
    """仓位计算结果"""
    symbol: str
    base_size: float                      # 基础仓位大小
    adjusted_size: float                  # 调整后仓位大小
    risk_amount: float                   # 风险金额
    risk_percentage: float               # 风险百分比
    stop_loss_distance: float             # 止损距离
    confidence: float                   # 置信度
    volatility_regime: VolatilityRegime  # 波动率状态
    adjustment_factors: Dict[str, float] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    recommended_leverage: float = 1.0


@dataclass
class TradeHistory:
    """交易历史数据"""
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_profit: float = 0.0
    total_loss: float = 0.0
    max_profit: float = 0.0
    max_loss: float = 0.0
    avg_profit: float = 0.0
    avg_loss: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    consecutive_losses: int = 0
    consecutive_wins: int = 0
    max_consecutive_losses: int = 0
    max_consecutive_wins: int = 0

    def update(self, pnl: float):
        """更新交易历史"""
        self.total_trades += 1

        if pnl > 0:
            self.winning_trades += 1
            self.total_profit += pnl
            self.max_profit = max(self.max_profit, pnl)
            self.consecutive_wins += 1
            self.consecutive_losses = 0
            self.max_consecutive_wins = max(self.max_consecutive_wins, self.consecutive_wins)
        else:
            self.losing_trades += 1
            self.total_loss += abs(pnl)
            self.max_loss = max(self.max_loss, abs(pnl))
            self.consecutive_losses += 1
            self.consecutive_wins = 0
            self.max_consecutive_losses = max(self.max_consecutive_losses, self.consecutive_losses)

        # 更新平均值
        if self.winning_trades > 0:
            self.avg_profit = self.total_profit / self.winning_trades
        if self.losing_trades > 0:
            self.avg_loss = self.total_loss / self.losing_trades

        # 更新胜率和盈亏比
        self.win_rate = self.winning_trades / self.total_trades if self.total_trades > 0 else 0
        if self.avg_loss > 0:
            self.profit_factor = self.avg_profit / self.avg_loss
        else:
            self.profit_factor = float('inf') if self.avg_profit > 0 else 0


class DynamicPositionSizer:
    """动态仓位计算器"""

    def __init__(self, config: Dict):
        self.config = config
        self.risk_model = RiskModel(config.get("risk_model", "composite"))

        # 基础风险参数
        self.base_risk_per_trade = config.get("base_risk_per_trade", 0.02)  # 2%
        self.max_risk_per_trade = config.get("max_risk_per_trade", 0.05)    # 5%
        self.max_total_risk = config.get("max_total_risk", 0.10)           # 10%

        # 账户管理
        self.account_balance = config.get("initial_balance", 10000.0)
        self.available_balance = self.account_balance
        self.used_margin = 0.0

        # 交易历史
        self.trade_history = TradeHistory()
        self.recent_trades = []  # 最近N笔交易
        self.max_recent_trades = config.get("max_recent_trades", 30)

        # 波动率参数
        self.atr_window = config.get("atr_window", 14)
        self.atr_multiplier = config.get("atr_multiplier", 2.0)
        self.volatility_adjustment_enabled = config.get("volatility_adjustment", True)

        # Kelly准则参数
        self.kelly_fraction = config.get("kelly_fraction", 0.5)  # 半Kelly
        self.min_kelly = config.get("min_kelly", 0.1)
        self.max_kelly = config.get("max_kelly", 0.25)

        # 连续亏损保护
        self.consecutive_loss_reduction = config.get("consecutive_loss_reduction", {
            "enabled": True,
            "threshold": 2,           # 连续2次亏损后开始减小
            "reduction_factor": 0.5,   # 每次亏损减少50%
            "reset_on_win": True
        })

        # 相关性控制
        self.max_correlated_exposure = config.get("max_correlated_exposure", 0.3)  # 30%
        self.correlation_threshold = config.get("correlation_threshold", 0.7)

        # 当前持仓
        self.current_positions: Dict[str, Dict] = {}

    def update_account_balance(self, new_balance: float):
        """更新账户余额"""
        self.account_balance = new_balance
        self.available_balance = new_balance - self.used_margin
        logger.info(f"账户余额更新: {new_balance:.2f}, 可用: {self.available_balance:.2f}")

    def record_trade(self, symbol: str, pnl: float, entry_price: float,
                    exit_price: float, size: float):
        """记录交易结果"""
        self.trade_history.update(pnl)

        # 添加到最近交易记录
        trade_record = {
            "symbol": symbol,
            "pnl": pnl,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "size": size,
            "timestamp": datetime.now()
        }
        self.recent_trades.append(trade_record)

        # 保持固定长度
        if len(self.recent_trades) > self.max_recent_trades:
            self.recent_trades.pop(0)

        logger.info(
            f"交易记录: {symbol} PNL={pnl:+.2f} "
            f"胜率={self.trade_history.win_rate:.2%} "
            f"盈亏比={self.trade_history.profit_factor:.2f}"
        )

    def calculate_position_size(self,
                             symbol: str,
                             current_price: float,
                             stop_loss_price: Optional[float] = None,
                             klines: Optional[List[Dict]] = None,
                             market_conditions: Optional[Dict] = None) -> PositionSizeResult:
        """
        计算最优仓位大小

        参数:
            symbol: 交易品种
            current_price: 当前价格
            stop_loss_price: 止损价格(可选)
            klines: K线数据(可选)
            market_conditions: 市场条件(可选)

        返回:
            PositionSizeResult
        """
        # 获取ATR
        atr = self._calculate_atr(klines) if klines else 0

        # 确定止损距离
        if stop_loss_price:
            stop_loss_distance = abs(current_price - stop_loss_price)
        elif atr > 0:
            stop_loss_distance = atr * self.atr_multiplier
        else:
            stop_loss_distance = current_price * 0.02  # 默认2%

        # 检测波动率状态
        volatility_regime = self._detect_volatility_regime(atr, current_price, klines)

        # 计算基础仓位
        base_size = self._calculate_base_size(
            current_price, stop_loss_distance, volatility_regime
        )

        # 计算调整因子
        adjustment_factors = {}

        # 1. 波动率调整
        if self.volatility_adjustment_enabled:
            vol_factor = self._get_volatility_adjustment_factor(volatility_regime)
            adjustment_factors["volatility"] = vol_factor

        # 2. 连续亏损调整
        loss_factor = self._get_consecutive_loss_factor()
        adjustment_factors["consecutive_loss"] = loss_factor

        # 3. 历史表现调整
        performance_factor = self._get_performance_adjustment_factor()
        adjustment_factors["performance"] = performance_factor

        # 4. 相关性调整
        correlation_factor = self._get_correlation_factor(symbol, market_conditions)
        adjustment_factors["correlation"] = correlation_factor

        # 5. 市场条件调整
        market_factor = self._get_market_condition_factor(market_conditions)
        adjustment_factors["market_condition"] = market_factor

        # 6. 总风险限制调整
        risk_limit_factor = self._get_risk_limit_factor()
        adjustment_factors["risk_limit"] = risk_limit_factor

        # 计算调整后仓位
        total_adjustment = np.prod(list(adjustment_factors.values()))
        adjusted_size = base_size * total_adjustment

        # 计算风险金额
        risk_amount = adjusted_size * stop_loss_distance
        risk_percentage = risk_amount / self.account_balance

        # 确保不超过最大风险
        if risk_percentage > self.max_risk_per_trade:
            adjusted_size = (self.account_balance * self.max_risk_per_trade) / stop_loss_distance
            risk_amount = adjusted_size * stop_loss_distance
            risk_percentage = self.max_risk_per_trade
            adjustment_factors["risk_limit"] = self.max_risk_per_trade / risk_percentage

        # 确保不超过可用保证金
        max_size_by_margin = self.available_balance / current_price
        if adjusted_size > max_size_by_margin:
            adjusted_size = max_size_by_margin * 0.95  # 保留5%缓冲
            risk_amount = adjusted_size * stop_loss_distance
            risk_percentage = risk_amount / self.account_balance

        # 计算置信度
        confidence = self._calculate_confidence(adjustment_factors, volatility_regime)

        # 生成警告
        warnings = self._generate_warnings(
            volatility_regime, risk_percentage, consecutive_losses=self.trade_history.consecutive_losses
        )

        # 计算推荐杠杆
        recommended_leverage = self._calculate_recommended_leverage(
            adjusted_size, current_price, risk_amount
        )

        return PositionSizeResult(
            symbol=symbol,
            base_size=base_size,
            adjusted_size=adjusted_size,
            risk_amount=risk_amount,
            risk_percentage=risk_percentage,
            stop_loss_distance=stop_loss_distance,
            confidence=confidence,
            volatility_regime=volatility_regime,
            adjustment_factors=adjustment_factors,
            warnings=warnings,
            recommended_leverage=recommended_leverage
        )

    def _calculate_base_size(self,
                            current_price: float,
                            stop_loss_distance: float,
                            volatility_regime: VolatilityRegime) -> float:
        """计算基础仓位大小"""

        if self.risk_model == RiskModel.FIXED_PERCENTAGE:
            # 固定百分比模型
            risk_amount = self.account_balance * self.base_risk_per_trade
            return risk_amount / stop_loss_distance

        elif self.risk_model == RiskModel.FIXED_RISK:
            # 固定风险金额
            risk_amount = self.config.get("fixed_risk_amount", 200)
            return risk_amount / stop_loss_distance

        elif self.risk_model == RiskModel.KELLY:
            # Kelly准则模型
            return self._kelly_sizing(current_price, stop_loss_distance)

        elif self.risk_model == RiskModel.OPTIMAL_F:
            # 最优f分数(Ralph Vince)
            return self._optimal_f_sizing(current_price, stop_loss_distance)

        elif self.risk_model == RiskModel.VOLATILITY_ADJUSTED:
            # 波动率调整模型
            vol_factor = self._get_volatility_adjustment_factor(volatility_regime)
            base_risk = self.base_risk_per_trade * vol_factor
            risk_amount = self.account_balance * base_risk
            return risk_amount / stop_loss_distance

        else:  # COMPOSITE
            # 综合模型 - 结合多种方法
            kelly_size = self._kelly_sizing(current_price, stop_loss_distance)
            fixed_size = (self.account_balance * self.base_risk_per_trade) / stop_loss_distance

            # 加权平均
            if self.trade_history.total_trades >= 10:
                # 有足够历史数据,更信任Kelly
                composite_size = kelly_size * 0.7 + fixed_size * 0.3
            else:
                # 数据不足,更保守
                composite_size = kelly_size * 0.3 + fixed_size * 0.7

            return composite_size

    def _kelly_sizing(self, current_price: float,
                     stop_loss_distance: float) -> float:
        """Kelly准则仓位计算"""
        if self.trade_history.total_trades < 10:
            # 数据不足,使用基础风险
            return (self.account_balance * self.base_risk_per_trade) / stop_loss_distance

        win_rate = self.trade_history.win_rate
        avg_win = self.trade_history.avg_profit
        avg_loss = self.trade_history.avg_loss

        if avg_loss == 0:
            return 0

        # Kelly公式: f = (p*b - q) / b
        # p = 胜率, q = 败率, b = 盈亏比
        b = avg_win / avg_loss
        kelly_f = (win_rate * b - (1 - win_rate)) / b

        # 限制Kelly范围
        kelly_f = max(self.min_kelly, min(kelly_f, self.max_kelly))

        # 应用半Kelly(更保守)
        kelly_f *= self.kelly_fraction

        # 计算仓位
        risk_amount = self.account_balance * kelly_f
        position_size = risk_amount / stop_loss_distance

        return position_size

    def _optimal_f_sizing(self, current_price: float,
                         stop_loss_distance: float) -> float:
        """最优f分数计算(Ralph Vince)"""
        if len(self.recent_trades) < 10:
            return (self.account_balance * self.base_risk_per_trade) / stop_loss_distance

        # 计算交易的ROI序列
        rois = []
        for trade in self.recent_trades:
            if trade["entry_price"] > 0:
                roi = trade["pnl"] / (trade["entry_price"] * trade["size"])
                rois.append(roi)

        if len(rois) < 5:
            return (self.account_balance * self.base_risk_per_trade) / stop_loss_distance

        # 简化版本:使用平均ROI和波动率
        avg_roi = np.mean(rois)
        std_roi = np.std(rois)

        if std_roi == 0:
            return (self.account_balance * self.base_risk_per_trade) / stop_loss_distance

        # 估计最优f (简化公式)
        optimal_f = avg_roi / (std_roi ** 2)

        # 限制范围
        optimal_f = max(self.min_kelly, min(optimal_f, self.max_kelly))

        risk_amount = self.account_balance * optimal_f
        return risk_amount / stop_loss_distance

    def _calculate_atr(self, klines: List[Dict]) -> float:
        """计算ATR"""
        if len(klines) < self.atr_window + 1:
            return 0

        true_ranges = []
        for i in range(1, len(klines)):
            high = klines[i].get("high", klines[i].get("close", 0))
            low = klines[i].get("low", klines[i].get("close", 0))
            prev_close = klines[i - 1].get("close", 0)

            tr = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close)
            )
            true_ranges.append(tr)

        return np.mean(true_ranges[-self.atr_window:])

    def _detect_volatility_regime(self, atr: float, current_price: float,
                                  klines: Optional[List[Dict]] = None) -> VolatilityRegime:
        """检测波动率状态"""
        if atr == 0 or current_price == 0:
            return VolatilityRegime.NORMAL

        # 计算ATR百分比
        atr_pct = (atr / current_price) * 100

        # 波动率阈值(可根据品种调整)
        if atr_pct < 0.3:
            return VolatilityRegime.EXTREME_LOW
        elif atr_pct < 0.5:
            return VolatilityRegime.LOW
        elif atr_pct < 1.5:
            return VolatilityRegime.NORMAL
        elif atr_pct < 3.0:
            return VolatilityRegime.HIGH
        else:
            return VolatilityRegime.EXTREME_HIGH

    def _get_volatility_adjustment_factor(self, regime: VolatilityRegime) -> float:
        """获取波动率调整因子"""
        factors = {
            VolatilityRegime.EXTREME_LOW: 1.3,  # 低波动增加仓位
            VolatilityRegime.LOW: 1.1,
            VolatilityRegime.NORMAL: 1.0,
            VolatilityRegime.HIGH: 0.7,          # 高波动减小仓位
            VolatilityRegime.EXTREME_HIGH: 0.4  # 极高波动大幅减小
        }
        return factors.get(regime, 1.0)

    def _get_consecutive_loss_factor(self) -> float:
        """获取连续亏损调整因子"""
        if not self.consecutive_loss_reduction["enabled"]:
            return 1.0

        threshold = self.consecutive_loss_reduction["threshold"]
        reduction_factor = self.consecutive_loss_reduction["reduction_factor"]

        consecutive_losses = self.trade_history.consecutive_losses

        if consecutive_losses < threshold:
            return 1.0
        else:
            # 超过阈值后每次亏损递减
            excess_losses = consecutive_losses - threshold + 1
            factor = reduction_factor ** excess_losses
            return max(factor, 0.2)  # 最小保留20%

    def _get_performance_adjustment_factor(self) -> float:
        """获取历史表现调整因子"""
        if self.trade_history.total_trades < 10:
            return 1.0

        # 基于盈亏比调整
        profit_factor = self.trade_history.profit_factor

        if profit_factor > 2.0:
            return 1.2  # 表现优秀,增加仓位
        elif profit_factor > 1.5:
            return 1.1
        elif profit_factor < 1.0:
            return 0.8  # 表现不佳,减小仓位
        else:
            return 1.0

    def _get_correlation_factor(self, symbol: str,
                             market_conditions: Optional[Dict] = None) -> float:
        """获取相关性调整因子"""
        if not market_conditions or symbol not in self.current_positions:
            return 1.0

        # 计算当前品种的相关性暴露
        correlated_exposure = self._calculate_correlated_exposure(symbol, market_conditions)

        if correlated_exposure > self.max_correlated_exposure:
            # 超过相关性限制,减小仓位
            reduction = 1 - (correlated_exposure / self.max_correlated_exposure)
            return max(reduction, 0.3)

        return 1.0

    def _calculate_correlated_exposure(self, symbol: str,
                                     market_conditions: Dict) -> float:
        """计算相关性暴露"""
        exposure = 0.0

        # 检查与当前持仓的相关性
        for pos_symbol, pos_data in self.current_positions.items():
            correlation = self._get_symbol_correlation(symbol, pos_symbol, market_conditions)
            if correlation > self.correlation_threshold:
                exposure += abs(pos_data.get("exposure", 0)) * correlation

        return exposure

    def _get_symbol_correlation(self, symbol1: str, symbol2: str,
                               market_conditions: Dict) -> float:
        """获取品种相关性"""
        # 预定义的相关性映射
        correlations = {
            # BTC相关
            "BTCUSDT-ETHUSDT": 0.85,
            "BTCUSDT-BNBUSDT": 0.75,
            "BTCUSDT-SOLUSDT": 0.70,

            # ETH相关
            "ETHUSDT-BNBUSDT": 0.70,
            "ETHUSDT-SOLUSDT": 0.65,

            # 外汇相关
            "EURUSD-GBPUSD": 0.85,
            "EURUSD-USDCHF": -0.90,
            "EURUSD-USDJPY": 0.50,

            # 黄金相关
            "XAUUSD-XAGUSD": 0.75,
            "XAUUSD-USDCHF": 0.50,
        }

        key = f"{symbol1}-{symbol2}"
        key_reverse = f"{symbol2}-{symbol1}"

        return correlations.get(key, correlations.get(key_reverse, 0))

    def _get_market_condition_factor(self,
                                  market_conditions: Optional[Dict] = None) -> float:
        """获取市场条件调整因子"""
        if not market_conditions:
            return 1.0

        factor = 1.0

        # 基于趋势强度调整
        trend_strength = market_conditions.get("trend_strength", 0.5)
        if trend_strength > 0.8:
            factor *= 1.1  # 强趋势增加仓位
        elif trend_strength < 0.3:
            factor *= 0.8  # 弱趋势减小仓位

        # 基于流动性调整
        liquidity_score = market_conditions.get("liquidity_score", 3)
        if liquidity_score < 2:
            factor *= 0.7  # 低流动性减小仓位

        # 基于交易时段调整
        trading_session = market_conditions.get("trading_session", "normal")
        if trading_session == "off_hours":
            factor *= 0.5  # 非交易时段大幅减小

        return factor

    def _get_risk_limit_factor(self) -> float:
        """获取总风险限制调整因子"""
        if not self.current_positions:
            return 1.0

        # 计算当前总风险
        current_total_risk = sum(
            pos.get("risk_percentage", 0)
            for pos in self.current_positions.values()
        )

        # 如果接近总风险上限,减小新仓位
        if current_total_risk >= self.max_total_risk:
            return 0  # 已达上限,不开新仓
        elif current_total_risk >= self.max_total_risk * 0.8:
            return 0.3  # 接近上限,大幅减小
        elif current_total_risk >= self.max_total_risk * 0.6:
            return 0.5  # 超过60%,适度减小
        else:
            return 1.0

    def _calculate_confidence(self, adjustment_factors: Dict,
                            volatility_regime: VolatilityRegime) -> float:
        """计算仓位置信度"""
        confidence = 1.0

        # 基于波动率调整置信度
        if volatility_regime == VolatilityRegime.EXTREME_LOW:
            confidence *= 0.9
        elif volatility_regime == VolatilityRegime.EXTREME_HIGH:
            confidence *= 0.7

        # 基于调整因子调整置信度
        for factor_name, factor_value in adjustment_factors.items():
            if factor_value < 0.5:
                confidence *= 0.8

        # 基于交易历史调整
        if self.trade_history.total_trades >= 30:
            if self.trade_history.win_rate > 0.6:
                confidence *= 1.1
            elif self.trade_history.win_rate < 0.4:
                confidence *= 0.8

        return min(confidence, 1.0)

    def _generate_warnings(self, volatility_regime: VolatilityRegime,
                         risk_percentage: float,
                         consecutive_losses: int = 0) -> List[str]:
        """生成警告信息"""
        warnings = []

        if volatility_regime == VolatilityRegime.EXTREME_HIGH:
            warnings.append("市场波动率极高,建议谨慎交易")

        elif volatility_regime == VolatilityRegime.EXTREME_LOW:
            warnings.append("市场波动率极低,可能存在风险")

        if risk_percentage > 0.04:
            warnings.append(f"单笔风险{risk_percentage:.1%}超过推荐值")

        if consecutive_losses >= 3:
            warnings.append(f"连续亏损{consecutive_losses}次,建议减小仓位或暂停交易")

        if self.trade_history.total_trades >= 10 and self.trade_history.win_rate < 0.4:
            warnings.append(f"近期胜率较低({self.trade_history.win_rate:.1%}),建议回顾策略")

        return warnings

    def _calculate_recommended_leverage(self, position_size: float,
                                      current_price: float,
                                      risk_amount: float) -> float:
        """计算推荐杠杆"""
        margin_required = position_size * current_price

        if margin_required == 0:
            return 1.0

        # 基于风险比例计算杠杆
        # 杠杆 = (账户余额 * 风险比例) / 保证金
        leverage = (self.account_balance * self.base_risk_per_trade * 3) / margin_required

        # 限制杠杆范围
        return max(1.0, min(leverage, 20.0))

    def add_position(self, symbol: str, size: float, price: float,
                   risk_percentage: float, exposure: float = 0):
        """添加持仓记录"""
        self.current_positions[symbol] = {
            "size": size,
            "entry_price": price,
            "risk_percentage": risk_percentage,
            "exposure": exposure or size * price / self.account_balance,
            "timestamp": datetime.now()
        }
        self.used_margin += size * price
        self.available_balance = self.account_balance - self.used_margin

    def remove_position(self, symbol: str, size: float, price: float):
        """移除持仓记录"""
        if symbol in self.current_positions:
            self.used_margin -= self.current_positions[symbol]["size"] * self.current_positions[symbol]["entry_price"]
            del self.current_positions[symbol]
            self.available_balance = self.account_balance - self.used_margin

    def get_statistics(self) -> Dict:
        """获取统计信息"""
        return {
            "account_balance": self.account_balance,
            "available_balance": self.available_balance,
            "used_margin": self.used_margin,
            "risk_model": self.risk_model.value,
            "base_risk_per_trade": self.base_risk_per_trade,
            "current_positions_count": len(self.current_positions),
            "trade_history": {
                "total_trades": self.trade_history.total_trades,
                "winning_trades": self.trade_history.winning_trades,
                "losing_trades": self.trade_history.losing_trades,
                "win_rate": self.trade_history.win_rate,
                "profit_factor": self.trade_history.profit_factor,
                "consecutive_losses": self.trade_history.consecutive_losses,
                "consecutive_wins": self.trade_history.consecutive_wins,
                "avg_profit": self.trade_history.avg_profit,
                "avg_loss": self.trade_history.avg_loss
            }
        }


class VolatilityAnalyzer:
    """波动率分析器"""

    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.lookback_periods = self.config.get("lookback_periods", [14, 30, 60])

    def analyze(self, klines: List[Dict]) -> Dict:
        """分析波动率"""
        if len(klines) < max(self.lookback_periods):
            return {}

        closes = [k["close"] for k in klines]
        returns = pd.Series(closes).pct_change().dropna()

        result = {
            "current_price": closes[-1],
            "volatility_regime": "normal",
            "volatility_metrics": {}
        }

        # 计算不同周期的波动率
        for period in self.lookback_periods:
            if len(returns) >= period:
                vol = returns.tail(period).std() * np.sqrt(252)  # 年化波动率
                result["volatility_metrics"][f"volatility_{period}d"] = vol

        # 计算ATR
        atr = self._calculate_atr(klines, 14)
        if atr:
            atr_pct = (atr / closes[-1]) * 100
            result["volatility_metrics"]["atr"] = atr
            result["volatility_metrics"]["atr_pct"] = atr_pct

            # 判断波动率状态
            if atr_pct < 0.3:
                result["volatility_regime"] = "extreme_low"
            elif atr_pct < 0.5:
                result["volatility_regime"] = "low"
            elif atr_pct < 1.5:
                result["volatility_regime"] = "normal"
            elif atr_pct < 3.0:
                result["volatility_regime"] = "high"
            else:
                result["volatility_regime"] = "extreme_high"

        # 计算布林带宽度
        bb_width = self._calculate_bollinger_width(klines, 20)
        if bb_width:
            result["volatility_metrics"]["bollinger_width"] = bb_width
            result["volatility_metrics"]["bollinger_squeeze"] = bb_width < 0.01

        # 波动率趋势
        if len(result["volatility_metrics"]) >= 2:
            vol_values = list(result["volatility_metrics"].values())
            result["volatility_trend"] = "expanding" if vol_values[-1] > vol_values[0] else "contracting"

        return result

    def _calculate_atr(self, klines: List[Dict], period: int) -> float:
        """计算ATR"""
        if len(klines) < period + 1:
            return 0

        true_ranges = []
        for i in range(1, len(klines)):
            high = klines[i].get("high", klines[i].get("close", 0))
            low = klines[i].get("low", klines[i].get("close", 0))
            prev_close = klines[i - 1].get("close", 0)

            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            true_ranges.append(tr)

        return np.mean(true_ranges[-period:])

    def _calculate_bollinger_width(self, klines: List[Dict], period: int) -> float:
        """计算布林带宽度"""
        if len(klines) < period:
            return 0

        closes = [k["close"] for k in klines]
        ma = np.mean(closes[-period:])
        std = np.std(closes[-period:])

        upper = ma + 2 * std
        lower = ma - 2 * std

        return (upper - lower) / ma if ma > 0 else 0


def create_position_sizer(config: Dict) -> DynamicPositionSizer:
    """创建仓位计算器"""
    return DynamicPositionSizer(config)


if __name__ == "__main__":
    # 测试代码
    config = {
        "risk_model": "composite",
        "base_risk_per_trade": 0.02,
        "max_risk_per_trade": 0.05,
        "max_total_risk": 0.10,
        "initial_balance": 10000.0,
        "atr_window": 14,
        "atr_multiplier": 2.0,
        "volatility_adjustment": True,
        "kelly_fraction": 0.5,
        "consecutive_loss_reduction": {
            "enabled": True,
            "threshold": 2,
            "reduction_factor": 0.5
        }
    }

    sizer = DynamicPositionSizer(config)

    # 模拟交易历史
    for _ in range(20):
        import random
        pnl = random.choice([100, -50, 150, -80, 200, -30, 120])
        sizer.record_trade("BTCUSDT", pnl, 40000, 40200, 0.1)

    # 测试仓位计算
    import random
    np.random.seed(42)
    klines = []
    price = 40000
    for i in range(100):
        high = price * (1 + random.uniform(-0.01, 0.01))
        low = price * (1 + random.uniform(-0.01, 0.01))
        close = price * (1 + random.uniform(-0.01, 0.01))
        klines.append({"high": high, "low": low, "close": close})
        price = close

    result = sizer.calculate_position_size("BTCUSDT", 40000, None, klines)

    print("\n动态仓位计算结果:")
    print(f"  基础仓位: {result.base_size:.6f}")
    print(f"  调整后仓位: {result.adjusted_size:.6f}")
    print(f"  风险金额: ${result.risk_amount:.2f}")
    print(f"  风险百分比: {result.risk_percentage:.2%}")
    print(f"  波动率状态: {result.volatility_regime.value}")
    print(f"  置信度: {result.confidence:.2%}")
    print(f"  推荐杠杆: {result.recommended_leverage:.1f}x")
    print(f"\n调整因子:")
    for name, factor in result.adjustment_factors.items():
        print(f"  {name}: {factor:.2%}")
    print(f"\n警告:")
    for warning in result.warnings:
        print(f"  {warning}")
