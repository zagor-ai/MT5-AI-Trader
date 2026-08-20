"""Robustness score for walk-forward OOS results."""
from __future__ import annotations
from typing import Dict


def walk_forward_score(result: Dict) -> float:
    windows = max(int(result.get("window_count", 0)), 1)
    positive_ratio = float(result.get("positive_window_ratio", 0.0))
    mean_net = float(result.get("oos_net_r_mean", 0.0))
    mean_pf = float(result.get("oos_pf_mean", 0.0))
    coverage = min(windows / 6.0, 1.0)
    consistency = min(max(positive_ratio, 0.0), 1.0)
    profit = max(mean_net, 0.0)
    pf_component = min(max(mean_pf, 0.0), 3.0)
    return float(profit * 0.45 + pf_component * 10.0 * 0.25 + consistency * 10.0 * 0.20 + coverage * 10.0 * 0.10)
