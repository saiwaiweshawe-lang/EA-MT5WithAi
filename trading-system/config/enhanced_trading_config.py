# 增强交易配置
# 整合所有新功能的完整配置

from dataclasses import dataclass, field
from typing import Dict, List, Optional
import json


@dataclass
class RiskManagementConfig:
    """风险管理配置"""
    # 基础风险参数
    base_risk_per_trade: float = 0.02      # 单笔基础风险 2%
    max_risk_per_trade: float = 0.05        # 单笔最大风险 5%
    max_total_risk: float = 0.10            # 总风险 10%

    # 止损参数
    stop_loss_pct: float = 0.02             # 基础止损 2%
    atr_multiplier: float = 2.0              # ATR倍数
    trailing_stop_activation: float = 0.02   # 移动止损激活 2%
    trailing_stop_distance: float = 0.01       # 移动止损距离 1%

    # 止盈参数
    take_profit_pct: float = 0.04           # 基础止盈 4%
    risk_reward_ratio: float = 2.0           # 盈亏比

    # 连续亏损控制
    consecutive_loss_reduction: bool = True
    consecutive_loss_threshold: int = 2
    consecutive_loss_factor: float = 0.5

    # 每日限制
    daily_loss_limit_pct: float = 0.05
    max_consecutive_losses: int = 3

    # 回撤控制
    drawdown_thresholds: Dict[str, float] = field(default_factory=lambda: {
        "warning": 0.03,
        "moderate": 0.05,
        "severe": 0.08,
        "critical": 0.12,
        "emergency": 0.15
    })
    cooling_periods: Dict[str, int] = field(default_factory=lambda: {
        "moderate": 60,
        "severe": 180,
        "critical": 480,
        "emergency": 1440
    })


@dataclass
class PositionManagementConfig:
    """仓位管理配置"""
    # 仓位计算模型
    risk_model: str = "composite"  # composite, kelly, volatility_adjusted

    # Kelly准则参数
    kelly_fraction: float = 0.5
    min_kelly: float = 0.1
    max_kelly: float = 0.25

    # 波动率调整
    volatility_adjustment_enabled: bool = True
    atr_window: int = 14

    # 持仓限制
    max_positions: int = 3
    max_per_symbol: int = 1

    # 相关性控制
    max_correlated_exposure: float = 0.30
    correlation_threshold: float = 0.7


@dataclass
class MultiTimeframeConfig:
    """多时间框架配置"""
    timeframes: Dict[str, List[str]] = field(default_factory=lambda: {
        "trend": ["1d", "4h"],      # 主趋势
        "entry": ["1h"],              # 入场方向
        "timing": ["15m", "5m"]      # 入场时机
    })

    # 确认参数
    confirmation_threshold: int = 2
    trend_alignment_required: bool = True

    # MA周期
    ma_periods: Dict[str, int] = field(default_factory=lambda: {
        "fast": 7,
        "medium": 25,
        "slow": 50,
        "long": 200
    })


@dataclass
class MarketStateFilterConfig:
    """市场状态过滤配置"""
    # 检测参数
    lookback_period: int = 100
    trend_period: int = 50

    # 阈值
    strong_trend_threshold: float = 0.7
    weak_trend_threshold: float = 0.3
    high_volatility_threshold: float = 0.02
    low_volatility_threshold: float = 0.005

    # 策略映射
    strategy_filtering: bool = True


@dataclass
class AdaptiveParameterConfig:
    """参数自适应配置"""
    adaptation_mode: str = "hybrid"  # volatility_based, trend_based, performance_based, hybrid
    auto_optimize: bool = True

    # 调整频率
    adjustment_interval_minutes: int = 60
    min_stable_periods: int = 5

    # 参数范围
    parameter_ranges: Dict[str, tuple] = field(default_factory=lambda: {
        "risk_per_trade": (0.005, 0.10),
        "stop_loss_pct": (0.005, 0.10),
        "take_profit_pct": (0.01, 0.20),
        "atr_multiplier": (1.0, 4.0)
    })


