#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
量化交易系统 V1.0.0 统一入口

用法:
    python main.py                 # 启动GUI客户端
    python main.py --api           # 启动API服务器
    python main.py --bot          # 启动Telegram机器人
    python main.py --crawler      # 启动新闻爬虫
    python main.py --evolution    # 运行策略进化
    python main.py --backtest    # 运行回测
    python main.py --status      # 查看系统状态
    python main.py --check       # 系统检查
"""

import sys
import os
import argparse
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def check_dependencies():
    """检查依赖"""
    required = [
        'MetaTrader5', 'ccxt', 'pandas', 'numpy', 
        'requests', 'PyQt6', 'flask'
    ]
    
    missing = []
    for module in required:
        try:
            __import__(module)
        except ImportError:
            missing.append(module)
    
    if missing:
        logger.error(f"缺少依赖: {', '.join(missing)}")
        logger.info("请运行: pip install -r requirements.txt")
        return False
    return True


def start_gui():
    """启动GUI客户端"""
    try:
        from PyQt6.QtWidgets import QApplication
        from client.ui.main_window import MainWindow
        
        logger.info("启动GUI客户端...")
        app = QApplication(sys.argv)
        app.setStyle("Fusion")
        
        window = MainWindow()
        window.show()
        
        sys.exit(app.exec())
    except ImportError as e:
        logger.error(f"PyQt6 未安装: {e}")
        logger.info("请运行: pip install PyQt6")
        sys.exit(1)


def start_api():
    """启动API服务器"""
    try:
        from api.server import create_app
        
        logger.info("启动API服务器...")
        app = create_app()
        app.run(host='0.0.0.0', port=5000, debug=False)
    except Exception as e:
        logger.error(f"API服务器启动失败: {e}")
        sys.exit(1)


def start_telegram_bot():
    """启动Telegram机器人"""
    try:
        from bots.telegram_bot import EnhancedTelegramBot
        
        logger.info("启动Telegram机器人...")
        bot = EnhancedTelegramBot()
        bot.run()
    except Exception as e:
        logger.error(f"Telegram机器人启动失败: {e}")
        sys.exit(1)


def start_news_crawler():
    """启动新闻爬虫"""
    try:
        from news.enhanced_news_aggregator import EnhancedNewsAggregator
        import json
        
        logger.info("启动新闻爬虫...")
        
        config_path = Path(__file__).parent / "news" / "config" / "news_config.json"
        with open(config_path) as f:
            config = json.load(f)
        
        aggregator = EnhancedNewsAggregator(config.get("news", {}))
        aggregator.start_scheduler()
        
        logger.info("新闻爬虫已启动，按 Ctrl+C 停止")
        import time
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("新闻爬虫已停止")
    except Exception as e:
        logger.error(f"新闻爬虫启动失败: {e}")
        sys.exit(1)


def run_evolution():
    """运行策略进化"""
    try:
        import pandas as pd
        import numpy as np
        from training.self_evolution_v2 import create_evolution_engine
        
        logger.info("运行策略进化...")
        
        config = {
            "population_size": 30,
            "elite_ratio": 0.1,
            "mutation_rate": 0.1,
            "early_stop_patience": 15,
        }
        
        np.random.seed(42)
        n_points = 2000
        prices = 2000 + np.cumsum(np.random.randn(n_points) * 10)
        market_data = pd.DataFrame({
            'close': prices,
            'open': np.roll(prices, 1) + np.random.randn(n_points) * 2,
            'high': prices + np.random.rand(n_points) * 20,
            'low': prices - np.random.rand(n_points) * 20,
            'volume': np.random.randint(1000, 10000, n_points)
        })
        
        engine = create_evolution_engine(config)
        best_strategy = engine.run(market_data, max_generations=50)
        
        if best_strategy:
            logger.info(f"最佳策略: {best_strategy.name}")
            logger.info(f"类型: {best_strategy.strategy_type}")
        else:
            logger.warning("未找到有效策略")
            
    except Exception as e:
        logger.error(f"策略进化失败: {e}")
        sys.exit(1)


def run_backtest():
    """运行回测"""
    try:
        from utilities.backtesting_engine import BacktestEngine
        import pandas as pd
        
        logger.info("运行回测...")
        
        config = {
            "initial_balance": 10000,
            "commission": 0.001,
        }
        
        engine = BacktestEngine(config)
        
        np.random.seed(42)
        n_points = 1000
        prices = 2000 + np.cumsum(np.random.randn(n_points) * 10)
        market_data = pd.DataFrame({
            'close': prices,
            'open': np.roll(prices, 1) + np.random.randn(n_points) * 2,
            'high': prices + np.random.rand(n_points) * 20,
            'low': prices - np.random.rand(n_points) * 20,
            'volume': np.random.randint(1000, 10000, n_points)
        })
        
        results = engine.run(market_data)
        logger.info(f"回测完成: 盈亏 {results.get('profit', 0):.2f}")
        
    except Exception as e:
        logger.error(f"回测失败: {e}")
        sys.exit(1)


def check_system():
    """系统检查"""
    try:
        from utilities.system_checker import SystemChecker
        
        logger.info("运行系统检查...")
        
        checker = SystemChecker()
        checker.run_all_checks()
        
    except Exception as e:
        logger.error(f"系统检查失败: {e}")
        sys.exit(1)


def show_status():
    """显示状态"""
    print("\n" + "=" * 50)
    print("  量化交易系统 V1.0.0 状态")
    print("=" * 50)
    
    print("\n[模块状态]")
    modules = [
        ("GUI客户端", "PyQt6"),
        ("API服务器", "flask"),
        ("Telegram机器人", "telegram"),
        ("新闻爬虫", "feedparser"),
        ("策略进化", "numpy"),
    ]
    
    for name, dep in modules:
        try:
            __import__(dep.lower() if dep.lower() != "PyQt6" else "PyQt6")
            status = "✓ 已安装"
        except ImportError:
            status = "✗ 未安装"
        print(f"  {name}: {status}")
    
    print("\n[配置文件]")
    config_dir = Path(__file__).parent / "config"
    if config_dir.exists():
        configs = list(config_dir.glob("*.json"))
        print(f"  配置文件: {len(configs)} 个")
        for cfg in configs[:5]:
            print(f"    - {cfg.name}")
    else:
        print("  配置文件目录不存在")
    
    print("\n" + "=" * 50)


def main():
    parser = argparse.ArgumentParser(
        description="量化交易系统 V1.0.0",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python main.py              启动GUI
  python main.py --api         启动API服务器
  python main.py --status      查看状态
  python main.py --check       系统检查
        """
    )
    
    parser.add_argument('--gui', action='store_true', help='启动GUI客户端')
    parser.add_argument('--api', action='store_true', help='启动API服务器')
    parser.add_argument('--bot', action='store_true', help='启动Telegram机器人')
    parser.add_argument('--crawler', action='store_true', help='启动新闻爬虫')
    parser.add_argument('--evolution', action='store_true', help='运行策略进化')
    parser.add_argument('--backtest', action='store_true', help='运行回测')
    parser.add_argument('--status', action='store_true', help='查看系统状态')
    parser.add_argument('--check', action='store_true', help='系统检查')
    
    args = parser.parse_args()
    
    if not any(vars(args).values()):
        if not check_dependencies():
            sys.exit(1)
        show_status()
        print("\n使用 --help 查看所有选项")
        sys.exit(0)
    
    if args.gui or not any(vars(args).values()):
        start_gui()
    elif args.api:
        start_api()
    elif args.bot:
        start_telegram_bot()
    elif args.crawler:
        start_news_crawler()
    elif args.evolution:
        run_evolution()
    elif args.backtest:
        run_backtest()
    elif args.status:
        show_status()
    elif args.check:
        check_system()


if __name__ == "__main__":
    main()
