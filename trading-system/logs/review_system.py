# 复盘日志系统
# 自动记录交易历史、分析交易结果、生成复盘报告

import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import sqlite3
import pandas as pd
from pathlib import Path

logger = logging.getLogger(__name__)


class TradeLogger:
    """交易日志记录器"""

    def __init__(self, config: Dict):
        self.config = config
        self.log_dir = config.get("log_dir", "logs/trades")
        self.db_path = config.get("db_path", "logs/trading.db")

        Path(self.log_dir).mkdir(parents=True, exist_ok=True)
        Path(os.path.dirname(self.db_path)).mkdir(parents=True, exist_ok=True)

        self._init_database()

    def _init_database(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 交易表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT NOT NULL,
                symbol TEXT NOT NULL,
                action TEXT NOT NULL,
                entry_price REAL,
                exit_price REAL,
                volume REAL,
                profit REAL,
                commission REAL,
                entry_time TEXT,
                exit_time TEXT,
                duration_seconds INTEGER,
                ai_confidence REAL,
                ai_reason TEXT,
                indicators_used TEXT,
                news_sentiment TEXT,
                strategy TEXT,
                magic_number INTEGER,
                ticket_id TEXT,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 信号表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                action TEXT NOT NULL,
                confidence REAL,
                price REAL,
                timestamp TEXT,
                ai_models_used TEXT,
                reason TEXT,
                executed BOOLEAN DEFAULT 0,
                executed_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 错误表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS errors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT,
                error_type TEXT,
                error_message TEXT,
                traceback TEXT,
                context TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 性能指标表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                platform TEXT NOT NULL,
                total_trades INTEGER,
                winning_trades INTEGER,
                losing_trades INTEGER,
                win_rate REAL,
                total_profit REAL,
                total_loss REAL,
                net_profit REAL,
                avg_profit_per_trade REAL,
                max_drawdown REAL,
                sharpe_ratio REAL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()
        conn.close()

    def log_trade(self, trade_data: Dict):
        """记录交易"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO trades (
                    platform, symbol, action, entry_price, exit_price,
                    volume, profit, commission, entry_time, exit_time,
                    duration_seconds, ai_confidence, ai_reason,
                    indicators_used, news_sentiment, strategy,
                    magic_number, ticket_id, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trade_data.get("platform"),
                trade_data.get("symbol"),
                trade_data.get("action"),
                trade_data.get("entry_price"),
                trade_data.get("exit_price"),
                trade_data.get("volume"),
                trade_data.get("profit"),
                trade_data.get("commission"),
                trade_data.get("entry_time"),
                trade_data.get("exit_time"),
                trade_data.get("duration_seconds"),
                trade_data.get("ai_confidence"),
                trade_data.get("ai_reason"),
                json.dumps(trade_data.get("indicators_used", {})),
                trade_data.get("news_sentiment"),
                trade_data.get("strategy"),
                trade_data.get("magic_number"),
                trade_data.get("ticket_id"),
                trade_data.get("notes")
            ))

            conn.commit()
            logger.info(f"交易已记录: {trade_data.get('symbol')} {trade_data.get('action')}")
        except Exception as e:
            logger.error(f"记录交易失败: {e}")
            conn.rollback()
        finally:
            conn.close()

    def log_signal(self, signal_data: Dict):
        """记录交易信号"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO signals (
                    symbol, action, confidence, price, timestamp,
                    ai_models_used, reason, executed, executed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                signal_data.get("symbol"),
                signal_data.get("action"),
                signal_data.get("confidence"),
                signal_data.get("price"),
                signal_data.get("timestamp"),
                json.dumps(signal_data.get("ai_models_used", [])),
                signal_data.get("reason"),
                signal_data.get("executed", 0),
                signal_data.get("executed_at")
            ))

            conn.commit()
        except Exception as e:
            logger.error(f"记录信号失败: {e}")
            conn.rollback()
        finally:
            conn.close()

    def log_error(self, error_data: Dict):
        """记录错误"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO errors (
                    platform, error_type, error_message, traceback, context
                ) VALUES (?, ?, ?, ?, ?)
            """, (
                error_data.get("platform"),
                error_data.get("error_type"),
                error_data.get("error_message"),
                error_data.get("traceback"),
                json.dumps(error_data.get("context", {}))
            ))

            conn.commit()
        except Exception as e:
            logger.error(f"记录错误失败: {e}")
            conn.rollback()
        finally:
            conn.close()

    def get_trades(self,
                   platform: Optional[str] = None,
                   symbol: Optional[str] = None,
                   start_date: Optional[str] = None,
                   end_date: Optional[str] = None,
                   limit: Optional[int] = None) -> List[Dict]:
        """获取交易记录"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        query = "SELECT * FROM trades WHERE 1=1"
        params = []

        if platform:
            query += " AND platform = ?"
            params.append(platform)

        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)

        if start_date:
            query += " AND entry_time >= ?"
            params.append(start_date)

        if end_date:
            query += " AND entry_time <= ?"
            params.append(end_date)

        query += " ORDER BY entry_time DESC"

        if limit:
            query += " LIMIT ?"
            params.append(limit)

        try:
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"获取交易记录失败: {e}")
            return []
        finally:
            conn.close()

    def get_signals(self,
                   symbol: Optional[str] = None,
                   executed_only: bool = False,
                   limit: Optional[int] = None) -> List[Dict]:
        """获取信号记录"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        query = "SELECT * FROM signals WHERE 1=1"
        params = []

        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)

        if executed_only:
            query += " AND executed = 1"

        query += " ORDER BY timestamp DESC"

        if limit:
            query += " LIMIT ?"
            params.append(limit)

        try:
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"获取信号记录失败: {e}")
            return []
        finally:
            conn.close()

    def calculate_daily_performance(self, date: Optional[str] = None) -> Dict:
        """计算每日性能"""
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # 获取当日交易
            cursor.execute("""
                SELECT platform, action, profit, exit_time
                FROM trades
                WHERE DATE(entry_time) = ? AND exit_time IS NOT NULL
            """, (date,))

            trades = cursor.fetchall()

            if not trades:
                return {"date": date, "message": "无交易记录"}

            # 按平台统计
            performance_by_platform = {}
            all_profits = []

            for trade in trades:
                platform, action, profit, exit_time = trade

                if platform not in performance_by_platform:
                    performance_by_platform[platform] = {
                        "total_trades": 0,
                        "winning_trades": 0,
                        "losing_trades": 0,
                        "total_profit": 0,
                        "profits": []
                    }

                performance_by_platform[platform]["total_trades"] += 1
                performance_by_platform[platform]["profits"].append(profit)
                all_profits.append(profit)

                if profit > 0:
                    performance_by_platform[platform]["winning_trades"] += 1
                else:
                    performance_by_platform[platform]["losing_trades"] += 1

                performance_by_platform[platform]["total_profit"] += profit

            # 计算每个平台的指标
            result = {"date": date, "platforms": {}}

            for platform, stats in performance_by_platform.items():
                total = stats["total_trades"]
                wins = stats["winning_trades"]
                losses = stats["losing_trades"]

                total_profit = stats["total_profit"]
                winning_profit = sum(p for p in stats["profits"] if p > 0)
                losing_profit = sum(p for p in stats["profits"] if p < 0)

                result["platforms"][platform] = {
                    "total_trades": total,
                    "winning_trades": wins,
                    "losing_trades": losses,
                    "win_rate": wins / total if total > 0 else 0,
                    "total_profit": total_profit,
                    "winning_profit": winning_profit,
                    "losing_profit": losing_profit,
                    "avg_profit_per_trade": total_profit / total if total > 0 else 0,
                    "profit_factor": winning_profit / abs(losing_profit) if losing_profit != 0 else float('inf')
                }

            # 全局统计
            result["overall"] = {
                "total_trades": sum(s["total_trades"] for s in performance_by_platform.values()),
                "net_profit": sum(s["total_profit"] for s in performance_by_platform.values()),
                "best_trade": max(all_profits) if all_profits else 0,
                "worst_trade": min(all_profits) if all_profits else 0
            }

            return result

        except Exception as e:
            logger.error(f"计算性能失败: {e}")
            return {"error": str(e)}
        finally:
            conn.close()


