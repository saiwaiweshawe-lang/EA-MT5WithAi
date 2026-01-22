#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
备份管理器 - 自动备份配置、数据和日志
"""

import os
import json
import logging
import shutil
import tarfile
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import hashlib
import threading
import time

logger = logging.getLogger(__name__)


class BackupManager:
    """备份管理器"""

    def __init__(self, config_path: str = None):
        self.base_dir = Path(__file__).parent.parent
        self.config = self._load_config(config_path)

        # 备份目录
        self.backup_dir = self.base_dir / self.config.get('backup_dir', 'backups')
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        # 备份状态
        self.backup_history = []
        self.is_running = False
        self.backup_thread = None

        # 加载备份历史
        self._load_backup_history()

    def _load_config(self, config_path: str = None) -> Dict:
        """加载配置"""
        if config_path is None:
            config_path = self.base_dir / "config" / "backup_config.json"

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning(f"配置文件 {config_path} 不存在,使用默认配置")
            return self._get_default_config()

    def _get_default_config(self) -> Dict:
        """获取默认配置"""
        return {
            "backup_dir": "backups",
            "schedule": {
                "enabled": True,
                "interval_hours": 24,
                "time": "03:00"
            },
            "retention": {
                "keep_daily": 7,
                "keep_weekly": 4,
                "keep_monthly": 3
            },
            "backup_targets": {
                "config": True,
                "database": True,
                "logs": True,
                "state_files": True
            },
            "remote_backup": {
                "enabled": False,
                "type": "local",
                "path": "/backup/remote"
            },
            "compression": {
                "enabled": True,
                "level": 6
            },
            "encryption": {
                "enabled": False,
                "key_file": "config/.backup_key"
            },
            "notification": {
                "enabled": True,
                "on_success": False,
                "on_failure": True
            }
        }

    def _load_backup_history(self):
        """加载备份历史"""
        history_file = self.backup_dir / "backup_history.json"
        if history_file.exists():
            try:
                with open(history_file, 'r', encoding='utf-8') as f:
                    self.backup_history = json.load(f)
            except Exception as e:
                logger.error(f"加载备份历史失败: {e}")
                self.backup_history = []

    def _save_backup_history(self):
        """保存备份历史"""
        history_file = self.backup_dir / "backup_history.json"
        try:
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump(self.backup_history, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"保存备份历史失败: {e}")

    def create_backup(self, backup_name: str = None) -> Optional[Dict]:
        """创建备份"""
        if backup_name is None:
            backup_name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        backup_path = self.backup_dir / backup_name
        backup_path.mkdir(parents=True, exist_ok=True)

        logger.info(f"开始创建备份: {backup_name}")

        backup_info = {
            "name": backup_name,
            "timestamp": datetime.now().isoformat(),
            "files": [],
            "size_bytes": 0,
            "status": "in_progress"
        }

        try:
            # 备份配置文件
            if self.config.get('backup_targets', {}).get('config', True):
                self._backup_configs(backup_path, backup_info)

            # 备份数据库
            if self.config.get('backup_targets', {}).get('database', True):
                self._backup_databases(backup_path, backup_info)

            # 备份日志
            if self.config.get('backup_targets', {}).get('logs', False):
                self._backup_logs(backup_path, backup_info)

            # 备份状态文件
            if self.config.get('backup_targets', {}).get('state_files', True):
                self._backup_state_files(backup_path, backup_info)

            # 压缩备份
            if self.config.get('compression', {}).get('enabled', True):
                compressed_file = self._compress_backup(backup_path, backup_name)
                backup_info['compressed_file'] = str(compressed_file)
                backup_info['size_bytes'] = compressed_file.stat().st_size

                # 删除临时目录
                shutil.rmtree(backup_path)
            else:
                backup_info['size_bytes'] = self._get_directory_size(backup_path)

            # 计算校验和
            if self.config.get('compression', {}).get('enabled', True):
                backup_info['checksum'] = self._calculate_checksum(compressed_file)

            # 远程备份
            if self.config.get('remote_backup', {}).get('enabled', False):
                self._upload_to_remote(backup_info)

            backup_info['status'] = 'success'
            logger.info(f"备份完成: {backup_name}, 大小: {backup_info['size_bytes']} 字节")

        except Exception as e:
            backup_info['status'] = 'failed'
            backup_info['error'] = str(e)
            logger.error(f"备份失败: {e}")

        # 记录备份历史
        self.backup_history.append(backup_info)
        self._save_backup_history()

        # 发送通知
        if self.config.get('notification', {}).get('enabled', True):
            self._send_notification(backup_info)

        # 清理旧备份
        self._cleanup_old_backups()

        return backup_info

    def _backup_configs(self, backup_path: Path, backup_info: Dict):
        """备份配置文件"""
        config_dir = self.base_dir / "config"
        if not config_dir.exists():
            return

        target_dir = backup_path / "config"
        target_dir.mkdir(parents=True, exist_ok=True)

        for config_file in config_dir.glob("*.json"):
            shutil.copy2(config_file, target_dir / config_file.name)
            backup_info['files'].append(f"config/{config_file.name}")

        logger.info(f"已备份 {len(list(target_dir.glob('*.json')))} 个配置文件")

    def _backup_databases(self, backup_path: Path, backup_info: Dict):
        """备份数据库"""
        # 备份SQLite数据库
        db_files = list(self.base_dir.glob("**/*.db"))

        if not db_files:
            return

        target_dir = backup_path / "databases"
        target_dir.mkdir(parents=True, exist_ok=True)

        for db_file in db_files:
            try:
                # 使用SQLite备份API
                relative_path = db_file.relative_to(self.base_dir)
                target_file = target_dir / db_file.name

                # 连接到源数据库
                src_conn = sqlite3.connect(str(db_file))
                dst_conn = sqlite3.connect(str(target_file))

                # 备份
                src_conn.backup(dst_conn)

                src_conn.close()
                dst_conn.close()

                backup_info['files'].append(f"databases/{db_file.name}")
                logger.info(f"已备份数据库: {db_file.name}")
            except Exception as e:
                logger.error(f"备份数据库 {db_file.name} 失败: {e}")

    def _backup_logs(self, backup_path: Path, backup_info: Dict):
        """备份日志文件(最近7天)"""
        logs_dir = self.base_dir / "logs"
        if not logs_dir.exists():
            return

        target_dir = backup_path / "logs"
        target_dir.mkdir(parents=True, exist_ok=True)

        # 只备份最近7天的日志
        cutoff_time = datetime.now() - timedelta(days=7)

        for log_file in logs_dir.rglob("*.log"):
            if log_file.stat().st_mtime > cutoff_time.timestamp():
                relative_path = log_file.relative_to(logs_dir)
                target_file = target_dir / relative_path
                target_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(log_file, target_file)
                backup_info['files'].append(f"logs/{relative_path}")

    def _backup_state_files(self, backup_path: Path, backup_info: Dict):
        """备份状态文件"""
        state_files = [
            "logs/circuit_state.json",
            "logs/cpu_limiter_state.json",
            "logs/performance_state.json"
        ]

        target_dir = backup_path / "state"
        target_dir.mkdir(parents=True, exist_ok=True)

        for state_file in state_files:
            source = self.base_dir / state_file
            if source.exists():
                shutil.copy2(source, target_dir / Path(state_file).name)
                backup_info['files'].append(f"state/{Path(state_file).name}")

    def _compress_backup(self, backup_path: Path, backup_name: str) -> Path:
        """压缩备份"""
        archive_path = self.backup_dir / f"{backup_name}.tar.gz"

        with tarfile.open(archive_path, "w:gz") as tar:
            tar.add(backup_path, arcname=backup_name)

        logger.info(f"备份已压缩: {archive_path}")
        return archive_path

    def _calculate_checksum(self, file_path: Path) -> str:
        """计算文件校验和"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def _get_directory_size(self, path: Path) -> int:
        """获取目录大小"""
        total = 0
        for entry in path.rglob("*"):
            if entry.is_file():
                total += entry.stat().st_size
        return total

    def _upload_to_remote(self, backup_info: Dict):
        """上传到远程存储"""
        remote_config = self.config.get('remote_backup', {})

        if remote_config.get('type') == 'local':
            # 本地远程路径
            remote_path = Path(remote_config.get('path'))
            remote_path.mkdir(parents=True, exist_ok=True)

            if 'compressed_file' in backup_info:
                source = Path(backup_info['compressed_file'])
                shutil.copy2(source, remote_path / source.name)
                logger.info(f"已上传到远程: {remote_path / source.name}")

    def _cleanup_old_backups(self):
        """清理旧备份"""
        retention = self.config.get('retention', {})
        keep_daily = retention.get('keep_daily', 7)
        keep_weekly = retention.get('keep_weekly', 4)
        keep_monthly = retention.get('keep_monthly', 3)

        # 按时间排序备份
        backups = sorted(
            [b for b in self.backup_history if b.get('status') == 'success'],
            key=lambda x: x['timestamp'],
            reverse=True
        )

        # 分类备份
        daily_backups = backups[:keep_daily]
        weekly_backups = []
        monthly_backups = []

        # 每周保留一个
        current_week = None
        for backup in backups[keep_daily:]:
            backup_date = datetime.fromisoformat(backup['timestamp'])
            week = backup_date.isocalendar()[1]
            if week != current_week:
                weekly_backups.append(backup)
                current_week = week
                if len(weekly_backups) >= keep_weekly:
                    break

        # 每月保留一个
        current_month = None
        for backup in backups[keep_daily:]:
            backup_date = datetime.fromisoformat(backup['timestamp'])
            month = backup_date.month
            if month != current_month:
                monthly_backups.append(backup)
                current_month = month
                if len(monthly_backups) >= keep_monthly:
                    break

        # 确定要保留的备份
        keep_backups = set()
        for backup in daily_backups + weekly_backups + monthly_backups:
            keep_backups.add(backup['name'])

        # 删除不需要的备份
        deleted_count = 0
        for backup in backups:
            if backup['name'] not in keep_backups:
                self._delete_backup(backup)
                deleted_count += 1

        if deleted_count > 0:
            logger.info(f"已清理 {deleted_count} 个旧备份")

    def _delete_backup(self, backup_info: Dict):
        """删除备份"""
        if 'compressed_file' in backup_info:
            file_path = Path(backup_info['compressed_file'])
            if file_path.exists():
                file_path.unlink()
        else:
            backup_path = self.backup_dir / backup_info['name']
            if backup_path.exists():
                shutil.rmtree(backup_path)

        # 从历史中移除
        self.backup_history = [b for b in self.backup_history if b['name'] != backup_info['name']]
        self._save_backup_history()

    def _send_notification(self, backup_info: Dict):
        """发送通知"""
        notification_config = self.config.get('notification', {})

        if backup_info['status'] == 'success' and not notification_config.get('on_success', False):
            return

        if backup_info['status'] == 'failed' and not notification_config.get('on_failure', True):
            return

        # 这里可以集成Telegram通知
        # 暂时只记录日志
        if backup_info['status'] == 'success':
            logger.info(f"✓ 备份成功通知: {backup_info['name']}")
        else:
            logger.error(f"✗ 备份失败通知: {backup_info['name']}, 错误: {backup_info.get('error')}")

    def restore_backup(self, backup_name: str, restore_path: Path = None) -> bool:
        """恢复备份"""
        if restore_path is None:
            restore_path = self.base_dir

        # 查找备份
        backup_info = None
        for backup in self.backup_history:
            if backup['name'] == backup_name:
                backup_info = backup
                break

        if not backup_info:
            logger.error(f"未找到备份: {backup_name}")
            return False

        try:
            if 'compressed_file' in backup_info:
                # 解压备份
                archive_path = Path(backup_info['compressed_file'])
                if not archive_path.exists():
                    logger.error(f"备份文件不存在: {archive_path}")
                    return False

                # 验证校验和
                if 'checksum' in backup_info:
                    checksum = self._calculate_checksum(archive_path)
                    if checksum != backup_info['checksum']:
                        logger.error("备份文件校验和不匹配")
                        return False

                # 解压
                with tarfile.open(archive_path, "r:gz") as tar:
                    tar.extractall(restore_path)

                logger.info(f"备份已恢复到: {restore_path}")
                return True
            else:
                logger.error("不支持的备份格式")
                return False

        except Exception as e:
            logger.error(f"恢复备份失败: {e}")
            return False

    def start_scheduled_backup(self):
        """启动定时备份"""
        if not self.config.get('schedule', {}).get('enabled', True):
            logger.info("定时备份未启用")
            return

        if self.is_running:
            logger.warning("定时备份已在运行")
            return

        self.is_running = True
        self.backup_thread = threading.Thread(target=self._backup_loop, daemon=True)
        self.backup_thread.start()
        logger.info("定时备份已启动")

    def stop_scheduled_backup(self):
        """停止定时备份"""
        self.is_running = False
        if self.backup_thread:
            self.backup_thread.join(timeout=5)
        logger.info("定时备份已停止")

    def _backup_loop(self):
        """备份循环"""
        interval_hours = self.config.get('schedule', {}).get('interval_hours', 24)

        while self.is_running:
            try:
                # 执行备份
                self.create_backup()

                # 等待下次备份
                time.sleep(interval_hours * 3600)

            except Exception as e:
                logger.error(f"定时备份出错: {e}")
                time.sleep(300)  # 出错后等待5分钟

    def list_backups(self) -> List[Dict]:
        """列出所有备份"""
        return sorted(
            self.backup_history,
            key=lambda x: x['timestamp'],
            reverse=True
        )

    def get_backup_info(self, backup_name: str) -> Optional[Dict]:
        """获取备份信息"""
        for backup in self.backup_history:
            if backup['name'] == backup_name:
                return backup
        return None


