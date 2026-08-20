"""Compatibility adapter between strategy-family candidates and StrategySpec."""
from __future__ import annotations
from typing import Any
from .strategy_families import StrategyCandidate
from .strategy_generator import StrategySpec


def candidate_to_spec(candidate: StrategyCandidate) -> StrategySpec:
    direction = candidate.direction.upper()
    if direction not in ("BUY", "SELL"):
        raise ValueError(f"Unsupported direction: {candidate.direction}")

    indicators = {
        "ema_fast": candidate.ema_fast,
        "ema_slow": candidate.ema_slow,
        "rsi_period": candidate.rsi_period,
        "rsi_buy": candidate.rsi_buy_min,
        "rsi_sell": candidate.rsi_sell_max,
        "atr_period": candidate.atr_period,
        "adx_period": candidate.adx_period,
        "adx_min": candidate.adx_min,
    }
    entry_rules = [
        {"type": "EMA_TREND", "fast": candidate.ema_fast, "slow": candidate.ema_slow,
         "relation": ">" if direction == "BUY" else "<"},
        {"type": "RSI_RANGE",
         "min": candidate.rsi_buy_min if direction == "BUY" else candidate.rsi_sell_min,
         "max": candidate.rsi_buy_max if direction == "BUY" else candidate.rsi_sell_max},
        {"type": "ADX_MIN", "period": candidate.adx_period, "min": candidate.adx_min},
    ]
    exit_rules = [
        {"type": "ATR_SL", "multiplier": 1.5},
        {"type": "RR_TP", "rr": candidate.rr},
    ]
    risk = {"atr_sl": 1.5, "rr": candidate.rr}
    return StrategySpec(
        name=candidate.name,
        direction=direction,
        indicators=indicators,
        entry_rules=entry_rules,
        exit_rules=exit_rules,
        risk=risk,
    )
