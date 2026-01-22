#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
交易策略回测引擎
用于在历史数据上测试交易策略
"""

import os
import sys
import json
import logging
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from collections import defaultdict

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

logger = logging.getLogger(__name__)


@dataclass
class Trade:
    """交易记录"""
    id: str
    symbol: str
    direction: str  # long, short
    entry_time: float
    entry_price: float
    exit_time: Optional[float] = None
    exit_price: Optional[float] = None
    quantity: float = 1.0
    commission: float = 0.0
    profit: float = 0.0
    profit_pct: float = 0.0
    status: str = "open"  # open, closed


@dataclass
class BacktestResult:
    """回测结果"""
    strategy_name: str
    symbol: str
    start_date: str
    end_date: str
    initial_capital: float
    final_capital: float
    total_return: float
    total_return_pct: float
    max_drawdown: float
    max_drawdown_pct: float
    sharpe_ratio: float
    win_rate: float
    profit_factor: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    avg_trade_profit: float
    avg_winning_trade: float
    avg_losing_trade: float
    max_consecutive_wins: int
    max_consecutive_losses: int
    trades: List[Trade] = None


class BacktestingEngine:
    """回测引擎"""

    def __init__(self, initial_capital: float = 100000.0,
                 commission_rate: float = 0.001):
        self.initial_capital = initial_capital
        self.commission_rate = commission_rate

        self.capital = initial_capital
        self.equity_curve = []
        self.trades: List[Trade] = []
        self.open_positions: Dict[str, Trade] = {}

        self.base_dir = Path(__file__).parent.parent
        self.data_dir = self.base_dir / "data" / "backtest"
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def load_historical_data(self, symbol: str, start_date: str,
                           end_date: str) -> pd.DataFrame:
        """
        加载历史数据

        Args:
            symbol: 交易品种
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)

        Returns:
            历史数据DataFrame (time, open, high, low, close, volume)
        """
        # 尝试从本地加载
        data_file = self.data_dir / f"{symbol}_{start_date}_{end_date}.csv"

        if data_file.exists():
            logger.info(f"从本地加载历史数据: {data_file}")
            df = pd.read_csv(data_file)
            df['time'] = pd.to_datetime(df['time'])
            return df

        # 否则生成模拟数据(实际应用中应该从MT5或其他数据源获取)
        logger.warning(f"历史数据不存在,生成模拟数据: {symbol}")
        df = self._generate_sample_data(symbol, start_date, end_date)

        # 保存到本地
        df.to_csv(data_file, index=False)

        return df

    def _generate_sample_data(self, symbol: str, start_date: str,
                             end_date: str) -> pd.DataFrame:
        """生成模拟历史数据"""
        start = pd.to_datetime(start_date)
        end = pd.to_datetime(end_date)

        # 生成时间序列(每小时)
        times = pd.date_range(start, end, freq='1H')

        # 生成价格数据(随机游走)
        initial_price = 50000.0  # 初始价格
        returns = np.random.normal(0.0001, 0.02, len(times))
        prices = initial_price * np.exp(np.cumsum(returns))

        # 生成OHLC数据
        data = []
        for i, (time, close) in enumerate(zip(times, prices)):
            # 生成合理的OHLC
            volatility = close * 0.01
            high = close + abs(np.random.normal(0, volatility))
            low = close - abs(np.random.normal(0, volatility))
            open_price = close + np.random.normal(0, volatility * 0.5)

            # 确保high >= low
            high = max(high, low, close, open_price)
            low = min(low, close, open_price)

            data.append({
                'time': time,
                'open': open_price,
                'high': high,
                'low': low,
                'close': close,
                'volume': np.random.randint(100, 10000)
            })

        df = pd.DataFrame(data)
        return df

    def run_backtest(self, strategy_func, symbol: str, start_date: str,
                    end_date: str, **strategy_params) -> BacktestResult:
        """
        运行回测

        Args:
            strategy_func: 策略函数,接收(df, params)返回信号
            symbol: 交易品种
            start_date: 开始日期
            end_date: 结束日期
            **strategy_params: 策略参数

        Returns:
            回测结果
        """
        logger.info(f"开始回测: {symbol} ({start_date} ~ {end_date})")

        # 重置状态
        self.capital = self.initial_capital
        self.equity_curve = []
        self.trades = []
        self.open_positions = {}

        # 加载历史数据
        df = self.load_historical_data(symbol, start_date, end_date)

        if df.empty:
            logger.error("历史数据为空")
            return None

        # 运行策略
        logger.info("运行策略...")
        signals = strategy_func(df, strategy_params)

        # 执行交易
        logger.info("执行交易...")
        for i in range(len(df)):
            row = df.iloc[i]
            timestamp = row['time'].timestamp()
            price = row['close']

            # 处理信号
            if i < len(signals):
                signal = signals[i]

                if signal == 1:  # 做多信号
                    self._open_position(symbol, 'long', timestamp, price)
                elif signal == -1:  # 做空信号
                    self._open_position(symbol, 'short', timestamp, price)
                elif signal == 0:  # 平仓信号
                    self._close_position(symbol, timestamp, price)

            # 更新权益曲线
            equity = self._calculate_equity(price)
            self.equity_curve.append({
                'time': timestamp,
                'equity': equity
            })

        # 平掉所有剩余持仓
        final_price = df.iloc[-1]['close']
        final_time = df.iloc[-1]['time'].timestamp()
        for symbol in list(self.open_positions.keys()):
            self._close_position(symbol, final_time, final_price)

        # 计算回测结果
        result = self._calculate_result(
            strategy_func.__name__, symbol, start_date, end_date
        )

        logger.info(f"回测完成: 总收益率={result.total_return_pct:.2f}%, "
                   f"夏普比率={result.sharpe_ratio:.2f}")

        return result

    def _open_position(self, symbol: str, direction: str,
                      timestamp: float, price: float):
        """开仓"""
        # 如果已有持仓,先平仓
        if symbol in self.open_positions:
            self._close_position(symbol, timestamp, price)

        # 计算交易数量(使用当前资金的一定比例)
        risk_pct = 0.95  # 使用95%的资金
        quantity = (self.capital * risk_pct) / price
        commission = quantity * price * self.commission_rate

        # 创建交易记录
        trade = Trade(
            id=f"{symbol}_{len(self.trades)}",
            symbol=symbol,
            direction=direction,
            entry_time=timestamp,
            entry_price=price,
            quantity=quantity,
            commission=commission
        )

        self.open_positions[symbol] = trade
        self.capital -= commission

        logger.debug(f"开仓: {direction} {symbol} @ {price:.2f}, "
                    f"数量={quantity:.4f}")

    def _close_position(self, symbol: str, timestamp: float, price: float):
        """平仓"""
        if symbol not in self.open_positions:
            return

        trade = self.open_positions.pop(symbol)

        # 计算盈亏
        commission = trade.quantity * price * self.commission_rate

        if trade.direction == 'long':
            profit = (price - trade.entry_price) * trade.quantity
        else:  # short
            profit = (trade.entry_price - price) * trade.quantity

        profit -= (trade.commission + commission)
        profit_pct = profit / (trade.entry_price * trade.quantity) * 100

        # 更新交易记录
        trade.exit_time = timestamp
        trade.exit_price = price
        trade.commission += commission
        trade.profit = profit
        trade.profit_pct = profit_pct
        trade.status = "closed"

        self.trades.append(trade)
        self.capital += profit

        logger.debug(f"平仓: {trade.direction} {symbol} @ {price:.2f}, "
                    f"盈亏={profit:.2f} ({profit_pct:.2f}%)")

    def _calculate_equity(self, current_price: float) -> float:
        """计算当前权益"""
        equity = self.capital

        # 加上未平仓位的浮动盈亏
        for trade in self.open_positions.values():
            if trade.direction == 'long':
                unrealized = (current_price - trade.entry_price) * trade.quantity
            else:
                unrealized = (trade.entry_price - current_price) * trade.quantity

            equity += unrealized

        return equity

    def _calculate_result(self, strategy_name: str, symbol: str,
                         start_date: str, end_date: str) -> BacktestResult:
        """计算回测结果"""
        final_capital = self.equity_curve[-1]['equity'] if self.equity_curve else self.initial_capital

        # 基本指标
        total_return = final_capital - self.initial_capital
        total_return_pct = (total_return / self.initial_capital) * 100

        # 最大回撤
        equity_values = [e['equity'] for e in self.equity_curve]
        max_drawdown, max_drawdown_pct = self._calculate_max_drawdown(equity_values)

        # 夏普比率
        sharpe_ratio = self._calculate_sharpe_ratio(equity_values)

        # 交易统计
        closed_trades = [t for t in self.trades if t.status == 'closed']
        winning_trades = [t for t in closed_trades if t.profit > 0]
        losing_trades = [t for t in closed_trades if t.profit <= 0]

        total_trades = len(closed_trades)
        num_winning = len(winning_trades)
        num_losing = len(losing_trades)

        win_rate = (num_winning / total_trades * 100) if total_trades > 0 else 0

        avg_trade_profit = np.mean([t.profit for t in closed_trades]) if closed_trades else 0
        avg_winning_trade = np.mean([t.profit for t in winning_trades]) if winning_trades else 0
        avg_losing_trade = np.mean([t.profit for t in losing_trades]) if losing_trades else 0

        # 盈利因子
        total_wins = sum(t.profit for t in winning_trades)
        total_losses = abs(sum(t.profit for t in losing_trades))
        profit_factor = (total_wins / total_losses) if total_losses > 0 else 0

        # 连续盈亏
        max_consecutive_wins, max_consecutive_losses = self._calculate_consecutive_trades(closed_trades)

        return BacktestResult(
            strategy_name=strategy_name,
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            initial_capital=self.initial_capital,
            final_capital=final_capital,
            total_return=total_return,
            total_return_pct=total_return_pct,
            max_drawdown=max_drawdown,
            max_drawdown_pct=max_drawdown_pct,
            sharpe_ratio=sharpe_ratio,
            win_rate=win_rate,
            profit_factor=profit_factor,
            total_trades=total_trades,
            winning_trades=num_winning,
            losing_trades=num_losing,
            avg_trade_profit=avg_trade_profit,
            avg_winning_trade=avg_winning_trade,
            avg_losing_trade=avg_losing_trade,
            max_consecutive_wins=max_consecutive_wins,
            max_consecutive_losses=max_consecutive_losses,
            trades=closed_trades
        )

    def _calculate_max_drawdown(self, equity_values: List[float]) -> Tuple[float, float]:
        """计算最大回撤"""
        if not equity_values:
            return 0, 0

        peak = equity_values[0]
        max_dd = 0
        max_dd_pct = 0

        for equity in equity_values:
            if equity > peak:
                peak = equity

            dd = peak - equity
            dd_pct = (dd / peak * 100) if peak > 0 else 0

            if dd > max_dd:
                max_dd = dd
                max_dd_pct = dd_pct

        return max_dd, max_dd_pct

    def _calculate_sharpe_ratio(self, equity_values: List[float],
                               risk_free_rate: float = 0.02) -> float:
        """计算夏普比率"""
        if len(equity_values) < 2:
            return 0

        # 计算收益率
        returns = np.diff(equity_values) / equity_values[:-1]

        if len(returns) == 0:
            return 0

        # 年化收益率
        avg_return = np.mean(returns) * 252 * 24  # 假设每小时数据
        std_return = np.std(returns) * np.sqrt(252 * 24)

        if std_return == 0:
            return 0

        sharpe = (avg_return - risk_free_rate) / std_return
        return sharpe

    def _calculate_consecutive_trades(self, trades: List[Trade]) -> Tuple[int, int]:
        """计算最大连续盈亏次数"""
        if not trades:
            return 0, 0

        max_wins = 0
        max_losses = 0
        current_wins = 0
        current_losses = 0

        for trade in trades:
            if trade.profit > 0:
                current_wins += 1
                current_losses = 0
                max_wins = max(max_wins, current_wins)
            else:
                current_losses += 1
                current_wins = 0
                max_losses = max(max_losses, current_losses)

        return max_wins, max_losses

    def generate_report(self, result: BacktestResult, output_path: str = None) -> str:
        """
        生成回测报告

        Args:
            result: 回测结果
            output_path: 输出路径(可选)

        Returns:
            报告文本
        """
        report = []
        report.append("=" * 80)
        report.append(f"回测报告 - {result.strategy_name}")
        report.append("=" * 80)
        report.append("")

        # 基本信息
        report.append("## 基本信息")
        report.append(f"交易品种: {result.symbol}")
        report.append(f"回测区间: {result.start_date} ~ {result.end_date}")
        report.append(f"初始资金: ${result.initial_capital:,.2f}")
        report.append("")

        # 收益指标
        report.append("## 收益指标")
        report.append(f"最终资金: ${result.final_capital:,.2f}")
        report.append(f"总收益: ${result.total_return:,.2f}")
        report.append(f"收益率: {result.total_return_pct:.2f}%")
        report.append(f"最大回撤: ${result.max_drawdown:,.2f} ({result.max_drawdown_pct:.2f}%)")
        report.append(f"夏普比率: {result.sharpe_ratio:.2f}")
        report.append("")

        # 交易统计
        report.append("## 交易统计")
        report.append(f"总交易次数: {result.total_trades}")
        report.append(f"盈利交易: {result.winning_trades} ({result.win_rate:.2f}%)")
        report.append(f"亏损交易: {result.losing_trades}")
        report.append(f"盈利因子: {result.profit_factor:.2f}")
        report.append("")

        report.append("## 交易表现")
        report.append(f"平均每笔交易: ${result.avg_trade_profit:,.2f}")
        report.append(f"平均盈利交易: ${result.avg_winning_trade:,.2f}")
        report.append(f"平均亏损交易: ${result.avg_losing_trade:,.2f}")
        report.append(f"最大连续盈利: {result.max_consecutive_wins}")
        report.append(f"最大连续亏损: {result.max_consecutive_losses}")
        report.append("")

        # 近期交易
        if result.trades:
            report.append("## 最近10笔交易")
            for trade in result.trades[-10:]:
                entry_time = datetime.fromtimestamp(trade.entry_time).strftime('%Y-%m-%d %H:%M')
                exit_time = datetime.fromtimestamp(trade.exit_time).strftime('%Y-%m-%d %H:%M')
                report.append(
                    f"- {trade.direction:5s} | "
                    f"{entry_time} @ ${trade.entry_price:,.2f} -> "
                    f"{exit_time} @ ${trade.exit_price:,.2f} | "
                    f"盈亏: ${trade.profit:,.2f} ({trade.profit_pct:+.2f}%)"
                )
            report.append("")

        report.append("=" * 80)

        report_text = "\n".join(report)

        # 保存到文件
        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(report_text)

            logger.info(f"报告已保存: {output_path}")

        return report_text

    def export_results(self, result: BacktestResult, output_dir: str):
        """
        导出回测结果

        Args:
            result: 回测结果
            output_dir: 输出目录
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        prefix = f"{result.strategy_name}_{result.symbol}_{timestamp}"

        # 导出汇总JSON
        summary_file = output_dir / f"{prefix}_summary.json"
        with open(summary_file, 'w', encoding='utf-8') as f:
            data = asdict(result)
            data.pop('trades', None)  # 移除交易详情
            json.dump(data, f, indent=2, ensure_ascii=False)

        # 导出交易详情CSV
        if result.trades:
            trades_file = output_dir / f"{prefix}_trades.csv"
            trades_data = []
            for trade in result.trades:
                trades_data.append({
                    'id': trade.id,
                    'symbol': trade.symbol,
                    'direction': trade.direction,
                    'entry_time': datetime.fromtimestamp(trade.entry_time).isoformat(),
                    'entry_price': trade.entry_price,
                    'exit_time': datetime.fromtimestamp(trade.exit_time).isoformat(),
                    'exit_price': trade.exit_price,
                    'quantity': trade.quantity,
                    'profit': trade.profit,
                    'profit_pct': trade.profit_pct
                })

            df = pd.DataFrame(trades_data)
            df.to_csv(trades_file, index=False)

        # 导出权益曲线CSV
        equity_file = output_dir / f"{prefix}_equity.csv"
        equity_df = pd.DataFrame(self.equity_curve)
        equity_df['time'] = pd.to_datetime(equity_df['time'], unit='s')
        equity_df.to_csv(equity_file, index=False)

        logger.info(f"回测结果已导出到: {output_dir}")


