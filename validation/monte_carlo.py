"""Monte Carlo trade-sequence simulation for robustness research."""
from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np


@dataclass(frozen=True)
class MonteCarloConfig:
    simulations: int = 2000
    seed: Optional[int] = 42
    confidence_low: float = 0.05
    confidence_high: float = 0.95


class MonteCarloSimulator:
    def __init__(self, config: Optional[MonteCarloConfig] = None):
        self.config = config or MonteCarloConfig()
        self.rng = np.random.default_rng(self.config.seed)

    def simulate_r_multiples(self, r_multiples: List[float]) -> Dict[str, float]:
        values = np.asarray(r_multiples, dtype=float)
        values = values[np.isfinite(values)]
        if values.size == 0:
            return {"simulations": 0, "median_net_r": 0.0, "p05_net_r": 0.0, "p95_net_r": 0.0, "p05_max_drawdown_r": 0.0}
        n = max(1, int(self.config.simulations))
        totals = np.empty(n, dtype=float)
        max_dd = np.empty(n, dtype=float)
        for i in range(n):
            sample = self.rng.choice(values, size=values.size, replace=True)
            curve = np.cumsum(sample)
            peak = np.maximum.accumulate(np.concatenate(([0.0], curve)))
            dd = peak[1:] - curve
            totals[i] = curve[-1]
            max_dd[i] = float(np.max(dd)) if dd.size else 0.0
        return {
            "simulations": n,
            "median_net_r": float(np.quantile(totals, 0.50)),
            "p05_net_r": float(np.quantile(totals, self.config.confidence_low)),
            "p95_net_r": float(np.quantile(totals, self.config.confidence_high)),
            "p05_max_drawdown_r": float(np.quantile(max_dd, self.config.confidence_low)),
            "median_max_drawdown_r": float(np.quantile(max_dd, 0.50)),
        }
