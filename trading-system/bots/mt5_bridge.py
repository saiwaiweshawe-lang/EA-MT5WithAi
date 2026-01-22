# MT5 桥接模块
# 用于与MetaTrader 5通信的Python接口

import MetaTrader5 as mt5
import logging
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class MT5Bridge:
    """MT5桥接类"""

    def __init__(self, config: Dict):
        self.config = config
        self.connected = False
        self.account = config.get("login", 0)
        self.password = config.get("password", "")
        self.server = config.get("server", "")
        self.path = config.get("path", "")
        self._initialize()

    def _initialize(self):
        """初始化MT5连接"""
        if not mt5.initialize():
            logger.error(f"MT5初始化失败: {mt5.last_error()}")
            return

        # 如果提供了登录信息，尝试登录
        if self.account and self.password and self.server:
            if mt5.login(self.account, self.password, self.server, self.path):
                self.connected = True
                logger.info(f"MT5登录成功: {self.account}@{self.server}")
            else:
                logger.error(f"MT5登录失败: {mt5.last_error()}")
        else:
            self.connected = True
            logger.info("MT5已初始化 (使用已登录账户)")

    def get_status(self) -> Dict:
        """获取MT5状态"""
        if not self.connected:
            return {
                "connected": False,
                "account": "N/A",
                "balance": "N/A"
            }

        account_info = mt5.account_info()
        if account_info is None:
            return {
                "connected": True,
                "account": "Unknown",
                "balance": "N/A"
            }

        return {
            "connected": True,
            "account": account_info.login,
            "balance": account_info.balance,
            "equity": account_info.equity,
            "margin": account_info.margin,
            "currency": account_info.currency
        }

    def get_balance(self) -> float:
        """获取账户余额"""
        account_info = mt5.account_info()
        if account_info:
            return account_info.balance
        return 0.0

    def get_positions(self, symbol: Optional[str] = None) -> List[Dict]:
        """获取持仓信息"""
        positions = mt5.positions_get(symbol=symbol)
        if positions is None:
            return []

        result = []
        for pos in positions:
            result.append({
                "ticket": pos.ticket,
                "symbol": pos.symbol,
                "type": "买入" if pos.type == mt5.POSITION_TYPE_BUY else "卖出",
                "volume": pos.volume,
                "price": pos.price_open,
                "sl": pos.sl,
                "tp": pos.tp,
                "profit": pos.profit,
                "time": datetime.fromtimestamp(pos.time).strftime('%Y-%m-%d %H:%M:%S')
            })

        return result

    def get_symbol_info(self, symbol: str) -> Optional[Dict]:
        """获取品种信息"""
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            return None

        return {
            "symbol": symbol_info.name,
            "bid": symbol_info.bid,
            "ask": symbol_info.ask,
            "point": symbol_info.point,
            "digits": symbol_info.digits,
            "trade_contract_size": symbol_info.trade_contract_size,
            "volume_min": symbol_info.volume_min,
            "volume_max": symbol_info.volume_max,
            "volume_step": symbol_info.volume_step
        }

    def execute_trade(self,
                     symbol: str,
                     trade_type: str,
                     volume: float,
                     price: Optional[float] = None,
                     sl: Optional[float] = None,
                     tp: Optional[float] = None,
                     comment: str = "TG Bot") -> Dict:
        """
        执行交易

        参数:
            symbol: 交易品种 (如: XAUUSD, EURUSD)
            trade_type: 交易类型 ("buy" 或 "sell")
            volume: 交易数量
            price: 价格 (None表示市价)
            sl: 止损价格
            tp: 止盈价格
            comment: 注释

        返回:
            交易结果
        """
        if not self.connected:
            return {"success": False, "message": "MT5未连接"}

        # 获取品种信息
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            return {"success": False, "message": f"品种 {symbol} 不存在"}

        # 确保品种可见
        if not symbol_info.visible:
            if not mt5.symbol_select(symbol, True):
                return {"success": False, "message": f"无法选择品种 {symbol}"}

        # 确定交易类型
        if trade_type.lower() in ["buy", "long"]:
            order_type = mt5.ORDER_TYPE_BUY
            action = mt5.TRADE_ACTION_DEAL
            price = price or mt5.symbol_info_tick(symbol).ask
        elif trade_type.lower() in ["sell", "short"]:
            order_type = mt5.ORDER_TYPE_SELL
            action = mt5.TRADE_ACTION_DEAL
            price = price or mt5.symbol_info_tick(symbol).bid
        else:
            return {"success": False, "message": "无效的交易类型"}

        # 准备交易请求
        request = {
            "action": action,
            "symbol": symbol,
            "volume": volume,
            "type": order_type,
            "price": price,
            "deviation": 20,
            "magic": 234000,
            "comment": comment,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        if sl is not None:
            request["sl"] = sl
        if tp is not None:
            request["tp"] = tp

        # 发送订单
        result = mt5.order_send(request)

        if result is None:
            return {"success": False, "message": "订单发送失败"}

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            return {
                "success": False,
                "message": f"订单失败 (代码: {result.retcode})",
                "error": result.comment
            }

        return {
            "success": True,
            "message": "订单执行成功",
            "ticket": result.order,
            "volume": result.volume,
            "price": result.price
        }

    def close_position(self, ticket: int, volume: Optional[float] = None) -> Dict:
        """平仓指定订单"""
        position = mt5.positions_get(ticket=ticket)
        if not position:
            return {"success": False, "message": "未找到该持仓"}

        position = position[0]
        volume_to_close = volume if volume else position.volume

        # 确定平仓方向
        if position.type == mt5.POSITION_TYPE_BUY:
            order_type = mt5.ORDER_TYPE_SELL
            price = mt5.symbol_info_tick(position.symbol).bid
        else:
            order_type = mt5.ORDER_TYPE_BUY
            price = mt5.symbol_info_tick(position.symbol).ask

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": position.symbol,
            "volume": volume_to_close,
            "type": order_type,
            "position": ticket,
            "price": price,
            "deviation": 20,
            "magic": 234000,
            "comment": "Close by TG Bot",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            return {
                "success": False,
                "message": f"平仓失败 (代码: {result.retcode})",
                "error": result.comment
            }

        return {"success": True, "message": "平仓成功"}

    def close_all_positions(self, symbol: Optional[str] = None) -> Dict:
        """平所有仓"""
        positions = mt5.positions_get(symbol=symbol)
        if not positions:
            return {"success": True, "message": "无持仓需平仓"}

        success_count = 0
        failed_count = 0

        for pos in positions:
            result = self.close_position(pos.ticket)
            if result["success"]:
                success_count += 1
            else:
                failed_count += 1

        return {
            "success": failed_count == 0,
            "message": f"平仓完成: 成功 {success_count}, 失败 {failed_count}"
        }

    def modify_position(self,
                       ticket: int,
                       sl: Optional[float] = None,
                       tp: Optional[float] = None) -> Dict:
        """修改持仓止损止盈"""
        if sl is None and tp is None:
            return {"success": False, "message": "未提供新的SL/TP"}

        position = mt5.positions_get(ticket=ticket)
        if not position:
            return {"success": False, "message": "未找到该持仓"}

        position = position[0]

        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": ticket,
            "symbol": position.symbol,
            "sl": sl if sl is not None else position.sl,
            "tp": tp if tp is not None else position.tp,
        }

        result = mt5.order_send(request)

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            return {
                "success": False,
                "message": f"修改失败 (代码: {result.retcode})",
                "error": result.comment
            }

        return {"success": True, "message": "修改成功"}

    def get_history(self,
                   symbol: Optional[str] = None,
                   from_date: Optional[datetime] = None,
                   to_date: Optional[datetime] = None) -> List[Dict]:
        """获取历史订单"""
        if from_date is None:
            from_date = datetime(1970, 1, 1)
        if to_date is None:
            to_date = datetime.now()

        history = mt5.history_deals_get(from_date, to_date, symbol=symbol)
        if history is None:
            return []

        result = []
        for deal in history:
            result.append({
                "ticket": deal.ticket,
                "symbol": deal.symbol,
                "type": "买入" if deal.type == mt5.DEAL_TYPE_BUY else "卖出",
                "volume": deal.volume,
                "price": deal.price,
                "commission": deal.commission,
                "swap": deal.swap,
                "profit": deal.profit,
                "time": datetime.fromtimestamp(deal.time).strftime('%Y-%m-%d %H:%M:%S')
            })

        return result

    def get_rates(self,
                 symbol: str,
                 timeframe: int = mt5.TIMEFRAME_H1,
                 count: int = 100) -> List[Dict]:
        """获取K线数据"""
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
        if rates is None:
            return []

        result = []
        for rate in rates:
            result.append({
                "time": datetime.fromtimestamp(rate['time']).strftime('%Y-%m-%d %H:%M:%S'),
                "open": rate['open'],
                "high": rate['high'],
                "low": rate['low'],
                "close": rate['close'],
                "volume": rate['tick_volume']
            })

        return result

    def shutdown(self):
        """关闭MT5连接"""
        mt5.shutdown()
        self.connected = False
        logger.info("MT5连接已关闭")


