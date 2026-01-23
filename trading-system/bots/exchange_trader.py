# 数字货币交易所交易模块
# 支持Binance、OKX等主流交易所

import hmac
import hashlib
import base64
import json
import time
import logging
from typing import Dict, List, Optional
from datetime import datetime
import requests

logger = logging.getLogger(__name__)


class ExchangeTrader:
    """交易所交易基类"""

    def __init__(self, config: Dict):
        self.config = config
        self.exchange = config.get("exchange", "binance").lower()
        self.api_key = config.get("api_key", "")
        self.api_secret = config.get("api_secret", "")
        self.passphrase = config.get("passphrase", "")  # OKX需要
        self.testnet = config.get("testnet", False)
        self.base_url = self._get_base_url()

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
                return "https://www.okx.com"  # OKX无独立的testnet
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

    def _generate_signature(self, params: Dict, method: str, endpoint: str) -> str:
        """生成签名"""
        if self.exchange == "binance" or self.exchange == "binance_futures":
            return self._binance_sign(params)
        elif self.exchange == "okx":
            return self._okx_sign(method, endpoint, params)
        elif self.exchange == "bybit":
            return self._bybit_sign(params)
        else:
            return ""

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
                if method == "GET":
                    url += "?" + param_str

        try:
            if method == "GET":
                response = requests.get(url, headers=headers, timeout=10)
            else:
                response = requests.post(url, headers=headers, json=params, timeout=10)

            return response.json()
        except Exception as e:
            logger.error(f"请求失败: {e}")
            return {"error": str(e)}

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
        account = self._make_request("GET", "/api/v3/account", signed=True)
        if "error" in account:
            return {"connected": False, "error": account.get("msg", "连接失败")}

        return {
            "connected": True,
            "account": self.api_key[:8] + "...",
            "balance": float(account.get("totalWalletBalance", 0)),
            "equity": float(account.get("totalWalletBalance", 0))
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

        return {
            "connected": True,
            "account": self.api_key[:8] + "...",
            "balance": balance
        }

    def get_balance(self) -> float:
        """获取余额"""
        status = self.get_status()
        return status.get("balance", 0)

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
                    "side": "多" if float(pos["positionAmt"]) > 0 else "空",
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
                        "side": "多" if pos["posSide"] == "long" else "空",
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
                        "side": "多" if pos["side"] == "Buy" else "空",
                        "amount": float(pos["size"]),
                        "price": float(pos["entry_price"]),
                        "pnl": float(pos["unrealised_pnl"])
                    })
        return result

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
                "symbol": symbol
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
                "symbol": symbol
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
                "symbol": symbol
            }
        else:
            return {"success": False, "message": "订单失败"}

    def close_all_positions(self) -> Dict:
        """平所有持仓"""
        positions = self.get_positions()
        success_count = 0
        failed_count = 0

        for pos in positions:
            side = "sell" if pos["side"] == "多" else "buy"
            result = self.execute_trade(pos["symbol"], side, pos["amount"])
            if result["success"]:
                success_count += 1
            else:
                failed_count += 1

        return {
            "success": failed_count == 0,
            "message": f"平仓完成: 成功 {success_count}, 失败 {failed_count}"
        }

    def close_position(self, symbol: str) -> Dict:
        """平指定品种持仓"""
        positions = self.get_positions(symbol)
        success_count = 0

        for pos in positions:
            side = "sell" if pos["side"] == "多" else "buy"
            result = self.execute_trade(symbol, side, pos["amount"])
            if result["success"]:
                success_count += 1

        if success_count == len(positions):
            return {"success": True, "message": "平仓成功"}
        elif success_count > 0:
            return {"success": True, "message": f"部分平仓成功 ({success_count}/{len(positions)})"}
        else:
            return {"success": False, "message": "平仓失败"}

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

    def get_klines(self, symbol: str, interval: str = "1h", limit: int = 100) -> List[Dict]:
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

    def _convert_interval_okx(self, interval: str) -> str:
        """转换K线周期为OKX格式"""
        mapping = {
            "1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
            "1h": "1H", "2h": "2H", "4h": "4H", "6h": "6H", "12h": "12H",
            "1d": "1D", "1w": "1W", "1M": "1M"
        }
        return mapping.get(interval, "1H")


# 交易策略类
class CryptoTradingStrategy:
    """加密货币交易策略"""

    def __init__(self, trader: ExchangeTrader, config: Dict):
        self.trader = trader
        self.config = config
        self.symbols = config.get("symbols", ["BTCUSDT", "ETHUSDT"])
        self.position_size = config.get("position_size", 0.001)
        self.stop_loss_pct = config.get("stop_loss_pct", 0.02)
        self.take_profit_pct = config.get("take_profit_pct", 0.04)

    def analyze(self, symbol: str) -> Dict:
        """分析市场并生成信号"""
        klines = self.trader.get_klines(symbol, "1h", 50)
        if len(klines) < 20:
            return {"signal": "hold", "reason": "数据不足"}

        closes = [k["close"] for k in klines]

        # 计算移动平均线
        ma7 = sum(closes[-7:]) / 7
        ma25 = sum(closes[-25:]) / 25

        # 计算RSI
        rsi = self._calculate_rsi(closes, 14)

        current_price = closes[-1]

        signal = "hold"
        reason = ""

        # 简单策略: MA交叉 + RSI
        if ma7 > ma25 and rsi < 70:
            signal = "buy"
            reason = f"MA7上穿MA25, RSI={rsi:.2f}"
        elif ma7 < ma25 and rsi > 30:
            signal = "sell"
            reason = f"MA7下穿MA25, RSI={rsi:.2f}"
        else:
            reason = f"MA7={ma7:.2f}, MA25={ma25:.2f}, RSI={rsi:.2f}"

        return {
            "signal": signal,
            "reason": reason,
            "price": current_price,
            "ma7": ma7,
            "ma25": ma25,
            "rsi": rsi
        }

    def _calculate_rsi(self, prices: List[float], period: int) -> float:
        """计算RSI指标"""
        if len(prices) < period + 1:
            return 50

        gains = []
        losses = []

        for i in range(1, len(prices)):
            change = prices[i] - prices[i - 1]
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))

        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period

        if avg_loss == 0:
            return 100

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return rsi

    def execute(self, symbol: str) -> Dict:
        """执行策略"""
        analysis = self.analyze(symbol)

        if analysis["signal"] == "hold":
            return {"action": "hold", "message": analysis["reason"]}

        # 获取当前持仓
        positions = self.trader.get_positions(symbol)

        # 检查是否已有该方向的持仓
        for pos in positions:
            pos_side = "buy" if pos["side"] == "多" else "sell"
            if pos_side == analysis["signal"]:
                return {"action": "hold", "message": "已有同方向持仓"}

        # 获取价格
        price_info = self.trader.get_price(symbol)
        if "error" in price_info:
            return {"action": "error", "message": "无法获取价格"}

        current_price = price_info["price"]

        # 计算止损止盈价格
        if analysis["signal"] == "buy":
            sl = current_price * (1 - self.stop_loss_pct)
            tp = current_price * (1 + self.take_profit_pct)
        else:
            sl = current_price * (1 + self.stop_loss_pct)
            tp = current_price * (1 - self.take_profit_pct)

        result = self.trader.execute_trade(
            symbol,
            analysis["signal"],
            self.position_size,
            current_price,
            "LIMIT"
        )

        return {
            "action": "trade",
            "signal": analysis["signal"],
            "result": result
        }
