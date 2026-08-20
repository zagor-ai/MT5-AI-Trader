"""Validation and overfitting penalty utilities."""
from __future__ import annotations
from typing import Dict


def validation_score(result: Dict) -> float:
    train = result.get("train", {})
    test = result.get("test", {})
    train_pf = max(float(train.get("profit_factor", 0.0)), 0.0)
    test_pf = max(float(test.get("profit_factor", 0.0)), 0.0)
    test_net = float(test.get("net_r", 0.0))
    test_dd = max(float(test.get("max_drawdown_r", 0.0)), 0.0)
    ratio = float(result.get("oos_to_train_ratio", 0.0))
    dd_ratio = float(result.get("dd_ratio", 1.0))
    pf_consistency = min(test_pf / train_pf, 1.0) if train_pf > 0 else 0.0
    ratio_score = max(0.0, min(ratio, 1.25)) / 1.25
    dd_penalty = min(max(dd_ratio - 1.0, 0.0), 2.0) * 0.15
    score = (test_net * 0.45) + (test_pf * 10.0 * 0.30) + (pf_consistency * 10.0 * 0.15) + (ratio_score * 10.0 * 0.10)
    score -= test_dd * 0.20
    score -= dd_penalty * 10.0
    return float(score)
