# 币圈实盘数据获取模块
# 获取链上数据、资金费、市场挂单、深度数据等

import os
import json
import logging
import requests
import time
import hashlib
import hmac
import base64
from typing import Dict, List, Optional
from datetime import datetime
import pandas as pd

logger = logging.getLogger(__name__)


class ExchangeDataProvider:
    """交易所数据提供者基类"""

    def __init__(self, config: Dict):
        self.config = config
        self.exchange = config.get("exchange", "binance")
        self.api_key = config.get("api_key", "")
        self.api_secret = config.get("api_secret", "")
        self.testnet = config.get("testnet", True)

        self.base_urls = {
            "binance": {
                "spot": "https://api.binance.com",
                "futures": "https://fapi.binance.com",
                "spot_test": "https://testnet.binance.vision",
                "futures_test": "https://testnet.binancefuture.com"
            },
            "okx": {
                "spot": "https://www.okx.com",
                "futures": "https://www.okx.com"
            },
            "bybit": {
                "spot": "https://api.bybit.com",
                "futures": "https://api.bybit.com"
            },
            "huobi": {
                "spot": "https://api.huobi.pro",
                "futures": "https://api.huobi.pro"
            }
        }

    def _get_headers(self) -> Dict:
        """获取请求头"""
        headers = {"Content-Type": "application/json"}

        if self.exchange == "binance" or self.exchange == "binance_futures":
            headers["X-MBX-APIKEY"] = self.api_key
        elif self.exchange == "okx":
            headers["OK-ACCESS-KEY"] = self.api_key
            headers["OK-ACCESS-SIGN"] = self._generate_okx_signature()
            headers["OK-ACCESS-TIMESTAMP"] = str(int(time.time() * 1000))
            headers["OK-ACCESS-PASSPHRASE"] = self.config.get("passphrase", "")

        return headers

    def _generate_okx_signature(self) -> str:
        """生成OKX签名（简化版，完整版本需要更复杂的处理）"""
        # 实际使用时需要正确实现签名
        import hmac
        import base64
        timestamp = str(int(time.time() * 1000))
        sign = hmac.new(self.api_secret.encode(), timestamp.encode(), hashlib.sha256).digest()
        return base64.b64encode(sign).decode()

    def _request(self, endpoint: str, method: str = "GET",
                  params: Optional[Dict] = None, data: Optional[Dict] = None) -> Dict:
        """发送请求"""
        try:
            headers = self._get_headers()

            if self.exchange == "binance":
                base_url = self.base_urls["binance"]["futures_test"] if self.testnet else self.base_urls["binance"]["futures"]
            elif self.exchange == "binance_spot":
                base_url = self.base_urls["binance"]["spot_test"] if self.testnet else self.base_urls["binance"]["spot"]
            elif self.exchange == "okx":
                base_url = self.base_urls["okx"]["futures"]
            elif self.exchange == "bybit":
                base_url = self.base_urls["bybit"]["futures"]
            elif self.exchange == "huobi":
                base_url = self.base_urls["huobi"]["futures"]
            else:
                raise ValueError(f"不支持的交易所: {self.exchange}")

            url = f"{base_url}{endpoint}"

            if method == "GET":
                response = requests.get(url, headers=headers, params=params, timeout=10)
            else:
                response = requests.post(url, headers=headers, json=data, timeout=10)

            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            logger.error(f"请求失败 {endpoint}: {e}")
            return {"error": str(e)}

    def get_account_info(self) -> Dict:
        """获取账户信息"""
        if self.exchange == "binance" or self.exchange == "binance_futures":
            result = self._request("/fapi/v2/account", "GET")
            if "error" in result:
                return result
            return {
                "total_balance": float(result.get("totalWalletBalance", 0)),
                "available_balance": float(result.get("availableBalance", 0)),
                "margin_balance": float(result.get("totalMarginBalance", 0))
            }
        else:
            return {"error": "未实现"}

    def get_positions(self) -> List[Dict]:
        """获取持仓"""
        if self.exchange == "binance" or self.exchange == "binance_futures":
            result = self._request("/fapi/v2/positionRisk", "GET")
            if "error" in result:
                return []

            positions = []
            for pos in result:
                positions.append({
                    "symbol": pos.get("symbol"),
                    "side": "long" if pos.get("positionSide") == "LONG" else "short",
                    "size": float(pos.get("positionAmt", 0)),
                    "entry_price": float(pos.get("entryPrice", 0)),
                    "mark_price": float(pos.get("markPrice", 0)),
                    "unrealized_pnl": float(pos.get("unRealizedProfit", 0)),
                    "margin": float(pos.get("isolatedMargin", 0)),
                    "leverage": pos.get("leverage", "1"),
                    "liquidation_price": float(pos.get("liquidationPrice", 0))
                })
            return positions
        else:
            return []

    def get_open_orders(self) -> List[Dict]:
        """获取挂单"""
        if self.exchange == "binance" or self.exchange == "binance_futures":
            result = self._request("/fapi/v1/openOrders", "GET")
            if "error" in result:
                return []

            orders = []
            for order in result:
                orders.append({
                    "order_id": order.get("orderId"),
                    "symbol": order.get("symbol"),
                    "side": order.get("side"),
                    "type": order.get("type"),
                    "quantity": float(order.get("origQty", 0)),
                    "price": float(order.get("price", 0)),
                    "status": order.get("status"),
                    "create_time": order.get("time")
                })
            return orders
        else:
            return []

    def get_order_book(self, symbol: str, limit: int = 20) -> Dict:
        """获取深度数据"""
        if self.exchange == "binance" or self.exchange == "binance_futures":
            result = self._request(f"/fapi/v1/depth?symbol={symbol}&limit={limit}", "GET")
            if "error" in result:
                return {}

            bids = [[float(price), float(amount)] for price, amount in result.get("bids", [])]
            asks = [[float(price), float(amount)] for price, amount in result.get("asks", [])]

            # 计算买卖压力
            total_bid_volume = sum(amount for _, amount in bids)
            total_ask_volume = sum(amount for _, amount in asks)
            pressure = (total_bid_volume / (total_bid_volume + total_ask_volume) * 100) if total_bid_volume + total_ask_volume > 0 else 50

            return {
                "symbol": symbol,
                "bids": bids[:10],
                "asks": asks[:10],
                "best_bid": bids[0][0] if bids else None,
                "best_ask": asks[0][0] if asks else None,
                "spread": (asks[0][0] - bids[0][0]) if asks and bids else 0,
                "spread_percent": ((asks[0][0] - bids[0][0]) / bids[0][0] * 100) if asks and bids else 0,
                "buying_pressure": pressure,
                "selling_pressure": 100 - pressure
            }
        else:
            return {}

    def get_funding_rate(self, symbol: str) -> Dict:
        """获取资金费率"""
        if self.exchange == "binance" or self.exchange == "binance_futures":
            result = self._request(f"/fapi/v1/premiumIndex?symbol={symbol}", "GET")
            if "error" in result:
                return {"error": result.get("error")}

            return {
                "symbol": symbol,
                "last_funding_rate": float(result.get("lastFundingRate", 0)),
                "next_funding_time": result.get("nextFundingTime"),
                "index_price": float(result.get("indexPrice", 0)),
                "mark_price": float(result.get("markPrice", 0))
            }
        elif self.exchange == "okx":
            result = self._request(f"/api/v5/public/funding-rate?instId={symbol}-USDT-SWAP", "GET")
            if "error" in result:
                return {"error": result.get("error")}

            data = result.get("data", [{}])
            return {
                "symbol": symbol,
                "funding_rate": float(data[0].get("fundingRate", 0)) / 100 if data else 0,
                "funding_time": data[0].get("fundingTime")
            }
        else:
            return {"error": "未实现"}

    def get_24h_funding_rate_history(self, symbol: str) -> List[Dict]:
        """获取24小时资金费历史"""
        if self.exchange == "binance" or self.exchange == "binance_futures":
            result = self._request(f"/fapi/v1/fundingRate?symbol={symbol}&limit=48", "GET")
            if "error" in result:
                return []

            history = []
            for rate in result:
                history.append({
                    "symbol": symbol,
                    "funding_rate": float(rate.get("fundingRate", 0)),
                    "funding_time": rate.get("fundingTime"),
                    "mark_price": float(rate.get("markPrice", 0))
                })
            return history
        else:
            return []

    def get_ticker_price(self, symbol: str) -> Dict:
        """获取实时价格"""
        if self.exchange == "binance" or self.exchange == "binance_futures":
            result = self._request(f"/fapi/v1/ticker/price?symbol={symbol}", "GET")
            if "error" in result:
                return {}

            data = result.get(symbol, {})
            return {
                "symbol": symbol,
                "price": float(data.get("lastPrice", 0)),
                "bid_price": float(data.get("bidPrice", 0)),
                "ask_price": float(data.get("askPrice", 0)),
                "timestamp": data.get("time")
            }
        else:
            return {}

    def get_klines(self, symbol: str, interval: str = "1h",
                 limit: int = 100) -> List[Dict]:
        """获取K线数据"""
        if self.exchange == "binance" or self.exchange == "binance_futures":
            result = self._request(f"/fapi/v1/klines?symbol={symbol}&interval={interval}&limit={limit}", "GET")
            if "error" in result:
                return []

            klines = []
            for k in result:
                klines.append({
                    "open": float(k[0]),
                    "high": float(k[1]),
                    "low": float(k[2]),
                    "close": float(k[3]),
                    "volume": float(k[4]),
                    "close_time": k[6],
                    "trades": int(k[8]) if len(k) > 8 else 0
                })
            return klines
        else:
            return []

    def get_leverage_bracket(self, symbol: str) -> Dict:
        """获取杠杆档位"""
        if self.exchange == "binance" or self.exchange == "binance_futures":
            result = self._request(f"/fapi/v1/leverageBracket?symbol={symbol}", "GET")
            if "error" in result:
                return {}

            brackets = result.get("brackets", [])
            return {
                "symbol": symbol,
                "brackets": brackets,
                "max_leverage": max([b["leverage"] for b in brackets]) if brackets else 1
            }
        else:
            return {}


