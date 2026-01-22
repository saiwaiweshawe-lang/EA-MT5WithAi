#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Telegram通知工具
"""

import os
import json
import logging
import requests
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Telegram通知器"""

    def __init__(self, config_path: str = None):
        self.base_dir = Path(__file__).parent.parent

        # 加载Telegram配置
        if config_path is None:
            config_path = self.base_dir / "config" / "telegram_config.json"

        self.config_path = Path(config_path)
        self.config = self._load_config()

        self.bot_token = self.config.get("bot_token", "")
        self.chat_id = self.config.get("chat_id", "")

    def _load_config(self) -> dict:
        """加载配置"""
        if not self.config_path.exists():
            logger.warning(f"Telegram配置文件不存在: {self.config_path}")
            return {}

        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"加载Telegram配置失败: {e}")
            return {}

    def send_message(self, message: str, parse_mode: str = "Markdown") -> bool:
        """
        发送消息

        Args:
            message: 消息内容
            parse_mode: 解析模式 (Markdown, HTML)

        Returns:
            是否发送成功
        """
        if not self.bot_token or not self.chat_id:
            logger.warning("Telegram配置未完成,跳过通知")
            return False

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"

        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": parse_mode
        }

        try:
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"发送Telegram消息失败: {e}")
            return False

    def send_alert(self, level: str, title: str, message: str) -> bool:
        """
        发送告警消息

        Args:
            level: 告警级别 (info, warning, critical)
            title: 告警标题
            message: 告警消息

        Returns:
            是否发送成功
        """
        # 根据级别选择图标
        icons = {
            "info": "ℹ️",
            "warning": "⚠️",
            "critical": "🚨"
        }

        icon = icons.get(level, "📢")

        # 构造消息
        alert_message = f"{icon} *{level.upper()}*\n\n"
        alert_message += f"*{title}*\n\n"
        alert_message += f"{message}"

        return self.send_message(alert_message)


# 全局实例
_notifier: Optional[TelegramNotifier] = None


def get_notifier() -> TelegramNotifier:
    """获取通知器实例"""
    global _notifier
    if _notifier is None:
        _notifier = TelegramNotifier()
    return _notifier


def send_alert(level: str, title: str, message: str) -> bool:
    """快捷函数:发送告警"""
    return get_notifier().send_alert(level, title, message)


def send_message(message: str) -> bool:
    """快捷函数:发送消息"""
    return get_notifier().send_message(message)


if __name__ == "__main__":
    # 测试
    logging.basicConfig(level=logging.INFO)

    notifier = TelegramNotifier()

    print("测试Telegram通知...")
    success = notifier.send_alert(
        "info",
        "系统测试",
        "这是一条测试消息"
    )

    if success:
        print("✓ 发送成功")
    else:
        print("✗ 发送失败")
