#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
增强的监控和告警系统
集成性能监控、健康检查、告警通知
"""

import os
import sys
import time
import json
import psutil
import logging
import requests
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from threading import Thread, Lock
from dataclasses import dataclass, asdict

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

logger = logging.getLogger(__name__)


@dataclass
class MetricThreshold:
    """指标阈值"""
    warning: float
    critical: float
    unit: str = ""


@dataclass
class Alert:
    """告警信息"""
    id: str
    level: str  # info, warning, critical
    category: str  # system, trading, component
    title: str
    message: str
    timestamp: float
    resolved: bool = False
    resolved_at: Optional[float] = None


class MonitoringSystem:
    """增强的监控系统"""

    def __init__(self, config_path: str = None):
        self.base_dir = Path(__file__).parent.parent

        # 加载配置
        if config_path is None:
            config_path = self.base_dir / "config" / "monitoring_config.json"

        self.config_path = Path(config_path)
        self.config = self._load_config()

        # 监控数据
        self.metrics_history: List[Dict] = []
        self.active_alerts: Dict[str, Alert] = {}
        self.alert_history: List[Alert] = []
        self.lock = Lock()

        # 阈值配置
        self.thresholds = {
            "cpu": MetricThreshold(warning=70.0, critical=85.0, unit="%"),
            "memory": MetricThreshold(warning=75.0, critical=90.0, unit="%"),
            "disk": MetricThreshold(warning=80.0, critical=95.0, unit="%"),
            "response_time": MetricThreshold(warning=1000.0, critical=3000.0, unit="ms")
        }

        # 组件健康状态
        self.component_health: Dict[str, Dict] = {}

        # 监控状态
        self.is_running = False
        self.monitor_thread: Optional[Thread] = None

    def _load_config(self) -> Dict:
        """加载配置"""
        if not self.config_path.exists():
            return self._get_default_config()

        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"加载配置失败: {e}")
            return self._get_default_config()

    def _get_default_config(self) -> Dict:
        """获取默认配置"""
        return {
            "monitoring": {
                "interval_seconds": 30,
                "metrics_retention_hours": 24,
                "alert_retention_days": 7
            },
            "notifications": {
                "telegram": {
                    "enabled": True,
                    "levels": ["critical", "warning"]
                },
                "email": {
                    "enabled": False,
                    "levels": ["critical"]
                },
                "webhook": {
                    "enabled": False,
                    "url": "",
                    "levels": ["critical", "warning"]
                }
            },
            "health_checks": {
                "api_server": {
                    "enabled": True,
                    "url": "http://localhost:5000/api/health",
                    "timeout": 5
                },
                "mt5_bridge": {
                    "enabled": True,
                    "check_interval": 60
                },
                "database": {
                    "enabled": True,
                    "check_interval": 300
                }
            }
        }

    def start(self):
        """启动监控系统"""
        if self.is_running:
            logger.warning("监控系统已经在运行")
            return

        self.is_running = True
        self.monitor_thread = Thread(target=self._monitoring_loop, daemon=True)
        self.monitor_thread.start()
        logger.info("监控系统已启动")

    def stop(self):
        """停止监控系统"""
        self.is_running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        logger.info("监控系统已停止")

    def _monitoring_loop(self):
        """监控循环"""
        interval = self.config.get("monitoring", {}).get("interval_seconds", 30)

        while self.is_running:
            try:
                # 收集系统指标
                metrics = self._collect_system_metrics()

                # 检查阈值
                self._check_thresholds(metrics)

                # 检查组件健康
                self._check_components_health()

                # 保存指标
                self._save_metrics(metrics)

                # 清理旧数据
                self._cleanup_old_data()

            except Exception as e:
                logger.error(f"监控循环出错: {e}")

            time.sleep(interval)

    def _collect_system_metrics(self) -> Dict:
        """收集系统指标"""
        metrics = {
            "timestamp": time.time(),
            "cpu": {
                "percent": psutil.cpu_percent(interval=1),
                "count": psutil.cpu_count(),
                "per_cpu": psutil.cpu_percent(interval=1, percpu=True)
            },
            "memory": {
                "percent": psutil.virtual_memory().percent,
                "total": psutil.virtual_memory().total,
                "available": psutil.virtual_memory().available,
                "used": psutil.virtual_memory().used
            },
            "disk": {
                "percent": psutil.disk_usage('/').percent,
                "total": psutil.disk_usage('/').total,
                "free": psutil.disk_usage('/').free,
                "used": psutil.disk_usage('/').used
            },
            "network": self._get_network_stats(),
            "processes": self._get_process_stats()
        }

        return metrics

    def _get_network_stats(self) -> Dict:
        """获取网络统计"""
        net_io = psutil.net_io_counters()
        return {
            "bytes_sent": net_io.bytes_sent,
            "bytes_recv": net_io.bytes_recv,
            "packets_sent": net_io.packets_sent,
            "packets_recv": net_io.packets_recv,
            "errin": net_io.errin,
            "errout": net_io.errout
        }

    def _get_process_stats(self) -> Dict:
        """获取进程统计"""
        component_processes = []

        # 读取组件进程信息
        process_file = self.base_dir / "logs" / "component_processes.json"
        if process_file.exists():
            try:
                with open(process_file, 'r', encoding='utf-8') as f:
                    process_info = json.load(f)

                for component, info in process_info.items():
                    try:
                        pid = info['pid']
                        if psutil.pid_exists(pid):
                            proc = psutil.Process(pid)
                            component_processes.append({
                                "component": component,
                                "pid": pid,
                                "cpu_percent": proc.cpu_percent(interval=0.1),
                                "memory_percent": proc.memory_percent(),
                                "status": proc.status()
                            })
                    except Exception:
                        pass
            except Exception as e:
                logger.error(f"读取进程信息失败: {e}")

        return {
            "total_processes": len(psutil.pids()),
            "component_processes": component_processes
        }

    def _check_thresholds(self, metrics: Dict):
        """检查阈值"""
        # 检查CPU
        cpu_percent = metrics['cpu']['percent']
        if cpu_percent >= self.thresholds['cpu'].critical:
            self._create_alert(
                "critical",
                "system",
                "CPU使用率严重过高",
                f"CPU使用率达到 {cpu_percent:.1f}%"
            )
        elif cpu_percent >= self.thresholds['cpu'].warning:
            self._create_alert(
                "warning",
                "system",
                "CPU使用率偏高",
                f"CPU使用率达到 {cpu_percent:.1f}%"
            )

        # 检查内存
        memory_percent = metrics['memory']['percent']
        if memory_percent >= self.thresholds['memory'].critical:
            self._create_alert(
                "critical",
                "system",
                "内存使用率严重过高",
                f"内存使用率达到 {memory_percent:.1f}%"
            )
        elif memory_percent >= self.thresholds['memory'].warning:
            self._create_alert(
                "warning",
                "system",
                "内存使用率偏高",
                f"内存使用率达到 {memory_percent:.1f}%"
            )

        # 检查磁盘
        disk_percent = metrics['disk']['percent']
        if disk_percent >= self.thresholds['disk'].critical:
            self._create_alert(
                "critical",
                "system",
                "磁盘空间严重不足",
                f"磁盘使用率达到 {disk_percent:.1f}%"
            )
        elif disk_percent >= self.thresholds['disk'].warning:
            self._create_alert(
                "warning",
                "system",
                "磁盘空间不足",
                f"磁盘使用率达到 {disk_percent:.1f}%"
            )

    def _check_components_health(self):
        """检查组件健康状态"""
        health_checks = self.config.get("health_checks", {})

        # 检查API服务器
        if health_checks.get("api_server", {}).get("enabled", True):
            self._check_api_health()

        # 检查组件进程
        self._check_component_processes()

    def _check_api_health(self):
        """检查API健康状态"""
        api_config = self.config.get("health_checks", {}).get("api_server", {})
        url = api_config.get("url", "http://localhost:5000/api/health")
        timeout = api_config.get("timeout", 5)

        try:
            response = requests.get(url, timeout=timeout)
            if response.status_code == 200:
                self._resolve_alert("api_health")
            else:
                self._create_alert(
                    "warning",
                    "component",
                    "API服务器响应异常",
                    f"状态码: {response.status_code}",
                    alert_id="api_health"
                )
        except requests.RequestException as e:
            self._create_alert(
                "critical",
                "component",
                "API服务器无法访问",
                str(e),
                alert_id="api_health"
            )

    def _check_component_processes(self):
        """检查组件进程状态"""
        process_file = self.base_dir / "logs" / "component_processes.json"

        if not process_file.exists():
            return

        try:
            with open(process_file, 'r', encoding='utf-8') as f:
                process_info = json.load(f)

            for component, info in process_info.items():
                pid = info['pid']
                display_name = info.get('display_name', component)

                if not psutil.pid_exists(pid):
                    self._create_alert(
                        "critical",
                        "component",
                        f"组件进程已停止: {display_name}",
                        f"PID {pid} 不存在",
                        alert_id=f"component_{component}"
                    )
                else:
                    self._resolve_alert(f"component_{component}")

        except Exception as e:
            logger.error(f"检查组件进程失败: {e}")

    def _create_alert(self, level: str, category: str, title: str,
                     message: str, alert_id: str = None):
        """创建告警"""
        if alert_id is None:
            alert_id = f"{category}_{title}_{int(time.time())}"

        # 检查是否已存在相同告警
        with self.lock:
            if alert_id in self.active_alerts:
                return

            alert = Alert(
                id=alert_id,
                level=level,
                category=category,
                title=title,
                message=message,
                timestamp=time.time()
            )

            self.active_alerts[alert_id] = alert
            self.alert_history.append(alert)

        logger.log(
            logging.CRITICAL if level == "critical" else logging.WARNING,
            f"[{level.upper()}] {title}: {message}"
        )

        # 发送通知
        self._send_notification(alert)

    def _resolve_alert(self, alert_id: str):
        """解决告警"""
        with self.lock:
            if alert_id in self.active_alerts:
                alert = self.active_alerts[alert_id]
                alert.resolved = True
                alert.resolved_at = time.time()
                del self.active_alerts[alert_id]

                logger.info(f"告警已解决: {alert.title}")

    def _send_notification(self, alert: Alert):
        """发送通知"""
        notifications = self.config.get("notifications", {})

        # Telegram通知
        if notifications.get("telegram", {}).get("enabled", False):
            if alert.level in notifications["telegram"].get("levels", []):
                self._send_telegram_notification(alert)

        # Webhook通知
        if notifications.get("webhook", {}).get("enabled", False):
            if alert.level in notifications["webhook"].get("levels", []):
                self._send_webhook_notification(alert)

    def _send_telegram_notification(self, alert: Alert):
        """发送Telegram通知"""
        try:
            from utilities.telegram_notifier import send_alert
            send_alert(alert.level, alert.title, alert.message)
        except Exception as e:
            logger.error(f"发送Telegram通知失败: {e}")

    def _send_webhook_notification(self, alert: Alert):
        """发送Webhook通知"""
        webhook_config = self.config.get("notifications", {}).get("webhook", {})
        url = webhook_config.get("url")

        if not url:
            return

        try:
            payload = {
                "level": alert.level,
                "category": alert.category,
                "title": alert.title,
                "message": alert.message,
                "timestamp": alert.timestamp
            }

            requests.post(url, json=payload, timeout=5)
        except Exception as e:
            logger.error(f"发送Webhook通知失败: {e}")

    def _save_metrics(self, metrics: Dict):
        """保存指标"""
        with self.lock:
            self.metrics_history.append(metrics)

        # 保存到文件
        metrics_dir = self.base_dir / "logs" / "monitoring"
        metrics_dir.mkdir(parents=True, exist_ok=True)

        today = datetime.now().strftime("%Y%m%d")
        metrics_file = metrics_dir / f"metrics_{today}.jsonl"

        try:
            with open(metrics_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(metrics, ensure_ascii=False) + '\n')
        except Exception as e:
            logger.error(f"保存指标失败: {e}")

    def _cleanup_old_data(self):
        """清理旧数据"""
        # 清理内存中的指标历史
        retention_hours = self.config.get("monitoring", {}).get("metrics_retention_hours", 24)
        cutoff_time = time.time() - (retention_hours * 3600)

        with self.lock:
            self.metrics_history = [
                m for m in self.metrics_history
                if m['timestamp'] > cutoff_time
            ]

        # 清理告警历史
        alert_retention_days = self.config.get("monitoring", {}).get("alert_retention_days", 7)
        alert_cutoff = time.time() - (alert_retention_days * 86400)

        with self.lock:
            self.alert_history = [
                a for a in self.alert_history
                if a.timestamp > alert_cutoff
            ]

    def get_current_metrics(self) -> Dict:
        """获取当前指标"""
        return self._collect_system_metrics()

    def get_active_alerts(self) -> List[Alert]:
        """获取活跃告警"""
        with self.lock:
            return list(self.active_alerts.values())

    def get_alert_history(self, hours: int = 24) -> List[Alert]:
        """获取告警历史"""
        cutoff = time.time() - (hours * 3600)
        with self.lock:
            return [a for a in self.alert_history if a.timestamp > cutoff]

    def get_metrics_summary(self, hours: int = 1) -> Dict:
        """获取指标摘要"""
        cutoff = time.time() - (hours * 3600)

        with self.lock:
            recent_metrics = [
                m for m in self.metrics_history
                if m['timestamp'] > cutoff
            ]

        if not recent_metrics:
            return {}

        # 计算平均值
        avg_cpu = sum(m['cpu']['percent'] for m in recent_metrics) / len(recent_metrics)
        avg_memory = sum(m['memory']['percent'] for m in recent_metrics) / len(recent_metrics)
        avg_disk = sum(m['disk']['percent'] for m in recent_metrics) / len(recent_metrics)

        # 计算最大值
        max_cpu = max(m['cpu']['percent'] for m in recent_metrics)
        max_memory = max(m['memory']['percent'] for m in recent_metrics)
        max_disk = max(m['disk']['percent'] for m in recent_metrics)

        return {
            "period_hours": hours,
            "sample_count": len(recent_metrics),
            "cpu": {
                "average": avg_cpu,
                "max": max_cpu
            },
            "memory": {
                "average": avg_memory,
                "max": max_memory
            },
            "disk": {
                "average": avg_disk,
                "max": max_disk
            }
        }


def main():
    """主函数"""
    import argparse

    # 配置日志
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )

    parser = argparse.ArgumentParser(description='监控和告警系统')
    parser.add_argument('action', choices=['start', 'status', 'alerts', 'metrics'],
                       help='操作类型')
    parser.add_argument('--daemon', '-d', action='store_true',
                       help='后台运行')

    args = parser.parse_args()

    monitor = MonitoringSystem()

    if args.action == 'start':
        print("启动监控系统...")
        monitor.start()

        if args.daemon:
            print("监控系统已在后台运行")
            # 保持运行
            try:
                while True:
                    time.sleep(60)
            except KeyboardInterrupt:
                print("\n停止监控系统...")
                monitor.stop()
        else:
            print("监控系统运行中 (按 Ctrl+C 停止)")
            try:
                while True:
                    time.sleep(60)
            except KeyboardInterrupt:
                print("\n停止监控系统...")
                monitor.stop()

    elif args.action == 'status':
        metrics = monitor.get_current_metrics()

        print("\n" + "=" * 70)
        print("系统状态")
        print("=" * 70)

        print(f"\nCPU:")
        print(f"  使用率: {metrics['cpu']['percent']:.1f}%")
        print(f"  核心数: {metrics['cpu']['count']}")

        print(f"\n内存:")
        print(f"  使用率: {metrics['memory']['percent']:.1f}%")
        print(f"  总量: {metrics['memory']['total'] / (1024**3):.1f} GB")
        print(f"  可用: {metrics['memory']['available'] / (1024**3):.1f} GB")

        print(f"\n磁盘:")
        print(f"  使用率: {metrics['disk']['percent']:.1f}%")
        print(f"  总量: {metrics['disk']['total'] / (1024**3):.1f} GB")
        print(f"  剩余: {metrics['disk']['free'] / (1024**3):.1f} GB")

        print(f"\n组件进程:")
        for proc in metrics['processes']['component_processes']:
            print(f"  {proc['component']:20s} | CPU: {proc['cpu_percent']:5.1f}% | "
                  f"内存: {proc['memory_percent']:5.1f}% | 状态: {proc['status']}")

        print("\n" + "=" * 70)

    elif args.action == 'alerts':
        monitor.start()
        time.sleep(2)  # 等待收集数据

        active_alerts = monitor.get_active_alerts()
        alert_history = monitor.get_alert_history(hours=24)

        print("\n" + "=" * 70)
        print("告警信息")
        print("=" * 70)

        print(f"\n活跃告警 ({len(active_alerts)}):")
        if active_alerts:
            for alert in active_alerts:
                timestamp = datetime.fromtimestamp(alert.timestamp).strftime("%Y-%m-%d %H:%M:%S")
                print(f"  [{alert.level.upper()}] {alert.title}")
                print(f"    时间: {timestamp}")
                print(f"    消息: {alert.message}")
                print()
        else:
            print("  无活跃告警")

        print(f"\n24小时告警历史 ({len(alert_history)}):")
        if alert_history:
            for alert in alert_history[-10:]:  # 显示最近10条
                timestamp = datetime.fromtimestamp(alert.timestamp).strftime("%Y-%m-%d %H:%M:%S")
                status = "已解决" if alert.resolved else "未解决"
                print(f"  [{alert.level.upper()}] {alert.title} - {status}")
                print(f"    时间: {timestamp}")
        else:
            print("  无告警历史")

        print("\n" + "=" * 70)

        monitor.stop()

    elif args.action == 'metrics':
        monitor.start()
        time.sleep(2)

        summary = monitor.get_metrics_summary(hours=1)

        print("\n" + "=" * 70)
        print("指标摘要 (过去1小时)")
        print("=" * 70)

        if summary:
            print(f"\n样本数: {summary['sample_count']}")

            print(f"\nCPU:")
            print(f"  平均: {summary['cpu']['average']:.1f}%")
            print(f"  最大: {summary['cpu']['max']:.1f}%")

            print(f"\n内存:")
            print(f"  平均: {summary['memory']['average']:.1f}%")
            print(f"  最大: {summary['memory']['max']:.1f}%")

            print(f"\n磁盘:")
            print(f"  平均: {summary['disk']['average']:.1f}%")
            print(f"  最大: {summary['disk']['max']:.1f}%")
        else:
            print("\n暂无数据")

        print("\n" + "=" * 70)

        monitor.stop()


if __name__ == "__main__":
    main()
