# 增强交易所交易模块
# 整合动态仓位管理、多时间框架分析、市场状态过滤、参数自适应等所有新功能

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import hmac
import hashlib
import base64
import json
import time
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import requests

# 导入新模块
from position_management.dynamic_position_sizer import (
    DynamicPositionSizer, PositionSizeResult, VolatilityAnalyzer
)
from position_management.trailing_stop_engine import AdvancedTrailingStopEngine
from analysis.multi_timeframe_analyzer import MultiTimeframeAnalyzer, MultiTimeframeResult
from analysis.market_state_filter import MarketStateDetector, StrategyFilter
from analysis.adaptive_parameter_system import AdaptiveParameterSystem
from strategies.funding_rate_arbitrage import FundingArbitrageStrategy
from risk_management.drawdown_controller import DrawdownController
from risk_management.correlation_manager import CorrelationRiskManager

logger = logging.getLogger(__name__)


class EnhancedExchangeTrader:
    """增强交易所交易类 - 整合所有高级功能"""

    def __init__(self, config: Dict):
        self.config = config
        self.exchange = config.get("exchange", "binance").lower()
        self.api_key = config.get("api_key", "")
        self.api_secret = config.get("api_secret", "")
        self.passphrase = config.get("passphrase", "")
        self.testnet = config.get("testnet", False)
        self.base_url = self._get_base_url()

        # 初始化各子模块
        self._init_submodules()

        # 持仓跟踪
        self.active_positions: Dict[str, Dict] = {}  # {symbol: {side, size, entry_price, sl, tp}}

        # 运行状态
        self.is_running = False

    def _init_submodules(self):
        """初始化所有子模块"""
        # 1. 动态仓位管理器
        position_config = self.config.get("position_management", {})
        position_config["initial_balance"] = self.config.get("initial_balance", 10000)
        self.position_sizer = DynamicPositionSizer(position_config)
        logger.info("动态仓位管理器已初始化")

        # 2. 移动止损引擎
        trailing_config = self.config.get("trailing_stop", {})
        self.trailing_engine = AdvancedTrailingStopEngine(trailing_config)
        logger.info("移动止损引擎已初始化")

        # 3. 多时间框架分析器
        mt_config = self.config.get("multi_timeframe", {})
        self.mtf_analyzer = MultiTimeframeAnalyzer(mt_config)
        logger.info("多时间框架分析器已初始化")

        # 4. 市场状态过滤器
        ms_config = self.config.get("market_state_filter", {})
        self.market_state_detector = MarketStateDetector(ms_config)
        self.strategy_filter = StrategyFilter(ms_config)
        logger.info("市场状态过滤器已初始化")

        # 5. 参数自适应系统
        ap_config = self.config.get("adaptive_parameters", {})
        base_params = self._get_base_parameters()
        ap_config["base_parameters"] = base_params
        self.adaptive_system = AdaptiveParameterSystem(ap_config)
        logger.info("参数自适应系统已初始化")

        # 6. 资金费率套利策略
        fa_config = self.config.get("funding_arbitrage", {})
        self.funding_strategy = FundingArbitrageStrategy(fa_config)
        logger.info("资金费率套利策略已初始化")

        # 7. 回撤控制器
        dd_config = self.config.get("drawdown_control", {})
        dd_config["initial_equity"] = self.config.get("initial_balance", 10000)
        self.drawdown_controller = DrawdownController(dd_config)
        logger.info("回撤控制器已初始化")

        # 8. 相关性风险管理器
        cr_config = self.config.get("correlation_risk", {})
        self.correlation_manager = CorrelationRiskManager(cr_config)
        logger.info("相关性风险管理器已初始化")

    def _get_base_url(self) -> str:
        """获取API基础URL"""
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
            raise ValueError(f"不支持的交易所: {self.exchange}")

    def _get_base_parameters(self) -> Dict:
        """获取基础参数"""
        rm_config = self.config.get("risk_management", {})
        return {
            "risk_per_trade": rm_config.get("base_risk_per_trade", 0.02),
            "stop_loss_pct": rm_config.get("stop_loss_pct", 0.02),
            "take_profit_pct": rm_config.get("take_profit_pct", 0.04),
            "atr_multiplier": rm_config.get("atr_multiplier", 2.0),
            "trailing_stop_activation": rm_config.get("trailing_stop_activation", 0.02),
            "trailing_stop_distance": rm_config.get("trailing_stop_distance", 0.01)
        }

    def _make_request(self, method: str, endpoint: str,
                     params: Optional[Dict] = None,
                     signed: bool = False) -> Dict:
        """发送API请求"""
        if params is None:
            params = {}

        url = self.base_url + endpoint
        headers = {"Content-Type": "application/json"}

        if signed:
            timestamp = int(time.time() * 1000)
            params["timestamp"] = timestamp

            if self.exchange == "binance" or self.exchange == "binance_futures":
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
            elif self.exchange == "bybit":
                sign = self._bybit_sign(params)
                headers["X-API-KEY"] = self.api_key
                headers["X-API-SIGN"] = sign

        try:
            if method == "GET":
                response = requests.get(url, headers=headers, timeout=10)
            else:
                response = requests.post(url, headers=headers, json=params, timeout=10)

            return response.json()
        except Exception as e:
            logger.error(f"请求失败: {e}")
            return {"error": str(e)}

    def _binance_sign(self, params: Dict) -> str:
        """Binance签名"""
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature

    def _okx_sign(self, method: str, endpoint: str, params: Dict) -> str:
        """OKX签名"""
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

    def _bybit_sign(self, params: Dict) -> str:
        """Bybit签名"""
        timestamp = str(int(time.time() * 1000))
        params["api_key"] = self.api_key
        params["timestamp"] = timestamp
        param_str = "&".join([f"{k}={v}" for k, v in sorted(params.items())])

        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            param_str.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        return signature

    # ============ 账户相关方法 ============

    def get_status(self) -> Dict:
        """获取账户状态"""
        if self.exchange == "binance" or self.exchange == "binance_futures":
            return self._binance_status()
        elif self.exchange == "okx":
            return self._okx_status()
        elif self.exchange == "bybit":
            return self._bybit_status()
        else:
            return {"connected": False, "error": "不支持的交易所"}

    def _binance_status(self) -> Dict:
        """Binance状态"""
        account = self._make_request("GET", "/fapi/v2/account", signed=True)
        if "error" in account:
            return {"connected": False, "error": account.get("msg", "连接失败")}

        balance = float(account.get("totalWalletBalance", 0))

        # 更新回撤控制器
        self.drawdown_controller.update_equity(balance)

        return {
            "connected": True,
            "account": self.api_key[:8] + "...",
            "balance": balance,
            "equity": balance
        }

    def _okx_status(self) -> Dict:
        """OKX状态"""
        balance = self._make_request("GET", "/api/v5/account/balance", signed=True)
        if "error" in balance:
            return {"connected": False, "error": "连接失败"}

        total_balance = 0
        if "data" in balance and balance["data"]:
            for bal in balance["data"][0].get("details", []):
                if bal.get("ccy") == "USDT":
                    total_balance += float(bal.get("bal", 0))

        # 更新回撤控制器
        self.drawdown_controller.update_equity(total_balance)

        # 更新仓位管理器
        self.position_sizer.update_account_balance(total_balance)

        return {
            "connected": True,
            "account": self.api_key[:8] + "...",
            "balance": total_balance
        }

    def _bybit_status(self) -> Dict:
        """Bybit状态"""
        wallet = self._make_request("GET", "/v2/private/wallet/balance", signed=True)
        if "error" in wallet:
            return {"connected": False, "error": "连接失败"}

        balance = 0
        if "result" in wallet:
            for item in wallet["result"].get("USDT", {}):
                balance += float(item.get("wallet_balance", 0))

        # 更新回撤控制器
        self.drawdown_controller.update_equity(balance)

        # 更新仓位管理器
        self.position_sizer.update_account_balance(balance)

        return {
            "connected": True,
            "account": self.api_key[:8] + "...",
            "balance": balance
        }

    def get_balance(self) -> float:
        """获取余额"""
        status = self.get_status()
        return status.get("balance", 0)

    # ============ 持仓相关方法 ============

    def get_positions(self, symbol: Optional[str] = None) -> List[Dict]:
        """获取持仓"""
        if self.exchange == "binance_futures":
            return self._binance_positions(symbol)
        elif self.exchange == "okx":
            return self._okx_positions(symbol)
        elif self.exchange == "bybit":
            return self._bybit_positions(symbol)
        else:
            return []

    def _binance_positions(self, symbol: Optional[str] = None) -> List[Dict]:
        """Binance持仓"""
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
        """OKX持仓"""
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

    def _bybit_positions(self, symbol: Optional[str] = None) -> List[Dict]:
        """Bybit持仓"""
        positions = self._make_request("GET", "/v2/private/position/list", signed=True)
        if "error" in positions:
            return []

        result = []
        if "result" in positions:
            for pos in positions["result"]:
                if symbol and pos["symbol"] != symbol:
                    continue
                if float(pos["size"]) != 0:
                    result.append({
                        "symbol": pos["symbol"],
                        "side": "long" if pos["side"] == "Buy" else "short",
                        "amount": float(pos["size"]),
                        "price": float(pos["entry_price"]),
                        "pnl": float(pos["unrealised_pnl"])
                    })
        return result

    # ============ 市场数据方法 ============

    def get_price(self, symbol: str) -> Dict:
        """获取当前价格"""
        if self.exchange == "binance" or self.exchange == "binance_futures":
            url = f"{self.base_url}/fapi/v1/ticker/price?symbol={symbol}"
        elif self.exchange == "okx":
            url = f"{self.base_url}/api/v5/market/ticker?instId={symbol}"
        elif self.exchange == "bybit":
            url = f"{self.base_url}/v2/public/tickers?symbol={symbol}"
        else:
            return {"error": "不支持的交易所"}

        try:
            response = requests.get(url, timeout=10)
            data = response.json()

            if self.exchange == "okx" and "data" in data:
                return {"symbol": symbol, "price": float(data["data"][0]["last"])}
            elif self.exchange == "bybit" and "result" in data:
                return {"symbol": symbol, "price": float(data["result"][0]["last_price"])}
            else:
                return {"symbol": symbol, "price": float(data["price"])}
        except Exception as e:
            return {"error": str(e)}

    def get_klines(self, symbol: str, interval: str = "1h",
                 limit: int = 100) -> List[Dict]:
        """获取K线数据"""
        if self.exchange == "binance" or self.exchange == "binance_futures":
            url = f"{self.base_url}/fapi/v1/klines?symbol={symbol}&interval={interval}&limit={limit}"
        elif self.exchange == "okx":
            okx_interval = self._convert_interval_okx(interval)
            url = f"{self.base_url}/api/v5/market/candles?instId={symbol}&bar={okx_interval}&limit={limit}"
        elif self.exchange == "bybit":
            url = f"{self.base_url}/v2/public/kline/list?symbol={symbol}&interval={interval}&limit={limit}"
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
            elif self.exchange == "bybit" and "result" in data:
                for k in data["result"]:
                    result.append({
                        "time": k["open_time"],
                        "open": float(k["open"]),
                        "high": float(k["high"]),
                        "low": float(k["low"]),
                        "close": float(k["close"]),
                        "volume": float(k["volume"])
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
            logger.error(f"获取K线失败: {e}")
            return []

    def get_multi_timeframe_klines(self, symbol: str) -> Dict[str, List[Dict]]:
        """获取多时间框架K线数据"""
        timeframes = ["1d", "4h", "1h", "15m", "5m"]
        klines_data = {}

        for tf in timeframes:
            klines_data[tf] = self.get_klines(symbol, tf, 200 if tf in ["1d", "4h"] else 500)

        return klines_data

    def _convert_interval_okx(self, interval: str) -> str:
        """转换K线周期为OKX格式"""
        mapping = {
            "1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
            "1h": "1H", "2h": "2H", "4h": "4H", "6h": "6H", "12h": "12H",
            "1d": "1D", "1w": "1W", "1M": "1M"
        }
        return mapping.get(interval, "1H")

    # ============ 交易执行方法 ============

    def execute_trade(self,
                     symbol: str,
                     side: str,
                     amount: float,
                     price: Optional[float] = None,
                     order_type: str = "MARKET") -> Dict:
        """
        执行交易

        参数:
            symbol: 交易对 (如: BTCUSDT)
            side: 方向 ("buy" 或 "sell")
            amount: 数量
            price: 价格 (None表示市价)
            order_type: 订单类型 ("MARKET" 或 "LIMIT")
        """
        # 检查回撤控制
        can_open, reason = self.drawdown_controller.can_open_position()
        if not can_open:
            return {
                "success": False,
                "message": f"回撤控制: {reason}",
                "blocked_by_risk_control": True
            }

        # 检查相关性风险
        current_price = price if price else self.get_price(symbol).get("price", 0)
        if current_price > 0:
            can_open, reason, max_size = self.correlation_manager.can_open_position(
                symbol, side, amount, current_price, self.get_balance()
            )
            if not can_open:
                return {
                    "success": False,
                    "message": f"相关性风险: {reason}",
                    "blocked_by_correlation_control": True,
                    "max_allowed_size": max_size
                }
            elif max_size < amount:
                amount = max_size
                logger.warning(f"仓位因相关性风险减小至 {max_size:.6f}")

        # 执行交易
        if self.exchange == "binance" or self.exchange == "binance_futures":
            return self._binance_trade(symbol, side, amount, price, order_type)
        elif self.exchange == "okx":
            return self._okx_trade(symbol, side, amount, price, order_type)
        elif self.exchange == "bybit":
            return self._bybit_trade(symbol, side, amount, price, order_type)
        else:
            return {"success": False, "message": "不支持的交易所"}

    def _binance_trade(self, symbol: str, side: str, amount: float,
                      price: Optional[float], order_type: str) -> Dict:
        """Binance交易"""
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
                "message": "订单成功",
                "order_id": result["orderId"],
                "symbol": symbol,
                "side": side,
                "amount": amount
            }
        else:
            return {"success": False, "message": result.get("msg", "订单失败")}

    def _okx_trade(self, symbol: str, side: str, amount: float,
                   price: Optional[float], order_type: str) -> Dict:
        """OKX交易"""
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
                "message": "订单成功",
                "order_id": result["data"][0]["ordId"],
                "symbol": symbol,
                "side": side,
                "amount": amount
            }
        else:
            return {"success": False, "message": "订单失败"}

    def _bybit_trade(self, symbol: str, side: str, amount: float,
                    price: Optional[float], order_type: str) -> Dict:
        """Bybit交易"""
        endpoint = "/private/linear/order/create"
        params = {
            "symbol": symbol,
            "side": "Buy" if side.lower() in ["buy", "long"] else "Sell",
            "order_type": "Market" if order_type == "MARKET" else "Limit",
            "qty": str(amount),
            "time_in_force": "GoodTillCancel"
        }

        if order_type == "LIMIT" and price:
            params["price"] = str(price)

        result = self._make_request("POST", endpoint, params, signed=True)

        if "result" in result and result["result"]:
            return {
                "success": True,
                "message": "订单成功",
                "order_id": result["result"]["order_id"],
                "symbol": symbol,
                "side": side,
                "amount": amount
            }
        else:
            return {"success": False, "message": "订单失败"}

    # ============ 增强分析方法 ============

    def analyze_with_enhanced_features(self,
                                     symbol: str) -> Dict:
        """
        使用所有增强功能分析市场

        返回:
            包含多时间框架分析、市场状态、资金费率等信息
        """
        # 1. 获取多时间框架K线
        klines_data = self.get_multi_timeframe_klines(symbol)

        # 2. 多时间框架分析
        mtf_result = self.mtf_analyzer.analyze(symbol, klines_data)

        # 3. 市场状态检测
        market_state = self.market_state_detector.detect(
            symbol, klines_data.get("1h", [])
        )

        # 4. 获取当前价格
        price_info = self.get_price(symbol)
        current_price = price_info.get("price", 0)

        return {
            "symbol": symbol,
            "current_price": current_price,
            "multi_timeframe": mtf_result,
            "market_state": market_state,
            "recommended_strategies": market_state.recommended_strategies,
            "forbidden_strategies": market_state.forbidden_strategies,
            "trading_condition": market_state.trading_condition.value,
            "can_trade": market_state.trading_condition.value not in ["avoid", "poor"]
        }

    def generate_trade_signal(self, symbol: str) -> Dict:
        """
        生成交易信号 - 综合所有增强功能

        返回:
            {
                "signal": "buy/sell/hold",
                "confidence": 0-1,
                "position_size": float,
                "stop_loss": float,
                "take_profit": float,
                "reason": str,
                "warnings": List[str]
            }
        """
        # 获取增强分析
        analysis = self.analyze_with_enhanced_features(symbol)

        mtf_result = analysis["multi_timeframe"]
        market_state = analysis["market_state"]

        # 检查是否可以交易
        if not analysis["can_trade"]:
            return {
                "signal": "hold",
                "confidence": 0,
                "reason": f"交易条件不佳: {analysis['trading_condition']}",
                "warnings": market_state.warnings + [f"禁止策略: {market_state.forbidden_strategies}"]
            }

        # 检查多时间框架趋势一致性
        if not mtf_result.trend_alignment:
            return {
                "signal": "hold",
                "confidence": 0.3,
                "reason": "多时间框架趋势不一致",
                "warnings": mtf_result.warnings
            }

        # 综合信号
        signal = mtf_result.entry_signal
        if signal == "hold":
            return {
                "signal": "hold",
                "confidence": 0,
                "reason": "无入场信号",
                "warnings": mtf_result.warnings
            }

        # 过滤信号
        filtered_signal, confidence, reasons = self.strategy_filter.filter_signal(
            symbol, signal,
            analysis.get("klines", {}).get("1h", []),
            "trend_follow"
        )

        if filtered_signal == "hold":
            return {
                "signal": "hold",
                "confidence": confidence,
                "reason": f"信号被过滤: {'; '.join(reasons)}",
                "warnings": reasons
            }

        # 获取自适应参数
        params = self.adaptive_system.get_parameters()

        # 计算动态仓位
        current_price = analysis["current_price"]
        position_result = self.position_sizer.calculate_position_size(
            symbol, current_price,
            stop_loss_price=current_price * (1 - params.get("stop_loss_pct", 0.02)),
            klines=analysis.get("klines", {}).get("1h", []),
            market_conditions={
                "trend_strength": market_state.trend_strength,
                "volatility_level": market_state.volatility_level.value,
                "liquidity_score": market_state.liquidity_score
            }
        )

        # 计算止损止盈
        if signal == "buy":
            sl = current_price * (1 - params.get("stop_loss_pct", 0.02))
            tp = current_price * (1 + params.get("take_profit_pct", 0.04))
        else:
            sl = current_price * (1 + params.get("stop_loss_pct", 0.02))
            tp = current_price * (1 - params.get("take_profit_pct", 0.04))

        # 收集所有警告
        warnings = []
        warnings.extend(mtf_result.warnings)
        warnings.extend(market_state.warnings)
        warnings.extend(position_result.warnings)

        return {
            "signal": filtered_signal,
            "confidence": min(confidence, position_result.confidence),
            "position_size": position_result.adjusted_size,
            "stop_loss": sl,
            "take_profit": tp,
            "recommended_leverage": position_result.recommended_leverage,
            "reason": f"综合信号: {filtered_signal} (置信度{confidence:.2%})",
            "warnings": warnings,
            "position_analysis": {
                "base_size": position_result.base_size,
                "adjusted_size": position_result.adjusted_size,
                "risk_percentage": position_result.risk_percentage,
                "volatility_regime": position_result.volatility_regime.value,
                "adjustment_factors": position_result.adjustment_factors
            }
        }

    def execute_with_risk_controls(self,
                                   signal: Dict,
                                   symbol: str) -> Dict:
        """
        使用风险控制执行交易

        参数:
            signal: generate_trade_signal 返回的信号
            symbol: 交易品种

        返回:
            执行结果
        """
        if signal["signal"] == "hold":
            return {
                "success": False,
                "message": signal["reason"],
                "signal": "hold"
            }

        # 再次检查回撤控制
        can_open, reason = self.drawdown_controller.can_open_position()
        if not can_open:
            return {
                "success": False,
                "message": f"被风险控制阻止: {reason}",
                "blocked_by_risk_control": True
            }

        # 执行交易
        result = self.execute_trade(
            symbol,
            signal["signal"],
            signal["position_size"]
        )

        if result.get("success"):
            # 记录持仓到移动止损引擎
            current_price = signal.get("current_price", 0)
            if "take_profit" in signal:
                sl = signal.get("stop_loss")
                tp = signal.get("take_profit")

                self.trailing_engine.update_position(
                    symbol=symbol,
                    side="long" if signal["signal"] == "buy" else "short",
                    entry_price=current_price,
                    current_price=current_price,
                    current_sl=sl,
                    current_tp=tp
                )

            # 添加到相关性管理器
            self.correlation_manager.add_position(
                symbol,
                signal["signal"],
                signal["position_size"],
                current_price,
                current_price
            )

            # 添加到仓位管理器
            self.position_sizer.add_position(
                symbol,
                signal["position_size"],
                current_price,
                signal.get("stop_loss_pct", 0.02),
                signal["position_size"] * current_price / self.get_balance()
            )

        return result

    def update_positions_and_trailing_stop(self):
        """更新所有持仓和移动止损"""
        positions = self.get_positions()

        for pos in positions:
            symbol = pos["symbol"]
            side = pos["side"]
            current_price = pos.get("current_price", self.get_price(symbol).get("price", 0))

            # 更新相关性管理器
            self.correlation_manager.update_position_price(symbol, current_price)

            # 更新移动止损
            if symbol in self.active_positions:
                active_pos = self.active_positions[symbol]
                new_sl, new_tp = self.trailing_engine.update_position(
                    symbol=symbol,
                    side=side,
                    entry_price=active_pos["entry_price"],
                    current_price=current_price,
                    current_sl=active_pos.get("sl"),
                    current_tp=active_pos.get("tp")
                )

                # 如果止损发生变化，可以在这里执行调整
                if new_sl != active_pos["sl"]:
                    logger.info(f"{symbol} 移动止损更新: {active_pos['sl']:.2f} -> {new_sl:.2f}")
                    active_pos["sl"] = new_sl

    def close_all_positions(self) -> Dict:
        """平所有持仓"""
        positions = self.get_positions()
        success_count = 0
        failed_count = 0

        for pos in positions:
            side = "sell" if pos["side"] == "long" else "buy"

            # 从移动止损引擎移除
            self.trailing_engine.remove_position(pos["symbol"], "long")

            # 从相关性管理器移除
            self.correlation_manager.remove_position(pos["symbol"])

            # 从仓位管理器移除
            if pos["symbol"] in self.active_positions:
                active_pos = self.active_positions[pos["symbol"]]
                self.position_sizer.remove_position(
                    pos["symbol"],
                    active_pos["size"],
                    pos["price"]
                )
                del self.active_positions[pos["symbol"]]

            # 执行平仓
            result = self.execute_trade(pos["symbol"], side, pos["amount"])
            if result["success"]:
                success_count += 1
            else:
                failed_count += 1

        return {
            "success": failed_count == 0,
            "message": f"平仓完成: 成功 {success_count}, 失败 {failed_count}"
        }

    def get_system_status(self) -> Dict:
        """获取系统状态"""
        # 回撤控制器状态
        dd_report = self.drawdown_controller.get_risk_report()

        # 相关性风险报告
        corr_report = self.correlation_manager.get_risk_report(self.get_balance())

        # 仓位管理器状态
        pos_stats = self.position_sizer.get_statistics()

        # 自适应参数状态
        param_report = self.adaptive_system.get_parameter_report()

        return {
            "timestamp": datetime.now().isoformat(),
            "account": {
                "balance": self.get_balance(),
                "positions_count": len(self.get_positions())
            },
            "drawdown_control": dd_report,
            "correlation_risk": {
                "total_positions": corr_report.total_positions,
                "correlated_positions": corr_report.correlated_positions,
                "overall_risk": corr_report.overall_risk_level
            },
            "position_management": pos_stats,
            "adaptive_parameters": {
                "current_params": param_report["current_parameters"],
                "adjustment_count": param_report["adjustment_count"]
            },
            "trailing_stop": self.trailing_engine.get_summary()
        }