@dataclass
class FundingArbitrageConfig:
    """资金费率套利配置"""
    # 资金费率阈值
    high_funding_threshold: float = 0.0001     # 0.01%
    low_funding_threshold: float = -0.0001      # -0.01%
    extreme_funding_threshold: float = 0.0003   # 0.03%

    # 策略参数
    min_profit_threshold: float = 0.001         # 0.1%
    min_confidence: float = 0.6
    max_position_size: float = 0.5

    # 限制
    max_daily_trades: int = 3


@dataclass
class TrailingStopConfig:
    """移动止损配置"""
    enabled: bool = True
    default_strategy: str = "dynamic"  # percentage, atr, support_resistance, chandelier, parabolic_sar, dynamic

    # 通用参数
    activation_profit_pct: float = 2.0
    trailing_distance_pct: float = 1.0
    step_size_pct: float = 0.5
    atr_multiplier: float = 2.0
    lock_profit_pct: float = 50.0

    # 范围限制
    max_trailing_distance_pct: float = 5.0
    min_trailing_distance_pct: float = 0.3


@dataclass
class EnhancedTradingConfig:
    """增强交易配置 - 整合所有模块"""

    # 账户设置
    initial_balance: float = 10000.0
    min_balance: float = 1000.0
    auto_recharge: bool = False

    # 交易所设置
    exchange: str = "binance_futures"
    testnet: bool = True

    # 交易品种
    symbols: List[str] = field(default_factory=lambda: [
        "BTCUSDT", "ETHUSDT", "BNBUSDT"
    ])

    # 子配置
    risk_management: RiskManagementConfig = field(default_factory=RiskManagementConfig)
    position_management: PositionManagementConfig = field(default_factory=PositionManagementConfig)
    multi_timeframe: MultiTimeframeConfig = field(default_factory=MultiTimeframeConfig)
    market_state_filter: MarketStateFilterConfig = field(default_factory=MarketStateFilterConfig)
    adaptive_parameters: AdaptiveParameterConfig = field(default_factory=AdaptiveParameterConfig)
    funding_arbitrage: FundingArbitrageConfig = field(default_factory=FundingArbitrageConfig)
    trailing_stop: TrailingStopConfig = field(default_factory=TrailingStopConfig)

    # 通知设置
    enable_notifications: bool = True
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # 日志设置
    log_level: str = "INFO"
    log_file: str = "logs/trading.log"

    def to_dict(self) -> Dict:
        """转换为字典"""
        from dataclasses import asdict
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> 'EnhancedTradingConfig':
        """从字典创建"""
        return cls(**data)

    @classmethod
    def from_json_file(cls, filepath: str) -> 'EnhancedTradingConfig':
        """从JSON文件加载"""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 递归处理嵌套字典
        return cls._from_dict_recursive(data)

    @classmethod
    def _from_dict_recursive(cls, data: Dict) -> 'EnhancedTradingConfig':
        """递归从字典创建"""
        result = {}

        for key, value in data.items():
            if isinstance(value, dict):
                # 检查是否有对应的dataclass
                if key == "risk_management":
                    result[key] = RiskManagementConfig(**value)
                elif key == "position_management":
                    result[key] = PositionManagementConfig(**value)
                elif key == "multi_timeframe":
                    result[key] = MultiTimeframeConfig(**value)
                elif key == "market_state_filter":
                    result[key] = MarketStateFilterConfig(**value)
                elif key == "adaptive_parameters":
                    result[key] = AdaptiveParameterConfig(**value)
                elif key == "funding_arbitrage":
                    result[key] = FundingArbitrageConfig(**value)
                elif key == "trailing_stop":
                    result[key] = TrailingStopConfig(**value)
                else:
                    result[key] = value
            else:
                result[key] = value

        return cls(**result)

    def to_json_file(self, filepath: str):
        """保存到JSON文件"""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)


def load_config(filepath: str) -> EnhancedTradingConfig:
    """加载配置文件"""
    try:
        return EnhancedTradingConfig.from_json_file(filepath)
    except FileNotFoundError:
        # 文件不存在，返回默认配置
        config = EnhancedTradingConfig()
        config.to_json_file(filepath)
        return config


def save_config(config: EnhancedTradingConfig, filepath: str):
    """保存配置"""
    config.to_json_file(filepath)


