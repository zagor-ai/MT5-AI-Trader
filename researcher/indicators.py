"""Pure pandas/numpy indicator calculations.

No MT5 or GUI dependency belongs in this module.
"""

import numpy as np
import pandas as pd


def ema(series, period):
    return series.ewm(span=period, adjust=False, min_periods=period).mean()


def rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return (100 - (100 / (1 + rs))).fillna(50.0)


def true_range(df):
    prev = df["close"].shift(1)
    return pd.concat([
        df["high"] - df["low"],
        (df["high"] - prev).abs(),
        (df["low"] - prev).abs(),
    ], axis=1).max(axis=1)


def atr(df, period=14):
    return true_range(df).ewm(alpha=1 / period, adjust=False, min_periods=period).mean()


def macd(series, fast=12, slow=26, signal=9):
    line = ema(series, fast) - ema(series, slow)
    sig = ema(line, signal)
    return line, sig, line - sig


def bollinger(series, period=20, std_mult=2.0):
    mid = series.rolling(period, min_periods=period).mean()
    std = series.rolling(period, min_periods=period).std()
    return mid + std_mult * std, mid, mid - std_mult * std


def stochastic(df, period=14, smooth=3):
    low = df["low"].rolling(period, min_periods=period).min()
    high = df["high"].rolling(period, min_periods=period).max()
    k = 100 * (df["close"] - low) / (high - low).replace(0, np.nan)
    d = k.rolling(smooth, min_periods=smooth).mean()
    return k, d


def adx(df, period=14):
    up = df["high"].diff()
    down = -df["low"].diff()
    plus_dm = pd.Series(np.where((up > down) & (up > 0), up, 0.0), index=df.index)
    minus_dm = pd.Series(np.where((down > up) & (down > 0), down, 0.0), index=df.index)
    tr = true_range(df)
    atr_n = tr.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    plus_di = 100 * plus_dm.ewm(alpha=1 / period, adjust=False, min_periods=period).mean() / atr_n
    minus_di = 100 * minus_dm.ewm(alpha=1 / period, adjust=False, min_periods=period).mean() / atr_n
    den = (plus_di + minus_di).replace(0, np.nan)
    dx = 100 * (plus_di - minus_di).abs() / den
    value = dx.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    return value.fillna(0), plus_di.fillna(0), minus_di.fillna(0)
