"""Out-of-sample evaluation helpers.

The OOS segment is never used to generate candidates. This module only evaluates
already selected specifications/results on unseen chronological data.
"""
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List

import pandas as pd


@dataclass(frozen=True)
class OOSConfig:
    minimum_trades: int = 20
    minimum_profit_factor: float = 1.0
    minimum_expectancy: float = 0.0
    minimum_pf_retention: float = 0.60


class OOSValidator:
    def __init__(self, config: OOSConfig | None = None):
        self.config = config or OOSConfig()

    def evaluate(self, train_result: Dict[str, Any], test_result: Dict[str, Any]) -> Dict[str, Any]:
        train_pf = float(train_result.get("profit_factor", 0.0))
        test_pf = float(test_result.get("profit_factor", 0.0))
        test_exp = float(test_result.get("expectancy", 0.0))
        test_trades = int(test_result.get("trade_count", 0))
        retention = test_pf / train_pf if train_pf > 0 else 0.0
        passed = (
            test_trades >= self.config.minimum_trades
            and test_pf >= self.config.minimum_profit_factor
            and test_exp >= self.config.minimum_expectancy
            and retention >= self.config.minimum_pf_retention
        )
        return {
            "train_pf": train_pf,
            "test_pf": test_pf,
            "test_expectancy": test_exp,
            "test_trades": test_trades,
            "pf_retention": retention,
            "oos_pass": passed,
        }

    def evaluate_many(self, rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
        output = []
        for row in rows:
            result = dict(row)
            result["oos_pass"] = bool(row.get("oos_pass", False))
            output.append(result)
        return output
