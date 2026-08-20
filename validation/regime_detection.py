"""Simple, deterministic market-regime classification for research.

Regimes are descriptive labels, not trade signals. The detector uses ATR
relative to its rolling baseline and EMA slope/relationship to classify bars.
"""
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class RegimeConfig:
    ema_fast: int = 50
    ema_slow: int = 200
    atr_period: int = 14
    baseline_period: int = 100
    high_vol_ratio: float = 1.30
    low_vol_ratio: float = 0.70
    slope_lookback: int = 5


class MarketRegimeDetector:
    def __init__(self, config: Optional[RegimeConfig] = None):
        self.config = config or RegimeConfig()

    def detect(self, data: pd.DataFrame) -> pd.Series:
        df = data.copy()
        df.columns = [str(c).lower() for c in df.columns]
        for col in ("high", "low", "close"):
            if col not in df:
                raise ValueError(f"Missing required column: {col}")
        close = pd.to_numeric(df["close"], errors="coerce")
        high = pd.to_numeric(df["high"], errors="coerce")
        low = pd.to_numeric(df["low"], errors="coerce")
        ema_fast = close.ewm(span=self.config.ema_fast, adjust=False).mean()
        ema_slow = close.ewm(span=self.config.ema_slow, adjust=False).mean()
        prev_close = close.shift(1)
        tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
        atr = tr.rolling(self.config.atr_period, min_periods=1).mean()
        atr_base = atr.rolling(self.config.baseline_period, min_periods=1).median()
        vol_ratio = atr / atr_base.replace(0, np.nan)
        slope = ema_fast.diff(self.config.slope_lookback)

        result = pd.Series("UNKNOWN", index=df.index, dtype="object")
        high_vol = vol_ratio >= self.config.high_vol_ratio
        low_vol = vol_ratio <= self.config.low_vol_ratio
        trend_up = (ema_fast > ema_slow) & (slope > 0)
        trend_down = (ema_fast < ema_slow) & (slope < 0)
        result[trend_up & ~high_vol] = "TREND_UP"
        result[trend_down & ~high_vol] = "TREND_DOWN"
        result[(~trend_up & ~trend_down) & ~high_vol & ~low_vol] = "RANGE"
        result[high_vol] = "HIGH_VOLATILITY"
        result[low_vol & ~high_vol] = "LOW_VOLATILITY"
        return result

    @staticmethod
    def distribution(regimes: pd.Series) -> pd.DataFrame:
        counts = regimes.value_counts(dropna=False)
        total = max(1, len(regimes))
        return pd.DataFrame({"bars": counts, "percent": counts / total * 100.0})