class CapitalManager:
    """本金管理器 - 自动计算和分配本金"""

    def __init__(self, config: Dict):
        self.config = config
        self.total_capital = config.get("total_capital", 10000)
        self.max_per_trade = config.get("max_per_trade", 0.1)  # 单笔最大10%
        self.min_capital = config.get("min_capital", 1000)
        self.auto_recharge = config.get("auto_recharge", True)

    def get_available_capital(self, current_positions: List[Dict],
                            current_price_map: Dict[str, float]) -> float:
        """获取可用本金"""
        # 计算持仓占用的保证金
        used_margin = 0
        for pos in current_positions:
            symbol = pos.get("symbol")
            if symbol in current_price_map:
                price = current_price_map[symbol]
                size = pos.get("size", 0)
                leverage = float(pos.get("leverage", 1))
                used_margin += (price * size) / leverage

        available = self.total_capital - used_margin

        # 确保不低于最低本金
        return max(available, self.min_capital)

    def calculate_position_size(self, symbol: str, price: float,
                              current_positions: List[Dict],
                              risk_ratio: float = 0.02) -> float:
        """计算仓位大小"""
        available = self.get_available_capital(current_positions, {symbol: price})

        # 基于风险比例计算
        size = (available * risk_ratio) / price

        # 确保不超过单笔最大限制
        size = min(size, self.max_per_trade * self.total_capital / price)

        # 确保不超过可用本金
        size = min(size, available / price)

        return size

    def record_capital_change(self, amount: float, reason: str):
        """记录本金变动"""
        logger.info(f"本金变动: {amount:+.2f}, 原因: {reason}")
        self.total_capital += amount

        # 自动充值检查
        if self.auto_recharge and self.total_capital < self.min_capital:
            logger.warning(f"本金低于最低值 {self.min_capital}，需要充值")
            # 这里可以添加自动充值逻辑

    def get_capital_status(self) -> Dict:
        """获取本金状态"""
        return {
            "total_capital": self.total_capital,
            "max_per_trade": self.max_per_trade,
            "min_capital": self.min_capital,
            "auto_recharge": self.auto_recharge
        }


