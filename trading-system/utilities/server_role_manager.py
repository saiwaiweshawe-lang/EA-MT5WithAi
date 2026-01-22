#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
服务器角色管理模块 - 管理双服务器部署架构
"""

import os
import sys
import json
import logging
import socket
from pathlib import Path
from typing import Dict, List, Optional
import requests

# 配置日志
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


class ServerRoleManager:
    """服务器角色管理器"""

    def __init__(self, config_path: str = None):
        self.base_dir = Path(__file__).parent.parent

        # 加载部署配置
        if config_path is None:
            config_path = self.base_dir / "config" / "deployment_config.json"

        self.config = self._load_config(config_path)

        # 当前服务器角色
        self.current_role = self._detect_server_role()

        # 当前服务器应运行的组件
        self.components = self._get_server_components()

        logger.info(f"服务器角色: {self.current_role}")
        logger.info(f"应运行组件: {', '.join(self.components)}")

    def _load_config(self, config_path: Path) -> Dict:
        """加载部署配置"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"加载部署配置失败: {e}")
            return {}

    def _detect_server_role(self) -> str:
        """检测当前服务器角色"""
        # 方法1: 从环境变量读取
        env_role = os.getenv('SERVER_ROLE')
        if env_role in ['primary', 'compute', 'server1', 'server2']:
            if env_role in ['primary', 'server1']:
                return 'server1'
            return 'server2'

        # 方法2: 从本地配置文件读取
        local_config_path = self.base_dir / "config" / "server_local.json"
        if local_config_path.exists():
            try:
                with open(local_config_path, 'r', encoding='utf-8') as f:
                    local_config = json.load(f)
                    role = local_config.get('server_role')
                    if role:
                        return role
            except Exception as e:
                logger.warning(f"读取本地配置失败: {e}")

        # 方法3: 根据IP地址匹配
        try:
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)

            server_roles = self.config.get('server_roles', {})
            for server_id, server_info in server_roles.items():
                if server_info.get('ip') == local_ip:
                    return server_id
        except Exception as e:
            logger.warning(f"IP检测失败: {e}")

        # 默认返回server1
        logger.warning("无法检测服务器角色,默认使用server1")
        return 'server1'

    def _get_server_components(self) -> List[str]:
        """获取当前服务器应运行的组件"""
        server_roles = self.config.get('server_roles', {})
        server_info = server_roles.get(self.current_role, {})
        return server_info.get('components', [])

    def should_run_component(self, component_name: str) -> bool:
        """判断当前服务器是否应该运行指定组件"""
        return component_name in self.components

    def get_component_info(self, component_name: str) -> Optional[Dict]:
        """获取组件详细信息"""
        component_dist = self.config.get('component_distribution', {})
        return component_dist.get(component_name)

    def is_component_cpu_intensive(self, component_name: str) -> bool:
        """判断组件是否为CPU密集型"""
        info = self.get_component_info(component_name)
        return info.get('cpu_intensive', False) if info else False

    def get_component_priority(self, component_name: str) -> str:
        """获取组件优先级"""
        info = self.get_component_info(component_name)
        return info.get('priority', 'medium') if info else 'medium'

    def get_remote_server_url(self) -> str:
        """获取远程服务器URL"""
        comm_config = self.config.get('communication', {})

        if self.current_role == 'server1':
            # server1访问server2
            return comm_config.get('server1_to_server2', {}).get('base_url', '')
        else:
            # server2访问server1
            return comm_config.get('server2_to_server1', {}).get('base_url', '')

    def get_api_key(self) -> str:
        """获取API密钥"""
        comm_config = self.config.get('communication', {})

        if self.current_role == 'server1':
            return comm_config.get('server1_to_server2', {}).get('api_key', '')
        else:
            return comm_config.get('server2_to_server1', {}).get('api_key', '')

    def call_remote_api(self, endpoint: str, method: str = 'GET',
                       data: Dict = None, timeout: int = None) -> Optional[Dict]:
        """调用远程服务器API"""
        remote_url = self.get_remote_server_url()
        if not remote_url:
            logger.error("未配置远程服务器URL")
            return None

        api_key = self.get_api_key()

        # 获取通信配置
        comm_config = self.config.get('communication', {})
        config_key = 'server1_to_server2' if self.current_role == 'server1' else 'server2_to_server1'
        comm_settings = comm_config.get(config_key, {})

        if timeout is None:
            timeout = comm_settings.get('timeout_seconds', 30)

        retry_times = comm_settings.get('retry_times', 3)

        # 构建完整URL
        url = f"{remote_url.rstrip('/')}/{endpoint.lstrip('/')}"

        # 请求头
        headers = {
            'X-API-Key': api_key,
            'Content-Type': 'application/json'
        }

        # 重试逻辑
        for attempt in range(retry_times):
            try:
                if method.upper() == 'GET':
                    response = requests.get(url, headers=headers, timeout=timeout)
                elif method.upper() == 'POST':
                    response = requests.post(url, headers=headers, json=data, timeout=timeout)
                elif method.upper() == 'PUT':
                    response = requests.put(url, headers=headers, json=data, timeout=timeout)
                else:
                    logger.error(f"不支持的HTTP方法: {method}")
                    return None

                response.raise_for_status()
                return response.json()

            except requests.exceptions.RequestException as e:
                logger.warning(f"API调用失败 (尝试 {attempt + 1}/{retry_times}): {e}")
                if attempt == retry_times - 1:
                    logger.error(f"API调用最终失败: {url}")
                    return None

        return None

    def check_remote_health(self) -> bool:
        """检查远程服务器健康状态"""
        try:
            result = self.call_remote_api('api/health', timeout=5)
            return result is not None and result.get('status') == 'ok'
        except Exception as e:
            logger.error(f"健康检查失败: {e}")
            return False

    def get_resource_limits(self) -> Dict:
        """获取当前服务器资源限制"""
        resource_limits = self.config.get('resource_limits', {})
        return resource_limits.get(self.current_role, {})

    def should_run_cpu_task_now(self, task_type: str = 'ai_training') -> bool:
        """判断当前时间是否应该运行CPU密集型任务"""
        from datetime import datetime

        resource_limits = self.get_resource_limits()
        schedule = resource_limits.get('cpu_intensive_schedule', {})
        task_schedule = schedule.get(task_type, {})

        if not task_schedule.get('enabled', False):
            return False

        current_hour = datetime.now().hour
        allowed_hours = task_schedule.get('allowed_hours', [])

        return current_hour in allowed_hours

    def get_max_concurrent_tasks(self, task_type: str = 'ai_training') -> int:
        """获取CPU密集型任务的最大并发数"""
        resource_limits = self.get_resource_limits()
        schedule = resource_limits.get('cpu_intensive_schedule', {})
        task_schedule = schedule.get(task_type, {})

        return task_schedule.get('max_concurrent_tasks', 1)

    def get_all_components_status(self) -> Dict:
        """获取所有组件的运行状态"""
        status = {
            "server_role": self.current_role,
            "components": {}
        }

        component_dist = self.config.get('component_distribution', {})
        for component_name in component_dist.keys():
            should_run = self.should_run_component(component_name)
            info = self.get_component_info(component_name)

            status["components"][component_name] = {
                "should_run_here": should_run,
                "server": info.get('server') if info else None,
                "priority": self.get_component_priority(component_name),
                "cpu_intensive": self.is_component_cpu_intensive(component_name)
            }

        return status

    def save_local_config(self, role: str = None):
        """保存本地服务器配置"""
        if role is None:
            role = self.current_role

        local_config = {
            "server_role": role,
            "updated_at": str(Path(__file__).parent.parent)
        }

        local_config_path = self.base_dir / "config" / "server_local.json"

        try:
            with open(local_config_path, 'w', encoding='utf-8') as f:
                json.dump(local_config, f, indent=2, ensure_ascii=False)
            logger.info(f"本地配置已保存: {role}")
        except Exception as e:
            logger.error(f"保存本地配置失败: {e}")


