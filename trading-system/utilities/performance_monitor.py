#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
性能监控模块 - 实时监控系统资源使用情况
"""

import os
import sys
import time
import json
import psutil
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List
import threading

# 配置日志
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


class PerformanceMonitor:
    """性能监控器"""

    def __init__(self, config_path: str = None):
        self.config = self._load_config(config_path)
        self.base_dir = Path(__file__).parent.parent
        self.log_dir = self.base_dir / "logs" / "performance"
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.monitoring = False
        self.monitor_thread = None

        # 阈值配置
        self.thresholds = self.config.get("thresholds", {
            "cpu_percent": 80,
            "memory_percent": 85,
            "disk_percent": 90,
            "process_memory_mb": 500
        })

        # 监控间隔（秒）
        self.interval = self.config.get("interval_seconds", 60)

        # 告警历史
        self.alert_history = []

    def _load_config(self, config_path: str = None) -> Dict:
        """加载配置文件"""
        if config_path and os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def get_system_metrics(self) -> Dict:
        """获取系统性能指标"""
        try:
            # CPU使用率
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            cpu_freq = psutil.cpu_freq()

            # 内存使用
            memory = psutil.virtual_memory()

            # 磁盘使用
            disk = psutil.disk_usage('/')

            # 网络IO
            net_io = psutil.net_io_counters()

            # 进程信息
            process = psutil.Process(os.getpid())
            process_info = {
                "pid": process.pid,
                "memory_mb": process.memory_info().rss / (1024 * 1024),
                "cpu_percent": process.cpu_percent(interval=1),
                "num_threads": process.num_threads(),
                "status": process.status()
            }

            return {
                "timestamp": datetime.now().isoformat(),
                "cpu": {
                    "percent": cpu_percent,
                    "count": cpu_count,
                    "freq_mhz": cpu_freq.current if cpu_freq else None
                },
                "memory": {
                    "total_mb": round(memory.total / (1024 * 1024), 2),
                    "available_mb": round(memory.available / (1024 * 1024), 2),
                    "used_mb": round(memory.used / (1024 * 1024), 2),
                    "percent": memory.percent
                },
                "disk": {
                    "total_gb": round(disk.total / (1024 * 1024 * 1024), 2),
                    "used_gb": round(disk.used / (1024 * 1024 * 1024), 2),
                    "free_gb": round(disk.free / (1024 * 1024 * 1024), 2),
                    "percent": disk.percent
                },
                "network": {
                    "bytes_sent_mb": round(net_io.bytes_sent / (1024 * 1024), 2),
                    "bytes_recv_mb": round(net_io.bytes_recv / (1024 * 1024), 2),
                    "packets_sent": net_io.packets_sent,
                    "packets_recv": net_io.packets_recv
                },
                "process": process_info
            }

        except Exception as e:
            logger.error(f"获取系统指标失败: {e}")
            return {}

    def check_thresholds(self, metrics: Dict) -> List[Dict]:
        """检查是否超过阈值"""
        alerts = []

        # 检查CPU
        if metrics["cpu"]["percent"] > self.thresholds["cpu_percent"]:
            alerts.append({
                "type": "cpu",
                "level": "warning",
                "message": f"CPU使用率过高: {metrics['cpu']['percent']}%",
                "value": metrics["cpu"]["percent"],
                "threshold": self.thresholds["cpu_percent"]
            })

        # 检查内存
        if metrics["memory"]["percent"] > self.thresholds["memory_percent"]:
            alerts.append({
                "type": "memory",
                "level": "warning",
                "message": f"内存使用率过高: {metrics['memory']['percent']}%",
                "value": metrics["memory"]["percent"],
                "threshold": self.thresholds["memory_percent"]
            })

        # 检查磁盘
        if metrics["disk"]["percent"] > self.thresholds["disk_percent"]:
            alerts.append({
                "type": "disk",
                "level": "critical",
                "message": f"磁盘使用率过高: {metrics['disk']['percent']}%",
                "value": metrics["disk"]["percent"],
                "threshold": self.thresholds["disk_percent"]
            })

        # 检查进程内存
        if metrics["process"]["memory_mb"] > self.thresholds["process_memory_mb"]:
            alerts.append({
                "type": "process_memory",
                "level": "warning",
                "message": f"进程内存使用过高: {metrics['process']['memory_mb']:.2f} MB",
                "value": metrics["process"]["memory_mb"],
                "threshold": self.thresholds["process_memory_mb"]
            })

        return alerts

    def log_metrics(self, metrics: Dict):
        """记录性能指标到日志文件"""
        try:
            today = datetime.now().strftime("%Y%m%d")
            log_file = self.log_dir / f"performance_{today}.jsonl"

            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(metrics, ensure_ascii=False) + '\n')

        except Exception as e:
            logger.error(f"记录性能日志失败: {e}")

    def send_alerts(self, alerts: List[Dict]):
        """发送告警（可以通过Telegram或其他方式）"""
        for alert in alerts:
            logger.warning(f"[性能告警] {alert['message']}")
            self.alert_history.append({
                **alert,
                "timestamp": datetime.now().isoformat()
            })

            # 限制告警历史大小
            if len(self.alert_history) > 100:
                self.alert_history = self.alert_history[-100:]

    def monitor_loop(self):
        """监控循环"""
        logger.info("性能监控启动")

        while self.monitoring:
            try:
                # 获取指标
                metrics = self.get_system_metrics()

                # 记录日志
                self.log_metrics(metrics)

                # 检查阈值
                alerts = self.check_thresholds(metrics)
                if alerts:
                    self.send_alerts(alerts)

                # 等待下一次检查
                time.sleep(self.interval)

            except Exception as e:
                logger.error(f"监控循环错误: {e}")
                time.sleep(self.interval)

        logger.info("性能监控已停止")

    def start(self):
        """启动监控"""
        if self.monitoring:
            logger.warning("监控已在运行中")
            return

        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self.monitor_loop, daemon=True)
        self.monitor_thread.start()
        logger.info(f"性能监控已启动，间隔: {self.interval}秒")

    def stop(self):
        """停止监控"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        logger.info("性能监控已停止")

    def get_recent_alerts(self, limit: int = 10) -> List[Dict]:
        """获取最近的告警"""
        return self.alert_history[-limit:]

    def get_summary(self) -> Dict:
        """获取性能摘要"""
        metrics = self.get_system_metrics()
        alerts = self.check_thresholds(metrics)

        return {
            "current_metrics": metrics,
            "active_alerts": alerts,
            "recent_alerts": self.get_recent_alerts(),
            "monitoring": self.monitoring,
            "thresholds": self.thresholds
        }


def main():
    """主函数 - 用于测试"""
    monitor = PerformanceMonitor()

    try:
        # 显示当前指标
        print("=== 当前系统性能 ===")
        metrics = monitor.get_system_metrics()
        print(json.dumps(metrics, indent=2, ensure_ascii=False))

        print("\n=== 阈值检查 ===")
        alerts = monitor.check_thresholds(metrics)
        if alerts:
            for alert in alerts:
                print(f"[{alert['level'].upper()}] {alert['message']}")
        else:
            print("所有指标正常")

        # 启动持续监控
        print(f"\n=== 启动持续监控 (间隔: {monitor.interval}秒) ===")
        print("按 Ctrl+C 停止监控")
        monitor.start()

        # 保持运行
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n正在停止监控...")
        monitor.stop()
        print("监控已停止")


if __name__ == "__main__":
    main()