class MarketDataCollector:
    """市场数据收集器 - 整合多个数据源"""

    def __init__(self, config: Dict):
        self.config = config
        self.providers = {}
        self.capital_manager = CapitalManager(config.get("capital", {}))

        # 初始化交易所数据提供者
        exchanges_config = config.get("exchanges", {})
        for ex_name, ex_config in exchanges_config.items():
            if ex_config.get("enabled", False):
                self.providers[ex_name] = ExchangeDataProvider(ex_config)

    def update_all_market_data(self) -> Dict:
        """更新所有市场数据"""
        all_data = {}

        for ex_name, provider in self.providers.items():
            try:
                # 获取账户信息
                account_info = provider.get_account_info()

                # 获取持仓
                positions = provider.get_positions()

                # 获取挂单
                orders = provider.get_open_orders()

                # 获取所有品种的资金费
                funding_rates = {}
                if positions:
                    symbols = list(set(pos.get("symbol") for pos in positions))
                    for symbol in symbols:
                        rates = provider.get_24h_funding_rate_history(symbol)
                        funding_rates[symbol] = rates[-24:] if len(rates) >= 24 else rates

                all_data[ex_name] = {
                    "account": account_info,
                    "positions": positions,
                    "orders": orders,
                    "funding_rates": funding_rates,
                    "timestamp": datetime.now().isoformat()
                }

            except Exception as e:
                logger.error(f"获取 {ex_name} 数据失败: {e}")
                all_data[ex_name] = {"error": str(e)}

        return all_data

    def get_trading_opportunity_analysis(self, symbol: str) -> Dict:
        """分析交易机会"""
        opportunities = []

        for ex_name, provider in self.providers.items():
            try:
                # 获取深度数据
                orderbook = provider.get_order_book(symbol, limit=20)

                if not orderbook:
                    continue

                # 获取资金费
                funding = provider.get_funding_rate(symbol)

                if "error" in funding:
                    funding_rate = 0
                else:
                    funding_rate = funding.get("last_funding_rate", 0)

                # 获取价格
                price_data = provider.get_ticker_price(symbol)

                if not price_data:
                    continue

                current_price = price_data.get("price", 0)
                spread = orderbook.get("spread", 0)
                spread_pct = orderbook.get("spread_percent", 0)

                # 计算交易信号
                signal = self._analyze_opportunity(
                    orderbook,
                    funding_rate,
                    current_price,
                    spread_pct
                )

                opportunities.append({
                    "exchange": ex_name,
                    "symbol": symbol,
                    "price": current_price,
                    "spread": spread,
                    "spread_percent": spread_pct,
                    "funding_rate": funding_rate,
                    "signal": signal["action"],
                    "confidence": signal["confidence"],
                    "reason": signal["reason"],
                    "order_book": {
                        "buying_pressure": orderbook.get("buying_pressure"),
                        "selling_pressure": orderbook.get("selling_pressure"),
                        "best_bid": orderbook.get("best_bid"),
                        "best_ask": orderbook.get("best_ask")
                    }
                })

            except Exception as e:
                logger.error(f"分析 {ex_name} 机会失败: {e}")

        return {
            "symbol": symbol,
            "opportunities": opportunities
        }

    def _analyze_opportunity(self, orderbook: Dict, funding_rate: float,
                          current_price: float, spread_pct: float) -> Dict:
        """分析交易机会"""
        confidence = 0.5
        action = "hold"
        reason = ""

        # 资金费分析
        if funding_rate > 0.01:  # 正资金费（做空）
            funding_signal = "short"
            confidence += 0.1
            reason += f"正资金费 {funding_rate*100:.3f}%，适合做空"
        elif funding_rate < -0.01:  # 负资金费（做多）
            funding_signal = "long"
            confidence += 0.1
            reason += f"负资金费 {funding_rate*100:.3f}%，适合做多"
        else:
            funding_signal = "neutral"
            reason += f"资金费接近0 {funding_rate*100:.3f}%"

        # 深度分析
        buying_pressure = orderbook.get("buying_pressure", 50)
        selling_pressure = orderbook.get("selling_pressure", 50)
        pressure_diff = abs(buying_pressure - selling_pressure)

        if buying_pressure > 60:  # 买盘压力大，价格可能上涨
            if funding_signal != "short":
                confidence += 0.15
                action = "buy"
                reason += "买盘压力大"
        elif selling_pressure > 60:  # 卖盘压力大，价格可能下跌
            if funding_signal != "long":
                confidence += 0.15
                action = "sell"
                reason += "卖盘压力大"

        # 点差分析
        if spread_pct < 0.01:
            confidence += 0.1
            reason += f"点差极小 {spread_pct:.2f}%"

        # 综合判断
        if confidence > 0.7:
            pass  # 保持当前判断
        elif confidence > 0.5:
            if action == "hold":
                action = funding_signal
        else:
            # 优先考虑资金费方向
            if (funding_signal == "long" and action == "sell") or \
               (funding_signal == "short" and action == "buy"):
                action = funding_signal

        return {
            "action": action,
            "confidence": min(confidence, 0.9),
            "reason": reason,
            "funding_direction": funding_signal
        }

    def execute_order(self, exchange: str, symbol: str, side: str,
                   quantity: float, order_type: str = "MARKET") -> Dict:
        """执行订单"""
        if exchange not in self.providers:
            return {"error": f"交易所 {exchange} 未配置"}

        provider = self.providers[exchange]

        endpoint = "/fapi/v1/order" if order_type == "MARKET" else "/fapi/v1/order"

        params = {
            "symbol": symbol,
            "side": side.upper(),
            "type": order_type,
            "quantity": f"{quantity:.6f}"
        }

        if order_type == "LIMIT":
            params["price"] = self._get_limit_price(provider, symbol, side)

        result = provider._request(endpoint, "POST", data=params)

        if "error" in result:
            return {"error": result.get("error")}

        return {
            "success": True,
            "order_id": result.get("orderId", result.get("orderId", "")),
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "price": result.get("price", 0),
            "status": result.get("status", "NEW")
        }

    def _get_limit_price(self, provider, symbol: str, side: str) -> float:
        """获取限价"""
        ticker = provider.get_ticker_price(symbol)
        if side.upper() == "BUY":
            return ticker.get("ask_price", 0)
        else:
            return ticker.get("bid_price", 0)

    def cancel_order(self, exchange: str, order_id: str) -> Dict:
        """取消订单"""
        if exchange not in self.providers:
            return {"error": f"交易所 {exchange} 未配置"}

        provider = self.providers[exchange]
        result = provider._request(f"/fapi/v1/order", "DELETE",
                                       params={"orderId": order_id})

        return {"success": result.get("code") == 200}

    def get_capital_status(self) -> Dict:
        """获取本金状态"""
        return self.capital_manager.get_capital_status()


