"""Chronological train/test split utilities."""
from dataclasses import dataclass
from typing import Any, Dict, Tuple

import pandas as pd


@dataclass(frozen=True)
class SplitConfig:
    train_ratio: float = 0.70
    min_train_bars: int = 500
    min_test_bars: int = 200


def chronological_split(data: pd.DataFrame, config: SplitConfig | None = None) -> Tuple[pd.DataFrame, pd.DataFrame]:
    cfg = config or SplitConfig()
    if not 0.5 <= cfg.train_ratio < 1.0:
        raise ValueError("train_ratio must be between 0.5 and 1.0")
    n = len(data)
    cut = int(n * cfg.train_ratio)
    if cut < cfg.min_train_bars or n - cut < cfg.min_test_bars:
        raise ValueError(f"Insufficient data for split: total={n}, train={cut}, test={n-cut}")
    return data.iloc[:cut].copy(), data.iloc[cut:].copy()


def compare_train_test(train: Dict[str, Any], test: Dict[str, Any]) -> Dict[str, Any]:
    """Return simple degradation measures; no optimization is performed here."""
    train_pf = float(train.get("profit_factor", 0.0))
    test_pf = float(test.get("profit_factor", 0.0))
    train_exp = float(train.get("expectancy", 0.0))
    test_exp = float(test.get("expectancy", 0.0))
    pf_ratio = test_pf / train_pf if train_pf > 0 else 0.0
    exp_ratio = test_exp / train_exp if train_exp > 0 else 0.0
    return {
        "train_profit_factor": train_pf,
        "test_profit_factor": test_pf,
        "pf_retention": pf_ratio,
        "train_expectancy": train_exp,
        "test_expectancy": test_exp,
        "expectancy_retention": exp_ratio,
        "passes_basic_oos": bool(test_pf >= 1.0 and test_exp > 0),
    }
