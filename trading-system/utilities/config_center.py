#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置管理中心
提供统一的配置加载、验证、更新、版本管理
"""

import os
import sys
import json
import shutil
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass, asdict

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from utilities.config_encryption import ConfigEncryption

logger = logging.getLogger(__name__)


@dataclass
class ConfigVersion:
    """配置版本信息"""
    version: str
    timestamp: float
    author: str
    description: str
    file_path: str


class ConfigCenter:
    """配置管理中心"""

    def __init__(self, config_dir: str = None):
        self.base_dir = Path(__file__).parent.parent

        if config_dir is None:
            config_dir = self.base_dir / "config"

        self.config_dir = Path(config_dir)
        self.versions_dir = self.config_dir / ".versions"
        self.versions_dir.mkdir(parents=True, exist_ok=True)

        # 配置加密
        self.encryption = ConfigEncryption()

        # 配置缓存
        self.config_cache: Dict[str, Dict] = {}

        # 配置版本记录
        self.version_history: Dict[str, List[ConfigVersion]] = {}
        self._load_version_history()

        # 配置模式定义
        self.config_schemas = self._load_schemas()

    def _load_schemas(self) -> Dict:
        """加载配置模式"""
        return {
            "telegram_config.json": {
                "required_fields": ["bot_token", "chat_id"],
                "optional_fields": ["allowed_users", "admin_users"]
            },
            "mt5_config.json": {
                "required_fields": ["server", "login", "password"],
                "optional_fields": ["timeout", "max_bars"]
            },
            "deployment_config.json": {
                "required_fields": ["deployment_mode", "server_roles"],
                "optional_fields": ["communication", "resource_limits"]
            }
        }

    def _load_version_history(self):
        """加载版本历史"""
        history_file = self.versions_dir / "history.json"

        if history_file.exists():
            try:
                with open(history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for filename, versions in data.items():
                        self.version_history[filename] = [
                            ConfigVersion(**v) for v in versions
                        ]
            except Exception as e:
                logger.error(f"加载版本历史失败: {e}")

    def _save_version_history(self):
        """保存版本历史"""
        history_file = self.versions_dir / "history.json"

        try:
            data = {}
            for filename, versions in self.version_history.items():
                data[filename] = [asdict(v) for v in versions]

            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"保存版本历史失败: {e}")

    def load_config(self, config_name: str, use_cache: bool = True,
                   decrypt: bool = True) -> Dict:
        """
        加载配置

        Args:
            config_name: 配置文件名
            use_cache: 是否使用缓存
            decrypt: 是否解密

        Returns:
            配置字典
        """
        # 检查缓存
        if use_cache and config_name in self.config_cache:
            return self.config_cache[config_name]

        config_path = self.config_dir / config_name

        if not config_path.exists():
            logger.error(f"配置文件不存在: {config_path}")
            return {}

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)

            # 解密
            if decrypt:
                config = self.encryption.decrypt_config(config)

            # 缓存
            if use_cache:
                self.config_cache[config_name] = config

            logger.info(f"已加载配置: {config_name}")
            return config

        except Exception as e:
            logger.error(f"加载配置失败 {config_name}: {e}")
            return {}

    def save_config(self, config_name: str, config: Dict, encrypt: bool = True,
                   backup: bool = True, version_info: str = "") -> bool:
        """
        保存配置

        Args:
            config_name: 配置文件名
            config: 配置字典
            encrypt: 是否加密
            backup: 是否备份旧版本
            version_info: 版本说明

        Returns:
            是否保存成功
        """
        config_path = self.config_dir / config_name

        try:
            # 备份旧版本
            if backup and config_path.exists():
                self._backup_config(config_name, version_info)

            # 加密
            if encrypt:
                config = self.encryption.encrypt_config(config)

            # 保存
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)

            # 清除缓存
            if config_name in self.config_cache:
                del self.config_cache[config_name]

            logger.info(f"已保存配置: {config_name}")
            return True

        except Exception as e:
            logger.error(f"保存配置失败 {config_name}: {e}")
            return False

    def _backup_config(self, config_name: str, description: str = ""):
        """备份配置"""
        config_path = self.config_dir / config_name

        if not config_path.exists():
            return

        # 生成版本号
        timestamp = datetime.now()
        version = timestamp.strftime("%Y%m%d_%H%M%S")

        # 备份文件路径
        backup_dir = self.versions_dir / config_name.replace('.json', '')
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_path = backup_dir / f"{version}.json"

        # 复制文件
        shutil.copy2(config_path, backup_path)

        # 记录版本
        version_info = ConfigVersion(
            version=version,
            timestamp=timestamp.timestamp(),
            author="system",
            description=description or "自动备份",
            file_path=str(backup_path)
        )

        if config_name not in self.version_history:
            self.version_history[config_name] = []

        self.version_history[config_name].append(version_info)
        self._save_version_history()

        logger.info(f"已备份配置 {config_name} -> {version}")

    def restore_config(self, config_name: str, version: str) -> bool:
        """
        恢复配置到指定版本

        Args:
            config_name: 配置文件名
            version: 版本号

        Returns:
            是否恢复成功
        """
        if config_name not in self.version_history:
            logger.error(f"配置 {config_name} 无版本历史")
            return False

        # 查找版本
        version_info = None
        for v in self.version_history[config_name]:
            if v.version == version:
                version_info = v
                break

        if not version_info:
            logger.error(f"未找到版本: {version}")
            return False

        # 恢复文件
        backup_path = Path(version_info.file_path)
        config_path = self.config_dir / config_name

        if not backup_path.exists():
            logger.error(f"备份文件不存在: {backup_path}")
            return False

        try:
            # 先备份当前配置
            self._backup_config(config_name, f"恢复前备份(恢复到{version})")

            # 恢复
            shutil.copy2(backup_path, config_path)

            # 清除缓存
            if config_name in self.config_cache:
                del self.config_cache[config_name]

            logger.info(f"已恢复配置 {config_name} 到版本 {version}")
            return True

        except Exception as e:
            logger.error(f"恢复配置失败: {e}")
            return False

    def validate_config(self, config_name: str, config: Dict = None) -> tuple[bool, List[str]]:
        """
        验证配置

        Args:
            config_name: 配置文件名
            config: 配置字典(如果为None则从文件加载)

        Returns:
            (是否有效, 错误消息列表)
        """
        if config is None:
            config = self.load_config(config_name, use_cache=False, decrypt=True)

        errors = []

        # 检查模式
        schema = self.config_schemas.get(config_name)
        if not schema:
            logger.warning(f"配置 {config_name} 无验证模式")
            return True, []

        # 检查必需字段
        for field in schema.get("required_fields", []):
            if field not in config or config[field] is None or config[field] == "":
                errors.append(f"缺少必需字段: {field}")

        # 类型检查(简单示例)
        if config_name == "mt5_config.json":
            if "login" in config and not isinstance(config["login"], (int, str)):
                errors.append("login 字段类型错误")

        is_valid = len(errors) == 0
        return is_valid, errors

    def get_config_value(self, config_name: str, key_path: str,
                        default: Any = None) -> Any:
        """
        获取配置值(支持点号路径)

        Args:
            config_name: 配置文件名
            key_path: 键路径,如 "server.ip"
            default: 默认值

        Returns:
            配置值
        """
        config = self.load_config(config_name)
        keys = key_path.split('.')
        value = config

        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default

        return value

    def set_config_value(self, config_name: str, key_path: str, value: Any,
                        save: bool = True) -> bool:
        """
        设置配置值(支持点号路径)

        Args:
            config_name: 配置文件名
            key_path: 键路径,如 "server.ip"
            value: 值
            save: 是否立即保存

        Returns:
            是否设置成功
        """
        config = self.load_config(config_name, use_cache=False, decrypt=True)
        keys = key_path.split('.')

        # 导航到目标位置
        current = config
        for i, key in enumerate(keys[:-1]):
            if key not in current:
                current[key] = {}
            current = current[key]

        # 设置值
        current[keys[-1]] = value

        # 保存
        if save:
            return self.save_config(
                config_name,
                config,
                version_info=f"更新 {key_path} = {value}"
            )
        else:
            # 更新缓存
            self.config_cache[config_name] = config
            return True

    def list_configs(self) -> List[str]:
        """列出所有配置文件"""
        configs = []
        for file in self.config_dir.glob("*.json"):
            if not file.name.startswith('.'):
                configs.append(file.name)
        return sorted(configs)

    def get_version_history(self, config_name: str) -> List[ConfigVersion]:
        """获取配置版本历史"""
        return self.version_history.get(config_name, [])

    def export_config(self, config_name: str, export_path: str,
                     decrypt: bool = True) -> bool:
        """
        导出配置

        Args:
            config_name: 配置文件名
            export_path: 导出路径
            decrypt: 是否解密后导出

        Returns:
            是否导出成功
        """
        config = self.load_config(config_name, use_cache=False, decrypt=decrypt)

        try:
            export_path = Path(export_path)
            export_path.parent.mkdir(parents=True, exist_ok=True)

            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)

            logger.info(f"已导出配置 {config_name} -> {export_path}")
            return True

        except Exception as e:
            logger.error(f"导出配置失败: {e}")
            return False

    def import_config(self, config_name: str, import_path: str,
                     encrypt: bool = True, backup: bool = True) -> bool:
        """
        导入配置

        Args:
            config_name: 配置文件名
            import_path: 导入路径
            encrypt: 是否加密
            backup: 是否备份当前配置

        Returns:
            是否导入成功
        """
        import_path = Path(import_path)

        if not import_path.exists():
            logger.error(f"导入文件不存在: {import_path}")
            return False

        try:
            with open(import_path, 'r', encoding='utf-8') as f:
                config = json.load(f)

            # 验证配置
            is_valid, errors = self.validate_config(config_name, config)
            if not is_valid:
                logger.error(f"配置验证失败: {errors}")
                return False

            # 保存
            return self.save_config(
                config_name,
                config,
                encrypt=encrypt,
                backup=backup,
                version_info=f"从 {import_path.name} 导入"
            )

        except Exception as e:
            logger.error(f"导入配置失败: {e}")
            return False

    def sync_configs(self, remote_dir: str, direction: str = "pull") -> bool:
        """
        同步配置

        Args:
            remote_dir: 远程配置目录
            direction: 同步方向 (pull=从远程拉取, push=推送到远程)

        Returns:
            是否同步成功
        """
        remote_dir = Path(remote_dir)

        if not remote_dir.exists():
            logger.error(f"远程目录不存在: {remote_dir}")
            return False

        try:
            configs = self.list_configs()

            for config_name in configs:
                local_path = self.config_dir / config_name
                remote_path = remote_dir / config_name

                if direction == "pull":
                    if remote_path.exists():
                        # 备份本地配置
                        self._backup_config(config_name, "同步前备份")
                        # 复制远程配置
                        shutil.copy2(remote_path, local_path)
                        logger.info(f"已从远程拉取: {config_name}")
                        # 清除缓存
                        if config_name in self.config_cache:
                            del self.config_cache[config_name]

                elif direction == "push":
                    if local_path.exists():
                        # 复制到远程
                        shutil.copy2(local_path, remote_path)
                        logger.info(f"已推送到远程: {config_name}")

            logger.info(f"配置同步完成 ({direction})")
            return True

        except Exception as e:
            logger.error(f"同步配置失败: {e}")
            return False

    def clear_cache(self):
        """清除配置缓存"""
        self.config_cache.clear()
        logger.info("配置缓存已清除")


# 全局实例
_config_manager: Optional[ConfigManager] = None


def get_config_manager() -> ConfigManager:
    """获取配置管理器实例"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager


