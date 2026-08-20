"""Market regime detection and strategy-by-regime robustness analysis.

Research-only. No MT5 orders or trading actions are performed.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any, Callable, Dict, List, Optional
import numpy as np
import pandas as pd

@dataclass(frozen=True)
class RegimeConfig:
    atr_period: int = 14
    trend_threshold: float = 0.0025
    high_volatility_quantile: float = 0.75
    low_volatility_quantile: float = 0.25
    min_bars_per_regime: int = 100

@dataclass(frozen=True)
class RegimeResult:
    regime: str
    bars: int
    start: str
    end: str
    trade_count: int
    net_r: float
    profit_factor: float
    max_drawdown_r: float
    score: float
    acceptable: bool

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def detect_regimes(data: pd.DataFrame, config: Optional[RegimeConfig] = None) -> pd.Series:
    cfg = config or RegimeConfig()
    required = {"open", "high", "low", "close"}
    missing = required.difference(data.columns)
    if missing:
        raise ValueError(f"Missing OHLC columns: {sorted(missing)}")
    close = pd.to_numeric(data["close"], errors="coerce")
    high = pd.to_numeric(data["high"], errors="coerce")
    low = pd.to_numeric(data["low"], errors="coerce")
    atr = pd.concat([high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1).rolling(cfg.atr_period).mean()
    atr_pct = atr / close.replace(0, np.nan)
    vol_hi = atr_pct.quantile(cfg.high_volatility_quantile)
    vol_lo = atr_pct.quantile(cfg.low_volatility_quantile)
    trend = (close / close.shift(cfg.atr_period) - 1.0).abs()
    direction = close.pct_change(cfg.atr_period)
    labels = pd.Series("RANGE_LOW_VOL", index=data.index, dtype="object")
    labels.loc[atr_pct >= vol_hi] = "RANGE_HIGH_VOL"
    labels.loc[(direction.abs() >= cfg.trend_threshold) & (atr_pct < vol_hi)] = "TREND_HIGH_VOL" if vol_hi <= vol_lo else "TREND"
    labels.loc[(direction.abs() < cfg.trend_threshold) & (atr_pct <= vol_lo)] = "RANGE_LOW_VOL"
    labels.loc[(direction.abs() >= cfg.trend_threshold) & (atr_pct <= vol_lo)] = "TREND_LOW_VOL"
    labels.loc[(direction.abs() < cfg.trend_threshold) & (atr_pct >= vol_hi)] = "RANGE_HIGH_VOL"
    return labels.fillna("UNKNOWN")


def analyze_regimes(data: pd.DataFrame, regimes: pd.Series, evaluator: Callable[[pd.DataFrame], Dict[str, Any]], config: Optional[RegimeConfig] = None) -> List[Dict[str, Any]]:
    cfg = config or RegimeConfig()
    results: List[Dict[str, Any]] = []
    for regime in sorted(str(x) for x in regimes.dropna().unique()):
        mask = regimes == regime
        subset = data.loc[mask]
        if len(subset) < cfg.min_bars_per_regime:
            continue
        metrics = dict(evaluator(subset) or {})
        trades = int(metrics.get("trade_count", 0))
        net_r = float(metrics.get("net_r", 0.0))
        pf = float(metrics.get("profit_factor", 0.0))
        dd = float(metrics.get("max_drawdown_r", 0.0))
        score = (net_r / max(dd, 1.0)) + min(pf, 5.0) * 0.5
        results.append(RegimeResult(regime, len(subset), str(subset.index[0]), str(subset.index[-1]), trades, net_r, pf, dd, score, net_r > 0 and pf >= 1.0).to_dict())
    return results


def regime_robustness_score(results: List[Dict[str, Any]]) -> float:
    if not results:
        return 0.0
    acceptable = sum(bool(x.get("acceptable")) for x in results) / len(results)
    positive = sum(float(x.get("net_r", 0.0)) > 0 for x in results) / len(results)
    pf_values = [float(x.get("profit_factor", 0.0)) for x in results]
    median_pf = float(np.median(pf_values)) if pf_values else 0.0
    return max(0.0, min(100.0, 55.0 * acceptable + 30.0 * positive + 15.0 * min(median_pf / 2.0, 1.0)))
