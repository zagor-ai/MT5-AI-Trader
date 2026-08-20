"""Combine validation dimensions into a conservative robustness assessment."""
from dataclasses import dataclass
from typing import Any, Dict


@dataclass(frozen=True)
class RobustnessConfig:
    min_oos_pass_rate: float = 0.60
    min_sensitivity_pass_rate: float = 0.60
    max_drawdown_r_limit: float = 10.0
    min_monte_carlo_p05_r: float = -5.0


class RobustnessEngine:
    def __init__(self, config: RobustnessConfig | None = None):
        self.config = config or RobustnessConfig()

    def evaluate(
        self,
        oos: Dict[str, Any],
        sensitivity: Dict[str, Any],
        monte_carlo: Dict[str, Any],
        max_drawdown_r: float,
    ) -> Dict[str, Any]:
        oos_pass = float(oos.get("pass_rate", 0.0))
        sensitivity_pass = float(sensitivity.get("pass_rate", 0.0))
        mc_p05 = float(monte_carlo.get("p05_net_r", 0.0))
        dd_ok = float(max_drawdown_r) <= self.config.max_drawdown_r_limit
        checks = {
            "oos_pass_rate": oos_pass >= self.config.min_oos_pass_rate,
            "sensitivity_pass_rate": sensitivity_pass >= self.config.min_sensitivity_pass_rate,
            "monte_carlo_p05": mc_p05 >= self.config.min_monte_carlo_p05_r,
            "drawdown_limit": dd_ok,
        }
        passed = sum(checks.values())
        score = 100.0 * passed / len(checks)
        return {
            "robustness_score": score,
            "robust": passed == len(checks),
            "checks": checks,
            "oos_pass_rate": oos_pass,
            "sensitivity_pass_rate": sensitivity_pass,
            "monte_carlo_p05_net_r": mc_p05,
            "max_drawdown_r": float(max_drawdown_r),
        }
