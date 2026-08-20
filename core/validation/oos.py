"""Out-of-sample evaluation helpers."""
from __future__ import annotations
from typing import Any, Callable, Dict, Iterable, List
import pandas as pd


def evaluate_oos(
    candidates: Iterable[Any],
    train_data: pd.DataFrame,
    test_data: pd.DataFrame,
    evaluator: Callable[[pd.DataFrame, Any], Dict[str, Any]],
    min_train_trades: int = 30,
    min_test_trades: int = 10,
) -> List[Dict[str, Any]]:
    accepted: List[Dict[str, Any]] = []
    for candidate in candidates:
        train = evaluator(train_data, candidate)
        if int(train.get("trade_count", 0)) < min_train_trades:
            continue
        test = evaluator(test_data, candidate)
        if int(test.get("trade_count", 0)) < min_test_trades:
            continue
        train_net = float(train.get("net_r", 0.0))
        test_net = float(test.get("net_r", 0.0))
        train_dd = max(float(train.get("max_drawdown_r", 0.0)), 1e-9)
        test_dd = max(float(test.get("max_drawdown_r", 0.0)), 1e-9)
        accepted.append({
            "candidate": candidate,
            "train": train,
            "test": test,
            "oos_net_r": test_net,
            "oos_pf": float(test.get("profit_factor", 0.0)),
            "oos_win_rate": float(test.get("win_rate", 0.0)),
            "oos_drawdown_r": test_dd,
            "oos_to_train_ratio": test_net / train_net if train_net > 0 else 0.0,
            "dd_ratio": test_dd / train_dd,
        })
    return accepted
