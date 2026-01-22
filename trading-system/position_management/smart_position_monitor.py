# 智能持仓监控管理器
# 自动扫描持仓并基于多维度数据进行智能决策

import os
import json
import logging
import time
import threading
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class Position:
    """持仓数据结构"""
    platform: str  # MT5 或 交易所名称
    symbol: str
    side: str  # long/short
    entry_price: float
    current_price: float
    size: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    entry_time: Optional[str] = None
    leverage: Optional[int] = 1
    ticket: Optional[str] = None  # 订单ID


@dataclass
class MarketContext:
    """市场环境上下文"""
    symbol: str
    current_price: float
    trend: str  # uptrend/downtrend/sideways
    volatility: str  # low/medium/high
    volume_ratio: float  # 相对平均成交量
    support_levels: List[float]
    resistance_levels: List[float]
    rsi: float
    macd_signal: str  # bullish/bearish/neutral
    news_sentiment: str  # positive/negative/neutral
    news_score: float  # -1 to 1
    funding_rate: Optional[float] = None  # 资金费率(仅合约)
    order_book_pressure: Optional[float] = None  # 买卖压力比


@dataclass
class Decision:
    """决策结果"""
    action: str  # hold/close/adjust_sl/adjust_tp/partial_close
    confidence: float  # 0-1
    reason: List[str]
    risk_level: str  # low/medium/high
    suggested_sl: Optional[float] = None
    suggested_tp: Optional[float] = None
    close_percentage: Optional[float] = None  # 部分平仓百分比
    urgency: str = "normal"  # low/normal/high/critical