class EnhancedCryptoTradingStrategy:
    """增强加密货币交易策略"""

    def __init__(self, trader: EnhancedExchangeTrader, config: Dict):
        self.trader = trader
        self.config = config
        self.symbols = config.get("symbols", ["BTCUSDT", "ETHUSDT"])

    def analyze_and_execute(self, symbol: str) -> Dict:
        """分析并执行交易"""
        # 生成交易信号
        signal = self.trader.generate_trade_signal(symbol)

        logger.info(
            f"{symbol} 信号: {signal['signal']}, "
            f"置信度: {signal['confidence']:.2%}, "
            f"仓位: {signal['position_size']:.6f}"
        )

        # 执行交易
        if signal["signal"] in ["buy", "sell"]:
            result = self.trader.execute_with_risk_controls(signal, symbol)
            return {
                "action": "executed",
                "signal": signal,
                "result": result
            }
        else:
            return {
                "action": "hold",
                "signal": signal,
                "reason": signal["reason"]
            }

    def update_positions(self):
        """更新持仓和移动止损"""
        self.trader.update_positions_and_trailing_stop()

    def get_full_report(self) -> Dict:
        """获取完整报告"""
        report = {
            "timestamp": datetime.now().isoformat(),
            "system_status": self.trader.get_system_status()
        }

        # 为每个品种生成信号报告
        report["signals"] = {}
        for symbol in self.symbols:
            try:
                signal = self.trader.generate_trade_signal(symbol)
                report["signals"][symbol] = {
                    "signal": signal["signal"],
                    "confidence": signal["confidence"],
                    "warnings": signal["warnings"]
                }
            except Exception as e:
                logger.error(f"生成 {symbol} 信号失败: {e}")
                report["signals"][symbol] = {"error": str(e)}

        return report


