# -*- coding: utf-8 -*-
"""
XAU Strategy Researcher Pro v2.1
--------------------------------
MT5-connected research GUI for XAUUSD.

Research only:
- No live orders are sent.
- MT5 connection diagnostics are visible.
- Historical data loading is a separate step.
- Research runs in a background thread.
- Log is timestamped and can be copied in one click.
- Results are ranked by out-of-sample performance and robustness penalties.

Required:
    MetaTrader5
    pandas
    numpy

Install:
    python -m pip install MetaTrader5 pandas numpy
"""

from __future__ import annotations

import json
import math
import random
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tkinter import messagebox
import tkinter as tk
from tkinter import ttk, filedialog

import numpy as np
import pandas as pd

try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None


APP_TITLE = "XAU Strategy Researcher Pro"
VERSION = "2.1"

TIMEFRAMES = {
    "M1": "TIMEFRAME_M1",
    "M5": "TIMEFRAME_M5",
    "M15": "TIMEFRAME_M15",
    "M30": "TIMEFRAME_M30",
    "H1": "TIMEFRAME_H1",
}

INDICATORS = [
    "EMA", "RSI", "MACD", "ADX", "ATR",
    "Bollinger", "Stochastic", "Ichimoku",
    "Price Action", "Spread", "Session"
]


@dataclass
class Config:
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


def finite(x):
    try:
        return math.isfinite(float(x))
    except Exception:
        return False


def safe_float(x, default=0.0):
    try:
        x = float(x)
        return x if math.isfinite(x) else default
    except Exception:
        return default


# =====================================================================
# MT5 CONNECTION / DIAGNOSTICS
# =====================================================================

def initialize_mt5():
    if mt5 is None:
        raise RuntimeError(
            "کتابخانه MetaTrader5 نصب نیست.\n\n"
            "اجرا کنید:\n"
            "python -m pip install MetaTrader5 pandas numpy"
        )

    if not mt5.initialize():
        err = mt5.last_error()
        raise RuntimeError(f"MT5 initialize failed: {err}")

    info = mt5.terminal_info()
    account = mt5.account_info()

    return info, account


def shutdown_mt5():
    if mt5 is not None:
        try:
            mt5.shutdown()
        except Exception:
            pass


def mt5_snapshot(symbol: str):
    """
    Connect temporarily, collect diagnostics, then shut down.
    """
    info, account = initialize_mt5()
    try:
        symbol_info = mt5.symbol_info(symbol)
        tick = mt5.symbol_info_tick(symbol)

        return {
            "terminal": info,
            "account": account,
            "symbol": symbol_info,
            "tick": tick,
            "last_error": mt5.last_error(),
        }
    finally:
        shutdown_mt5()


def load_rates(symbol: str, timeframe: str, start: str, end: str, logger):
    logger("[MT5] Initializing terminal...")
    initialize_mt5()

    try:
        terminal = mt5.terminal_info()
        account = mt5.account_info()

        if terminal:
            logger(f"[MT5] Terminal: {getattr(terminal, 'name', 'Unknown')}")
            logger(f"[MT5] Build: {getattr(terminal, 'build', 'Unknown')}")

        if account:
            logger(f"[MT5] Account: {getattr(account, 'login', 'Unknown')}")
            logger(f"[MT5] Server: {getattr(account, 'server', 'Unknown')}")
            logger(f"[MT5] Balance: {getattr(account, 'balance', 0):.2f}")
            logger(f"[MT5] Equity: {getattr(account, 'equity', 0):.2f}")

        if not mt5.symbol_select(symbol, True):
            raise RuntimeError(
                f"Cannot select symbol {symbol}. MT5 error: {mt5.last_error()}"
            )

        sinfo = mt5.symbol_info(symbol)
        if sinfo is None:
            raise RuntimeError(
                f"Symbol {symbol} was not found in this MT5 terminal."
            )

        logger(f"[MT5] Symbol found: {symbol}")
        logger(f"[MT5] Digits: {getattr(sinfo, 'digits', '?')}")
        logger(f"[MT5] Point: {getattr(sinfo, 'point', '?')}")

        tick = mt5.symbol_info_tick(symbol)
        if tick:
            logger(
                f"[MT5] Tick: bid={safe_float(tick.bid):.3f} "
                f"ask={safe_float(tick.ask):.3f}"
            )

        a = datetime.strptime(start, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        b = (
            datetime.strptime(end, "%Y-%m-%d") + timedelta(days=1)
        ).replace(tzinfo=timezone.utc)

        tf = getattr(mt5, TIMEFRAMES[timeframe])
        logger(f"[DATA] Requesting {symbol} {timeframe}: {start} -> {end}")

        rates = mt5.copy_rates_range(symbol, tf, a, b)

        if rates is None:
            raise RuntimeError(
                f"MT5 returned no data. Error: {mt5.last_error()}"
            )

        if len(rates) == 0:
            raise RuntimeError(
                "MT5 returned 0 bars. Make sure the terminal is open and "
                "the requested history is available."
            )

        logger(f"[DATA] MT5 returned {len(rates):,} bars.")

        df = pd.DataFrame(rates)

        if "time" not in df.columns:
            raise RuntimeError("MT5 data does not contain a time column.")

        df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
        df = df.drop_duplicates(subset=["time"]).sort_values("time")
        df = df.set_index("time")

        for c in ["open", "high", "low", "close"]:
            df[c] = pd.to_numeric(df[c], errors="coerce")

        if "spread" in df.columns:
            df["spread"] = pd.to_numeric(
                df["spread"], errors="coerce"
            ).fillna(0.0)
            spread_available = True
        else:
            df["spread"] = 0.0
            spread_available = False

        df["spread_available"] = spread_available

        before = len(df)
        df = df.dropna(subset=["open", "high", "low", "close"])

        df = df[
            (df["high"] >= df["low"])
            & (df["high"] >= df["open"])
            & (df["high"] >= df["close"])
            & (df["low"] <= df["open"])
            & (df["low"] <= df["close"])
        ]

        removed = before - len(df)

        if len(df) < 1000:
            raise RuntimeError(
                f"Only {len(df)} valid bars are available. "
                "At least 1000 bars are recommended."
            )

        logger(f"[DATA] Valid bars: {len(df):,}")
        if removed:
            logger(f"[DATA] Invalid rows removed: {removed:,}")

        logger(
            f"[DATA] First: {df.index[0].strftime('%Y-%m-%d %H:%M:%S UTC')}"
        )
        logger(
            f"[DATA] Last : {df.index[-1].strftime('%Y-%m-%d %H:%M:%S UTC')}"
        )

        if spread_available:
            logger("[DATA] Historical spread column: AVAILABLE")
        else:
            logger(
                "[WARN] Historical spread column is unavailable. "
                "Spread filter will use zero data."
            )

        return df

    finally:
        shutdown_mt5()


# =====================================================================
# INDICATORS
# =====================================================================

def ema(s, n):
    return s.ewm(span=n, adjust=False, min_periods=n).mean()


def rsi(s, n=14):
    d = s.diff()
    up = d.clip(lower=0)
    down = -d.clip(upper=0)

    au = up.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    ad = down.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()

    rs = au / ad.replace(0, np.nan)
    return (100 - (100 / (1 + rs))).fillna(50.0)


def true_range(df):
    pc = df["close"].shift(1)
    return pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - pc).abs(),
            (df["low"] - pc).abs(),
        ],
        axis=1,
    ).max(axis=1)


