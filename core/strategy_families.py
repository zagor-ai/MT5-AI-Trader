"""Constrained strategy-family generator.

The generator intentionally limits combinations to reduce brute-force curve
fitting. It produces signal specifications; execution remains in Backtester.
"""
from dataclasses import dataclass, asdict
from itertools import product
from typing import Dict, List


@dataclass(frozen=True)
class StrategyCandidate:
    name: str
    family: str
    direction: str
    ema_fast: int = 50
    ema_slow: int = 200
    rsi_period: int = 14
    rsi_buy_min: float = 50.0
    rsi_buy_max: float = 70.0
    rsi_sell_min: float = 30.0
    rsi_sell_max: float = 50.0
    atr_period: int = 14
    adx_period: int = 14
    adx_min: float = 20.0
    rr: float = 2.0

    def to_dict(self) -> Dict:
        return asdict(self)


def generate_candidates(max_candidates: int = 300) -> List[StrategyCandidate]:
    """Generate a bounded, deterministic candidate set.

    Only economically sensible combinations are emitted. The caller may cap
    the final list, but never gets an unbounded Cartesian product.
    """
    fast_values = (20, 50)
    slow_values = (100, 200)
    adx_values = (20.0, 25.0, 30.0)
    rr_values = (1.5, 2.0, 2.5)
    candidates: List[StrategyCandidate] = []

    for fast, slow, adx_min, rr, direction in product(
        fast_values, slow_values, adx_values, rr_values, ("BUY", "SELL")
    ):
        if fast >= slow:
            continue
        family = "TREND_PULLBACK"
        name = f"{family}_{direction}_EMA{fast}_{slow}_ADX{adx_min:g}_RR{rr:g}"
        candidates.append(StrategyCandidate(
            name=name, family=family, direction=direction,
            ema_fast=fast, ema_slow=slow, adx_min=adx_min, rr=rr,
        ))
        if len(candidates) >= max_candidates:
            return candidates

    return candidates
