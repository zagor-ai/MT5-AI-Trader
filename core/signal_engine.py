"""Translate StrategySpec objects into deterministic OHLC signals."""
from typing import Tuple
import numpy as np
import pandas as pd
from .strategy_generator import StrategySpec


class SignalEngine:
    @staticmethod
    def _atr(df: pd.DataFrame, period: int) -> pd.Series:
        prev = df["close"].shift(1)
        tr = pd.concat([(df["high"]-df["low"]), (df["high"]-prev).abs(), (df["low"]-prev).abs()], axis=1).max(axis=1)
        return tr.rolling(period, min_periods=period).mean()

    def build(self, data: pd.DataFrame, spec: StrategySpec) -> Tuple[pd.Series, pd.Series]:
        df = data.copy()
        df.columns = [str(c).lower() for c in df.columns]
        close = pd.to_numeric(df["close"], errors="coerce")
        fast_n = int(spec.indicators["ema_fast"])
        slow_n = int(spec.indicators["ema_slow"])
        rsi_n = int(spec.indicators["rsi_period"])
        atr_n = int(spec.indicators["atr_period"])
        fast = close.ewm(span=fast_n, adjust=False).mean()
        slow = close.ewm(span=slow_n, adjust=False).mean()
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(rsi_n, min_periods=rsi_n).mean()
        loss = (-delta.clip(upper=0)).rolling(rsi_n, min_periods=rsi_n).mean()
        rs = gain / loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        atr = self._atr(df, atr_n)
        if spec.direction == "BUY":
            cond = (fast > slow) & rsi.between(float(spec.indicators["rsi_buy"]), 70, inclusive="both")
            signal = cond.astype(int)
        else:
            cond = (fast < slow) & rsi.between(30, float(spec.indicators["rsi_sell"]), inclusive="both")
            signal = -cond.astype(int)
        return signal, atr * float(spec.risk["atr_sl"])
