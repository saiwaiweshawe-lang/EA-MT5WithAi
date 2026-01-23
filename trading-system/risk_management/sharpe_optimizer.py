# Sharpe Ratio Optimization Module
# Calculate and optimize Sharpe ratio, adjust positions in high Sharpe, low volatility environments

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import logging
import numpy as np

logger = logging.getLogger(__name__)


class SharpeRegime(Enum):
    """Sharpe ratio regime"""
    EXCELLENT = "excellent"      # Sharpe > 2.0
    GOOD = "good"                   # Sharpe > 1.0
    NORMAL = "normal"                # Sharpe > 0.5
    POOR = "poor"                  # Sharpe > 0
    NEGATIVE = "negative"            # Sharpe <= 0


@dataclass
class SharpeMetrics:
    """Sharpe ratio metrics"""
    sharpe_ratio: float
    sharpe_annualized: float
    sortino_ratio: float
    volatility: float
    returns_mean: float
    returns_std: float
    max_drawdown: float
    regime: SharpeRegime


@dataclass
class PositionAdjustment:
    """Position adjustment based on Sharpe ratio"""
    base_size: float
    adjusted_size: float
    multiplier: float              # Adjustment multiplier
    reason: str
    sharpe_metrics: SharpeMetrics
    confidence_adjustment: float


