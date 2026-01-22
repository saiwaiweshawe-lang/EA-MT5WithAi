# 紧急熔断功能
# 当亏损达到阈值时自动停止交易

import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class CircuitBreaker:
    """熔断器"""

    def __init__(self, config: Dict, mt5_bridge=None, exchange_trader=None):
        self.config = config
        self.enabled = config.get("enabled", True)
        self.mt5_bridge = mt5_bridge
        self.exchange_trader = exchange_trader

        # 熔断阈值
        self.max_loss_per_day = config.get("max_loss_per_day", -1000)
        self.max_consecutive_losses = config.get("max_consecutive_losses", 5)
        self.max_drawdown_pct = config.get("max_drawdown_pct", 10)  # 最大回撤百分比

        # 自动操作
        self.auto_stop_trading = config.get("auto_stop_trading", True)
        self.notify_on_trigger = config.get("notify_on_trigger", True)
        self.auto_recover_after_hours = config.get("auto_recover_after_hours", 24)

        # 状态文件
        self.state_file = config.get("state_file", "logs/circuit_state.json")

        # 加载状态
        self.state = self._load_state()

    def _load_state(self) -> Dict:
        """加载状态"""
        Path(os.path.dirname(self.state_file)).mkdir(parents=True, exist_ok=True)

        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                    # 检查是否需要重置（跨天）
                    last_date = state.get("last_date", "")
                    today = datetime.now().strftime("%Y-%m-%d")

                    if last_date != today:
                        # 跨天重置
                        return self._reset_state()
                    return state
            except Exception as e:
                logger.error(f"加载熔断状态失败: {e}")

        return self._reset_state()

    def _reset_state(self) -> Dict:
        """重置状态"""
        return {
            "triggered": False,
            "last_date": datetime.now().strftime("%Y-%m-%d"),
            "current_daily_loss": 0,
            "current_daily_profit": 0,
            "current_daily_net": 0,
            "trade_count_today": 0,
            "consecutive_losses": 0,
            "max_consecutive_losses": 0,
            "trigger_count_total": 0,
            "recover_count_total": 0,
            "last_trigger_time": None,
            "last_recover_time": None,
            "trades_today": [],
            "daily_high_balance": None,
            "max_daily_drawdown": 0
        }

    def _save_state(self):
        """保存状态"""
        try:
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(self.state, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"保存熔断状态失败: {e}")

    def get_status(self) -> Dict:
        """获取熔断状态"""
        # 检查是否跨天需要重置
        today = datetime.now().strftime("%Y-%m-%d")
        if self.state.get("last_date", "") != today:
            self.state = self._reset_state()
            self._save_state()

        return {
            "triggered": self.state["triggered"],
            "enabled": self.enabled,
            "current_daily_loss": self.state["current_daily_loss"],
            "current_daily_profit": self.state["current_daily_profit"],
            "current_daily_net": self.state["current_daily_net"],
            "trade_count_today": self.state["trade_count_today"],
            "consecutive_losses": self.state["consecutive_losses"],
            "max_daily_loss": self.max_loss_per_day,
            "max_consecutive_losses": self.max_consecutive_losses,
            "trigger_count_total": self.state["trigger_count_total"],
            "recover_count_total": self.state["recover_count_total"],
            "last_trigger_time": self.state["last_trigger_time"],
            "last_recover_time": self.state["last_recover_time"]
        }

    def is_triggered(self) -> bool:
        """检查熔断是否触发"""
        if not self.enabled:
            return False

        self._check_auto_recover()
        return self.state["triggered"]

    def can_trade(self) -> bool:
        """检查是否可以交易"""
        if not self.enabled:
            return True

        self._check_auto_recover()
        return not self.state["triggered"]

    def record_trade(self, symbol: str, action: str, profit: float):
        """记录交易"""
        if not self.enabled:
            return

        # 更新当日统计
        self.state["trade_count_today"] += 1
        self.state["trades_today"].append({
            "symbol": symbol,
            "action": action,
            "profit": profit,
            "time": datetime.now().isoformat()
        })

        # 更新盈亏
        if profit > 0:
            self.state["current_daily_profit"] += profit
            self.state["consecutive_losses"] = 0
        else:
            self.state["current_daily_loss"] += profit
            self.state["consecutive_losses"] += 1
            if self.state["consecutive_losses"] > self.state["max_consecutive_losses"]:
                self.state["max_consecutive_losses"] = self.state["consecutive_losses"]

        # 更新净盈亏
        self.state["current_daily_net"] = (
            self.state["current_daily_profit"] + self.state["current_daily_loss"]
        )

        # 更新最大回撤
        if profit > 0:
            # 盈利时更新最高点
            if self.state["daily_high_balance"] is None:
                self.state["daily_high_balance"] = profit
            else:
                self.state["daily_high_balance"] = max(
                    self.state["daily_high_balance"],
                    self.state["current_daily_net"]
                )

            # 计算回撤
            if self.state["daily_high_balance"] > 0:
                drawdown = (self.state["daily_high_balance"] - self.state["current_daily_net"])
                if self.state["daily_high_balance"] > 0:
                    drawdown_pct = drawdown / self.state["daily_high_balance"] * 100
                    self.state["max_daily_drawdown"] = max(
                        self.state["max_daily_drawdown"],
                        drawdown_pct
                    )

        # 检查是否触发熔断
        triggered = self._check_triggers()

        if triggered != self.state["triggered"]:
            if triggered:
                self._on_trigger()
            else:
                self._on_recover()

        self._save_state()

        return triggered

    def _check_triggers(self) -> bool:
        """检查熔断触发条件"""
        triggers = []

        # 条件1: 日亏损达到阈值
        if self.state["current_daily_loss"] <= self.max_loss_per_day:
            triggers.append("daily_loss_threshold")

        # 条件2: 连续亏损达到次数
        if self.state["consecutive_losses"] >= self.max_consecutive_losses:
            triggers.append("consecutive_losses")

        # 条件3: 最大回撤超过阈值
        if self.state["max_daily_drawdown"] >= self.max_drawdown_pct:
            triggers.append("max_drawdown")

        # 条件4: 超过当日允许的最大交易次数且亏损
        if (self.state["trade_count_today"] > 50 and
            self.state["current_daily_net"] < 0):
            triggers.append("excessive_trades")

        # 只要有一个条件满足就触发
        self.state["trigger_reasons"] = triggers
        return len(triggers) > 0

    def _on_trigger(self):
        """熔断触发时执行"""
        logger.warning(f"熔断触发！原因: {self.state['trigger_reasons']}")

        self.state["triggered"] = True
        self.state["last_trigger_time"] = datetime.now().isoformat()
        self.state["trigger_count_total"] += 1

        # 自动停止交易
        if self.auto_stop_trading:
            self._stop_all_trading()

    def _on_recover(self):
        """熔断恢复时执行"""
        logger.info("熔断已恢复")

        self.state["triggered"] = False
        self.state["last_recover_time"] = datetime.now().isoformat()
        self.state["recover_count_total"] += 1
        self.state["trigger_reasons"] = []

    def _check_auto_recover(self):
        """检查是否自动恢复"""
        if not self.state["triggered"]:
            return

        last_trigger = self.state.get("last_trigger_time")
        if not last_trigger:
            return

        try:
            trigger_time = datetime.fromisoformat(last_trigger)
            elapsed = (datetime.now() - trigger_time).total_seconds() / 3600  # 转换为小时

            if elapsed >= self.auto_recover_after_hours:
                logger.info(f"熔断已超过 {self.auto_recover_after_hours} 小时，自动恢复")
                self._on_recover()
                self._save_state()
        except Exception as e:
            logger.error(f"检查自动恢复失败: {e}")

    def _stop_all_trading(self):
        """停止所有交易"""
        logger.info("停止所有交易...")

        # 关闭所有MT5持仓
        if self.mt5_bridge:
            try:
                result = self.mt5_bridge.close_all_positions()
                logger.info(f"MT5平仓: {result}")
            except Exception as e:
                logger.error(f"MT5平仓失败: {e}")

        # 关闭所有交易所持仓
        if self.exchange_trader:
            try:
                result = self.exchange_trader.close_all_positions()
                logger.info(f"交易所平仓: {result}")
            except Exception as e:
                logger.error(f"交易所平仓失败: {e}")

    def reset(self):
        """手动重置熔断器"""
        logger.info("手动重置熔断器")
        self.state = self._reset_state()
        self._save_state()

    def get_risk_level(self) -> str:
        """获取当前风险等级"""
        if self.state["triggered"]:
            return "critical"

        # 计算风险分数
        risk_score = 0

        # 日亏损接近阈值
        loss_ratio = abs(self.state["current_daily_loss"]) / abs(self.max_loss_per_day)
        if loss_ratio > 0.8:
            risk_score += 30
        elif loss_ratio > 0.5:
            risk_score += 15
        elif loss_ratio > 0.2:
            risk_score += 5

        # 连续亏损
        consecutive_ratio = self.state["consecutive_losses"] / self.max_consecutive_losses
        if consecutive_ratio >= 1:
            risk_score += 40
        elif consecutive_ratio >= 0.6:
            risk_score += 20
        elif consecutive_ratio >= 0.4:
            risk_score += 10

        # 最大回撤
        drawdown_ratio = self.state["max_daily_drawdown"] / self.max_drawdown_pct
        if drawdown_ratio >= 1:
            risk_score += 30
        elif drawdown_ratio >= 0.5:
            risk_score += 15
        elif drawdown_ratio >= 0.2:
            risk_score += 5

        # 根据分数确定风险等级
        if risk_score >= 70:
            return "critical"
        elif risk_score >= 50:
            return "high"
        elif risk_score >= 30:
            return "medium"
        else:
            return "low"

    def get_alert_message(self) -> Optional[str]:
        """获取熔断警报消息"""
        if not self.state["triggered"]:
            return None

        reasons = self.state.get("trigger_reasons", [])

        message = "熔断保护已触发\n\n触发原因:\n"
        for reason in reasons:
            reason_map = {
                "daily_loss_threshold": f"- 日亏损达到阈值: {self.state['current_daily_loss']:.2f} <= {self.max_loss_per_day}",
                "consecutive_losses": f"- 连续亏损次数达到: {self.state['consecutive_losses']} >= {self.max_consecutive_losses}",
                "max_drawdown": f"- 最大回撤超过阈值: {self.state['max_daily_drawdown']:.1f}% >= {self.max_drawdown_pct}%",
                "excessive_trades": f"- 交易次数过多且亏损: {self.state['trade_count_today']} > 50"
            }
            message += reason_map.get(reason, f"- {reason}")

        message += f"\n今日统计:\n"
        message += f"- 净盈亏: {self.state['current_daily_net']:.2f}\n"
        message += f"- 交易次数: {self.state['trade_count_today']}\n"
        message += f"- 连续亏损: {self.state['consecutive_losses']}次\n"

        return message

    def get_recommendation(self) -> str:
        """获取风险建议"""
        risk_level = self.get_risk_level()

        recommendations = {
            "critical": """
建议立即执行以下操作：
1. 停止所有新开仓
2. 评估当前交易策略
3. 检查是否需要调整止损设置
4. 减少下次交易的仓位大小
5. 考虑休息一段时间再交易
""",
            "high": """
建议执行以下操作：
1. 暂停新开仓
2. 严格设置止损
3. 减少仓位大小
4. 审查最近亏损交易的原因
5. 考虑调整交易策略
""",
            "medium": """
建议执行以下操作：
1. 适当减少仓位
2. 确保止损设置合理
3. 密切监控市场变化
4. 避免情绪化交易
5. 继续执行风险控制策略
""",
            "low": """
建议执行以下操作：
1. 保持当前交易策略
2. 定期评估交易表现
3. 继续执行风险管理
4. 记录并分析每笔交易
"""
        }

        return recommendations.get(risk_level, "")

    def get_trades_summary(self) -> Dict:
        """获取交易摘要"""
        trades = self.state.get("trades_today", [])

        if not trades:
            return {
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "best_trade": None,
                "worst_trade": None
            }

        winning_trades = [t for t in trades if t["profit"] > 0]
        losing_trades = [t for t in trades if t["profit"] < 0]

        best_trade = max(trades, key=lambda x: x["profit"]) if trades else None
        worst_trade = min(trades, key=lambda x: x["profit"]) if trades else None

        return {
            "total_trades": len(trades),
            "winning_trades": len(winning_trades),
            "losing_trades": len(losing_trades),
            "best_trade": best_trade,
            "worst_trade": worst_trade,
            "all_trades": trades
        }

    def export_trades(self, filepath: str):
        """导出今日交易"""
        trades = self.state.get("trades_today", [])

        if not trades:
            return False

        Path(os.path.dirname(filepath)).mkdir(parents=True, exist_ok=True)

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("时间,品种,方向,盈亏\n")
            for trade in trades:
                f.write(f"{trade['time']},{trade['symbol']},{trade['action']},{trade['profit']}\n")

        logger.info(f"交易记录已导出: {filepath}")
        return True

    def get_config_summary(self) -> Dict:
        """获取配置摘要"""
        return {
            "enabled": self.enabled,
            "auto_stop_trading": self.auto_stop_trading,
            "notify_on_trigger": self.notify_on_trigger,
            "auto_recover_after_hours": self.auto_recover_after_hours,
            "max_loss_per_day": self.max_loss_per_day,
            "max_consecutive_losses": self.max_consecutive_losses,
            "max_drawdown_pct": self.max_drawdown_pct
        }


def create_circuit_breaker(config: Dict,
                          mt5_bridge=None,
                          exchange_trader=None) -> CircuitBreaker:
    """创建熔断器"""
    return CircuitBreaker(config, mt5_bridge, exchange_trader)


if __name__ == "__main__":
    # 测试代码
    config = {
        "enabled": True,
        "max_loss_per_day": -1000,
        "max_consecutive_losses": 5,
        "max_drawdown_pct": 10,
        "auto_stop_trading": True,
        "notify_on_trigger": True,
        "auto_recover_after_hours": 24,
        "state_file": "logs/circuit_state.json"
    }

    breaker = CircuitBreaker(config)

    # 模拟一些交易
    print("熔断器测试:")
    print(f"可以交易: {breaker.can_trade()}")

    # 模拟连续亏损
    for i in range(3):
        breaker.record_trade("XAUUSD", "sell", -100)
        print(f"交易 {i+1}: 可以交易={breaker.can_trade()}, 连续亏损={breaker.get_status()['consecutive_losses']}")

    # 检查状态
    status = breaker.get_status()
    print(f"\n当前状态: {status}")
    print(f"风险等级: {breaker.get_risk_level()}")
