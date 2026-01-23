# VaR (Value at Risk) Dynamic Adjustment Module
# Calculate VaR and dynamically adjust positions based on extreme risk

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
import logging
import numpy as np

logger = logging.getLogger(__name__)


class VaRMethod(Enum):
    """VaR calculation methods"""
    HISTORICAL = "historical"       # Historical simulation
    PARAMETRIC = "parametric"       # Normal distribution
    MONTE_CARLO = "monte_carlo"    # Monte Carlo simulation
    EWMA = "ewma"                  # Exponentially Weighted Moving Average


@dataclass
class VaRResult:
    """VaR calculation result"""
    var_95: float              # VaR at 95% confidence
    var_99: float              # VaR at 99% confidence
    var_99_9: float            # VaR at 99.9% confidence
    expected_shortfall: float   # Expected shortfall (ES)
    volatility: float          # Current volatility
    method: VaRMethod
    confidence_level: float    # Confidence level used
    max_loss_estimate: float  # Estimated maximum loss


@dataclass
class PositionRiskAdjustment:
    """Position size adjustment based on VaR"""
    base_size: float
    adjusted_size: float
    adjustment_multiplier: float    # 0-1
    var_limit_pct: float           # Maximum allowed loss percentage
    current_risk_pct: float        # Current risk as percentage of VaR
    risk_level: str               # low/medium/high/extreme
    reason: str