class SharpeOptimizer:
    """Sharpe ratio optimizer"""

    def __init__(self, config: Dict = None):
        self.config = config or {}

        # Calculation window
        self.sharpe_window = self.config.get("sharpe_window", 30)       # 30 days
        self.min_trades_for_sharpe = self.config.get("min_trades", 10)

        # Risk-free rate (annual)
        self.risk_free_rate = self.config.get("risk_free_rate", 0.02)   # 2% annual

        # Regime thresholds
        self.sharpe_threshold_excellent = self.config.get("sharpe_threshold_excellent", 2.0)
        self.sharpe_threshold_good = self.config.get("sharpe_threshold_good", 1.0)
        self.sharpe_threshold_normal = self.config.get("sharpe_threshold_normal", 0.5)

        # Volatility adjustment thresholds
        self.low_volatility_threshold = self.config.get("low_volatility_threshold", 0.01)  # 1% daily
        self.high_volatility_threshold = self.config.get("high_volatility_threshold", 0.03)   # 3% daily

        # Position adjustment multipliers
        self.excellent_sharpe_multiplier = self.config.get("excellent_sharpe_multiplier", 1.3)
        self.good_sharpe_multiplier = self.config.get("good_sharpe_multiplier", 1.1)
        self.low_volatility_multiplier = self.config.get("low_volatility_multiplier", 1.2)
        self.high_volatility_multiplier = self.config.get("high_volatility_multiplier", 0.8)

        # Trade history
        self.trade_history: List[Dict] = []

        # Returns history (for Sharpe calculation)
        self.returns_history: List[float] = []

        # Equity curve
        self.equity_history: List[Tuple[datetime, float]] = []

    def record_trade(self, pnl: float, timestamp: Optional[datetime] = None,
                  symbol: str = "", entry_price: float = 0.0,
                  exit_price: float = 0.0, size: float = 0.0):
        """
        Record a trade result

        Args:
            pnl: Trade PnL
            timestamp: Trade timestamp
            symbol: Trading symbol
            entry_price: Entry price
            exit_price: Exit price
            size: Position size
        """
        trade = {
            "timestamp": timestamp or datetime.now(),
            "symbol": symbol,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "size": size,
            "pnl": pnl,
            "pnl_pct": pnl / (entry_price * size) if size > 0 else 0
        }

        self.trade_history.append(trade)

        # Calculate return
        return_value = 1.0 + pnl / (entry_price * size) if size > 0 else 1.0
        self.returns_history.append(return_value - 1.0)  # Convert to return

        # Maintain history length
        max_history = self.sharpe_window
        if len(self.returns_history) > max_history:
            self.returns_history.pop(0)

        logger.info(f"交易记录: {symbol} PnL={pnl:+.2f} Return={return_value-1:.2%}")

    def update_equity(self, equity: float, timestamp: Optional[datetime] = None):
        """
        Update equity curve for drawdown calculation

        Args:
            equity: Current equity
            timestamp: Timestamp
        """
        self.equity_history.append((timestamp or datetime.now(), equity))

        # Maintain reasonable history
        max_equity_history = self.sharpe_window * 10
        if len(self.equity_history) > max_equity_history:
            self.equity_history.pop(0)

    def calculate_sharpe_metrics(self) -> SharpeMetrics:
        """
        Calculate Sharpe ratio and related metrics

        Returns:
            SharpeMetrics
        """
        if len(self.returns_history) < self.min_trades_for_sharpe:
            return SharpeMetrics(
                sharpe_ratio=0.0,
                sharpe_annualized=0.0,
                sortino_ratio=0.0,
                volatility=0.0,
                returns_mean=0.0,
                returns_std=0.0,
                max_drawdown=0.0,
                regime=SharpeRegime.NORMAL
            )

        returns = np.array(self.returns_history)

        # Calculate daily statistics
        returns_mean = np.mean(returns)
        returns_std = np.std(returns)
        volatility = returns_std * np.sqrt(252)  # Annualized volatility

        # Calculate Sharpe ratio
        excess_returns = returns_mean - (self.risk_free_rate / 252)  # Daily risk-free rate

        if returns_std == 0:
            sharpe_daily = 0.0
        else:
            sharpe_daily = excess_returns / returns_std

        sharpe_annualized = sharpe_daily * np.sqrt(252)

        # Calculate Sortino ratio (downside deviation only)
        downside_returns = returns[returns < 0]
        if len(downside_returns) > 0:
            downside_std = np.std(downside_returns)
            if downside_std > 0:
                sortino_ratio = excess_returns / downside_std
            else:
                sortino_ratio = 0.0
        else:
            sortino_ratio = excess_returns / returns_std if returns_std > 0 else 0.0

        # Calculate max drawdown
        max_drawdown = self._calculate_max_drawdown()

        # Classify regime
        regime = self._classify_regime(sharpe_annualized)

        return SharpeMetrics(
            sharpe_ratio=sharpe_daily,
            sharpe_annualized=sharpe_annualized,
            sortino_ratio=sortino_ratio,
            volatility=volatility,
            returns_mean=returns_mean,
            returns_std=returns_std,
            max_drawdown=max_drawdown,
            regime=regime
        )

    def _calculate_max_drawdown(self) -> float:
        """Calculate maximum drawdown from equity curve"""
        if len(self.equity_history) < 2:
            return 0.0

        peak = self.equity_history[0][1]
        max_dd = 0.0

        for _, equity in self.equity_history[1:]:
            if equity > peak:
                peak = equity

            dd = (peak - equity) / peak if peak > 0 else 0
            max_dd = max(max_dd, dd)

        return max_dd

    def _classify_regime(self, sharpe_annualized: float) -> SharpeRegime:
        """Classify Sharpe ratio regime"""
        if sharpe_annualized >= self.sharpe_threshold_excellent:
            return SharpeRegime.EXCELLENT
        elif sharpe_annualized >= self.sharpe_threshold_good:
            return SharpeRegime.GOOD
        elif sharpe_annualized >= self.sharpe_threshold_normal:
            return SharpeRegime.NORMAL
        elif sharpe_annualized > 0:
            return SharpeRegime.POOR
        else:
            return SharpeRegime.NEGATIVE

    def get_position_adjustment(self, base_size: float) -> PositionAdjustment:
        """
        Get position size adjustment based on Sharpe ratio

        Args:
            base_size: Base position size

        Returns:
            PositionAdjustment
        """
        metrics = self.calculate_sharpe_metrics()

        # Determine adjustment multiplier
        multiplier = 1.0
        reason = "正常交易，基于基础仓位"
        confidence_adjustment = 1.0

        # Sharpe ratio adjustment
        if metrics.regime == SharpeRegime.EXCELLENT:
            multiplier = self.excellent_sharpe_multiplier
            confidence_adjustment = 1.2
            reason = f"夏普比率优秀({metrics.sharpe_annualized:.2f})，增加仓位至{multiplier:.0%}"
        elif metrics.regime == SharpeRegime.GOOD:
            multiplier = self.good_sharpe_multiplier
            confidence_adjustment = 1.1
            reason = f"夏普比率良好({metrics.sharpe_annualized:.2f})，小幅增加仓位至{multiplier:.0%}"
        elif metrics.regime == SharpeRegime.POOR:
            multiplier = 0.8
            confidence_adjustment = 0.7
            reason = f"夏普比率较差({metrics.sharpe_annualized:.2f})，减小仓位至{multiplier:.0%}"
        elif metrics.regime == SharpeRegime.NEGATIVE:
            multiplier = 0.5
            confidence_adjustment = 0.5
            reason = f"夏普比率为负({metrics.sharpe_annualized:.2f})，大幅减小仓位至{multiplier:.0%}"

        # Volatility adjustment (combined with Sharpe)
        daily_volatility = metrics.volatility / np.sqrt(252)

        if daily_volatility < self.low_volatility_threshold:
            # Low volatility with good Sharpe - increase position
            if metrics.regime in [SharpeRegime.EXCELLENT, SharpeRegime.GOOD]:
                multiplier *= self.low_volatility_multiplier
                reason = f"低波动优秀夏普({metrics.sharpe_annualized:.2f})，增加仓位至{multiplier:.0%}"
        elif daily_volatility > self.high_volatility_threshold:
            # High volatility - reduce position
            multiplier *= self.high_volatility_multiplier
            confidence_adjustment *= 0.9
            reason = f"高波动环境({metrics.volatility:.2%})，减小仓位至{multiplier:.0%}"

        # Limit multiplier range
        multiplier = max(0.3, min(1.5, multiplier))

        adjusted_size = base_size * multiplier

        return PositionAdjustment(
            base_size=base_size,
            adjusted_size=adjusted_size,
            multiplier=multiplier,
            reason=reason,
            sharpe_metrics=metrics,
            confidence_adjustment=confidence_adjustment
        )

    def get_sharpe_summary(self) -> Dict:
        """Get Sharpe ratio analysis summary"""
        metrics = self.calculate_sharpe_metrics()

        return {
            "trades_count": len(self.trade_history),
            "returns_count": len(self.returns_history),
            "sharpe_daily": metrics.sharpe_ratio,
            "sharpe_annualized": metrics.sharpe_annualized,
            "sortino_ratio": metrics.sortino_ratio,
            "volatility_annual": metrics.volatility,
            "returns_mean": metrics.returns_mean,
            "returns_std": metrics.returns_std,
            "max_drawdown": metrics.max_drawdown,
            "regime": metrics.regime.value,
            "risk_free_rate": self.risk_free_rate
        }