class ReviewReportGenerator:
    """复盘报告生成器"""

    def __init__(self, logger: TradeLogger, ai_ensemble=None):
        self.logger = logger
        self.ai_ensemble = ai_ensemble

    def generate_daily_report(self, date: Optional[str] = None) -> str:
        """生成每日复盘报告"""
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        performance = self.logger.calculate_daily_performance(date)

        if "message" in performance:
            return f"\n{'='*60}\n每日复盘报告 - {date}\n{'='*60}\n\n{performance['message']}\n"

        report = f"""
{'='*60}
每日复盘报告 - {date}
{'='*60}

【总体表现】
总交易次数: {performance['overall']['total_trades']}
净盈利: {performance['overall']['net_profit']:.2f}
最佳交易: {performance['overall']['best_trade']:.2f}
最差交易: {performance['overall']['worst_trade']:.2f}

【各平台表现】
"""

        for platform, stats in performance["platforms"].items():
            report += f"""
{platform.upper()}
  交易次数: {stats['total_trades']}
  盈亏比: {stats['winning_trades']} / {stats['losing_trades']}
  胜率: {stats['win_rate']*100:.2f}%
  总盈亏: {stats['total_profit']:.2f}
  盈利交易总盈: {stats['winning_profit']:.2f}
  亏损交易总亏: {stats['losing_profit']:.2f}
  平均每笔盈亏: {stats['avg_profit_per_trade']:.2f}
  盈亏比: {stats['profit_factor']:.2f}
"""

        report += "\n" + "="*60 + "\n"

        return report

    def generate_weekly_report(self, week_start: Optional[str] = None) -> str:
        """生成每周复盘报告"""
        if week_start is None:
            today = datetime.now()
            week_start = (today - timedelta(days=today.weekday())).strftime("%Y-%m-%d")

        week_end = (datetime.strptime(week_start, "%Y-%m-%d") + timedelta(days=6)).strftime("%Y-%m-%d")

        conn = sqlite3.connect(self.logger.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT platform, symbol, action, entry_price, exit_price,
                       profit, entry_time, exit_time, ai_reason
                FROM trades
                WHERE DATE(entry_time) BETWEEN ? AND ?
                AND exit_time IS NOT NULL
                ORDER BY entry_time
            """, (week_start, week_end))

            trades = cursor.fetchall()

            if not trades:
                return f"\n{'='*60}\n每周复盘报告 - {week_start} 至 {week_end}\n{'='*60}\n\n无交易记录\n"

            report = f"""
{'='*60}
每周复盘报告 - {week_start} 至 {week_end}
{'='*60}

【交易明细】
"""

            for trade in trades:
                platform, symbol, action, entry_price, exit_price, profit, entry_time, exit_time, ai_reason = trade

                report += f"""
[{entry_time}] {platform.upper()} {symbol}
  操作: {action.upper()}
  入场价: {entry_price:.5f}
  出场价: {exit_price:.5f}
  盈亏: {profit:.2f}
  AI理由: {ai_reason or 'N/A'}
"""

            # 统计
            total_trades = len(trades)
            winning_trades = sum(1 for t in trades if t[5] > 0)
            losing_trades = total_trades - winning_trades
            net_profit = sum(t[5] for t in trades)

            report += f"""
【周度总结】
总交易次数: {total_trades}
盈利交易: {winning_trades}
亏损交易: {losing_trades}
胜率: {winning_trades/total_trades*100:.2f}%
净盈亏: {net_profit:.2f}
"""

            report += "\n" + "="*60 + "\n"

            return report

        except Exception as e:
            logger.error(f"生成周报失败: {e}")
            return f"生成周报失败: {e}"
        finally:
            conn.close()

    def generate_ai_analysis_report(self, date: Optional[str] = None) -> str:
        """使用AI生成分析报告"""
        if not self.ai_ensemble:
            return "AI集成器未启用，无法生成AI分析报告"

        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        trades = self.logger.get_trades(start_date=date, end_date=date)

        if not trades:
            return f"日期 {date} 无交易记录"

        # 构建分析提示
        prompt = f"""请分析以下交易数据并给出复盘建议：

日期: {date}
总交易次数: {len(trades)}

交易明细:
"""
        for trade in trades:
            prompt += f"""
品种: {trade['symbol']}
操作: {trade['action']}
入场价: {trade['entry_price']}
出场价: {trade['exit_price']}
盈亏: {trade['profit']}
AI置信度: {trade['ai_confidence']}
AI理由: {trade['ai_reason']}
"""

        prompt += """

请分析：
1. 交易策略的有效性
2. 亏损交易的原因
3. 盈利交易的特点
4. 改进建议
5. 风险控制建议
"""

        try:
            analysis = self.ai_ensemble.analyze_text(prompt)

            return f"""
{'='*60}
AI分析报告 - {date}
{'='*60}

{analysis}

{'='*60}
"""
        except Exception as e:
            logger.error(f"AI分析失败: {e}")
            return f"AI分析失败: {e}"

    def save_report(self, report: str, filename: str):
        """保存报告到文件"""
        report_dir = self.logger.log_dir + "/reports"
        Path(report_dir).mkdir(parents=True, exist_ok=True)

        filepath = os.path.join(report_dir, filename)

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(report)

        logger.info(f"报告已保存: {filepath}")

    def export_to_csv(self, start_date: Optional[str] = None,
                     end_date: Optional[str] = None) -> str:
        """导出交易数据到CSV"""
        trades = self.logger.get_trades(start_date=start_date, end_date=end_date)

        if not trades:
            return "无交易数据可导出"

        df = pd.DataFrame(trades)

        # 转换JSON字段
        for col in ['indicators_used']:
            if col in df.columns:
                df[col] = df[col].apply(lambda x: json.loads(x) if x else {})

        filepath = os.path.join(self.logger.log_dir, f"trades_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
        df.to_csv(filepath, index=False, encoding='utf-8-sig')

        return filepath


def create_trade_logger(config: Dict) -> TradeLogger:
    """创建交易日志记录器"""
    return TradeLogger(config)


if __name__ == "__main__":
    config = {
        "log_dir": "logs/trades",
        "db_path": "logs/trading.db"
    }

    logger_instance = TradeLogger(config)
    reporter = ReviewReportGenerator(logger_instance)

    # 测试生成日报
    daily_report = reporter.generate_daily_report()
    print(daily_report)

    # 保存报告
    reporter.save_report(
        daily_report,
        f"daily_report_{datetime.now().strftime('%Y%m%d')}.txt"
    )