class VaRManager:
    """Value at Risk manager"""

    def __init__(self, config: Dict = None):
        self.config = config or {}

        # VaR parameters
        self.var_method = VaRMethod(self.config.get("var_method", "historical"))
        self.confidence_level = self.config.get("confidence_level", 0.95)  # 95% confidence
        self.lookback_period = self.config.get("lookback_period", 100)  # Lookback for historical VaR
        self.ewma_lambda = self.config.get("ewma_lambda", 0.94)  # Decay factor

        # Risk limits
        self.max_var_pct = self.config.get("max_var_pct", 0.02)  # 2% of equity at most
        self.warning_var_pct = self.config.get("warning_var_pct", 0.015)  # 1.5% warning
        self.emergency_var_pct = self.config.get("emergency_var_pct", 0.04)  # 4% emergency

        # Position adjustment thresholds
        self.risk_level_thresholds = self.config.get("risk_level_thresholds", {
            "low": 0.5,           # Use up to 50% of max
            "medium": 0.7,        # Use up to 70% of max
            "high": 0.9,          # Use up to 90% of max
            "extreme": 1.0         # Use up to 100% of max
        })

        # PnL history for VaR calculation
        self.pnl_history: List[float] = []

        # EWMA volatility tracking
        self.ewma_variance = None
        self.ewma_volatility = None

        # Position risk tracking
        self.current_positions: Dict[str, Dict] = {}

    def record_pnl(self, pnl: float):
        """
        Record PnL for VaR calculation

        Args:
            pnl: Trade profit/loss (percentage of equity)
        """
        self.pnl_history.append(pnl)

        # Maintain history length
        if len(self.pnl_history) > self.lookback_period:
            self.pnl_history.pop(0)

        logger.debug(f"记录PnL: {pnl:+.4f}, 历史长度: {len(self.pnl_history)}")

    def calculate_var(self, confidence_level: Optional[float] = None) -> VaRResult:
        """
        Calculate Value at Risk

        Args:
            confidence_level: Confidence level (default from config)

        Returns:
            VaRResult
        """
        if confidence_level is None:
            confidence_level = self.confidence_level

        if len(self.pnl_history) < 10:
            # Not enough data, use default
            return VaRResult(
                var_95=self.max_var_pct * 0.5,
                var_99=self.max_var_pct * 0.8,
                var_99_9=self.max_var_pct,
                expected_shortfall=self.max_var_pct * 0.7,
                volatility=0.02,
                method=VaRMethod.HISTORICAL,
                confidence_level=confidence_level,
                max_loss_estimate=self.max_var_pct
            )

        # Calculate based on method
        if self.var_method == VaRMethod.HISTORICAL:
            return self._historical_var(confidence_level)
        elif self.var_method == VaRMethod.PARAMETRIC:
            return self._parametric_var(confidence_level)
        elif self.var_method == VaRMethod.EWMA:
            return self._ewma_var(confidence_level)
        elif self.var_method == VaRMethod.MONTE_CARLO:
            return self._monte_carlo_var(confidence_level)
        else:
            # Default to historical
            return self._historical_var(confidence_level)

    def _historical_var(self, confidence_level: float) -> VaRResult:
        """Historical VaR using sorted PnLs"""
        pnl_array = np.array(self.pnl_history)

        # Calculate volatility
        volatility = np.std(pnl_array)

        # Sort returns and find quantiles
        sorted_pnl = np.sort(pnl_array)
        n = len(sorted_pnl)

        # VaR at different confidence levels
        var_95 = sorted_pnl[int(n * (1 - confidence_level))] if n > 0 else 0
        var_99 = sorted_pnl[int(n * 0.01)] if n > 0 else 0
        var_99_9 = sorted_pnl[0] if n > 0 else 0  # Minimum PnL

        # Expected Shortfall (average of losses beyond VaR)
        losses = sorted_pnl[sorted_pnl < 0]
        if len(losses) > 0 and var_95 < 0:
            expected_shortfall = np.mean(losses[losses <= var_95])
        else:
            expected_shortfall = 0.0

        return VaRResult(
            var_95=abs(var_95),
            var_99=abs(var_99),
            var_99_9=abs(var_99_9),
            expected_shortfall=abs(expected_shortfall),
            volatility=volatility,
            method=VaRMethod.HISTORICAL,
            confidence_level=confidence_level,
            max_loss_estimate=abs(var_99_9)
        )

    def _parametric_var(self, confidence_level: float) -> VaRResult:
        """Parametric VaR assuming normal distribution"""
        pnl_array = np.array(self.pnl_history)

        # Calculate mean and standard deviation
        mean_return = np.mean(pnl_array)
        std = np.std(pnl_array)

        # Z-score for confidence level
        from scipy.stats import norm
        z_score = norm.ppf(confidence_level)

        # VaR = mean - z * std (one-sided for losses)
        var_95 = mean_return - z_score * std

        # 99% and 99.9%
        z_99 = norm.ppf(0.99)
        z_99_9 = norm.ppf(0.999)

        var_99 = mean_return - z_99 * std
        var_99_9 = mean_return - z_99_9 * std

        # Expected shortfall
        from scipy.stats import truncnorm
        expected_shortfall = mean_return - (norm.pdf(z_score) / (1 - confidence_level)) * std

        return VaRResult(
            var_95=abs(var_95),
            var_99=abs(var_99),
            var_99_9=abs(var_99_9),
            expected_shortfall=abs(expected_shortfall),
            volatility=std,
            method=VaRMethod.PARAMETRIC,
            confidence_level=confidence_level,
            max_loss_estimate=abs(var_99_9)
        )

    def _ewma_var(self, confidence_level: float) -> VaRResult:
        """EWMA VaR with volatility smoothing"""
        pnl_array = np.array(self.pnl_history)

        # Initialize EWMA
        if self.ewma_variance is None:
            self.ewma_variance = np.var(pnl_array)
        else:
            # Update EWMA of variance
            new_variance = np.var(pnl_array[-1:]) if len(pnl_array) > 1 else 0
            self.ewma_variance = self.ewma_lambda * self.ewma_variance + (1 - self.ewma_lambda) * new_variance

        ewma_volatility = np.sqrt(self.ewma_variance)

        # Calculate VaR using EWMA volatility
        from scipy.stats import norm
        z_score = norm.ppf(confidence_level)

        var_95 = -z_score * ewma_volatility

        # 99% and 99.9%
        z_99 = norm.ppf(0.99)
        z_99_9 = norm.ppf(0.999)

        var_99 = -z_99 * ewma_volatility
        var_99_9 = -z_99_9 * ewma_volatility

        # Expected shortfall
        expected_shortfall = (ewma_volatility * norm.pdf(z_score) / (1 - confidence_level))

        return VaRResult(
            var_95=abs(var_95),
            var_99=abs(var_99),
            var_99_9=abs(var_99_9),
            expected_shortfall=abs(expected_shortfall),
            volatility=ewma_volatility,
            method=VaRMethod.EWMA,
            confidence_level=confidence_level,
            max_loss_estimate=abs(var_99_9)
        )

    def _monte_carlo_var(self, confidence_level: float, simulations: int = 10000) -> VaRResult:
        """Monte Carlo VaR simulation"""
        pnl_array = np.array(self.pnl_history)

        if len(pnl_array) < 20:
            return self._historical_var(confidence_level)

        # Fit distribution to returns
        mean_return = np.mean(pnl_array)
        std_return = np.std(pnl_array)

        # Monte Carlo simulation
        simulated_returns = np.random.normal(mean_return, std_return, simulations)

        # Sort and get quantiles
        sorted_sim = np.sort(simulated_returns)
        n = len(sorted_sim)

        var_95 = sorted_sim[int(n * (1 - confidence_level))]
        var_99 = sorted_sim[int(n * 0.01)]
        var_99_9 = sorted_sim[0]

        # Expected shortfall
        losses = sorted_sim[sorted_sim < 0]
        if len(losses) > 0 and var_95 < 0:
            expected_shortfall = np.mean(losses[losses <= var_95])
        else:
            expected_shortfall = 0.0

        return VaRResult(
            var_95=abs(var_95),
            var_99=abs(var_99),
            var_99_9=abs(var_99_9),
            expected_shortfall=abs(expected_shortfall),
            volatility=std_return,
            method=VaRMethod.MONTE_CARLO,
            confidence_level=confidence_level,
            max_loss_estimate=abs(var_99_9)
        )

    def get_position_adjustment(self, base_size: float, equity: float) -> PositionRiskAdjustment:
        """
        Get position size adjustment based on VaR

        Args:
            base_size: Base position size
            equity: Account equity

        Returns:
            PositionRiskAdjustment
        """
        var_result = self.calculate_var()

        # Calculate current risk as percentage of VaR limit
        var_limit = equity * self.max_var_pct
        current_risk_pct = var_result.var_95 / var_limit if var_limit > 0 else 0

        # Determine risk level
        risk_level = self._determine_risk_level(var_result.var_95, var_limit)

        # Calculate adjustment multiplier
        multiplier = self.risk_level_thresholds.get(risk_level, 1.0)

        adjusted_size = base_size * multiplier

        return PositionRiskAdjustment(
            base_size=base_size,
            adjusted_size=adjusted_size,
            adjustment_multiplier=multiplier,
            var_limit_pct=self.max_var_pct,
            current_risk_pct=current_risk_pct,
            risk_level=risk_level,
            reason=f"VaR调整: {var_result.var_95:.2%} (极限{self.max_var_pct:.0%})，风险等级={risk_level}，系数={multiplier:.2f}"
        )

    def _determine_risk_level(self, var_value: float, var_limit: float) -> str:
        """Determine risk level based on VaR"""
        if var_limit == 0:
            return "low"

        risk_pct = var_value / var_limit

        if risk_pct < 0.5:
            return "low"
        elif risk_pct < 0.7:
            return "medium"
        elif risk_pct < 0.9:
            return "high"
        else:
            return "extreme"

    def should_trade(self, equity: float) -> Tuple[bool, str, float]:
        """
        Check if trading is allowed based on VaR constraints

        Args:
            equity: Account equity

        Returns:
            (should_trade: bool, reason: str, max_position_size_pct: float)
        """
        var_result = self.calculate_var()
        var_limit = equity * self.max_var_pct
        emergency_limit = equity * self.emergency_var_pct

        # Check emergency threshold
        if var_result.var_95 >= emergency_limit:
            logger.warning(f"VaR触发紧急停止: {var_result.var_95:.2%} >= {self.emergency_var_pct:.0%}")
            return False, f"VaR触发紧急停止：极端风险{var_result.var_95:.2%}超过{self.emergency_var_pct:.0%}", 0.0

        # Check max threshold (reduce size)
        if var_result.var_95 >= var_limit:
            logger.warning(f"VaR达到最大限制: {var_result.var_95:.2%} >= {self.max_var_pct:.0%}")
            return True, f"VaR达到最大限制，需减小仓位", 0.5

        return True, "VaR在安全范围内", 1.0

    def get_var_summary(self, equity: float = 10000.0) -> Dict:
        """Get VaR analysis summary"""
        var_result = self.calculate_var()

        return {
            "method": var_result.method.value,
            "confidence_level": var_result.confidence_level,
            "var_95_pct": var_result.var_95 * 100,
            "var_99_pct": var_result.var_99 * 100,
            "var_99_9_pct": var_result.var_99_9 * 100,
            "expected_shortfall_pct": var_result.expected_shortfall * 100,
            "volatility_pct": var_result.volatility * 100,
            "max_limit_pct": self.max_var_pct * 100,
            "current_limit_equity": equity * self.max_var_pct,
            "is_emergency": var_result.var_95 >= (equity * self.emergency_var_pct)
        }


