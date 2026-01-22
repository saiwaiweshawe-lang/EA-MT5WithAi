#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
服务器同步系统单元测试
"""

import os
import sys
import json
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from utilities.server_sync import (
    ServerSyncManager,
    DataReplicator,
    ServerRole,
    ServerStatus,
    HeartbeatData,
    SyncTask
)


class TestServerSyncManager(unittest.TestCase):
    """服务器同步管理器测试"""

    def setUp(self):
        """测试前准备"""
        self.test_dir = Path(__file__).parent / "test_sync"
        self.test_dir.mkdir(parents=True, exist_ok=True)

        # 创建测试配置
        self.test_config = {
            "server_id": "test-server-1",
            "role": "primary",
            "peer_server": {
                "url": "http://test-server-2:5000",
                "auth_token": "test-token"
            },
            "heartbeat_interval": 1,
            "heartbeat_timeout": 3,
            "failover_threshold": 2,
            "sync_interval": 1,
            "sync_batch_size": 10
        }

        config_path = self.test_dir / "server_sync_config.json"
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(self.test_config, f)

        self.manager = ServerSyncManager(config_path=str(config_path))

    def tearDown(self):
        """测试后清理"""
        if self.manager.running:
            self.manager.stop()

        import shutil
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_initialization(self):
        """测试初始化"""
        self.assertEqual(self.manager.server_id, "test-server-1")
        self.assertEqual(self.manager.role, ServerRole.PRIMARY)
        self.assertEqual(self.manager.heartbeat_interval, 1)
        self.assertEqual(self.manager.failover_threshold, 2)

    def test_heartbeat_data_creation(self):
        """测试心跳数据创建"""
        heartbeat = HeartbeatData(
            server_id="test-server",
            role="primary",
            status="healthy",
            timestamp=time.time(),
            cpu_usage=50.0,
            memory_usage=60.0,
            active_connections=10,
            pending_tasks=5,
            last_sync_time=time.time(),
            metadata={}
        )

        self.assertEqual(heartbeat.server_id, "test-server")
        self.assertEqual(heartbeat.role, "primary")
        self.assertEqual(heartbeat.status, "healthy")

    def test_receive_heartbeat(self):
        """测试接收心跳"""
        heartbeat_data = {
            "server_id": "test-server-2",
            "role": "backup",
            "status": "healthy",
            "timestamp": time.time(),
            "cpu_usage": 40.0,
            "memory_usage": 50.0,
            "active_connections": 5,
            "pending_tasks": 0,
            "last_sync_time": time.time(),
            "metadata": {}
        }

        self.manager.receive_heartbeat(heartbeat_data)

        self.assertEqual(len(self.manager.peer_heartbeat_history), 1)
        self.assertGreater(self.manager.peer_last_heartbeat, 0)
        self.assertEqual(self.manager.peer_status, ServerStatus.HEALTHY)

    def test_add_sync_task(self):
        """测试添加同步任务"""
        # 添加低优先级任务
        self.manager.add_sync_task(
            task_type='data',
            data={'key': 'test1', 'value': 'value1'},
            priority=8
        )

        # 添加高优先级任务
        self.manager.add_sync_task(
            task_type='config',
            data={'key': 'test2', 'value': 'value2'},
            priority=2
        )

        # 添加中优先级任务
        self.manager.add_sync_task(
            task_type='state',
            data={'key': 'test3', 'value': 'value3'},
            priority=5
        )

        self.assertEqual(len(self.manager.sync_queue), 3)

        # 验证优先级排序(优先级数字越小越靠前)
        first_task = self.manager.sync_queue[0]
        self.assertEqual(first_task.priority, 2)
        self.assertEqual(first_task.task_type, 'config')

    def test_sync_task_creation(self):
        """测试同步任务创建"""
        task = SyncTask(
            task_id="test-task-1",
            task_type="data",
            priority=5,
            data={'key': 'value'},
            timestamp=time.time()
        )

        self.assertEqual(task.status, "pending")
        self.assertEqual(task.retries, 0)
        self.assertEqual(task.max_retries, 3)

    def test_get_status(self):
        """测试获取状态"""
        status = self.manager.get_status()

        self.assertIn('server_id', status)
        self.assertIn('role', status)
        self.assertIn('status', status)
        self.assertIn('sync_queue_size', status)
        self.assertEqual(status['server_id'], 'test-server-1')
        self.assertEqual(status['role'], 'primary')

    @patch('utilities.server_sync.requests.post')
    def test_send_to_peer(self, mock_post):
        """测试发送数据到对端"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'success': True}
        mock_post.return_value = mock_response

        result = self.manager._send_to_peer(
            '/api/test',
            {'data': 'test'}
        )

        self.assertIsNotNone(result)
        self.assertTrue(result['success'])
        mock_post.assert_called_once()

    def test_role_update(self):
        """测试角色更新"""
        old_role = self.manager.role

        # 模拟故障转移
        self.manager.role = ServerRole.BACKUP
        self.manager._update_role_config()

        # 重新加载配置验证
        with open(self.manager.config_path, 'r') as f:
            config = json.load(f)

        self.assertEqual(config['role'], 'backup')

    def test_failover_callback(self):
        """测试故障转移回调"""
        callback_called = {'called': False}

        def test_callback(old_role, new_role):
            callback_called['called'] = True
            callback_called['old_role'] = old_role
            callback_called['new_role'] = new_role

        self.manager.register_failover_callback(test_callback)

        # 模拟备份服务器触发故障转移
        self.manager.role = ServerRole.BACKUP
        self.manager._trigger_failover()

        self.assertTrue(callback_called['called'])
        self.assertEqual(callback_called['old_role'], ServerRole.BACKUP)
        self.assertEqual(callback_called['new_role'], ServerRole.PRIMARY)

    def test_failback_callback(self):
        """测试回切回调"""
        callback_called = {'called': False}

        def test_callback(old_role, new_role):
            callback_called['called'] = True

        self.manager.register_failback_callback(test_callback)

        # 由于回切需要验证对端健康,我们需要 mock
        with patch.object(self.manager, '_verify_peer_health', return_value=True):
            self.manager.role = ServerRole.PRIMARY
            self.manager._trigger_failback()

            self.assertTrue(callback_called['called'])

    def test_consecutive_failures_tracking(self):
        """测试连续失败跟踪"""
        self.manager.role = ServerRole.BACKUP
        self.manager.peer_last_heartbeat = time.time() - 100  # 100秒前

        # 模拟心跳检查
        self.manager._check_peer_heartbeat()

        # 应该增加失败计数
        self.assertGreater(self.manager.consecutive_failures, 0)


