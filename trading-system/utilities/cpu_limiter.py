#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CPU智能限制模块 - 防止长期占用过高CPU
"""

import os
import time
import psutil
import logging
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from pathlib import Path
import json

logger = logging.getLogger(__name__)


class CPULimiter:
    """CPU智能限制器"""

    def __init__(self, config_path: str = None):
        self.config = self._load_config(config_path)
        self.base_dir = Path(__file__).parent.parent
        self.state_file = self.base_dir / "logs" / "cpu_limiter_state.json"
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

        # CPU限制配置
        self.max_cpu_percent = self.config.get("max_cpu_percent", 85)
        self.warning_cpu_percent = self.config.get("warning_cpu_percent", 80)
        self.check_interval = self.config.get("check_interval_seconds", 30)
        self.high_cpu_window = self.config.get("high_cpu_window_minutes", 30)
        self.cooldown_duration = self.config.get("cooldown_duration_seconds", 300)

        # 状态
        self.monitoring = False
        self.monitor_thread = None
        self.throttling = False
        self.cpu_history = []
        self.high_cpu_start_time = None
        self.last_throttle_time = None

        # 加载状态
        self._load_state()

    def _load_config(self, config_path: str = None) -> Dict:
        """加载配置文件"""
        if not config_path:
            config_path = Path(__file__).parent.parent / "config" / "cpu_limiter_config.json"

        if config_path and os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)

        # 默认配置
        return {
            "max_cpu_percent": 85,
            "warning_cpu_percent": 80,
            "check_interval_seconds": 30,
            "high_cpu_window_minutes": 30,
            "cooldown_duration_seconds": 300,
            "auto_throttle": True,
            "notify_on_throttle": True,
            "throttle_actions": {
                "reduce_ai_requests": True,
                "increase_sleep_time": True,
                "pause_non_critical": True
            }
        }

    def _load_state(self):
        """加载持久化状态"""
        try:
            if self.state_file.exists():
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                    self.throttling = state.get("throttling", False)
                    if state.get("high_cpu_start_time"):
                        self.high_cpu_start_time = datetime.fromisoformat(state["high_cpu_start_time"])
                    if state.get("last_throttle_time"):
                        self.last_throttle_time = datetime.fromisoformat(state["last_throttle_time"])
        except Exception as e:
            logger.error(f"加载CPU限制器状态失败: {e}")

    def _save_state(self):
        """保存持久化状态"""
        try:
            state = {
                "throttling": self.throttling,
                "high_cpu_start_time": self.high_cpu_start_time.isoformat() if self.high_cpu_start_time else None,
                "last_throttle_time": self.last_throttle_time.isoformat() if self.last_throttle_time else None,
                "timestamp": datetime.now().isoformat()
            }
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"保存CPU限制器状态失败: {e}")

    def get_current_cpu(self) -> float:
        """获取当前CPU使用率"""
        return psutil.cpu_percent(interval=1)

    def get_process_cpu(self) -> float:
        """获取当前进程CPU使用率"""
        try:
            process = psutil.Process(os.getpid())
            return process.cpu_percent(interval=1)
        except Exception:
            return 0.0

    def check_cpu_status(self) -> Dict:
        """检查CPU状态"""
        current_cpu = self.get_current_cpu()
        process_cpu = self.get_process_cpu()

        # 记录CPU历史
        self.cpu_history.append({
            "timestamp": datetime.now(),
            "system_cpu": current_cpu,
            "process_cpu": process_cpu
        })

        # 保持最近1小时的历史
        cutoff_time = datetime.now() - timedelta(hours=1)
        self.cpu_history = [h for h in self.cpu_history if h["timestamp"] > cutoff_time]

        status = {
            "current_cpu": current_cpu,
            "process_cpu": process_cpu,
            "warning": False,
            "critical": False,
            "throttling": self.throttling,
            "message": "CPU使用正常"
        }

        # 检查是否需要告警
        if current_cpu >= self.max_cpu_percent:
            status["critical"] = True
            status["message"] = f"CPU使用率过高: {current_cpu:.1f}%"

            # 记录高CPU开始时间
            if not self.high_cpu_start_time:
                self.high_cpu_start_time = datetime.now()

            # 检查是否需要限制
            if self.high_cpu_start_time:
                duration = (datetime.now() - self.high_cpu_start_time).total_seconds() / 60
                if duration >= self.high_cpu_window:
                    if self.config.get("auto_throttle", True) and not self.throttling:
                        self._activate_throttle()
                        status["message"] = f"CPU持续高负载{duration:.1f}分钟，已启动限制"

        elif current_cpu >= self.warning_cpu_percent:
            status["warning"] = True
            status["message"] = f"CPU使用率较高: {current_cpu:.1f}%"

        else:
            # CPU恢复正常
            if self.high_cpu_start_time:
                self.high_cpu_start_time = None
                self._save_state()

            # 检查是否可以解除限制
            if self.throttling and self.last_throttle_time:
                cooldown_elapsed = (datetime.now() - self.last_throttle_time).total_seconds()
                if cooldown_elapsed >= self.cooldown_duration:
                    self._deactivate_throttle()
                    status["message"] = "CPU恢复正常，已解除限制"

        return status

    def _activate_throttle(self):
        """激活CPU限制"""
        if self.throttling:
            return

        self.throttling = True
        self.last_throttle_time = datetime.now()
        self._save_state()

        logger.warning("CPU限制已激活")

        # 发送通知
        if self.config.get("notify_on_throttle", True):
            self._send_notification("CPU限制激活", f"系统CPU使用率持续过高，已启动智能限制")

    def _deactivate_throttle(self):
        """解除CPU限制"""
        if not self.throttling:
            return

        self.throttling = False
        self._save_state()

        logger.info("CPU限制已解除")

        # 发送通知
        if self.config.get("notify_on_throttle", True):
            self._send_notification("CPU限制解除", "系统CPU使用率恢复正常")

    def _send_notification(self, title: str, message: str):
        """发送通知（可以集成到Telegram）"""
        # TODO: 集成Telegram通知
        logger.info(f"[通知] {title}: {message}")

    def get_throttle_config(self) -> Dict:
        """获取当前限制配置"""
        if not self.throttling:
            return {
                "throttling": False,
                "actions": {}
            }

        return {
            "throttling": True,
            "actions": {
                "reduce_ai_requests": self.config.get("throttle_actions", {}).get("reduce_ai_requests", True),
                "increase_sleep_time": self.config.get("throttle_actions", {}).get("increase_sleep_time", True),
                "pause_non_critical": self.config.get("throttle_actions", {}).get("pause_non_critical", True)
            },
            "recommendations": [
                "减少AI模型调用频率",
                "增加操作间隔时间",
                "暂停非关键任务",
                "降低并发处理数量"
            ]
        }

    def should_throttle_operation(self, operation_type: str = "general") -> bool:
        """判断是否应该限制某个操作"""
        if not self.throttling:
            return False

        throttle_actions = self.config.get("throttle_actions", {})

        # 根据操作类型判断
        if operation_type == "ai_request" and throttle_actions.get("reduce_ai_requests", True):
            return True
        elif operation_type == "non_critical" and throttle_actions.get("pause_non_critical", True):
            return True

        return False

    def get_sleep_multiplier(self) -> float:
        """获取sleep时间乘数"""
        if not self.throttling:
            return 1.0

        if self.config.get("throttle_actions", {}).get("increase_sleep_time", True):
            return 2.0  # 将sleep时间翻倍

        return 1.0

    def monitor_loop(self):
        """监控循环"""
        logger.info("CPU限制器监控启动")

        while self.monitoring:
            try:
                status = self.check_cpu_status()

                # 记录日志
                if status["critical"]:
                    logger.warning(status["message"])
                elif status["warning"]:
                    logger.info(status["message"])

                # 等待下一次检查
                time.sleep(self.check_interval)

            except Exception as e:
                logger.error(f"CPU监控循环错误: {e}")
                time.sleep(self.check_interval)

        logger.info("CPU限制器监控已停止")

    def start(self):
        """启动监控"""
        if self.monitoring:
            logger.warning("CPU限制器已在运行中")
            return

        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self.monitor_loop, daemon=True)
        self.monitor_thread.start()
        logger.info(f"CPU限制器已启动，检查间隔: {self.check_interval}秒")

    def stop(self):
        """停止监控"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        logger.info("CPU限制器已停止")

    def get_statistics(self) -> Dict:
        """获取统计信息"""
        if not self.cpu_history:
            return {
                "avg_cpu": 0,
                "max_cpu": 0,
                "min_cpu": 0,
                "samples": 0
            }

        recent_history = [h for h in self.cpu_history if h["timestamp"] > datetime.now() - timedelta(minutes=30)]

        return {
            "avg_cpu": sum(h["system_cpu"] for h in recent_history) / len(recent_history),
            "max_cpu": max(h["system_cpu"] for h in recent_history),
            "min_cpu": min(h["system_cpu"] for h in recent_history),
            "avg_process_cpu": sum(h["process_cpu"] for h in recent_history) / len(recent_history),
            "samples": len(recent_history),
            "time_window_minutes": 30
        }

    def get_summary(self) -> Dict:
        """获取摘要信息"""
        status = self.check_cpu_status()
        stats = self.get_statistics()

        return {
            "current_status": status,
            "statistics": stats,
            "throttle_config": self.get_throttle_config(),
            "config": {
                "max_cpu_percent": self.max_cpu_percent,
                "warning_cpu_percent": self.warning_cpu_percent,
                "high_cpu_window_minutes": self.high_cpu_window
            }
        }


# 创建全局实例
cpu_limiter = CPULimiter()


def main():
    """测试主函数"""
    import logging
    logging.basicConfig(level=logging.INFO)

    limiter = CPULimiter()

    print("=== CPU限制器测试 ===")
    print(f"当前CPU: {limiter.get_current_cpu():.1f}%")
    print(f"进程CPU: {limiter.get_process_cpu():.1f}%")
    print()

    summary = limiter.get_summary()
    print(json.dumps(summary, indent=2, ensure_ascii=False))

    print("\n=== 启动持续监控 ===")
    print("按 Ctrl+C 停止监控")
    limiter.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n正在停止监控...")
        limiter.stop()
        print("监控已停止")


if __name__ == "__main__":
    main()
