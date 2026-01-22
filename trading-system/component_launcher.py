#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
组件启动器 - 根据服务器角色启动相应组件
"""

import os
import sys
import time
import logging
import subprocess
from pathlib import Path
from typing import Dict, List

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from utilities.server_role_manager import ServerRoleManager

# 配置日志
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


class ComponentLauncher:
    """组件启动器"""

    def __init__(self):
        self.base_dir = Path(__file__).parent
        self.role_manager = ServerRoleManager()

        # 组件启动命令映射
        self.component_commands = {
            # Server1 组件
            "telegram_bot": ["python", "bots/telegram_bot.py"],
            "api_server": ["python", "api/server.py"],
            "mt5_bridge": ["python", "bridges/mt5_bridge.py"],
            "position_monitor": ["python", "monitors/position_monitor.py"],
            "circuit_breaker": ["python", "protections/circuit_breaker.py"],
            "performance_monitor": ["python", "utilities/performance_monitor.py"],

            # Server2 组件
            "ai_ensemble": ["python", "ai/ensemble_model.py"],
            "news_aggregator": ["python", "data/news_aggregator.py"],
            "dynamic_indicators": ["python", "indicators/dynamic_indicators.py"],
            "shadow_trading": ["python", "training/shadow_trading.py"],
            "self_evolution": ["python", "training/self_evolution.py"],
            "proprietary_model_trainer": ["python", "training/proprietary_model_trainer.py"],
            "data_provider": ["python", "data/data_provider.py"],
            "review_system": ["python", "analysis/review_system.py"],
            "daily_analyzer": ["python", "analysis/daily_analyzer.py"],
            "exchange_trader": ["python", "traders/exchange_trader.py"]
        }

        # 组件显示名称
        self.component_names = {
            "telegram_bot": "Telegram机器人",
            "api_server": "API服务器",
            "mt5_bridge": "MT5桥接",
            "position_monitor": "持仓监控",
            "circuit_breaker": "熔断保护",
            "performance_monitor": "性能监控",
            "ai_ensemble": "AI模型集成",
            "news_aggregator": "新闻聚合",
            "dynamic_indicators": "动态指标",
            "shadow_trading": "影子交易",
            "self_evolution": "自我进化",
            "proprietary_model_trainer": "模型训练",
            "data_provider": "数据提供",
            "review_system": "复盘系统",
            "daily_analyzer": "每日分析",
            "exchange_trader": "交易所交易"
        }

        self.processes = {}
        self.process_info_file = self.base_dir / "logs" / "component_processes.json"

    def get_components_to_start(self) -> List[str]:
        """获取需要启动的组件列表"""
        components = []
        for component in self.role_manager.components:
            if component in self.component_commands:
                components.append(component)
            else:
                logger.warning(f"未找到组件启动命令: {component}")
        return components

    def start_component(self, component: str, background: bool = True) -> bool:
        """启动单个组件"""
        if component not in self.component_commands:
            logger.error(f"未知组件: {component}")
            return False

        command = self.component_commands[component]
        display_name = self.component_names.get(component, component)

        try:
            logger.info(f"启动 {display_name} ({component})...")

            # 检查文件是否存在
            script_path = self.base_dir / command[1]
            if not script_path.exists():
                logger.warning(f"组件脚本不存在: {script_path}")
                return False

            if background:
                # 后台运行
                process = subprocess.Popen(
                    command,
                    cwd=str(self.base_dir),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    stdin=subprocess.PIPE
                )
                self.processes[component] = process
                logger.info(f"✓ {display_name} 已启动 (PID: {process.pid})")
            else:
                # 前台运行
                subprocess.run(command, cwd=str(self.base_dir))

            return True

        except Exception as e:
            logger.error(f"启动 {display_name} 失败: {e}")
            return False

    def start_all_components(self, background: bool = True, delay: int = 2):
        """启动所有组件"""
        components = self.get_components_to_start()

        if not components:
            logger.warning("没有需要启动的组件")
            return

        logger.info(f"服务器角色: {self.role_manager.current_role}")
        logger.info(f"计划启动 {len(components)} 个组件")
        logger.info("=" * 50)

        # 按优先级排序
        components_with_priority = []
        for component in components:
            priority = self.role_manager.get_component_priority(component)
            priority_value = {"high": 0, "medium": 1, "low": 2}.get(priority, 1)
            components_with_priority.append((priority_value, component))

        components_with_priority.sort()

        # 启动组件
        success_count = 0
        for _, component in components_with_priority:
            if self.start_component(component, background=background):
                success_count += 1
                time.sleep(delay)  # 延迟启动下一个组件

        logger.info("=" * 50)
        logger.info(f"启动完成: {success_count}/{len(components)} 个组件成功启动")

        # 保存进程信息
        self._save_process_info()

    def stop_all_components(self):
        """停止所有组件"""
        import psutil

        logger.info("停止所有组件...")

        # 先尝试停止内存中的进程
        for component, process in list(self.processes.items()):
            try:
                display_name = self.component_names.get(component, component)
                logger.info(f"停止 {display_name}...")
                process.terminate()
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logger.warning(f"强制终止 {display_name}...")
                process.kill()
            except Exception as e:
                logger.error(f"停止 {display_name} 失败: {e}")

        self.processes.clear()

        # 再停止文件中记录的进程
        process_info = self._load_process_info()
        for component, info in process_info.items():
            try:
                pid = info['pid']
                display_name = info['display_name']

                if psutil.pid_exists(pid):
                    logger.info(f"停止 {display_name} (PID: {pid})...")
                    proc = psutil.Process(pid)
                    proc.terminate()

                    try:
                        proc.wait(timeout=5)
                    except psutil.TimeoutExpired:
                        logger.warning(f"强制终止 {display_name}...")
                        proc.kill()
            except Exception as e:
                logger.error(f"停止 {display_name} 失败: {e}")

        logger.info("所有组件已停止")

        # 清除进程信息
        self._clear_process_info()

    def _save_process_info(self):
        """保存进程信息到文件"""
        import json

        process_info = {}
        for component, process in self.processes.items():
            process_info[component] = {
                "pid": process.pid,
                "command": self.component_commands[component],
                "display_name": self.component_names.get(component, component),
                "started_at": time.time()
            }

        self.process_info_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.process_info_file, 'w', encoding='utf-8') as f:
            json.dump(process_info, f, indent=2, ensure_ascii=False)

    def _load_process_info(self) -> Dict:
        """加载进程信息"""
        import json

        if not self.process_info_file.exists():
            return {}

        try:
            with open(self.process_info_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"加载进程信息失败: {e}")
            return {}

    def _clear_process_info(self):
        """清除进程信息文件"""
        if self.process_info_file.exists():
            self.process_info_file.unlink()

    def get_running_components(self) -> List[str]:
        """获取正在运行的组件列表"""
        import psutil

        running = []
        process_info = self._load_process_info()

        for component, info in process_info.items():
            try:
                # 检查进程是否存在
                if psutil.pid_exists(info['pid']):
                    proc = psutil.Process(info['pid'])
                    if proc.is_running():
                        running.append(component)
            except Exception:
                pass

        return running

    def show_component_status(self):
        """显示组件状态"""
        print("\n" + "=" * 70)
        print(f"服务器角色: {self.role_manager.current_role}")
        print("=" * 70)

        status = self.role_manager.get_all_components_status()

        print("\n应在本服务器运行的组件:")
        print("-" * 70)

        for component, info in status["components"].items():
            if info["should_run_here"]:
                display_name = self.component_names.get(component, component)
                priority = info["priority"]
                cpu_mark = "[CPU密集]" if info["cpu_intensive"] else ""

                # 检查是否已启动
                running = "●" if component in self.processes else "○"

                print(f"{running} {display_name:20s} | 优先级: {priority:8s} {cpu_mark}")

        print("\n其他服务器的组件:")
        print("-" * 70)

        for component, info in status["components"].items():
            if not info["should_run_here"]:
                display_name = self.component_names.get(component, component)
                server = info["server"]
                print(f"  {display_name:20s} → {server}")

        print("\n" + "=" * 70)


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='组件启动器')
    parser.add_argument('--foreground', '-f', action='store_true',
                       help='前台运行(不推荐)')
    parser.add_argument('--delay', '-d', type=int, default=2,
                       help='组件启动间隔(秒)')
    parser.add_argument('--status', '-s', action='store_true',
                       help='只显示状态,不启动')
    parser.add_argument('--stop', action='store_true',
                       help='停止所有运行中的组件')

    args = parser.parse_args()

    launcher = ComponentLauncher()

    if args.status:
        launcher.show_component_status()
        return

    if args.stop:
        launcher.stop_all_components()
        return

    try:
        launcher.show_component_status()
        print("\n准备启动组件...")
        time.sleep(2)

        launcher.start_all_components(
            background=not args.foreground,
            delay=args.delay
        )

        if not args.foreground:
            print("\n所有组件已在后台运行")
            print("使用 stop_system 停止系统")
        else:
            print("\n按 Ctrl+C 停止所有组件")
            while True:
                time.sleep(1)

    except KeyboardInterrupt:
        print("\n\n正在停止组件...")
        launcher.stop_all_components()
        print("已停止")


if __name__ == "__main__":
    main()