# 示例策略
def simple_ma_crossover_strategy(df: pd.DataFrame, params: Dict) -> List[int]:
    """
    简单移动平均线交叉策略

    Args:
        df: 历史数据
        params: 参数 {fast_period, slow_period}

    Returns:
        信号列表 (1=做多, -1=做空, 0=平仓/不操作)
    """
    fast_period = params.get('fast_period', 10)
    slow_period = params.get('slow_period', 30)

    # 计算移动平均线
    df['ma_fast'] = df['close'].rolling(window=fast_period).mean()
    df['ma_slow'] = df['close'].rolling(window=slow_period).mean()

    signals = []
    position = 0  # 0=空仓, 1=多头

    for i in range(len(df)):
        if i < slow_period:
            signals.append(0)
            continue

        ma_fast = df.iloc[i]['ma_fast']
        ma_slow = df.iloc[i]['ma_slow']
        prev_ma_fast = df.iloc[i-1]['ma_fast']
        prev_ma_slow = df.iloc[i-1]['ma_slow']

        # 金叉:快线上穿慢线,做多
        if prev_ma_fast <= prev_ma_slow and ma_fast > ma_slow:
            if position == 0:
                signals.append(1)
                position = 1
            else:
                signals.append(0)
        # 死叉:快线下穿慢线,平仓
        elif prev_ma_fast >= prev_ma_slow and ma_fast < ma_slow:
            if position == 1:
                signals.append(0)
                position = 0
            else:
                signals.append(0)
        else:
            signals.append(0)

    return signals


