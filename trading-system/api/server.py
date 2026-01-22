# 域名远程控制API服务器
# 通过Web API接收来自域名的交易指令，并转发到Telegram/MT5

import os
import json
import logging
import psutil
import platform
from datetime import datetime
from typing import Dict, Optional
from flask import Flask, request, jsonify
from flask_cors import CORS
import threading
import time

from mt5_bridge import MT5Bridge, EAManager
from exchange_trader import ExchangeTrader

# 配置日志
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# 全局变量
mt5_bridge: Optional[MT5Bridge] = None
exchange_trader: Optional[ExchangeTrader] = None
ea_manager: Optional[EAManager] = None
config: Dict = {}

# 命令队列（供MT5 EA查询）
pending_commands = {}


def load_config(config_path: str = "config/server_config.json") -> Dict:
    """加载配置文件"""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning(f"配置文件 {config_path} 未找到")
        return {
            "server": {
                "host": "0.0.0.0",
                "port": 5000,
                "debug": True
            },
            "security": {
                "api_keys": ["your-secret-api-key"],
                "allowed_ips": ["0.0.0.0/0"]
            },
            "mt5": {},
            "exchange": {}
        }


def init_trading_systems():
    """初始化交易系统"""
    global mt5_bridge, exchange_trader, ea_manager

    # 初始化MT5桥接
    if config.get("mt5"):
        mt5_bridge = MT5Bridge(config["mt5"])
        ea_manager = EAManager("config/ea_config.json")
        logger.info("MT5系统初始化完成")

    # 初始化交易所交易
    if config.get("exchange"):
        exchange_trader = ExchangeTrader(config["exchange"])
        logger.info(f"{config['exchange'].get('exchange', '交易所')}系统初始化完成")


def verify_api_key(api_key: str) -> bool:
    """验证API密钥"""
    allowed_keys = config.get("security", {}).get("api_keys", [])
    return api_key in allowed_keys


def verify_ip(client_ip: str) -> bool:
    """验证IP地址"""
    allowed_ips = config.get("security", {}).get("allowed_ips", ["0.0.0.0/0"])
    # 简单实现，实际应使用IP范围匹配
    return True


# ==================== API 路由 ====================