class TestDataReplicator(unittest.TestCase):
    """数据复制器测试"""

    def setUp(self):
        """测试前准备"""
        self.test_dir = Path(__file__).parent / "test_replicator"
        self.test_dir.mkdir(parents=True, exist_ok=True)

        config_path = self.test_dir / "server_sync_config.json"
        test_config = {
            "server_id": "test-server",
            "role": "primary"
        }

        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(test_config, f)

        self.sync_manager = ServerSyncManager(config_path=str(config_path))
        self.replicator = DataReplicator(self.sync_manager)

    def tearDown(self):
        """测试后清理"""
        import shutil
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_replicate_data(self):
        """测试复制数据"""
        key = "test_key"
        value = {"data": "test_value"}

        self.replicator.replicate(key, value, priority=3)

        # 验证数据已存储
        stored_value = self.replicator.get(key)
        self.assertEqual(stored_value, value)

        # 验证同步任务已添加
        self.assertGreater(len(self.sync_manager.sync_queue), 0)

    def test_receive_replicated_data(self):
        """测试接收复制数据"""
        key = "received_key"
        value = {"data": "received_value"}

        self.replicator.receive_replicated_data(key, value)

        # 验证数据已存储
        stored_value = self.replicator.get(key)
        self.assertEqual(stored_value, value)

    def test_get_nonexistent_data(self):
        """测试获取不存在的数据"""
        result = self.replicator.get("nonexistent_key")
        self.assertIsNone(result)

    def test_thread_safety(self):
        """测试线程安全"""
        import threading

        def replicate_data(i):
            self.replicator.replicate(f"key_{i}", f"value_{i}")

        threads = []
        for i in range(10):
            thread = threading.Thread(target=replicate_data, args=(i,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # 验证所有数据都已复制
        for i in range(10):
            value = self.replicator.get(f"key_{i}")
            self.assertEqual(value, f"value_{i}")


class TestServerRoleAndStatus(unittest.TestCase):
    """服务器角色和状态枚举测试"""

    def test_server_role_enum(self):
        """测试服务器角色枚举"""
        self.assertEqual(ServerRole.PRIMARY.value, "primary")
        self.assertEqual(ServerRole.BACKUP.value, "backup")
        self.assertEqual(ServerRole.STANDALONE.value, "standalone")

    def test_server_status_enum(self):
        """测试服务器状态枚举"""
        self.assertEqual(ServerStatus.HEALTHY.value, "healthy")
        self.assertEqual(ServerStatus.DEGRADED.value, "degraded")
        self.assertEqual(ServerStatus.FAILED.value, "failed")
        self.assertEqual(ServerStatus.UNKNOWN.value, "unknown")


if __name__ == "__main__":
    unittest.main()
