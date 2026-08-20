"""Rolling walk-forward validation for chronological strategy research."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any, Callable, Dict, Iterable, List
import pandas as pd

@dataclass(frozen=True)
class WalkForwardWindow:
    index: int
    train_start: int
    train_end: int
    test_start: int
    test_end: int

    def to_dict(self) -> Dict[str, int]:
        return asdict(self)


def build_windows(n_bars: int, train_bars: int, test_bars: int, step_bars: int | None = None) -> List[WalkForwardWindow]:
    if train_bars <= 0 or test_bars <= 0:
        raise ValueError("train_bars and test_bars must be positive")
    step = test_bars if step_bars is None else step_bars
    if step <= 0:
        raise ValueError("step_bars must be positive")
    windows: List[WalkForwardWindow] = []
    start = 0
    idx = 1
    while start + train_bars + test_bars <= n_bars:
        windows.append(WalkForwardWindow(idx, start, start + train_bars, start + train_bars, start + train_bars + test_bars))
        start += step
        idx += 1
    return windows


def evaluate_walk_forward(
    data: pd.DataFrame,
    candidates: Iterable[Any],
    evaluator: Callable[[pd.DataFrame, Any], Dict[str, Any]],
    train_bars: int,
    test_bars: int,
    step_bars: int | None = None,
    min_test_trades: int = 10,
) -> List[Dict[str, Any]]:
    """Evaluate each candidate independently on every OOS window.

    No optimization is performed on the test segment. The same candidate is
    simply measured on each future window, which makes consistency visible.
    """
    windows = build_windows(len(data), train_bars, test_bars, step_bars)
    results: List[Dict[str, Any]] = []
    for candidate in candidates:
        window_results = []
        for window in windows:
            train = data.iloc[window.train_start:window.train_end]
            test = data.iloc[window.test_start:window.test_end]
            train_result = evaluator(train, candidate)
            test_result = evaluator(test, candidate)
            if int(test_result.get("trade_count", 0)) < min_test_trades:
                continue
            window_results.append({"window": window.to_dict(), "train": train_result, "test": test_result})
        if window_results:
            oos_nets = [float(x["test"].get("net_r", 0.0)) for x in window_results]
            oos_pfs = [float(x["test"].get("profit_factor", 0.0)) for x in window_results]
            positive = sum(1 for x in oos_nets if x > 0)
            results.append({
                "candidate": candidate,
                "windows": window_results,
                "window_count": len(window_results),
                "positive_windows": positive,
                "positive_window_ratio": positive / len(window_results),
                "oos_net_r_sum": sum(oos_nets),
                "oos_net_r_mean": sum(oos_nets) / len(oos_nets),
                "oos_pf_mean": sum(oos_pfs) / len(oos_pfs),
            })
    return results