@app.route("/api/health", methods=["GET"])
def health_check():
    """增强的健康检查"""
    try:
        # 获取系统资源信息
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')

        # 获取进程信息
        process = psutil.Process(os.getpid())
        process_memory = process.memory_info().rss / (1024 * 1024)  # MB

        return jsonify({
            "status": "ok",
            "timestamp": datetime.now().isoformat(),
            "services": {
                "mt5": mt5_bridge is not None,
                "exchange": exchange_trader is not None,
                "ea_manager": ea_manager is not None
            },
            "system": {
                "platform": platform.system(),
                "python_version": platform.python_version(),
                "cpu_percent": cpu_percent,
                "memory": {
                    "total_mb": round(memory.total / (1024 * 1024), 2),
                    "available_mb": round(memory.available / (1024 * 1024), 2),
                    "used_percent": memory.percent
                },
                "disk": {
                    "total_gb": round(disk.total / (1024 * 1024 * 1024), 2),
                    "free_gb": round(disk.free / (1024 * 1024 * 1024), 2),
                    "used_percent": disk.percent
                },
                "process_memory_mb": round(process_memory, 2)
            },
            "command_queue": {
                "active_queues": len(pending_commands),
                "total_pending": sum(len(q) for q in pending_commands.values())
            }
        })
    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        return jsonify({
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500


@app.route("/api/command", methods=["GET"])
def get_command():
    """
    获取待执行命令 (供MT5 EA查询)
    参数: symbol, magic
    """
    symbol = request.args.get("symbol", "XAUUSD")
    magic = int(request.args.get("magic", "234000"))

    key = f"{symbol}_{magic}"

    if key in pending_commands and pending_commands[key]:
        command = pending_commands[key].pop(0)
        return jsonify({"command": command})
    else:
        return jsonify({"command": ""})


@app.route("/api/status", methods=["POST"])
def receive_status():
    """接收MT5 EA状态报告"""
    try:
        data = request.get_json()
        logger.info(f"收到状态报告: {data}")
        # 可以存储到数据库或发送到Telegram
        return jsonify({"status": "received"})
    except Exception as e:
        logger.error(f"处理状态失败: {e}")
        return jsonify({"error": str(e)}), 400


@app.route("/api/mt5/trade", methods=["POST"])
def mt5_trade():
    """
    执行MT5交易
    Body:
        {
            "api_key": "your-secret-key",
            "symbol": "XAUUSD",
            "action": "buy/sell",
            "lot_size": 0.01,
            "price": null (市价)
        }
    """
    if not mt5_bridge:
        return jsonify({"error": "MT5服务未初始化"}), 503

    try:
        data = request.get_json()

        # 验证API密钥
        if not verify_api_key(data.get("api_key", "")):
            return jsonify({"error": "无效的API密钥"}), 401

        # 验证IP
        if not verify_ip(request.remote_addr):
            return jsonify({"error": "IP地址不被允许"}), 403

        symbol = data.get("symbol", "XAUUSD")
        action = data.get("action")
        lot_size = float(data.get("lot_size", 0.01))
        price = data.get("price")

        result = mt5_bridge.execute_trade(symbol, action, lot_size, price)

        return jsonify(result)

    except Exception as e:
        logger.error(f"MT5交易失败: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/mt5/positions", methods=["GET"])
def mt5_positions():
    """获取MT5持仓"""
    if not mt5_bridge:
        return jsonify({"error": "MT5服务未初始化"}), 503

    try:
        api_key = request.headers.get("X-API-Key", request.args.get("api_key", ""))
        if not verify_api_key(api_key):
            return jsonify({"error": "无效的API密钥"}), 401

        symbol = request.args.get("symbol")
        positions = mt5_bridge.get_positions(symbol)

        return jsonify({"positions": positions})

    except Exception as e:
        logger.error(f"获取持仓失败: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/mt5/close", methods=["POST"])
def mt5_close():
    """
    平MT5持仓
    Body:
        {
            "api_key": "your-secret-key",
            "symbol": "XAUUSD" (可选，不指定则平所有仓),
            "ticket": null (指定ticket只平单个)
        }
    """
    if not mt5_bridge:
        return jsonify({"error": "MT5服务未初始化"}), 503

    try:
        data = request.get_json()

        if not verify_api_key(data.get("api_key", "")):
            return jsonify({"error": "无效的API密钥"}), 401

        symbol = data.get("symbol")
        ticket = data.get("ticket")

        if ticket:
            result = mt5_bridge.close_position(ticket)
        elif symbol:
            positions = mt5_bridge.get_positions(symbol)
            for pos in positions:
                mt5_bridge.close_position(pos["ticket"])
            result = {"success": True, "message": f"已平{symbol}所有持仓"}
        else:
            result = mt5_bridge.close_all_positions()

        return jsonify(result)

    except Exception as e:
        logger.error(f"平仓失败: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/mt5/strategy", methods=["POST"])
def mt5_strategy():
    """
    运行MT5策略
    Body:
        {
            "api_key": "your-secret-key",
            "strategy": "gold"
        }
    """
    if not ea_manager:
        return jsonify({"error": "EA管理器未初始化"}), 503

    try:
        data = request.get_json()

        if not verify_api_key(data.get("api_key", "")):
            return jsonify({"error": "无效的API密钥"}), 401

        strategy_name = data.get("strategy", "gold")
        result = ea_manager.run_strategy(strategy_name)

        return jsonify(result)

    except Exception as e:
        logger.error(f"策略执行失败: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/exchange/trade", methods=["POST"])
def exchange_trade():
    """
    执行交易所交易
    Body:
        {
            "api_key": "your-secret-key",
            "symbol": "BTCUSDT",
            "side": "buy/sell",
            "amount": 0.001,
            "price": null (市价)
        }
    """
    if not exchange_trader:
        return jsonify({"error": "交易所服务未初始化"}), 503

    try:
        data = request.get_json()

        if not verify_api_key(data.get("api_key", "")):
            return jsonify({"error": "无效的API密钥"}), 401

        symbol = data.get("symbol", "BTCUSDT")
        side = data.get("side")
        amount = float(data.get("amount", 0.001))
        price = data.get("price")

        result = exchange_trader.execute_trade(symbol, side, amount, price)

        return jsonify(result)

    except Exception as e:
        logger.error(f"交易所交易失败: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/exchange/positions", methods=["GET"])
def exchange_positions():
    """获取交易所持仓"""
    if not exchange_trader:
        return jsonify({"error": "交易所服务未初始化"}), 503

    try:
        api_key = request.headers.get("X-API-Key", request.args.get("api_key", ""))
        if not verify_api_key(api_key):
            return jsonify({"error": "无效的API密钥"}), 401

        symbol = request.args.get("symbol")
        positions = exchange_trader.get_positions(symbol)

        return jsonify({"positions": positions})

    except Exception as e:
        logger.error(f"获取持仓失败: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/exchange/close", methods=["POST"])
def exchange_close():
    """
    平交易所持仓
    Body:
        {
            "api_key": "your-secret-key",
            "symbol": "BTCUSDT" (可选)
        }
    """
    if not exchange_trader:
        return jsonify({"error": "交易所服务未初始化"}), 503

    try:
        data = request.get_json()

        if not verify_api_key(data.get("api_key", "")):
            return jsonify({"error": "无效的API密钥"}), 401

        symbol = data.get("symbol")

        if symbol:
            result = exchange_trader.close_position(symbol)
        else:
            result = exchange_trader.close_all_positions()

        return jsonify(result)

    except Exception as e:
        logger.error(f"平仓失败: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/balance", methods=["GET"])
def get_balance():
    """获取所有平台余额"""
    try:
        api_key = request.headers.get("X-API-Key", request.args.get("api_key", ""))
        if not verify_api_key(api_key):
            return jsonify({"error": "无效的API密钥"}), 401

        balances = {}

        if mt5_bridge:
            balances["mt5"] = {
                "balance": mt5_bridge.get_balance(),
                "status": mt5_bridge.get_status()
            }

        if exchange_trader:
            balances["exchange"] = {
                "balance": exchange_trader.get_balance(),
                "status": exchange_trader.get_status()
            }

        return jsonify(balances)

    except Exception as e:
        logger.error(f"获取余额失败: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/send-command", methods=["POST"])
def send_command():
    """
    发送命令到MT5 EA (放入队列供EA查询)
    Body:
        {
            "api_key": "your-secret-key",
            "symbol": "XAUUSD",
            "command": "BUY:0.01" / "SELL:0.01" / "CLOSE_ALL" / "CLOSE_PROFIT"
        }
    """
    try:
        data = request.get_json()

        if not verify_api_key(data.get("api_key", "")):
            return jsonify({"error": "无效的API密钥"}), 401

        symbol = data.get("symbol", "XAUUSD")
        command = data.get("command")
        magic = data.get("magic", "234000")

        key = f"{symbol}_{magic}"

        if key not in pending_commands:
            pending_commands[key] = []

        pending_commands[key].append(command)

        # 限制队列长度
        if len(pending_commands[key]) > 100:
            pending_commands[key] = pending_commands[key][-100:]

        logger.info(f"命令已添加到队列: {symbol} - {command}")

        return jsonify({
            "success": True,
            "message": "命令已添加",
            "queue_length": len(pending_commands[key])
        })

    except Exception as e:
        logger.error(f"发送命令失败: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/overview", methods=["GET"])
def overview():
    """获取系统概览"""
    try:
        api_key = request.headers.get("X-API-Key", request.args.get("api_key", ""))
        if not verify_api_key(api_key):
            return jsonify({"error": "无效的API密钥"}), 401

        overview_data = {
            "timestamp": datetime.now().isoformat(),
            "mt5": {},
            "exchange": {}
        }

        if mt5_bridge:
            overview_data["mt5"] = {
                "status": mt5_bridge.get_status(),
                "positions": mt5_bridge.get_positions()
            }

        if exchange_trader:
            overview_data["exchange"] = {
                "status": exchange_trader.get_status(),
                "positions": exchange_trader.get_positions()
            }

        overview_data["command_queue"] = {
            "queues": len(pending_commands),
            "total_commands": sum(len(q) for q in pending_commands.values())
        }

        return jsonify(overview_data)

    except Exception as e:
        logger.error(f"获取概览失败: {e}")
        return jsonify({"error": str(e)}), 500


# ==================== 错误处理 ====================

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "接口不存在"}), 404


@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "服务器内部错误"}), 500


# ==================== 主程序 ====================

def main():
    """主函数"""
    global config

    # 加载配置
    config = load_config()

    # 初始化交易系统
    init_trading_systems()

    # 启动服务器
    server_config = config.get("server", {})
    host = server_config.get("host", "0.0.0.0")
    port = server_config.get("port", 5000)
    debug = server_config.get("debug", False)

    logger.info(f"服务器启动中... http://{host}:{port}")

    app.run(host=host, port=port, debug=debug, threaded=True)


if __name__ == "__main__":
    main()
