"""Monte Carlo robustness analysis for completed strategy trades.

Research-only: no MT5 trading or order API is used.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Sequence
import numpy as np

@dataclass(frozen=True)
class MonteCarloConfig:
    simulations: int = 2000
    seed: Optional[int] = 42
    confidence_low: float = 0.05
    confidence_high: float = 0.95
    risk_fraction: float = 0.01
    ruin_equity_fraction: float = 0.50

class MonteCarloSimulator:
    def __init__(self, config: Optional[MonteCarloConfig] = None):
        self.config = config or MonteCarloConfig()
        self.rng = np.random.default_rng(self.config.seed)

    @staticmethod
    def _extract_r_multiples(trades: Sequence[Any]) -> np.ndarray:
        values: List[float] = []
        for trade in trades:
            value = trade.get("r_multiple", trade.get("r", 0.0)) if isinstance(trade, dict) else getattr(trade, "r_multiple", getattr(trade, "r", 0.0))
            try:
                value = float(value)
                if np.isfinite(value): values.append(value)
            except (TypeError, ValueError):
                pass
        return np.asarray(values, dtype=float)

    def simulate_r_multiples(self, r_multiples: Sequence[float]) -> Dict[str, float]:
        values = np.asarray(r_multiples, dtype=float); values = values[np.isfinite(values)]
        if values.size < 2:
            raise ValueError("Monte Carlo requires at least 2 valid R-multiple observations")
        n = max(1, int(self.config.simulations)); totals = np.empty(n); max_dd = np.empty(n); final_equity = np.empty(n); ruin = np.zeros(n, dtype=bool)
        for i in range(n):
            sample = self.rng.choice(values, size=values.size, replace=True)
            curve_r = np.cumsum(sample); peak_r = np.maximum.accumulate(np.concatenate(([0.0], curve_r))); dd_r = peak_r[1:] - curve_r
            totals[i] = curve_r[-1]; max_dd[i] = float(np.max(dd_r)) if dd_r.size else 0.0
            equity = 1.0; peak = 1.0
            for r in sample:
                equity *= max(0.0, 1.0 + self.config.risk_fraction * float(r)); peak = max(peak, equity)
                if equity <= self.config.ruin_equity_fraction: ruin[i] = True
            final_equity[i] = equity
        q = lambda a, p: float(np.quantile(a, p))
        return {
            "simulations": float(n), "observed_net_r": float(np.sum(values)),
            "median_net_r": q(totals, .50), "p05_net_r": q(totals, self.config.confidence_low), "p95_net_r": q(totals, self.config.confidence_high),
            "median_max_drawdown_r": q(max_dd, .50), "p95_max_drawdown_r": q(max_dd, .95),
            "probability_positive": float(np.mean(totals > 0)), "probability_ruin": float(np.mean(ruin)),
            "median_final_equity": q(final_equity, .50), "p05_final_equity": q(final_equity, self.config.confidence_low), "p95_final_equity": q(final_equity, self.config.confidence_high)
        }

    def simulate_trades(self, trades: Sequence[Any]) -> Dict[str, float]:
        return self.simulate_r_multiples(self._extract_r_multiples(trades))
