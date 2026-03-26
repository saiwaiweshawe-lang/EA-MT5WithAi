#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置管理器单元测试
"""

import os
import sys
import json
import unittest
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from utilities.config_center import ConfigCenter


class TestConfigCenter(unittest.TestCase):
    """配置管理器测试"""

    def setUp(self):
        """测试前准备"""
        self.test_dir = Path(__file__).parent / "test_configs"
        self.test_dir.mkdir(parents=True, exist_ok=True)

        self.manager = ConfigCenter(config_dir=str(self.test_dir))

        # 创建测试配置
        self.test_config = {
            "server": {
                "ip": "127.0.0.1",
                "port": 5000
            },
            "database": {
                "host": "localhost",
                "password": "test123"
            }
        }

    def tearDown(self):
        """测试后清理"""
        # 清理测试文件
        import shutil
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_save_and_load_config(self):
        """测试保存和加载配置"""
        # 保存配置
        success = self.manager.save_config(
            "test_config.json",
            self.test_config,
            encrypt=False,
            backup=False
        )
        self.assertTrue(success)

        # 加载配置
        loaded = self.manager.load_config(
            "test_config.json",
            use_cache=False,
            decrypt=False
        )

        self.assertEqual(loaded["server"]["ip"], "127.0.0.1")
        self.assertEqual(loaded["server"]["port"], 5000)

    def test_get_config_value(self):
        """测试获取配置值"""
        # 保存配置
        self.manager.save_config(
            "test_config.json",
            self.test_config,
            encrypt=False,
            backup=False
        )

        # 获取嵌套值
        ip = self.manager.get_config_value("test_config.json", "server.ip")
        self.assertEqual(ip, "127.0.0.1")

        port = self.manager.get_config_value("test_config.json", "server.port")
        self.assertEqual(port, 5000)

        # 不存在的值应返回默认值
        value = self.manager.get_config_value(
            "test_config.json",
            "nonexistent.key",
            default="default_value"
        )
        self.assertEqual(value, "default_value")

    def test_set_config_value(self):
        """测试设置配置值"""
        # 保存初始配置
        self.manager.save_config(
            "test_config.json",
            self.test_config,
            encrypt=False,
            backup=False
        )

        # 更新值
        success = self.manager.set_config_value(
            "test_config.json",
            "server.port",
            8080
        )
        self.assertTrue(success)

        # 验证更新
        port = self.manager.get_config_value("test_config.json", "server.port")
        self.assertEqual(port, 8080)

    def test_config_caching(self):
        """测试配置缓存"""
        # 保存配置
        self.manager.save_config(
            "test_config.json",
            self.test_config,
            encrypt=False,
            backup=False
        )

        # 第一次加载
        config1 = self.manager.load_config("test_config.json", use_cache=True)

        # 第二次加载(应该使用缓存)
        config2 = self.manager.load_config("test_config.json", use_cache=True)

        # 应该是同一个对象
        self.assertIs(config1, config2)

        # 清除缓存后重新加载
        self.manager.clear_cache()
        config3 = self.manager.load_config("test_config.json", use_cache=True)

        # 应该是新对象
        self.assertIsNot(config1, config3)

    def test_list_configs(self):
        """测试列出配置文件"""
        # 创建多个配置文件
        self.manager.save_config("config1.json", {"test": 1}, encrypt=False, backup=False)
        self.manager.save_config("config2.json", {"test": 2}, encrypt=False, backup=False)
        self.manager.save_config("config3.json", {"test": 3}, encrypt=False, backup=False)

        configs = self.manager.list_configs()

        self.assertEqual(len(configs), 3)
        self.assertIn("config1.json", configs)
        self.assertIn("config2.json", configs)
        self.assertIn("config3.json", configs)


if __name__ == "__main__":
    unittest.main()
