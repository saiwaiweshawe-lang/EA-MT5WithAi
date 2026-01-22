# Telegram Trading Bot
# 支持MT5外汇和币圈交易的Telegram机器人

import logging
import asyncio
import json
import os
from datetime import datetime
from typing import Dict, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
    ConversationHandler
)

# 导入交易模块
from exchange_trader import ExchangeTrader
from mt5_bridge import MT5Bridge

# 配置日志
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# 状态常量
SELECT_PLATFORM, SELECT_ACTION, ENTER_SYMBOL, ENTER_AMOUNT, ENTER_PRICE = range(5)


class TelegramTradingBot:
    """Telegram交易机器人"""

    def __init__(self, config_path: str = "config/bot_config.json"):
        self.config = self._load_config(config_path)
        self.app = Application.builder().token(self.config["telegram_bot_token"]).build()
        self.mt5_bridge = MT5Bridge(self.config.get("mt5_config", {}))
        self.exchange_trader = ExchangeTrader(self.config.get("exchange_config", {}))
        self.user_sessions = {}

        # 注册命令处理器
        self._register_handlers()

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
                "exchange_config": {}
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
        self.app.add_handler(CallbackQueryHandler(self.button_callback))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """启动命令"""
        user_id = update.effective_user.id

        if user_id not in self.config.get("authorized_users", []):
            await update.message.reply_text("您没有权限使用此机器人！")
            return

        welcome_text = """
欢迎使用交易机器人

可用命令：
/start - 启动机器人
/help - 显示帮助信息
/status - 查看系统状态
/balance - 查看账户余额
/positions - 查看待持仓位
/trade - 执行交易
/close - 平仓
/settings - 查看设置
"""
        await update.message.reply_text(welcome_text)

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """帮助命令"""
        help_text = """
交易机器人帮助

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

设置命令：
/settings - 查看当前设置

交易平台：
- MT5: 外汇、黄金、白银等
- Exchange: 币圈交易所（Binance/OKX等）

风险提示：
交易有风险，投资需谨慎！
"""
        await update.message.reply_text(help_text)

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """状态命令"""
        user_id = update.effective_user.id

        if user_id not in self.config.get("authorized_users", []):
            await update.message.reply_text("权限不足！")
            return

        # 获取MT5状态
        mt5_status = self.mt5_bridge.get_status()

        # 获取交易所状态
        exchange_status = self.exchange_trader.get_status()

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
"""
        await update.message.reply_text(settings_text)

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

    def start(self):
        """启动机器人"""
        logger.info("Telegram交易机器人启动中...")
        self.app.run_polling(allowed_updates=Update.ALL_TYPES)


def main():
    """主函数"""
    bot = TelegramTradingBot()
    bot.start()


if __name__ == "__main__":
    main()
