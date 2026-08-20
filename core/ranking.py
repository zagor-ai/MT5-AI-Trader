"""Research ranking independent from GUI and broker connectivity."""
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List


@dataclass(frozen=True)
class RankingWeights:
    net_r: float = 0.25
    profit_factor: float = 0.20
    expectancy: float = 0.15
    win_rate: float = 0.10
    stability: float = 0.15
    drawdown: float = 0.15


class StrategyRanker:
    def __init__(self, weights: RankingWeights | None = None):
        self.weights = weights or RankingWeights()

    @staticmethod
    def _clip(value: float, low: float = 0.0, high: float = 1.0) -> float:
        return max(low, min(high, float(value)))

    def score(self, metrics: Dict[str, Any]) -> float:
        net_r = self._clip(float(metrics.get("net_r", 0.0)) / 20.0)
        pf = self._clip((float(metrics.get("profit_factor", 0.0)) - 1.0) / 2.0)
        exp = self._clip((float(metrics.get("expectancy", 0.0)) + 0.5) / 1.5)
        wr = self._clip(float(metrics.get("win_rate", 0.0)) / 100.0)
        stability = self._clip(float(metrics.get("stability_score", 0.0)) / 100.0)
        dd = self._clip(1.0 - float(metrics.get("max_drawdown_pct", metrics.get("max_drawdown", 100.0))) / 50.0)
        w = self.weights
        return 100.0 * (
            w.net_r * net_r
            + w.profit_factor * pf
            + w.expectancy * exp
            + w.win_rate * wr
            + w.stability * stability
            + w.drawdown * dd
        )

    def rank(self, results: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
        ranked = []
        for item in results:
            row = dict(item)
            row["ranking_score"] = round(self.score(row), 4)
            ranked.append(row)
        return sorted(ranked, key=lambda x: x["ranking_score"], reverse=True)