class OnChainDataManager:
    """链上数据管理器"""

    def __init__(self, config: Dict):
        self.config = config
        self.enabled = config.get("enabled", False)
        self.rpc_urls = config.get("rpc_urls", {})
        self.wallet_address = config.get("wallet_address", "")
        self.whale_alert_enabled = config.get("whale_alert", {}).get("enabled", False)
        self.whale_threshold = config.get("whale_alert", {}).get("threshold", 1000000)  # 100万USDT

    def get_chain_data(self, chain: str, token: str) -> Dict:
        """获取链上数据"""
        if not self.enabled:
            return {"error": "链上数据未启用"}

        rpc_url = self.rpc_urls.get(chain)
        if not rpc_url:
            return {"error": f"未配置 {chain} 的RPC节点"}

        try:
            # 这里需要集成区块链节点，使用web3.py等库
            # 简化实现，实际需要完整实现
            return {
                "chain": chain,
                "token": token,
                "rpc_url": rpc_url,
                "note": "需要配置web3.py等库进行完整实现"
            }
        except Exception as e:
            logger.error(f"获取链上数据失败: {e}")
            return {"error": str(e)}

    def get_large_transactions(self, chain: str, token: str,
                             hours: int = 24) -> List[Dict]:
        """获取大额交易"""
        if not self.enabled or not self.whale_alert_enabled:
            return []

        # 这里需要集成区块链API（如Etherscan, BscScan等）
        # 简化实现
        return []

    def get_whale_wallet_activity(self, chain: str, addresses: List[str]) -> List[Dict]:
        """监控鲸鱼钱包活动"""
        if not self.enabled:
            return []

        # 监控指定地址的大额转账
        activities = []
        for addr in addresses:
            # 这里需要调用区块链API
            pass

        return activities


