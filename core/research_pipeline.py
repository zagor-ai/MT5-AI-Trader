"""End-to-end read-only pipeline for one StrategyCandidate."""
from __future__ import annotations
from typing import Any, Dict
import pandas as pd
from .strategy_adapter import candidate_to_spec
from .signal_engine import SignalEngine
from .backtester import Backtester


def evaluate_candidate(data: pd.DataFrame, candidate: Any, backtester: Backtester | None = None) -> Dict[str, Any]:
    spec = candidate_to_spec(candidate)
    signals, sl_distance = SignalEngine().build(data, spec)
    frame = data.copy()
    frame.columns = [str(c).lower() for c in frame.columns]
    frame["signal"] = signals
    frame["sl_distance"] = sl_distance
    result = (backtester or Backtester()).run(frame)
    result["strategy"] = spec.to_dict()
    return result