class SmartPositionMonitor:
    """智能持仓监控器"""

    def __init__(self, config: Dict):
        self.config = config
        self.enabled = config.get("enabled", True)
        self.scan_interval = config.get("scan_interval_seconds", 30)
        self.auto_execute = config.get("auto_execute", False)
        self.require_confirmation = config.get("require_confirmation", True)

        # 风险管理参数
        self.max_loss_per_position_pct = config.get("max_loss_per_position_pct", 5)
        self.target_profit_pct = config.get("target_profit_pct", 10)
        self.trailing_stop_trigger_pct = config.get("trailing_stop_trigger_pct", 3)
        self.partial_close_profit_pct = config.get("partial_close_profit_pct", 5)

        # 决策权重
        self.weights = config.get("decision_weights", {
            "technical": 0.4,
            "fundamental": 0.2,
            "news": 0.2,
            "risk": 0.2
        })

        # 数据提供者(稍后注入)
        self.mt5_bridge = None
        self.exchange_traders = {}
        self.data_provider = None
        self.ai_ensemble = None
        self.news_aggregator = None
        self.indicator_system = None

        # 监控状态
        self.is_running = False
        self.monitoring_thread = None
        self.last_scan_time = None
        self.decisions_history = []

        # 决策缓存(避免短时间内重复决策)
        self.decision_cache = {}
        self.cache_ttl = 60  # 秒

    def set_providers(self, mt5_bridge=None, exchange_traders=None,
                     data_provider=None, ai_ensemble=None,
                     news_aggregator=None, indicator_system=None):
        """设置数据提供者"""
        self.mt5_bridge = mt5_bridge
        self.exchange_traders = exchange_traders or {}
        self.data_provider = data_provider
        self.ai_ensemble = ai_ensemble
        self.news_aggregator = news_aggregator
        self.indicator_system = indicator_system
        logger.info("数据提供者已设置")

    def start(self):
        """启动监控"""
        if self.is_running:
            logger.warning("持仓监控已在运行中")
            return

        self.is_running = True
        self.monitoring_thread = threading.Thread(
            target=self._monitoring_loop,
            daemon=True
        )
        self.monitoring_thread.start()
        logger.info(f"智能持仓监控已启动 (扫描间隔: {self.scan_interval}秒)")

    def stop(self):
        """停止监控"""
        self.is_running = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5)
        logger.info("智能持仓监控已停止")

    def _monitoring_loop(self):
        """监控主循环"""
        while self.is_running:
            try:
                self.scan_and_analyze()
                self.last_scan_time = datetime.now()
            except Exception as e:
                logger.error(f"持仓扫描出错: {e}")

            # 等待下次扫描
            time.sleep(self.scan_interval)

    def scan_and_analyze(self) -> List[Tuple[Position, Decision]]:
        """扫描所有持仓并分析"""
        logger.info("开始扫描持仓...")

        all_positions = self._get_all_positions()
        results = []

        for position in all_positions:
            # 检查缓存
            cache_key = f"{position.platform}_{position.symbol}_{position.ticket}"
            if cache_key in self.decision_cache:
                cached_time, cached_decision = self.decision_cache[cache_key]
                if time.time() - cached_time < self.cache_ttl:
                    logger.debug(f"使用缓存决策: {cache_key}")
                    results.append((position, cached_decision))
                    continue

            # 获取市场上下文
            market_context = self._get_market_context(position)

            # 生成决策
            decision = self._make_decision(position, market_context)

            # 缓存决策
            self.decision_cache[cache_key] = (time.time(), decision)

            # 记录
            results.append((position, decision))
            self._log_decision(position, decision, market_context)

            # 执行决策
            if self.auto_execute and decision.action != "hold":
                self._execute_decision(position, decision)

        logger.info(f"持仓扫描完成,共分析 {len(all_positions)} 个持仓")
        return results

    def _get_all_positions(self) -> List[Position]:
        """获取所有平台的持仓"""
        positions = []

        # MT5持仓
        if self.mt5_bridge:
            try:
                mt5_positions = self.mt5_bridge.get_positions()
                for pos in mt5_positions:
                    positions.append(Position(
                        platform="MT5",
                        symbol=pos["symbol"],
                        side="long" if pos["type"] == "买入" else "short",
                        entry_price=pos["price"],
                        current_price=self._get_current_price("MT5", pos["symbol"]),
                        size=pos["volume"],
                        unrealized_pnl=pos["profit"],
                        unrealized_pnl_pct=self._calculate_pnl_pct(
                            pos["price"],
                            self._get_current_price("MT5", pos["symbol"]),
                            pos["type"] == "买入"
                        ),
                        stop_loss=pos.get("sl"),
                        take_profit=pos.get("tp"),
                        entry_time=pos.get("time"),
                        ticket=str(pos["ticket"])
                    ))
            except Exception as e:
                logger.error(f"获取MT5持仓失败: {e}")

        # 交易所持仓
        for exchange_name, trader in self.exchange_traders.items():
            try:
                if hasattr(trader, 'data_provider'):
                    exchange_positions = trader.data_provider.get_positions()
                    for pos in exchange_positions:
                        if pos["size"] != 0:  # 忽略空持仓
                            positions.append(Position(
                                platform=exchange_name,
                                symbol=pos["symbol"],
                                side=pos["side"],
                                entry_price=pos["entry_price"],
                                current_price=pos["mark_price"],
                                size=pos["size"],
                                unrealized_pnl=pos["unrealized_pnl"],
                                unrealized_pnl_pct=self._calculate_pnl_pct(
                                    pos["entry_price"],
                                    pos["mark_price"],
                                    pos["side"] == "long"
                                ),
                                leverage=int(pos.get("leverage", 1)),
                                ticket=f"{pos['symbol']}_{pos['side']}"
                            ))
            except Exception as e:
                logger.error(f"获取{exchange_name}持仓失败: {e}")

        return positions

    def _get_current_price(self, platform: str, symbol: str) -> float:
        """获取当前价格"""
        try:
            if platform == "MT5" and self.mt5_bridge:
                info = self.mt5_bridge.get_symbol_info(symbol)
                return (info["bid"] + info["ask"]) / 2 if info else 0
            elif platform in self.exchange_traders:
                # 使用数据提供者获取最新价格
                if hasattr(self.exchange_traders[platform], 'data_provider'):
                    positions = self.exchange_traders[platform].data_provider.get_positions()
                    for pos in positions:
                        if pos["symbol"] == symbol:
                            return pos["mark_price"]
            return 0
        except Exception as e:
            logger.error(f"获取价格失败 {platform} {symbol}: {e}")
            return 0

    def _calculate_pnl_pct(self, entry_price: float, current_price: float,
                          is_long: bool) -> float:
        """计算盈亏百分比"""
        if entry_price == 0:
            return 0

        if is_long:
            return ((current_price - entry_price) / entry_price) * 100
        else:
            return ((entry_price - current_price) / entry_price) * 100

    def _get_market_context(self, position: Position) -> MarketContext:
        """获取市场环境上下文"""
        symbol = position.symbol

        # 初始化默认值
        context = MarketContext(
            symbol=symbol,
            current_price=position.current_price,
            trend="sideways",
            volatility="medium",
            volume_ratio=1.0,
            support_levels=[],
            resistance_levels=[],
            rsi=50,
            macd_signal="neutral",
            news_sentiment="neutral",
            news_score=0
        )

        try:
            # 技术指标
            if self.indicator_system:
                indicators = self.indicator_system.get_signals(symbol)
                context.trend = indicators.get("trend", "sideways")
                context.volatility = indicators.get("volatility_level", "medium")
                context.rsi = indicators.get("rsi", 50)
                context.macd_signal = indicators.get("macd_signal", "neutral")
                context.support_levels = indicators.get("support_levels", [])
                context.resistance_levels = indicators.get("resistance_levels", [])

            # 新闻情绪
            if self.news_aggregator:
                news_data = self.news_aggregator.get_sentiment(symbol)
                context.news_sentiment = news_data.get("sentiment", "neutral")
                context.news_score = news_data.get("score", 0)

            # 订单簿数据
            if self.data_provider:
                orderbook = self.data_provider.get_order_book(symbol)
                if orderbook:
                    context.order_book_pressure = orderbook.get("buying_pressure", 50)

                # 资金费率(仅合约)
                if position.platform != "MT5":
                    funding = self.data_provider.get_funding_rate(symbol)
                    if funding:
                        context.funding_rate = funding.get("funding_rate", 0)

        except Exception as e:
            logger.error(f"获取市场上下文失败 {symbol}: {e}")

        return context

    def _make_decision(self, position: Position,
                      market_context: MarketContext) -> Decision:
        """
        综合决策引擎
        基于多维度分析生成持仓决策
        """
        reasons = []
        scores = {
            "close": 0,
            "hold": 0,
            "adjust": 0
        }

        # === 1. 风险管理分析 ===
        risk_score = self._analyze_risk(position, reasons)

        # === 2. 技术面分析 ===
        technical_score = self._analyze_technical(position, market_context, reasons)

        # === 3. 基本面分析 ===
        fundamental_score = self._analyze_fundamental(position, market_context, reasons)

        # === 4. 新闻情绪分析 ===
        news_score = self._analyze_news(position, market_context, reasons)

        # === 5. AI模型决策 ===
        ai_score = self._get_ai_decision(position, market_context, reasons)

        # 综合评分
        final_score = (
            risk_score * self.weights.get("risk", 0.2) +
            technical_score * self.weights.get("technical", 0.4) +
            fundamental_score * self.weights.get("fundamental", 0.2) +
            news_score * self.weights.get("news", 0.2)
        )

        # 生成决策
        return self._generate_final_decision(
            position, market_context, final_score, reasons, ai_score
        )

    def _analyze_risk(self, position: Position, reasons: List[str]) -> float:
        """风险分析"""
        score = 0

        # 止损检查
        if position.unrealized_pnl_pct <= -self.max_loss_per_position_pct:
            score -= 50
            reasons.append(
                f"⚠️ 亏损已达{position.unrealized_pnl_pct:.2f}% "
                f"(止损线{-self.max_loss_per_position_pct}%)"
            )
        elif position.unrealized_pnl_pct <= -self.max_loss_per_position_pct * 0.7:
            score -= 20
            reasons.append(
                f"⚠️ 亏损接近止损线 ({position.unrealized_pnl_pct:.2f}%)"
            )

        # 止盈检查
        if position.unrealized_pnl_pct >= self.target_profit_pct:
            score += 30
            reasons.append(
                f"✅ 盈利已达目标 {position.unrealized_pnl_pct:.2f}% "
                f"(目标{self.target_profit_pct}%)"
            )
        elif position.unrealized_pnl_pct >= self.partial_close_profit_pct:
            score += 10
            reasons.append(
                f"📊 盈利{position.unrealized_pnl_pct:.2f}%,可考虑部分止盈"
            )

        return score

    def _analyze_technical(self, position: Position,
                          context: MarketContext, reasons: List[str]) -> float:
        """技术面分析"""
        score = 0

        # 趋势分析
        if position.side == "long":
            if context.trend == "uptrend":
                score += 20
                reasons.append("📈 趋势与持仓方向一致(上涨)")
            elif context.trend == "downtrend":
                score -= 30
                reasons.append("📉 趋势转为下跌,与多头持仓相反")
        else:  # short
            if context.trend == "downtrend":
                score += 20
                reasons.append("📉 趋势与持仓方向一致(下跌)")
            elif context.trend == "uptrend":
                score -= 30
                reasons.append("📈 趋势转为上涨,与空头持仓相反")

        # RSI分析
        if context.rsi > 70:
            if position.side == "long":
                score -= 15
                reasons.append(f"⚠️ RSI超买 ({context.rsi:.1f}),多头风险增加")
            else:
                score += 10
        elif context.rsi < 30:
            if position.side == "short":
                score -= 15
                reasons.append(f"⚠️ RSI超卖 ({context.rsi:.1f}),空头风险增加")
            else:
                score += 10

        # MACD信号
        if context.macd_signal == "bullish" and position.side == "short":
            score -= 15
            reasons.append("⚠️ MACD看涨信号,与空头持仓相反")
        elif context.macd_signal == "bearish" and position.side == "long":
            score -= 15
            reasons.append("⚠️ MACD看跌信号,与多头持仓相反")

        # 支撑阻力
        if context.support_levels and context.resistance_levels:
            if position.side == "long":
                nearest_resistance = min([r for r in context.resistance_levels
                                        if r > position.current_price], default=None)
                if nearest_resistance:
                    distance_pct = ((nearest_resistance - position.current_price) /
                                  position.current_price * 100)
                    if distance_pct < 1:
                        score -= 10
                        reasons.append(f"⚠️ 接近阻力位 {nearest_resistance:.2f}")

        return score

    def _analyze_fundamental(self, position: Position,
                           context: MarketContext, reasons: List[str]) -> float:
        """基本面分析"""
        score = 0

        # 资金费率分析(仅合约)
        if context.funding_rate is not None:
            if abs(context.funding_rate) > 0.01:  # 1%
                if position.side == "long" and context.funding_rate > 0.01:
                    score -= 10
                    reasons.append(
                        f"⚠️ 资金费率偏高 ({context.funding_rate*100:.3f}%), "
                        "多头需支付费用"
                    )
                elif position.side == "short" and context.funding_rate < -0.01:
                    score -= 10
                    reasons.append(
                        f"⚠️ 资金费率偏低 ({context.funding_rate*100:.3f}%), "
                        "空头需支付费用"
                    )

        # 订单簿压力
        if context.order_book_pressure is not None:
            if position.side == "long" and context.order_book_pressure < 40:
                score -= 15
                reasons.append(
                    f"⚠️ 卖压较大 (买压{context.order_book_pressure:.1f}%)"
                )
            elif position.side == "short" and context.order_book_pressure > 60:
                score -= 15
                reasons.append(
                    f"⚠️ 买压较大 (买压{context.order_book_pressure:.1f}%)"
                )

        return score

    def _analyze_news(self, position: Position,
                     context: MarketContext, reasons: List[str]) -> float:
        """新闻情绪分析"""
        score = 0

        if context.news_score > 0.3:  # 正面新闻
            if position.side == "long":
                score += 15
                reasons.append("📰 新闻情绪正面,利好多头")
            else:
                score -= 10
                reasons.append("📰 新闻情绪正面,不利空头")
        elif context.news_score < -0.3:  # 负面新闻
            if position.side == "short":
                score += 15
                reasons.append("📰 新闻情绪负面,利好空头")
            else:
                score -= 10
                reasons.append("📰 新闻情绪负面,不利多头")

        return score

    def _get_ai_decision(self, position: Position,
                        context: MarketContext, reasons: List[str]) -> float:
        """获取AI模型决策"""
        if not self.ai_ensemble:
            return 0

        try:
            # 构建AI分析数据
            market_data = {
                "symbol": position.symbol,
                "price": position.current_price,
                "change_24h": position.unrealized_pnl_pct
            }

            indicators = {
                "trend": context.trend,
                "rsi": context.rsi,
                "macd": context.macd_signal,
                "volatility": context.volatility
            }

            news = [{"sentiment": context.news_sentiment}]

            # 获取AI决策
            ai_decision = self.ai_ensemble.get_ensemble_decision(
                market_data, indicators, news
            )

            action = ai_decision.get("action", "hold")
            confidence = ai_decision.get("confidence", 0)

            if action == "sell" and position.side == "long":
                reasons.append(
                    f"🤖 AI建议卖出 (置信度{confidence:.2f}): "
                    f"{ai_decision.get('reason', '')}"
                )
                return -30 * confidence
            elif action == "buy" and position.side == "short":
                reasons.append(
                    f"🤖 AI建议买入 (置信度{confidence:.2f}): "
                    f"{ai_decision.get('reason', '')}"
                )
                return -30 * confidence
            elif action == "hold":
                reasons.append(f"🤖 AI建议持有 (置信度{confidence:.2f})")
                return 10 * confidence

        except Exception as e:
            logger.error(f"AI决策失败: {e}")

        return 0

    def _generate_final_decision(self, position: Position,
                                context: MarketContext,
                                score: float, reasons: List[str],
                                ai_score: float) -> Decision:
        """生成最终决策"""

        # 决策阈值
        CLOSE_THRESHOLD = -30
        ADJUST_THRESHOLD = 20

        # 确定风险等级
        if abs(position.unrealized_pnl_pct) > 10 or context.volatility == "high":
            risk_level = "high"
        elif abs(position.unrealized_pnl_pct) > 5 or context.volatility == "medium":
            risk_level = "medium"
        else:
            risk_level = "low"

        # 紧急平仓条件
        if (position.unrealized_pnl_pct <= -self.max_loss_per_position_pct or
            score <= CLOSE_THRESHOLD * 1.5):
            return Decision(
                action="close",
                confidence=0.9,
                reason=reasons,
                risk_level="high",
                urgency="critical"
            )

        # 平仓条件
        if score <= CLOSE_THRESHOLD:
            return Decision(
                action="close",
                confidence=min(abs(score) / 50, 0.95),
                reason=reasons,
                risk_level=risk_level,
                urgency="high" if score < CLOSE_THRESHOLD * 1.2 else "normal"
            )

        # 部分止盈
        if position.unrealized_pnl_pct >= self.partial_close_profit_pct and score > 0:
            return Decision(
                action="partial_close",
                confidence=0.7,
                reason=reasons,
                risk_level="low",
                close_percentage=50,  # 平仓50%
                urgency="normal"
            )

        # 调整止盈止损
        if score >= ADJUST_THRESHOLD or position.unrealized_pnl_pct >= self.trailing_stop_trigger_pct:
            new_sl, new_tp = self._calculate_new_sl_tp(position, context)
            return Decision(
                action="adjust_sl",
                confidence=0.75,
                reason=reasons,
                risk_level=risk_level,
                suggested_sl=new_sl,
                suggested_tp=new_tp,
                urgency="normal"
            )

        # 默认持有
        return Decision(
            action="hold",
            confidence=0.8,
            reason=reasons if reasons else ["当前市场状况适合继续持有"],
            risk_level=risk_level,
            urgency="low"
        )

    def _calculate_new_sl_tp(self, position: Position,
                            context: MarketContext) -> Tuple[float, float]:
        """计算新的止损止盈价格"""
        current_price = position.current_price

        # 移动止损:保护已有利润
        if position.side == "long":
            # 多头:止损移动到成本价之上
            if position.unrealized_pnl_pct > self.trailing_stop_trigger_pct:
                profit_protection = position.unrealized_pnl_pct * 0.5  # 保护50%利润
                new_sl = position.entry_price * (1 + profit_protection / 100)
            else:
                new_sl = position.entry_price * (1 - self.max_loss_per_position_pct / 100)

            # 止盈:基于阻力位或固定百分比
            if context.resistance_levels:
                new_tp = min([r for r in context.resistance_levels if r > current_price],
                           default=current_price * (1 + self.target_profit_pct / 100))
            else:
                new_tp = current_price * (1 + self.target_profit_pct / 100)

        else:  # short
            # 空头:止损移动到成本价之下
            if position.unrealized_pnl_pct > self.trailing_stop_trigger_pct:
                profit_protection = position.unrealized_pnl_pct * 0.5
                new_sl = position.entry_price * (1 - profit_protection / 100)
            else:
                new_sl = position.entry_price * (1 + self.max_loss_per_position_pct / 100)

            # 止盈:基于支撑位或固定百分比
            if context.support_levels:
                new_tp = max([s for s in context.support_levels if s < current_price],
                           default=current_price * (1 - self.target_profit_pct / 100))
            else:
                new_tp = current_price * (1 - self.target_profit_pct / 100)

        return new_sl, new_tp

    def _execute_decision(self, position: Position, decision: Decision):
        """执行决策"""
        if not self.auto_execute:
            logger.info(f"自动执行已禁用,仅记录决策: {decision.action}")
            return

        try:
            logger.info(
                f"执行决策: {decision.action} for {position.symbol} "
                f"on {position.platform}"
            )

            # 这里需要调用实际的交易接口
            # 由于不同平台API不同,需要分别处理
            # TODO: 实现具体执行逻辑

        except Exception as e:
            logger.error(f"执行决策失败: {e}")

    def _log_decision(self, position: Position, decision: Decision,
                     context: MarketContext):
        """记录决策"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "position": asdict(position),
            "decision": asdict(decision),
            "market_context": asdict(context)
        }

        self.decisions_history.append(log_entry)

        # 持久化到文件
        log_file = self.config.get("decision_log_file",
                                   "logs/position_decisions.jsonl")
        try:
            os.makedirs(os.path.dirname(log_file), exist_ok=True)
            with open(log_file, "a") as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error(f"记录决策失败: {e}")

    def get_summary(self) -> Dict:
        """获取监控摘要"""
        return {
            "enabled": self.enabled,
            "is_running": self.is_running,
            "last_scan_time": self.last_scan_time.isoformat() if self.last_scan_time else None,
            "scan_interval": self.scan_interval,
            "auto_execute": self.auto_execute,
            "total_decisions": len(self.decisions_history),
            "recent_decisions": self.decisions_history[-10:] if self.decisions_history else []
        }
