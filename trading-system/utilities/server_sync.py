#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
双服务器同步和故障转移系统
实现主备服务器之间的状态同步、健康监测和自动故障转移
"""

import os
import sys
import json
import time
import socket
import logging
import threading
import requests
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum
from collections import deque

logger = logging.getLogger(__name__)


class ServerRole(Enum):
    """服务器角色"""
    PRIMARY = "primary"      # 主服务器
    BACKUP = "backup"        # 备份服务器
    STANDALONE = "standalone"  # 单机模式


class ServerStatus(Enum):
    """服务器状态"""
    HEALTHY = "healthy"      # 健康
    DEGRADED = "degraded"    # 降级
    FAILED = "failed"        # 失败
    UNKNOWN = "unknown"      # 未知


@dataclass
class HeartbeatData:
    """心跳数据"""
    server_id: str
    role: str
    status: str
    timestamp: float
    cpu_usage: float
    memory_usage: float
    active_connections: int
    pending_tasks: int
    last_sync_time: float
    metadata: Dict[str, Any]


@dataclass
class SyncTask:
    """同步任务"""
    task_id: str
    task_type: str  # state, config, data, log
    priority: int   # 1-10, 数字越小优先级越高
    data: Dict[str, Any]
    timestamp: float
    retries: int = 0
    max_retries: int = 3
    status: str = "pending"  # pending, syncing, completed, failed


class ServerSyncManager:
    """服务器同步管理器"""

    def __init__(self, config_path: str = None):
        """
        初始化同步管理器

        Args:
            config_path: 配置文件路径
        """
        self.base_dir = Path(__file__).parent.parent

        if config_path is None:
            config_path = self.base_dir / "config" / "server_sync_config.json"

        self.config_path = Path(config_path)
        self.config = self._load_config()

        # 服务器信息
        self.server_id = self.config.get('server_id', socket.gethostname())
        self.role = ServerRole(self.config.get('role', 'standalone'))
        self.status = ServerStatus.HEALTHY

        # 对端服务器信息
        self.peer_server = self.config.get('peer_server', {})
        self.peer_status = ServerStatus.UNKNOWN
        self.peer_last_heartbeat = 0

        # 心跳配置
        self.heartbeat_interval = self.config.get('heartbeat_interval', 5)
        self.heartbeat_timeout = self.config.get('heartbeat_timeout', 15)
        self.failover_threshold = self.config.get('failover_threshold', 3)

        # 同步配置
        self.sync_interval = self.config.get('sync_interval', 10)
        self.sync_batch_size = self.config.get('sync_batch_size', 100)

        # 同步队列
        self.sync_queue = deque()
        self.sync_lock = threading.Lock()

        # 心跳历史
        self.heartbeat_history = deque(maxlen=100)
        self.peer_heartbeat_history = deque(maxlen=100)

        # 故障计数
        self.consecutive_failures = 0

        # 线程控制
        self.running = False
        self.heartbeat_thread = None
        self.sync_thread = None

        # 回调函数
        self.failover_callbacks: List[Callable] = []
        self.failback_callbacks: List[Callable] = []

        logger.info(f"服务器同步管理器初始化: {self.server_id} ({self.role.value})")

    def _load_config(self) -> Dict:
        """加载配置"""
        if not self.config_path.exists():
            logger.warning(f"配置文件不存在: {self.config_path}")
            return {}

        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"加载配置失败: {e}")
            return {}

    def start(self):
        """启动同步管理器"""
        if self.running:
            logger.warning("同步管理器已在运行")
            return

        self.running = True

        # 启动心跳线程
        self.heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop,
            daemon=True
        )
        self.heartbeat_thread.start()

        # 启动同步线程
        self.sync_thread = threading.Thread(
            target=self._sync_loop,
            daemon=True
        )
        self.sync_thread.start()

        logger.info("服务器同步管理器已启动")

    def stop(self):
        """停止同步管理器"""
        self.running = False

        if self.heartbeat_thread:
            self.heartbeat_thread.join(timeout=5)

        if self.sync_thread:
            self.sync_thread.join(timeout=5)

        logger.info("服务器同步管理器已停止")

    def _heartbeat_loop(self):
        """心跳循环"""
        while self.running:
            try:
                # 发送心跳
                self._send_heartbeat()

                # 检查对端心跳
                self._check_peer_heartbeat()

                time.sleep(self.heartbeat_interval)
            except Exception as e:
                logger.error(f"心跳循环错误: {e}")
                time.sleep(self.heartbeat_interval)

    def _send_heartbeat(self):
        """发送心跳"""
        try:
            # 收集系统信息
            import psutil
            cpu_usage = psutil.cpu_percent(interval=1)
            memory_usage = psutil.virtual_memory().percent

            # 构建心跳数据
            heartbeat = HeartbeatData(
                server_id=self.server_id,
                role=self.role.value,
                status=self.status.value,
                timestamp=time.time(),
                cpu_usage=cpu_usage,
                memory_usage=memory_usage,
                active_connections=0,  # 由具体应用填充
                pending_tasks=len(self.sync_queue),
                last_sync_time=time.time(),
                metadata={}
            )

            # 记录心跳
            self.heartbeat_history.append(heartbeat)

            # 发送到对端服务器
            if self.peer_server and self.role != ServerRole.STANDALONE:
                self._send_to_peer('/api/heartbeat', asdict(heartbeat))

            logger.debug(f"发送心跳: {self.server_id}")
        except Exception as e:
            logger.error(f"发送心跳失败: {e}")

    def _check_peer_heartbeat(self):
        """检查对端心跳"""
        if self.role == ServerRole.STANDALONE:
            return

        current_time = time.time()
        time_since_last_heartbeat = current_time - self.peer_last_heartbeat

        # 检查心跳超时
        if self.peer_last_heartbeat > 0 and time_since_last_heartbeat > self.heartbeat_timeout:
            self.consecutive_failures += 1
            logger.warning(f"对端心跳超时: {time_since_last_heartbeat:.1f}秒 (失败次数: {self.consecutive_failures})")

            # 达到故障转移阈值
            if self.consecutive_failures >= self.failover_threshold:
                if self.role == ServerRole.BACKUP:
                    self._trigger_failover()
        else:
            # 重置故障计数
            if self.consecutive_failures > 0:
                logger.info("对端服务器恢复")
                self.consecutive_failures = 0

                # 如果当前是主服务器,考虑回切
                if self.role == ServerRole.PRIMARY:
                    self._trigger_failback()

    def _trigger_failover(self):
        """触发故障转移"""
        logger.critical("触发故障转移: 备份服务器升级为主服务器")

        old_role = self.role
        self.role = ServerRole.PRIMARY
        self.peer_status = ServerStatus.FAILED

        # 更新配置
        self._update_role_config()

        # 执行故障转移回调
        for callback in self.failover_callbacks:
            try:
                callback(old_role, self.role)
            except Exception as e:
                logger.error(f"故障转移回调失败: {e}")

        logger.info("故障转移完成")

    def _trigger_failback(self):
        """触发回切"""
        if self.role != ServerRole.PRIMARY:
            return

        # 检查原主服务器是否真的恢复
        if not self._verify_peer_health():
            return

        logger.info("触发回切: 主服务器降级为备份服务器")

        old_role = self.role
        self.role = ServerRole.BACKUP
        self.peer_status = ServerStatus.HEALTHY

        # 更新配置
        self._update_role_config()

        # 执行回切回调
        for callback in self.failback_callbacks:
            try:
                callback(old_role, self.role)
            except Exception as e:
                logger.error(f"回切回调失败: {e}")

        logger.info("回切完成")

    def _verify_peer_health(self) -> bool:
        """验证对端服务器健康状态"""
        try:
            response = self._send_to_peer('/api/health', timeout=5)
            if response and response.get('status') == 'healthy':
                return True
        except Exception as e:
            logger.error(f"验证对端健康状态失败: {e}")

        return False

    def _update_role_config(self):
        """更新角色配置"""
        try:
            self.config['role'] = self.role.value
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            logger.info(f"角色配置已更新: {self.role.value}")
        except Exception as e:
            logger.error(f"更新角色配置失败: {e}")

    def _sync_loop(self):
        """同步循环"""
        while self.running:
            try:
                self._process_sync_queue()
                time.sleep(self.sync_interval)
            except Exception as e:
                logger.error(f"同步循环错误: {e}")
                time.sleep(self.sync_interval)

    def _process_sync_queue(self):
        """处理同步队列"""
        if not self.sync_queue:
            return

        if self.role == ServerRole.STANDALONE:
            return

        # 批量处理同步任务
        batch = []
        with self.sync_lock:
            for _ in range(min(self.sync_batch_size, len(self.sync_queue))):
                if self.sync_queue:
                    batch.append(self.sync_queue.popleft())

        if not batch:
            return

        logger.info(f"处理同步任务: {len(batch)} 个")

        for task in batch:
            self._execute_sync_task(task)

    def _execute_sync_task(self, task: SyncTask):
        """执行同步任务"""
        try:
            task.status = "syncing"

            # 根据任务类型执行不同的同步逻辑
            endpoint = f'/api/sync/{task.task_type}'
            response = self._send_to_peer(endpoint, task.data, timeout=30)

            if response and response.get('success'):
                task.status = "completed"
                logger.debug(f"同步任务完成: {task.task_id}")
            else:
                raise Exception(f"同步失败: {response}")
        except Exception as e:
            task.retries += 1
            if task.retries >= task.max_retries:
                task.status = "failed"
                logger.error(f"同步任务失败 (已重试{task.retries}次): {task.task_id} - {e}")
            else:
                task.status = "pending"
                with self.sync_lock:
                    self.sync_queue.append(task)
                logger.warning(f"同步任务重试: {task.task_id} ({task.retries}/{task.max_retries})")

    def _send_to_peer(self, endpoint: str, data: Dict = None, timeout: int = 10) -> Optional[Dict]:
        """发送数据到对端服务器"""
        if not self.peer_server:
            return None

        url = f"{self.peer_server.get('url')}{endpoint}"
        headers = {'Content-Type': 'application/json'}

        # 添加认证
        auth_token = self.peer_server.get('auth_token')
        if auth_token:
            headers['Authorization'] = f'Bearer {auth_token}'

        try:
            if data:
                response = requests.post(url, json=data, headers=headers, timeout=timeout)
            else:
                response = requests.get(url, headers=headers, timeout=timeout)

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"对端响应错误: {response.status_code}")
                return None
        except requests.exceptions.Timeout:
            logger.error(f"对端请求超时: {url}")
            return None
        except Exception as e:
            logger.error(f"发送到对端失败: {e}")
            return None

    def add_sync_task(self, task_type: str, data: Dict, priority: int = 5):
        """
        添加同步任务

        Args:
            task_type: 任务类型 (state, config, data, log)
            data: 同步数据
            priority: 优先级 (1-10)
        """
        task = SyncTask(
            task_id=f"{task_type}_{int(time.time() * 1000)}",
            task_type=task_type,
            priority=priority,
            data=data,
            timestamp=time.time()
        )

        with self.sync_lock:
            # 按优先级插入
            inserted = False
            for i, existing_task in enumerate(self.sync_queue):
                if task.priority < existing_task.priority:
                    self.sync_queue.insert(i, task)
                    inserted = True
                    break

            if not inserted:
                self.sync_queue.append(task)

        logger.debug(f"添加同步任务: {task.task_id}")

    def receive_heartbeat(self, heartbeat_data: Dict):
        """
        接收对端心跳

        Args:
            heartbeat_data: 心跳数据
        """
        try:
            heartbeat = HeartbeatData(**heartbeat_data)
            self.peer_heartbeat_history.append(heartbeat)
            self.peer_last_heartbeat = heartbeat.timestamp
            self.peer_status = ServerStatus(heartbeat.status)

            logger.debug(f"收到对端心跳: {heartbeat.server_id}")
        except Exception as e:
            logger.error(f"处理对端心跳失败: {e}")

    def register_failover_callback(self, callback: Callable):
        """注册故障转移回调"""
        self.failover_callbacks.append(callback)

    def register_failback_callback(self, callback: Callable):
        """注册回切回调"""
        self.failback_callbacks.append(callback)

    def get_status(self) -> Dict:
        """获取同步状态"""
        return {
            'server_id': self.server_id,
            'role': self.role.value,
            'status': self.status.value,
            'peer_status': self.peer_status.value,
            'sync_queue_size': len(self.sync_queue),
            'consecutive_failures': self.consecutive_failures,
            'last_heartbeat': self.peer_last_heartbeat,
            'time_since_last_heartbeat': time.time() - self.peer_last_heartbeat if self.peer_last_heartbeat > 0 else -1
        }

    def force_failover(self):
        """强制故障转移(用于测试或维护)"""
        if self.role == ServerRole.BACKUP:
            logger.warning("手动触发故障转移")
            self._trigger_failover()
        else:
            logger.warning("只有备份服务器可以执行故障转移")

    def force_failback(self):
        """强制回切(用于测试或维护)"""
        if self.role == ServerRole.PRIMARY:
            logger.warning("手动触发回切")
            self._trigger_failback()
        else:
            logger.warning("只有主服务器可以执行回切")


class DataReplicator:
    """数据复制器"""

    def __init__(self, sync_manager: ServerSyncManager):
        self.sync_manager = sync_manager
        self.replicated_data = {}
        self.lock = threading.Lock()

    def replicate(self, key: str, value: Any, priority: int = 5):
        """
        复制数据到对端

        Args:
            key: 数据键
            value: 数据值
            priority: 优先级
        """
        with self.lock:
            self.replicated_data[key] = {
                'value': value,
                'timestamp': time.time()
            }

        # 添加同步任务
        self.sync_manager.add_sync_task(
            task_type='data',
            data={'key': key, 'value': value},
            priority=priority
        )

    def get(self, key: str) -> Optional[Any]:
        """获取复制数据"""
        with self.lock:
            data = self.replicated_data.get(key)
            return data['value'] if data else None

    def receive_replicated_data(self, key: str, value: Any):
        """接收复制数据"""
        with self.lock:
            self.replicated_data[key] = {
                'value': value,
                'timestamp': time.time()
            }
        logger.debug(f"接收复制数据: {key}")


def main():
    """主函数 - 用于测试"""
    import argparse

    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )

    parser = argparse.ArgumentParser(description='服务器同步管理器')
    parser.add_argument('--config', '-c', help='配置文件路径')
    parser.add_argument('--role', '-r', choices=['primary', 'backup', 'standalone'],
                       help='服务器角色')
    parser.add_argument('--status', '-s', action='store_true',
                       help='显示同步状态')
    parser.add_argument('--failover', action='store_true',
                       help='手动触发故障转移')

    args = parser.parse_args()

    # 创建同步管理器
    manager = ServerSyncManager(config_path=args.config)

    if args.role:
        manager.role = ServerRole(args.role)
        manager._update_role_config()
        print(f"角色已设置为: {args.role}")

    if args.status:
        status = manager.get_status()
        print(json.dumps(status, indent=2, ensure_ascii=False))
        return

    if args.failover:
        manager.force_failover()
        print("故障转移已触发")
        return

    # 启动管理器
    manager.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n正在停止...")
        manager.stop()


if __name__ == "__main__":
    main()
