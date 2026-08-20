"""Central configuration for XAU Strategy Researcher Pro v2.2."""

from dataclasses import dataclass


@dataclass(slots=True)
class ResearchConfig:
    symbol: str = "XAUUSD"
    timeframe: str = "M5"
    start: str = "2025-01-01"
    end: str = "2026-08-18"
    train_pct: int = 70
    max_candidates: int = 300
    min_train_trades: int = 80
    min_test_trades: int = 25
    initial_balance: float = 500.0
    risk_pct: float = 1.0
    max_spread_points: float = 80.0
    commission_r_per_trade: float = 0.02
    slippage_r_per_trade: float = 0.03
    rr_min: float = 1.4
    rr_max: float = 2.2
    rr_step: float = 0.4
    sl_min: float = 1.0
    sl_max: float = 2.0
    sl_step: float = 0.5
    max_hold_bars: int = 24
    seed: int = 42