class MT5DataProvider:
    """MT5实盘数据提供者 - 外汇、黄金"""

    def __init__(self, mt5_bridge=None):
        self.mt5_bridge = mt5_bridge
        self.supported_symbols = {
            "XAUUSD": {"name": "黄金", "digits": 2, "pip_size": 0.01},
            "XAGUSD": {"name": "白银", "digits": 2, "pip_size": 0.01},
            "EURUSD": {"name": "欧元/美元", "digits": 5, "pip_size": 0.0001},
            "GBPUSD": {"name": "英镑/美元", "digits": 5, "pip_size": 0.0001},
            "USDJPY": {"name": "美元/日元", "digits": 3, "pip_size": 0.01},
            "USDCHF": {"name": "美元/瑞郎", "digits": 5, "pip_size": 0.0001},
            "AUDUSD": {"name": "澳元/美元", "digits": 5, "pip_size": 0.0001},
            "NZDUSD": {"name": "纽元/美元", "digits": 5, "pip_size": 0.0001},
            "USDCAD": {"name": "美元/加元", "digits": 5, "pip_size": 0.0001},
            "USDHKD": {"name": "美元/港币", "digits": 5, "pip_size": 0.0001},
            "EURGBP": {"name": "欧元/英镑", "digits": 5, "pip_size": 0.0001},
            "EURJPY": {"name": "欧元/日元", "digits": 3, "pip_size": 0.01},
            "GBPJPY": {"name": "英镑/日元", "digits": 3, "pip_size": 0.01},
            "GBPCHF": {"name": "英镑/瑞郎", "digits": 5, "pip_size": 0.0001},
            "USDPLN": {"name": "美元/波兰兹罗提", "digits": 5, "pip_size": 0.0001},
            "USDMXN": {"name": "美元/墨西哥比索", "digits": 5, "pip_size": 0.0001},
            "USDTRY": {"name": "美元/土耳其里拉", "digits": 5, "pip_size": 0.0001},
            "USDZAR": {"name": "美元/南非兰特", "digits": 5, "pip_size": 0.0001},
            "USDRUB": {"name": "美元/俄罗斯卢布", "digits": 5, "pip_size": 0.0001}
        }

    def get_account_info(self) -> Dict:
        """获取MT5账户信息"""
        if self.mt5_bridge:
            try:
                return self.mt5_bridge.get_account_info()
            except Exception as e:
                logger.error(f"获取MT5账户信息失败: {e}")
                return {"error": str(e)}
        return {"error": "MT5未连接"}

    def get_positions(self) -> List[Dict]:
        """获取MT5持仓"""
        if self.mt5_bridge:
            try:
                return self.mt5_bridge.get_positions()
            except Exception as e:
                logger.error(f"获取MT5持仓失败: {e}")
                return []
        return []

    def get_order_book(self, symbol: str, limit: int = 20) -> Dict:
        """获取MT5深度数据"""
        if not self.mt5_bridge:
            return {}

        try:
            # MT5通过价格获取买卖盘
            tick = self.mt5_bridge.get_tick(symbol)
            if not tick:
                return {}

            current_price = tick.get("bid", 0)
            if current_price == 0:
                current_price = tick.get("ask", 0)

            if current_price == 0:
                return {}

            # 获取品种信息
            symbol_info = self.supported_symbols.get(symbol, {})
            pip_size = symbol_info.get("pip_size", 0.0001)

            # 构建模拟深度（MT5没有直接获取深度的API，需要通过Level2数据）
            bids = []
            asks = []

            for i in range(1, min(limit + 1, 11)):
                bid_price = current_price - (i * pip_size)
                ask_price = current_price + (i * pip_size)

                # 这里应该从MT5获取真实挂单量
                # 简化实现，使用预估量
                bid_volume = max(1.0, 10.0 / i)  # 靠近当前价挂单更多
                ask_volume = max(1.0, 10.0 / i)

                if bid_price > 0:
                    bids.append([round(bid_price, 6), round(bid_volume, 2)])
                asks.append([round(ask_price, 6), round(ask_volume, 2)])

            # 计算买卖压力
            total_bid_volume = sum(v for _, v in bids)
            total_ask_volume = sum(v for _, v in asks)
            pressure = (total_bid_volume / (total_bid_volume + total_ask_volume) * 100) if total_bid_volume + total_ask_volume > 0 else 50

            return {
                "symbol": symbol,
                "bids": bids,
                "asks": asks,
                "best_bid": bids[0][0] if bids else None,
                "best_ask": asks[0][0] if asks else None,
                "spread": (asks[0][0] - bids[0][0]) if asks and bids else 0,
                "spread_pips": round((asks[0][0] - bids[0][0]) / pip_size, 1) if asks and bids else 0,
                "buying_pressure": pressure,
                "selling_pressure": 100 - pressure,
                "source": "MT5"
            }
        except Exception as e:
            logger.error(f"获取MT5深度数据失败: {e}")
            return {}

    def get_market_depth_analysis(self, symbol: str) -> Dict:
        """分析市场深度"""
        orderbook = self.get_order_book(symbol, limit=50)

        if not orderbook:
            return {"error": "无法获取深度数据"}

        bids = orderbook.get("bids", [])
        asks = orderbook.get("asks", [])

        # 计算不同深度档位的成交量
        depth_analysis = {
            "symbol": symbol,
            "depth_levels": {},
            "imbalance": {},
            "liquidity_score": 0
        }

        for level in [5, 10, 20]:
            if len(bids) >= level and len(asks) >= level:
                bid_vol = sum(v for _, v in bids[:level])
                ask_vol = sum(v for _, v in asks[:level])
                total_vol = bid_vol + ask_vol

                imbalance = (bid_vol - ask_vol) / total_vol if total_vol > 0 else 0

                depth_analysis["depth_levels"][f"level_{level}"] = {
                    "bid_volume": round(bid_vol, 2),
                    "ask_volume": round(ask_vol, 2),
                    "total_volume": round(total_vol, 2),
                    "imbalance_pct": round(imbalance * 100, 2)
                }

        # 流动性评分
        total_bid_vol = sum(v for _, v in bids[:10])
        total_ask_vol = sum(v for _, v in asks[:10])
        liquidity = (total_bid_vol + total_ask_vol) / 20

        if liquidity > 5:
            liquidity_score = 5  # 高流动性
        elif liquidity > 2:
            liquidity_score = 3  # 中等流动性
        else:
            liquidity_score = 1  # 低流动性

        depth_analysis["liquidity_score"] = liquidity_score

        return depth_analysis

    def get_available_symbols(self) -> List[Dict]:
        """获取可用品种列表"""
        symbols_list = []
        for symbol, info in self.supported_symbols.items():
            symbols_list.append({
                "symbol": symbol,
                "name": info["name"],
                "digits": info["digits"],
                "pip_size": info["pip_size"],
                "category": "forex" if symbol != "XAUUSD" and symbol != "XAGUSD" else "commodity"
            })
        return symbols_list

    def calculate_position_size(self, symbol: str, risk_percent: float,
                              stop_loss_pips: float, account_balance: float) -> float:
        """计算仓位大小"""
        symbol_info = self.supported_symbols.get(symbol, {})
        pip_value = symbol_info.get("pip_size", 0.0001)

        # 风险金额 = 账户余额 * 风险比例
        risk_amount = account_balance * (risk_percent / 100)

        # 仓位大小 = 风险金额 / (止损点数 * 点值)
        if stop_loss_pips > 0 and pip_value > 0:
            position_size = risk_amount / (stop_loss_pips * pip_value * 10)
        else:
            position_size = risk_amount / (account_balance * 0.01)

        # 限制最大仓位为账户的10%
        max_size = account_balance * 0.1
        position_size = min(position_size, max_size)

        return round(position_size, 2)


