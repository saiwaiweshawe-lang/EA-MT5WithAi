# Telegram增强版交易机器人
# 支持每日盈亏AI分析报告、TG文本推送、紧急熔断功能

import logging
import asyncio
import json
import os
from datetime import datetime, timedelta
from typing import Dict, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
    JobQueue
)

# 导入交易模块
from exchange_trader import ExchangeTrader
from mt5_bridge import MT5Bridge
from daily_analyzer import DailyProfitAnalyzer, AIReportGenerator
from circuit_breaker import CircuitBreaker

# 配置日志
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# 状态常量
SELECT_PLATFORM, SELECT_ACTION, ENTER_SYMBOL, ENTER_AMOUNT, ENTER_PRICE = range(5)


class EnhancedTelegramBot:
    """增强版Telegram交易机器人"""

    def __init__(self, config_path: str = "config/bot_config.json"):
        self.config = self._load_config(config_path)
        self.app = Application.builder().token(self.config["telegram_bot_token"]).build()

        self.mt5_bridge = MT5Bridge(self.config.get("mt5_config", {}))
        self.exchange_trader = ExchangeTrader(self.config.get("exchange_config", {}))

        # 每日盈亏分析器
        analyzer_config = self.config.get("daily_analysis", {})
        self.profit_analyzer = DailyProfitAnalyzer(analyzer_config)

        # AI报告生成器
        ai_config = self.config.get("ai", {})
        self.ai_reporter = AIReportGenerator(ai_config)

        # 熔断器
        circuit_config = self.config.get("circuit_breaker", {})
        self.circuit_breaker = CircuitBreaker(circuit_config, self.mt5_bridge, self.exchange_trader)

        self.user_sessions = {}

        # 注册命令处理器
        self._register_handlers()

        # 启动定时任务
        self._schedule_jobs()

    def _load_config(self, config_path: str) -> dict:
        """加载配置文件"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning(f"配置文件 {config_path} 未找到，使用默认配置")
            return {
                "telegram_bot_token": "",
                "telegram_chat_id": "",
                "authorized_users": [],
                "mt5_config": {},
                "exchange_config": {},
                "daily_analysis": {
                    "enabled": True,
                    "report_time": "23:30",
                    "daily_loss_threshold": -500,
                    "daily_profit_target": 200
                },
                "circuit_breaker": {
                    "enabled": True,
                    "max_loss_per_day": -1000,
                    "max_consecutive_losses": 5,
                    "auto_stop_trading": True,
                    "notify_on_trigger": True,
                    "auto_recover_after_hours": 24
                }
            }

    def _register_handlers(self):
        """注册所有处理器"""
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("help", self.help_command))
        self.app.add_handler(CommandHandler("status", self.status_command))
        self.app.add_handler(CommandHandler("balance", self.balance_command))
        self.app.add_handler(CommandHandler("positions", self.positions_command))
        self.app.add_handler(CommandHandler("trade", self.trade_command))
        self.app.add_handler(CommandHandler("close", self.close_command))
        self.app.add_handler(CommandHandler("settings", self.settings_command))
        self.app.add_handler(CommandHandler("report", self.report_command))
        self.app.add_handler(CommandHandler("daily", self.daily_command))
        self.app.add_handler(CommandHandler("circuit", self.circuit_status_command))
        self.app.add_handler(CommandHandler("reset_circuit", self.reset_circuit_command))
        self.app.add_handler(CallbackQueryHandler(self.button_callback))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))

    def _schedule_jobs(self):
        """调度定时任务"""
        # 每日盈亏报告
        report_time = self.config.get("daily_analysis", {}).get("report_time", "23:30")
        hour, minute = map(int, report_time.split(":"))

        self.app.job_queue.run_daily(
            self.send_daily_report,
            time=(hour, minute, 0),
            name="daily_report"
        )

        # 每小时检查熔断状态
        self.app.job_queue.run_repeating(
            self.check_circuit_status,
            interval=timedelta(hours=1),
            first=datetime.now() + timedelta(minutes=5),
            name="circuit_check"
        )

        logger.info(f"定时任务已调度: 每日报告 {report_time}, 每小时检查熔断")

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """启动命令"""
        user_id = update.effective_user.id

        if user_id not in self.config.get("authorized_users", []):
            await update.message.reply_text("您没有权限使用此机器人！")
            return

        welcome_text = f"""
