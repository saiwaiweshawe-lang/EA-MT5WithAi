# 增强版交易系统配置

import os
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class TradingConfig:
    """交易配置管理"""

    def __init__(self, config_dir: str = "config"):
        self.config_dir = config_dir
        self.configs = {}
        self._load_all_configs()

    def _load_all_configs(self):
        """加载所有配置文件"""
        config_files = {
            "ai": "ai_config.json",
            "bot": "bot_config.json",
            "server": "server_config.json",
            "ea": "ea_config.json",
            "vps": "vps_config.json"
        }

        for name, filename in config_files.items():
            self.configs[name] = self._load_config(filename)

    def _load_config(self, filename: str) -> Dict:
        """加载配置文件"""
        filepath = os.path.join(self.config_dir, filename)

        try:
            if os.path.exists(filepath):
                with open(filepath, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"加载配置 {filename} 失败: {e}")

        return {}

    def get(self, key: str, default=None):
        """获取配置值"""
        keys = key.split('.')
        value = self.configs

        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default

        return value if value is not None else default

    def set(self, key: str, value):
        """设置配置值"""
        keys = key.split('.')
        config = self.configs

        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]

        config[keys[-1]] = value

    def save(self, name: str):
        """保存配置"""
        config_files = {
            "ai": "ai_config.json",
            "bot": "bot_config.json",
            "server": "server_config.json",
            "ea": "ea_config.json",
            "vps": "vps_config.json"
        }

        if name not in config_files:
            logger.error(f"未知配置名称: {name}")
            return

        filepath = os.path.join(self.config_dir, config_files[name])
        Path(os.path.dirname(filepath)).mkdir(parents=True, exist_ok=True)

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.configs.get(name, {}), f, indent=2, ensure_ascii=False)

        logger.info(f"配置已保存: {filepath}")


def create_config(config_dir: str = "config") -> TradingConfig:
    """创建配置管理器"""
    return TradingConfig(config_dir)


if __name__ == "__main__":
    config = TradingConfig()
    print("配置加载完成")
    print(f"AI模型数量: {len(config.get('ai.models', {}))}")
    print(f"新闻源数量: {len(config.get('news.sources', {}))}")
