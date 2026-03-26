import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class MT5AccountInfo:
    login: int
    server: str
    balance: float
    equity: float
    margin: float
    free_margin: float
    currency: str


@dataclass
class MT5SymbolInfo:
    name: str
    description: str
    bid: float
    ask: float
    spread: float
    digits: int
    min_lot: float
    max_lot: float
    lot_step: float
    tick_value: float
    tick_size: float


class MT5Connector:
    def __init__(self):
        self._connected = False
        self._mt5 = None
        self._account_info: Optional[MT5AccountInfo] = None
        self._symbols_cache: List[str] = []

    def is_connected(self) -> bool:
        return self._connected

    def connect(self, server: str, account: int, password: str) -> Tuple[bool, str]:
        try:
            import MetaTrader5 as mt5
            
            if mt5.initialize():
                authorized = mt5.login(login=account, server=server, password=password)
                
                if authorized:
                    self._mt5 = mt5
                    self._connected = True
                    self._account_info = self._get_account_info()
                    self._symbols_cache = self._fetch_all_symbols()
                    logger.info(f"MT5 connected: Account {account} on {server}")
                    return True, "连接成功"
                else:
                    error = mt5.last_error()
                    logger.error(f"MT5 login failed: {error}")
                    return False, f"登录失败: {error}"
            else:
                error = mt5.last_error()
                logger.error(f"MT5 initialization failed: {error}")
                return False, f"初始化失败: {error}"
                
        except ImportError:
            logger.warning("MetaTrader5 package not installed, using simulation mode")
            return self._connect_simulation(server, account, password)
        except Exception as e:
            logger.error(f"MT5 connection error: {e}")
            return False, str(e)

    def _connect_simulation(self, server: str, account: int, password: str) -> Tuple[bool, str]:
        self._connected = True
        self._account_info = MT5AccountInfo(
            login=account,
            server=server,
            balance=10000.0,
            equity=10000.0,
            margin=0.0,
            free_margin=10000.0,
            currency="USD"
        )
        self._symbols_cache = self._get_simulation_symbols()
        logger.info(f"MT5 simulation mode: Account {account}")
        return True, "模拟模式连接成功"

    def _get_account_info(self) -> MT5AccountInfo:
        if not self._mt5:
            return None
        
        try:
            info = self._mt5.account_info()
            if info:
                return MT5AccountInfo(
                    login=info.login,
                    server=info.server,
                    balance=info.balance,
                    equity=info.equity,
                    margin=info.margin,
                    free_margin=info.margin_free,
                    currency=info.currency
                )
        except Exception as e:
            logger.error(f"Failed to get account info: {e}")
        
        return None

    def _fetch_all_symbols(self) -> List[str]:
        if not self._mt5:
            return self._get_simulation_symbols()
        
        try:
            symbols = self._mt5.symbols_get()
            return [s.name for s in symbols if s.visible]
        except Exception as e:
            logger.error(f"Failed to fetch symbols: {e}")
            return self._get_simulation_symbols()

    def _get_simulation_symbols(self) -> List[str]:
        return [
            "XAUUSD", "XAUUSD.m", "XAUUSD.e",
            "EURUSD", "EURUSD.m", "EURUSD.e",
            "GBPUSD", "GBPUSD.m", "GBPUSD.e",
            "USDJPY", "USDJPY.m", "USDJPY.e",
            "BTCUSD", "BTCUSD.m", "BTCUSD.e",
            "ETHUSD", "ETHUSD.m", "ETHUSD.e",
            "BTCJPY", "BTCJPY.m",
            "ETHBTC",
        ]

    def get_available_symbols(self, filter_type: str = "all") -> List[str]:
        all_symbols = self._symbols_cache
        
        if filter_type == "forex":
            return [s for s in all_symbols if any(x in s for x in ["EUR", "GBP", "USD", "JPY", "AUD", "NZD", "CHF", "CAD"])]
        elif filter_type == "metals":
            return [s for s in all_symbols if "XAU" in s or "XAG" in s]
        elif filter_type == "crypto":
            return [s for s in all_symbols if any(x in s for x in ["BTC", "ETH", "BNB", "XRP", "ADA", "SOL"])]
        
        return all_symbols

    def get_symbol_info(self, symbol: str) -> Optional[MT5SymbolInfo]:
        if not self._connected:
            return None

        try:
            if self._mt5:
                tick = self._mt5.symbol_info_tick(symbol)
                info = self._mt5.symbol_info(symbol)
                
                if tick and info:
                    return MT5SymbolInfo(
                        name=symbol,
                        description=info.description,
                        bid=tick.bid,
                        ask=tick.ask,
                        spread=int(info.spread),
                        digits=info.digits,
                        min_lot=info.volume_min,
                        max_lot=info.volume_max,
                        lot_step=info.volume_step,
                        tick_value=info.trade_tick_value,
                        tick_size=info.trade_tick_size
                    )
            else:
                return self._get_simulation_symbol_info(symbol)
                
        except Exception as e:
            logger.error(f"Failed to get symbol info for {symbol}: {e}")
        
        return None

    def _get_simulation_symbol_info(self, symbol: str) -> MT5SymbolInfo:
        base_prices = {
            "XAUUSD": 2050.0, "EURUSD": 1.0850, "GBPUSD": 1.2650,
            "USDJPY": 148.50, "BTCUSD": 42500.0, "ETHUSD": 2250.0
        }
        price = base_prices.get(symbol, 1000.0)
        
        return MT5SymbolInfo(
            name=symbol,
            description=f"{symbol} Symbol",
            bid=price,
            ask=price + price * 0.0002,
            spread=20 if "XAU" not in symbol else 30,
            digits=2 if price > 100 else 5,
            min_lot=0.01,
            max_lot=100.0,
            lot_step=0.01,
            tick_value=price * 0.0001,
            tick_size=0.00001
        )

    def get_account_info(self) -> Optional[MT5AccountInfo]:
        if self._connected:
            self._account_info = self._get_account_info()
        return self._account_info

    def get_current_prices(self, symbols: List[str]) -> Dict[str, Dict[str, float]]:
        prices = {}
        
        for symbol in symbols:
            info = self.get_symbol_info(symbol)
            if info:
                prices[symbol] = {
                    "bid": info.bid,
                    "ask": info.ask,
                    "spread": info.spread
                }
        
        return prices

    def place_order(self, symbol: str, order_type: str, volume: float,
                    price: float = 0.0, sl: float = 0.0, tp: float = 0.0,
                    comment: str = "") -> Tuple[bool, str, int]:
        if not self._connected:
            return False, "未连接", 0

        try:
            if self._mt5:
                if order_type == "buy":
                    order_type_enum = self._mt5.ORDER_TYPE_BUY
                elif order_type == "sell":
                    order_type_enum = self._mt5.ORDER_TYPE_SELL
                elif order_type == "buy_limit":
                    order_type_enum = self._mt5.ORDER_TYPE_BUY_LIMIT
                elif order_type == "sell_limit":
                    order_type_enum = self._mt5.ORDER_TYPE_SELL_LIMIT
                else:
                    return False, f"未知订单类型: {order_type}", 0

                request = {
                    "action": self._mt5.TRADE_ACTION_DEAL,
                    "symbol": symbol,
                    "volume": volume,
                    "type": order_type_enum,
                    "price": price,
                    "sl": sl,
                    "tp": tp,
                    "comment": comment,
                    "type_filling": self._mt5.ORDER_FILLING_IOC,
                }

                result = self._mt5.order_send(request)
                
                if result.retcode == self._mt5.TRADE_RETCODE_DONE:
                    return True, "订单成功", result.order
                else:
                    return False, f"订单失败: {result.comment}", 0
            else:
                return True, f"模拟订单: {order_type} {symbol} {volume}", 999999

        except Exception as e:
            logger.error(f"Order failed: {e}")
            return False, str(e), 0

    def close_order(self, ticket: int, volume: float) -> Tuple[bool, str]:
        if not self._connected or not self._mt5:
            return False, "未连接"

        try:
            positions = self._mt5.positions_get(ticket=ticket)
            if positions:
                pos = positions[0]
                symbol = pos.symbol
                order_type = self._mt5.ORDER_TYPE_SELL if pos.type == self._mt5.ORDER_TYPE_BUY else self._mt5.ORDER_TYPE_BUY
                
                request = {
                    "action": self._mt5.TRADE_ACTION_DEAL,
                    "symbol": symbol,
                    "volume": volume,
                    "type": order_type,
                    "position": ticket,
                    "price": pos.price_current,
                    "type_filling": self._mt5.ORDER_FILLING_IOC,
                }
                
                result = self._mt5.order_send(request)
                
                if result.retcode == self._mt5.TRADE_RETCODE_DONE:
                    return True, "平仓成功"
                else:
                    return False, f"平仓失败: {result.comment}"
            
            return False, "未找到持仓"
            
        except Exception as e:
            logger.error(f"Close order failed: {e}")
            return False, str(e)

    def get_positions(self) -> List[Dict]:
        if not self._connected:
            return []

        try:
            if self._mt5:
                positions = self._mt5.positions_get()
                return [
                    {
                        "ticket": p.ticket,
                        "symbol": p.symbol,
                        "type": "buy" if p.type == self._mt5.ORDER_TYPE_BUY else "sell",
                        "volume": p.volume,
                        "price": p.price_open,
                        "current_price": p.price_current,
                        "profit": p.profit,
                        "comment": p.comment
                    }
                    for p in positions
                ]
            else:
                return self._get_simulation_positions()
                
        except Exception as e:
            logger.error(f"Failed to get positions: {e}")
            return []

    def _get_simulation_positions(self) -> List[Dict]:
        return [
            {
                "ticket": 12345,
                "symbol": "XAUUSD",
                "type": "buy",
                "volume": 0.1,
                "price": 2045.0,
                "current_price": 2050.0,
                "profit": 50.0,
                "comment": "Simulated"
            }
        ]

    def disconnect(self):
        if self._mt5:
            self._mt5.shutdown()
        self._connected = False
        self._mt5 = None
        logger.info("MT5 disconnected")