# 默认配置模板
DEFAULT_CONFIG_TEMPLATE = {
    "initial_balance": 10000.0,
    "exchange": "binance_futures",
    "testnet": True,
    "symbols": ["BTCUSDT", "ETHUSDT"],

    "risk_management": {
        "base_risk_per_trade": 0.02,
        "max_risk_per_trade": 0.05,
        "max_total_risk": 0.10,
        "stop_loss_pct": 0.02,
        "atr_multiplier": 2.0,
        "take_profit_pct": 0.04,
        "risk_reward_ratio": 2.0,
        "consecutive_loss_reduction": True,
        "consecutive_loss_threshold": 2,
        "consecutive_loss_factor": 0.5,
        "daily_loss_limit_pct": 0.05,
        "max_consecutive_losses": 3,
        "drawdown_thresholds": {
            "warning": 0.03,
            "moderate": 0.05,
            "severe": 0.08,
            "critical": 0.12,
            "emergency": 0.15
        },
        "cooling_periods": {
            "moderate": 60,
            "severe": 180,
            "critical": 480,
            "emergency": 1440
        }
    },

    "position_management": {
        "risk_model": "composite",
        "kelly_fraction": 0.5,
        "min_kelly": 0.1,
        "max_kelly": 0.25,
        "volatility_adjustment_enabled": True,
        "atr_window": 14,
        "max_positions": 3,
        "max_per_symbol": 1,
        "max_correlated_exposure": 0.30,
        "correlation_threshold": 0.7
    },

    "multi_timeframe": {
        "timeframes": {
            "trend": ["1d", "4h"],
            "entry": ["1h"],
            "timing": ["15m", "5m"]
        },
        "confirmation_threshold": 2,
        "trend_alignment_required": True,
        "ma_periods": {
            "fast": 7,
            "medium": 25,
            "slow": 50,
            "long": 200
        }
    },

    "market_state_filter": {
        "lookback_period": 100,
        "trend_period": 50,
        "strong_trend_threshold": 0.7,
        "weak_trend_threshold": 0.3,
        "high_volatility_threshold": 0.02,
        "low_volatility_threshold": 0.005,
        "strategy_filtering": True
    },

    "adaptive_parameters": {
        "adaptation_mode": "hybrid",
        "auto_optimize": True,
        "adjustment_interval_minutes": 60,
        "min_stable_periods": 5,
        "parameter_ranges": {
            "risk_per_trade": (0.005, 0.10),
            "stop_loss_pct": (0.005, 0.10),
            "take_profit_pct": (0.01, 0.20),
            "atr_multiplier": (1.0, 4.0)
        }
    },

    "funding_arbitrage": {
        "high_funding_threshold": 0.0001,
        "low_funding_threshold": -0.0001,
        "extreme_funding_threshold": 0.0003,
        "min_profit_threshold": 0.001,
        "min_confidence": 0.6,
        "max_position_size": 0.5,
        "max_daily_trades": 3
    },

    "trailing_stop": {
        "enabled": True,
        "default_strategy": "dynamic",
        "activation_profit_pct": 2.0,
        "trailing_distance_pct": 1.0,
        "step_size_pct": 0.5,
        "atr_multiplier": 2.0,
        "lock_profit_pct": 50.0,
        "max_trailing_distance_pct": 5.0,
        "min_trailing_distance_pct": 0.3
    },

    "enable_notifications": True,
    "log_level": "INFO",
    "log_file": "logs/trading.log"
}


if __name__ == "__main__":
    # 测试代码
    import os

    # 创建默认配置文件
    config_path = "config/enhanced_trading_config.json"
    os.makedirs(os.path.dirname(config_path), exist_ok=True)

    config = EnhancedTradingConfig()
    config.to_json_file(config_path)

    print(f"默认配置已创建: {config_path}")
    print("\n配置摘要:")
    print(f"  初始资金: ${config.initial_balance:,.2f}")
    print(f"  基础风险: {config.risk_management.base_risk_per_trade:.1%}")
    print(f"  最大仓位: {config.position_management.max_positions}")
    print(f"  交易品种: {', '.join(config.symbols)}")
    print(f"  时间框架: {config.multi_timeframe.timeframes}")
