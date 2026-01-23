# 交易系统优化指南
# 基于已实现的系统提供详细的优化建议

from typing import Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class OptimizationArea(Enum):
    """优化领域"""
    RISK_MANAGEMENT = "risk_management"           # 风险管理
    SIGNAL_QUALITY = "signal_quality"               # 信号质量
    POSITION_SIZING = "position_sizing"           # 仓位管理
    EXIT_STRATEGY = "exit_strategy"                # 出场策略
    PORTFOLIO_DIVERSIFICATION = "portfolio_diversification"  # 投资组合分散
    PSYCHOLOGICAL = "psychological"               # 心理控制
    SYSTEM_PERFORMANCE = "system_performance"         # 系统性能


@dataclass
class OptimizationAction:
    """优化行动"""
    area: OptimizationArea
    priority: str  # high/medium/low
    title: str
    description: str
    implementation_steps: List[str]
    expected_benefit: str
    complexity: str  # low/medium/high
    estimated_hours: int


@dataclass
class OptimizationPlan:
    """优化计划"""
    timestamp: datetime
    performance_baseline: Dict
    actions: List[OptimizationAction]
    quick_wins: List[OptimizationAction]  # 快速改进
    long_term_goals: List[OptimizationAction]  # 长期目标


class TradingSystemOptimizer:
    """交易系统优化器"""

    def __init__(self, config: Dict = None):
        self.config = config or {}

        # 优化历史
        self.optimization_history: List[OptimizationPlan] = []

        # 当前系统状态
        self.current_state = {
            "risk_per_trade": 0.02,
            "max_positions": 3,
            "win_rate": 0.5,
            "profit_factor": 1.5,
            "max_drawdown": 0.1,
            "sharpe_ratio": 0.5
        }

    def analyze_and_generate_optimization_plan(self,
                                             performance_data: Dict,
                                             system_state: Dict) -> OptimizationPlan:
        """
        分析当前状态并生成优化计划

        参数:
            performance_data: 性能数据
            system_state: 系统当前状态

        返回:
            OptimizationPlan
        """
        # 更新当前状态
        self.current_state.update(system_state)

        actions = []
        quick_wins = []
        long_term_goals = []

        # 分析各领域并生成优化行动
        actions.extend(self._analyze_risk_management(performance_data))
        actions.extend(self._analyze_signal_quality(performance_data))
        actions.extend(self._analyze_position_sizing(performance_data))
        actions.extend(self._analyze_exit_strategy(performance_data))
        actions.extend(self._analyze_portfolio_diversification(performance_data))
        actions.extend(self._analyze_psychological(performance_data))
        actions.extend(self._analyze_system_performance(performance_data))

        # 分类优化行动
        for action in actions:
            if action.complexity == "low" and action.estimated_hours <= 2:
                quick_wins.append(action)
            elif action.complexity == "low" or action.priority == "high":
                quick_wins.append(action)
            else:
                long_term_goals.append(action)

        # 排序
        priority_order = {"high": 0, "medium": 1, "low": 2}
        quick_wins.sort(key=lambda x: priority_order[x.priority])
        long_term_goals.sort(key=lambda x: priority_order[x.priority])

        plan = OptimizationPlan(
            timestamp=datetime.now(),
            performance_baseline=performance_data,
            actions=actions,
            quick_wins=quick_wins,
            long_term_goals=long_term_goals
        )

        self.optimization_history.append(plan)
        return plan

    def _analyze_risk_management(self, performance_data: Dict) -> List[OptimizationAction]:
        """分析风险管理"""
        actions = []
        win_rate = performance_data.get("win_rate", 0.5)
        max_drawdown = performance_data.get("max_drawdown", 0.1)
        consecutive_losses = performance_data.get("consecutive_losses", 0)

        # 高胜率但高回撤 - 需要更积极的仓位管理
        if win_rate > 0.6 and max_drawdown > 0.08:
            actions.append(OptimizationAction(
                area=OptimizationArea.RISK_MANAGEMENT,
                priority="high",
                title="实施更积极的移动止损",
                description="当前高胜率但高回撤,需要更积极的移动止损策略",
                implementation_steps=[
                    "启用dynamic策略的移动止损引擎",
                    "设置激活阈值为2%盈利",
                    "设置锁定利润比例为60%",
                    "盈利超过5%后每1%盈利移动止损0.5%"
                ],
                expected_benefit="最大回撤降低至6-8%",
                complexity="medium",
                estimated_hours=4
            ))

        # 连续亏损 - 需要更严格的风险控制
        if consecutive_losses >= 3:
            actions.append(OptimizationAction(
                area=OptimizationArea.RISK_MANAGEMENT,
                priority="critical",
                title="实施连续亏损保护机制",
                description="连续亏损需要立即降低风险",
                implementation_steps=[
                    "连续3次亏损后仓位减至50%",
                    "连续4次亏损后仓位减至25%",
                    "连续5次亏损后暂停交易1天",
                    "恢复盈利后逐步恢复仓位"
                ],
                expected_benefit="避免连续亏损扩大",
                complexity="low",
                estimated_hours=1
            ))

        # 固定仓位 - 需要动态仓位
        if self.current_state["risk_per_trade"] == 0.02:  # 检查是否是固定仓位
            actions.append(OptimizationAction(
                area=OptimizationArea.RISK_MANAGEMENT,
                priority="high",
                title="实施动态仓位管理",
                description="基于ATR和Kelly准则动态计算仓位",
                implementation_steps=[
                    "启用DynamicPositionSizer",
                    "设置risk_model为composite",
                    "配置ATR窗口为14",
                    "设置Kelly分数为0.5(半Kelly)",
                    "根据波动率调整仓位:高波动减50%,低波动增20%"
                ],
                expected_benefit="降低回撤20-30%",
                complexity="medium",
                estimated_hours=3
            ))

        return actions

    def _analyze_signal_quality(self, performance_data: Dict) -> List[OptimizationAction]:
        """分析信号质量"""
        actions = []

        win_rate = performance_data.get("win_rate", 0.5)
        trade_count = performance_data.get("trade_count", 0)

        # 低胜率 - 需要改善信号过滤
        if win_rate < 0.4 and trade_count >= 20:
            actions.append(OptimizationAction(
                area=OptimizationArea.SIGNAL_QUALITY,
                priority="high",
                title="实施多时间框架确认",
                description="当前胜率偏低,需要更严格的信号确认",
                implementation_steps=[
                    "配置多时间框架:日线(4H),4小时(1H),1小时(15M)",
                    "要求日线和4小时趋势方向一致",
                    "使用15分钟时间框架确认精确入场点",
                    "设置最低置信度为70%才入场",
                    "在趋势不一致时暂停交易"
                ],
                expected_benefit="胜率提升至55-60%",
                complexity="high",
                estimated_hours=6
            ))

        # 启用市场状态过滤
        if not self.current_state.get("market_filter_enabled", False):
            actions.append(OptimizationAction(
                area=OptimizationArea.SIGNAL_QUALITY,
                priority="high",
                title="启用市场状态过滤器",
                description="避免在不适合的市场状态下交易",
                implementation_steps=[
                    "检测8种市场状态(strong_uptrend到choppy)",
                    "配置状态到策略的映射",
                    "无序市场(choppy)完全避免交易",
                    "震荡市场(ranging)仅使用均值回归策略",
                    "强趋势市场仅使用趋势跟踪策略"
                ],
                expected_benefit="减少50%的假信号",
                complexity="medium",
                estimated_hours=4
            ))

        # 添加技术指标组合
        actions.append(OptimizationAction(
            area=OptimizationArea.SIGNAL_QUALITY,
            priority="medium",
            title="增加信号确认指标",
            description="使用多个指标组合确认信号",
            implementation_steps=[
                "主信号: MA交叉(7日和25日)",
                "确认1: RSI不在超买超卖区(30-70范围)",
                "确认2: MACD柱状图同方向",
                "确认3: 成交量放大(至少是平均的1.2倍)",
                "所有条件满足才入场"
            ],
            expected_benefit="信号质量提升30%",
            complexity="low",
                estimated_hours=2
        ))

        return actions

    def _analyze_position_sizing(self, performance_data: Dict) -> List[OptimizationAction]:
        """分析仓位管理"""
        actions = []

        # 基于波动率的仓位调整
        actions.append(OptimizationAction(
            area=OptimizationArea.POSITION_SIZING,
            priority="medium",
            title="实施波动率自适应仓位",
            description="根据市场波动率动态调整仓位大小",
            implementation_steps=[
                "使用ATR(14周期)测量波动率",
                "正常波动率(ATR/价格 <1%)使用标准风险2%",
                "高波动率(ATR/价格 >2%)使用50%标准风险1%",
                "极高波动率(ATR/价格 >3%)使用25%标准风险0.5%",
                "低波动率(ATR/价格 <0.5%)使用150%标准风险3%",
                "每天开盘时计算当日波动率并调整仓位"
            ],
            expected_benefit="适应不同市场条件,稳定收益",
            complexity="medium",
            estimated_hours=3
        ))

        # Kelly准则优化
        if self.current_state.get("win_rate", 0.5) > 0.55:
            actions.append(OptimizationAction(
                area=OptimizationArea.POSITION_SIZING,
                priority="low",
                title="考虑启用Kelly准则",
                description="当前胜率较高,可以尝试Kelly准则",
                implementation_steps=[
                    "计算历史胜率、平均盈利、平均亏损",
                    "Kelly f = (胜率*平均盈利 - 败率*平均亏损) / 平均盈利",
                    "使用半Kelly(0.5 * f)降低风险",
                    "设置最大仓位为Kelly的50%",
                    "每20笔交易重新计算一次Kelly值"
                ],
            expected_benefit="在正期望时最大化长期增长",
            complexity="high",
            estimated_hours=5
        ))

        return actions

    def _analyze_exit_strategy(self, performance_data: Dict) -> List[OptimizationAction]:
        """分析出场策略"""
        actions = []

        profit_factor = performance_data.get("profit_factor", 1.5)
        avg_holding_time = performance_data.get("avg_holding_time", 120)  # 分钟

        # 分批止盈优化
        actions.append(OptimizationAction(
            area=OptimizationArea.EXIT_STRATEGY,
            priority="high",
            title="实施分批止盈策略",
            description="分批锁定利润,避免错过大行情",
            implementation_steps=[
                "设置3个止盈目标: 1.5倍止损距离、2.5倍、4倍",
                "盈利达到第一个目标时平仓30%",
                "盈利达到第二个目标时再平仓40%",
                "剩余30%保持到最后目标",
                "使用OCO订单或手动执行"
            ],
            expected_benefit="提高盈利兑现率",
            complexity="low",
            estimated_hours=2
        ))

        # 移动止盈优化
        actions.append(OptimizationAction(
            area=OptimizationArea.EXIT_STRATEGY,
            priority="medium",
            title="优化移动止盈策略",
            description="在盈利时逐步收紧移动止盈",
            implementation_steps=[
                "盈利达到2%时激活移动止盈",
                "初始移动距离为1%",
                "每增加1%盈利,移动距离减少0.2%",
                "确保移动止盈只能向有利方向移动",
                "至少锁定50%已有利润",
                "价格回撤触发移动止盈时保护利润"
            ],
            expected_benefit="锁定更多利润",
            complexity="low",
            estimated_hours=2
        ))

        # 基于时间的出场
        if avg_holding_time > 240:  # 超过4小时
            actions.append(OptimizationAction(
                area=OptimizationArea.EXIT_STRATEGY,
                priority="medium",
                title="实施时间止损",
                description="长期持仓使用时间止损避免资金占用",
                implementation_steps=[
                    "设置最大持仓时间为4小时",
                    "持仓时间超过3小时检查趋势是否继续",
                    "趋势减弱时考虑提前出场",
                    "到达时间限制时评估市场状态决定是否续仓"
                ],
                expected_benefit="提高资金周转率",
                complexity="low",
                estimated_hours=2
        ))

        return actions

    def _analyze_portfolio_diversification(self, performance_data: Dict) -> List[OptimizationAction]:
        """分析投资组合分散"""
        actions = []

        # 品种相关性检查
        actions.append(OptimizationAction(
            area=OptimizationArea.PORTFOLIO_DIVERSIFICATION,
            priority="medium",
            title="实施品种相关性检查",
            description="避免同时持有高相关品种,分散风险",
            implementation_steps=[
                "计算各品种之间的Pearson相关性",
                "设置相关性阈值为0.7",
                "禁止同时持有相关性超过0.7的品种同方向",
                "同高相关品种只能多空对冲",
                "相关性超过0.8的品种限制总暴露为10%"
            ],
            expected_benefit="降低组合风险30-40%",
            complexity="high",
            estimated_hours=6
        ))

        # 多样化时间框架
        actions.append(OptimizationAction(
            area=OptimizationArea.PORTFOLIO_DIVERSIFICATION,
            priority="low",
            title="使用多个时间框架的交易",
            description="不同品种使用不同时间框架",
            implementation_steps=[
                "BTC/ETH使用4H-1H-15M组合",
                "DeFi代币使用1H-15M-5M组合",
                "小盘币使用15M-5M组合",
                "每个组合独立运行,不相互干扰",
                "总仓位分散到不同时间框架"
            ],
            expected_benefit="分散交易机会",
            complexity="medium",
            estimated_hours=4
        ))

        return actions

    def _analyze_psychological(self, performance_data: Dict) -> List[OptimizationAction]:
        """分析心理控制"""
        actions = []

        # 交易频率控制
        actions.append(OptimizationAction(
            area=OptimizationArea.PSYCHOLOGICAL,
            priority="high",
            title="实施交易频率控制",
            description="避免过度交易,保持冷静心态",
            implementation_steps=[
                "设置每日最大交易次数为5次",
                "设置每两笔交易间隔至少30分钟",
                "设置最大持仓数为3个",
                "亏损后强制暂停交易1小时",
                "连续3次亏损后暂停交易直到第二天"
            ],
            expected_benefit="减少情绪化决策",
            complexity="low",
            estimated_hours=1
        ))

        # 盈亏比记录
        actions.append(OptimizationAction(
            area=OptimizationArea.PSYCHOLOGICAL,
            priority="medium",
            title="建立交易日志",
            description="记录每笔交易的详细信息,便于复盘",
            implementation_steps=[
                "记录入场理由和市场状态",
                "记录情绪评分(1-5)",
                "记录出场原因和盈亏",
                "每周回顾日志,识别错误模式",
                "根据日志调整策略"
            ],
            expected_benefit="持续改进交易能力",
            complexity="low",
            estimated_hours=2
        ))

        # 冷却机制
        actions.append(OptimizationAction(
            area=OptimizationArea.PSYCHOLOGICAL,
            priority="medium",
            title="实施心理冷却机制",
            description="在连续亏损后设置强制冷却期",
            implementation_steps=[
                "连续2次亏损后强制暂停30分钟",
                "连续3次亏损后强制暂停2小时",
                "连续4次亏损后强制暂停至收盘",
                "冷却期内只观察不交易",
                "使用冷却期进行复盘和学习"
            ],
            expected_benefit="避免情绪化追涨杀跌",
            complexity="low",
            estimated_hours=1
        ))

        return actions

    def _analyze_system_performance(self, performance_data: Dict) -> List[OptimizationAction]:
        """分析系统性能"""
        actions = []

        # 参数自适应
        actions.append(OptimizationAction(
            area=OptimizationArea.SYSTEM_PERFORMANCE,
            priority="high",
            title="启用参数自适应系统",
            description="根据市场状况自动调整策略参数",
            implementation_steps=[
                "配置adaptation_mode为hybrid",
                "根据波动率自动调整止损距离",
                "根据趋势强度调整仓位大小",
                "根据历史表现调整入场要求",
                "每小时评估市场状态并更新参数",
                "参数变化幅度限制在20%以内避免过度调整"
            ],
            expected_benefit="适应市场变化,提高稳定性",
            complexity="high",
            estimated_hours=8
        ))

        # 资金费率套利
        actions.append(OptimizationAction(
            area=OptimizationArea.SYSTEM_PERFORMANCE,
            priority="medium",
            title="整合资金费率套利策略",
            description="利用永续合约的资金费率获取稳定收益",
            implementation_steps=[
                "监控各品种资金费率",
                "资金费率>0.01%时做空收取费用",
                "资金费率<-0.01%时做多收取费用",
                "设置最小盈利阈值为0.1%",
                "使用8-24小时持仓时间",
                "注意价格波动风险,设置止损保护"
            ],
            expected_benefit="稳定年化收益5-10%",
            complexity="medium",
            estimated_hours=4
        ))

        # 移动止损引擎整合
        actions.append(OptimizationAction(
            area=OptimizationArea.SYSTEM_PERFORMANCE,
            priority="high",
            title="整合高级移动止损引擎",
            description="使用多策略移动止损(ATR/支撑阻力/动态等)",
            implementation_steps=[
                "配置default_strategy为dynamic",
                "根据市场状态自动切换止损策略",
                "高波动使用ATR策略(更大空间)",
                "低波动使用支撑阻力策略(更精确)",
                "盈利达到2%时激活移动止损",
                "价格每更新都重新计算止损位"
            ],
            expected_benefit="提升盈利兑现率15-25%",
            complexity="medium",
            estimated_hours=3
        ))

        # 系统监控和告警
        actions.append(OptimizationAction(
            area=OptimizationArea.SYSTEM_PERFORMANCE,
            priority="medium",
            title="实施系统监控和告警",
            description="实时监控系统状态,及时发现异常",
            implementation_steps=[
                "监控账户余额和持仓情况",
                "设置最大回撤告警(10%)",
                "设置每日亏损告警(5%)",
                "设置连续亏损告警(3次)",
                "通过Telegram或邮件及时通知",
                "异常情况自动停止交易"
            ],
            expected_benefit="及时发现和处理风险",
            complexity="low",
            estimated_hours=2
        ))

        return actions

    def format_optimization_plan(self, plan: OptimizationPlan) -> str:
        """格式化输出优化计划"""
        output = []
        output.append("=" * 80)
        output.append(f"交易系统优化计划 - {plan.timestamp.strftime('%Y-%m-%d %H:%M')}")
        output.append("=" * 80)

        # 性能基线
        output.append("\n【性能基线】")
        baseline = plan.performance_baseline
        output.append(f"  胜率: {baseline.get('win_rate', 0)*100:.1f}%")
        output.append(f"  盈亏比: {baseline.get('profit_factor', 0):.2f}")
        output.append(f"  最大回撤: {baseline.get('max_drawdown', 0)*100:.1f}%")
        output.append(f"  夏普比率: {baseline.get('sharpe_ratio', 0):.2f}")
        output.append(f"  总交易数: {baseline.get('trade_count', 0)}")

        # 快速改进
        if plan.quick_wins:
            output.append(f"\n【快速改进】(预计{sum(a.estimated_hours for a in plan.quick_wins)}小时)")
            for i, action in enumerate(plan.quick_wins, 1):
                output.append(f"\n{i}. {action.title} [{action.priority}优先级]")
                output.append(f"   描述: {action.description}")
                output.append(f"   预期收益: {action.expected_benefit}")
                output.append(f"   复杂度: {action.complexity}")
                output.append(f"   实施步骤:")
                for step in action.implementation_steps:
                    output.append(f"      • {step}")

        # 长期目标
        if plan.long_term_goals:
            output.append(f"\n【长期目标】(预计{sum(a.estimated_hours for a in plan.long_term_goals)}小时)")
            for i, action in enumerate(plan.long_term_goals, 1):
                output.append(f"\n{i}. {action.title} [{action.priority}优先级]")
                output.append(f"   描述: {action.description}")
                output.append(f"   预期收益: {action.expected_benefit}")
                output.append(f"   复杂度: {action.complexity}")
                output.append(f"   实施步骤:")
                for step in action.implementation_steps:
                    output.append(f"      • {step}")

        # 总计
        total_hours = sum(a.estimated_hours for a in plan.actions)
        output.append(f"\n【总计】")
        output.append(f"  优化行动数: {len(plan.actions)}")
        output.append(f"  预计总工时: {total_hours}小时")
        output.append(f"  快速改进: {len(plan.quick_wins)}项")
        output.append(f"  长期目标: {len(plan.long_term_goals)}项")

        output.append("\n" + "=" * 80)

        return "\n".join(output)

    def get_best_practices(self) -> List[Dict]:
        """获取最佳实践"""
        return [
            {
                "category": "入场管理",
                "title": "多时间框架确认",
                "description": "使用日线和4小时确认趋势,1小时确定方向,15分钟精确入场",
                "do": "等待所有时间框架信号一致",
                "don't": "单一时间框架假信号时立即入场"
            },
            {
                "category": "仓位管理",
                "title": "动态仓位计算",
                "description": "基于ATR和风险百分比动态计算仓位",
                "do": "根据波动率调整仓位大小",
                "don't": "使用固定的仓位大小不管市场条件"
            },
            {
                "category": "止损管理",
                "title": "止损立即设置",
                "description": "开仓后立即设置止损,不得延迟或取消",
                "do": "使用OCO订单或设置后立即挂止损单",
                "don't": "心理止损或计划以后再设"
            },
            {
                "category": "止盈管理",
                "title": "分批止盈",
                "description": "达到目标时分批平仓,锁定部分利润",
                "do": "设置多个止盈位,分批出场",
                "don't": "持有等待完全目标,可能错过反转"
            },
            {
                "category": "市场过滤",
                "title": "市场状态识别",
                "description": "识别市场状态,避免不利条件下的交易",
                "do": "震荡市场时使用区间策略,无序时暂停",
                "don't": "所有市场条件下使用相同策略"
            },
            {
                "category": "心理控制",
                "title": "交易频率控制",
                "description": "限制每日交易次数和持仓数量",
                "do": "设定每日最大交易5次,持仓不超过3个",
                "don't": "频繁交易或持仓过多"
            },
            {
                "category": "风险管理",
                "title": "连续亏损保护",
                "description": "连续亏损时逐步减小仓位或暂停",
                "do": "连续2次亏损后减仓,连续3次后暂停",
                "don't": "亏损后加大仓位试图回本"
            },
            {
                "category": "系统优化",
                "title": "参数自适应",
                "description": "根据市场状况和历史表现自动调整参数",
                "do": "启用参数自适应系统,动态优化",
                "don't": "长期不调整参数导致策略失效"
            }
        ]

    def get_common_mistakes_and_solutions(self) -> List[Dict]:
        """获取常见错误和解决方案"""
        return [
            {
                "mistake": "过度交易",
                "description": "频繁开平仓,增加手续费和滑点",
                "impact": "高",
                "solution": [
                    "设置每日最大交易次数(建议3-5次)",
                    "设置最小交易间隔(建议30分钟)",
                    "设置最大持仓数(建议2-3个)",
                    "制定交易计划并严格执行"
                ]
            },
            {
                "mistake": "情绪化交易",
                "description": "因恐惧或贪婪做出非理性决策",
                "impact": "极高",
                "solution": [
                    "亏损后强制暂停交易(建议1小时)",
                    "盈利后保持冷静,避免过度自信",
                    "制定明确的交易规则并遵守",
                    "记录情绪日志进行自我监控"
                ]
            },
            {
                "mistake": "移动止损",
                "description": "价格回调时因为心理因素放宽止损",
                "impact": "高",
                "solution": [
                    "使用自动止损引擎,避免人工干预",
                    "设置止损只能向有利方向移动",
                    "使用OCO订单一次性设置止损止盈",
                    "禁止取消或扩大止损"
                ]
            },
            {
                "mistake": "逆势交易",
                "description": "在强趋势中逆势做反弹",
                "impact": "高",
                "solution": [
                    "等待趋势确认信号后再入场",
                    "使用多时间框架确认趋势方向",
                    "逆势交易使用更小的仓位(50%)",
                    "设置更严格的止损"
                ]
            },
            {
                "mistake": "不加止损",
                "description": "抱着侥幸心理不设置止损",
                "impact": "极高",
                "solution": [
                    "开仓前必须确定止损位",
                    "止损是最后防线,不可取消",
                    "使用交易所的强制平仓功能",
                    "定期检查止损是否有效"
                ]
            },
            {
                "mistake": "仓位过重",
                "description": "单个品种仓位过大,风险集中",
                "impact": "高",
                "solution": [
                    "单笔风险不超过2-3%",
                    "总风险不超过10%",
                    "分散到2-3个不相关品种",
                    "高波动品种使用更小仓位"
                ]
            },
            {
                "mistake": "追涨杀跌",
                "description": "价格快速波动时盲目跟随",
                "impact": "中",
                "solution": [
                    "等待价格稳定后再做决策",
                    "确认趋势后再入场",
                    "不要在快速拉升的高点追多",
                    "不要在快速下跌的低点杀跌"
                ]
            },
            {
                "mistake": "缺乏复盘",
                "description": "不记录和回顾交易,重复犯错",
                "impact": "中",
                "solution": [
                    "记录每笔交易的详细信息",
                    "每周/每月进行交易复盘",
                    "识别盈利交易和亏损交易的共同特征",
                    "根据复盘结果调整策略"
                ]
            },
            {
                "mistake": "忽视资金费率",
                "description": "永续合约不考虑资金费率成本",
                "impact": "中",
                "solution": [
                    "检查资金费率方向和大小",
                    "正费率时考虑做空套利",
                    "负费率时考虑做多套利",
                    "长时间持仓时资金费率成本很高"
                ]
            }
        ]