if __name__ == "__main__":
    # 测试代码
    from config.enhanced_trading_config import EnhancedTradingConfig, DEFAULT_CONFIG_TEMPLATE
    import os

    # 创建配置文件
    config_path = "config/enhanced_trading_config.json"
    os.makedirs(os.path.dirname(config_path), exist_ok=True)

    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(DEFAULT_CONFIG_TEMPLATE, f, indent=2, ensure_ascii=False)

    print(f"配置文件已创建: {config_path}")

    # 初始化增强交易器
    config = DEFAULT_CONFIG_TEMPLATE.copy()
    config["api_key"] = "test"
    config["api_secret"] = "test"

    trader = EnhancedExchangeTrader(config)

    print("\n增强交易系统已初始化")
    print("集成的功能模块:")
    print("  ✓ 动态仓位管理")
    print("  ✓ 多时间框架分析")
    print("  ✓ 市场状态过滤")
    print("  ✓ 参数自适应系统")
    print("  ✓ 资金费率套利")
    print("  ✓ 回撤控制和仓位递减")
    print("  ✓ 相关性风险控制")
    print("  ✓ 高级移动止损引擎")

    print("\n系统状态:")
    status = trader.get_system_status()
    print(f"  余额: ${status['account']['balance']:,.2f}")
    print(f"  持仓数: {status['account']['positions_count']}")