def main():
    """主函数"""
    import argparse

    # 配置日志
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )

    parser = argparse.ArgumentParser(description='配置管理中心')
    subparsers = parser.add_subparsers(dest='command', help='命令')

    # list命令
    subparsers.add_parser('list', help='列出所有配置文件')

    # get命令
    parser_get = subparsers.add_parser('get', help='获取配置值')
    parser_get.add_argument('config', help='配置文件名')
    parser_get.add_argument('key', help='键路径(如 server.ip)')

    # set命令
    parser_set = subparsers.add_parser('set', help='设置配置值')
    parser_set.add_argument('config', help='配置文件名')
    parser_set.add_argument('key', help='键路径')
    parser_set.add_argument('value', help='值')

    # validate命令
    parser_validate = subparsers.add_parser('validate', help='验证配置')
    parser_validate.add_argument('config', help='配置文件名')

    # versions命令
    parser_versions = subparsers.add_parser('versions', help='查看版本历史')
    parser_versions.add_argument('config', help='配置文件名')

    # restore命令
    parser_restore = subparsers.add_parser('restore', help='恢复到指定版本')
    parser_restore.add_argument('config', help='配置文件名')
    parser_restore.add_argument('version', help='版本号')

    # export命令
    parser_export = subparsers.add_parser('export', help='导出配置')
    parser_export.add_argument('config', help='配置文件名')
    parser_export.add_argument('output', help='输出路径')
    parser_export.add_argument('--decrypt', action='store_true', help='解密后导出')

    # import命令
    parser_import = subparsers.add_parser('import', help='导入配置')
    parser_import.add_argument('config', help='配置文件名')
    parser_import.add_argument('input', help='输入路径')

    args = parser.parse_args()

    manager = ConfigManager()

    if args.command == 'list':
        print("\n配置文件列表:")
        print("=" * 50)
        for config in manager.list_configs():
            print(f"  {config}")
        print()

    elif args.command == 'get':
        value = manager.get_config_value(args.config, args.key)
        print(f"\n{args.config} -> {args.key}:")
        print(json.dumps(value, indent=2, ensure_ascii=False))
        print()

    elif args.command == 'set':
        # 尝试解析JSON值
        try:
            value = json.loads(args.value)
        except (json.JSONDecodeError, ValueError):
            value = args.value

        success = manager.set_config_value(args.config, args.key, value)
        if success:
            print(f"✓ 已设置 {args.key} = {value}")
        else:
            print(f"✗ 设置失败")

    elif args.command == 'validate':
        is_valid, errors = manager.validate_config(args.config)
        print(f"\n配置验证: {args.config}")
        print("=" * 50)
        if is_valid:
            print("✓ 配置有效")
        else:
            print("✗ 配置无效")
            for error in errors:
                print(f"  - {error}")
        print()

    elif args.command == 'versions':
        versions = manager.get_version_history(args.config)
        print(f"\n版本历史: {args.config}")
        print("=" * 70)
        if versions:
            for v in reversed(versions[-10:]):  # 显示最近10个版本
                timestamp = datetime.fromtimestamp(v.timestamp).strftime("%Y-%m-%d %H:%M:%S")
                print(f"  {v.version} | {timestamp}")
                print(f"    {v.description}")
                print()
        else:
            print("  无版本历史")
        print()

    elif args.command == 'restore':
        success = manager.restore_config(args.config, args.version)
        if success:
            print(f"✓ 已恢复到版本 {args.version}")
        else:
            print(f"✗ 恢复失败")

    elif args.command == 'export':
        success = manager.export_config(args.config, args.output, decrypt=args.decrypt)
        if success:
            print(f"✓ 已导出到 {args.output}")
        else:
            print(f"✗ 导出失败")

    elif args.command == 'import':
        success = manager.import_config(args.config, args.input)
        if success:
            print(f"✓ 已从 {args.input} 导入")
        else:
            print(f"✗ 导入失败")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
