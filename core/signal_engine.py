"""Translate StrategySpec objects into deterministic OHLC signals.

This module is read-only: it calculates research signals and ATR risk
information; it never sends orders to MetaTrader 5.
"""
from typing import Tuple
import pandas as pd
from .strategy_generator import StrategySpec
from .indicators.technical import ema, rsi, atr, adx


class SignalEngine:
    def build(self, data: pd.DataFrame, spec: StrategySpec) -> Tuple[pd.Series, pd.Series]:
        df = data.copy()
        df.columns = [str(c).lower() for c in df.columns]
        required = {"open", "high", "low", "close"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"Missing OHLC columns: {sorted(missing)}")

        close = pd.to_numeric(df["close"], errors="coerce")
        fast_n = int(spec.indicators["ema_fast"])
        slow_n = int(spec.indicators["ema_slow"])
        rsi_n = int(spec.indicators["rsi_period"])
        atr_n = int(spec.indicators["atr_period"])
        adx_n = int(spec.indicators.get("adx_period", 14))
        adx_min = float(spec.filters.get("adx_min", 0)) if hasattr(spec, "filters") else 0.0

        fast = ema(close, fast_n)
        slow = ema(close, slow_n)
        rsi_value = rsi(close, rsi_n)
        atr_value = atr(df, atr_n)
        adx_value = adx(df, adx_n)

        if spec.direction == "BUY":
            cond = (
                (fast > slow)
                & rsi_value.between(float(spec.indicators["rsi_buy"]), 70, inclusive="both")
                & (adx_value >= adx_min)
            )
            signal = cond.astype("int8")
        else:
            cond = (
                (fast < slow)
                & rsi_value.between(30, float(spec.indicators["rsi_sell"]), inclusive="both")
                & (adx_value >= adx_min)
            )
            signal = -cond.astype("int8")

        return signal, atr_value * float(spec.risk["atr_sl"])