def atr(df, n=14):
    return true_range(df).ewm(
        alpha=1 / n, adjust=False, min_periods=n
    ).mean()


def adx(df, n=14):
    up = df["high"].diff()
    down = -df["low"].diff()

    plus_dm = pd.Series(
        np.where((up > down) & (up > 0), up, 0.0),
        index=df.index,
    )
    minus_dm = pd.Series(
        np.where((down > up) & (down > 0), down, 0.0),
        index=df.index,
    )

    tr = true_range(df)
    atr_n = tr.ewm(
        alpha=1 / n, adjust=False, min_periods=n
    ).mean()

    plus_di = (
        100
        * plus_dm.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
        / atr_n
    )
    minus_di = (
        100
        * minus_dm.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
        / atr_n
    )

    den = (plus_di + minus_di).replace(0, np.nan)
    dx = 100 * (plus_di - minus_di).abs() / den
    adx_v = dx.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()

    return (
        adx_v.fillna(0),
        plus_di.fillna(0),
        minus_di.fillna(0),
    )


def macd(s):
    f = ema(s, 12)
    sl = ema(s, 26)
    line = f - sl
    sig = ema(line, 9)
    return line, sig, line - sig


def bollinger(s, n=20, k=2):
    mid = s.rolling(n, min_periods=n).mean()
    sd = s.rolling(n, min_periods=n).std()
    return mid, mid + k * sd, mid - k * sd


def stochastic(df, n=14, d=3):
    lo = df["low"].rolling(n, min_periods=n).min()
    hi = df["high"].rolling(n, min_periods=n).max()
    k = 100 * (df["close"] - lo) / (hi - lo).replace(0, np.nan)
    return k.fillna(50), k.rolling(d, min_periods=d).mean().fillna(50)


def build_features(df, logger=None):
    if logger:
        logger("[FEATURES] Calculating indicators...")

    x = df.copy()

    for n in (9, 20, 21, 50, 100, 200):
        x[f"ema{n}"] = ema(x["close"], n)

    x["rsi14"] = rsi(x["close"], 14)
    x["atr14"] = atr(x, 14)
    x["atr_pct"] = 100 * x["atr14"] / x["close"].replace(0, np.nan)

    x["adx14"], x["plus_di"], x["minus_di"] = adx(x, 14)
    x["macd"], x["macd_sig"], x["macd_hist"] = macd(x["close"])

    x["bb_mid"], x["bb_up"], x["bb_lo"] = bollinger(x["close"], 20, 2)
    x["stoch_k"], x["stoch_d"] = stochastic(x, 14, 3)

    conv = (
        x["high"].rolling(9, min_periods=9).max()
        + x["low"].rolling(9, min_periods=9).min()
    ) / 2

    base = (
        x["high"].rolling(26, min_periods=26).max()
        + x["low"].rolling(26, min_periods=26).min()
    ) / 2

    x["ichi_conv"] = conv
    x["ichi_base"] = base
    x["ichi_a"] = (conv + base) / 2

    x["ichi_b"] = (
        x["high"].rolling(52, min_periods=52).max()
        + x["low"].rolling(52, min_periods=52).min()
    ) / 2

    candle_range = (x["high"] - x["low"]).replace(0, np.nan)

    x["body_pct"] = (
        (x["close"] - x["open"]).abs() / candle_range
    )

    x["upper_wick_pct"] = (
        x["high"] - x[["open", "close"]].max(axis=1)
    ) / candle_range

    x["lower_wick_pct"] = (
        x[["open", "close"]].min(axis=1) - x["low"]
    ) / candle_range

    x["bull"] = x["close"] > x["open"]
    x["bear"] = x["close"] < x["open"]
    x["hour"] = x.index.hour

    for c in [
        "close", "high", "low",
        "ema20", "ema50", "ema100", "ema200"
    ]:
        x[f"prev_{c}"] = x[c].shift(1)

    if logger:
        logger("[FEATURES] Indicators ready.")

    return x


# =====================================================================
# SIGNAL ENGINE
# =====================================================================

def session_ok(hour, mode):
    if mode == "All":
        return True
    if mode == "London":
        return 8 <= hour < 17
    if mode == "NY":
        return 13 <= hour < 22
    return (8 <= hour < 17) or (13 <= hour < 22)


def signal_at(df, i, direction, p, selected):
    r = df.iloc[i]
    prev = df.iloc[i - 1]

    if not finite(r["atr14"]) or r["atr14"] <= 0:
        return False

    if "EMA" in selected:
        fast = p["fast"]
        slow = p["slow"]

        ef = r[f"ema{fast}"]
        es = r[f"ema{slow}"]
        pef = prev[f"ema{fast}"]

        if not all(finite(v) for v in (ef, es, pef)):
            return False

        if direction == "BUY":
            if not (ef > es and ef > pef):
                return False
            if abs(r["close"] - ef) > p["pullback"] * r["atr14"]:
                return False
        else:
            if not (ef < es and ef < pef):
                return False
            if abs(r["close"] - ef) > p["pullback"] * r["atr14"]:
                return False

    if "RSI" in selected:
        lo, hi = p["rsi_lo"], p["rsi_hi"]

        if direction == "BUY":
            if not lo <= r["rsi14"] <= hi:
                return False
        else:
            if not 100 - hi <= r["rsi14"] <= 100 - lo:
                return False

    if "MACD" in selected:
        if direction == "BUY":
            if not (r["macd"] > r["macd_sig"] and r["macd_hist"] > 0):
                return False
        else:
            if not (r["macd"] < r["macd_sig"] and r["macd_hist"] < 0):
                return False

    if "ADX" in selected:
        if r["adx14"] < p["adx"]:
            return False

        if direction == "BUY" and r["plus_di"] <= r["minus_di"]:
            return False

        if direction == "SELL" and r["minus_di"] <= r["plus_di"]:
            return False

    if "ATR" in selected:
        if not p["atr_min"] <= r["atr_pct"] <= p["atr_max"]:
            return False

    if "Bollinger" in selected:
        if direction == "BUY":
            if not (
                prev["close"] <= prev["bb_mid"]
                and r["close"] > r["bb_mid"]
            ):
                return False
        else:
            if not (
                prev["close"] >= prev["bb_mid"]
                and r["close"] < r["bb_mid"]
            ):
                return False

    if "Stochastic" in selected:
        if direction == "BUY":
            if not (
                r["stoch_k"] > r["stoch_d"]
                and r["stoch_k"] < p["stoch_hi"]
            ):
                return False
        else:
            if not (
                r["stoch_k"] < r["stoch_d"]
                and r["stoch_k"] > 100 - p["stoch_hi"]
            ):
                return False

    if "Ichimoku" in selected:
        top = max(r["ichi_a"], r["ichi_b"])
        bot = min(r["ichi_a"], r["ichi_b"])

        if not all(finite(v) for v in (top, bot)):
            return False

        if direction == "BUY":
            if not (
                r["close"] > top
                and r["ichi_conv"] > r["ichi_base"]
            ):
                return False
        else:
            if not (
                r["close"] < bot
                and r["ichi_conv"] < r["ichi_base"]
            ):
                return False

    if "Price Action" in selected:
        if r["body_pct"] < p["body"]:
            return False

        if direction == "BUY":
            if not (r["bull"] and r["close"] > prev["high"]):
                return False
        else:
            if not (r["bear"] and r["close"] < prev["low"]):
                return False

    if "Spread" in selected:
        if safe_float(r["spread"]) > p["spread"]:
            return False

    if "Session" in selected:
        if not session_ok(int(r["hour"]), p["session"]):
            return False

    return True