class UnifiedMarketDataProvider:
    """统一市场数据提供者 - 整合MT5和交易所"""

    def __init__(self, config: Dict):
        self.config = config

        # 币圈交易所数据
        self.exchanges = {}
        exchanges_config = config.get("exchanges", {})
        for ex_name, ex_config in exchanges_config.items():
            if ex_config.get("enabled", False):
                self.exchanges[ex_name] = ExchangeDataProvider(ex_config)

        # MT5数据
        self.mt5_provider = None
        if config.get("mt5_enabled", False):
            # 需要传入MT5Bridge实例
            pass

        # 链上数据
        self.onchain = OnChainDataManager(config.get("onchain", {}))

        # 本金管理
        self.capital_manager = CapitalManager(config.get("capital", {}))

    def update_all_data(self) -> Dict:
        """更新所有数据源"""
        all_data = {}

        # MT5数据
        if self.mt5_provider:
            try:
                all_data["mt5"] = {
                    "account": self.mt5_provider.get_account_info(),
                    "positions": self.mt5_provider.get_positions(),
                    "type": "forex_commodity"
                }
            except Exception as e:
                logger.error(f"MT5数据获取失败: {e}")
                all_data["mt5"] = {"error": str(e)}

        # 交易所数据
        for ex_name, provider in self.exchanges.items():
            try:
                all_data[ex_name] = {
                    "account": provider.get_account_info(),
                    "positions": provider.get_positions(),
                    "orders": provider.get_open_orders(),
                    "type": "crypto"
                }
            except Exception as e:
                logger.error(f"{ex_name}数据获取失败: {e}")
                all_data[ex_name] = {"error": str(e)}

        all_data["timestamp"] = datetime.now().isoformat()
        return all_data

    def get_trading_opportunities(self, symbols: List[str]) -> List[Dict]:
        """获取所有交易机会"""
        opportunities = []

        for symbol in symbols:
            # 判断是MT5品种还是币圈品种
            if symbol in self.mt5_provider.supported_symbols if self.mt5_provider else []:
                if self.mt5_provider:
                    depth = self.mt5_provider.get_order_book(symbol)
                    analysis = self.mt5_provider.get_market_depth_analysis(symbol)
                    opportunities.append({
                        "platform": "MT5",
                        "symbol": symbol,
                        "depth": depth,
                        "analysis": analysis
                    })
            else:
                # 币圈品种
                for ex_name, provider in self.exchanges.items():
                    try:
                        opp = provider.get_order_book(symbol, limit=20)
                        funding = provider.get_funding_rate(symbol)
                        price = provider.get_ticker_price(symbol)

                        if opp and price:
                            opportunities.append({
                                "platform": ex_name,
                                "symbol": symbol,
                                "depth": opp,
                                "funding": funding,
                                "price": price.get("price", 0)
                            })
                    except Exception as e:
                        logger.error(f"获取 {ex_name} {symbol} 机会失败: {e}")

        return opportunities

    def get_available_symbols(self) -> Dict:
        """获取所有可用品种"""
        symbols = {"mt5": [], "crypto": {}}

        if self.mt5_provider:
            symbols["mt5"] = self.mt5_provider.get_available_symbols()

        for ex_name, provider in self.exchanges.items():
            try:
                # 获取交易所交易对列表
                symbols["crypto"][ex_name] = []  # 需要实现获取交易对
            except Exception as e:
                logger.error(f"获取 {ex_name} 交易对失败: {e}")

        return symbols


