# VPS自动适应配置模块
# 根据服务器硬件调整系统参数

import os
import psutil
import logging
import platform
import json
from typing import Dict, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class VPSConfig:
    """VPS配置管理器"""

    def __init__(self, config_path: str = "config/vps_config.json"):
        self.config_path = config_path
        self.config = self._load_or_create_config()
        self.system_info = self._detect_system()

    def _load_or_create_config(self) -> Dict:
        """加载或创建配置"""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"加载配置失败: {e}")

        return self._create_default_config()

    def _create_default_config(self) -> Dict:
        """创建默认配置"""
        return {
            "system": {
                "detected": False,
                "auto_adjust": True,
                "last_check": None
            },
            "mt5": {
                "max_ea_instances": 1,
                "terminal_priority": "normal",
                "max_positions_per_ea": 10
            },
            "ai": {
                "max_concurrent_requests": 3,
                "model_cache_size_mb": 512,
                "enable_local_model": False,
                "enable_gpu": True
            },
            "trading": {
                "max_symbols": 20,
                "check_interval_ms": 1000,
                "data_history_days": 30
            },
            "logging": {
                "log_level": "INFO",
                "max_log_size_mb": 100,
                "log_retention_days": 7
            },
            "database": {
                "cache_size_mb": 256,
                "backup_interval_hours": 24
            },
            "performance": {
                "enable_monitoring": True,
                "alert_cpu_threshold": 80,
                "alert_memory_threshold": 85,
                "alert_disk_threshold": 90
            }
        }

    def _detect_system(self) -> Dict:
        """检测系统信息"""
        info = {
            "hostname": platform.node(),
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "cpu": {
                "cores": psutil.cpu_count(logical=True),
                "physical_cores": psutil.cpu_count(logical=False),
                "frequency": psutil.cpu_freq().max if psutil.cpu_freq() else 0,
                "usage_percent": psutil.cpu_percent(interval=1)
            },
            "memory": {
                "total_gb": psutil.virtual_memory().total / (1024**3),
                "available_gb": psutil.virtual_memory().available / (1024**3),
                "used_percent": psutil.virtual_memory().percent
            },
            "disk": {},
            "network": {}
        }

        # 检测所有磁盘
        for partition in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                info["disk"][partition.mountpoint] = {
                    "total_gb": usage.total / (1024**3),
                    "used_gb": usage.used / (1024**3),
                    "free_gb": usage.free / (1024**3),
                    "used_percent": usage.percent
                }
            except Exception as e:
                logger.warning(f"无法获取磁盘信息 {partition.mountpoint}: {e}")

        # 检测网络接口
        try:
            info["network"] = {
                "interfaces": list(psutil.net_if_addrs().keys())
            }
        except Exception as e:
            logger.warning(f"无法获取网络信息: {e}")

        return info

    def detect_vps_profile(self) -> str:
        """检测VPS配置文件"""
        cpu_cores = self.system_info["cpu"]["physical_cores"]
        memory_gb = self.system_info["memory"]["total_gb"]

        # 检测已知的VPS配置
        if cpu_cores == 8 and 15.5 <= memory_gb <= 16.5:
            return "high_performance"  # 8核16G
        elif cpu_cores == 8 and 7.5 <= memory_gb <= 8.5:
            return "medium_performance"  # 8核8G
        elif cpu_cores >= 4 and memory_gb >= 8:
            return "standard"
        elif cpu_cores >= 2 and memory_gb >= 4:
            return "basic"
        else:
            return "minimal"

    def adjust_config(self) -> Dict:
        """根据系统调整配置"""
        profile = self.detect_vps_profile()
        logger.info(f"检测到VPS配置文件: {profile}")

        adjustments = self._get_profile_adjustments(profile)

        # 应用调整
        for section, settings in adjustments.items():
            if section in self.config:
                for key, value in settings.items():
                    self.config[section][key] = value
                    logger.info(f"调整配置: {section}.{key} = {value}")

        # 标记已检测
        self.config["system"]["detected"] = True
        self.config["system"]["last_check"] = str(datetime.now())

        # 保存配置
        self.save_config()

        return {
            "profile": profile,
            "adjustments": adjustments,
            "system_info": self.system_info
        }

    def _get_profile_adjustments(self, profile: str) -> Dict:
        """获取配置文件的调整参数"""
        profiles = {
            "high_performance": {
                "mt5": {
                    "max_ea_instances": 4,
                    "terminal_priority": "high",
                    "max_positions_per_ea": 20
                },
                "ai": {
                    "max_concurrent_requests": 5,
                    "model_cache_size_mb": 2048,
                    "enable_local_model": True,
                    "enable_gpu": True
                },
                "trading": {
                    "max_symbols": 50,
                    "check_interval_ms": 500,
                    "data_history_days": 90
                },
                "database": {
                    "cache_size_mb": 1024
                }
            },
            "medium_performance": {
                "mt5": {
                    "max_ea_instances": 2,
                    "terminal_priority": "normal",
                    "max_positions_per_ea": 15
                },
                "ai": {
                    "max_concurrent_requests": 3,
                    "model_cache_size_mb": 1024,
                    "enable_local_model": False,
                    "enable_gpu": True
                },
                "trading": {
                    "max_symbols": 30,
                    "check_interval_ms": 800,
                    "data_history_days": 60
                },
                "database": {
                    "cache_size_mb": 512
                }
            },
            "standard": {
                "mt5": {
                    "max_ea_instances": 2,
                    "terminal_priority": "normal",
                    "max_positions_per_ea": 10
                },
                "ai": {
                    "max_concurrent_requests": 2,
                    "model_cache_size_mb": 512,
                    "enable_local_model": False,
                    "enable_gpu": False
                },
                "trading": {
                    "max_symbols": 20,
                    "check_interval_ms": 1000,
                    "data_history_days": 30
                },
                "database": {
                    "cache_size_mb": 256
                }
            },
            "basic": {
                "mt5": {
                    "max_ea_instances": 1,
                    "terminal_priority": "normal",
                    "max_positions_per_ea": 5
                },
                "ai": {
                    "max_concurrent_requests": 1,
                    "model_cache_size_mb": 256,
                    "enable_local_model": False,
                    "enable_gpu": False
                },
                "trading": {
                    "max_symbols": 10,
                    "check_interval_ms": 2000,
                    "data_history_days": 15
                },
                "database": {
                    "cache_size_mb": 128
                }
            },
            "minimal": {
                "mt5": {
                    "max_ea_instances": 1,
                    "terminal_priority": "low",
                    "max_positions_per_ea": 3
                },
                "ai": {
                    "max_concurrent_requests": 1,
                    "model_cache_size_mb": 128,
                    "enable_local_model": False,
                    "enable_gpu": False
                },
                "trading": {
                    "max_symbols": 5,
                    "check_interval_ms": 5000,
                    "data_history_days": 7
                },
                "database": {
                    "cache_size_mb": 64
                }
            }
        }

        return profiles.get(profile, profiles["standard"])

    def save_config(self):
        """保存配置"""
        Path(os.path.dirname(self.config_path)).mkdir(parents=True, exist_ok=True)

        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=2, ensure_ascii=False)

        logger.info(f"配置已保存: {self.config_path}")

    def get_config(self) -> Dict:
        """获取配置"""
        return self.config

    def get_system_info(self) -> Dict:
        """获取系统信息"""
        return self.system_info

    def update_system_status(self) -> Dict:
        """更新系统状态"""
        self.system_info = self._detect_system()
        return self.system_info

    def check_performance_alerts(self) -> Dict:
        """检查性能警报"""
        alerts = []

        config_perf = self.config.get("performance", {})

        # CPU检查
        cpu_usage = self.system_info["cpu"]["usage_percent"]
        cpu_threshold = config_perf.get("alert_cpu_threshold", 80)
        if cpu_usage > cpu_threshold:
            alerts.append({
                "type": "cpu",
                "level": "warning",
                "message": f"CPU使用率过高: {cpu_usage:.1f}% (阈值: {cpu_threshold}%)"
            })

        # 内存检查
        memory_usage = self.system_info["memory"]["used_percent"]
        memory_threshold = config_perf.get("alert_memory_threshold", 85)
        if memory_usage > memory_threshold:
            alerts.append({
                "type": "memory",
                "level": "warning",
                "message": f"内存使用率过高: {memory_usage:.1f}% (阈值: {memory_threshold}%)"
            })

        # 磁盘检查
        disk_threshold = config_perf.get("alert_disk_threshold", 90)
        for mount, disk_info in self.system_info["disk"].items():
            if disk_info["used_percent"] > disk_threshold:
                alerts.append({
                    "type": "disk",
                    "level": "critical",
                    "message": f"磁盘 {mount} 空间不足: {disk_info['used_percent']:.1f}% (阈值: {disk_threshold}%)"
                })

        return {
            "alerts": alerts,
            "alert_count": len(alerts),
            "severity": "critical" if any(a["level"] == "critical" for a in alerts) else "warning" if alerts else "ok"
        }

    def optimize_for_trading(self):
        """为交易优化系统设置"""
        import subprocess

        if self.system_info["system"] != "Linux":
            logger.warning("系统优化仅支持Linux")
            return

        logger.info("开始系统优化...")

        optimizations = []

        try:
            # 调整swappiness
            try:
                with open("/proc/sys/vm/swappiness", "r") as f:
                    current = f.read().strip()
                if int(current) > 10:
                    subprocess.run(["sysctl", "-w", "vm.swappiness=10"], check=True)
                    optimizations.append("vm.swappiness 设置为 10")
            except Exception as e:
                logger.warning(f"无法调整swappiness: {e}")

            # 调整文件描述符限制
            try:
                with open("/proc/sys/fs/file-max", "r") as f:
                    current = f.read().strip()
                if int(current) < 65536:
                    subprocess.run(["sysctl", "-w", "fs.file-max=65536"], check=True)
                    optimizations.append("fs.file-max 设置为 65536")
            except Exception as e:
                logger.warning(f"无法调整文件描述符限制: {e}")

            # 设置MT5进程优先级（如果安装）
            try:
                result = subprocess.run(["pgrep", "-f", "terminal64"], capture_output=True, text=True)
                if result.returncode == 0 and result.stdout.strip():
                    pids = result.stdout.strip().split("\n")
                    for pid in pids:
                        subprocess.run(["renice", "-5", str(pid)], check=True)
                        optimizations.append(f"MT5进程 {pid} 优先级已提升")
            except Exception as e:
                logger.warning(f"无法调整进程优先级: {e}")

        except Exception as e:
            logger.error(f"系统优化失败: {e}")

        logger.info(f"系统优化完成: {len(optimizations)} 项调整")
        return optimizations

    def get_resource_allocation(self) -> Dict:
        """获取资源分配建议"""
        profile = self.detect_vps_profile()

        allocations = {
            "high_performance": {
                "mt5_instances": 4,
                "trading_pairs": 30,
                "ai_models": 3,
                "concurrent_signals": 10,
                "data_cache_gb": 4,
                "log_retention_days": 30
            },
            "medium_performance": {
                "mt5_instances": 2,
                "trading_pairs": 20,
                "ai_models": 2,
                "concurrent_signals": 5,
                "data_cache_gb": 2,
                "log_retention_days": 14
            },
            "standard": {
                "mt5_instances": 2,
                "trading_pairs": 15,
                "ai_models": 1,
                "concurrent_signals": 3,
                "data_cache_gb": 1,
                "log_retention_days": 7
            },
            "basic": {
                "mt5_instances": 1,
                "trading_pairs": 10,
                "ai_models": 1,
                "concurrent_signals": 2,
                "data_cache_gb": 0.5,
                "log_retention_days": 3
            },
            "minimal": {
                "mt5_instances": 1,
                "trading_pairs": 5,
                "ai_models": 0,
                "concurrent_signals": 1,
                "data_cache_gb": 0.25,
                "log_retention_days": 1
            }
        }

        return allocations.get(profile, allocations["standard"])

    def print_system_info(self):
        """打印系统信息"""
        print(f"""
{'='*60}
系统信息检测报告
{'='*60}

主机名: {self.system_info['hostname']}
操作系统: {self.system_info['system']} {self.system_info['release']}
架构: {self.system_info['machine']}
处理器: {self.system_info['processor']}

【CPU】
物理核心: {self.system_info['cpu']['physical_cores']}
逻辑核心: {self.system_info['cpu']['cores']}
最大频率: {self.system_info['cpu']['frequency']:.0f} MHz
当前使用率: {self.system_info['cpu']['usage_percent']:.1f}%

【内存】
总内存: {self.system_info['memory']['total_gb']:.2f} GB
可用内存: {self.system_info['memory']['available_gb']:.2f} GB
使用率: {self.system_info['memory']['used_percent']:.1f}%

【磁盘】
""")
        for mount, disk in self.system_info['disk'].items():
            print(f"{mount}:")
            print(f"  总容量: {disk['total_gb']:.2f} GB")
            print(f"  已使用: {disk['used_gb']:.2f} GB ({disk['used_percent']:.1f}%)")
            print(f"  可用: {disk['free_gb']:.2f} GB")

        print(f"""
【网络接口】
{', '.join(self.system_info['network']['interfaces'])}

【VPS配置文件】
检测到的配置: {self.detect_vps_profile()}

【资源分配建议】
""")
        allocation = self.get_resource_allocation()
        for key, value in allocation.items():
            print(f"  {key}: {value}")

        print("\n" + "="*60)


def create_vps_config(config_path: str = "config/vps_config.json") -> VPSConfig:
    """创建VPS配置管理器"""
    return VPSConfig(config_path)


if __name__ == "__main__":
    from datetime import datetime

    vps = VPSConfig()
    vps.print_system_info()

    # 调整配置
    result = vps.adjust_config()
    print(f"\n配置调整完成: {result['profile']}")

    # 检查性能警报
    alerts = vps.check_performance_alerts()
    if alerts["alerts"]:
        print(f"\n发现 {len(alerts['alerts'])} 个警报:")
        for alert in alerts["alerts"]:
            print(f"  [{alert['level'].upper()}] {alert['message']}")
    else:
        print("\n系统状态正常，无警报")

    # 优化系统（仅Linux）
    if platform.system() == "Linux":
        print("\n正在优化系统...")
        vps.optimize_for_trading()
