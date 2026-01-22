# 清理垃圾功能
# 自动清理日志、缓存、临时文件等

import os
import logging
import shutil
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List
from pathlib import Path
import psutil

logger = logging.getLogger(__name__)


class GarbageCleaner:
    """垃圾清理器"""

    def __init__(self, config: Dict):
        self.config = config
        self.enabled = config.get("enabled", True)
        self.auto_clean = config.get("auto_clean", True)
        self.clean_interval_hours = config.get("clean_interval_hours", 24)

        # 清理规则
        self.log_retention_days = config.get("log_retention_days", 7)
        self.cache_retention_days = config.get("cache_retention_days", 3)
        self.temp_retention_hours = config.get("temp_retention_hours", 1)
        self.db_backup_retention_days = config.get("db_backup_retention_days", 30)

        # 要清理的目录
        self.clean_dirs = config.get("clean_dirs", [
            "logs",
            "cache",
            "temp",
            "shadow_trading",
            "training/history"
        ])

        # 要清理的文件模式
        self.file_patterns = config.get("file_patterns", [
            "*.log",
            "*.tmp",
            "*.cache",
            "*.pyc",
            "__pycache__",
            "*.bak",
            "*.swp"
        ])

    def clean_all(self) -> Dict:
        """执行所有清理"""
        if not self.enabled:
            return {"status": "disabled"}

        logger.info("开始清理系统垃圾...")
        start_time = datetime.now()

        results = {
            "logs": self.clean_logs(),
            "cache": self.clean_cache(),
            "temp": self.clean_temp(),
            "database": self.clean_database(),
            "python_cache": self.clean_python_cache(),
            "disk": self.check_disk_cleanup(),
            "memory": self.check_memory_cleanup()
        }

        duration = (datetime.now() - start_time).total_seconds()
        total_freed = sum(r.get("freed_mb", 0) for r in results.values())

        summary = {
            "status": "completed",
            "duration_seconds": duration,
            "total_freed_mb": total_freed,
            "details": results
        }

        logger.info(f"清理完成: 释放 {total_freed:.2f} MB, 耗时 {duration:.2f} 秒")

        return summary

    def clean_logs(self) -> Dict:
        """清理日志文件"""
        if "logs" not in self.clean_dirs:
            return {"status": "skipped"}

        logger.info("清理日志文件...")

        freed_mb = 0.0
        deleted_count = 0

        cutoff_date = datetime.now() - timedelta(days=self.log_retention_days)

        for log_dir in ["logs", "logs/trades", "logs/trades/reports"]:
            dir_path = Path(log_dir)
            if not dir_path.exists():
                continue

            for file_path in dir_path.rglob("*"):
                if not file_path.is_file():
                    continue

                try:
                    # 获取文件修改时间
                    mtime = datetime.fromtimestamp(file_path.stat().st_mtime)

                    if mtime < cutoff_date:
                        size_mb = file_path.stat().st_size / (1024 * 1024)
                        file_path.unlink()
                        freed_mb += size_mb
                        deleted_count += 1
                        logger.debug(f"已删除日志: {file_path}")

                except Exception as e:
                    logger.warning(f"无法删除 {file_path}: {e}")

        logger.info(f"日志清理完成: 删除 {deleted_count} 个文件, 释放 {freed_mb:.2f} MB")

        return {
            "status": "completed",
            "deleted_files": deleted_count,
            "freed_mb": freed_mb
        }

    def clean_cache(self) -> Dict:
        """清理缓存文件"""
        if "cache" not in self.clean_dirs:
            return {"status": "skipped"}

        logger.info("清理缓存文件...")

        freed_mb = 0.0
        deleted_count = 0

        cutoff_date = datetime.now() - timedelta(days=self.cache_retention_days)

        cache_dirs = ["cache", "training/models", ".cache", "__pycache__"]

        for cache_dir in cache_dirs:
            dir_path = Path(cache_dir)
            if not dir_path.exists():
                continue

            try:
                # 对于__pycache__目录，直接删除整个目录
                if dir_path.name == "__pycache__":
                    size_mb = sum(f.stat().st_size for f in dir_path.rglob("*")) / (1024 * 1024)
                    shutil.rmtree(dir_path)
                    freed_mb += size_mb
                    deleted_count += 1
                    continue

                for file_path in dir_path.rglob("*"):
                    if not file_path.is_file():
                        continue

                    try:
                        mtime = datetime.fromtimestamp(file_path.stat().st_mtime)

                        # 检查文件模式
                        if any(file_path.match(p) for p in self.file_patterns):
                            if mtime < cutoff_date:
                                size_mb = file_path.stat().st_size / (1024 * 1024)
                                file_path.unlink()
                                freed_mb += size_mb
                                deleted_count += 1
                                logger.debug(f"已删除缓存: {file_path}")

                    except Exception as e:
                        logger.warning(f"无法删除 {file_path}: {e}")

                # 删除空目录
                for subdir in sorted(dir_path.rglob("*"), reverse=True):
                    if subdir.is_dir() and not any(subdir.iterdir()):
                        subdir.rmdir()

            except Exception as e:
                logger.warning(f"清理缓存目录 {cache_dir} 失败: {e}")

        logger.info(f"缓存清理完成: 删除 {deleted_count} 个文件, 释放 {freed_mb:.2f} MB")

        return {
            "status": "completed",
            "deleted_files": deleted_count,
            "freed_mb": freed_mb
        }

    def clean_temp(self) -> Dict:
        """清理临时文件"""
        if "temp" not in self.clean_dirs:
            return {"status": "skipped"}

        logger.info("清理临时文件...")

        freed_mb = 0.0
        deleted_count = 0

        cutoff_time = datetime.now() - timedelta(hours=self.temp_retention_hours)

        temp_patterns = ["*.tmp", "*.temp", "~*", ".DS_Store", "Thumbs.db"]

        for pattern in temp_patterns:
            for file_path in Path(".").rglob(pattern):
                if not file_path.is_file():
                    continue

                try:
                    mtime = datetime.fromtimestamp(file_path.stat().st_mtime)

                    if mtime < cutoff_time:
                        size_mb = file_path.stat().st_size / (1024 * 1024)
                        file_path.unlink()
                        freed_mb += size_mb
                        deleted_count += 1
                        logger.debug(f"已删除临时文件: {file_path}")

                except Exception as e:
                    logger.warning(f"无法删除 {file_path}: {e}")

        logger.info(f"临时文件清理完成: 删除 {deleted_count} 个文件, 释放 {freed_mb:.2f} MB")

        return {
            "status": "completed",
            "deleted_files": deleted_count,
            "freed_mb": freed_mb
        }

    def clean_database(self) -> Dict:
        """清理数据库"""
        logger.info("清理数据库...")

        freed_mb = 0.0
        cleaned_count = 0

        # 查找所有SQLite数据库
        db_files = list(Path(".").rglob("*.db")) + list(Path(".").rglob("*.sqlite"))

        for db_path in db_files:
            try:
                # 连接数据库
                conn = sqlite3.connect(db_path)

                # 获取数据库大小
                db_size_mb = db_path.stat().st_size / (1024 * 1024)

                # 执行VACUUM清理
                conn.execute("VACUUM")

                # 清理影子交易历史
                cursor = conn.cursor()

                # 删除超过保留期限的影子交易记录
                cutoff_date = (datetime.now() - timedelta(days=self.db_backup_retention_days)).isoformat()
                cursor.execute(
                    "DELETE FROM shadow_trades WHERE created_at < ? AND status = 'closed'",
                    (cutoff_date,)
                )

                deleted_rows = cursor.rowcount
                conn.commit()

                # 关闭连接
                conn.close()

                # 获取清理后的大小
                new_size_mb = db_path.stat().st_size / (1024 * 1024)
                freed = db_size_mb - new_size_mb

                if freed > 0:
                    freed_mb += freed
                    cleaned_count += deleted_rows
                    logger.info(f"数据库 {db_path} 清理: 释放 {freed:.2f} MB, 删除 {deleted_rows} 行")

            except Exception as e:
                logger.warning(f"清理数据库 {db_path} 失败: {e}")

        logger.info(f"数据库清理完成: 释放 {freed_mb:.2f} MB")

        return {
            "status": "completed",
            "freed_mb": freed_mb,
            "cleaned_rows": cleaned_count
        }

    def clean_python_cache(self) -> Dict:
        """清理Python缓存"""
        logger.info("清理Python缓存...")

        freed_mb = 0.0
        deleted_dirs = 0

        # 清理__pycache__目录
        for cache_dir in Path(".").rglob("__pycache__"):
            try:
                size_mb = sum(f.stat().st_size for f in cache_dir.rglob("*")) / (1024 * 1024)
                shutil.rmtree(cache_dir)
                freed_mb += size_mb
                deleted_dirs += 1
                logger.debug(f"已删除: {cache_dir}")
            except Exception as e:
                logger.warning(f"无法删除 {cache_dir}: {e}")

        # 清理.pyc文件
        for pyc_file in Path(".").rglob("*.pyc"):
            try:
                size_mb = pyc_file.stat().st_size / (1024 * 1024)
                pyc_file.unlink()
                freed_mb += size_mb
                logger.debug(f"已删除: {pyc_file}")
            except Exception as e:
                logger.warning(f"无法删除 {pyc_file}: {e}")

        logger.info(f"Python缓存清理完成: 删除 {deleted_dirs} 个目录, 释放 {freed_mb:.2f} MB")

        return {
            "status": "completed",
            "deleted_dirs": deleted_dirs,
            "freed_mb": freed_mb
        }

    def check_disk_cleanup(self) -> Dict:
        """检查磁盘使用情况"""
        logger.info("检查磁盘使用情况...")

        disk_info = {}

        for partition in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                used_percent = usage.percent

                disk_info[partition.mountpoint] = {
                    "total_gb": usage.total / (1024**3),
                    "used_gb": usage.used / (1024**3),
                    "free_gb": usage.free / (1024**3),
                    "used_percent": used_percent,
                    "needs_cleanup": used_percent > 80
                }

                if used_percent > 90:
                    logger.warning(f"磁盘 {partition.mountpoint} 空间不足: {used_percent:.1f}%")

            except Exception as e:
                logger.warning(f"无法获取磁盘信息 {partition.mountpoint}: {e}")

        return {
            "status": "checked",
            "disks": disk_info
        }

    def check_memory_cleanup(self) -> Dict:
        """检查内存使用情况"""
        logger.info("检查内存使用情况...")

        mem = psutil.virtual_memory()

        memory_info = {
            "total_gb": mem.total / (1024**3),
            "used_gb": mem.used / (1024**3),
            "free_gb": mem.free / (1024**3),
            "used_percent": mem.percent,
            "swap_total_gb": psutil.swap_memory().total / (1024**3),
            "swap_used_gb": psutil.swap_memory().used / (1024**3)
        }

        if mem.percent > 85:
            logger.warning(f"内存使用率过高: {mem.percent:.1f}%")

        return {
            "status": "checked",
            "memory": memory_info
        }

    def clean_specific_pattern(self, pattern: str, older_than_days: int = 0) -> Dict:
        """清理特定模式的文件"""
        logger.info(f"清理匹配模式的文件: {pattern}")

        freed_mb = 0.0
        deleted_count = 0

        cutoff_date = datetime.now() - timedelta(days=older_than_days) if older_than_days > 0 else None

        for file_path in Path(".").rglob(pattern):
            if not file_path.is_file():
                continue

            try:
                if cutoff_date:
                    mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                    if mtime < cutoff_date:
                        size_mb = file_path.stat().st_size / (1024 * 1024)
                        file_path.unlink()
                        freed_mb += size_mb
                        deleted_count += 1
                else:
                    size_mb = file_path.stat().st_size / (1024 * 1024)
                    file_path.unlink()
                    freed_mb += size_mb
                    deleted_count += 1

            except Exception as e:
                logger.warning(f"无法删除 {file_path}: {e}")

        return {
            "status": "completed",
            "deleted_files": deleted_count,
            "freed_mb": freed_mb
        }

    def schedule_auto_clean(self):
        """调度自动清理"""
        if not self.auto_clean:
            return

        import threading
        import time

        interval_seconds = self.clean_interval_hours * 3600

        def clean_loop():
            while True:
                try:
                    self.clean_all()
                except Exception as e:
                    logger.error(f"自动清理失败: {e}")

                time.sleep(interval_seconds)

        thread = threading.Thread(target=clean_loop, daemon=True)
        thread.start()

        logger.info(f"自动清理已启动，间隔: {self.clean_interval_hours} 小时")