欢迎使用AI增强交易机器人

可用命令：
/start - 启动机器人
/help - 显示帮助信息
/status - 查看系统状态
/balance - 查看账户余额
/positions - 查看待持仓位
/trade - 执行交易
/close - 平仓
/settings - 查看设置
/report - 生成分析报告
/daily - 每日盈亏报告
/circuit - 查看熔断状态
/reset_circuit - 重置熔断器

⚠️ 新功能：
- 每日AI盈亏分析
- 紧急熔断保护
- 自动风险警报
"""
        await update.message.reply_text(welcome_text)

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """帮助命令"""
        help_text = """
AI增强交易机器人帮助

基础命令：
/start - 启动机器人
/help - 显示此帮助

查询命令：
/status - 查看所有平台状态
/balance [mt5/exchange] - 查看余额
/positions [mt5/exchange] - 查看待持仓位

交易命令：
/trade - 开始交易流程
/close [mt5/exchange] - 平所有仓或指定仓

分析命令：
/report - 生成AI分析报告
/daily [date] - 每日盈亏分析
/daily detailed - 详细版每日报告

熔断命令：
/circuit - 查看熔断状态
/reset_circuit - 手动重置熔断器

设置命令：
/settings - 查看当前设置

交易平台：
- MT5: 外汇、黄金、白银等
- Exchange: 币圈交易所（Binance/OKX等）

新功能说明：
1. 每日AI盈亏分析
   - 分析每日交易表现
   - AI智能解读交易数据
   - 识别最佳交易时段
   - 生成改进建议

2. 紧急熔断保护
   - 日亏损达到阈值自动停止
   - 连续亏损自动暂停
   - 可配置恢复时间
   - 实时TG通知

3. 风险警报
   - 大额亏损提醒
   - 大额盈利通知
   - 目标达成提醒
   - 高风险状态提醒
"""
        await update.message.reply_text(help_text)

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """状态命令（增强版）"""
        user_id = update.effective_user.id

        if user_id not in self.config.get("authorized_users", []):
            await update.message.reply_text("权限不足！")
            return

        # 获取MT5状态
        mt5_status = self.mt5_bridge.get_status()

        # 获取交易所状态
        exchange_status = self.exchange_trader.get_status()

        # 获取熔断状态
        circuit_status = self.circuit_breaker.get_status()

        status_text = f"""
系统状态

时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

MT5 状态:
连接: {'已连接' if mt5_status['connected'] else '未连接'}
账户: {mt5_status.get('account', 'N/A')}
余额: {mt5_status.get('balance', 'N/A')}

交易所状态:
连接: {'已连接' if exchange_status['connected'] else '未连接'}
账户: {exchange_status.get('account', 'N/A')}
余额: {exchange_status.get('balance', 'N/A')}

