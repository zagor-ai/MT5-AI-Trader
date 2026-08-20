"""Dependency-light technical indicators for XAU research.

All functions are deterministic and operate on pandas Series/DataFrames. They
are research features only and do not place orders.
"""
from __future__ import annotations
import numpy as np
import pandas as pd


def ema(s: pd.Series, period: int) -> pd.Series:
    return s.ewm(span=period, adjust=False, min_periods=period).mean()


def rsi(s: pd.Series, period: int = 14) -> pd.Series:
    delta = s.diff()
    up = delta.clip(lower=0.0)
    down = -delta.clip(upper=0.0)
    avg_up = up.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_down = down.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = avg_up / avg_down.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    prev = df["close"].shift(1)
    tr = pd.concat([(df["high"] - df["low"]), (df["high"] - prev).abs(), (df["low"] - prev).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()


def macd(s: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    line = ema(s, fast) - ema(s, slow)
    sig = line.ewm(span=signal, adjust=False, min_periods=signal).mean()
    return line, sig, line - sig


def adx(df: pd.DataFrame, period: int = 14):
    high, low, close = df["high"], df["low"], df["close"]
    up = high.diff()
    down = -low.diff()
    plus_dm = up.where((up > down) & (up > 0), 0.0)
    minus_dm = down.where((down > up) & (down > 0), 0.0)
    a = atr(df, period)
    plus_di = 100 * plus_dm.ewm(alpha=1 / period, adjust=False, min_periods=period).mean() / a.replace(0, np.nan)
    minus_di = 100 * minus_dm.ewm(alpha=1 / period, adjust=False, min_periods=period).mean() / a.replace(0, np.nan)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    return dx.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()


def bollinger(s: pd.Series, period: int = 20, std_mult: float = 2.0):
    mid = s.rolling(period, min_periods=period).mean()
    std = s.rolling(period, min_periods=period).std(ddof=0)
    return mid, mid + std_mult * std, mid - std_mult * std


def stochastic(df: pd.DataFrame, period: int = 14, smooth: int = 3):
    low_n = df["low"].rolling(period, min_periods=period).min()
    high_n = df["high"].rolling(period, min_periods=period).max()
    k = 100 * (df["close"] - low_n) / (high_n - low_n).replace(0, np.nan)
    d = k.rolling(smooth, min_periods=smooth).mean()
    return k, d


def ichimoku(df: pd.DataFrame):
    high9 = df["high"].rolling(9, min_periods=9).max()
    low9 = df["low"].rolling(9, min_periods=9).min()
    conversion = (high9 + low9) / 2
    high26 = df["high"].rolling(26, min_periods=26).max()
    low26 = df["low"].rolling(26, min_periods=26).min()
    base = (high26 + low26) / 2
    span_a = (conversion + base) / 2
    high52 = df["high"].rolling(52, min_periods=52).max()
    low52 = df["low"].rolling(52, min_periods=52).min()
    span_b = (high52 + low52) / 2
    return conversion, base, span_a, span_b
