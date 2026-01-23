# 交易建议和优化指南
# 基于已实现的系统功能提供具体的交易建议

from typing import Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class MarketCondition(Enum):
    """市场条件"""
    STRONG_UPTREND = "strong_uptrend"
    WEAK_UPTREND = "weak_uptrend"
    RANGING = "ranging"
    VOLATILE_TREND = "volatile_trend"
    CHOPPY = "choppy"
    STRONG_DOWNTREND = "strong_downtrend"


class TradingStyle(Enum):
    """交易风格"""
    SCALPER = "scalper"            # 剥头皮
    INTRADAY = "intraday"         # 日内交易
    SWING = "swing"                # 波段交易
    POSITION = "position"            # 中长线
    ARBITRAGE = "arbitrage"          # 套利


@dataclass
class TradingRecommendation:
    """交易建议"""
    symbol: str
    condition: MarketCondition
    action: str  # buy/sell/hold/avoid
    confidence: float
    reason: str
    entry_zone: Tuple[float, float]  # (low, high)
    stop_loss: float
    take_profit_levels: List[float]  # 多个止盈位
    position_size_pct: float  # 建议仓位百分比
    timeframe: str
    style: TradingStyle
    risk_level: str  # low/medium/high
    notes: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class TradingAdvisor:
    """交易顾问 - 提供具体的交易建议"""

    def __init__(self, config: Dict = None):
        self.config = config or {}

        # 交易参数
        self.risk_per_trade = self.config.get("risk_per_trade", 0.02)
        self.max_positions = self.config.get("max_positions", 3)
        self.default_stop_loss = self.config.get("default_stop_loss", 0.02)

        # 交易风格偏好
        self.preferred_style = self.config.get("preferred_style", TradingStyle.SWING)

        # 建议历史
        self.recommendation_history: List[TradingRecommendation] = []
        self.max_history = 100

    def generate_recommendations(self,
                                 market_analysis: Dict,
                                 funding_rate: Optional[float] = None,
                                 account_balance: float = 10000) -> List[TradingRecommendation]:
        """
        生成交易建议

        参数:
            market_analysis: 市场分析结果
            funding_rate: 资金费率(可选)
            account_balance: 账户余额

        返回:
            交易建议列表
        """
        symbol = market_analysis.get("symbol", "")
        recommendations = []

        # 获取市场状态
        market_state = market_analysis.get("market_state", "ranging")
        trend_strength = market_analysis.get("trend_strength", 0.5)
        volatility_level = market_analysis.get("volatility_level", "medium")

        # 获取多时间框架信号
        mtf_signal = market_analysis.get("multi_timeframe_signal", {})
        composite_signal = mtf_signal.get("composite_signal", "hold")

        # 确定市场条件
        condition = self._determine_market_condition(
            market_state, trend_strength, volatility_level
        )

        # 获取当前价格
        current_price = market_analysis.get("current_price", 0)

        # 基于条件生成建议
        if condition == MarketCondition.STRONG_UPTREND:
            recommendations.extend(self._strong_uptrend_recommendations(
                symbol, current_price, market_analysis, account_balance
            ))
        elif condition == MarketCondition.WEAK_UPTREND:
            recommendations.extend(self._weak_uptrend_recommendations(
                symbol, current_price, market_analysis, account_balance
            ))
        elif condition == MarketCondition.RANGING:
            recommendations.extend(self._ranging_recommendations(
                symbol, current_price, market_analysis, account_balance
            ))
        elif condition == MarketCondition.VOLATILE_TREND:
            recommendations.extend(self._volatile_trend_recommendations(
                symbol, current_price, market_analysis, account_balance
            ))
        elif condition == MarketCondition.CHOPPY:
            recommendations.extend(self._choppy_recommendations(
                symbol, current_price, account_balance
            ))
        elif condition == MarketCondition.STRONG_DOWNTREND:
            recommendations.extend(self._strong_downtrend_recommendations(
                symbol, current_price, market_analysis, account_balance
            ))

        # 资金费率套利建议
        if funding_rate is not None and abs(funding_rate) > 0.0001:
            arb_recommendation = self._generate_funding_arbitrage_recommendation(
                symbol, current_price, funding_rate, account_balance
            )
            if arb_recommendation:
                recommendations.append(arb_recommendation)

        # 记录历史
        for rec in recommendations:
            self.recommendation_history.append(rec)
        if len(self.recommendation_history) > self.max_history:
            self.recommendation_history.pop(0)

        return recommendations

    def _determine_market_condition(self,
                                   market_state: str,
                                   trend_strength: float,
                                   volatility_level: str) -> MarketCondition:
        """确定市场条件"""
        if trend_strength > 0.7 and volatility_level == "high":
            return MarketCondition.VOLATILE_TREND
        elif trend_strength > 0.7:
            if market_state in ["uptrend", "strong_uptrend"]:
                return MarketCondition.STRONG_UPTREND
            elif market_state in ["downtrend", "strong_downtrend"]:
                return MarketCondition.STRONG_DOWNTREND
        elif trend_strength > 0.4:
            return MarketCondition.WEAK_UPTREND
        elif trend_strength < 0.3:
            return MarketCondition.RANGING
        elif volatility_level == "low" and trend_strength < 0.3:
            return MarketCondition.CHOPPY
        else:
            return MarketCondition.RANGING

    def _strong_uptrend_recommendations(self,
                                       symbol: str,
                                       current_price: float,
                                       analysis: Dict,
                                       balance: float) -> List[TradingRecommendation]:
        """强上升趋势建议"""
        recommendations = []

        # 支撑阻力位
        support_levels = analysis.get("support_levels", [])
        resistance_levels = analysis.get("resistance_levels", [])
        nearest_resistance = min([r for r in resistance_levels if r > current_price],
                                default=current_price * 1.05)

        # 建议1: 突破做多(激进)
        recommendations.append(TradingRecommendation(
            symbol=symbol,
            condition=MarketCondition.STRONG_UPTREND,
            action="buy",
            confidence=0.75,
            reason="强上升趋势,等待突破阻力位",
            entry_zone=(current_price * 0.99, nearest_resistance * 1.02),
            stop_loss=current_price * 0.97,
            take_profit_levels=[
                nearest_resistance * 1.02,
                nearest_resistance * 1.05,
                nearest_resistance * 1.10
            ],
            position_size_pct=0.025,  # 2.5%
            timeframe="4H",
            style=TradingStyle.SWING,
            risk_level="medium",
            notes=[
                "确认突破阻力位后再入场",
                "使用分批建仓降低风险",
                "目标位可以分批止盈"
            ],
            warnings=["强趋势中回调可能较大"]
        ))

        # 建议2: 回调做多(保守)
        recommendations.append(TradingRecommendation(
            symbol=symbol,
            condition=MarketCondition.STRONG_UPTREND,
            action="buy",
            confidence=0.80,
            reason="上升趋势中的回调机会",
            entry_zone=(current_price * 0.97, current_price * 0.99),
            stop_loss=current_price * 0.95,
            take_profit_levels=[
                current_price * 1.05,
                current_price * 1.10
            ],
            position_size_pct=0.03,  # 3%
            timeframe="1H",
            style=TradingStyle.SWING,
            risk_level="low",
            notes=[
                "回调入场,更安全的入场点",
                "设置 tighter 止损",
                "盈利目标可以更激进"
            ],
            warnings=[]
        ))

        # 建议3: 高位做空(激进-仅适合经验丰富)
        recommendations.append(TradingRecommendation(
            symbol=symbol,
            condition=MarketCondition.STRONG_UPTREND,
            action="sell",
            confidence=0.45,
            reason="高位做空,等待反转信号",
            entry_zone=(nearest_resistance * 0.98, nearest_resistance * 1.02),
            stop_loss=nearest_resistance * 1.05,
            take_profit_levels=[
                current_price * 0.95,
                current_price * 0.90
            ],
            position_size_pct=0.015,  # 1.5%
            timeframe="1H",
            style=TradingStyle.SWING,
            risk_level="high",
            notes=[
                "仅在有明确反转信号时入场",
                "需要更严格的止损",
                "适合短期交易"
            ],
            warnings=["逆势交易风险较高", "需要强大的反转确认"]
        ))

        return recommendations

    def _weak_uptrend_recommendations(self,
                                     symbol: str,
                                     current_price: float,
                                     analysis: Dict,
                                     balance: float) -> List[TradingRecommendation]:
        """弱上升趋势建议"""
        recommendations = []

        # 建议1: 低位做多
        recommendations.append(TradingRecommendation(
            symbol=symbol,
            condition=MarketCondition.WEAK_UPTREND,
            action="buy",
            confidence=0.65,
            reason="弱势上升趋势,寻找支撑位做多",
            entry_zone=(current_price * 0.98, current_price * 1.00),
            stop_loss=current_price * 0.96,
            take_profit_levels=[
                current_price * 1.03,
                current_price * 1.06
            ],
            position_size_pct=0.02,  # 2%
            timeframe="1H",
            style=TradingStyle.SWING,
            risk_level="medium",
            notes=[
                "使用较小的仓位",
                "更紧的止损",
                "较短的持仓周期"
            ],
            warnings=["趋势可能转为震荡", "注意假突破"]
        ))

        # 建议2: 区间交易
        recommendations.append(TradingRecommendation(
            symbol=symbol,
            condition=MarketCondition.WEAK_UPTREND,
            action="hold",
            confidence=0.70,
            reason="弱势趋势中采取区间交易策略",
            entry_zone=(0, 0),  # 待定
            stop_loss=0,
            take_profit_levels=[],
            position_size_pct=0.02,
            timeframe="15M",
            style=TradingStyle.SWING,
            risk_level="low",
            notes=[
                "在支撑位附近做多",
                "在阻力位附近做空",
                "使用较小的目标位"
            ],
            warnings=["确认趋势后转为顺势交易"]
        ))

        return recommendations

    def _ranging_recommendations(self,
                               symbol: str,
                               current_price: float,
                               analysis: Dict,
                               balance: float) -> List[TradingRecommendation]:
        """震荡市场建议"""
        recommendations = []

        support_levels = analysis.get("support_levels", [])
        resistance_levels = analysis.get("resistance_levels", [])

        # 如果有支撑阻力位
        if support_levels and resistance_levels:
            nearest_support = max([s for s in support_levels if s < current_price],
                                   default=current_price * 0.97)
            nearest_resistance = min([r for r in resistance_levels if r > current_price],
                                      default=current_price * 1.03)

            # 建议1: 支撑位做多
            recommendations.append(TradingRecommendation(
                symbol=symbol,
                condition=MarketCondition.RANGING,
                action="buy",
                confidence=0.60,
                reason="震荡市场,支撑位做多",
                entry_zone=(nearest_support * 0.995, nearest_support * 1.005),
                stop_loss=nearest_support * 0.99,
                take_profit_levels=[
                    (nearest_support + nearest_resistance) / 2,
                    nearest_resistance
                ],
                position_size_pct=0.015,  # 1.5%
                timeframe="15M",
                style=TradingStyle.SWING,
                risk_level="low",
                notes=[
                    "严格的止盈目标",
                    "触及目标后立即出场",
                    "避免过度交易"
                ],
                warnings=["震荡市场趋势可能快速转变"]
            ))

            # 建议2: 阻力位做空
            recommendations.append(TradingRecommendation(
                symbol=symbol,
                condition=MarketCondition.RANGING,
                action="sell",
                confidence=0.60,
                reason="震荡市场,阻力位做空",
                entry_zone=(nearest_resistance * 0.995, nearest_resistance * 1.005),
                stop_loss=nearest_resistance * 1.01,
                take_profit_levels=[
                    (nearest_support + nearest_resistance) / 2,
                    nearest_support
                ],
                position_size_pct=0.015,  # 1.5%
                timeframe="15M",
                style=TradingStyle.SWING,
                risk_level="low",
                notes=[
                    "对称的交易策略",
                    "快速进出",
                    "使用限价单入场"
                ],
                warnings=["震荡市场趋势可能快速转变"]
            ))

        return recommendations

    def _volatile_trend_recommendations(self,
                                      symbol: str,
                                      current_price: float,
                                      analysis: Dict,
                                      balance: float) -> List[TradingRecommendation]:
        """高波动趋势建议"""
        recommendations = []

        # 建议1: 突破追单
        recommendations.append(TradingRecommendation(
            symbol=symbol,
            condition=MarketCondition.VOLATILE_TREND,
            action="buy",
            confidence=0.55,
            reason="高波动趋势,突破后追单",
            entry_zone=(current_price * 1.02, current_price * 1.05),
            stop_loss=current_price * 1.00,
            take_profit_levels=[current_price * 1.10],
            position_size_pct=0.015,  # 1.5%
            timeframe="1H",
            style=TradingStyle.SWING,
            risk_level="high",
            notes=[
                "确认突破有效后再入场",
                "使用较大的止损",
                "分批止盈锁定利润"
            ],
            warnings=["高波动市场滑点风险大", "需要快速反应"]
        ))

        # 建议2: 回调抄底(高风险)
        recommendations.append(TradingRecommendation(
            symbol=symbol,
            condition=MarketCondition.VOLATILE_TREND,
            action="buy",
            confidence=0.40,
            reason="高波动中回调抄底",
            entry_zone=(current_price * 0.93, current_price * 0.96),
            stop_loss=current_price * 0.91,
            take_profit_levels=[current_price * 1.08],
            position_size_pct=0.01,  # 1%
            timeframe="4H",
            style=TradingStyle.SWING,
            risk_level="very_high",
            notes=[
                "仅在有明确支撑时入场",
                "更小的仓位",
                "快速止损",
                "分批加仓"
            ],
            warnings=["极高风险策略", "可能面临更大亏损"]
        ))

        # 建议3: 等待观望
        recommendations.append(TradingRecommendation(
            symbol=symbol,
            condition=MarketCondition.VOLATILE_TREND,
            action="hold",
            confidence=0.85,
            reason="高波动市场,建议观望等待稳定",
            entry_zone=(0, 0),
            stop_loss=0,
            take_profit_levels=[],
            position_size_pct=0,
            timeframe="4H",
            style=TradingStyle.SWING,
            risk_level="none",
            notes=[
                "等待波动率降低",
                "等待趋势明确",
                "可以使用小仓位测试"
            ],
            warnings=["等待更清晰的入场信号"]
        ))

        return recommendations

    def _choppy_recommendations(self,
                                symbol: str,
                                current_price: float,
                                balance: float) -> List[TradingRecommendation]:
        """无序震荡建议"""
        return [
            TradingRecommendation(
                symbol=symbol,
                condition=MarketCondition.CHOPPY,
                action="hold",
                confidence=0.90,
                reason="无序震荡市场,建议避免交易",
                entry_zone=(0, 0),
                stop_loss=0,
                take_profit_levels=[],
                position_size_pct=0,
                timeframe="1D",
                style=TradingStyle.SWING,
                risk_level="none",
                notes=[
                    "市场缺乏明确方向",
                    "假信号概率很高",
                    "等待趋势形成后再交易"
                ],
                warnings=[
                    "避免在无序市场交易",
                    "此时交易容易导致亏损",
                    "考虑使用其他交易对"
                ]
            )
        ]

    def _strong_downtrend_recommendations(self,
                                        symbol: str,
                                        current_price: float,
                                        analysis: Dict,
                                        balance: float) -> List[TradingRecommendation]:
        """强下降趋势建议"""
        recommendations = []

        # 支撑阻力位
        support_levels = analysis.get("support_levels", [])
        nearest_support = min([s for s in support_levels if s < current_price],
                                default=current_price * 0.95)

        # 建议1: 突破做空
        recommendations.append(TradingRecommendation(
            symbol=symbol,
            condition=MarketCondition.STRONG_DOWNTREND,
            action="sell",
            confidence=0.75,
            reason="强下降趋势,等待突破支撑位",
            entry_zone=(nearest_support * 0.98, current_price * 1.02),
            stop_loss=current_price * 1.03,
            take_profit_levels=[
                nearest_support * 0.98,
                nearest_support * 0.95,
                nearest_support * 0.90
            ],
            position_size_pct=0.025,
            timeframe="4H",
            style=TradingStyle.SWING,
            risk_level="medium",
            notes=[
                "确认突破支撑位",
                "使用分批建仓",
                "目标位可以分批止盈"
            ],
            warnings=["强趋势中反弹可能较大"]
        ))

        # 建议2: 反弹做空(保守)
        recommendations.append(TradingRecommendation(
            symbol=symbol,
            condition=MarketCondition.STRONG_DOWNTREND,
            action="sell",
            confidence=0.80,
            reason="下降趋势中的反弹做空",
            entry_zone=(current_price * 1.01, current_price * 1.03),
            stop_loss=current_price * 1.05,
            take_profit_levels=[
                current_price * 0.95,
                current_price * 0.90
            ],
            position_size_pct=0.03,
            timeframe="1H",
            style=TradingStyle.SWING,
            risk_level="low",
            notes=[
                "反弹入场,更安全",
                "设置 tighter 止损",
                "盈利目标可以更激进"
            ],
            warnings=[]
        ))

        return recommendations

    def _generate_funding_arbitrage_recommendation(self,
                                               symbol: str,
                                               current_price: float,
                                               funding_rate: float,
                                               balance: float) -> Optional[TradingRecommendation]:
        """生成资金费率套利建议"""
        # 正资金费率: 做空收取费用
        if funding_rate > 0.0001:
            return TradingRecommendation(
                symbol=symbol,
                condition=MarketCondition.RANGING,
                action="sell",
                confidence=0.70 + min(funding_rate * 10000, 0.2),
                reason=f"正资金费率({funding_rate*100:.3f}%),做空收取费用",
                entry_zone=(current_price * 0.999, current_price * 1.001),
                stop_loss=current_price * (1 + abs(funding_rate) * 10),  # 宽止损
                take_profit_levels=[current_price * 0.98, current_price * 0.96],
                position_size_pct=0.03,
                timeframe="8H",
                style=TradingStyle.POSITION,
                risk_level="low",
                notes=[
                    "主要目的是收取资金费率",
                    "避免价格大幅波动导致亏损",
                    "持仓时间越长收益越高",
                    f"预期日收益: {funding_rate * 3 * 100:.4f}%"
                ],
                warnings=["资金费率可能变化", "需监控市场变化"]
            )

        # 负资金费率: 做多收取费用
        elif funding_rate < -0.0001:
            return TradingRecommendation(
                symbol=symbol,
                condition=MarketCondition.RANGING,
                action="buy",
                confidence=0.70 + min(abs(funding_rate) * 10000, 0.2),
                reason=f"负资金费率({funding_rate*100:.3f}%),做多收取费用",
                entry_zone=(current_price * 0.999, current_price * 1.001),
                stop_loss=current_price * (1 - abs(funding_rate) * 10),
                take_profit_levels=[current_price * 1.02, current_price * 1.04],
                position_size_pct=0.03,
                timeframe="8H",
                style=TradingStyle.POSITION,
                risk_level="low",
                notes=[
                    "主要目的是收取资金费率",
                    "避免价格大幅波动导致亏损",
                    "持仓时间越长收益越高",
                    f"预期日收益: {abs(funding_rate) * 3 * 100:.4f}%"
                ],
                warnings=["资金费率可能变化", "需监控市场变化"]
            )

        return None

    def get_trading_rules(self) -> List[Dict]:
        """获取交易规则"""
        rules = []

        # 基础规则
        rules.extend([
            {
                "rule_id": "R001",
                "category": "基础",
                "name": "单笔风险限制",
                "description": f"每笔交易最大风险{self.risk_per_trade*100:.1f}%",
                "action": "limit_position_size"
            },
            {
                "rule_id": "R002",
                "category": "基础",
                "name": "最大持仓数",
                "description": f"同时最多持有{self.max_positions}个品种",
                "action": "limit_positions"
            }
        ])

        # 市场状态规则
        rules.extend([
            {
                "rule_id": "M001",
                "category": "市场状态",
                "name": "强趋势优先顺势",
                "description": "强上升趋势只做多,强下降趋势只做空",
                "action": "direction_filter"
            },
            {
                "rule_id": "M002",
                "category": "市场状态",
                "name": "震荡市场使用区间策略",
                "description": "震荡市场采用支撑阻力交易,使用小仓位",
                "action": "use_range_strategy"
            },
            {
                "rule_id": "M003",
                "category": "市场状态",
                "name": "无序市场避免交易",
                "description": "无序震荡(choppy)市场暂停交易",
                "action": "avoid_trading"
            },
            {
                "rule_id": "M004",
                "category": "市场状态",
                "name": "高波动市场降低仓位",
                "description": "高波动市场使用50%标准仓位",
                "action": "reduce_position_size"
            }
        ])

        # 多时间框架规则
        rules.extend([
            {
                "rule_id": "T001",
                "category": "多时间框架",
                "name": "趋势对齐要求",
                "description": "要求日线和4小时趋势方向一致",
                "action": "check_trend_alignment"
            },
            {
                "rule_id": "T002",
                "category": "多时间框架",
                "name": "入场时间框架确认",
                "description": "用15分钟/5分钟确认精确入场点",
                "action": "confirm_entry_timing"
            },
            {
                "rule_id": "T003",
                "category": "多时间框架",
                "name": "趋势不一致观望",
                "description": "多时间框架趋势方向不一致时观望",
                "action": "wait_for_alignment"
            }
        ])

        # 风险管理规则
        rules.extend([
            {
                "rule_id": "K001",
                "category": "风险管理",
                "name": "止损立即设置",
                "description": "开仓后立即设置止损,不得延迟",
                "action": "set_stop_immediately"
            },
            {
                "rule_id": "K002",
                "category": "风险管理",
                "name": "止损不扩大",
                "description": "止损只能向有利方向移动,不能扩大",
                "action": "trail_only_profitable"
            },
            {
                "rule_id": "K003",
                "category": "风险管理",
                "name": "连续亏损减仓",
                "description": "连续2次亏损后仓位减半",
                "action": "reduce_on_consecutive_losses"
            },
            {
                "rule_id": "K004",
                "category": "风险管理",
                "name": "单日亏损限制",
                "description": "单日亏损超过5%暂停交易",
                "action": "daily_loss_limit"
            },
            {
                "rule_id": "K005",
                "category": "风险管理",
                "name": "相关性限制",
                "description": "避免同时持有高相关性品种",
                "action": "limit_correlated_positions"
            }
        ])

        # 资金费率套利规则
        rules.extend([
            {
                "rule_id": "F001",
                "category": "资金费率",
                "name": "正费做空",
                "description": "资金费率>0.01%时做空收取费用",
                "action": "short_positive_funding"
            },
            {
                "rule_id": "F002",
                "category": "资金费率",
                "name": "负费做多",
                "description": "资金费率<-0.01%时做多收取费用",
                "action": "long_negative_funding"
            },
            {
                "rule_id": "F003",
                "category": "资金费率",
                "name": "套利仓位控制",
                "description": "资金费率套利使用中仓位,避免高杠杆",
                "action": "use_medium_position"
            },
            {
                "rule_id": "F004",
                "category": "资金费率",
                "name": "套利时间要求",
                "description": "资金费率套利持仓至少8小时",
                "action": "minimum_hold_time"
            }
        ])

        return rules

    def get_optimization_suggestions(self,
                                   performance_stats: Dict) -> List[Dict]:
        """获取优化建议"""
        suggestions = []

        win_rate = performance_stats.get("win_rate", 0.5)
        profit_factor = performance_stats.get("profit_factor", 1.5)
        max_drawdown = performance_stats.get("max_drawdown", 0.1)
        sharpe_ratio = performance_stats.get("sharpe_ratio", 0.5)

        # 胜率优化
        if win_rate < 0.4:
            suggestions.append({
                "category": "胜率优化",
                "priority": "high",
                "suggestion": "胜率偏低,建议: 1) 增加入场确认条件 2) 等待更明确的趋势 3) 减少震荡市场交易",
                "expected_improvement": "胜率提升10-15%"
            })
        elif win_rate > 0.7:
            suggestions.append({
                "category": "胜率优化",
                "priority": "low",
                "suggestion": "胜率较高,可以考虑: 1) 适度增加仓位 2) 扩大交易品种",
                "expected_improvement": "总收益增加15-20%"
            })

        # 盈亏比优化
        if profit_factor < 1.2:
            suggestions.append({
                "category": "盈亏比优化",
                "priority": "high",
                "suggestion": f"盈亏比偏低({profit_factor:.2f}),建议: 1) 调整止盈目标 2) 使用移动止损锁定利润 3) 增加持仓时间",
                "expected_improvement": "盈亏比提升到1.5-2.0"
            })
        elif profit_factor > 2.5:
            suggestions.append({
                "category": "盈亏比优化",
                "priority": "medium",
                "suggestion": f"盈亏比较高({profit_factor:.2f}),可以考虑: 1) 适度收紧止损 2) 增加交易频率",
                "expected_improvement": "交易频率增加,整体收益稳定"
            })

        # 回撤优化
        if max_drawdown > 0.15:
            suggestions.append({
                "category": "回撤优化",
                "priority": "critical",
                "suggestion": f"最大回撤较高({max_drawdown*100:.1f}%),必须: 1) 降低单笔风险 2) 严格止损执行 3) 增加回撤保护机制",
                "expected_improvement": "最大回撤降低到8-10%"
            })
        elif max_drawdown > 0.1:
            suggestions.append({
                "category": "回撤优化",
                "priority": "high",
                "suggestion": f"回撤偏高({max_drawdown*100:.1f}%),建议: 1) 减小仓位 2) 使用更严格的止损 3) 考虑使用移动止损",
                "expected_improvement": "回撤降低到5-8%"
            })

        # 夏普比率优化
        if sharpe_ratio < 0.5:
            suggestions.append({
                "category": "风险调整收益比",
                "priority": "high",
                "suggestion": f"夏普比率偏低({sharpe_ratio:.2f}),建议: 1) 优化风险调整 2) 寻找更稳定的交易机会 3) 考虑资金费率套利",
                "expected_improvement": "夏普比率提升到1.0-1.5"
            })

        return suggestions

    def format_recommendations(self,
                               recommendations: List[TradingRecommendation]) -> str:
        """格式化输出建议"""
        output = []
        output.append("=" * 80)
        output.append(f"交易建议报告 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        output.append("=" * 80)

        for i, rec in enumerate(recommendations, 1):
            output.append(f"\n【建议 {i}】{rec.symbol} - {rec.condition.value.upper()}")
            output.append("-" * 80)
            output.append(f"  操作: {rec.action.upper()}")
            output.append(f"  置信度: {rec.confidence*100:.0f}%")
            output.append(f"  原因: {rec.reason}")
            output.append(f"  时间框架: {rec.timeframe}")
            output.append(f"  交易风格: {rec.style.value}")
            output.append(f"  风险等级: {rec.risk_level}")

            if rec.entry_zone[0] > 0:
                output.append(f"  入场区间: {rec.entry_zone[0]:.4f} - {rec.entry_zone[1]:.4f}")
            else:
                output.append("  入场区间: 待观察")

            if rec.stop_loss > 0:
                output.append(f"  止损: {rec.stop_loss:.4f}")

            if rec.take_profit_levels:
                tp_str = " / ".join([f"{tp:.4f}" for tp in rec.take_profit_levels])
                output.append(f"  止盈位: {tp_str}")

            output.append(f"  建议仓位: {rec.position_size_pct*100:.1f}%")

            if rec.notes:
                output.append("\n  说明:")
                for note in rec.notes:
                    output.append(f"    • {note}")

            if rec.warnings:
                output.append("\n  警告:")
                for warning in rec.warnings:
                    output.append(f"    ⚠️  {warning}")

        output.append("\n" + "=" * 80)

        return "\n".join(output)


def create_trading_advisor(config: Dict = None) -> TradingAdvisor:
    """创建交易顾问"""
    return TradingAdvisor(config)


if __name__ == "__main__":
    # 测试代码
    advisor = TradingAdvisor()

    # 模拟市场分析
    market_analysis = {
        "symbol": "BTCUSDT",
        "current_price": 40000,
        "market_state": "strong_uptrend",
        "trend_strength": 0.8,
        "volatility_level": "medium",
        "support_levels": [38000, 39000],
        "resistance_levels": [41000, 42000],
        "multi_timeframe_signal": {
            "composite_signal": "buy",
            "trend_alignment": True,
            "confidence": 0.75
        }
    }

    # 生成建议
    recommendations = advisor.generate_recommendations(
        market_analysis,
        funding_rate=0.00025,
        account_balance=10000
    )

    # 输出建议
    print(advisor.format_recommendations(recommendations))

    # 输出规则
    rules = advisor.get_trading_rules()
    print(f"\n\n交易规则数量: {len(rules)}")
    for rule in rules[:10]:  # 显示前10条
        print(f"\n  [{rule['rule_id']}] {rule['name']}")
        print(f"    类别: {rule['category']}")
        print(f"    说明: {rule['description']}")
        print(f"    行动: {rule['action']}")
