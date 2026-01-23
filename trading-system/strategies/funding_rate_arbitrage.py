# 资金费率套利策略
# 基于永续合约资金费率进行套利交易

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class FundingSignal(Enum):
    """资金费率信号"""
    STRONG_SHORT = "strong_short"      # 强做空信号
    SHORT = "short"                    # 做空信号
    WEAK_SHORT = "weak_short"          # 弱做空信号
    NEUTRAL = "neutral"                # 中性
    WEAK_LONG = "weak_long"            # 弱做多信号
    LONG = "long"                      # 做多信号
    STRONG_LONG = "strong_long"        # 强做多信号


@dataclass
class FundingArbitrageOpportunity:
    """资金费率套利机会"""
    symbol: str
    current_funding_rate: float
    predicted_funding_rate: float
    funding_trend: str  # rising/falling/stable
    signal: FundingSignal
    signal_strength: float  # 0-1
    expected_daily_return: float
    entry_price: float
    recommended_side: str  # long/short
    confidence: float
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    estimated_profit_24h: float = 0
    risk_level: str = "low"  # low/medium/high


class FundingRateAnalyzer:
    """资金费率分析器"""

    def __init__(self, config: Dict = None):
        self.config = config or {}

        # 资金费率阈值
        self.high_funding_threshold = self.config.get("high_funding_threshold", 0.0001)  # 0.01%
        self.low_funding_threshold = self.config.get("low_funding_threshold", -0.0001)   # -0.01%
        self.extreme_funding_threshold = self.config.get("extreme_funding_threshold", 0.0003)  # 0.03%

        # 预测参数
        self.prediction_window = self.config.get("prediction_window", 8)  # 8小时
        self.history_length = self.config.get("history_length", 48)  # 48期

        # 资金费率历史
        self.funding_history: Dict[str, List[Dict]] = {}

    def analyze_funding_rate(self,
                            symbol: str,
                            current_funding_rate: float,
                            funding_history: List[Dict],
                            market_data: Optional[Dict] = None) -> FundingArbitrageOpportunity:
        """
        分析资金费率并生成套利机会

        参数:
            symbol: 交易品种
            current_funding_rate: 当前资金费率
            funding_history: 历史资金费率数据 [{"funding_time": timestamp, "funding_rate": rate}]
            market_data: 市场数据(可选)

        返回:
            FundingArbitrageOpportunity
        """
        # 预测资金费率
        predicted_rate, funding_trend = self._predict_funding_rate(funding_history)

        # 生成信号
        signal, signal_strength, reasons = self._generate_signal(
            current_funding_rate, predicted_rate, funding_trend, funding_history
        )

        # 计算预期收益
        expected_daily_return = current_funding_rate * 3  # 每天3次收费
        estimated_profit_24h = self._calculate_estimated_profit(
            current_funding_rate, signal, market_data
        )

        # 确定推荐方向
        recommended_side = self._get_recommended_side(signal)

        # 计算置信度
        confidence = self._calculate_confidence(
            signal_strength, funding_trend, funding_history
        )

        # 生成警告
        warnings = self._generate_warnings(
            current_funding_rate, predicted_rate, funding_trend, market_data
        )

        # 评估风险
        risk_level = self._assess_risk_level(
            current_funding_rate, funding_trend, market_data
        )

        # 获取入场价格
        entry_price = market_data.get("current_price", 0) if market_data else 0

        return FundingArbitrageOpportunity(
            symbol=symbol,
            current_funding_rate=current_funding_rate,
            predicted_funding_rate=predicted_rate,
            funding_trend=funding_trend,
            signal=signal,
            signal_strength=signal_strength,
            expected_daily_return=expected_daily_return,
            entry_price=entry_price,
            recommended_side=recommended_side,
            confidence=confidence,
            reasons=reasons,
            warnings=warnings,
            estimated_profit_24h=estimated_profit_24h,
            risk_level=risk_level
        )

    def _predict_funding_rate(self,
                              funding_history: List[Dict]) -> Tuple[float, str]:
        """预测资金费率"""
        if len(funding_history) < 3:
            return 0, "stable"

        rates = [f["funding_rate"] for f in funding_history[-self.history_length:]]

        # 趋势分析
        recent_rates = rates[-10:]
        older_rates = rates[-20:-10] if len(rates) >= 20 else rates[:-10]

        recent_avg = np.mean(recent_rates)
        older_avg = np.mean(older_rates)

        if recent_avg > older_avg * 1.2:
            funding_trend = "rising"
        elif recent_avg < older_avg * 0.8:
            funding_trend = "falling"
        else:
            funding_trend = "stable"

        # 简单预测:基于移动平均
        predicted_rate = np.mean(rates[-8:])

        # 趋势调整
        if funding_trend == "rising":
            predicted_rate = predicted_rate * 1.1
        elif funding_trend == "falling":
            predicted_rate = predicted_rate * 0.9

        return predicted_rate, funding_trend

    def _generate_signal(self,
                        current_rate: float,
                        predicted_rate: float,
                        funding_trend: str,
                        history: List[Dict]) -> Tuple[FundingSignal, float, List[str]]:
        """生成资金费率信号"""
        reasons = []
        signal_strength = 0

        # 基于当前费率判断
        if current_rate > self.extreme_funding_threshold:
            signal = FundingSignal.STRONG_SHORT
            signal_strength = 0.9
            reasons.append(f"资金费率极高({current_rate*100:.4f}%),强烈建议做空收取费用")
        elif current_rate > self.high_funding_threshold:
            signal = FundingSignal.SHORT
            signal_strength = 0.7
            reasons.append(f"资金费率偏高({current_rate*100:.4f}%),建议做空")
        elif current_rate < -self.extreme_funding_threshold:
            signal = FundingSignal.STRONG_LONG
            signal_strength = 0.9
            reasons.append(f"资金费率极低({current_rate*100:.4f}%),强烈建议做多收取费用")
        elif current_rate < -self.low_funding_threshold:
            signal = FundingSignal.LONG
            signal_strength = 0.7
            reasons.append(f"资金费率偏低({current_rate*100:.4f}%),建议做多")
        else:
            signal = FundingSignal.NEUTRAL
            signal_strength = 0.1
            reasons.append("资金费率接近0,无明显套利机会")

        # 基于趋势调整
        if signal != FundingSignal.NEUTRAL:
            if funding_trend == "rising":
                if signal in [FundingSignal.SHORT, FundingSignal.STRONG_SHORT]:
                    signal_strength *= 1.2  # 上升趋势加强做空信号
                    reasons.append("资金费率上升趋势,做空信号增强")
                elif signal in [FundingSignal.LONG, FundingSignal.STRONG_LONG]:
                    signal_strength *= 0.5  # 上升趋势削弱做多信号
                    reasons.append("资金费率上升趋势,做多信号减弱")

            elif funding_trend == "falling":
                if signal in [FundingSignal.LONG, FundingSignal.STRONG_LONG]:
                    signal_strength *= 1.2  # 下降趋势加强做多信号
                    reasons.append("资金费率下降趋势,做多信号增强")
                elif signal in [FundingSignal.SHORT, FundingSignal.STRONG_SHORT]:
                    signal_strength *= 0.5  # 下降趋势削弱做空信号
                    reasons.append("资金费率下降趋势,做空信号减弱")

        # 基于预测调整
        if abs(predicted_rate - current_rate) > abs(current_rate) * 0.5:
            if (predicted_rate > current_rate and
                signal in [FundingSignal.SHORT, FundingSignal.STRONG_SHORT]):
                signal_strength *= 1.1
                reasons.append("预测资金费率将继续上升")
            elif (predicted_rate < current_rate and
                  signal in [FundingSignal.LONG, FundingSignal.STRONG_LONG]):
                signal_strength *= 1.1
                reasons.append("预测资金费率将继续下降")

        # 限制强度范围
        signal_strength = max(0, min(1, signal_strength))

        # 根据强度调整信号等级
        if signal == FundingSignal.SHORT and signal_strength > 0.8:
            signal = FundingSignal.STRONG_SHORT
        elif signal == FundingSignal.LONG and signal_strength > 0.8:
            signal = FundingSignal.STRONG_LONG
        elif signal == FundingSignal.SHORT and signal_strength < 0.4:
            signal = FundingSignal.WEAK_SHORT
        elif signal == FundingSignal.LONG and signal_strength < 0.4:
            signal = FundingSignal.WEAK_LONG

        return signal, signal_strength, reasons

    def _calculate_estimated_profit(self,
                                   funding_rate: float,
                                   signal: FundingSignal,
                                   market_data: Optional[Dict]) -> float:
        """计算预估24小时利润"""
        if signal in [FundingSignal.NEUTRAL, FundingSignal.WEAK_SHORT, FundingSignal.WEAK_LONG]:
            return 0

        # 基础利润:资金费率收入 * 3次/天
        base_profit = abs(funding_rate) * 3

        # 调整价格波动影响
        if market_data:
            volatility = market_data.get("volatility_score", 0.5)
            # 高波动增加风险,降低预期利润
            base_profit *= (1 - volatility * 0.2)

        # 基于信号强度调整
        if signal in [FundingSignal.STRONG_SHORT, FundingSignal.STRONG_LONG]:
            base_profit *= 1.2

        return base_profit

    def _get_recommended_side(self, signal: FundingSignal) -> str:
        """获取推荐交易方向"""
        if signal in [FundingSignal.SHORT, FundingSignal.STRONG_SHORT]:
            return "short"
        elif signal in [FundingSignal.LONG, FundingSignal.STRONG_LONG]:
            return "long"
        else:
            return "hold"

    def _calculate_confidence(self,
                               signal_strength: float,
                               funding_trend: str,
                               history: List[Dict]) -> float:
        """计算置信度"""
        confidence = signal_strength

        # 基于趋势调整
        if funding_trend in ["rising", "falling"]:
            confidence *= 1.1

        # 基于历史稳定性调整
        if len(history) >= 20:
            recent_rates = [h["funding_rate"] for h in history[-20:]]
            stability = 1 - np.std(recent_rates) / (np.mean(np.abs(recent_rates)) + 0.0001)
            confidence *= min(stability, 1.2)

        return min(confidence, 0.95)

    def _generate_warnings(self,
                           current_rate: float,
                           predicted_rate: float,
                           funding_trend: str,
                           market_data: Optional[Dict]) -> List[str]:
        """生成警告"""
        warnings = []

        # 价格波动警告
        if market_data:
            volatility = market_data.get("volatility_score", 0)
            if volatility > 0.8:
                warnings.append("市场波动率极高,资金费率套利风险增加")

            trend_strength = market_data.get("trend_strength", 0)
            if trend_strength > 0.7 and (
                (current_rate > 0 and trend_strength > 0.7) or
                (current_rate < 0 and trend_strength < 0.3)
            ):
                warnings.append("价格趋势与资金费率方向一致,可能增加反转风险")

        # 资金费率极值警告
        if abs(current_rate) > self.extreme_funding_threshold * 2:
            warnings.append("资金费率达到极值,可能发生剧烈调整")

        # 趋势反转警告
        if funding_trend != "stable":
            # 检查是否有反转迹象
            if abs(predicted_rate - current_rate) > abs(current_rate) * 0.3:
                direction = "上升" if predicted_rate > current_rate else "下降"
                warnings.append(f"预测资金费率将{direction},注意趋势反转风险")

        return warnings

    def _assess_risk_level(self,
                           current_rate: float,
                           funding_trend: str,
                           market_data: Optional[Dict]) -> str:
        """评估风险水平"""
        risk_score = 0

        # 资金费率风险
        if abs(current_rate) > self.extreme_funding_threshold:
            risk_score += 2
        elif abs(current_rate) > self.high_funding_threshold:
            risk_score += 1

        # 趋势风险
        if funding_trend != "stable":
            risk_score += 1

        # 市场风险
        if market_data:
            volatility = market_data.get("volatility_score", 0)
            if volatility > 0.8:
                risk_score += 2
            elif volatility > 0.5:
                risk_score += 1

        if risk_score >= 4:
            return "high"
        elif risk_score >= 2:
            return "medium"
        else:
            return "low"


