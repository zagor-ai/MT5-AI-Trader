"""Walk-forward validation utilities for chronological market research.

The optimizer callback is only given the in-sample window. The resulting
selection is then evaluated on the immediately following out-of-sample window.
No future data is exposed to the optimizer.
"""
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

import pandas as pd


@dataclass(frozen=True)
class WalkForwardConfig:
    train_bars: int = 5000
    test_bars: int = 1000
    step_bars: Optional[int] = None
    minimum_test_trades: int = 20


class WalkForwardValidator:
    def __init__(self, config: Optional[WalkForwardConfig] = None):
        self.config = config or WalkForwardConfig()

    def windows(self, data: pd.DataFrame) -> List[Dict[str, Any]]:
        cfg = self.config
        step = cfg.step_bars or cfg.test_bars
        if cfg.train_bars <= 0 or cfg.test_bars <= 0 or step <= 0:
            raise ValueError("train_bars, test_bars and step_bars must be positive")
        output = []
        start = 0
        n = len(data)
        while start + cfg.train_bars + cfg.test_bars <= n:
            train_end = start + cfg.train_bars
            test_end = train_end + cfg.test_bars
            output.append({
                "train_start": start,
                "train_end": train_end,
                "test_start": train_end,
                "test_end": test_end,
            })
            start += step
        return output

    def run(
        self,
        data: pd.DataFrame,
        optimizer: Callable[[pd.DataFrame], Any],
        evaluator: Callable[[Any, pd.DataFrame], Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for number, window in enumerate(self.windows(data), start=1):
            train = data.iloc[window["train_start"]:window["train_end"]].copy()
            test = data.iloc[window["test_start"]:window["test_end"]].copy()
            selected = optimizer(train)
            evaluation = dict(evaluator(selected, test))
            evaluation.update({"window": number, **window})
            evaluation["selected_candidate"] = selected
            evaluation["oos_pass"] = int(evaluation.get("trade_count", 0)) >= self.config.minimum_test_trades
            results.append(evaluation)
        return results

    @staticmethod
    def aggregate(results: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not results:
            return {"windows": 0, "passed_windows": 0, "pass_rate": 0.0}
        passed = sum(bool(r.get("oos_pass")) for r in results)
        pfs = [float(r.get("profit_factor", 0.0)) for r in results]
        return {
            "windows": len(results),
            "passed_windows": passed,
            "pass_rate": passed / len(results),
            "average_profit_factor": sum(pfs) / len(pfs),
        }
