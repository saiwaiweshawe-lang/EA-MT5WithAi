#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一测试运行器
发现并运行所有测试用例,生成测试报告
"""

import os
import sys
import json
import time
import logging
import unittest
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass, asdict

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

logger = logging.getLogger(__name__)


@dataclass
class TestResult:
    """测试结果"""
    test_name: str
    module: str
    status: str  # success, failure, error, skipped
    duration: float
    message: str = ""
    traceback: str = ""


@dataclass
class TestSuiteResult:
    """测试套件结果"""
    name: str
    start_time: float
    end_time: float
    duration: float
    total_tests: int
    passed: int
    failed: int
    errors: int
    skipped: int
    success_rate: float
    tests: List[TestResult]


class TestRunner:
    """测试运行器"""

    def __init__(self, test_dir: str = None):
        self.base_dir = Path(__file__).parent.parent

        if test_dir is None:
            test_dir = self.base_dir / "tests"

        self.test_dir = Path(test_dir)
        self.reports_dir = self.base_dir / "reports" / "tests"
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def discover_tests(self, pattern: str = "test_*.py") -> List[str]:
        """
        发现测试文件

        Args:
            pattern: 文件名模式

        Returns:
            测试文件路径列表
        """
        test_files = []

        for file in self.test_dir.glob(f"**/{pattern}"):
            if file.is_file():
                test_files.append(str(file))

        logger.info(f"发现 {len(test_files)} 个测试文件")
        return sorted(test_files)

    def run_tests(self, test_pattern: str = "test_*.py",
                  verbose: bool = True) -> TestSuiteResult:
        """
        运行测试

        Args:
            test_pattern: 测试文件模式
            verbose: 是否详细输出

        Returns:
            测试套件结果
        """
        start_time = time.time()

        # 发现测试
        loader = unittest.TestLoader()
        suite = loader.discover(
            str(self.test_dir),
            pattern=test_pattern,
            top_level_dir=str(self.base_dir)
        )

        # 运行测试
        runner = unittest.TextTestRunner(
            verbosity=2 if verbose else 1,
            stream=sys.stdout
        )

        logger.info("开始运行测试...")
        test_result = runner.run(suite)

        end_time = time.time()
        duration = end_time - start_time

        # 收集结果
        tests = []

        # 成功的测试
        for test in test_result.successes if hasattr(test_result, 'successes') else []:
            tests.append(TestResult(
                test_name=str(test),
                module=test.__class__.__module__,
                status='success',
                duration=0
            ))

        # 失败的测试
        for test, traceback in test_result.failures:
            tests.append(TestResult(
                test_name=str(test),
                module=test.__class__.__module__,
                status='failure',
                duration=0,
                message="Test failed",
                traceback=traceback
            ))

        # 错误的测试
        for test, traceback in test_result.errors:
            tests.append(TestResult(
                test_name=str(test),
                module=test.__class__.__module__,
                status='error',
                duration=0,
                message="Test error",
                traceback=traceback
            ))

        # 跳过的测试
        for test, reason in test_result.skipped:
            tests.append(TestResult(
                test_name=str(test),
                module=test.__class__.__module__,
                status='skipped',
                duration=0,
                message=reason
            ))

        total = test_result.testsRun
        passed = total - len(test_result.failures) - len(test_result.errors)
        success_rate = (passed / total * 100) if total > 0 else 0

        result = TestSuiteResult(
            name="All Tests",
            start_time=start_time,
            end_time=end_time,
            duration=duration,
            total_tests=total,
            passed=passed,
            failed=len(test_result.failures),
            errors=len(test_result.errors),
            skipped=len(test_result.skipped),
            success_rate=success_rate,
            tests=tests
        )

        logger.info(f"测试完成: {passed}/{total} 通过 ({success_rate:.1f}%)")

        return result

    def generate_report(self, result: TestSuiteResult,
                       output_path: str = None) -> str:
        """
        生成测试报告

        Args:
            result: 测试结果
            output_path: 输出路径

        Returns:
            报告文本
        """
        report = []
        report.append("=" * 80)
        report.append("测试报告")
        report.append("=" * 80)
        report.append("")

        # 概览
        report.append("## 概览")
        start_time = datetime.fromtimestamp(result.start_time)
        report.append(f"开始时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"运行时长: {result.duration:.2f}秒")
        report.append(f"总测试数: {result.total_tests}")
        report.append(f"通过: {result.passed}")
        report.append(f"失败: {result.failed}")
        report.append(f"错误: {result.errors}")
        report.append(f"跳过: {result.skipped}")
        report.append(f"成功率: {result.success_rate:.1f}%")
        report.append("")

        # 失败的测试
        failed_tests = [t for t in result.tests if t.status == 'failure']
        if failed_tests:
            report.append("## 失败的测试")
            for test in failed_tests:
                report.append(f"### {test.test_name}")
                report.append(f"模块: {test.module}")
                report.append(f"```")
                report.append(test.traceback)
                report.append(f"```")
                report.append("")

        # 错误的测试
        error_tests = [t for t in result.tests if t.status == 'error']
        if error_tests:
            report.append("## 错误的测试")
            for test in error_tests:
                report.append(f"### {test.test_name}")
                report.append(f"模块: {test.module}")
                report.append(f"```")
                report.append(test.traceback)
                report.append(f"```")
                report.append("")

        # 跳过的测试
        skipped_tests = [t for t in result.tests if t.status == 'skipped']
        if skipped_tests:
            report.append("## 跳过的测试")
            for test in skipped_tests:
                report.append(f"- {test.test_name}: {test.message}")
            report.append("")

        report.append("=" * 80)

        report_text = "\n".join(report)

        # 保存到文件
        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(report_text)

            logger.info(f"报告已保存: {output_path}")

        return report_text

    def export_results(self, result: TestSuiteResult):
        """
        导出测试结果

        Args:
            result: 测试结果
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 导出JSON
        json_file = self.reports_dir / f"test_result_{timestamp}.json"
        with open(json_file, 'w', encoding='utf-8') as f:
            data = asdict(result)
            json.dump(data, f, indent=2, ensure_ascii=False)

        # 导出文本报告
        txt_file = self.reports_dir / f"test_report_{timestamp}.txt"
        report = self.generate_report(result, str(txt_file))

        logger.info(f"测试结果已导出到: {self.reports_dir}")


def main():
    """主函数"""
    import argparse

    # 配置日志
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )

    parser = argparse.ArgumentParser(description='统一测试运行器')
    parser.add_argument('--pattern', '-p', default='test_*.py',
                       help='测试文件模式')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='详细输出')
    parser.add_argument('--export', '-e', action='store_true',
                       help='导出测试结果')

    args = parser.parse_args()

    # 创建测试运行器
    runner = TestRunner()

    # 运行测试
    result = runner.run_tests(
        test_pattern=args.pattern,
        verbose=args.verbose
    )

    # 生成报告
    print("\n")
    print(runner.generate_report(result))

    # 导出结果
    if args.export:
        runner.export_results(result)

    # 返回退出码
    sys.exit(0 if result.failed == 0 and result.errors == 0 else 1)


if __name__ == "__main__":
    main()
