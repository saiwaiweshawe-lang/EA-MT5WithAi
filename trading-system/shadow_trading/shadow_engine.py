# 影子训练场功能
# 在虚拟环境中测试策略，不影响实盘

import os
import json
import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
import sqlite3

logger = logging.getLogger(__name__)


@dataclass
class ShadowTrade:
    """影子交易"""
    id: str
    symbol: str
    action: str  # buy/sell
    entry_price: float
    exit_price: Optional[float] = None
    volume: float = 0.01
    entry_time: Optional[str] = None
    exit_time: Optional[str] = None
    profit: float = 0.0
    strategy: str = ""
    parameters: Dict = None
    status: str = "open"  # open/closed

    def __post_init__(self):
        if self.parameters is None:
            self.parameters = {}
        if self.entry_time is None:
            self.entry_time = datetime.now().isoformat()


@dataclass
class ShadowPosition:
    """影子持仓"""
    trade: ShadowTrade
    stop_loss: float
    take_profit: float
    current_pnl: float = 0.0


class ShadowTradingEngine:
    """影子交易引擎"""

    def __init__(self, config: Dict):
        self.config = config
        self.enabled = config.get("enabled", True)
        self.simulation_mode = config.get("simulation_mode", "paper")
        self.db_path = config.get("db_path", "shadow_trading/shadow.db")
        self.initial_balance = config.get("initial_balance", 10000)
        self.spread = config.get("spread", 0.0002)  # 点差
        self.commission = config.get("commission", 0.0005)  # 手续费

        Path(os.path.dirname(self.db_path)).mkdir(parents=True, exist_ok=True)
        self._init_database()

        self.balance = self.initial_balance
        self.equity = self.initial_balance
        self.positions: Dict[str, ShadowPosition] = {}
        self.trades: List[ShadowTrade] = []

    def _init_database(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS shadow_trades (
                id TEXT PRIMARY KEY,
                symbol TEXT NOT NULL,
                action TEXT NOT NULL,
                entry_price REAL NOT NULL,
                exit_price REAL,
                volume REAL,
                entry_time TEXT,
                exit_time TEXT,
                profit REAL,
                strategy TEXT,
                parameters TEXT,
                status TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS simulation_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy_name TEXT,
                parameters TEXT,
                start_time TEXT,
                end_time TEXT,
                initial_balance REAL,
                final_balance REAL,
                total_trades INTEGER,
                winning_trades INTEGER,
                losing_trades INTEGER,
                win_rate REAL,
                total_profit REAL,
                total_loss REAL,
                max_drawdown REAL,
                sharpe_ratio REAL,
                profit_factor REAL
            )
        """)

        conn.commit()
        conn.close()

    def execute_trade(self,
                    symbol: str,
                    action: str,
                    price: float,
                    volume: float,
                    strategy: str,
                    parameters: Dict,
                    stop_loss_pips: Optional[float] = None,
                    take_profit_pips: Optional[float] = None) -> ShadowTrade:
        """执行影子交易"""
        trade_id = f"{symbol}_{action}_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"

        # 计算止损止盈价格
        stop_loss = None
        take_profit = None

        pip_size = 0.0001  # 假设1点=0.0001

        if stop_loss_pips:
            if action.lower() in ["buy", "long"]:
                stop_loss = price - stop_loss_pips * pip_size
            else:
                stop_loss = price + stop_loss_pips * pip_size

        if take_profit_pips:
            if action.lower() in ["buy", "long"]:
                take_profit = price + take_profit_pips * pip_size
            else:
                take_profit = price - take_profit_pips * pip_size

        trade = ShadowTrade(
            id=trade_id,
            symbol=symbol,
            action=action,
            entry_price=price,
            volume=volume,
            strategy=strategy,
            parameters=parameters
        )

        # 创建影子持仓
        self.positions[trade_id] = ShadowPosition(
            trade=trade,
            stop_loss=stop_loss,
            take_profit=take_profit
        )

        self.trades.append(trade)

        # 保存到数据库
        self._save_trade(trade)

        logger.info(f"影子交易开仓: {symbol} {action} @ {price}")
        return trade

    def update_positions(self, current_prices: Dict[str, float]):
        """更新持仓状态"""
        closed_trades = []

        for trade_id, position in list(self.positions.items()):
            trade = position.trade
            current_price = current_prices.get(trade.symbol)

            if current_price is None:
                continue

            # 计算浮动盈亏
            if trade.action.lower() in ["buy", "long"]:
                pnl = (current_price - trade.entry_price) * trade.volume * 100000
            else:
                pnl = (trade.entry_price - current_price) * trade.volume * 100000

            position.current_pnl = pnl

            # 检查止损止盈
            close_trade = False
            close_reason = ""

            if position.stop_loss:
                if trade.action.lower() in ["buy", "long"]:
                    if current_price <= position.stop_loss:
                        close_trade = True
                        close_reason = "stop_loss"
                else:
                    if current_price >= position.stop_loss:
                        close_trade = True
                        close_reason = "stop_loss"

            if position.take_profit:
                if trade.action.lower() in ["buy", "long"]:
                    if current_price >= position.take_profit:
                        close_trade = True
                        close_reason = "take_profit"
                else:
                    if current_price <= position.take_profit:
                        close_trade = True
                        close_reason = "take_profit"

            if close_trade:
                self.close_trade(trade_id, current_price, close_reason)
                closed_trades.append(trade_id)

        # 移除已平仓的交易
        for trade_id in closed_trades:
            self.positions.pop(trade_id, None)

        # 计算总权益
        self.equity = self.balance + sum(p.current_pnl for p in self.positions.values())

    def close_trade(self, trade_id: str, exit_price: float, reason: str = "manual"):
        """平仓"""
        if trade_id not in self.positions:
            logger.warning(f"交易不存在: {trade_id}")
            return

        position = self.positions[trade_id]
        trade = position.trade

        # 计算盈亏
        if trade.action.lower() in ["buy", "long"]:
            gross_profit = (exit_price - trade.entry_price) * trade.volume * 100000
        else:
            gross_profit = (trade.entry_price - exit_price) * trade.volume * 100000

        # 扣除手续费
        commission = trade.entry_price * trade.volume * 0.01 * self.commission * 2
        net_profit = gross_profit - commission

        # 更新交易
        trade.exit_price = exit_price
        trade.exit_time = datetime.now().isoformat()
        trade.profit = net_profit
        trade.status = "closed"

        # 更新余额
        self.balance += net_profit

        # 保存到数据库
        self._update_trade(trade)

        logger.info(f"影子交易平仓: {trade.symbol} {trade.action} @ {exit_price}, "
                   f"盈亏: {net_profit:.2f}, 原因: {reason}")

    def get_performance(self) -> Dict:
        """获取影子交易表现"""
        closed_trades = [t for t in self.trades if t.status == "closed"]

        if not closed_trades:
            return {
                "total_trades": 0,
                "win_rate": 0,
                "net_profit": 0
            }

        total_trades = len(closed_trades)
        winning_trades = sum(1 for t in closed_trades if t.profit > 0)
        losing_trades = total_trades - winning_trades
        net_profit = sum(t.profit for t in closed_trades)

        total_profit = sum(t.profit for t in closed_trades if t.profit > 0)
        total_loss = abs(sum(t.profit for t in closed_trades if t.profit < 0))

        win_rate = winning_trades / total_trades if total_trades > 0 else 0
        profit_factor = total_profit / total_loss if total_loss > 0 else float('inf')

        # 计算最大回撤
        equity_curve = [self.initial_balance]
        for trade in closed_trades:
            equity_curve.append(equity_curve[-1] + trade.profit)

        max_drawdown = 0
        peak = equity_curve[0]

        for value in equity_curve:
            if value > peak:
                peak = value
            else:
                drawdown = (peak - value) / peak
                if drawdown > max_drawdown:
                    max_drawdown = drawdown

        return {
            "balance": self.balance,
            "equity": self.equity,
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "win_rate": win_rate,
            "net_profit": net_profit,
            "total_profit": total_profit,
            "total_loss": total_loss,
            "profit_factor": profit_factor,
            "max_drawdown": max_drawdown,
            "return_pct": (net_profit / self.initial_balance) * 100
        }

    def _save_trade(self, trade: ShadowTrade):
        """保存交易到数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO shadow_trades (
                    id, symbol, action, entry_price, exit_price, volume,
                    entry_time, exit_time, profit, strategy, parameters, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trade.id, trade.symbol, trade.action, trade.entry_price,
                trade.exit_price, trade.volume, trade.entry_time, trade.exit_time,
                trade.profit, trade.strategy, json.dumps(trade.parameters),
                trade.status
            ))

            conn.commit()
        except Exception as e:
            logger.error(f"保存影子交易失败: {e}")
            conn.rollback()
        finally:
            conn.close()

    def _update_trade(self, trade: ShadowTrade):
        """更新交易到数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                UPDATE shadow_trades
                SET exit_price=?, exit_time=?, profit=?, status=?
                WHERE id=?
            """, (trade.exit_price, trade.exit_time, trade.profit, trade.status, trade.id))

            conn.commit()
        except Exception as e:
            logger.error(f"更新影子交易失败: {e}")
            conn.rollback()
        finally:
            conn.close()

    def save_simulation_result(self, strategy_name: str, parameters: Dict):
        """保存模拟结果"""
        performance = self.get_performance()

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO simulation_results (
                    strategy_name, parameters, start_time, end_time,
                    initial_balance, final_balance, total_trades, winning_trades,
                    losing_trades, win_rate, total_profit, total_loss,
                    max_drawdown, profit_factor
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                strategy_name, json.dumps(parameters),
                self.trades[0].entry_time if self.trades else datetime.now().isoformat(),
                datetime.now().isoformat(),
                self.initial_balance, performance["balance"],
                performance["total_trades"], performance["winning_trades"],
                performance["losing_trades"], performance["win_rate"],
                performance["total_profit"], performance["total_loss"],
                performance["max_drawdown"], performance["profit_factor"]
            ))

            conn.commit()
            logger.info(f"模拟结果已保存: {strategy_name}")
        except Exception as e:
            logger.error(f"保存模拟结果失败: {e}")
            conn.rollback()
        finally:
            conn.close()

    def reset(self):
        """重置影子账户"""
        self.balance = self.initial_balance
        self.equity = self.initial_balance
        self.positions.clear()
        self.trades.clear()
        logger.info("影子账户已重置")