def main():
    """主函数"""
    import argparse

    # 配置日志
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )

    parser = argparse.ArgumentParser(description='备份管理器')
    parser.add_argument('action', choices=['create', 'restore', 'list', 'cleanup', 'start'],
                       help='操作类型')
    parser.add_argument('--name', help='备份名称')
    parser.add_argument('--config', help='配置文件路径')

    args = parser.parse_args()

    manager = BackupManager(config_path=args.config)

    if args.action == 'create':
        backup_info = manager.create_backup(args.name)
        if backup_info['status'] == 'success':
            print(f"✓ 备份成功: {backup_info['name']}")
            print(f"  大小: {backup_info['size_bytes'] / 1024 / 1024:.2f} MB")
            print(f"  文件数: {len(backup_info['files'])}")
        else:
            print(f"✗ 备份失败: {backup_info.get('error')}")

    elif args.action == 'restore':
        if not args.name:
            print("错误: 请指定备份名称 --name")
            return

        success = manager.restore_backup(args.name)
        if success:
            print(f"✓ 恢复成功: {args.name}")
        else:
            print(f"✗ 恢复失败")

    elif args.action == 'list':
        backups = manager.list_backups()
        print(f"\n共有 {len(backups)} 个备份:\n")
        for backup in backups:
            status_icon = "✓" if backup['status'] == 'success' else "✗"
            size_mb = backup['size_bytes'] / 1024 / 1024
            print(f"{status_icon} {backup['name']}")
            print(f"  时间: {backup['timestamp']}")
            print(f"  大小: {size_mb:.2f} MB")
            print(f"  文件数: {len(backup['files'])}")
            print()

    elif args.action == 'cleanup':
        manager._cleanup_old_backups()
        print("✓ 已清理旧备份")

    elif args.action == 'start':
        manager.start_scheduled_backup()
        print("✓ 定时备份已启动")
        print("按 Ctrl+C 停止...")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            manager.stop_scheduled_backup()
            print("\n✓ 定时备份已停止")


if __name__ == "__main__":
    main()