# EA策略类
class GoldTradingStrategy:
    """黄金交易策略"""

    def __init__(self, mt5_bridge: MT5Bridge, config: Dict):
        self.mt5 = mt5_bridge
        self.config = config
        self.symbol = config.get("symbol", "XAUUSD")
        self.lot_size = config.get("lot_size", 0.01)
        self.timeframe = config.get("timeframe", mt5.TIMEFRAME_H1)
        self.stop_loss_pips = config.get("stop_loss_pips", 100)
        self.take_profit_pips = config.get("take_profit_pips", 200)

    def analyze(self) -> Dict:
        """分析市场并生成交易信号"""
        rates = self.mt5.get_rates(self.symbol, self.timeframe, 50)
        if len(rates) < 20:
            return {"signal": "hold", "reason": "数据不足"}

        # 简单策略: 移动平均线
        closes = [r['close'] for r in rates]
        ma5 = sum(closes[-5:]) / 5
        ma20 = sum(closes[-20:]) / 20

        current_price = closes[-1]

        signal = "hold"
        reason = ""

        if ma5 > ma20 and current_price > ma5:
            signal = "buy"
            reason = "MA5上穿MA20且价格在MA5之上"
        elif ma5 < ma20 and current_price < ma5:
            signal = "sell"
            reason = "MA5下穿MA20且价格在MA5之下"
        else:
            reason = f"MA5={ma5:.2f}, MA20={ma20:.2f}"

        return {
            "signal": signal,
            "reason": reason,
            "price": current_price,
            "ma5": ma5,
            "ma20": ma20
        }

    def execute(self) -> Dict:
        """执行策略"""
        analysis = self.analyze()

        if analysis["signal"] == "hold":
            return {"action": "hold", "message": analysis["reason"]}

        # 获取当前持仓
        positions = self.mt5.get_positions(self.symbol)

        # 检查是否已有该方向的持仓
        for pos in positions:
            pos_type = "buy" if "买入" in pos["type"] else "sell"
            if pos_type == analysis["signal"]:
                return {"action": "hold", "message": "已有同方向持仓"}

        # 获取品种信息计算SL/TP
        symbol_info = self.mt5.get_symbol_info(self.symbol)
        if not symbol_info:
            return {"action": "error", "message": "无法获取品种信息"}

        pip = symbol_info["point"] * 10

        sl = None
        tp = None

        if analysis["signal"] == "buy":
            sl = analysis["price"] - (self.stop_loss_pips * pip)
            tp = analysis["price"] + (self.take_profit_pips * pip)
        else:
            sl = analysis["price"] + (self.stop_loss_pips * pip)
            tp = analysis["price"] - (self.take_profit_pips * pip)

        result = self.mt5.execute_trade(
            self.symbol,
            analysis["signal"],
            self.lot_size,
            None,  # 市价
            sl,
            tp,
            "Auto Gold EA"
        )

        return {
            "action": "trade",
            "signal": analysis["signal"],
            "result": result
        }


class EAManager:
    """EA管理器"""

    def __init__(self, config_path: str):
        self.config = self._load_config(config_path)
        self.mt5 = MT5Bridge(self.config.get("mt5", {}))
        self.strategies = {}

        # 初始化策略
        if "gold" in self.config.get("strategies", {}):
            self.strategies["gold"] = GoldTradingStrategy(
                self.mt5,
                self.config["strategies"]["gold"]
            )

    def _load_config(self, config_path: str) -> Dict:
        """加载配置"""
        import json
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            return {}

    def run_strategy(self, strategy_name: str) -> Dict:
        """运行指定策略"""
        if strategy_name not in self.strategies:
            return {"error": f"策略 {strategy_name} 不存在"}

        strategy = self.strategies[strategy_name]
        return strategy.execute()

    def run_all_strategies(self) -> Dict:
        """运行所有策略"""
        results = {}
        for name in self.strategies:
            results[name] = self.run_strategy(name)
        return results