# =====================================================================
# BACKTEST
# =====================================================================

def summarize_trades(trades, cfg):
    arr = np.array([t["net_r"] for t in trades], dtype=float)

    if len(arr) == 0:
        return {
            "trades": 0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "net_r": 0.0,
            "expectancy_r": 0.0,
            "avg_r": 0.0,
            "max_drawdown_r": 0.0,
            "max_drawdown_pct": 0.0,
            "max_win_streak": 0,
            "max_loss_streak": 0,
            "avg_hold": 0.0,
            "gross_profit_r": 0.0,
            "gross_loss_r": 0.0,
            "raw_net_r": 0.0,
            "final_balance": cfg.initial_balance,
            "trades_data": trades,
        }

    gp = float(arr[arr > 0].sum())
    gl = float(abs(arr[arr < 0].sum()))

    if gl == 0:
        pf = 99.0 if gp > 0 else 0.0
    else:
        pf = gp / gl

    eq = np.cumsum(arr)
    peaks = np.maximum.accumulate(np.maximum(eq, 0.0))
    dd = peaks - eq
    max_dd_r = float(dd.max())

    equity = float(cfg.initial_balance)
    peak_equity = equity
    max_dd_pct = 0.0

    for r in arr:
        equity += equity * (cfg.risk_pct / 100.0) * r
        peak_equity = max(peak_equity, equity)

        if peak_equity > 0:
            dd_pct = (peak_equity - equity) / peak_equity * 100
            max_dd_pct = max(max_dd_pct, dd_pct)

    cur_w = cur_l = max_w = max_l = 0

    for v in arr:
        if v > 0:
            cur_w += 1
            cur_l = 0
            max_w = max(max_w, cur_w)
        elif v < 0:
            cur_l += 1
            cur_w = 0
            max_l = max(max_l, cur_l)
        else:
            cur_w = cur_l = 0

    return {
        "trades": int(len(arr)),
        "win_rate": float((arr > 0).mean() * 100),
        "profit_factor": float(pf),
        "net_r": float(arr.sum()),
        "expectancy_r": float(arr.mean()),
        "avg_r": float(arr.mean()),
        "max_drawdown_r": max_dd_r,
        "max_drawdown_pct": float(max_dd_pct),
        "max_win_streak": int(max_w),
        "max_loss_streak": int(max_l),
        "avg_hold": float(np.mean([t["hold_bars"] for t in trades])),
        "gross_profit_r": gp,
        "gross_loss_r": gl,
        "raw_net_r": float(
            sum(t["raw_r"] for t in trades)
        ),
        "final_balance": float(equity),
        "trades_data": trades,
    }


def backtest(
    df,
    direction,
    p,
    selected,
    start_i,
    end_i,
    cfg,
):
    trades = []

    i = max(start_i, 201)
    last = min(end_i, len(df) - 1)

    while i < last - 1:
        if not signal_at(df, i, direction, p, selected):
            i += 1
            continue

        signal_bar = df.iloc[i]
        entry_i = i + 1

        entry = safe_float(
            df.iloc[entry_i]["open"], np.nan
        )
        av = safe_float(
            signal_bar["atr14"], np.nan
        )

        if not finite(entry) or not finite(av) or av <= 0:
            i += 1
            continue

        dist = av * p["sl"]

        if direction == "BUY":
            sl = entry - dist
            tp = entry + dist * p["rr"]
        else:
            sl = entry + dist
            tp = entry - dist * p["rr"]

        exit_i = None
        exit_price = None
        reason = "TIME"

        last_j = min(
            last - 1,
            entry_i + p["hold"]
        )

        for j in range(entry_i, last_j + 1):
            bar = df.iloc[j]
            hi = safe_float(bar["high"], np.nan)
            lo = safe_float(bar["low"], np.nan)

            if not finite(hi) or not finite(lo):
                continue

            if direction == "BUY":
                hit_sl = lo <= sl
                hit_tp = hi >= tp

                # Conservative: SL wins if both are touched.
                if hit_sl:
                    exit_price = sl
                    exit_i = j
                    reason = "SL"
                    break

                if hit_tp:
                    exit_price = tp
                    exit_i = j
                    reason = "TP"
                    break

            else:
                hit_sl = hi >= sl
                hit_tp = lo <= tp

                if hit_sl:
                    exit_price = sl
                    exit_i = j
                    reason = "SL"
                    break

                if hit_tp:
                    exit_price = tp
                    exit_i = j
                    reason = "TP"
                    break

        if exit_i is None:
            exit_i = last_j
            exit_price = safe_float(
                df.iloc[exit_i]["close"], entry
            )

        if direction == "BUY":
            raw_r = (exit_price - entry) / dist
        else:
            raw_r = (entry - exit_price) / dist

        cost_r = (
            cfg.commission_r_per_trade
            + cfg.slippage_r_per_trade
        )

        spread_points = safe_float(
            df.iloc[entry_i]["spread"], 0
        )

        if "Spread" in selected:
            if spread_points > p["spread"]:
                i = exit_i + 1
                continue

        if spread_points > 0 and p["spread"] > 0:
            cost_r += min(
                0.15,
                (spread_points / p["spread"]) * 0.05,
            )

        net_r = raw_r - cost_r

        trades.append(
            {
                "signal_time": df.index[i].isoformat(),
                "entry_time": df.index[entry_i].isoformat(),
                "exit_time": df.index[exit_i].isoformat(),
                "direction": direction,
                "entry": float(entry),
                "exit": float(exit_price),
                "sl": float(sl),
                "tp": float(tp),
                "raw_r": float(raw_r),
                "net_r": float(net_r),
                "reason": reason,
                "hold_bars": int(exit_i - entry_i + 1),
                "spread_points": float(spread_points),
            }
        )

        i = exit_i + 1

    return summarize_trades(trades, cfg)