class SystemOptimizer:
    """系统优化器"""

    def __init__(self, config: Dict):
        self.config = config

    def optimize_system(self) -> Dict:
        """优化系统"""
        logger.info("开始系统优化...")

        results = {}

        # 清理Python进程
        results["processes"] = self.clean_zombie_processes()

        # 清理僵尸线程
        results["threads"] = self.check_threads()

        # 优化文件描述符
        results["file_descriptors"] = self.check_file_descriptors()

        # 压缩日志
        results["log_compression"] = self.compress_old_logs()

        return results

    def clean_zombie_processes(self) -> Dict:
        """清理僵尸进程"""
        zombie_count = 0

        for proc in psutil.process_iter(['pid', 'name', 'status']):
            try:
                if proc.info['status'] == 'zombie':
                    # 僵尸进程通常需要父进程处理
                    logger.debug(f"发现僵尸进程: {proc.info}")
                    zombie_count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        return {
            "zombie_processes": zombie_count
        }

    def check_threads(self) -> Dict:
        """检查线程数"""
        thread_count = 0
        main_pid = os.getpid()

        try:
            process = psutil.Process(main_pid)
            thread_count = process.num_threads()
        except psutil.NoSuchProcess:
            pass

        return {
            "thread_count": thread_count,
            "status": "normal" if thread_count < 50 else "high"
        }

    def check_file_descriptors(self) -> Dict:
        """检查文件描述符使用"""
        try:
            main_pid = os.getpid()
            process = psutil.Process(main_pid)
            fd_count = process.num_fds()

            # 获取系统限制
            soft_limit, hard_limit = psutil.Process().rlimit(psutil.RLIMIT_NOFILE)

            return {
                "open_fds": fd_count,
                "soft_limit": soft_limit,
                "hard_limit": hard_limit,
                "usage_percent": fd_count / soft_limit * 100 if soft_limit > 0 else 0
            }
        except (psutil.NoSuchProcess, AttributeError):
            return {"status": "unavailable"}

    def compress_old_logs(self) -> Dict:
        """压缩旧日志"""
        import gzip

        compressed_count = 0
        saved_mb = 0.0

        cutoff_date = datetime.now() - timedelta(days=3)

        for log_file in Path("logs").rglob("*.log"):
            try:
                mtime = datetime.fromtimestamp(log_file.stat().st_mtime)

                if mtime < cutoff_date:
                    # 压缩文件
                    gz_file = log_file.with_suffix(log_file.suffix + '.gz')

                    if not gz_file.exists():
                        original_size = log_file.stat().st_size

                        with open(log_file, 'rb') as f_in:
                            with gzip.open(gz_file, 'wb') as f_out:
                                f_out.writelines(f_in)

                        compressed_size = gz_file.stat().st_size
                        saved_mb += (original_size - compressed_size) / (1024 * 1024)

                        # 删除原文件
                        log_file.unlink()

                        compressed_count += 1
                        logger.debug(f"已压缩: {log_file}")

            except Exception as e:
                logger.warning(f"压缩 {log_file} 失败: {e}")

        return {
            "compressed_files": compressed_count,
            "saved_mb": saved_mb
        }