def create_sharpe_optimizer(config: Dict = None) -> SharpeOptimizer:
    """Create Sharpe ratio optimizer"""
    return SharpeOptimizer(config)


if __name__ == "__main__":
    # Test code
    optimizer = SharpeOptimizer()

    print("\n=== Testing Sharpe Ratio Optimization ===")

    import random
    random.seed(42)

    # Simulate trading with varying returns
    base_equity = 10000.0
    equity = base_equity

    print("\nSimulating trading (30 days):")

    # Generate returns with positive Sharpe (good performance)
    returns = []
    for i in range(30):
        # Mix of small losses and larger wins for good Sharpe
        if random.random() < 0.3:
            ret = random.uniform(-0.02, -0.005)  # Small loss
        else:
            ret = random.uniform(0.01, 0.04)     # Larger win

        returns.append(ret)
        equity *= (1 + ret)

        # Record as trade
        pnl = equity - base_equity
        base_equity = equity
        optimizer.record_trade(pnl)
        optimizer.update_equity(equity)

        print(f"  Day {i+1}: Return={ret:+.2%}, Equity={equity:.2f}")

    # Calculate Sharpe metrics
    print("\nSharpe Metrics:")
    metrics = optimizer.calculate_sharpe_metrics()
    print(f"  Sharpe (daily): {metrics.sharpe_ratio:.3f}")
    print(f"  Sharpe (annual): {metrics.sharpe_annualized:.3f}")
    print(f"  Sortino Ratio: {metrics.sortino_ratio:.3f}")
    print(f"  Volatility (annual): {metrics.volatility:.3f}")
    print(f"  Max Drawdown: {metrics.max_drawdown:.2%}")
    print(f"  Regime: {metrics.regime.value}")

    # Test position adjustment
    base_size = 0.1
    adjustment = optimizer.get_position_adjustment(base_size)

    print("\nPosition Adjustment:")
    print(f"  Base size: {base_size}")
    print(f"  Adjusted size: {adjustment.adjusted_size:.4f}")
    print(f"  Multiplier: {adjustment.multiplier:.2f}")
    print(f"  Reason: {adjustment.reason}")
    print(f"  Confidence adjustment: {adjustment.confidence_adjustment:.2f}")