class FundingArbitrageStrategy:
    """资金费率套利策略"""

    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.analyzer = FundingRateAnalyzer(config)

        # 策略参数
        self.min_profit_threshold = self.config.get("min_profit_threshold", 0.001)  # 0.1%
        self.max_position_size = self.config.get("max_position_size", 0.5)  # 最大仓位50%
        self.min_confidence = self.config.get("min_confidence", 0.6)

        # 风险控制
        self.max_daily_trades = self.config.get("max_daily_trades", 3)
        self.daily_trade_count = 0
        self.last_reset_date = datetime.now().date()

        # 持仓跟踪
        self.positions: Dict[str, Dict] = {}

        # 盈亏跟踪
        self.total_profit = 0
        self.total_loss = 0
        self.trade_count = 0

    def should_trade(self, opportunity: FundingArbitrageOpportunity) -> bool:
        """判断是否应该交易"""
        # 检查信号
        if opportunity.signal == FundingSignal.NEUTRAL:
            return False

        # 检查信号强度
        if opportunity.signal_strength < 0.5:
            return False

        # 检查置信度
        if opportunity.confidence < self.min_confidence:
            return False

        # 检查预期收益
        if abs(opportunity.expected_daily_return) < self.min_profit_threshold:
            return False

        # 检查风险
        if opportunity.risk_level == "high":
            return False

        # 检查每日交易次数
        self._check_daily_limit()

        if self.daily_trade_count >= self.max_daily_trades:
            logger.info("已达到每日交易次数限制")
            return False

        return True

    def _check_daily_limit(self):
        """检查每日限制"""
        today = datetime.now().date()
        if today != self.last_reset_date:
            self.daily_trade_count = 0
            self.last_reset_date = today

    def get_position_size(self,
                         opportunity: FundingArbitrageOpportunity,
                         account_balance: float,
                         risk_per_trade: float) -> float:
        """计算仓位大小"""
        # 基础仓位
        base_size = account_balance * risk_per_trade / opportunity.entry_price

        # 根据信号强度调整
        adjusted_size = base_size * opportunity.signal_strength

        # 应用最大限制
        adjusted_size = min(adjusted_size, self.max_position_size * account_balance / opportunity.entry_price)

        return adjusted_size

    def record_entry(self, opportunity: FundingArbitrageOpportunity,
                      size: float, price: float):
        """记录入场"""
        self.positions[opportunity.symbol] = {
            "side": opportunity.recommended_side,
            "size": size,
            "entry_price": price,
            "entry_time": datetime.now(),
            "funding_rate": opportunity.current_funding_rate,
            "expected_daily_return": opportunity.expected_daily_return
        }

        self.daily_trade_count += 1

        logger.info(
            f"资金费率套利入场: {opportunity.symbol} "
            f"{opportunity.recommended_side} {size:.6f} @ {price:.2f}"
        )

    def record_exit(self, symbol: str, exit_price: float, profit: float):
        """记录出场"""
        if symbol in self.positions:
            position = self.positions[symbol]

            duration = (datetime.now() - position["entry_time"]).total_seconds() / 3600

            logger.info(
                f"资金费率套利出场: {symbol} "
                f"{position['side']} 盈亏: {profit:+.2f} "
                f"持仓时长: {duration:.1f}小时"
            )

            # 更新统计
            if profit > 0:
                self.total_profit += profit
            else:
                self.total_loss += abs(profit)
            self.trade_count += 1

            del self.positions[symbol]

    def get_statistics(self) -> Dict:
        """获取策略统计"""
        win_rate = 0
        if self.trade_count > 0:
            profitable_trades = sum(1 for pos in self.positions.values())
            win_rate = profitable_trades / self.trade_count

        profit_factor = (self.total_profit / self.total_loss
                        if self.total_loss > 0 else float('inf'))

        return {
            "total_profit": self.total_profit,
            "total_loss": self.total_loss,
            "net_profit": self.total_profit - self.total_loss,
            "trade_count": self.trade_count,
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "current_positions": len(self.positions),
            "daily_trade_count": self.daily_trade_count,
            "daily_trade_limit": self.max_daily_trades
        }


