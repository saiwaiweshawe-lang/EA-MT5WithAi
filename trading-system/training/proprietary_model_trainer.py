# 自有交易模型训练框架
# 培养和进化专属的交易策略模型

import os
import json
import logging
import pickle
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
import sqlite3

logger = logging.getLogger(__name__)


class ModelType(Enum):
    """模型类型"""
    ENTRY_SIGNAL = "entry_signal"  # 入场信号模型
    EXIT_SIGNAL = "exit_signal"  # 出场信号模型
    POSITION_SIZING = "position_sizing"  # 仓位管理模型
    RISK_ASSESSMENT = "risk_assessment"  # 风险评估模型
    MARKET_REGIME = "market_regime"  # 市场状态识别模型


@dataclass
class TradeRecord:
    """交易记录"""
    timestamp: str
    symbol: str
    side: str  # long/short
    entry_price: float
    exit_price: float
    quantity: float
    pnl: float
    pnl_pct: float
    duration_minutes: int
    entry_indicators: Dict
    exit_indicators: Dict
    market_context: Dict
    tags: List[str] = None  # 标签:如"trend_following", "mean_reversion"


@dataclass
class ModelPerformance:
    """模型性能指标"""
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    sharpe_ratio: float
    max_drawdown: float
    total_pnl: float
    total_pnl_pct: float


