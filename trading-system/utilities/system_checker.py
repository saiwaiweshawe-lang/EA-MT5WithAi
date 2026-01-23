#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
系统自检模块 - 检测并修复缺失的依赖、配置和资源
"""

import os
import sys
import json
import subprocess
import importlib.util
from pathlib import Path
from typing import Dict, List, Tuple
import urllib.request
import shutil

class SystemChecker:
    """系统自检器"""

    def __init__(self, base_dir: str = None):
        self.base_dir = Path(base_dir or os.path.dirname(os.path.dirname(__file__)))
        self.issues = []
        self.fixes = []

    def run_full_check(self) -> Dict:
        """运行完整的系统检查"""
        print("=" * 60)
        print("系统自检开始...")
        print("=" * 60)
        print()

        results = {
            "python_deps": self.check_python_dependencies(),
            "config_files": self.check_config_files(),
            "directories": self.check_directories(),
            "external_resources": self.check_external_resources(),
            "system_tools": self.check_system_tools()
        }

        print()
        print("=" * 60)
        print("自检完成!")
        print("=" * 60)
        self._print_summary(results)

        return results

    def check_python_dependencies(self) -> Dict:
        """检查并安装缺失的 Python 依赖"""
        print("[1/5] 检查 Python 依赖包...")

        required_packages = [
            "telegram",
            "MetaTrader5",
            "ccxt",
            "pandas",
            "numpy",
            "scikit-learn",
            "flask",
            "requests",
            "python-dotenv",
            "schedule",
            "ta",
            "openai",
            "anthropic"
        ]

        missing = []
        installed = []

        for package in required_packages:
            # 特殊处理包名映射
            import_name = package
            if package == "MetaTrader5":
                import_name = "MetaTrader5"
            elif package == "python-dotenv":
                import_name = "dotenv"
            elif package == "scikit-learn":
                import_name = "sklearn"

            if not self._is_package_installed(import_name):
                missing.append(package)
                print(f"  ❌ 缺失: {package}")
            else:
                installed.append(package)
                print(f"  ✅ 已安装: {package}")

        # 自动安装缺失的包
        if missing:
            print(f"\n  发现 {len(missing)} 个缺失的依赖包,开始自动安装...")
            self._install_packages(missing)
        else:
            print("  所有依赖包已安装!")

        return {
            "status": "ok" if not missing else "fixed",
            "installed": installed,
            "missing": missing
        }

    def check_config_files(self) -> Dict:
        """检查并创建缺失的配置文件"""
        print("\n[2/5] 检查配置文件...")

        config_dir = self.base_dir / "config"
        required_configs = {
            "bot_config.json": self._get_default_bot_config(),
            "server_config.json": self._get_default_server_config(),
            "ea_config.json": self._get_default_ea_config(),
            "vps_config.json": self._get_default_vps_config(),
            "ai_config.json": self._get_default_ai_config(),
            "position_management_config.json": self._get_default_position_config()
        }

        missing = []
        existing = []

        for config_file, default_content in required_configs.items():
            config_path = config_dir / config_file
            if not config_path.exists():
                missing.append(config_file)
                print(f"  ❌ 缺失: {config_file}")
                # 创建默认配置文件
                config_path.parent.mkdir(parents=True, exist_ok=True)
                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(default_content, f, indent=2, ensure_ascii=False)
                print(f"     ✓ 已创建默认配置文件")
            else:
                existing.append(config_file)
                print(f"  ✅ 存在: {config_file}")

        return {
            "status": "ok" if not missing else "fixed",
            "existing": existing,
            "missing": missing
        }

    def check_directories(self) -> Dict:
        """检查并创建必要的目录"""
        print("\n[3/5] 检查必要目录...")

        required_dirs = [
            "logs",
            "logs/trades",
            "cache",
            "temp",
            "data",
            "training/models",
            "training/models/proprietary",
            "training/history",
            "shadow_trading",
            "position_management",
            "data_sources"
        ]

        missing = []
        existing = []

        for dir_name in required_dirs:
            dir_path = self.base_dir / dir_name
            if not dir_path.exists():
                missing.append(dir_name)
                print(f"  ❌ 缺失: {dir_name}")
                dir_path.mkdir(parents=True, exist_ok=True)
                print(f"     ✓ 已创建目录")
            else:
                existing.append(dir_name)
                print(f"  ✅ 存在: {dir_name}")

        return {
            "status": "ok" if not missing else "fixed",
            "existing": existing,
            "missing": missing
        }

    def check_external_resources(self) -> Dict:
        """检查并下载外部资源(如需要)"""
        print("\n[4/5] 检查外部资源...")

        # 检查 TA-Lib (可选但推荐)
        talib_installed = self._is_package_installed("talib")
        if talib_installed:
            print("  ✅ TA-Lib 已安装")
        else:
            print("  ⚠️  TA-Lib 未安装 (可选,用于高级技术分析)")
            print("     安装方法: https://github.com/mrjbq7/ta-lib")

        # 检查模型文件目录
        models_dir = self.base_dir / "training" / "models" / "proprietary"
        if models_dir.exists() and list(models_dir.glob("*.pkl")):
            print(f"  ✅ 发现已训练的模型文件")
        else:
            print(f"  ℹ️  暂无训练模型 (将在首次运行后生成)")

        return {
            "status": "ok",
            "talib_installed": talib_installed,
            "models_found": models_dir.exists() and list(models_dir.glob("*.pkl"))
        }

    def check_system_tools(self) -> Dict:
        """检查系统工具(screen, git等)"""
        print("\n[5/5] 检查系统工具...")

        tools = {
            "python3": "python3 --version",
            "pip": "pip --version",
            "git": "git --version"
        }

        optional_tools = {
            "screen": "screen --version",
            "systemctl": "systemctl --version"
        }

        available = {}
        missing = []

        # 检查必需工具
        for tool, cmd in tools.items():
            if self._is_command_available(tool):
                available[tool] = True
                print(f"  ✅ {tool} 可用")
            else:
                available[tool] = False
                missing.append(tool)
                print(f"  ❌ {tool} 未找到")

        # 检查可选工具
        for tool, cmd in optional_tools.items():
            if self._is_command_available(tool):
                available[tool] = True
                print(f"  ✅ {tool} 可用 (可选)")
            else:
                available[tool] = False
                print(f"  ⚠️  {tool} 未找到 (可选)")

        return {
            "status": "ok" if not missing else "warning",
            "available": available,
            "missing": missing
        }

    def _is_package_installed(self, package_name: str) -> bool:
        """检查 Python 包是否已安装"""
        try:
            importlib.import_module(package_name)
            return True
        except ImportError:
            return False

    def _install_packages(self, packages: List[str]):
        """安装 Python 包"""
        try:
            # 尝试使用清华镜像
            print("  使用清华镜像源...")
            subprocess.check_call([
                sys.executable, "-m", "pip", "install",
                "-i", "https://pypi.tuna.tsinghua.edu.cn/simple"
            ] + packages)
            print("  ✓ 安装成功!")
        except subprocess.CalledProcessError:
            # 回退到官方源
            print("  清华源失败,使用官方源...")
            try:
                subprocess.check_call([
                    sys.executable, "-m", "pip", "install"
                ] + packages)
                print("  ✓ 安装成功!")
            except subprocess.CalledProcessError as e:
                print(f"  ✗ 安装失败: {e}")

    def _is_command_available(self, command: str) -> bool:
        """检查系统命令是否可用"""
        return shutil.which(command) is not None

    def _print_summary(self, results: Dict):
        """打印检查摘要"""
        print("\n📊 检查摘要:")
        print("-" * 60)

        total_issues = 0
        total_fixed = 0

        for category, result in results.items():
            status = result.get("status", "unknown")
            if status == "fixed":
                fixed_count = len(result.get("missing", []))
                total_fixed += fixed_count
                print(f"  {category}: ✓ 已修复 {fixed_count} 个问题")
            elif status == "warning":
                warning_count = len(result.get("missing", []))
                total_issues += warning_count
                print(f"  {category}: ⚠️  {warning_count} 个警告")
            elif status == "ok":
                print(f"  {category}: ✅ 正常")

        print("-" * 60)
        if total_fixed > 0:
            print(f"✅ 已自动修复 {total_fixed} 个问题")
        if total_issues > 0:
            print(f"⚠️  存在 {total_issues} 个警告 (非关键)")
        if total_issues == 0 and total_fixed == 0:
            print("✅ 系统状态良好,无需修复!")

    # 默认配置模板
    def _get_default_bot_config(self) -> Dict:
        """获取默认 bot 配置"""
        return {
            "telegram_bot_token": "your-telegram-bot-token-here",
            "telegram_chat_id": "your-telegram-chat-id",
            "authorized_users": [],
            "notifications": {
                "enabled": True,
                "trade_alerts": True,
                "profit_alerts": True,
                "loss_alerts": True
            },
            "daily_analysis": {
                "enabled": True,
                "report_time": "23:30"
            },
            "circuit_breaker": {
                "enabled": True,
                "max_loss_per_day": -1000,
                "max_consecutive_losses": 5
            }
        }

    def _get_default_server_config(self) -> Dict:
        """获取默认 server 配置"""
        return {
            "host": "0.0.0.0",
            "port": 5000,
            "debug": False,
            "api_key": "your-api-key-here",
            "allowed_ips": ["127.0.0.1"]
        }

    def _get_default_ea_config(self) -> Dict:
        """获取默认 EA 配置"""
        return {
            "symbol": "XAUUSD",
            "timeframe": "H1",
            "lot_size": 0.01,
            "max_positions": 3,
            "stop_loss_pips": 50,
            "take_profit_pips": 100
        }

    def _get_default_vps_config(self) -> Dict:
        """获取默认 VPS 配置"""
        return {
            "profile": "auto",
            "max_memory_mb": 4096,
            "max_cpu_cores": 4,
            "optimization_level": "balanced"
        }

    def _get_default_ai_config(self) -> Dict:
        """获取默认 AI 配置"""
        return {
            "enabled": True,
            "models": {
                "openai": {
                    "enabled": False,
                    "api_key": "",
                    "model": "gpt-4"
                },
                "anthropic": {
                    "enabled": False,
                    "api_key": "",
                    "model": "claude-3-sonnet-20240229"
                },
                "deepseek": {
                    "enabled": True,
                    "api_key": "",
                    "model": "deepseek-chat"
                }
            }
        }

    def _get_default_position_config(self) -> Dict:
        """获取默认持仓管理配置"""
        return {
            "position_monitor": {
                "enabled": True,
                "scan_interval_seconds": 60,
                "auto_execute_decisions": False
            },
            "trailing_stop": {
                "enabled": True,
                "default_strategy": "dynamic",
                "activation_profit_pct": 2.0
            },
            "free_data_sources": {
                "enabled": True,
                "cache_ttl_seconds": 300
            }
        }


def main():
    """主函数"""
    checker = SystemChecker()
    results = checker.run_full_check()

    # 返回状态码
    has_errors = any(r.get("status") == "error" for r in results.values())
    return 1 if has_errors else 0


if __name__ == "__main__":
    sys.exit(main())
