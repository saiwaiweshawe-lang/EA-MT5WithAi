import json
import os
import logging
from dataclasses import dataclass, asdict, field
from typing import List, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class MT5Config:
    server: str = ""
    account: int = 0
    password: str = ""
    symbols: List[str] = field(default_factory=list)
    enabled: bool = False


@dataclass
class ExchangeConfig:
    api_key: str = ""
    api_secret: str = ""
    enabled: bool = False
    symbols: List[str] = field(default_factory=list)


@dataclass
class TradingConfig:
    auto_trade: bool = False
    max_positions: int = 3
    risk_per_trade: float = 0.02
    stop_loss_pips: int = 50
    take_profit_pips: int = 100


@dataclass
class NewsConfig:
    enabled: bool = True
    interval_minutes: int = 15
    keywords: List[str] = field(default_factory=lambda: [
        "bitcoin", "btc", "ethereum", "eth", "crypto", "trading"
    ])


@dataclass
class AppConfig:
    mt5: MT5Config = field(default_factory=MT5Config)
    exchanges: Dict[str, ExchangeConfig] = field(default_factory=dict)
    trading: TradingConfig = field(default_factory=TradingConfig)
    news: NewsConfig = field(default_factory=NewsConfig)
    first_run: bool = True


class ConfigManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        
        self.config_dir = os.path.join(os.path.expanduser("~"), ".quant_trader")
        self.config_file = os.path.join(self.config_dir, "config.json")
        self._ensure_config_dir()
        self.config = self._load_config()
        self._initialized = True

    def _ensure_config_dir(self):
        if not os.path.exists(self.config_dir):
            os.makedirs(self.config_dir, exist_ok=True)
            logger.info(f"Created config directory: {self.config_dir}")

    def _load_config(self) -> AppConfig:
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                mt5 = MT5Config(**data.get("mt5", {}))
                exchanges = {
                    name: ExchangeConfig(**cfg) 
                    for name, cfg in data.get("exchanges", {}).items()
                }
                trading = TradingConfig(**data.get("trading", {}))
                news = NewsConfig(**data.get("news", {}))
                
                return AppConfig(
                    mt5=mt5,
                    exchanges=exchanges,
                    trading=trading,
                    news=news,
                    first_run=data.get("first_run", True)
                )
            except Exception as e:
                logger.error(f"Failed to load config: {e}")
        
        return AppConfig()

    def save_config(self):
        try:
            data = {
                "mt5": asdict(self.config.mt5),
                "exchanges": {
                    name: asdict(cfg) 
                    for name, cfg in self.config.exchanges.items()
                },
                "trading": asdict(self.config.trading),
                "news": asdict(self.config.news),
                "first_run": self.config.first_run
            }
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.info("Config saved successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
            return False

    def update_mt5(self, server: str, account: int, password: str):
        self.config.mt5.server = server
        self.config.mt5.account = account
        self.config.mt5.password = password
        self.config.mt5.enabled = True
        self.save_config()

    def update_exchange(self, name: str, api_key: str, api_secret: str):
        self.config.exchanges[name] = ExchangeConfig(
            api_key=api_key,
            api_secret=api_secret,
            enabled=True
        )
        self.save_config()

    def update_trading(self, auto_trade: bool = None, max_positions: int = None,
                      risk_per_trade: float = None):
        if auto_trade is not None:
            self.config.trading.auto_trade = auto_trade
        if max_positions is not None:
            self.config.trading.max_positions = max_positions
        if risk_per_trade is not None:
            self.config.trading.risk_per_trade = risk_per_trade
        self.save_config()

    def set_mt5_symbols(self, symbols: List[str]):
        self.config.mt5.symbols = symbols
        self.save_config()

    def set_exchange_symbols(self, exchange: str, symbols: List[str]):
        if exchange in self.config.exchanges:
            self.config.exchanges[exchange].symbols = symbols
            self.save_config()

    def mark_first_run_complete(self):
        self.config.first_run = False
        self.save_config()

    def is_configured(self) -> bool:
        return (
            (self.config.mt5.enabled and self.config.mt5.account > 0) or
            any(cfg.enabled for cfg in self.config.exchanges.values())
        )

    def get_status(self) -> Dict:
        return {
            "mt5_connected": self.config.mt5.enabled,
            "mt5_server": self.config.mt5.server,
            "exchanges": {
                name: cfg.enabled 
                for name, cfg in self.config.exchanges.items()
            },
            "auto_trade": self.config.trading.auto_trade,
            "first_run": self.config.first_run
        }


def get_config_manager() -> ConfigManager:
    return ConfigManager()