class BacktestEngine:
    """回测引擎"""

    def __init__(self, config: Dict):
        self.config = config
        self.initial_balance = config.get("initial_balance", 10000)
        self.spread = config.get("spread", 0.0002)
        self.commission = config.get("commission", 0.0005)

    def run_backtest(self,
                    price_data: pd.DataFrame,
                    strategy_func,
                    parameters: Dict) -> Dict:
        """运行回测"""
        logger.info(f"开始回测，数据点数: {len(price_data)}")

        balance = self.initial_balance
        equity_curve = [balance]
        trades = []
        position = None

        for i in range(len(price_data)):
            current_data = price_data.iloc[i]
            price = current_data['close']
            time = current_data.get('time', i)

            # 计算指标（历史数据）
            if i < 100:
                continue

            # 获取策略信号
            signal = strategy_func(price_data.iloc[:i+1], parameters)

            # 执行交易
            if position is None:
                if signal['action'] != 'hold':
                    position = {
                        'action': signal['action'],
                        'entry_price': price,
                        'volume': signal.get('volume', 0.01),
                        'stop_loss': signal.get('stop_loss'),
                        'take_profit': signal.get('take_profit'),
                        'entry_time': time
                    }
            else:
                # 检查止损止盈
                close = False
                close_reason = ''

                if position['action'] == 'buy':
                    if position['stop_loss'] and price <= position['stop_loss']:
                        close = True
                        close_reason = 'stop_loss'
                    elif position['take_profit'] and price >= position['take_profit']:
                        close = True
                        close_reason = 'take_profit'
                else:
                    if position['stop_loss'] and price >= position['stop_loss']:
                        close = True
                        close_reason = 'stop_loss'
                    elif position['take_profit'] and price <= position['take_profit']:
                        close = True
                        close_reason = 'take_profit'

                if close:
                    # 计算盈亏
                    if position['action'] == 'buy':
                        gross_profit = (price - position['entry_price']) * position['volume'] * 100000
                    else:
                        gross_profit = (position['entry_price'] - price) * position['volume'] * 100000

                    commission = price * position['volume'] * 0.01 * self.commission * 2
                    net_profit = gross_profit - commission

                    balance += net_profit

                    trades.append({
                        'entry_price': position['entry_price'],
                        'exit_price': price,
                        'action': position['action'],
                        'volume': position['volume'],
                        'profit': net_profit,
                        'entry_time': position['entry_time'],
                        'exit_time': time,
                        'reason': close_reason
                    })

                    position = None

            equity_curve.append(balance)

        # 计算性能指标
        performance = self._calculate_performance_metrics(equity_curve, trades)

        logger.info(f"回测完成: 总交易={performance['total_trades']}, "
                   f"胜率={performance['win_rate']*100:.1f}%, "
                   f"净盈利={performance['net_profit']:.2f}")

        return {
            'performance': performance,
            'equity_curve': equity_curve,
            'trades': trades
        }

    def _calculate_performance_metrics(self,
                                     equity_curve: List[float],
                                     trades: List[Dict]) -> Dict:
        """计算性能指标"""
        total_trades = len(trades)

        if total_trades == 0:
            return {
                'total_trades': 0,
                'win_rate': 0,
                'net_profit': 0
            }

        winning_trades = sum(1 for t in trades if t['profit'] > 0)
        losing_trades = total_trades - winning_trades
        net_profit = sum(t['profit'] for t in trades)

        total_profit = sum(t['profit'] for t in trades if t['profit'] > 0)
        total_loss = abs(sum(t['profit'] for t in trades if t['profit'] < 0))

        win_rate = winning_trades / total_trades if total_trades > 0 else 0
        profit_factor = total_profit / total_loss if total_loss > 0 else float('inf')

        # 最大回撤
        max_drawdown = 0
        peak = equity_curve[0]

        for value in equity_curve:
            if value > peak:
                peak = value
            else:
                drawdown = (peak - value) / peak
                if drawdown > max_drawdown:
                    max_drawdown = drawdown

        # 夏普比率（简化计算）
        returns = [equity_curve[i] / equity_curve[i-1] - 1 for i in range(1, len(equity_curve))]
        sharpe_ratio = np.mean(returns) / np.std(returns) * np.sqrt(252) if np.std(returns) > 0 else 0

        return {
            'initial_balance': self.initial_balance,
            'final_balance': equity_curve[-1],
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': win_rate,
            'net_profit': net_profit,
            'total_profit': total_profit,
            'total_loss': total_loss,
            'profit_factor': profit_factor,
            'max_drawdown': max_drawdown,
            'sharpe_ratio': sharpe_ratio,
            'return_pct': (net_profit / self.initial_balance) * 100
        }


def create_shadow_engine(config: Dict) -> ShadowTradingEngine:
    """创建影子交易引擎"""
    return ShadowTradingEngine(config)


def create_backtest_engine(config: Dict) -> BacktestEngine:
    """创建回测引擎"""
    return BacktestEngine(config)


if __name__ == "__main__":
    # 测试代码
    config = {
        "enabled": True,
        "initial_balance": 10000,
        "db_path": "shadow_trading/shadow.db"
    }

    engine = ShadowTradingEngine(config)

    # 模拟一些交易
    current_prices = {"XAUUSD": 2025.50}

    # 开多仓
    engine.execute_trade(
        symbol="XAUUSD",
        action="buy",
        price=2025.50,
        volume=0.01,
        strategy="test",
        parameters={"rsi": 25},
        stop_loss_pips=200,
        take_profit_pips=400
    )

    # 更新持仓
    engine.update_positions(current_prices)

    # 模拟价格变化并平仓
    current_prices["XAUUSD"] = 2029.50
    engine.update_positions(current_prices)

    # 查看表现
    performance = engine.get_performance()
    print(f"影子交易表现: {performance}")