# =====================================================================
# CANDIDATES / RANKING
# =====================================================================

def parameter_candidates(cfg, selected):
    ema_pairs = (
        [(9, 21), (20, 50), (20, 100), (50, 200)]
        if "EMA" in selected
        else [(20, 50)]
    )

    rsi_ranges = (
        [(50, 65), (52, 68), (55, 70), (45, 60)]
        if "RSI" in selected
        else [(52, 68)]
    )

    adx_values = (
        [18, 20, 25, 30]
        if "ADX" in selected
        else [20]
    )

    atr_ranges = (
        [(0.03, 0.10), (0.05, 0.15), (0.03, 0.20), (0.05, 0.30)]
        if "ATR" in selected
        else [(0.0, 999.0)]
    )

    pulls = [0.25, 0.35, 0.50]
    sls = list(
        np.arange(
            cfg.sl_min,
            cfg.sl_max + 0.0001,
            cfg.sl_step
        )
    )
    rrs = list(
        np.arange(
            cfg.rr_min,
            cfg.rr_max + 0.0001,
            cfg.rr_step
        )
    )

    bodies = (
        [0.40, 0.50, 0.60]
        if "Price Action" in selected
        else [0.45]
    )

    sessions = (
        ["London", "NY", "Both", "All"]
        if "Session" in selected
        else ["All"]
    )

    spreads = (
        [cfg.max_spread_points]
        if "Spread" in selected
        else [999999.0]
    )

    stoch_hi = (
        [70, 80]
        if "Stochastic" in selected
        else [80]
    )

    candidates = []

    for ep, rrsi, adx_v, atr_rng, pull, sl, rr, body, sess, spr, shi in __import__(
        "itertools"
    ).product(
        ema_pairs,
        rsi_ranges,
        adx_values,
        atr_ranges,
        pulls,
        sls,
        rrs,
        bodies,
        sessions,
        spreads,
        stoch_hi,
    ):
        candidates.append(
            {
                "fast": ep[0],
                "slow": ep[1],
                "rsi_lo": rrsi[0],
                "rsi_hi": rrsi[1],
                "adx": float(adx_v),
                "atr_min": float(atr_rng[0]),
                "atr_max": float(atr_rng[1]),
                "pullback": float(pull),
                "sl": float(sl),
                "rr": float(rr),
                "body": float(body),
                "spread": float(spr),
                "session": sess,
                "stoch_hi": float(shi),
                "hold": int(cfg.max_hold_bars),
            }
        )

    rng = random.Random(cfg.seed)
    rng.shuffle(candidates)

    return candidates[:max(1, int(cfg.max_candidates))]


def stability_score(train, test):
    if train["trades"] <= 0 or test["trades"] <= 0:
        return 0.0

    pf_t = min(train["profit_factor"], 5.0)
    pf_o = min(test["profit_factor"], 5.0)

    pf_ratio = min(
        1.0,
        pf_o / max(pf_t, 1.0)
    )

    if train["expectancy_r"] > 0:
        exp_ratio = max(
            0.0,
            min(
                1.0,
                test["expectancy_r"]
                / train["expectancy_r"]
            ),
        )
    else:
        exp_ratio = 0.0

    dd_penalty = max(
        0.0,
        1.0 - test["max_drawdown_pct"] / 50.0
    )

    wr_diff = abs(
        train["win_rate"] - test["win_rate"]
    )

    consistency = max(
        0.0,
        1.0 - wr_diff / 30.0
    )

    return 100 * (
        0.35 * pf_ratio
        + 0.30 * exp_ratio
        + 0.20 * consistency
        + 0.15 * dd_penalty
    )


def overfit_penalty(train, test):
    penalty = 0.0

    if train["trades"] > 0 and test["trades"] > 0:
        pf_gap = max(
            0.0,
            train["profit_factor"]
            - test["profit_factor"],
        )
        penalty += min(30.0, pf_gap * 8.0)

        exp_gap = max(
            0.0,
            train["expectancy_r"]
            - test["expectancy_r"],
        )
        penalty += min(20.0, exp_gap * 20.0)

        wr_gap = max(
            0.0,
            train["win_rate"]
            - test["win_rate"]
            - 10.0,
        )
        penalty += min(15.0, wr_gap * 0.5)

    if train["trades"] < 80:
        penalty += 20.0
    elif train["trades"] < 120:
        penalty += 10.0

    if test["trades"] < 40:
        penalty += 12.0

    return min(70.0, penalty)


def final_score(train, test):
    if train["trades"] == 0 or test["trades"] == 0:
        return -999.0

    pf = min(test["profit_factor"], 4.0)
    exp = max(
        -1.0,
        min(test["expectancy_r"], 1.0)
    )
    dd = min(test["max_drawdown_pct"], 50.0)
    trades = min(test["trades"], 300)

    raw = (
        25 * min(pf / 2.0, 1.0)
        + 25 * max(0.0, exp + 0.25)
        + 15 * (1 - dd / 50.0)
        + 10 * min(test["win_rate"] / 70.0, 1.0)
        + 10 * min(trades / 100.0, 1.0)
        + 15 * stability_score(train, test) / 100.0
    )

    return raw - overfit_penalty(train, test)


def run_research(df, cfg, selected, logger, progress):
    features = build_features(df, logger)

    split = int(
        len(features) * cfg.train_pct / 100
    )

    split = max(
        300,
        min(split, len(features) - 300)
    )

    candidates = parameter_candidates(
        cfg, selected
    )

    total = len(candidates) * 2
    done = 0
    results = []

    logger(
        f"[RESEARCH] Candidates generated: {len(candidates)}"
    )
    logger(
        f"[RESEARCH] Train bars: {split:,} | "
        f"OOS bars: {len(features) - split:,}"
    )

    for n, p in enumerate(candidates, 1):
        for direction in ("BUY", "SELL"):
            train = backtest(
                features,
                direction,
                p,
                selected,
                0,
                split,
                cfg,
            )

            test = backtest(
                features,
                direction,
                p,
                selected,
                split,
                len(features),
                cfg,
            )

            done += 1
            progress(done, total)

            if (
                train["trades"]
                < cfg.min_train_trades
            ):
                continue

            if (
                test["trades"]
                < cfg.min_test_trades
            ):
                continue

            stability = stability_score(
                train, test
            )

            score = final_score(
                train, test
            )

            name = (
                f"{direction} | "
                f"EMA {p['fast']}/{p['slow']} | "
                f"RSI {p['rsi_lo']}-{p['rsi_hi']} | "
                f"ADX {p['adx']} | "
                f"SL {p['sl']:.1f} ATR | "
                f"RR {p['rr']:.1f}"
            )

            results.append(
                {
                    "name": name,
                    "direction": direction,
                    "params": p,
                    "train": train,
                    "test": test,
                    "stability": stability,
                    "score": score,
                }
            )

        if n == 1 or n % max(
            1, len(candidates) // 10
        ) == 0:
            logger(
                f"[RESEARCH] Candidate {n}/{len(candidates)} | "
                f"Accepted: {len(results)}"
            )

    results.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    logger(
        f"[RESEARCH] Completed. "
        f"Accepted strategies: {len(results)}"
    )

    return results, features, split