熔断保护:
状态: {'已触发' if circuit_status['triggered'] else '正常'}
当日亏损: {circuit_status.get('current_daily_loss', 0):.2f}
阈值: {circuit_status.get('max_daily_loss', 0):.2f}
连续亏损: {circuit_status.get('consecutive_losses', 0)}次
"""
        await update.message.reply_text(status_text)

    async def balance_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """余额命令"""
        user_id = update.effective_user.id

        if user_id not in self.config.get("authorized_users", []):
            await update.message.reply_text("权限不足！")
            return

        args = context.args
        platform = args[0] if args else "all"

        if platform in ["all", "mt5"]:
            mt5_balance = self.mt5_bridge.get_balance()
            await update.message.reply_text(f"MT5余额: {mt5_balance}")

        if platform in ["all", "exchange"]:
            exchange_balance = self.exchange_trader.get_balance()
            await update.message.reply_text(f"交易所余额: {exchange_balance}")

    async def positions_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """持仓命令"""
        user_id = update.effective_user.id

        if user_id not in self.config.get("authorized_users", []):
            await update.message.reply_text("权限不足！")
            return

        args = context.args
        platform = args[0] if args else "all"

        if platform in ["all", "mt5"]:
            positions = self.mt5_bridge.get_positions()
            if positions:
                text = "MT5持仓:\n"
                for pos in positions:
                    text += f"{pos['symbol']} {pos['type']} {pos['volume']} @ {pos['price']}\n"
                await update.message.reply_text(text)
            else:
                await update.message.reply_text("MT5无持仓")

        if platform in ["all", "exchange"]:
            positions = self.exchange_trader.get_positions()
            if positions:
                text = "交易所持仓:\n"
                for pos in positions:
                    text += f"{pos['symbol']} {pos['side']} {pos['amount']} @ {pos['price']}\n"
                await update.message.reply_text(text)
            else:
                await update.message.reply_text("交易所无持仓")

    async def trade_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """交易命令 - 选择平台"""
        user_id = update.effective_user.id

        if user_id not in self.config.get("authorized_users", []):
            await update.message.reply_text("权限不足！")
            return

        # 检查熔断状态
        if self.circuit_breaker.is_triggered():
            await update.message.reply_text("熔断已触发，暂停交易！使用 /reset_circuit 重置")
            return

        keyboard = [
            [InlineKeyboardButton("MT5", callback_data="platform_mt5")],
            [InlineKeyboardButton("交易所", callback_data="platform_exchange")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text("选择交易平台:", reply_markup=reply_markup)
        return SELECT_PLATFORM

    async def close_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """平仓命令"""
        user_id = update.effective_user.id

        if user_id not in self.config.get("authorized_users", []):
            await update.message.reply_text("权限不足！")
            return

        keyboard = [
            [InlineKeyboardButton("平MT5所有仓", callback_data="close_mt5_all")],
            [InlineKeyboardButton("平交易所所有仓", callback_data="close_exchange_all")],
            [InlineKeyboardButton("平所有仓", callback_data="close_all")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text("选择平仓选项:", reply_markup=reply_markup)

    async def settings_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """设置命令"""
        user_id = update.effective_user.id

        if user_id not in self.config.get("authorized_users", []):
            await update.message.reply_text("权限不足！")
            return

        settings_text = f"""
当前设置

授权用户: {', '.join(map(str, self.config.get('authorized_users', [])))}

MT5配置:
服务器: {self.config.get('mt5_config', {}).get('server', 'N/A')}
登录: {self.config.get('mt5_config', {}).get('login', 'N/A')}

交易所配置:
交易所: {self.config.get('exchange_config', {}).get('exchange', 'N/A')}
账户: {self.config.get('exchange_config', {}).get('account', 'N/A')}

熔断配置:
启用: {self.config.get('circuit_breaker', {}).get('enabled', False)}
日亏损阈值: {self.config.get('circuit_breaker', {}).get('max_loss_per_day', 0)}
连续亏损次数: {self.config.get('circuit_breaker', {}).get('max_consecutive_losses', 0)}
自动停止交易: {self.config.get('circuit_breaker', {}).get('auto_stop_trading', False)}

每日分析:
启用: {self.config.get('daily_analysis', {}).get('enabled', False)}
报告时间: {self.config.get('daily_analysis', {}).get('report_time', '23:30')}
亏损阈值: {self.config.get('daily_analysis', {}).get('daily_loss_threshold', 0)}
盈利目标: {self.config.get('daily_analysis', {}).get('daily_profit_target', 0)}
"""
        await update.message.reply_text(settings_text)

    async def report_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """生成AI分析报告"""
        user_id = update.effective_user.id

        if user_id not in self.config.get("authorized_users", []):
            await update.message.reply_text("权限不足！")
            return

        await update.message.reply_text("正在生成AI分析报告，请稍候...")

        # 获取今日分析
        analysis = self.profit_analyzer.analyze_daily_performance()

        # 生成AI报告
        report = self.ai_reporter.generate_daily_report(analysis)

        # 检查消息长度
        if len(report) > 4000:
            # 分开发送
            parts = [report[i:i+4000] for i in range(0, len(report), 4000)]
            for part in parts:
                await update.message.reply_text(part)
        else:
            await update.message.reply_text(report)

    async def daily_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """每日盈亏报告命令"""
        user_id = update.effective_user.id

        if user_id not in self.config.get("authorized_users", []):
            await update.message.reply_text("权限不足！")
            return

        args = context.args
        date = args[0] if args else None

        # 检查是否详细版
        detailed = False
        if args and args[-1] == "detailed":
            detailed = True
            if date == "detailed":
                date = None

        # 分析指定日期
        analysis = self.profit_analyzer.analyze_daily_performance(date)

        # 生成TG消息
        tg_message = self.ai_reporter.generate_tg_message(analysis, detailed=detailed)

        await update.message.reply_text(tg_message)

    async def circuit_status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """熔断状态命令"""
        user_id = update.effective_user.id

        if user_id not in self.config.get("authorized_users", []):
            await update.message.reply_text("权限不足！")
            return

        status = self.circuit_breaker.get_status()

        status_text = f"""