def main():
    """主函数 - 用于测试"""
    import sys

    manager = ServerRoleManager()

    print("=" * 50)
    print("服务器角色管理器")
    print("=" * 50)
    print(f"\n当前服务器角色: {manager.current_role}")
    print(f"应运行组件: {', '.join(manager.components)}")

    print("\n" + "=" * 50)
    print("所有组件状态:")
    print("=" * 50)

    status = manager.get_all_components_status()
    for component, info in status["components"].items():
        should_run = "✓" if info["should_run_here"] else "✗"
        cpu_mark = "[CPU密集]" if info["cpu_intensive"] else ""
        priority = info["priority"]
        print(f"{should_run} {component:30s} 优先级:{priority:8s} {cpu_mark}")

    print("\n" + "=" * 50)
    print("资源限制:")
    print("=" * 50)
    limits = manager.get_resource_limits()
    print(f"最大CPU: {limits.get('max_cpu_percent', 'N/A')}%")
    print(f"最大内存: {limits.get('max_memory_percent', 'N/A')}%")

    print("\n" + "=" * 50)
    print("CPU密集型任务调度:")
    print("=" * 50)
    print(f"AI训练是否可运行: {manager.should_run_cpu_task_now('ai_training')}")
    print(f"AI训练最大并发: {manager.get_max_concurrent_tasks('ai_training')}")
    print(f"模型进化是否可运行: {manager.should_run_cpu_task_now('model_evolution')}")
    print(f"模型进化最大并发: {manager.get_max_concurrent_tasks('model_evolution')}")

    print("\n" + "=" * 50)
    print("远程服务器:")
    print("=" * 50)
    print(f"远程URL: {manager.get_remote_server_url()}")
    print(f"健康检查: ", end='')
    if manager.check_remote_health():
        print("✓ 正常")
    else:
        print("✗ 无法连接")

    # 如果提供了命令行参数,保存角色配置
    if len(sys.argv) > 1:
        role = sys.argv[1]
        if role in ['server1', 'server2', 'primary', 'compute']:
            if role == 'primary':
                role = 'server1'
            elif role == 'compute':
                role = 'server2'
            manager.save_local_config(role)
            print(f"\n已保存服务器角色配置: {role}")


if __name__ == "__main__":
    main()