def create_cleaner(config: Dict) -> GarbageCleaner:
    """创建垃圾清理器"""
    return GarbageCleaner(config)


def create_optimizer(config: Dict) -> SystemOptimizer:
    """创建系统优化器"""
    return SystemOptimizer(config)


if __name__ == "__main__":
    # 测试代码
    config = {
        "enabled": True,
        "auto_clean": False,
        "log_retention_days": 7,
        "cache_retention_days": 3,
        "temp_retention_hours": 1,
        "db_backup_retention_days": 30,
        "clean_dirs": ["logs", "cache", "temp"],
        "file_patterns": ["*.log", "*.tmp", "*.cache"]
    }

    cleaner = GarbageCleaner(config)
    optimizer = SystemOptimizer({})

    # 执行清理
    print("=" * 60)
    print("开始清理系统垃圾...")
    print("=" * 60)

    result = cleaner.clean_all()

    print(f"\n清理结果:")
    print(f"  状态: {result['status']}")
    print(f"  耗时: {result['duration_seconds']:.2f} 秒")
    print(f"  释放空间: {result['total_freed_mb']:.2f} MB")

    print("\n详细结果:")
    for key, value in result['details'].items():
        if isinstance(value, dict) and "freed_mb" in value:
            print(f"  {key}: {value['freed_mb']:.2f} MB")

    # 系统优化
    print("\n" + "=" * 60)
    print("系统优化...")
    print("=" * 60)

    opt_result = optimizer.optimize_system()

    print(f"\n优化结果:")
    for key, value in opt_result.items():
        print(f"  {key}: {value}")
