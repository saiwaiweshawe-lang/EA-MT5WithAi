# 每日盈亏分析与AI报告生成器

import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import sqlite3
import pandas as pd
from pathlib import Path

logger = logging.getLogger(__name__)


class DailyProfitAnalyzer:
    """每日盈亏分析器"""

    def __init__(self, config: Dict, trade_logger=None):
        self.config = config
        self.db_path = config.get("db_path", "logs/trading.db")
        self.trade_logger = trade_logger
        self.enabled = config.get("enabled", True)
        self.analysis_time = config.get("analysis_time", "23:30")  # 每日分析时间

        # 盈亏阈值
        self.daily_loss_threshold = config.get("daily_loss_threshold", -500)  # 日亏损阈值
        self.daily_profit_target = config.get("daily_profit_target", 200)  # 日盈利目标

    def get_trades_by_date(self, date: str) -> List[Dict]:
        """获取指定日期的交易"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT * FROM trades
                WHERE DATE(entry_time) = ? AND exit_time IS NOT NULL
                ORDER BY entry_time
            """, (date,))

            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"获取交易记录失败: {e}")
            return []
        finally:
            conn.close()

    def analyze_daily_performance(self, date: Optional[str] = None) -> Dict:
        """分析每日绩效"""
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        trades = self.get_trades_by_date(date)

        if not trades:
            return {
                "date": date,
                "status": "no_trades",
                "message": "无交易记录"
            }

        # 基础统计
        total_trades = len(trades)
        winning_trades = sum(1 for t in trades if t["profit"] > 0)
        losing_trades = total_trades - winning_trades

        total_profit = sum(t["profit"] for t in trades)
        total_commission = sum(t.get("commission", 0) for t in trades)
        net_profit = total_profit - total_commission

        winning_profit = sum(t["profit"] for t in trades if t["profit"] > 0)
        losing_loss = abs(sum(t["profit"] for t in trades if t["profit"] < 0))

        # 按平台统计
        by_platform = {}
        for t in trades:
            platform = t.get("platform", "unknown")
            if platform not in by_platform:
                by_platform[platform] = {"count": 0, "profit": 0}

            by_platform[platform]["count"] += 1
            by_platform[platform]["profit"] += t["profit"]

        # 按品种统计
        by_symbol = {}
        for t in trades:
            symbol = t.get("symbol", "unknown")
            if symbol not in by_symbol:
                by_symbol[symbol] = {"count": 0, "profit": 0, "max_loss": 0}

            by_symbol[symbol]["count"] += 1
            by_symbol[symbol]["profit"] += t["profit"]
            by_symbol[symbol]["max_loss"] = min(by_symbol[symbol]["max_loss"], t["profit"])

        # 按时间段统计
        by_time_period = self._analyze_by_time_period(trades)

        # 盈亏比
        profit_factor = winning_profit / losing_loss if losing_loss > 0 else float('inf')

        # 胜率
        win_rate = winning_trades / total_trades if total_trades > 0 else 0

        # 平均盈利/亏损
        avg_profit = winning_profit / winning_trades if winning_trades > 0 else 0
        avg_loss = losing_loss / losing_trades if losing_trades > 0 else 0

        # 连盈连亏统计
        streaks = self._calculate_streaks(trades)

        # 风险评估
        risk_level = self._assess_risk_level(net_profit, profit_factor, streaks)

        # 达成目标
        target_status = (
            "exceeded" if net_profit > self.daily_profit_target else
            "met" if net_profit > 0 else "not_met"
        )

        # 熔断状态
        circuit_breaker_triggered = net_profit < self.daily_loss_threshold

        return {
            "date": date,
            "status": "analyzed",
            "summary": {
                "total_trades": total_trades,
                "winning_trades": winning_trades,
                "losing_trades": losing_trades,
                "win_rate": win_rate,
                "total_profit": total_profit,
                "total_commission": total_commission,
                "net_profit": net_profit,
                "profit_factor": profit_factor,
                "avg_profit": avg_profit,
                "avg_loss": avg_loss,
                "risk_reward_ratio": avg_profit / abs(avg_loss) if avg_loss != 0 else 0
            },
            "by_platform": by_platform,
            "by_symbol": by_symbol,
            "by_time_period": by_time_period,
            "streaks": streaks,
            "risk_assessment": {
                "level": risk_level,
                "recommendation": self._get_risk_recommendation(risk_level)
            },
            "targets": {
                "daily_target": self.daily_profit_target,
                "status": target_status,
                "achieved": net_profit > 0
            },
            "circuit_breaker": {
                "triggered": circuit_breaker_triggered,
                "threshold": self.daily_loss_threshold,
                "current_loss": net_profit if net_profit < 0 else 0
            }
        }

    def _analyze_by_time_period(self, trades: List[Dict]) -> Dict:
        """按时间段分析"""
        periods = {
            "morning": {"count": 0, "profit": 0},      # 00:00-08:00
            "morning_trading": {"count": 0, "profit": 0},  # 08:00-12:00
            "afternoon": {"count": 0, "profit": 0},     # 12:00-16:00
            "evening": {"count": 0, "profit": 0},       # 16:00-20:00
            "night": {"count": 0, "profit": 0}          # 20:00-24:00
        }

        for trade in trades:
            try:
                entry_time = datetime.fromisoformat(trade.get("entry_time", ""))
                hour = entry_time.hour

                if 0 <= hour < 8:
                    periods["morning"]["count"] += 1
                    periods["morning"]["profit"] += trade["profit"]
                elif 8 <= hour < 12:
                    periods["morning_trading"]["count"] += 1
                    periods["morning_trading"]["profit"] += trade["profit"]
                elif 12 <= hour < 16:
                    periods["afternoon"]["count"] += 1
                    periods["afternoon"]["profit"] += trade["profit"]
                elif 16 <= hour < 20:
                    periods["evening"]["count"] += 1
                    periods["evening"]["profit"] += trade["profit"]
                else:
                    periods["night"]["count"] += 1
                    periods["night"]["profit"] += trade["profit"]
            except Exception as e:
                continue

        return periods

    def _calculate_streaks(self, trades: List[Dict]) -> Dict:
        """计算连盈连亏"""
        if not trades:
            return {"max_winning_streak": 0, "max_losing_streak": 0}

        current_streak = 0
        max_winning_streak = 0
        max_losing_streak = 0

        for trade in trades:
            profit = trade["profit"]

            if profit > 0:
                if current_streak > 0:
                    current_streak += 1
                else:
                    current_streak = 1
                max_winning_streak = max(max_winning_streak, current_streak)
            else:
                if current_streak < 0:
                    current_streak -= 1
                else:
                    current_streak = -1
                max_losing_streak = max(max_losing_streak, abs(current_streak))

        return {
            "max_winning_streak": max_winning_streak,
            "max_losing_streak": max_losing_streak
        }

    def _assess_risk_level(self, net_profit: float,
                           profit_factor: float,
                           streaks: Dict) -> str:
        """评估风险等级"""
        if net_profit < self.daily_loss_threshold * 0.5:
            return "critical"
        elif streaks["max_losing_streak"] >= 5:
            return "high"
        elif profit_factor < 1.0 or streaks["max_losing_streak"] >= 3:
            return "medium"
        else:
            return "low"

    def _get_risk_recommendation(self, risk_level: str) -> str:
        """获取风险建议"""
        recommendations = {
            "critical": "立即停止交易，检查策略问题，重新评估风险控制",
            "high": "大幅减少仓位，加强止损，暂停新开仓",
            "medium": "适当减少仓位，检查止损设置",
            "low": "继续保持当前策略，定期监控"
        }
        return recommendations.get(risk_level, "")


