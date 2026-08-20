"""Rolling walk-forward validation with progress and stop checkpoints."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any, Callable, Dict, Iterable, List, Optional
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
    start, index = 0, 1
    while start + train_bars + test_bars <= n_bars:
        windows.append(WalkForwardWindow(index, start, start + train_bars, start + train_bars, start + train_bars + test_bars))
        start += step
        index += 1
    return windows


def evaluate_walk_forward(data: pd.DataFrame, candidates: Iterable[Any], evaluator: Callable[[pd.DataFrame, Any], Dict[str, Any]], train_bars: int, test_bars: int, step_bars: int | None = None, min_test_trades: int = 10, stop_event: Optional[Any] = None, progress_callback: Optional[Callable[[int, int, int, int], None]] = None, log_callback: Optional[Callable[[str], None]] = None) -> List[Dict[str, Any]]:
    windows = build_windows(len(data), train_bars, test_bars, step_bars)
    candidate_list = list(candidates)
    candidate_total, window_total = len(candidate_list), len(windows)
    results: List[Dict[str, Any]] = []
    if log_callback:
        log_callback(f"[WALK-FORWARD] Windows available: {window_total}")
    for candidate_index, candidate in enumerate(candidate_list, 1):
        if stop_event is not None and stop_event.is_set():
            if log_callback: log_callback(f"[WALK-FORWARD] STOP before strategy {candidate_index}/{candidate_total}")
            break
        window_results = []
        name = getattr(candidate, "name", f"Strategy {candidate_index}")
        if log_callback: log_callback(f"[WALK-FORWARD] Strategy {candidate_index}/{candidate_total}: {name}")
        for window_index, window in enumerate(windows, 1):
            if stop_event is not None and stop_event.is_set():
                if log_callback: log_callback(f"[WALK-FORWARD] STOP at strategy {candidate_index}/{candidate_total}, window {window_index - 1}/{window_total}")
                break
            if progress_callback: progress_callback(candidate_index, candidate_total, window_index, window_total)
            if log_callback: log_callback(f"[WALK-FORWARD] Strategy {candidate_index}/{candidate_total} | Window {window_index}/{window_total}")
            train = data.iloc[window.train_start:window.train_end]
            test = data.iloc[window.test_start:window.test_end]
            train_result = evaluator(train, candidate)
            if stop_event is not None and stop_event.is_set(): break
            test_result = evaluator(test, candidate)
            if int(test_result.get("trade_count", 0)) < min_test_trades:
                if log_callback: log_callback(f"[WALK-FORWARD] Strategy {candidate_index} Window {window_index}: rejected, OOS trades={test_result.get('trade_count', 0)} < {min_test_trades}")
                continue
            window_results.append({"window": window.to_dict(), "train": train_result, "test": test_result})
        if window_results:
            nets = [float(x["test"].get("net_r", 0.0)) for x in window_results]
            pfs = [float(x["test"].get("profit_factor", 0.0)) for x in window_results]
            positive = sum(1 for value in nets if value > 0)
            results.append({"candidate": candidate, "windows": window_results, "window_count": len(window_results), "positive_windows": positive, "positive_window_ratio": positive / len(window_results), "oos_net_r_sum": sum(nets), "oos_net_r_mean": sum(nets) / len(nets), "oos_pf_mean": sum(pfs) / len(pfs)})
    return results