def create_funding_arbitrage_strategy(config: Dict = None) -> FundingArbitrageStrategy:
    """创建资金费率套利策略"""
    return FundingArbitrageStrategy(config)


if __name__ == "__main__":
    # 测试代码
    config = {
        "high_funding_threshold": 0.0001,
        "low_funding_threshold": -0.0001,
        "extreme_funding_threshold": 0.0003,
        "min_profit_threshold": 0.001,
        "min_confidence": 0.6
    }

    strategy = FundingArbitrageStrategy(config)

    # 模拟资金费率历史
    import random
    np.random.seed(42)

    def generate_funding_history(base_rate, count):
        history = []
        rate = base_rate
        base_time = datetime.now() - timedelta(hours=count)
        for i in range(count):
            rate = rate * (1 + random.uniform(-0.3, 0.3))
            history.append({
                "funding_time": base_time + timedelta(hours=i),
                "funding_rate": rate
            })
        return history

    # 测试不同场景
    test_cases = [
        ("高资金费率(做多收取费用)", 0.00025),
        ("低资金费率(做空收取费用)", -0.0002),
        ("正常资金费率", 0.00005)
    ]

    print("\n=== 资金费率套利策略测试 ===\n")

    for name, funding_rate in test_cases:
        print(f"{'='*60}")
        print(f"测试场景: {name}")
        print(f"{'='*60}")

        # 生成历史数据
        history = generate_funding_history(funding_rate, 48)

        # 市场数据
        market_data = {
            "current_price": 40000,
            "volatility_score": 0.4,
            "trend_strength": 0.5
        }

        # 分析机会
        opportunity = strategy.analyzer.analyze_funding_rate(
            "BTCUSDT", funding_rate, history, market_data
        )

        print(f"\n信号: {opportunity.signal.value}")
        print(f"信号强度: {opportunity.signal_strength:.2f}")
        print(f"置信度: {opportunity.confidence:.2%}")
        print(f"推荐方向: {opportunity.recommended_side}")
        print(f"预期日收益: {opportunity.expected_daily_return*100:.4f}%")
        print(f"预估24h利润: {opportunity.estimated_profit_24h*100:.4f}%")
        print(f"风险水平: {opportunity.risk_level}")

        print(f"\n原因:")
        for reason in opportunity.reasons:
            print(f"  - {reason}")

        if opportunity.warnings:
            print(f"\n警告:")
            for warning in opportunity.warnings:
                print(f"  - {warning}")

        # 检查是否应该交易
        should_trade = strategy.should_trade(opportunity)
        print(f"\n是否交易: {'是' if should_trade else '否'}")
