#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一日志工具 - 提供标准化的日志和异常处理
"""

import os
import sys
import logging
import traceback
from datetime import datetime
from pathlib import Path
from typing import Optional
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
import json


class ColoredFormatter(logging.Formatter):
    """彩色日志格式化器"""

    # 颜色代码
    COLORS = {
        'DEBUG': '\033[36m',      # 青色
        'INFO': '\033[32m',       # 绿色
        'WARNING': '\033[33m',    # 黄色
        'ERROR': '\033[31m',      # 红色
        'CRITICAL': '\033[35m',   # 紫色
    }
    RESET = '\033[0m'

    def format(self, record):
        # 添加颜色
        if record.levelname in self.COLORS:
            record.levelname = f"{self.COLORS[record.levelname]}{record.levelname}{self.RESET}"
        return super().format(record)


class TradingLogger:
    """交易系统日志器"""

    def __init__(
        self,
        name: str = "trading_system",
        log_dir: str = "logs",
        level: int = logging.INFO,
        enable_console: bool = True,
        enable_file: bool = True,
        enable_json: bool = False,
        max_bytes: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 10
    ):
        self.name = name
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # 创建logger
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        self.logger.handlers.clear()  # 清除已有的处理器

        # 日志格式
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        colored_formatter = ColoredFormatter(
            '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # 控制台处理器
        if enable_console:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(level)
            console_handler.setFormatter(colored_formatter)
            self.logger.addHandler(console_handler)

        # 文件处理器 - 按大小滚动
        if enable_file:
            log_file = self.log_dir / f"{name}.log"
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding='utf-8'
            )
            file_handler.setLevel(level)
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)

            # 错误日志单独文件
            error_log_file = self.log_dir / f"{name}_error.log"
            error_handler = RotatingFileHandler(
                error_log_file,
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding='utf-8'
            )
            error_handler.setLevel(logging.ERROR)
            error_handler.setFormatter(formatter)
            self.logger.addHandler(error_handler)

        # JSON格式日志（用于日志分析）
        if enable_json:
            json_log_file = self.log_dir / f"{name}.jsonl"
            json_handler = RotatingFileHandler(
                json_log_file,
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding='utf-8'
            )
            json_handler.setLevel(level)
            json_handler.setFormatter(JsonFormatter())
            self.logger.addHandler(json_handler)

    def debug(self, msg: str, **kwargs):
        """调试日志"""
        self.logger.debug(msg, extra=kwargs)

    def info(self, msg: str, **kwargs):
        """信息日志"""
        self.logger.info(msg, extra=kwargs)

    def warning(self, msg: str, **kwargs):
        """警告日志"""
        self.logger.warning(msg, extra=kwargs)

    def error(self, msg: str, exc_info: bool = False, **kwargs):
        """错误日志"""
        self.logger.error(msg, exc_info=exc_info, extra=kwargs)

    def critical(self, msg: str, exc_info: bool = False, **kwargs):
        """严重错误日志"""
        self.logger.critical(msg, exc_info=exc_info, extra=kwargs)

    def exception(self, msg: str, **kwargs):
        """异常日志（自动包含堆栈信息）"""
        self.logger.exception(msg, extra=kwargs)

    def log_trade(self, trade_info: dict):
        """记录交易日志"""
        trade_log_file = self.log_dir / "trades" / f"trades_{datetime.now().strftime('%Y%m%d')}.jsonl"
        trade_log_file.parent.mkdir(parents=True, exist_ok=True)

        with open(trade_log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps({
                **trade_info,
                "timestamp": datetime.now().isoformat()
            }, ensure_ascii=False) + '\n')


class JsonFormatter(logging.Formatter):
    """JSON格式化器"""

    def format(self, record):
        log_data = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, ensure_ascii=False)


class ExceptionHandler:
    """统一异常处理器"""

    def __init__(self, logger: TradingLogger):
        self.logger = logger

    def handle(self, func):
        """装饰器：捕获并记录异常"""
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                self.logger.exception(f"函数 {func.__name__} 发生异常: {str(e)}")
                raise
        return wrapper

    def safe_execute(self, func, *args, default=None, **kwargs):
        """安全执行函数，出错返回默认值"""
        try:
            return func(*args, **kwargs)
        except Exception as e:
            self.logger.error(f"执行 {func.__name__} 失败: {str(e)}", exc_info=True)
            return default

    def log_and_raise(self, error_msg: str, exception_class=Exception):
        """记录错误并抛出异常"""
        self.logger.error(error_msg, exc_info=True)
        raise exception_class(error_msg)


def setup_global_exception_handler(logger: TradingLogger):
    """设置全局异常处理器"""
    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        logger.critical(
            "未捕获的异常",
            exc_info=(exc_type, exc_value, exc_traceback)
        )

    sys.excepthook = handle_exception


# 创建默认日志器
default_logger = TradingLogger(
    name="trading_system",
    level=logging.INFO,
    enable_console=True,
    enable_file=True,
    enable_json=True
)

# 设置全局异常处理
setup_global_exception_handler(default_logger)

# 导出便捷函数
debug = default_logger.debug
info = default_logger.info
warning = default_logger.warning
error = default_logger.error
critical = default_logger.critical
exception = default_logger.exception
log_trade = default_logger.log_trade


def create_logger(name: str, **kwargs) -> TradingLogger:
    """创建自定义日志器"""
    return TradingLogger(name=name, **kwargs)


if __name__ == "__main__":
    # 测试日志功能
    logger = create_logger("test_logger")

    logger.debug("这是调试信息")
    logger.info("这是普通信息")
    logger.warning("这是警告信息")
    logger.error("这是错误信息")
    logger.critical("这是严重错误信息")

    # 测试异常日志
    try:
        1 / 0
    except Exception:
        logger.exception("捕获到除零异常")

    # 测试交易日志
    logger.log_trade({
        "symbol": "BTCUSDT",
        "side": "BUY",
        "amount": 0.001,
        "price": 50000,
        "status": "success"
    })

    print("\n日志测试完成，请查看 logs/ 目录")