# =====================================================================
# EXPORT
# =====================================================================

def clean_result(r):
    return {
        "name": r["name"],
        "direction": r["direction"],
        "params": r["params"],
        "stability_score": r["stability"],
        "final_score": r["score"],
        "train": {
            k: v
            for k, v in r["train"].items()
            if k != "trades_data"
        },
        "test": {
            k: v
            for k, v in r["test"].items()
            if k != "trades_data"
        },
    }


def export_results(results, folder, symbol):
    folder.mkdir(
        parents=True,
        exist_ok=True
    )

    json_path = (
        folder
        / f"{symbol}_strategy_results.json"
    )

    csv_path = (
        folder
        / f"{symbol}_strategy_ranking.csv"
    )

    trades_path = (
        folder
        / f"{symbol}_top_strategy_trades.csv"
    )

    json_path.write_text(
        json.dumps(
            [clean_result(r) for r in results],
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    rows = []

    for rank, r in enumerate(results, 1):
        tr = r["train"]
        te = r["test"]

        rows.append(
            {
                "rank": rank,
                "score": r["score"],
                "stability": r["stability"],
                "direction": r["direction"],
                "name": r["name"],
                "train_trades": tr["trades"],
                "train_pf": tr["profit_factor"],
                "train_win_rate": tr["win_rate"],
                "train_expectancy_r": tr["expectancy_r"],
                "train_dd_pct": tr["max_drawdown_pct"],
                "test_trades": te["trades"],
                "test_pf": te["profit_factor"],
                "test_win_rate": te["win_rate"],
                "test_expectancy_r": te["expectancy_r"],
                "test_dd_pct": te["max_drawdown_pct"],
                "test_net_r": te["net_r"],
            }
        )

    pd.DataFrame(rows).to_csv(
        csv_path,
        index=False,
        encoding="utf-8-sig",
    )

    if results:
        pd.DataFrame(
            results[0]["test"]["trades_data"]
        ).to_csv(
            trades_path,
            index=False,
            encoding="utf-8-sig",
        )

    return (
        json_path,
        csv_path,
        trades_path,
    )


# =====================================================================
# GUI
# =====================================================================

class App(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title(
            f"{APP_TITLE} v{VERSION}"
        )

        self.geometry("1280x900")
        self.minsize(1100, 760)

        self.vars = {}
        self.indicator_vars = {}

        self.results = []
        self.last_features = None
        self.last_split = None
        self.loaded_data = None

        self.running = False
        self.mt5_connected = False

        self._build_ui()
        self._startup_log()

    # -----------------------------------------------------------------
    # UI
    # -----------------------------------------------------------------

    def _build_ui(self):
        header = ttk.Frame(
            self,
            padding=10
        )
        header.pack(fill="x")

        ttk.Label(
            header,
            text=f"{APP_TITLE} v{VERSION}",
            font=("Segoe UI", 17, "bold"),
        ).pack(side="left")

        ttk.Label(
            header,
            text="RESEARCH ONLY — NO LIVE ORDERS",
            foreground="darkred",
            font=("Segoe UI", 10, "bold"),
        ).pack(side="right")

        status = ttk.LabelFrame(
            self,
            text="MT5 / DATA STATUS",
            padding=8,
        )
        status.pack(
            fill="x",
            padx=10,
            pady=(0, 8)
        )

        self.status_vars = {}

        status_items = [
            ("MT5", "mt5", "NOT CHECKED"),
            ("Terminal", "terminal", "-"),
            ("Account", "account", "-"),
            ("Server", "server", "-"),
            ("Symbol", "symbol", "-"),
            ("Data", "data", "NOT LOADED"),
        ]

        for col, (label, key, value) in enumerate(
            status_items
        ):
            ttk.Label(
                status,
                text=label + ":",
                font=("Segoe UI", 9, "bold"),
            ).grid(
                row=0,
                column=col * 2,
                sticky="e",
                padx=(6, 3),
            )

            v = tk.StringVar(
                value=value
            )
            self.status_vars[key] = v

            ttk.Label(
                status,
                textvariable=v,
                width=18,
            ).grid(
                row=0,
                column=col * 2 + 1,
                sticky="w",
                padx=(0, 8),
            )

        controls = ttk.Frame(
            self,
            padding=(10, 0, 10, 8)
        )
        controls.pack(fill="x")

        self.connect_btn = ttk.Button(
            controls,
            text="🔌 CONNECT MT5",
            command=self.connect_mt5,
        )
        self.connect_btn.pack(
            side="left",
            padx=(0, 5)
        )

        self.load_btn = ttk.Button(
            controls,
            text="📥 LOAD DATA",
            command=self.load_data,
        )
        self.load_btn.pack(
            side="left",
            padx=5
        )

        self.run_btn = ttk.Button(
            controls,
            text="▶ START RESEARCH",
            command=self.start_research,
        )
        self.run_btn.pack(
            side="left",
            padx=5
        )

        self.stop_btn = ttk.Button(
            controls,
            text="■ STOP",
            command=self.stop_research,
            state="disabled",
        )
        self.stop_btn.pack(
            side="left",
            padx=5
        )

        self.copy_btn = ttk.Button(
            controls,
            text="📋 COPY LOG",
            command=self.copy_log,
        )
        self.copy_btn.pack(
            side="right",
            padx=5
        )

        ttk.Button(
            controls,
            text="CLEAR LOG",
            command=self.clear_log,
        ).pack(
            side="right",
            padx=5
        )

        self.progress = ttk.Progressbar(
            controls,
            mode="determinate",
            length=220,
        )
        self.progress.pack(
            side="right",
            padx=10
        )

        self.progress_text = tk.StringVar(
            value="Idle"
        )

        ttk.Label(
            controls,
            textvariable=self.progress_text,
        ).pack(side="right")

        main = ttk.Panedwindow(
            self,
            orient="horizontal"
        )
        main.pack(
            fill="both",
            expand=True,
            padx=10,
            pady=(0, 10),
        )

        left = ttk.Frame(
            main,
            padding=8
        )
        right = ttk.Frame(
            main,
            padding=8
        )

        main.add(left, weight=0)
        main.add(right, weight=1)

        self._build_settings(left)
        self._build_results(right)

        footer = ttk.Label(
            self,
            textvariable=self.progress_text,
            relief="sunken",
            anchor="w",
        )
        footer.pack(
            fill="x",
            side="bottom"
        )

    def _build_settings(self, parent):
        data_box = ttk.LabelFrame(
            parent,
            text="Data / Research Settings",
            padding=8,
        )
        data_box.pack(
            fill="x",
            pady=(0, 8)
        )

        fields = [
            ("Symbol", "symbol", "XAUUSD"),
            ("Timeframe", "timeframe", "M5"),
            ("Start", "start", "2025-01-01"),
            ("End", "end", "2026-08-18"),
            ("Train %", "train_pct", "70"),
            ("Max Candidates", "max_candidates", "300"),
            ("Min Train Trades", "min_train_trades", "80"),
            ("Min Test Trades", "min_test_trades", "25"),
            ("Initial Balance", "initial_balance", "500"),
            ("Risk % / Trade", "risk_pct", "1.0"),
            ("Max Spread Points", "max_spread_points", "80"),
            ("Commission R", "commission_r_per_trade", "0.02"),
            ("Slippage R", "slippage_r_per_trade", "0.03"),
            ("RR Min", "rr_min", "1.4"),
            ("RR Max", "rr_max", "2.2"),
            ("RR Step", "rr_step", "0.4"),
            ("SL Min ATR", "sl_min", "1.0"),
            ("SL Max ATR", "sl_max", "2.0"),
            ("SL Step", "sl_step", "0.5"),
            ("Max Hold Bars", "max_hold_bars", "24"),
        ]

        for row, (label, key, default) in enumerate(fields):
            ttk.Label(
                data_box,
                text=label,
            ).grid(
                row=row,
                column=0,
                sticky="w",
                pady=2,
            )

            v = tk.StringVar(
                value=default
            )
            self.vars[key] = v

            ttk.Entry(
                data_box,
                textvariable=v,
                width=16,
            ).grid(
                row=row,
                column=1,
                sticky="ew",
                pady=2,
            )

        data_box.columnconfigure(
            1,
            weight=1
        )

        ind_box = ttk.LabelFrame(
            parent,
            text="Indicators / Filters",
            padding=8,
        )
        ind_box.pack(
            fill="x",
            pady=(0, 8)
        )

        defaults = {
            "EMA": True,
            "RSI": True,
            "MACD": True,
            "ADX": True,
            "ATR": True,
            "Bollinger": False,
            "Stochastic": False,
            "Ichimoku": False,
            "Price Action": True,
            "Spread": True,
            "Session": True,
        }

        for i, name in enumerate(
            INDICATORS
        ):
            v = tk.BooleanVar(
                value=defaults[name]
            )
            self.indicator_vars[name] = v

            ttk.Checkbutton(
                ind_box,
                text=name,
                variable=v,
            ).grid(
                row=i // 2,
                column=i % 2,
                sticky="w",
                pady=2,
            )

        note = ttk.Label(
            parent,
            text=(
                "Workflow:\n"
                "1) CONNECT MT5\n"
                "2) LOAD DATA\n"
                "3) START RESEARCH\n"
                "4) Copy LOG if anything looks wrong"
            ),
            justify="left",
        )
        note.pack(
            fill="x",
            pady=4
        )

    def _build_results(self, parent):
        result_box = ttk.LabelFrame(
            parent,
            text="Strategy Ranking",
            padding=6,
        )
        result_box.pack(
            fill="both",
            expand=True
        )

        cols = (
            "rank", "score", "stability",
            "direction", "train_pf", "test_pf",
            "test_wr", "test_exp",
            "test_dd", "trades", "name"
        )

        self.tree = ttk.Treeview(
            result_box,
            columns=cols,
            show="headings",
        )

        heads = {
            "rank": "#",
            "score": "Score",
            "stability": "Stability",
            "direction": "Dir",
            "train_pf": "Train PF",
            "test_pf": "OOS PF",
            "test_wr": "OOS Win%",
            "test_exp": "OOS Exp(R)",
            "test_dd": "OOS DD%",
            "trades": "OOS Trades",
            "name": "Strategy",
        }

        widths = {
            "rank": 45,
            "score": 70,
            "stability": 80,
            "direction": 60,
            "train_pf": 75,
            "test_pf": 75,
            "test_wr": 80,
            "test_exp": 90,
            "test_dd": 75,
            "trades": 80,
            "name": 440,
        }

        for c in cols:
            self.tree.heading(
                c,
                text=heads[c]
            )
            self.tree.column(
                c,
                width=widths[c],
                anchor="center",
            )

        self.tree.column(
            "name",
            anchor="w"
        )

        self.tree.pack(
            side="left",
            fill="both",
            expand=True
        )

        scroll = ttk.Scrollbar(
            result_box,
            orient="vertical",
            command=self.tree.yview,
        )
        scroll.pack(
            side="right",
            fill="y"
        )

        self.tree.configure(
            yscrollcommand=scroll.set
        )

        self.tree.bind(
            "<<TreeviewSelect>>",
            self.show_selected,
        )

        bottom = ttk.LabelFrame(
            parent,
            text="Log / Selected Strategy",
            padding=6,
        )
        bottom.pack(
            fill="both",
            expand=False,
            pady=(8, 0)
        )

        self.log_text = tk.Text(
            bottom,
            height=17,
            wrap="word",
            font=("Consolas", 9),
        )

        self.log_text.pack(
            fill="both",
            expand=True,
            side="left"
        )

        scroll2 = ttk.Scrollbar(
            bottom,
            orient="vertical",
            command=self.log_text.yview,
        )

        scroll2.pack(
            side="right",
            fill="y"
        )

        self.log_text.configure(
            yscrollcommand=scroll2.set
        )

    # -----------------------------------------------------------------
    # LOG
    # -----------------------------------------------------------------

    def _startup_log(self):
        self.log(
            f"[SYSTEM] {APP_TITLE} v{VERSION} started."
        )
        self.log(
            "[SYSTEM] Research-only mode. "
            "No live orders will be sent."
        )

        if mt5 is None:
            self.log(
                "[ERROR] MetaTrader5 Python package is NOT installed."
            )
            self.status_vars["mt5"].set(
                "PACKAGE MISSING"
            )
        else:
            self.log(
                "[SYSTEM] MetaTrader5 Python package detected."
            )
            self.status_vars["mt5"].set(
                "NOT CONNECTED"
            )

        self.log(
            "[SYSTEM] Click CONNECT MT5 to test the terminal."
        )

    def log(self, message):
        timestamp = datetime.now().strftime(
            "%H:%M:%S"
        )

        line = f"{timestamp} {message}\n"

        def write():
            self.log_text.insert(
                "end",
                line
            )
            self.log_text.see("end")

        self.after(
            0,
            write
        )

    def clear_log(self):
        self.log_text.delete(
            "1.0",
            "end"
        )

    def copy_log(self):
        text = self.log_text.get(
            "1.0",
            "end"
        ).strip()

        if not text:
            messagebox.showinfo(
                "COPY LOG",
                "Log is empty."
            )
            return

        self.clipboard_clear()
        self.clipboard_append(text)
        self.update()

        self.status(
            "Log copied to clipboard."
        )

    # -----------------------------------------------------------------
    # STATUS
    # -----------------------------------------------------------------

    def status(self, text):
        self.progress_text.set(text)

    # -----------------------------------------------------------------
    # MT5
    # -----------------------------------------------------------------

    def connect_mt5(self):
        if self.running:
            return

        self.connect_btn.configure(
            state="disabled"
        )

        self.log(
            "[MT5] Testing connection..."
        )

        thread = threading.Thread(
            target=self._connect_worker,
            daemon=True,
        )
        thread.start()

    def _connect_worker(self):
        try:
            snapshot = mt5_snapshot(
                self.vars["symbol"].get().strip()
            )

            terminal = snapshot["terminal"]
            account = snapshot["account"]
            symbol = snapshot["symbol"]
            tick = snapshot["tick"]

            self.mt5_connected = True

            self.after(
                0,
                lambda: self.status_vars["mt5"].set(
                    "CONNECTED ✓"
                )
            )

            self.after(
                0,
                lambda: self.status_vars["terminal"].set(
                    str(
                        getattr(
                            terminal,
                            "name",
                            "MT5"
                        )
                    )[:18]
                )
            )

            if account:
                self.after(
                    0,
                    lambda: self.status_vars["account"].set(
                        str(
                            getattr(
                                account,
                                "login",
                                "-"
                            )
                        )
                    )
                )

                self.after(
                    0,
                    lambda: self.status_vars["server"].set(
                        str(
                            getattr(
                                account,
                                "server",
                                "-"
                            )
                        )[:18]
                    )
                )

            self.after(
                0,
                lambda: self.status_vars["symbol"].set(
                    "AVAILABLE ✓"
                )
            )

            self.log(
                "[MT5] CONNECTION SUCCESS ✓"
            )

            if tick:
                self.log(
                    f"[MT5] Current tick: "
                    f"Bid={safe_float(tick.bid):.3f} "
                    f"Ask={safe_float(tick.ask):.3f}"
                )

            self.log(
                "[MT5] Symbol is available."
            )

        except Exception as e:
            self.mt5_connected = False

            self.after(
                0,
                lambda: self.status_vars["mt5"].set(
                    "ERROR ✗"
                )
            )

            self.log(
                f"[MT5] CONNECTION FAILED: {e}"
            )

            self.after(
                0,
                lambda: messagebox.showerror(
                    "MT5 Connection",
                    str(e)
                )
            )

        finally:
            self.after(
                0,
                lambda: self.connect_btn.configure(
                    state="normal"
                )
            )

    # -----------------------------------------------------------------
    # DATA
    # -----------------------------------------------------------------

    def load_data(self):
        if self.running:
            return

        try:
            cfg = self.read_config()
        except Exception as e:
            messagebox.showerror(
                "Configuration",
                str(e)
            )
            return

        self.load_btn.configure(
            state="disabled"
        )

        self.status(
            "Loading historical data..."
        )

        self.log(
            "[DATA] Starting data download..."
        )

        thread = threading.Thread(
            target=self._load_worker,
            args=(cfg,),
            daemon=True,
        )
        thread.start()

    def _load_worker(self, cfg):
        try:
            df = load_rates(
                cfg.symbol,
                cfg.timeframe,
                cfg.start,
                cfg.end,
                self.log,
            )

            self.loaded_data = df

            self.after(
                0,
                lambda: self.status_vars["data"].set(
                    f"{len(df):,} bars ✓"
                )
            )

            self.after(
                0,
                lambda: self.status_vars["symbol"].set(
                    f"{cfg.symbol} ✓"
                )
            )

            self.log(
                "[DATA] LOAD COMPLETE ✓"
            )

            self.status(
                f"Data ready: {len(df):,} bars."
            )

        except Exception as e:
            self.loaded_data = None

            self.log(
                f"[DATA] LOAD FAILED: {e}"
            )

            self.after(
                0,
                lambda: self.status_vars["data"].set(
                    "ERROR ✗"
                )
            )

            self.after(
                0,
                lambda: messagebox.showerror(
                    "Data Error",
                    str(e)
                )
            )

        finally:
            self.after(
                0,
                lambda: self.load_btn.configure(
                    state="normal"
                )
            )

    # -----------------------------------------------------------------
    # RESEARCH
    # -----------------------------------------------------------------

    def start_research(self):
        if self.running:
            return

        try:
            cfg = self.read_config()
            selected = self.selected_indicators()

            if not selected:
                raise ValueError(
                    "Select at least one indicator/filter."
                )

        except Exception as e:
            messagebox.showerror(
                "Configuration",
                str(e)
            )
            return

        if self.loaded_data is None:
            answer = messagebox.askyesno(
                "Data not loaded",
                "Historical data is not loaded.\n\n"
                "Load data automatically now?"
            )

            if not answer:
                return

            self.load_data()
            return

        self.running = True

        self.run_btn.configure(
            state="disabled"
        )
        self.connect_btn.configure(
            state="disabled"
        )
        self.load_btn.configure(
            state="disabled"
        )
        self.stop_btn.configure(
            state="normal"
        )

        self.progress["value"] = 0
        self.progress["maximum"] = 1

        self.clear_log()

        self.log(
            "[RESEARCH] ======================================="
        )
        self.log(
            "[RESEARCH] STARTED"
        )
        self.log(
            f"[RESEARCH] Symbol={cfg.symbol} "
            f"Timeframe={cfg.timeframe}"
        )
        self.log(
            f"[RESEARCH] Indicators: {', '.join(selected)}"
        )

        thread = threading.Thread(
            target=self._research_worker,
            args=(cfg, selected),
            daemon=True,
        )
        thread.start()

    def _research_worker(self, cfg, selected):
        try:
            self.log(
                "[RESEARCH] Using already loaded MT5 data."
            )

            results, features, split = run_research(
                self.loaded_data,
                cfg,
                selected,
                self.log,
                self.update_progress,
            )

            self.results = results
            self.last_features = features
            self.last_split = split

            self.after(
                0,
                self.populate_results
            )

            if not results:
                self.log(
                    "[RESEARCH] NO ACCEPTED STRATEGY."
                )
                self.log(
                    "[RESEARCH] Try more history, "
                    "less restrictive filters, "
                    "or lower minimum trade counts."
                )
            else:
                top = results[0]

                self.log(
                    "[RESEARCH] ======================================="
                )
                self.log(
                    f"[RESULT] TOP SCORE={top['score']:.2f}"
                )
                self.log(
                    f"[RESULT] Stability="
                    f"{top['stability']:.1f}/100"
                )
                self.log(
                    f"[RESULT] OOS PF="
                    f"{top['test']['profit_factor']:.2f}"
                )
                self.log(
                    f"[RESULT] OOS Win Rate="
                    f"{top['test']['win_rate']:.2f}%"
                )
                self.log(
                    f"[RESULT] OOS Expectancy="
                    f"{top['test']['expectancy_r']:.4f}R"
                )
                self.log(
                    f"[RESULT] OOS DD="
                    f"{top['test']['max_drawdown_pct']:.2f}%"
                )
                self.log(
                    f"[RESULT] OOS Trades="
                    f"{top['test']['trades']}"
                )

                out = (
                    Path.cwd()
                    / "research_results"
                )

                paths = export_results(
                    results,
                    out,
                    cfg.symbol,
                )

                self.log(
                    f"[EXPORT] Folder: {out}"
                )
                self.log(
                    f"[EXPORT] {paths[0].name}"
                )
                self.log(
                    f"[EXPORT] {paths[1].name}"
                )
                self.log(
                    f"[EXPORT] {paths[2].name}"
                )

        except Exception as e:
            self.log(
                f"[RESEARCH] ERROR: {e}"
            )

            self.after(
                0,
                lambda: messagebox.showerror(
                    "Research Error",
                    str(e)
                )
            )

        finally:
            self.after(
                0,
                self.research_finished
            )

    def update_progress(self, done, total):
        def update():
            self.progress["maximum"] = max(
                1,
                total
            )
            self.progress["value"] = done

            pct = (
                done / total * 100
                if total
                else 0
            )

            self.progress_text.set(
                f"Research: {done}/{total} "
                f"({pct:.1f}%)"
            )

        self.after(
            0,
            update
        )

    def stop_research(self):
        """
        v2.1 uses a safe UI stop request placeholder.
        The current backtest loop is intentionally allowed to finish its
        current operation to avoid corrupting result state.
        """
        if self.running:
            self.log(
                "[RESEARCH] STOP requested. "
                "Current operation will finish safely."
            )
            self.status(
                "Stop requested..."
            )

    def research_finished(self):
        self.running = False

        self.run_btn.configure(
            state="normal"
        )
        self.connect_btn.configure(
            state="normal"
        )
        self.load_btn.configure(
            state="normal"
        )
        self.stop_btn.configure(
            state="disabled"
        )

        self.progress_text.set(
            "Research finished."
        )

    # -----------------------------------------------------------------
    # RESULTS
    # -----------------------------------------------------------------

    def populate_results(self):
        self.tree.delete(
            *self.tree.get_children()
        )

        for rank, r in enumerate(
            self.results,
            1
        ):
            tr = r["train"]
            te = r["test"]

            self.tree.insert(
                "",
                "end",
                iid=str(rank - 1),
                values=(
                    rank,
                    f"{r['score']:.2f}",
                    f"{r['stability']:.1f}",
                    r["direction"],
                    f"{tr['profit_factor']:.2f}",
                    f"{te['profit_factor']:.2f}",
                    f"{te['win_rate']:.1f}",
                    f"{te['expectancy_r']:.3f}",
                    f"{te['max_drawdown_pct']:.1f}",
                    te["trades"],
                    r["name"],
                ),
            )

    def show_selected(self, _event=None):
        selected = self.tree.selection()

        if not selected or not self.results:
            return

        idx = int(
            selected[0]
        )

        if idx >= len(self.results):
            return

        r = self.results[idx]

        self.log(
            "------------------------------------------------"
        )
        self.log(
            f"[SELECTED] {r['name']}"
        )
        self.log(
            f"[SELECTED] Score={r['score']:.2f}"
        )
        self.log(
            f"[SELECTED] Stability="
            f"{r['stability']:.1f}/100"
        )
        self.log(
            f"[SELECTED] Train: "
            f"Trades={r['train']['trades']} "
            f"PF={r['train']['profit_factor']:.2f}"
        )
        self.log(
            f"[SELECTED] OOS: "
            f"Trades={r['test']['trades']} "
            f"PF={r['test']['profit_factor']:.2f} "
            f"Exp={r['test']['expectancy_r']:.3f}R "
            f"DD={r['test']['max_drawdown_pct']:.2f}%"
        )
        self.log(
            "[SELECTED] Parameters: "
            + json.dumps(
                r["params"],
                ensure_ascii=False
            )
        )

    # -----------------------------------------------------------------
    # CONFIG
    # -----------------------------------------------------------------

    def read_config(self):
        def num(key, cast=float):
            return cast(
                self.vars[key].get().strip()
            )

        cfg = Config(
            symbol=self.vars["symbol"].get().strip(),
            timeframe=self.vars["timeframe"].get().strip().upper(),
            start=self.vars["start"].get().strip(),
            end=self.vars["end"].get().strip(),
            train_pct=num("train_pct", int),
            max_candidates=num(
                "max_candidates",
                int
            ),
            min_train_trades=num(
                "min_train_trades",
                int
            ),
            min_test_trades=num(
                "min_test_trades",
                int
            ),
            initial_balance=num(
                "initial_balance"
            ),
            risk_pct=num("risk_pct"),
            max_spread_points=num(
                "max_spread_points"
            ),
            commission_r_per_trade=num(
                "commission_r_per_trade"
            ),
            slippage_r_per_trade=num(
                "slippage_r_per_trade"
            ),
            rr_min=num("rr_min"),
            rr_max=num("rr_max"),
            rr_step=num("rr_step"),
            sl_min=num("sl_min"),
            sl_max=num("sl_max"),
            sl_step=num("sl_step"),
            max_hold_bars=num(
                "max_hold_bars",
                int
            ),
        )

        if cfg.timeframe not in TIMEFRAMES:
            raise ValueError(
                "Timeframe must be M1, M5, M15, M30 or H1."
            )

        if not (
            30 <= cfg.train_pct <= 90
        ):
            raise ValueError(
                "Train % must be between 30 and 90."
            )

        if cfg.max_candidates < 1:
            raise ValueError(
                "Max Candidates must be >= 1."
            )

        if cfg.min_train_trades < 10:
            raise ValueError(
                "Min Train Trades must be >= 10."
            )

        if cfg.min_test_trades < 5:
            raise ValueError(
                "Min Test Trades must be >= 5."
            )

        if cfg.rr_min <= 0:
            raise ValueError(
                "RR Min must be > 0."
            )

        if cfg.rr_max < cfg.rr_min:
            raise ValueError(
                "RR Max must be >= RR Min."
            )

        if cfg.sl_min <= 0:
            raise ValueError(
                "SL Min ATR must be > 0."
            )

        if cfg.sl_max < cfg.sl_min:
            raise ValueError(
                "SL Max ATR must be >= SL Min ATR."
            )

        return cfg

    def selected_indicators(self):
        return [
            name
            for name, var
            in self.indicator_vars.items()
            if var.get()
        ]


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
