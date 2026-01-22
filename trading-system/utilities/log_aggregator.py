#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
日志聚合和分析系统
收集、解析、查询和分析系统日志
"""

import os
import sys
import re
import json
import gzip
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from collections import defaultdict, Counter
from dataclasses import dataclass, asdict

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

logger = logging.getLogger(__name__)


@dataclass
class LogEntry:
    """日志条目"""
    timestamp: float
    level: str
    component: str
    message: str
    source_file: Optional[str] = None
    line_number: Optional[int] = None
    extra: Optional[Dict] = None


class LogAggregator:
    """日志聚合器"""

    def __init__(self, logs_dir: str = None):
        self.base_dir = Path(__file__).parent.parent

        if logs_dir is None:
            logs_dir = self.base_dir / "logs"

        self.logs_dir = Path(logs_dir)

        # 日志解析正则表达式
        self.log_patterns = [
            # 标准格式: 2024-01-01 12:00:00 - component - LEVEL - message
            re.compile(
                r'(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:,\d{3})?)\s*-\s*'
                r'(?P<component>[^\s]+)\s*-\s*'
                r'(?P<level>[A-Z]+)\s*-\s*'
                r'(?P<message>.*)'
            ),
            # 简化格式: [LEVEL] message
            re.compile(
                r'\[(?P<level>[A-Z]+)\]\s*(?P<message>.*)'
            )
        ]

    def collect_logs(self, component: str = None, hours: int = 24) -> List[LogEntry]:
        """
        收集日志

        Args:
            component: 组件名称(None表示所有组件)
            hours: 收集最近多少小时的日志

        Returns:
            日志条目列表
        """
        logs = []
        cutoff_time = datetime.now() - timedelta(hours=hours)

        # 确定要扫描的日志文件
        log_files = []

        if component:
            # 特定组件
            pattern = f"{component}*.log"
            log_files = list(self.logs_dir.glob(pattern))
        else:
            # 所有组件
            log_files = list(self.logs_dir.glob("*.log"))

        # 解析日志文件
        for log_file in log_files:
            try:
                component_name = log_file.stem

                with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        entry = self._parse_log_line(line, component_name)
                        if entry:
                            # 过滤时间
                            entry_time = datetime.fromtimestamp(entry.timestamp)
                            if entry_time >= cutoff_time:
                                logs.append(entry)

            except Exception as e:
                logger.error(f"读取日志文件失败 {log_file}: {e}")

        # 按时间排序
        logs.sort(key=lambda x: x.timestamp)

        return logs

    def _parse_log_line(self, line: str, component: str) -> Optional[LogEntry]:
        """解析日志行"""
        line = line.strip()
        if not line:
            return None

        for pattern in self.log_patterns:
            match = pattern.match(line)
            if match:
                data = match.groupdict()

                # 解析时间戳
                timestamp_str = data.get('timestamp')
                if timestamp_str:
                    try:
                        # 尝试多种时间格式
                        for fmt in [
                            "%Y-%m-%d %H:%M:%S,%f",
                            "%Y-%m-%d %H:%M:%S"
                        ]:
                            try:
                                dt = datetime.strptime(timestamp_str, fmt)
                                timestamp = dt.timestamp()
                                break
                            except ValueError:
                                continue
                        else:
                            timestamp = datetime.now().timestamp()
                    except Exception:
                        timestamp = datetime.now().timestamp()
                else:
                    timestamp = datetime.now().timestamp()

                return LogEntry(
                    timestamp=timestamp,
                    level=data.get('level', 'INFO'),
                    component=data.get('component', component),
                    message=data.get('message', line)
                )

        # 无法解析,返回原始行
        return LogEntry(
            timestamp=datetime.now().timestamp(),
            level='INFO',
            component=component,
            message=line
        )

    def search_logs(self, keyword: str, component: str = None,
                   level: str = None, hours: int = 24) -> List[LogEntry]:
        """
        搜索日志

        Args:
            keyword: 关键词
            component: 组件名称
            level: 日志级别
            hours: 搜索最近多少小时

        Returns:
            匹配的日志条目
        """
        logs = self.collect_logs(component, hours)

        # 过滤
        results = []
        for log in logs:
            # 级别过滤
            if level and log.level != level:
                continue

            # 关键词过滤
            if keyword and keyword.lower() not in log.message.lower():
                continue

            results.append(log)

        return results

    def analyze_errors(self, hours: int = 24) -> Dict:
        """
        分析错误

        Args:
            hours: 分析最近多少小时

        Returns:
            错误统计
        """
        logs = self.collect_logs(hours=hours)

        # 过滤错误和警告
        error_logs = [log for log in logs if log.level in ['ERROR', 'CRITICAL']]
        warning_logs = [log for log in logs if log.level == 'WARNING']

        # 按组件统计
        errors_by_component = Counter(log.component for log in error_logs)
        warnings_by_component = Counter(log.component for log in warning_logs)

        # 提取错误类型
        error_types = Counter()
        for log in error_logs:
            # 简单提取错误类型(第一个单词或异常类名)
            words = log.message.split()
            if words:
                error_type = words[0]
                if 'Exception' in error_type or 'Error' in error_type:
                    error_types[error_type] += 1

        # 时间分布
        hourly_errors = defaultdict(int)
        for log in error_logs:
            hour = datetime.fromtimestamp(log.timestamp).strftime("%Y-%m-%d %H:00")
            hourly_errors[hour] += 1

        return {
            "total_errors": len(error_logs),
            "total_warnings": len(warning_logs),
            "errors_by_component": dict(errors_by_component),
            "warnings_by_component": dict(warnings_by_component),
            "error_types": dict(error_types.most_common(10)),
            "hourly_errors": dict(sorted(hourly_errors.items())),
            "recent_errors": [asdict(log) for log in error_logs[-10:]]
        }

    def analyze_activity(self, hours: int = 24) -> Dict:
        """
        分析活动

        Args:
            hours: 分析最近多少小时

        Returns:
            活动统计
        """
        logs = self.collect_logs(hours=hours)

        # 按组件统计
        logs_by_component = Counter(log.component for log in logs)

        # 按级别统计
        logs_by_level = Counter(log.level for log in logs)

        # 时间分布
        hourly_logs = defaultdict(int)
        for log in logs:
            hour = datetime.fromtimestamp(log.timestamp).strftime("%Y-%m-%d %H:00")
            hourly_logs[hour] += 1

        # 活跃组件
        active_components = []
        for component, count in logs_by_component.most_common():
            # 计算该组件的最近日志时间
            component_logs = [log for log in logs if log.component == component]
            if component_logs:
                last_log_time = max(log.timestamp for log in component_logs)
                active_components.append({
                    "component": component,
                    "log_count": count,
                    "last_activity": last_log_time
                })

        return {
            "total_logs": len(logs),
            "logs_by_component": dict(logs_by_component),
            "logs_by_level": dict(logs_by_level),
            "hourly_logs": dict(sorted(hourly_logs.items())),
            "active_components": active_components[:10]
        }

    def archive_old_logs(self, days: int = 7, compress: bool = True) -> int:
        """
        归档旧日志

        Args:
            days: 归档多少天前的日志
            compress: 是否压缩

        Returns:
            归档的文件数
        """
        archive_dir = self.logs_dir / "archive"
        archive_dir.mkdir(parents=True, exist_ok=True)

        cutoff_time = datetime.now() - timedelta(days=days)
        archived_count = 0

        for log_file in self.logs_dir.glob("*.log"):
            try:
                # 检查文件修改时间
                mtime = datetime.fromtimestamp(log_file.stat().st_mtime)

                if mtime < cutoff_time:
                    # 归档
                    date_str = mtime.strftime("%Y%m%d")
                    archive_name = f"{log_file.stem}_{date_str}.log"

                    if compress:
                        archive_path = archive_dir / f"{archive_name}.gz"
                        with open(log_file, 'rb') as f_in:
                            with gzip.open(archive_path, 'wb') as f_out:
                                f_out.writelines(f_in)
                    else:
                        archive_path = archive_dir / archive_name
                        log_file.rename(archive_path)

                    logger.info(f"已归档日志: {log_file.name} -> {archive_path.name}")
                    archived_count += 1

                    # 删除原文件(如果压缩)
                    if compress and log_file.exists():
                        log_file.unlink()

            except Exception as e:
                logger.error(f"归档日志失败 {log_file}: {e}")

        return archived_count

    def generate_report(self, hours: int = 24) -> str:
        """
        生成日志报告

        Args:
            hours: 报告时间范围

        Returns:
            报告文本
        """
        activity = self.analyze_activity(hours)
        errors = self.analyze_errors(hours)

        report = []
        report.append("=" * 70)
        report.append(f"日志分析报告 (最近{hours}小时)")
        report.append("=" * 70)
        report.append("")

        # 概览
        report.append("## 概览")
        report.append(f"- 总日志数: {activity['total_logs']}")
        report.append(f"- 错误数: {errors['total_errors']}")
        report.append(f"- 警告数: {errors['total_warnings']}")
        report.append("")

        # 按级别统计
        report.append("## 日志级别分布")
        for level, count in sorted(activity['logs_by_level'].items()):
            report.append(f"- {level:10s}: {count}")
        report.append("")

        # 活跃组件
        report.append("## 活跃组件 (Top 10)")
        for comp_info in activity['active_components'][:10]:
            last_time = datetime.fromtimestamp(comp_info['last_activity'])
            report.append(
                f"- {comp_info['component']:20s}: "
                f"{comp_info['log_count']:5d} 条 | "
                f"最后活动: {last_time.strftime('%H:%M:%S')}"
            )
        report.append("")

        # 错误分析
        if errors['total_errors'] > 0:
            report.append("## 错误分析")
            report.append("")

            report.append("### 按组件:")
            for component, count in sorted(
                errors['errors_by_component'].items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]:
                report.append(f"- {component:20s}: {count} 个错误")
            report.append("")

            if errors['error_types']:
                report.append("### 错误类型:")
                for error_type, count in list(errors['error_types'].items())[:10]:
                    report.append(f"- {error_type}: {count}")
                report.append("")

            report.append("### 最近的错误:")
            for log in errors['recent_errors'][-5:]:
                timestamp = datetime.fromtimestamp(log['timestamp'])
                report.append(f"- [{timestamp.strftime('%H:%M:%S')}] {log['component']}")
                report.append(f"  {log['message'][:100]}")
            report.append("")

        report.append("=" * 70)

        return "\n".join(report)

    def export_logs(self, output_path: str, component: str = None,
                   level: str = None, hours: int = 24, format: str = "json") -> bool:
        """
        导出日志

        Args:
            output_path: 输出路径
            component: 组件名称
            level: 日志级别
            hours: 时间范围
            format: 导出格式 (json, csv, txt)

        Returns:
            是否导出成功
        """
        logs = self.collect_logs(component, hours)

        # 过滤级别
        if level:
            logs = [log for log in logs if log.level == level]

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            if format == "json":
                with open(output_path, 'w', encoding='utf-8') as f:
                    data = [asdict(log) for log in logs]
                    json.dump(data, f, indent=2, ensure_ascii=False)

            elif format == "csv":
                import csv
                with open(output_path, 'w', encoding='utf-8', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(['timestamp', 'level', 'component', 'message'])
                    for log in logs:
                        timestamp_str = datetime.fromtimestamp(log.timestamp).isoformat()
                        writer.writerow([timestamp_str, log.level, log.component, log.message])

            elif format == "txt":
                with open(output_path, 'w', encoding='utf-8') as f:
                    for log in logs:
                        timestamp_str = datetime.fromtimestamp(log.timestamp).strftime('%Y-%m-%d %H:%M:%S')
                        f.write(f"[{timestamp_str}] [{log.level}] {log.component}: {log.message}\n")

            logger.info(f"已导出 {len(logs)} 条日志到 {output_path}")
            return True

        except Exception as e:
            logger.error(f"导出日志失败: {e}")
            return False


def main():
    """主函数"""
    import argparse

    # 配置日志
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )

    parser = argparse.ArgumentParser(description='日志聚合和分析')
    subparsers = parser.add_subparsers(dest='command', help='命令')

    # search命令
    parser_search = subparsers.add_parser('search', help='搜索日志')
    parser_search.add_argument('keyword', help='搜索关键词')
    parser_search.add_argument('--component', '-c', help='组件名称')
    parser_search.add_argument('--level', '-l', help='日志级别')
    parser_search.add_argument('--hours', '-t', type=int, default=24, help='时间范围(小时)')

    # errors命令
    parser_errors = subparsers.add_parser('errors', help='分析错误')
    parser_errors.add_argument('--hours', '-t', type=int, default=24, help='时间范围(小时)')

    # activity命令
    parser_activity = subparsers.add_parser('activity', help='分析活动')
    parser_activity.add_argument('--hours', '-t', type=int, default=24, help='时间范围(小时)')

    # report命令
    parser_report = subparsers.add_parser('report', help='生成报告')
    parser_report.add_argument('--hours', '-t', type=int, default=24, help='时间范围(小时)')
    parser_report.add_argument('--output', '-o', help='输出文件路径')

    # archive命令
    parser_archive = subparsers.add_parser('archive', help='归档旧日志')
    parser_archive.add_argument('--days', '-d', type=int, default=7, help='归档天数')
    parser_archive.add_argument('--no-compress', action='store_true', help='不压缩')

    # export命令
    parser_export = subparsers.add_parser('export', help='导出日志')
    parser_export.add_argument('output', help='输出文件路径')
    parser_export.add_argument('--component', '-c', help='组件名称')
    parser_export.add_argument('--level', '-l', help='日志级别')
    parser_export.add_argument('--hours', '-t', type=int, default=24, help='时间范围(小时)')
    parser_export.add_argument('--format', '-f', choices=['json', 'csv', 'txt'],
                              default='json', help='导出格式')

    args = parser.parse_args()

    aggregator = LogAggregator()

    if args.command == 'search':
        logs = aggregator.search_logs(
            args.keyword,
            component=args.component,
            level=args.level,
            hours=args.hours
        )

        print(f"\n找到 {len(logs)} 条日志:")
        print("=" * 70)
        for log in logs[-50:]:  # 显示最后50条
            timestamp = datetime.fromtimestamp(log.timestamp).strftime('%Y-%m-%d %H:%M:%S')
            print(f"[{timestamp}] [{log.level}] {log.component}")
            print(f"  {log.message}")
            print()

    elif args.command == 'errors':
        analysis = aggregator.analyze_errors(hours=args.hours)

        print("\n错误分析:")
        print("=" * 70)
        print(f"总错误数: {analysis['total_errors']}")
        print(f"总警告数: {analysis['total_warnings']}")
        print()

        if analysis['errors_by_component']:
            print("按组件:")
            for component, count in sorted(
                analysis['errors_by_component'].items(),
                key=lambda x: x[1],
                reverse=True
            ):
                print(f"  {component:20s}: {count}")
            print()

        if analysis['error_types']:
            print("错误类型:")
            for error_type, count in list(analysis['error_types'].items()):
                print(f"  {error_type}: {count}")
            print()

    elif args.command == 'activity':
        analysis = aggregator.analyze_activity(hours=args.hours)

        print("\n活动分析:")
        print("=" * 70)
        print(f"总日志数: {analysis['total_logs']}")
        print()

        print("按级别:")
        for level, count in sorted(analysis['logs_by_level'].items()):
            print(f"  {level:10s}: {count}")
        print()

        print("活跃组件:")
        for comp_info in analysis['active_components']:
            last_time = datetime.fromtimestamp(comp_info['last_activity'])
            print(f"  {comp_info['component']:20s}: {comp_info['log_count']:5d} 条 "
                  f"| 最后: {last_time.strftime('%H:%M:%S')}")
        print()

    elif args.command == 'report':
        report = aggregator.generate_report(hours=args.hours)

        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(report)
            print(f"报告已保存到: {args.output}")
        else:
            print(report)

    elif args.command == 'archive':
        count = aggregator.archive_old_logs(
            days=args.days,
            compress=not args.no_compress
        )
        print(f"已归档 {count} 个日志文件")

    elif args.command == 'export':
        success = aggregator.export_logs(
            args.output,
            component=args.component,
            level=args.level,
            hours=args.hours,
            format=args.format
        )
        if success:
            print(f"✓ 日志已导出到 {args.output}")
        else:
            print("✗ 导出失败")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
