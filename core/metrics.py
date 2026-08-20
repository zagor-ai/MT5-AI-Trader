"""Metrics calculated from BacktestResult without trading side effects."""
from typing import Any, Dict
import numpy as np


def calculate_metrics(result: Any) -> Dict[str, Any]:
    trades = list(getattr(result, "trades", []))
    r = np.asarray([float(t.r_multiple) for t in trades], dtype=float)
    pnl = np.asarray([float(t.pnl) for t in trades], dtype=float)
    wins = r[r > 0]
    losses = r[r < 0]
    gross_win = float(wins.sum()) if wins.size else 0.0
    gross_loss = float(-losses.sum()) if losses.size else 0.0
    pf = gross_win / gross_loss if gross_loss > 0 else (float("inf") if gross_win > 0 else 0.0)
    equity = np.asarray(getattr(result, "equity_curve", []), dtype=float)
    if equity.size:
        peaks = np.maximum.accumulate(equity)
        dd = peaks - equity
        max_dd_cash = float(dd.max())
        max_dd_pct = float((dd / np.maximum(peaks, 1e-12)).max() * 100.0)
    else:
        max_dd_cash = max_dd_pct = 0.0
    return {
        "trade_count": int(r.size),
        "wins": int((r > 0).sum()),
        "losses": int((r < 0).sum()),
        "win_rate": float((r > 0).mean() * 100.0) if r.size else 0.0,
        "profit_factor": pf,
        "expectancy_r": float(r.mean()) if r.size else 0.0,
        "average_r": float(r.mean()) if r.size else 0.0,
        "net_r": float(r.sum()) if r.size else 0.0,
        "net_pnl": float(pnl.sum()) if pnl.size else 0.0,
        "max_drawdown_cash": max_dd_cash,
        "max_drawdown_percent": max_dd_pct,
    }
