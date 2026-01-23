# Enhanced Exchange Trader V2
# Integrates all 14 win rate improvement suggestions

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import hmac
import hashlib
import base64
import json
import time
import logging
from typing import Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass
import requests

# Import original modules
from position_management.dynamic_position_sizer import DynamicPositionSizer
from position_management.trailing_stop_engine import AdvancedTrailingStopEngine
from analysis.multi_timeframe_analyzer import MultiTimeframeAnalyzer
from analysis.market_state_filter import MarketStateDetector, StrategyFilter
from analysis.adaptive_parameter_system import AdaptiveParameterSystem
from strategies.funding_rate_arbitrage import FundingArbitrageStrategy
from risk_management.drawdown_controller import DrawdownController
from risk_management.correlation_manager import CorrelationRiskManager

# Import new modules
from entry.trend_alignment import TrendAlignmentChecker, TrendDirection
from entry.pullback_entry import PullbackEntryStrategy
from entry.rsi_pullback_entry import RSIPullbackEntry, TrendDirection as RSI_Trend
from entry.macd_divergence import MACDDivergenceDetector
from risk_management.dynamic_stop_loss import DynamicStopLossCalculator
from position_management.position_scaling import ScaleInStrategy
from filters.volatility_time_filter import VolatilityTimeFilter
from filters.choppy_market_detector import ChoppyMarketDetector
from exit.partial_take_profit import PartialTakeProfitStrategy
from entry.multi_indicator_confirm import MultiIndicatorConfirm
from position_management.volatility_adjustment import VolatilityAdjustment
from risk_management.loss_streak_manager import LossStreakManager, TradeRecord, TradeStatus

logger = logging.getLogger(__name__)


@dataclass
class TradeSignal:
    """Trading signal"""
    signal: str                  # buy/sell/hold
    confidence: float            # Confidence 0-1
    entry_price: Optional[float]
    stop_loss: Optional[float]
    take_profit: Optional[float]
    position_size: float
    reasons: List[str]
    warnings: List[str]
    filters_passed: List[str]
    filters_failed: List[str]