def create_market_data_collector(config_path: str) -> MarketDataCollector:
    """创建市场数据收集器"""
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)

    return MarketDataCollector(config)


if __name__ == "__main__":
    # 测试代码
    config = {
        "capital": {
            "total_capital": 10000,
            "max_per_trade": 0.1,
            "min_capital": 1000,
            "auto_recharge": True
        },
        "exchanges": {
            "binance_futures": {
                "enabled": True,
                "exchange": "binance_futures",
                "api_key": "your-api-key",
                "api_secret": "",
                "testnet": True
            },
            "okx": {
                "enabled": False,
                "exchange": "okx",
                "api_key": "",
                "api_secret": "",
                "passphrase": ""
            }
        },
        "onchain": {
            "enabled": False,
            "rpc_urls": {},
            "wallet_address": ""
        }
    }

    collector = MarketDataCollector(config)

    # 测试获取数据
    print("测试市场数据收集...")

    # 测试账户信息
    for ex_name in list(collector.providers.keys()):
        try:
            account = collector.providers[ex_name].get_account_info()
            print(f"\n{ex_name} 账户:")
            print(f"  总余额: {account.get('total_balance', 'N/A')}")
            print(f"  可用余额: {account.get('available_balance', 'N/A')}")

            # 测试持仓
            positions = collector.providers[ex_name].get_positions()
            print(f"  持仓数: {len(positions)}")

            # 测试挂单
            orders = collector.providers[ex_name].get_open_orders()
            print(f"  挂单数: {len(orders)}")
        except Exception as e:
            print(f"  {ex_name} 错误: {e}")

    # 测试资金费
    if "binance_futures" in collector.providers:
        funding = collector.providers["binance_futures"].get_funding_rate("BTCUSDT")
        print(f"\nBTCUSDT资金费: {funding}")

    # 测试深度
    orderbook = collector.get_trading_opportunity_analysis("BTCUSDT")
    print(f"\nBTCUSDT交易机会:")
    for opp in orderbook["opportunities"][:3]:
        print(f"  {opp['exchange']}: {opp['signal']} ({opp['confidence']:.2f}) - {opp['reason']}")