def create_system_optimizer(config: Dict = None) -> TradingSystemOptimizer:
    """创建系统优化器"""
    return TradingSystemOptimizer(config)


if __name__ == "__main__":
    # 测试代码
    optimizer = TradingSystemOptimizer()

    # 模拟性能数据
    performance_data = {
        "win_rate": 0.42,
        "profit_factor": 1.3,
        "max_drawdown": 0.15,
        "sharpe_ratio": 0.45,
        "consecutive_losses": 2,
        "trade_count": 35,
        "avg_holding_time": 180
    }

    system_state = {
        "risk_per_trade": 0.02,
        "max_positions": 3,
        "market_filter_enabled": False
    }

    # 生成优化计划
    plan = optimizer.analyze_and_generate_optimization_plan(
        performance_data, system_state
    )

    # 输出优化计划
    print(optimizer.format_optimization_plan(plan))

    # 输出最佳实践
    print("\n\n【交易最佳实践】")
    practices = optimizer.get_best_practices()
    for practice in practices:
        print(f"\n{practice['category']}: {practice['title']}")
        print(f"  描述: {practice['description']}")
        print(f"  应该: {practice['do']}")
        print(f"  避免: {practice['don't']}")

    # 输出常见错误
    print("\n\n【常见错误与解决方案】")
    mistakes = optimizer.get_common_mistakes_and_solutions()
    for i, mistake in enumerate(mistakes, 1):
        print(f"\n{i}. {mistake['mistake']}")
        print(f"  描述: {mistake['description']}")
        print(f"  影响: {mistake['impact']}")
        print(f"  解决方案:")
        for sol in mistake['solution']:
            print(f"    • {sol}")