class ProprietaryModelTrainer:
    """自有模型训练器"""

    def __init__(self, config: Dict):
        self.config = config
        self.enabled = config.get("enabled", True)

        # 数据存储
        self.db_path = config.get("db_path", "training/proprietary_models.db")
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        self.models_dir = config.get("models_dir", "training/models/proprietary")
        os.makedirs(self.models_dir, exist_ok=True)

        # 训练参数
        self.min_trades_for_training = config.get("min_trades_for_training", 100)
        self.retrain_interval_days = config.get("retrain_interval_days", 7)
        self.validation_split = config.get("validation_split", 0.2)

        # 特征工程配置
        self.feature_config = config.get("features", {
            "price_features": ["sma_20", "sma_50", "rsi", "macd", "bb_position"],
            "volume_features": ["volume_sma_ratio", "volume_trend"],
            "volatility_features": ["atr", "bb_width", "price_volatility"],
            "time_features": ["hour", "day_of_week", "is_asian_session"],
            "market_features": ["trend", "support_distance", "resistance_distance"]
        })

        # 模型注册表
        self.models: Dict[str, Any] = {}
        self.model_metadata: Dict[str, Dict] = {}

        # 初始化数据库
        self._init_database()

        # 加载已有模型
        self._load_existing_models()

        logger.info("自有交易模型训练框架已初始化")

    def _init_database(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 交易记录表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trade_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                entry_price REAL NOT NULL,
                exit_price REAL NOT NULL,
                quantity REAL NOT NULL,
                pnl REAL NOT NULL,
                pnl_pct REAL NOT NULL,
                duration_minutes INTEGER,
                entry_indicators TEXT,
                exit_indicators TEXT,
                market_context TEXT,
                tags TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 模型训练历史表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS model_training_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_name TEXT NOT NULL,
                model_type TEXT NOT NULL,
                version INTEGER NOT NULL,
                train_start_date TEXT,
                train_end_date TEXT,
                num_samples INTEGER,
                performance_metrics TEXT,
                feature_importance TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 模型预测记录表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS model_predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_name TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                symbol TEXT NOT NULL,
                prediction TEXT NOT NULL,
                confidence REAL,
                actual_outcome TEXT,
                is_correct BOOLEAN,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()
        conn.close()

    def record_trade(self, trade: TradeRecord):
        """记录交易"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO trade_records
            (timestamp, symbol, side, entry_price, exit_price, quantity,
             pnl, pnl_pct, duration_minutes, entry_indicators, exit_indicators,
             market_context, tags)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            trade.timestamp,
            trade.symbol,
            trade.side,
            trade.entry_price,
            trade.exit_price,
            trade.quantity,
            trade.pnl,
            trade.pnl_pct,
            trade.duration_minutes,
            json.dumps(trade.entry_indicators),
            json.dumps(trade.exit_indicators),
            json.dumps(trade.market_context),
            json.dumps(trade.tags) if trade.tags else None
        ))

        conn.commit()
        conn.close()

        logger.info(f"交易记录已保存: {trade.symbol} {trade.side} PnL={trade.pnl_pct:.2f}%")

    def get_trade_history(self, symbol: Optional[str] = None,
                         start_date: Optional[str] = None,
                         end_date: Optional[str] = None,
                         limit: int = 1000) -> List[TradeRecord]:
        """获取交易历史"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        query = "SELECT * FROM trade_records WHERE 1=1"
        params = []

        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)

        if start_date:
            query += " AND timestamp >= ?"
            params.append(start_date)

        if end_date:
            query += " AND timestamp <= ?"
            params.append(end_date)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()

        conn.close()

        records = []
        for row in rows:
            records.append(TradeRecord(
                timestamp=row[1],
                symbol=row[2],
                side=row[3],
                entry_price=row[4],
                exit_price=row[5],
                quantity=row[6],
                pnl=row[7],
                pnl_pct=row[8],
                duration_minutes=row[9],
                entry_indicators=json.loads(row[10]) if row[10] else {},
                exit_indicators=json.loads(row[11]) if row[11] else {},
                market_context=json.loads(row[12]) if row[12] else {},
                tags=json.loads(row[13]) if row[13] else []
            ))

        return records

    def train_entry_model(self, symbol: Optional[str] = None) -> Dict:
        """
        训练入场信号模型
        使用历史交易数据训练一个分类模型
        """
        logger.info("开始训练入场信号模型...")

        # 1. 获取训练数据
        trades = self.get_trade_history(symbol=symbol)

        if len(trades) < self.min_trades_for_training:
            logger.warning(
                f"交易数据不足({len(trades)}/{self.min_trades_for_training}),无法训练"
            )
            return {"success": False, "message": "数据不足"}

        # 2. 特征工程
        X, y = self._prepare_entry_features(trades)

        if X.shape[0] == 0:
            return {"success": False, "message": "特征提取失败"}

        # 3. 训练模型
        model, metrics = self._train_classification_model(X, y)

        # 4. 保存模型
        model_name = f"entry_signal_{symbol or 'all'}"
        self._save_model(model_name, ModelType.ENTRY_SIGNAL, model, metrics)

        logger.info(f"入场模型训练完成: {metrics}")

        return {
            "success": True,
            "model_name": model_name,
            "metrics": metrics
        }

    def train_exit_model(self, symbol: Optional[str] = None) -> Dict:
        """训练出场信号模型"""
        logger.info("开始训练出场信号模型...")

        trades = self.get_trade_history(symbol=symbol)

        if len(trades) < self.min_trades_for_training:
            return {"success": False, "message": "数据不足"}

        # 特征工程:分析成功交易的出场特征
        X, y = self._prepare_exit_features(trades)

        if X.shape[0] == 0:
            return {"success": False, "message": "特征提取失败"}

        model, metrics = self._train_classification_model(X, y)

        model_name = f"exit_signal_{symbol or 'all'}"
        self._save_model(model_name, ModelType.EXIT_SIGNAL, model, metrics)

        logger.info(f"出场模型训练完成: {metrics}")

        return {
            "success": True,
            "model_name": model_name,
            "metrics": metrics
        }

    def train_position_sizing_model(self, symbol: Optional[str] = None) -> Dict:
        """训练仓位管理模型"""
        logger.info("开始训练仓位管理模型...")

        trades = self.get_trade_history(symbol=symbol)

        if len(trades) < self.min_trades_for_training:
            return {"success": False, "message": "数据不足"}

        # 分析:什么情况下应该用大仓位,什么情况小仓位
        X, y = self._prepare_position_sizing_features(trades)

        if X.shape[0] == 0:
            return {"success": False, "message": "特征提取失败"}

        # 这里使用回归模型预测最优仓位比例
        model, metrics = self._train_regression_model(X, y)

        model_name = f"position_sizing_{symbol or 'all'}"
        self._save_model(model_name, ModelType.POSITION_SIZING, model, metrics)

        logger.info(f"仓位管理模型训练完成: {metrics}")

        return {
            "success": True,
            "model_name": model_name,
            "metrics": metrics
        }

    def _prepare_entry_features(self, trades: List[TradeRecord]) -> Tuple[np.ndarray, np.ndarray]:
        """准备入场特征"""
        features = []
        labels = []

        for trade in trades:
            # 特征:入场时的指标
            indicators = trade.entry_indicators
            market = trade.market_context

            feature_vector = [
                indicators.get("rsi", 50),
                indicators.get("macd", 0),
                indicators.get("sma_20", 0),
                indicators.get("sma_50", 0),
                indicators.get("bb_position", 0.5),
                indicators.get("atr", 0),
                market.get("trend_score", 0),
                market.get("volume_ratio", 1),
                market.get("volatility", 0)
            ]

            # 标签:是否盈利
            label = 1 if trade.pnl > 0 else 0

            features.append(feature_vector)
            labels.append(label)

        return np.array(features), np.array(labels)

    def _prepare_exit_features(self, trades: List[TradeRecord]) -> Tuple[np.ndarray, np.ndarray]:
        """准备出场特征"""
        features = []
        labels = []

        for trade in trades:
            # 特征:出场时的指标
            indicators = trade.exit_indicators

            feature_vector = [
                indicators.get("rsi", 50),
                indicators.get("macd", 0),
                indicators.get("bb_position", 0.5),
                trade.pnl_pct,  # 当前盈亏
                trade.duration_minutes,  # 持仓时间
                indicators.get("trend_strength", 0)
            ]

            # 标签:是否在最佳时机出场(例如是否接近最大盈利)
            # 这里简化为:盈利>5%且持仓时间适中为好的出场
            label = 1 if (trade.pnl_pct > 5 and 30 < trade.duration_minutes < 480) else 0

            features.append(feature_vector)
            labels.append(label)

        return np.array(features), np.array(labels)

    def _prepare_position_sizing_features(self, trades: List[TradeRecord]) -> Tuple[np.ndarray, np.ndarray]:
        """准备仓位管理特征"""
        features = []
        targets = []

        for trade in trades:
            market = trade.market_context

            feature_vector = [
                market.get("volatility", 0),
                market.get("trend_strength", 0),
                market.get("liquidity_score", 0),
                trade.entry_indicators.get("rsi", 50),
                market.get("news_sentiment", 0)
            ]

            # 目标:最优仓位比例(基于实际盈亏推断)
            # 盈利大的交易,当时的仓位是"好"的
            # 这里简化:高盈利->建议大仓位,亏损->建议小仓位
            if trade.pnl_pct > 10:
                optimal_size = 0.8  # 80%
            elif trade.pnl_pct > 5:
                optimal_size = 0.5
            elif trade.pnl_pct > 0:
                optimal_size = 0.3
            else:
                optimal_size = 0.1

            features.append(feature_vector)
            targets.append(optimal_size)

        return np.array(features), np.array(targets)

    def _train_classification_model(self, X: np.ndarray, y: np.ndarray) -> Tuple[Any, Dict]:
        """训练分类模型"""
        try:
            from sklearn.model_selection import train_test_split
            from sklearn.ensemble import RandomForestClassifier
            from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

            # 划分训练集和验证集
            X_train, X_val, y_train, y_val = train_test_split(
                X, y, test_size=self.validation_split, random_state=42
            )

            # 训练随机森林模型
            model = RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                min_samples_split=5,
                random_state=42
            )
            model.fit(X_train, y_train)

            # 验证
            y_pred = model.predict(X_val)

            metrics = {
                "accuracy": accuracy_score(y_val, y_pred),
                "precision": precision_score(y_val, y_pred, zero_division=0),
                "recall": recall_score(y_val, y_pred, zero_division=0),
                "f1_score": f1_score(y_val, y_pred, zero_division=0),
                "train_samples": len(X_train),
                "val_samples": len(X_val)
            }

            return model, metrics

        except ImportError:
            logger.error("sklearn未安装,无法训练模型")
            # 回退到简单规则模型
            return None, {}

    def _train_regression_model(self, X: np.ndarray, y: np.ndarray) -> Tuple[Any, Dict]:
        """训练回归模型"""
        try:
            from sklearn.model_selection import train_test_split
            from sklearn.ensemble import RandomForestRegressor
            from sklearn.metrics import mean_squared_error, r2_score

            X_train, X_val, y_train, y_val = train_test_split(
                X, y, test_size=self.validation_split, random_state=42
            )

            model = RandomForestRegressor(
                n_estimators=100,
                max_depth=10,
                min_samples_split=5,
                random_state=42
            )
            model.fit(X_train, y_train)

            y_pred = model.predict(X_val)

            metrics = {
                "mse": mean_squared_error(y_val, y_pred),
                "r2_score": r2_score(y_val, y_pred),
                "train_samples": len(X_train),
                "val_samples": len(X_val)
            }

            return model, metrics

        except ImportError:
            logger.error("sklearn未安装,无法训练模型")
            return None, {}

    def _save_model(self, model_name: str, model_type: ModelType,
                   model: Any, metrics: Dict):
        """保存模型"""
        # 保存模型文件
        model_path = os.path.join(self.models_dir, f"{model_name}.pkl")
        with open(model_path, "wb") as f:
            pickle.dump(model, f)

        # 保存元数据
        self.model_metadata[model_name] = {
            "type": model_type.value,
            "created_at": datetime.now().isoformat(),
            "metrics": metrics,
            "path": model_path
        }

        self.models[model_name] = model

        # 记录到数据库
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO model_training_history
            (model_name, model_type, version, performance_metrics)
            VALUES (?, ?, ?, ?)
        """, (
            model_name,
            model_type.value,
            1,  # 版本号
            json.dumps(metrics)
        ))

        conn.commit()
        conn.close()

        logger.info(f"模型已保存: {model_name} at {model_path}")

    def _load_existing_models(self):
        """加载已有模型"""
        if not os.path.exists(self.models_dir):
            return

        for filename in os.listdir(self.models_dir):
            if filename.endswith(".pkl"):
                model_name = filename[:-4]
                model_path = os.path.join(self.models_dir, filename)

                try:
                    with open(model_path, "rb") as f:
                        model = pickle.load(f)
                        self.models[model_name] = model
                        logger.info(f"已加载模型: {model_name}")
                except Exception as e:
                    logger.error(f"加载模型失败 {model_name}: {e}")

    def predict_entry_signal(self, symbol: str, indicators: Dict,
                            market_context: Dict) -> Dict:
        """预测入场信号"""
        model_name = f"entry_signal_{symbol}"

        if model_name not in self.models:
            model_name = "entry_signal_all"  # 尝试通用模型

        if model_name not in self.models:
            return {
                "should_enter": False,
                "confidence": 0,
                "reason": "模型未训练"
            }

        model = self.models[model_name]

        # 准备特征
        feature_vector = np.array([[
            indicators.get("rsi", 50),
            indicators.get("macd", 0),
            indicators.get("sma_20", 0),
            indicators.get("sma_50", 0),
            indicators.get("bb_position", 0.5),
            indicators.get("atr", 0),
            market_context.get("trend_score", 0),
            market_context.get("volume_ratio", 1),
            market_context.get("volatility", 0)
        ]])

        try:
            prediction = model.predict(feature_vector)[0]
            confidence = model.predict_proba(feature_vector)[0][1] if hasattr(model, 'predict_proba') else 0.5

            return {
                "should_enter": bool(prediction),
                "confidence": float(confidence),
                "reason": f"模型预测(置信度{confidence:.2f})"
            }

        except Exception as e:
            logger.error(f"预测失败: {e}")
            return {
                "should_enter": False,
                "confidence": 0,
                "reason": "预测出错"
            }

    def predict_optimal_position_size(self, symbol: str, indicators: Dict,
                                     market_context: Dict) -> float:
        """预测最优仓位大小"""
        model_name = f"position_sizing_{symbol}"

        if model_name not in self.models:
            model_name = "position_sizing_all"

        if model_name not in self.models:
            return 0.2  # 默认20%

        model = self.models[model_name]

        feature_vector = np.array([[
            market_context.get("volatility", 0),
            market_context.get("trend_strength", 0),
            market_context.get("liquidity_score", 0),
            indicators.get("rsi", 50),
            market_context.get("news_sentiment", 0)
        ]])

        try:
            predicted_size = model.predict(feature_vector)[0]
            return max(0.05, min(1.0, predicted_size))  # 限制在5%-100%
        except Exception as e:
            logger.error(f"仓位预测失败: {e}")
            return 0.2

    def evaluate_strategy_performance(self, symbol: Optional[str] = None,
                                     days: int = 30) -> ModelPerformance:
        """评估策略性能"""
        start_date = (datetime.now() - timedelta(days=days)).isoformat()
        trades = self.get_trade_history(symbol=symbol, start_date=start_date)

        if not trades:
            return ModelPerformance(
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                win_rate=0,
                avg_win=0,
                avg_loss=0,
                profit_factor=0,
                sharpe_ratio=0,
                max_drawdown=0,
                total_pnl=0,
                total_pnl_pct=0
            )

        winning_trades = [t for t in trades if t.pnl > 0]
        losing_trades = [t for t in trades if t.pnl <= 0]

        win_rate = len(winning_trades) / len(trades) if trades else 0
        avg_win = np.mean([t.pnl for t in winning_trades]) if winning_trades else 0
        avg_loss = abs(np.mean([t.pnl for t in losing_trades])) if losing_trades else 0

        total_win = sum(t.pnl for t in winning_trades)
        total_loss = abs(sum(t.pnl for t in losing_trades))
        profit_factor = total_win / total_loss if total_loss > 0 else float('inf')

        total_pnl = sum(t.pnl for t in trades)
        total_pnl_pct = sum(t.pnl_pct for t in trades)

        # 计算最大回撤
        cumulative = np.cumsum([t.pnl for t in trades])
        running_max = np.maximum.accumulate(cumulative)
        drawdown = running_max - cumulative
        max_drawdown = np.max(drawdown) if len(drawdown) > 0 else 0

        # Sharpe比率(简化版)
        returns = [t.pnl_pct for t in trades]
        sharpe_ratio = (np.mean(returns) / np.std(returns) * np.sqrt(252)) if np.std(returns) > 0 else 0

        return ModelPerformance(
            total_trades=len(trades),
            winning_trades=len(winning_trades),
            losing_trades=len(losing_trades),
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            profit_factor=profit_factor,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown,
            total_pnl=total_pnl,
            total_pnl_pct=total_pnl_pct
        )

    def get_summary(self) -> Dict:
        """获取训练框架摘要"""
        total_trades = len(self.get_trade_history(limit=10000))

        return {
            "enabled": self.enabled,
            "total_trades_recorded": total_trades,
            "active_models": len(self.models),
            "model_list": list(self.models.keys()),
            "min_trades_for_training": self.min_trades_for_training,
            "models_ready_for_training": total_trades >= self.min_trades_for_training
        }