class AIReportGenerator:
    """AI报告生成器"""

    def __init__(self, config: Dict, ai_ensemble=None):
        self.config = config
        self.ai_ensemble = ai_ensemble
        self.enabled = config.get("enabled", True)
        self.report_language = config.get("language", "zh")  # zh/en

    def generate_daily_report(self, analysis: Dict) -> str:
        """生成每日分析报告（使用AI）"""
        if not self.enabled:
            return self._generate_basic_report(analysis)

        if self.ai_ensemble:
            return self._generate_ai_report(analysis)
        else:
            return self._generate_basic_report(analysis)

    def _generate_ai_report(self, analysis: Dict) -> str:
        """使用AI生成详细报告"""
        if analysis["status"] == "no_trades":
            return f"\n📊 {analysis['date']} 每日盈亏分析\n\n无交易记录\n"

        # 构建分析提示
        prompt = self._build_analysis_prompt(analysis)

        try:
            ai_response = self.ai_ensemble.analyze_text(prompt)
            return self._format_ai_report(analysis, ai_response)
        except Exception as e:
            logger.error(f"AI报告生成失败: {e}")
            return self._generate_basic_report(analysis)

    def _build_analysis_prompt(self, analysis: Dict) -> str:
        """构建AI分析提示"""
        date = analysis["date"]
        summary = analysis["summary"]
        by_platform = analysis["by_platform"]
        by_symbol = analysis["by_symbol"]
        streaks = analysis["streaks"]
        risk = analysis["risk_assessment"]
        circuit = analysis["circuit_breaker"]

        prompt = f"""请分析以下每日交易数据并生成详细报告：

【日期】{date}

【交易概览】
总交易: {summary['total_trades']}
盈利交易: {summary['winning_trades']}
亏损交易: {summary['losing_trades']}
胜率: {summary['win_rate']*100:.1f}%
净盈亏: {summary['net_profit']:.2f}
盈亏比: {summary['profit_factor']:.2f}

【按平台统计】
"""
        for platform, data in by_platform.items():
            prompt += f"{platform}: {data['count']}笔, 盈亏={data['profit']:.2f}\n"

        prompt += f"""
【按品种统计】
"""
        for symbol, data in by_symbol.items():
            prompt += f"{symbol}: {data['count']}笔, 盈亏={data['profit']:.2f}\n"

        prompt += f"""
【连盈连亏】
最大连盈: {streaks['max_winning_streak']}笔
最大连亏: {streaks['max_losing_streak']}笔

【风险评估】
风险等级: {risk['level']}
建议: {risk['recommendation']}

【熔断状态】
{'已触发！' if circuit['triggered'] else '未触发'}

请生成包含以下内容的分析报告：
1. 今日交易表现总结
2. 亏损交易原因分析
3. 盈利交易特点
4. 最佳交易时间段
5. 明日交易建议
6. 风险控制建议
7. 策略调整建议

用简洁专业的语言生成报告。"""

        return prompt

    def _format_ai_report(self, analysis: Dict, ai_response: str) -> str:
        """格式化AI报告"""
        header = f"""
{'='*60}
📊 每日盈亏分析报告 - {analysis['date']}
{'='*60}
"""

        summary_section = f"""
【交易概览】
交易次数: {analysis['summary']['total_trades']}
盈利次数: {analysis['summary']['winning_trades']}
亏损次数: {analysis['summary']['losing_trades']}
胜率: {analysis['summary']['win_rate']*100:.1f}%
总盈利: {analysis['summary']['total_profit']:.2f}
手续费: {analysis['summary']['total_commission']:.2f}
净盈亏: {analysis['summary']['net_profit']:.2f}
盈亏比: {analysis['summary']['profit_factor']:.2f}
平均盈利: {analysis['summary']['avg_profit']:.2f}
平均亏损: {analysis['summary']['avg_loss']:.2f}
"""

        # 熔断警示
        if analysis['circuit_breaker']['triggered']:
            circuit_alert = f"""

⚠️⚠️⚠️ 熔断已触发 ⚠️⚠️⚠️
当前亏损: {analysis['circuit_breaker']['current_loss']:.2f}
熔断阈值: {analysis['circuit_breaker']['threshold']}
已自动停止交易！
"""
        else:
            circuit_alert = "\n熔断状态: 正常\n"

        risk_section = f"""
【风险评估】
风险等级: {analysis['risk_assessment']['level'].upper()}
建议: {analysis['risk_assessment']['recommendation']}
"""

        ai_section = f"""
【AI智能分析】
{ai_response}
"""

        footer = f"""
{'='*60}
生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
{'='*60}
"""

        return header + summary_section + circuit_alert + risk_section + ai_section + footer

    def _generate_basic_report(self, analysis: Dict) -> str:
        """生成基础报告（无AI）"""
        if analysis["status"] == "no_trades":
            return f"\n📊 {analysis['date']} 每日盈亏分析\n\n无交易记录\n"

        summary = analysis["summary"]

        report = f"""
{'='*60}
📊 每日盈亏分析报告 - {analysis['date']}
{'='*60}

【交易概览】
交易次数: {summary['total_trades']}
盈利次数: {summary['winning_trades']}
亏损次数: {summary['losing_trades']}
胜率: {summary['win_rate']*100:.1f}%
总盈利: {summary['total_profit']:.2f}
手续费: {summary['total_commission']:.2f}
净盈亏: {summary['net_profit']:.2f}
盈亏比: {summary['profit_factor']:.2f}
平均盈利: {summary['avg_profit']:.2f}
平均亏损: {summary['avg_loss']:.2f}

【按平台统计】
"""
        for platform, data in analysis["by_platform"].items():
            report += f"  {platform}: {data['count']}笔, 盈亏={data['profit']:.2f}\n"

        report += """
【按品种统计】
"""
        for symbol, data in analysis["by_symbol"].items():
            report += f"  {symbol}: {data['count']}笔, 盈亏={data['profit']:.2f}\n"

        report += f"""
【连盈连亏】
最大连盈: {analysis['streaks']['max_winning_streak']}笔
最大连亏: {analysis['streaks']['max_losing_streak']}笔

【风险评估】
风险等级: {analysis['risk_assessment']['level'].upper()}
建议: {analysis['risk_assessment']['recommendation']}

【熔断状态】
{'已触发！' if analysis['circuit_breaker']['triggered'] else '未触发'}
"""

        if analysis['circuit_breaker']['triggered']:
            report += f"\n⚠️ 当前亏损: {analysis['circuit_breaker']['current_loss']:.2f}\n"

        report += f"""
{'='*60}
"""

        return report

    def generate_tg_message(self, analysis: Dict, detailed: bool = False) -> str:
        """生成Telegram消息"""
        if analysis["status"] == "no_trades":
            return f"📊 {analysis['date']} 每日交易报告\n\n无交易记录"

        summary = analysis["summary"]
        risk = analysis["risk_assessment"]

        if detailed:
            # 详细版消息
            message = f"""
📊 每日盈亏报告 - {analysis['date']}

【交易概览】
交易: {summary['total_trades']}笔
胜率: {summary['win_rate']*100:.1f}%
净盈亏: {summary['net_profit']:+.2f}
盈亏比: {summary['profit_factor']:.2f}

【最佳平台】
"""
            # 找出表现最好的平台
            best_platform = max(analysis["by_platform"].items(),
                              key=lambda x: x[1]["profit"])
            message += f"{best_platform[0]}: {best_platform[1]['profit']:+.2f}\n"

            message += f"""
【连盈连亏】
最大连盈: {analysis['streaks']['max_winning_streak']}笔
最大连亏: {analysis['streaks']['max_losing_streak']}笔

【风险评估】
{risk['level'].upper()} - {risk['recommendation'][:30]}...
"""

            if analysis['circuit_breaker']['triggered']:
                message += f"\n⚠️ 熔断已触发！停止交易\n"
        else:
            # 简洁版消息
            profit_emoji = "📈" if summary["net_profit"] > 0 else "📉"
            risk_emoji = {
                "low": "🟢",
                "medium": "🟡",
                "high": "🟠",
                "critical": "🔴"
            }

            message = f"""{profit_emoji} {analysis['date']} 每日报告

交易: {summary['total_trades']}笔 | 胜率: {summary['win_rate']*100:.1f}%
净盈亏: {summary['net_profit']:+.2f} | 盈亏比: {summary['profit_factor']:.2f}

{risk_emoji[risk['level']]} 风险: {risk['level'].upper()}
"""

            if analysis['circuit_breaker']['triggered']:
                message += f"\n🚨 熔断触发！"

        return message

    def generate_alert_message(self, alert_type: str, details: Dict) -> str:
        """生成警报消息"""
        alerts = {
            "circuit_breaker": {
                "emoji": "🚨",
                "title": "熔断触发",
                "message": "当日亏损达到阈值，交易已自动停止"
            },
            "high_risk": {
                "emoji": "⚠️",
                "title": "高风险警报",
                "message": "风险等级上升，建议减少仓位"
            },
            "recovery": {
                "emoji": "🟢",
                "title": "熔断恢复",
                "message": "风险已降低，可以恢复交易"
            },
            "daily_target": {
                "emoji": "🎯",
                "title": "目标达成",
                "message": f"今日盈利目标已达成: {details.get('profit', 0):.2f}"
            },
            "large_loss": {
                "emoji": "📉",
                "title": "大额亏损",
                "message": f"单笔大额亏损: {details.get('loss', 0):.2f}"
            },
            "large_profit": {
                "emoji": "📈",
                "title": "大额盈利",
                "message": f"单笔大额盈利: {details.get('profit', 0):.2f}"
            }
        }

        alert = alerts.get(alert_type, alerts["high_risk"])
        return f"{alert['emoji']} {alert['title']}\n{alert['message']}\n{json.dumps(details, ensure_ascii=False)[:100]}"


def create_daily_analyzer(config: Dict, trade_logger=None) -> DailyProfitAnalyzer:
    """创建每日盈亏分析器"""
    return DailyProfitAnalyzer(config, trade_logger)


def create_ai_report_generator(config: Dict, ai_ensemble=None) -> AIReportGenerator:
    """创建AI报告生成器"""
    return AIReportGenerator(config, ai_ensemble)


if __name__ == "__main__":
    # 测试代码
    config = {
        "enabled": True,
        "db_path": "logs/trading.db",
        "daily_loss_threshold": -500,
        "daily_profit_target": 200,
        "language": "zh"
    }

    analyzer = DailyProfitAnalyzer(config)
    generator = AIReportGenerator(config)

    # 分析今日
    analysis = analyzer.analyze_daily_performance()

    # 生成报告
    report = generator.generate_daily_report(analysis)
    print(report)

    # 生成TG消息
    tg_message = generator.generate_tg_message(analysis, detailed=False)
    print("\nTelegram消息:")
    print(tg_message)