def main():
    """主函数"""
    import argparse

    # 配置日志
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )

    parser = argparse.ArgumentParser(description='交易策略回测引擎')
    parser.add_argument('--symbol', '-s', default='BTCUSD',
                       help='交易品种')
    parser.add_argument('--start', default='2024-01-01',
                       help='开始日期 (YYYY-MM-DD)')
    parser.add_argument('--end', default='2024-12-31',
                       help='结束日期 (YYYY-MM-DD)')
    parser.add_argument('--capital', '-c', type=float, default=100000.0,
                       help='初始资金')
    parser.add_argument('--fast-period', type=int, default=10,
                       help='快速均线周期')
    parser.add_argument('--slow-period', type=int, default=30,
                       help='慢速均线周期')
    parser.add_argument('--output', '-o',
                       help='报告输出路径')

    args = parser.parse_args()

    # 创建回测引擎
    engine = BacktestingEngine(initial_capital=args.capital)

    # 运行回测
    result = engine.run_backtest(
        simple_ma_crossover_strategy,
        symbol=args.symbol,
        start_date=args.start,
        end_date=args.end,
        fast_period=args.fast_period,
        slow_period=args.slow_period
    )

    if result:
        # 生成报告
        report = engine.generate_report(result, args.output)
        print(report)

        # 导出结果
        output_dir = Path(__file__).parent.parent / "reports" / "backtests"
        engine.export_results(result, str(output_dir))


if __name__ == "__main__":
    main()
