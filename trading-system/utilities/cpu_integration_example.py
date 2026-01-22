#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CPU限制集成示例 - 演示如何在现有模块中集成CPU限制功能
"""

import time
import logging
from pathlib import Path
from utilities.cpu_limiter import CPULimiter

logger = logging.getLogger(__name__)


class CPUAwareModule:
    """CPU感知模块基类"""

    def __init__(self):
        self.cpu_limiter = CPULimiter()
        self.cpu_limiter.start()
        logger.info("CPU限制器已启动")

    def should_run_operation(self, operation_type: str = "general") -> bool:
        """
        判断是否应该执行某个操作

        Args:
            operation_type: 操作类型 ("ai_request", "non_critical", "general")

        Returns:
            是否应该执行
        """
        return not self.cpu_limiter.should_throttle_operation(operation_type)

    def get_sleep_time(self, base_sleep: float) -> float:
        """
        获取调整后的sleep时间

        Args:
            base_sleep: 基础sleep时间

        Returns:
            调整后的sleep时间
        """
        multiplier = self.cpu_limiter.get_sleep_multiplier()
        return base_sleep * multiplier

    def safe_cpu_intensive_operation(self, operation_func, *args, **kwargs):
        """
        安全执行CPU密集型操作

        Args:
            operation_func: 要执行的函数
            *args, **kwargs: 函数参数

        Returns:
            函数执行结果,如果被限制则返回None
        """
        if not self.should_run_operation("ai_request"):
            logger.warning("CPU使用率过高,跳过CPU密集型操作")
            return None

        try:
            return operation_func(*args, **kwargs)
        except Exception as e:
            logger.error(f"操作执行失败: {e}")
            return None

    def cleanup(self):
        """清理资源"""
        if self.cpu_limiter:
            self.cpu_limiter.stop()
            logger.info("CPU限制器已停止")


# ============================================================================
# 示例1: AI模型集成
# ============================================================================

class AIEnsembleWithCPULimit(CPUAwareModule):
    """带CPU限制的AI模型集成"""

    def __init__(self):
        super().__init__()
        self.model_cache = {}

    def predict(self, data):
        """预测操作"""
        # 检查是否应该执行AI请求
        if not self.should_run_operation("ai_request"):
            logger.warning("CPU限制中,使用缓存结果或简化预测")
            return self._get_simplified_prediction(data)

        # 正常预测
        return self._full_prediction(data)

    def _full_prediction(self, data):
        """完整预测"""
        logger.info("执行完整AI预测")
        # 实际的AI预测逻辑
        time.sleep(0.1)  # 模拟计算
        return {"prediction": "full", "confidence": 0.95}

    def _get_simplified_prediction(self, data):
        """简化预测"""
        logger.info("执行简化预测")
        # 使用更简单的逻辑或缓存
        return {"prediction": "simplified", "confidence": 0.70}


# ============================================================================
# 示例2: 训练模块集成
# ============================================================================

class ModelTrainerWithCPULimit(CPUAwareModule):
    """带CPU限制的模型训练器"""

    def train_loop(self, epochs: int = 100):
        """训练循环"""
        logger.info(f"开始训练,计划{epochs}轮")

        for epoch in range(epochs):
            # 检查是否应该继续训练
            if not self.should_run_operation("ai_request"):
                logger.warning(f"CPU限制中,暂停训练 (轮次 {epoch}/{epochs})")

                # 等待CPU恢复
                sleep_time = self.get_sleep_time(60)
                logger.info(f"等待 {sleep_time:.1f} 秒后继续")
                time.sleep(sleep_time)
                continue

            # 执行训练
            self._train_one_epoch(epoch)

            # 使用调整后的sleep时间
            sleep_time = self.get_sleep_time(1)
            time.sleep(sleep_time)

        logger.info("训练完成")

    def _train_one_epoch(self, epoch: int):
        """训练一轮"""
        logger.info(f"训练轮次 {epoch}")
        # 实际的训练逻辑
        time.sleep(0.5)  # 模拟训练


# ============================================================================
# 示例3: 数据处理集成
# ============================================================================

class DataProcessorWithCPULimit(CPUAwareModule):
    """带CPU限制的数据处理器"""

    def process_large_dataset(self, data_items: list):
        """处理大数据集"""
        logger.info(f"开始处理 {len(data_items)} 条数据")
        results = []

        for i, item in enumerate(data_items):
            # 非关键操作,可以跳过
            if not self.should_run_operation("non_critical"):
                logger.debug(f"跳过非关键数据处理 ({i}/{len(data_items)})")
                continue

            # 处理数据
            result = self._process_item(item)
            results.append(result)

            # 调整sleep时间
            if i % 10 == 0:
                sleep_time = self.get_sleep_time(0.1)
                time.sleep(sleep_time)

        logger.info(f"处理完成,成功 {len(results)}/{len(data_items)} 条")
        return results

    def _process_item(self, item):
        """处理单个项目"""
        # 实际的处理逻辑
        time.sleep(0.01)
        return {"processed": True, "item": item}


# ============================================================================
# 测试函数
# ============================================================================

def test_ai_ensemble():
    """测试AI模型集成"""
    print("\n" + "=" * 50)
    print("测试 AI模型集成")
    print("=" * 50)

    model = AIEnsembleWithCPULimit()

    for i in range(5):
        result = model.predict({"data": i})
        print(f"预测 {i}: {result}")
        time.sleep(1)

    model.cleanup()


def test_model_trainer():
    """测试训练器集成"""
    print("\n" + "=" * 50)
    print("测试 模型训练器")
    print("=" * 50)

    trainer = ModelTrainerWithCPULimit()
    trainer.train_loop(epochs=10)
    trainer.cleanup()


def test_data_processor():
    """测试数据处理器集成"""
    print("\n" + "=" * 50)
    print("测试 数据处理器")
    print("=" * 50)

    processor = DataProcessorWithCPULimit()
    data = list(range(50))
    results = processor.process_large_dataset(data)
    print(f"处理结果: {len(results)} 条")
    processor.cleanup()


if __name__ == "__main__":
    import sys

    # 配置日志
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )

    if len(sys.argv) > 1:
        test_type = sys.argv[1]
        if test_type == "ai":
            test_ai_ensemble()
        elif test_type == "train":
            test_model_trainer()
        elif test_type == "data":
            test_data_processor()
        else:
            print("用法: python cpu_integration_example.py [ai|train|data]")
    else:
        print("演示所有集成示例:")
        test_ai_ensemble()
        test_model_trainer()
        test_data_processor()
