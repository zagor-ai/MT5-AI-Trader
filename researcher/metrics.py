"""Pure performance metrics for backtest results."""

import numpy as np


def summarize_r(values, initial_balance=500.0, risk_pct=1.0):
    values = np.asarray(values, dtype=float)
    if values.size == 0:
        return {
            "trades": 0, "win_rate": 0.0, "profit_factor": 0.0,
            "net_r": 0.0, "expectancy_r": 0.0, "avg_r": 0.0,
            "max_drawdown_r": 0.0, "max_drawdown_pct": 0.0,
        }

    gross_profit = float(values[values > 0].sum())
    gross_loss = float(abs(values[values < 0].sum()))
    pf = 99.0 if gross_loss == 0 and gross_profit > 0 else (gross_profit / gross_loss if gross_loss else 0.0)
    cumulative = np.cumsum(values)
    peak = np.maximum.accumulate(np.maximum(cumulative, 0.0))
    max_dd_r = float((peak - cumulative).max())

    balance = float(initial_balance)
    peak_balance = balance
    max_dd_pct = 0.0
    risk_fraction = risk_pct / 100.0
    for r in values:
        balance += balance * risk_fraction * r
        peak_balance = max(peak_balance, balance)
        if peak_balance > 0:
            max_dd_pct = max(max_dd_pct, (peak_balance - balance) / peak_balance * 100.0)

    return {
        "trades": int(values.size),
        "win_rate": float((values > 0).mean() * 100.0),
        "profit_factor": float(pf),
        "net_r": float(values.sum()),
        "expectancy_r": float(values.mean()),
        "avg_r": float(values.mean()),
        "max_drawdown_r": max_dd_r,
        "max_drawdown_pct": float(max_dd_pct),
        "final_balance": float(balance),
        "gross_profit_r": gross_profit,
        "gross_loss_r": gross_loss,
    }