class EnhancedExchangeTraderV2:
    """Enhanced exchange trader V2 - Integrates all 14 win rate improvement suggestions"""

    def __init__(self, config: Dict):
        self.config = config
        self.exchange = config.get("exchange", "binance").lower()
        self.api_key = config.get("api_key", "")
        self.api_secret = config.get("api_secret", "")
        self.passphrase = config.get("passphrase", "")
        self.testnet = config.get("testnet", False)
        self.base_url = self._get_base_url()

        # Initialize all sub-modules
        self._init_all_modules()

        # Position tracking
        self.active_positions: Dict[str, Dict] = {}

        # Exit plan tracking
        self.exit_plans: Dict[str, object] = {}

        # Running state
        self.is_running = False

    def _init_all_modules(self):
        """Initialize all modules (8 original + 12 new = 20 total)"""
        # ========== Original modules (8) ==========
        logger.info("Initializing original modules...")

        # 1. Dynamic position sizer
        position_config = self.config.get("position_management", {})
        position_config["initial_balance"] = self.config.get("initial_balance", 10000)
        self.position_sizer = DynamicPositionSizer(position_config)
        logger.info("  [OK] Dynamic position sizer")

        # 2. Trailing stop engine
        trailing_config = self.config.get("trailing_stop", {})
        self.trailing_engine = AdvancedTrailingStopEngine(trailing_config)
        logger.info("  [OK] Trailing stop engine")

        # 3. Multi-timeframe analyzer
        mt_config = self.config.get("multi_timeframe", {})
        self.mtf_analyzer = MultiTimeframeAnalyzer(mt_config)
        logger.info("  [OK] Multi-timeframe analyzer")

        # 4. Market state filter
        ms_config = self.config.get("market_state_filter", {})
        self.market_state_detector = MarketStateDetector(ms_config)
        self.strategy_filter = StrategyFilter(ms_config)
        logger.info("  [OK] Market state filter")

        # 5. Adaptive parameter system
        ap_config = self.config.get("adaptive_parameters", {})
        base_params = self._get_base_parameters()
        ap_config["base_parameters"] = base_params
        self.adaptive_system = AdaptiveParameterSystem(ap_config)
        logger.info("  [OK] Adaptive parameter system")

        # 6. Funding rate arbitrage strategy
        fa_config = self.config.get("funding_arbitrage", {})
        self.funding_strategy = FundingArbitrageStrategy(fa_config)
        logger.info("  [OK] Funding rate arbitrage strategy")

        # 7. Drawdown controller
        dd_config = self.config.get("drawdown_control", {})
        dd_config["initial_equity"] = self.config.get("initial_balance", 10000)
        self.drawdown_controller = DrawdownController(dd_config)
        logger.info("  [OK] Drawdown controller")

        # 8. Correlation risk manager
        cr_config = self.config.get("correlation_risk", {})
        self.correlation_manager = CorrelationRiskManager(cr_config)
        logger.info("  [OK] Correlation risk manager")

        # ========== New modules (12) ==========
        logger.info("Initializing new modules...")

        # 9. Trend alignment checker (Suggestion 1)
        ta_config = self.config.get("trend_alignment", {})
        self.trend_alignment_checker = TrendAlignmentChecker(ta_config)
        logger.info("  [OK] Trend alignment checker")

        # 10. Pullback entry strategy (Suggestion 2)
        pb_config = self.config.get("pullback_entry", {})
        self.pullback_strategy = PullbackEntryStrategy(pb_config)
        logger.info("  [OK] Pullback entry strategy")

        # 11. RSI pullback entry strategy (Suggestion 3)
        rsi_config = self.config.get("rsi_pullback", {})
        self.rsi_pullback_entry = RSIPullbackEntry(rsi_config)
        logger.info("  [OK] RSI pullback entry strategy")

        # 12. MACD divergence detector (Suggestion 4)
        macd_config = self.config.get("macd_divergence", {})
        self.macd_divergence_detector = MACDDivergenceDetector(macd_config)
        logger.info("  [OK] MACD divergence detector")

        # 13. Dynamic stop loss calculator (Suggestion 5)
        dsl_config = self.config.get("dynamic_stop_loss", {})
        self.dynamic_stop_loss = DynamicStopLossCalculator(dsl_config)
        logger.info("  [OK] Dynamic stop loss calculator")

        # 14. Scale-in strategy (Suggestion 6)
        scale_config = self.config.get("scale_in", {})
        self.scale_in_strategy = ScaleInStrategy(scale_config)
        logger.info("  [OK] Scale-in strategy")

        # 15. Volatility time filter (Suggestion 8)
        vt_config = self.config.get("volatility_time_filter", {})
        self.volatility_time_filter = VolatilityTimeFilter(vt_config)
        logger.info("  [OK] Volatility time filter")

        # 16. Choppy market detector (Suggestion 9)
        cm_config = self.config.get("choppy_market", {})
        self.choppy_detector = ChoppyMarketDetector(cm_config)
        logger.info("  [OK] Choppy market detector")

        # 17. Partial take profit strategy (Suggestion 10, 11)
        tp_config = self.config.get("partial_take_profit", {})
        self.partial_tp_strategy = PartialTakeProfitStrategy(tp_config)
        logger.info("  [OK] Partial take profit strategy")

        # 18. Multi indicator confirm (Suggestion 13)
        mi_config = self.config.get("multi_indicator", {})
        self.multi_indicator_confirm = MultiIndicatorConfirm(mi_config)
        logger.info("  [OK] Multi indicator confirm")

        # 19. Volatility adjustment (Suggestion 14)
        va_config = self.config.get("volatility_adjustment", {})
        self.volatility_adjustment = VolatilityAdjustment(va_config)
        logger.info("  [OK] Volatility adjustment")

        # 20. Loss streak manager (Suggestion 15)
        ls_config = self.config.get("loss_streak", {})
        self.loss_streak_manager = LossStreakManager(ls_config)
        logger.info("  [OK] Loss streak manager")

        logger.info(f"Total: 8 original + 12 new = 20 modules initialized")

    def _get_base_url(self) -> str:
        """Get API base URL"""
        if self.exchange == "binance":
            if self.testnet:
                return "https://testnet.binance.vision"
            return "https://api.binance.com"
        elif self.exchange == "binance_futures":
            if self.testnet:
                return "https://testnet.binancefuture.com"
            return "https://fapi.binance.com"
        elif self.exchange == "okx":
            if self.testnet:
                return "https://www.okx.com"
            return "https://www.okx.com"
        elif self.exchange == "bybit":
            if self.testnet:
                return "https://api-testnet.bybit.com"
            return "https://api.bybit.com"
        elif self.exchange == "huobi":
            if self.testnet:
                return "https://api.huobi.pro"
            return "https://api.huobi.pro"
        else:
            raise ValueError(f"Unsupported exchange: {self.exchange}")

    def _get_base_parameters(self) -> Dict:
        """Get base parameters"""
        rm_config = self.config.get("risk_management", {})
        return {
            "risk_per_trade": rm_config.get("base_risk_per_trade", 0.02),
            "stop_loss_pct": rm_config.get("stop_loss_pct", 0.02),
            "take_profit_pct": rm_config.get("take_profit_pct", 0.04),
            "atr_multiplier": rm_config.get("atr_multiplier", 2.0),
            "trailing_stop_activation": rm_config.get("trailing_stop_activation", 0.02),
            "trailing_stop_distance": rm_config.get("trailing_stop_distance", 0.01)
        }

    def generate_comprehensive_signal(self, symbol: str) -> TradeSignal:
        """
        Generate comprehensive trading signal with all filters applied

        Args:
            symbol: Trading symbol

        Returns:
            TradeSignal
        """
        # Prepare market data
        klines_data = self.get_multi_timeframe_klines(symbol)

        if not klines_data or len(klines_data.get("1h", [])) < 50:
            return TradeSignal(
                signal="hold",
                confidence=0.0,
                entry_price=None,
                stop_loss=None,
                take_profit=None,
                position_size=0.0,
                reasons=["Insufficient data"],
                warnings=["Cannot get enough market data"],
                filters_passed=[],
                filters_failed=["market_data"]
            )

        # Extract data
        closes_1h = [k["close"] for k in klines_data.get("1h", [])]
        highs_1h = [k["high"] for k in klines_data.get("1h", [])]
        lows_1h = [k["low"] for k in klines_data.get("1h", [])]

        current_price = closes_1h[-1]

        # Initialize signal
        filters_passed = []
        filters_failed = []
        warnings = []
        reasons = []

        # ========== Filter checks ==========

        # 1. Volatility time filter (Suggestion 8)
        should_trade_time, time_reason = self.volatility_time_filter.should_trade()
        if should_trade_time:
            filters_passed.append(f"Time: {time_reason}")
        else:
            filters_failed.append(f"Time: {time_reason}")
            warnings.append(time_reason)

        # 2. Choppy market detection (Suggestion 9)
        market_result = self.choppy_detector.analyze_multi_timeframe(klines_data)
        if market_result["tradeable"]:
            filters_passed.append(f"Market: {market_result['reason']}")
        else:
            filters_failed.append(f"Market: {market_result['reason']}")
            warnings.append(market_result['reason'])

        # 3. Loss streak check (Suggestion 15)
        should_trade_loss, loss_reason = self.loss_streak_manager.should_trade()
        if should_trade_loss:
            filters_passed.append(f"Loss control: {loss_reason}")
        else:
            filters_failed.append(f"Loss control: {loss_reason}")
            warnings.append(loss_reason)

        # 4. Drawdown control check
        dd_action = self.drawdown_controller.check_action()
        if dd_action and dd_action.stop_trading:
            filters_failed.append(f"Drawdown: {dd_action.reason}")
            warnings.append(dd_action.reason)

        # If critical filter failed, return immediately
        critical_failures = ["Time", "Market", "Loss control", "Drawdown"]
        has_critical_failure = any(
            any(f.startswith(c) for f in filters_failed)
            for c in critical_failures
        )

        if has_critical_failure:
            return TradeSignal(
                signal="hold",
                confidence=0.0,
                entry_price=current_price,
                stop_loss=None,
                take_profit=None,
                position_size=0.0,
                reasons=reasons,
                warnings=warnings,
                filters_passed=filters_passed,
                filters_failed=filters_failed
            )

        # ========== Signal analysis ==========

        # 5. Multi-timeframe analysis
        mtf_result = self.mtf_analyzer.analyze(symbol, klines_data)

        # 6. Trend alignment check (Suggestion 1)
        timeframe_trends = {
            "1d": self._convert_mtf_trend(mtf_result.timeframe_signals.get("1d")),
            "4h": self._convert_mtf_trend(mtf_result.timeframe_signals.get("4h")),
            "1h": self._convert_mtf_trend(mtf_result.timeframe_signals.get("1h"))
        }
        trend_check = self.trend_alignment_checker.check_alignment(timeframe_trends)

        if trend_check["aligned"]:
            filters_passed.append(f"Trend alignment: {trend_check['recommendation']}")
        else:
            filters_failed.append(f"Trend alignment: {trend_check['recommendation']}")
            warnings.append(trend_check["recommendation"])

        # Determine signal direction
        signal_direction = mtf_result.composite_signal
        if signal_direction == "hold":
            reasons.append("No clear signal from multi-timeframe")
            return TradeSignal(
                signal="hold",
                confidence=mtf_result.composite_confidence,
                entry_price=current_price,
                stop_loss=None,
                take_profit=None,
                position_size=0.0,
                reasons=reasons,
                warnings=warnings,
                filters_passed=filters_passed,
                filters_failed=filters_failed
            )

        # 7. Multi indicator confirm (Suggestion 13)
        should_trade_indicator, indicator_reason, indicator_confidence = \
            self.multi_indicator_confirm.should_trade(
                closes_1h, highs_1h, lows_1h, current_price, signal_direction
            )

        if should_trade_indicator:
            filters_passed.append(f"Multi indicator: {indicator_reason}")
        else:
            filters_failed.append(f"Multi indicator: {indicator_reason}")
            warnings.append(indicator_reason)

        # 8. RSI pullback check (Suggestion 3)
        rsi_trend = RSI_Trend.UPTREND if signal_direction == "buy" else RSI_Trend.DOWNTREND
        rsi_signal = self.rsi_pullback_entry.analyze(
            closes_1h, rsi_trend, current_price
        )

        if rsi_signal.signal == signal_direction:
            filters_passed.append(f"RSI: {rsi_signal.reason}")
        else:
            filters_failed.append(f"RSI: {rsi_signal.reason}")

        # 9. MACD divergence check (Suggestion 4)
        macd_divergence = self.macd_divergence_detector.detect_divergence(
            closes_1h, highs_1h, lows_1h
        )

        if macd_divergence.signal == "hold":
            # No divergence, continue
            pass
        elif macd_divergence.signal == signal_direction:
            filters_passed.append(f"MACD divergence: {macd_divergence.reason}")
        else:
            # Divergence direction conflict
            filters_failed.append(f"MACD divergence: {macd_divergence.reason}")
            warnings.append(macd_divergence.reason)

        # 10. Market state strategy filter
        market_state = self.market_state_detector.detect_market_state(closes_1h)
        allowed_strategies = self.strategy_filter.get_allowed_strategies(market_state)

        current_strategy = "trend_follow" if signal_direction == "buy" else "trend_follow"
        if current_strategy in allowed_strategies:
            filters_passed.append(f"Market strategy: {market_state.value} allows {current_strategy}")
        else:
            filters_failed.append(f"Market strategy: {market_state.value} forbids {current_strategy}")

        # Calculate comprehensive confidence
        total_filters = len(filters_passed) + len(filters_failed)
        pass_rate = len(filters_passed) / total_filters if total_filters > 0 else 0

        base_confidence = mtf_result.composite_confidence
        confidence = base_confidence * pass_rate

        # If important filter failed, reduce confidence
        if len(filters_failed) > 2:
            confidence *= 0.5

        if len(filters_failed) >= len(filters_passed):
            # Failed filters more than passed filters, don't trade
            return TradeSignal(
                signal="hold",
                confidence=confidence,
                entry_price=current_price,
                stop_loss=None,
                take_profit=None,
                position_size=0.0,
                reasons=reasons,
                warnings=warnings,
                filters_passed=filters_passed,
                filters_failed=filters_failed
            )

        # ========== Stop loss / Take profit calculation ==========

        # 11. Dynamic stop loss (Suggestion 5)
        sl_result = self.dynamic_stop_loss.calculate_stop_loss(
            current_price, signal_direction,
            highs_1h, lows_1h, closes_1h,
            support_levels=mtf_result.support_levels,
            resistance_levels=mtf_result.resistance_levels
        )
        stop_loss = sl_result.price

        # 12. Volatility adjustment (Suggestion 14)
        volatility_summary = self.volatility_adjustment.get_volatility_summary(
            highs_1h, lows_1h, closes_1h
        )

        # 13. Base position size calculation
        base_size = self.position_sizer.calculate_position_size(
            symbol, signal_direction, current_price, stop_loss
        )

        # 14. Apply volatility adjustment
        adjusted_size = self.volatility_adjustment.get_adjusted_position_size(
            base_size, highs_1h, lows_1h, closes_1h
        )

        # 15. Loss streak adjustment
        final_size = self.loss_streak_manager.get_adjusted_position_size(adjusted_size)

        # Take profit calculation
        rm_config = self.config.get("risk_management", {})
        risk_reward_ratio = rm_config.get("risk_reward_ratio", 2.0)

        if signal_direction == "buy":
            take_profit = current_price * (1 + abs(current_price - stop_loss) / current_price * risk_reward_ratio)
        else:
            take_profit = current_price * (1 - abs(current_price - stop_loss) / current_price * risk_reward_ratio)

        # Summarize reasons
        reasons.append(f"Signal: {signal_direction}")
        reasons.append(f"Confidence: {confidence:.1%}")
        reasons.append(f"Stop loss: {stop_loss:.2f} ({sl_result.reason})")
        reasons.append(f"Volatility: {volatility_summary['volatility_level']}")
        reasons.append(f"Adjustment factor: {volatility_summary['recommended_multiplier']:.2f}")

        return TradeSignal(
            signal=signal_direction,
            confidence=confidence,
            entry_price=current_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            position_size=final_size,
            reasons=reasons,
            warnings=warnings,
            filters_passed=filters_passed,
            filters_failed=filters_failed
        )

    def _convert_mtf_trend(self, timeframe_signal) -> Optional[TrendDirection]:
        """Convert multi-timeframe trend direction"""
        if timeframe_signal is None:
            return None

        trend_map = {
            "strong_uptrend": TrendDirection.UPTREND,
            "uptrend": TrendDirection.UPTREND,
            "weak_uptrend": TrendDirection.UPTREND,
            "neutral": TrendDirection.NEUTRAL,
            "weak_downtrend": TrendDirection.DOWNTREND,
            "downtrend": TrendDirection.DOWNTREND,
            "strong_downtrend": TrendDirection.DOWNTREND
        }
        return trend_map.get(timeframe_signal.trend.value)

    def execute_with_all_filters(self, symbol: str) -> Dict:
        """
        Execute trade with all filters

        Args:
            symbol: Trading symbol

        Returns:
            Execution result
        """
        # Generate comprehensive signal
        signal = self.generate_comprehensive_signal(symbol)

        if signal.signal == "hold":
            return {
                "success": False,
                "action": "hold",
                "reason": signal.filters_failed[0] if signal.filters_failed else "Did not pass filters",
                "signal": signal
            }

        # Check correlation risk
        account_balance = self.get_balance()
        can_open, corr_reason, _ = self.correlation_manager.can_open_position(
            symbol, signal.signal, signal.position_size,
            signal.entry_price, account_balance
        )

        if not can_open:
            return {
                "success": False,
                "action": "blocked",
                "reason": f"Correlation risk: {corr_reason}",
                "signal": signal
            }

        # Execute trade
        result = self.execute_trade(
            symbol, signal.signal, signal.position_size,
            signal.entry_price, "LIMIT"
        )

        # If trade successful, create exit plan
        if result.get("success"):
            self._create_exit_plan(symbol, signal)

        return {
            "success": result.get("success", False),
            "action": "trade",
            "result": result,
            "signal": signal
        }

    def _create_exit_plan(self, symbol: str, signal: TradeSignal):
        """Create exit plan"""
        if symbol in self.exit_plans:
            return  # Already exists

        exit_plan = self.partial_tp_strategy.create_exit_plan(
            symbol=symbol,
            direction=signal.signal,
            entry_price=signal.entry_price,
            stop_loss=signal.stop_loss
        )

        self.exit_plans[symbol] = exit_plan
        logger.info(f"Created exit plan for {symbol}")

    def update_positions(self):
        """Update positions and check take profit / stop loss"""
        positions = self.get_positions()

        for pos in positions:
            symbol = pos["symbol"]
            current_price = self.get_price(symbol).get("price", 0)

            if symbol in self.exit_plans:
                # Update exit plan
                exit_plan = self.exit_plans[symbol]
                exit_result = self.partial_tp_strategy.update_price(exit_plan, current_price)

                if exit_result["action"] in ["take_profit", "stop_loss"]:
                    # Need to close position
                    close_pct = exit_result["close_pct"]
                    if close_pct > 0:
                        total_size = pos["amount"]
                        close_size = total_size * close_pct

                        side = "sell" if pos["side"] == "long" else "buy"

                        logger.info(f"Executing TP/SL for {symbol} close {close_pct:.0%}")

                        # Record trade result
                        pnl_pct = (current_price - exit_plan.entry_price) / exit_plan.entry_price
                        if exit_plan.direction == "sell":
                            pnl_pct = -pnl_pct

                        status = TradeStatus.WIN if pnl_pct > 0 else TradeStatus.LOSS
                        if abs(pnl_pct) < 0.001:
                            status = TradeStatus.BREAKEVEN

                        trade_record = TradeRecord(
                            symbol=symbol,
                            entry_price=exit_plan.entry_price,
                            exit_price=current_price,
                            side=exit_plan.direction,
                            size=close_size,
                            pnl=close_size * (current_price - exit_plan.entry_price),
                            pnl_pct=pnl_pct,
                            status=status,
                            timestamp=datetime.now()
                        )

                        self.loss_streak_manager.add_trade(trade_record)

                        if exit_result["action"] == "stop_loss":
                            self.partial_tp_strategy.close_plan(exit_plan, "stopped_out")

    def get_multi_timeframe_klines(self, symbol: str) -> Dict[str, List[Dict]]:
        """Get multi-timeframe klines data"""
        timeframes = ["1d", "4h", "1h", "15m", "5m"]
        klines_data = {}

        for tf in timeframes:
            limit = 200 if tf in ["1d", "4h"] else 500
            klines_data[tf] = self.get_klines(symbol, tf, limit)

        return klines_data

    def _make_request(self, method: str, endpoint: str,
                     params: Optional[Dict] = None,
                     signed: bool = False) -> Dict:
        """Send API request"""
        if params is None:
            params = {}

        url = self.base_url + endpoint
        headers = {"Content-Type": "application/json"}

        if signed:
            timestamp = int(time.time() * 1000)
            params["timestamp"] = timestamp

            if self.exchange in ["binance", "binance_futures"]:
                signature = self._binance_sign(params)
                if method == "GET":
                    url += "?" + "&".join([f"{k}={v}" for k, v in params.items()])
                    url += f"&signature={signature}"
                else:
                    params["signature"] = signature
            elif self.exchange == "okx":
                sign = self._okx_sign(method, endpoint, params)
                headers["OK-ACCESS-KEY"] = self.api_key
                headers["OK-ACCESS-SIGN"] = sign
                headers["OK-ACCESS-TIMESTAMP"] = str(timestamp)
                headers["OK-ACCESS-PASSPHRASE"] = self.passphrase

        try:
            if method == "GET":
                response = requests.get(url, headers=headers, timeout=10)
            else:
                response = requests.post(url, headers=headers, json=params, timeout=10)

            return response.json()
        except Exception as e:
            logger.error(f"Request failed: {e}")
            return {"error": str(e)}

    def _binance_sign(self, params: Dict) -> str:
        """Binance signature"""
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature

    def _okx_sign(self, method: str, endpoint: str, params: Dict) -> str:
        """OKX signature"""
        timestamp = str(time.time())
        if method == "GET":
            body = ""
        else:
            body = json.dumps(params)

        message = timestamp + method + endpoint + body
        mac = hmac.new(
            self.api_secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).digest()
        signature = base64.b64encode(mac).decode()

        return signature

    def get_status(self) -> Dict:
        """Get account status"""
        if self.exchange == "binance" or self.exchange == "binance_futures":
            return self._binance_status()
        elif self.exchange == "okx":
            return self._okx_status()
        else:
            return {"connected": False, "error": "Unsupported exchange"}

    def _binance_status(self) -> Dict:
        """Binance status"""
        account = self._make_request("GET", "/fapi/v2/account", signed=True)
        if "error" in account:
            return {"connected": False, "error": account.get("msg", "Connection failed")}

        balance = float(account.get("totalWalletBalance", 0))
        return {
            "connected": True,
            "account": self.api_key[:8] + "...",
            "balance": balance,
            "equity": balance
        }

    def _okx_status(self) -> Dict:
        """OKX status"""
        balance = self._make_request("GET", "/api/v5/account/balance", signed=True)
        if "error" in balance:
            return {"connected": False, "error": "Connection failed"}

        total_balance = 0
        if "data" in balance and balance["data"]:
            for bal in balance["data"][0].get("details", []):
                if bal.get("ccy") == "USDT":
                    total_balance += float(bal.get("bal", 0))

        return {
            "connected": True,
            "account": self.api_key[:8] + "...",
            "balance": total_balance
        }

    def get_balance(self) -> float:
        """Get balance"""
        status = self.get_status()
        return status.get("balance", 0)

    def get_positions(self, symbol: Optional[str] = None) -> List[Dict]:
        """Get positions"""
        if self.exchange == "binance_futures":
            return self._binance_positions(symbol)
        elif self.exchange == "okx":
            return self._okx_positions(symbol)
        else:
            return []

    def _binance_positions(self, symbol: Optional[str] = None) -> List[Dict]:
        """Binance positions"""
        positions = self._make_request("GET", "/fapi/v2/positionRisk", signed=True)
        if "error" in positions:
            return []

        result = []
        for pos in positions:
            if symbol and pos["symbol"] != symbol:
                continue
            if float(pos["positionAmt"]) != 0:
                result.append({
                    "symbol": pos["symbol"],
                    "side": "long" if float(pos["positionAmt"]) > 0 else "short",
                    "amount": abs(float(pos["positionAmt"])),
                    "price": float(pos["entryPrice"]),
                    "pnl": float(pos["unRealizedProfit"])
                })
        return result

    def _okx_positions(self, symbol: Optional[str] = None) -> List[Dict]:
        """OKX positions"""
        positions = self._make_request("GET", "/api/v5/account/positions", signed=True)
        if "error" in positions:
            return []

        result = []
        if "data" in positions:
            for pos in positions["data"]:
                if symbol and pos["instId"] != symbol:
                    continue
                if float(pos["pos"]) != 0:
                    result.append({
                        "symbol": pos["instId"],
                        "side": "long" if pos["posSide"] == "long" else "short",
                        "amount": abs(float(pos["pos"])),
                        "price": float(pos["avgPx"]),
                        "pnl": float(pos["upl"])
                    })
        return result

    def execute_trade(self, symbol: str, side: str, amount: float,
                     price: Optional[float] = None,
                     order_type: str = "MARKET") -> Dict:
        """Execute trade"""
        if self.exchange == "binance" or self.exchange == "binance_futures":
            return self._binance_trade(symbol, side, amount, price, order_type)
        elif self.exchange == "okx":
            return self._okx_trade(symbol, side, amount, price, order_type)
        else:
            return {"success": False, "message": "Unsupported exchange"}

    def _binance_trade(self, symbol: str, side: str, amount: float,
                      price: Optional[float], order_type: str) -> Dict:
        """Binance trade"""
        endpoint = "/fapi/v1/order"
        params = {
            "symbol": symbol,
            "side": "BUY" if side.lower() in ["buy", "long"] else "SELL",
            "type": order_type,
            "quantity": str(amount),
        }

        if order_type == "LIMIT" and price:
            params["price"] = str(price)
            params["timeInForce"] = "GTC"

        result = self._make_request("POST", endpoint, params, signed=True)

        if "orderId" in result:
            return {
                "success": True,
                "message": "Order successful",
                "order_id": result["orderId"],
                "symbol": symbol
            }
        else:
            return {"success": False, "message": result.get("msg", "Order failed")}

    def _okx_trade(self, symbol: str, side: str, amount: float,
                   price: Optional[float], order_type: str) -> Dict:
        """OKX trade"""
        endpoint = "/api/v5/trade/order"
        params = {
            "instId": symbol,
            "tdMode": "cross",
            "side": "buy" if side.lower() in ["buy", "long"] else "sell",
            "ordType": "market" if order_type == "MARKET" else "limit",
            "sz": str(amount)
        }

        if order_type == "LIMIT" and price:
            params["px"] = str(price)

        result = self._make_request("POST", endpoint, params, signed=True)

        if "data" in result and result["data"]:
            return {
                "success": True,
                "message": "Order successful",
                "order_id": result["data"][0]["ordId"],
                "symbol": symbol
            }
        else:
            return {"success": False, "message": "Order failed"}

    def get_price(self, symbol: str) -> Dict:
        """Get current price"""
        if self.exchange == "binance" or self.exchange == "binance_futures":
            url = f"{self.base_url}/fapi/v1/ticker/price?symbol={symbol}"
        elif self.exchange == "okx":
            url = f"{self.base_url}/api/v5/market/ticker?instId={symbol}"
        else:
            return {"error": "Unsupported exchange"}

        try:
            response = requests.get(url, timeout=10)
            data = response.json()

            if self.exchange == "okx" and "data" in data:
                return {"symbol": symbol, "price": float(data["data"][0]["last"])}
            else:
                return {"symbol": symbol, "price": float(data["price"])}
        except Exception as e:
            return {"error": str(e)}

    def get_klines(self, symbol: str, interval: str = "1h",
                 limit: int = 100) -> List[Dict]:
        """Get klines data"""
        if self.exchange == "binance" or self.exchange == "binance_futures":
            url = f"{self.base_url}/fapi/v1/klines?symbol={symbol}&interval={interval}&limit={limit}"
        elif self.exchange == "okx":
            okx_interval = self._convert_interval_okx(interval)
            url = f"{self.base_url}/api/v5/market/candles?instId={symbol}&bar={okx_interval}&limit={limit}"
        else:
            return []

        try:
            response = requests.get(url, timeout=10)
            data = response.json()

            result = []
            if self.exchange == "okx" and "data" in data:
                for k in data["data"]:
                    result.append({
                        "time": k[0],
                        "open": float(k[1]),
                        "high": float(k[2]),
                        "low": float(k[3]),
                        "close": float(k[4]),
                        "volume": float(k[5])
                    })
            else:
                for k in data:
                    result.append({
                        "time": k[0],
                        "open": float(k[1]),
                        "high": float(k[2]),
                        "low": float(k[3]),
                        "close": float(k[4]),
                        "volume": float(k[5])
                    })
            return result
        except Exception as e:
            logger.error(f"Get klines failed: {e}")
            return []

    def _convert_interval_okx(self, interval: str) -> str:
        """Convert klines interval to OKX format"""
        mapping = {
            "1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
            "1h": "1H", "2h": "2H", "4h": "4H", "6h": "6H", "12h": "12H",
            "1d": "1D", "1w": "1W", "1M": "1M"
        }
        return mapping.get(interval, "1H")


def create_enhanced_trader_v2(config: Dict) -> "EnhancedExchangeTraderV2":
    """Create enhanced trader V2"""
    return EnhancedExchangeTraderV2(config)


if __name__ == "__main__":
    # Test code
    config = {
        "exchange": "binance_futures",
        "testnet": True,
        "api_key": "",
        "api_secret": "",
        "initial_balance": 10000,
        "symbols": ["BTCUSDT", "ETHUSDT"]
    }

    trader = create_enhanced_trader_v2(config)

    print("\n=== Enhanced Exchange Trader V2 Initialized ===")
    print("Total modules: 20 (8 original + 12 new)")