熔断保护状态

当前状态: {'已触发' if status['triggered'] else '正常'}

当日统计:
总亏损: {status.get('current_daily_loss', 0):.2f}
总盈利: {status.get('current_daily_profit', 0):.2f}
净盈亏: {status.get('current_daily_net', 0):.2f}
交易次数: {status.get('trade_count_today', 0)}

阈值设置:
日亏损阈值: {status.get('max_daily_loss', 0):.2f}
连续亏损次数: {status.get('max_consecutive_losses', 0)}

历史记录:
触发次数: {status.get('trigger_count_total', 0)}
恢复次数: {status.get('recover_count_total', 0)}
最后触发: {status.get('last_trigger_time', '从未')}
最后恢复: {status.get('last_recover_time', '从未')}
"""

        if status["triggered"]:
            status_text += f"\n⚠️ 熔断已触发！交易已暂停。"
            status_text += f"\n使用 /reset_circuit 手动重置熔断器"

        await update.message.reply_text(status_text)

    async def reset_circuit_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """重置熔断器命令"""
        user_id = update.effective_user.id

        if user_id not in self.config.get("authorized_users", []):
            await update.message.reply_text("权限不足！")
            return

        # 重置熔断器
        self.circuit_breaker.reset()
        await update.message.reply_text("熔断器已重置，可以继续交易")

    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """按钮回调处理"""
        query = update.callback_query
        await query.answer()

        user_id = update.effective_user.id
        if user_id not in self.config.get("authorized_users", []):
            await query.edit_message_text("权限不足！")
            return

        data = query.data

        # 平仓操作
        if data.startswith("close_"):
            if data == "close_mt5_all":
                result = self.mt5_bridge.close_all_positions()
                await query.edit_message_text(f"MT5平仓结果: {result}")
            elif data == "close_exchange_all":
                result = self.exchange_trader.close_all_positions()
                await query.edit_message_text(f"交易所平仓结果: {result}")
            elif data == "close_all":
                mt5_result = self.mt5_bridge.close_all_positions()
                ex_result = self.exchange_trader.close_all_positions()
                await query.edit_message_text(f"MT5: {mt5_result}\n交易所: {ex_result}")

        # 平台选择
        elif data.startswith("platform_"):
            platform = data.replace("platform_", "")
            self.user_sessions[user_id] = {"platform": platform}

            # 显示交易方向选择
            keyboard = [
                [InlineKeyboardButton("买入", callback_data=f"action_{platform}_buy")],
                [InlineKeyboardButton("卖出", callback_data=f"action_{platform}_sell")],
                [InlineKeyboardButton("取消", callback_data="cancel")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(f"选择交易方向 ({platform}):", reply_markup=reply_markup)

        # 交易操作
        elif data.startswith("action_"):
            _, platform, action = data.split("_")
            self.user_sessions[user_id]["action"] = action
            await query.edit_message_text(f"请输入交易品种 (如: XAUUSD, BTCUSDT):")

        elif data == "cancel":
            self.user_sessions.pop(user_id, None)
            await query.edit_message_text("已取消交易")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理文本消息"""
        user_id = update.effective_user.id
        text = update.message.text.strip()

        if user_id not in self.user_sessions:
            await update.message.reply_text("请先使用 /trade 命令开始交易")
            return

        session = self.user_sessions[user_id]
        platform = session.get("platform")
        action = session.get("action")

        # 检查熔断状态
        if self.circuit_breaker.is_triggered():
            await update.message.reply_text("熔断已触发，暂停交易！")
            return

        # 简单的交易流程：symbol -> amount -> price
        if "symbol" not in session:
            session["symbol"] = text.upper()
            await update.message.reply_text(f"品种: {text.upper()}\n请输入交易数量:")
        elif "amount" not in session:
            try:
                session["amount"] = float(text)
                await update.message.reply_text(f"数量: {text}\n请输入价格 (或输入 'market' 使用市价):")
            except ValueError:
                await update.message.reply_text("无效的数量，请重新输入:")
        elif "price" not in session:
            price = None if text.lower() == "market" else float(text)
            session["price"] = price

            # 执行交易
            if platform == "mt5":
                result = self.mt5_bridge.execute_trade(
                    session["symbol"],
                    action,
                    session["amount"],
                    price
                )
            else:
                result = self.exchange_trader.execute_trade(
                    session["symbol"],
                    action,
                    session["amount"],
                    price
                )

            # 清除会话
            self.user_sessions.pop(user_id, None)

            await update.message.reply_text(f"交易结果: {result}")

            # 记录到熔断器
            if result.get("success"):
                profit = 0  # 这里应该是实际盈亏
                self.circuit_breaker.record_trade(
                    session["symbol"],
                    action,
                    profit
                )

            # 检查是否需要发送警报
            await self._check_and_send_alerts(result, session, user_id)

    async def _check_and_send_alerts(self, trade_result: Dict, session: Dict, user_id: int):
        """检查并发送交易警报"""
        if not trade_result.get("success"):
            return

        # 检查熔断状态
        if self.circuit_breaker.is_triggered():
            alert_msg = self.ai_reporter.generate_alert_message("circuit_breaker", {
                "current_loss": self.circuit_breaker.get_status()["current_daily_loss"],
                "threshold": self.config.get("circuit_breaker", {}).get("max_loss_per_day")
            })
            await self._send_alert(user_id, alert_msg)
            return

        # 检查风险等级
        risk_level = self.circuit_breaker.get_risk_level()
        if risk_level in ["high", "critical"]:
            alert_msg = self.ai_reporter.generate_alert_message("high_risk", {
                "level": risk_level,
                "consecutive_losses": self.circuit_breaker.get_status().get("consecutive_losses", 0)
            })
            await self._send_alert(user_id, alert_msg)

    async def _send_alert(self, user_id: int, message: str):
        """发送警报消息"""
        try:
            # 获取chat_id
            chat_id = self.config.get("telegram_chat_id")
            if not chat_id:
                # 尝试从用户ID获取
                return

            await self.app.bot.send_message(chat_id=chat_id, text=message)
            logger.info(f"已发送警报: {message[:50]}...")
        except Exception as e:
            logger.error(f"发送警报失败: {e}")

    async def send_daily_report(self, context: ContextTypes.DEFAULT_TYPE):
        """定时发送每日报告"""
        logger.info("开始生成每日盈亏报告...")

        # 分析今日
        analysis = self.profit_analyzer.analyze_daily_performance()

        # 生成报告
        report = self.ai_reporter.generate_daily_report(analysis)

        # 发送到所有授权用户
        chat_id = self.config.get("telegram_chat_id")

        if chat_id:
            try:
                # 如果报告太长，分开发送
                if len(report) > 4000:
                    parts = [report[i:i+4000] for i in range(0, len(report), 4000)]
                    for part in parts:
                        await context.bot.send_message(chat_id=chat_id, text=part)
                else:
                    await context.bot.send_message(chat_id=chat_id, text=report)

                logger.info("每日报告已发送")
            except Exception as e:
                logger.error(f"发送每日报告失败: {e}")

    async def check_circuit_status(self, context: ContextTypes.DEFAULT_TYPE):
        """定时检查熔断状态"""
        status = self.circuit_breaker.get_status()

        if status["triggered"] and self.config.get("circuit_breaker", {}).get("auto_stop_trading"):
            logger.warning("熔断已触发，自动停止交易")

    def start(self):
        """启动机器人"""
        logger.info("Telegram增强交易机器人启动中...")
        self.app.run_polling(allowed_updates=Update.ALL_TYPES)


def main():
    """主函数"""
    bot = EnhancedTelegramBot()
    bot.start()


if __name__ == "__main__":
    main()