def create_var_manager(config: Dict = None) -> VaRManager:
    """Create VaR manager"""
    return VaRManager(config)


if __name__ == "__main__":
    # Test code
    manager = VaRManager()

    print("\n=== Testing VaR Dynamic Adjustment ===")

    import random
    random.seed(42)

    # Simulate PnL history
    base_equity = 10000.0
    equity = base_equity

    # Generate 100 PnLs (mix of small losses and gains for moderate Sharpe)
    pnls = []
    for i in range(100):
        if random.random() < 0.6:
            pnl = random.uniform(-0.015, -0.002) * equity  # Loss 0.2%-0.5%
        else:
            pnl = random.uniform(0.005, 0.02) * equity   # Gain 0.5%-2%
        pnls.append(pnl)
        equity += pnl

    # Record PnLs
    for pnl in pnls:
        manager.record_pnl(pnl / base_equity)  # Convert to percentage

    print(f"\nPnL History: {len(pnls)} trades")
    print(f"  Mean: {np.mean(pnls):.2f}, Std: {np.std(pnls):.2f}")

    # Test VaR calculation
    print("\nVaR Calculation:")
    for method in [VaRMethod.HISTORICAL, VaRMethod.PARAMETRIC, VaRMethod.EWMA]:
        manager.var_method = method
        var = manager.calculate_var(0.95)
        print(f"  {method.value}:")
        print(f"    VaR 95%: {var.var_95:.2%}")
        print(f"    VaR 99%: {var.var_99:.2%}")
        print(f"    Expected Shortfall: {var.expected_shortfall:.2%}")
        print(f"    Volatility: {var.volatility:.2%}")

    # Test position adjustment
    print("\nPosition Adjustment:")
    adjustment = manager.get_position_adjustment(0.1, base_equity)
    print(f"  Base size: {adjustment.base_size}")
    print(f"  Adjusted size: {adjustment.adjusted_size:.4f}")
    print(f"  Multiplier: {adjustment.adjustment_multiplier:.2f}")
    print(f"  Reason: {adjustment.reason}")

    # Test trading decision
    should_trade, reason, max_size = manager.should_trade(base_equity)
    print(f"\nTrading Decision:")
    print(f"  Should trade: {should_trade}")
    print(f"  Reason: {reason}")
    print(f"  Max position size: {max_size:.0%}")
