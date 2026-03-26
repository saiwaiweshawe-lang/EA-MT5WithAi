# UI Module
from .main_window import MainWindow
from .dashboard import DashboardWidget
from .mt5_panel import MT5Panel
from .exchange_panel import ExchangePanel
from .news_panel import NewsPanel
from .strategy_panel import StrategyPanel
from .settings_dialog import SettingsDialog
from .wizard import SetupWizard

__all__ = [
    "MainWindow",
    "DashboardWidget",
    "MT5Panel",
    "ExchangePanel",
    "NewsPanel",
    "StrategyPanel",
    "SettingsDialog",
    "SetupWizard",
]
