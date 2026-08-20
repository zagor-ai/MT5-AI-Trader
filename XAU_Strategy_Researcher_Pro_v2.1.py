# -*- coding: utf-8 -*-
"""
XAU Strategy Researcher Pro v2.1
================================

Research-only engine for XAUUSD / MetaTrader 5.

IMPORTANT:
    This application NEVER sends trading orders.
    MT5 is used only for terminal diagnostics and historical data.

Main features:
    - MT5 diagnostics
    - Historical data loading
    - Indicator selection
    - Candidate generation
    - Backtesting
    - Train / OOS split
    - Stability score
    - Overfitting penalty
    - Strategy ranking
    - Progress tracking
    - Real stop request
    - Copyable log
    - JSON / CSV export

Required:
    Python 3.10+
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
import sys
import threading
import traceback
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from itertools import product

import tkinter as tk
from tkinter import ttk, messagebox

import numpy as np
import pandas as pd

try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None


# ============================================================
# APPLICATION
# ============================================================

APP_TITLE = "XAU Strategy Researcher Pro"
VERSION = "2.1"

BASE_DIR = Path(__file__).resolve().parent
RESULTS_DIR = BASE_DIR / "research_results"

TIMEFRAMES = {
    "M1": "TIMEFRAME_M1",
    "M5": "TIMEFRAME_M5",
    "M15": "TIMEFRAME_M15",
    "M30": "TIMEFRAME_M30",
    "H1": "TIMEFRAME_H1",
}

INDICATORS = [
    "EMA",
    "RSI",
    "MACD",
    "ADX",
    "ATR",
    "Bollinger",
    "Stochastic",
    "Ichimoku",
    "Price Action",
    "Spread",
    "Session",
]


# ============================================================
# CONFIG
# ============================================================

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


# ============================================================
# HELPERS
# ============================================================

def finite(value) -> bool:
    try:
        return math.isfinite(float(value))
    except Exception:
        return False


def safe_float(value, default=0.0):
    try:
        value = float(value)
        return value if math.isfinite(value) else default
    except Exception:
        return default


def safe_int(value, default=0):
    try:
        return int(value)
    except Exception:
        return default


def now_text():
    return datetime.now().strftime("%H:%M:%S")


def mt5_error_text():
    if mt5 is None:
        return "MetaTrader5 package unavailable"

    try:
        return str(mt5.last_error())
    except Exception:
        return "Unknown MT5 error"


# ============================================================
# MT5 SERVICE
# ============================================================

class MT5Service:

    def __init__(self):
        self.connected = False

    def initialize(self):
        if mt5 is None:
            raise RuntimeError(
                "MetaTrader5 Python package is not installed.\n\n"
                "Install with:\n"
                "python -m pip install MetaTrader5 pandas numpy"
            )

        if self.connected:
            return

        ok = mt5.initialize()

        if not ok:
            self.connected = False
            raise RuntimeError(
                f"mt5.initialize() failed.\n"
                f"Last error: {mt5_error_text()}"
            )

        self.connected = True

    def shutdown(self):
        if mt5 is not None:
            try:
                mt5.shutdown()
            except Exception:
                pass

        self.connected = False

    def diagnostics(self, symbol):
        self.initialize()

        terminal = mt5.terminal_info()
        account = mt5.account_info()

        if terminal is None:
            raise RuntimeError(
                f"terminal_info() failed.\n"
                f"Last error: {mt5_error_text()}"
            )

        symbol_info = mt5.symbol_info(symbol)

        if symbol_info is None:
            similar = []

            try:
                all_symbols = mt5.symbols_get()
                if all_symbols:
                    upper = symbol.upper()

                    for item in all_symbols:
                        name = getattr(item, "name", "")
                        if upper in name.upper() or "XAU" in name.upper():
                            similar.append(name)

                    similar = similar[:15]
            except Exception:
                pass

            extra = ""
            if similar:
                extra = (
                    "\n\nPossible symbols:\n"
                    + ", ".join(similar)
                )

            raise RuntimeError(
                f"Symbol '{symbol}' was not found in this MT5 terminal."
                + extra
            )

        selected = mt5.symbol_select(symbol, True)

        if not selected:
            raise RuntimeError(
                f"symbol_select('{symbol}', True) failed.\n"
                f"Last error: {mt5_error_text()}"
            )

        tick = mt5.symbol_info_tick(symbol)

        return {
            "terminal": terminal,
            "account": account,
            "symbol": symbol_info,
            "tick": tick,
        }

    def load_rates(self, symbol, timeframe, start, end, logger):
        self.initialize()

        logger("[MT5] Initializing terminal...")

        terminal = mt5.terminal_info()
        account = mt5.account_info()

        if terminal:
            logger(
                f"[MT5] Terminal: "
                f"{getattr(terminal, 'name', 'Unknown')}"
            )
            logger(
                f"[MT5] Build: "
                f"{getattr(terminal, 'build', 'Unknown')}"
            )

        if account:
            logger(
                f"[MT5] Account: "
                f"{getattr(account, 'login', 'Unknown')}"
            )
            logger(
                f"[MT5] Server: "
                f"{getattr(account, 'server', 'Unknown')}"
            )

        symbol_info = mt5.symbol_info(symbol)

        if symbol_info is None:
            raise RuntimeError(
                f"Symbol '{symbol}' is not available."
            )

        if not mt5.symbol_select(symbol, True):
            raise RuntimeError(
                f"Cannot select {symbol}.\n"
                f"MT5 error: {mt5_error_text()}"
            )

        logger(f"[MT5] Symbol: {symbol} AVAILABLE ✓")

        tick = mt5.symbol_info_tick(symbol)

        if tick:
            logger(
                f"[MT5] Tick: "
                f"Bid={safe_float(tick.bid):.3f} "
                f"Ask={safe_float(tick.ask):.3f}"
            )

        try:
            start_dt = datetime.strptime(
                start, "%Y-%m-%d"
            ).replace(tzinfo=timezone.utc)

            end_dt = (
                datetime.strptime(
                    end, "%Y-%m-%d"
                )
                + timedelta(days=1)
            ).replace(tzinfo=timezone.utc)

        except ValueError:
            raise RuntimeError(
                "Date format must be YYYY-MM-DD."
            )

        if timeframe not in TIMEFRAMES:
            raise RuntimeError(
                f"Unsupported timeframe: {timeframe}"
            )

        tf = getattr(
            mt5,
            TIMEFRAMES[timeframe]
        )

        logger(
            f"[DATA] Requesting "
            f"{symbol} {timeframe}: "
            f"{start} -> {end}"
        )

        rates = mt5.copy_rates_range(
            symbol,
            tf,
            start_dt,
            end_dt,
        )

        if rates is None:
            raise RuntimeError(
                "MT5 returned None.\n"
                f"Last error: {mt5_error_text()}"
            )

        if len(rates) == 0:
            raise RuntimeError(
                "MT5 returned 0 bars.\n"
                "Make sure the terminal is open and "
                "the requested history is available."
            )

        logger(
            f"[DATA] MT5 returned "
            f"{len(rates):,} raw bars."
        )

        df = pd.DataFrame(rates)

        required = [
            "time",
            "open",
            "high",
            "low",
            "close",
        ]

        missing = [
            c for c in required
            if c not in df.columns
        ]

        if missing:
            raise RuntimeError(
                "MT5 data missing columns: "
                + ", ".join(missing)
            )

        df["time"] = pd.to_datetime(
            df["time"],
            unit="s",
            utc=True,
        )

        df = (
            df.drop_duplicates(
                subset=["time"]
            )
            .sort_values("time")
            .set_index("time")
        )

        for col in [
            "open",
            "high",
            "low",
            "close",
        ]:
            df[col] = pd.to_numeric(
                df[col],
                errors="coerce",
            )

        if "spread" in df.columns:
            df["spread"] = pd.to_numeric(
                df["spread"],
                errors="coerce",
            ).fillna(0.0)

            spread_available = True
        else:
            df["spread"] = 0.0
            spread_available = False

        df["spread_available"] = spread_available

        before = len(df)

        df = df.dropna(
            subset=[
                "open",
                "high",
                "low",
                "close",
            ]
        )

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
                f"Only {len(df):,} valid bars available.\n"
                "At least 1000 bars are recommended."
            )

        logger(
            f"[DATA] Valid bars: "
            f"{len(df):,} ✓"
        )

        if removed:
            logger(
                f"[DATA] Invalid rows removed: "
                f"{removed:,}"
            )

        logger(
            "[DATA] First bar: "
            + df.index[0].strftime(
                "%Y-%m-%d %H:%M:%S UTC"
            )
        )

        logger(
            "[DATA] Last bar: "
            + df.index[-1].strftime(
                "%Y-%m-%d %H:%M:%S UTC"
            )
        )

        if spread_available:
            logger(
                "[DATA] Historical spread: AVAILABLE ✓"
            )
        else:
            logger(
                "[WARN] Historical spread column "
                "unavailable."
            )

        return df


# ============================================================
# INDICATORS
# ============================================================

def ema(series, period):
    return series.ewm(
        span=period,
        adjust=False,
        min_periods=period,
    ).mean()


def rsi(series, period=14):
    delta = series.diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(
        alpha=1 / period,
        adjust=False,
        min_periods=period,
    ).mean()

    avg_loss = loss.ewm(
        alpha=1 / period,
        adjust=False,
        min_periods=period,
    ).mean()

    rs = avg_gain / avg_loss.replace(
        0,
        np.nan,
    )

    result = 100 - (
        100 / (1 + rs)
    )

    return result.fillna(50.0)


def true_range(df):
    previous_close = df["close"].shift(1)

    return pd.concat(
        [
            df["high"] - df["low"],
            (
                df["high"]
                - previous_close
            ).abs(),
            (
                df["low"]
                - previous_close
            ).abs(),
        ],
        axis=1,
    ).max(axis=1)


def atr(df, period=14):
    return true_range(df).ewm(
        alpha=1 / period,
        adjust=False,
        min_periods=period,
    ).mean()


def adx(df, period=14):
    up = df["high"].diff()
    down = -df["low"].diff()

    plus_dm = pd.Series(
        np.where(
            (up > down) & (up > 0),
            up,
            0.0,
        ),
        index=df.index,
    )

    minus_dm = pd.Series(
        np.where(
            (down > up) & (down > 0),
            down,
            0.0,
        ),
        index=df.index,
    )

    tr = true_range(df)

    atr_n = tr.ewm(
        alpha=1 / period,
        adjust=False,
        min_periods=period,
    ).mean()

    plus_di = (
        100
        * plus_dm.ewm(
            alpha=1 / period,
            adjust=False,
            min_periods=period,
        ).mean()
        / atr_n
    )

    minus_di = (
        100
        * minus_dm.ewm(
            alpha=1 / period,
            adjust=False,
            min_periods=period,
        ).mean()
        / atr_n
    )

    denominator = (
        plus_di + minus_di
    ).replace(0, np.nan)

    dx = (
        100
        * (plus_di - minus_di).abs()
        / denominator
    )

    adx_value = dx.ewm(
        alpha=1 / period,
        adjust=False,
        min_periods=period,
    ).mean()

    return (
        adx_value.fillna(0),
        plus_di.fillna(0),
        minus_di.fillna(0),
    )


def macd(series):
    fast = ema(series, 12)
    slow = ema(series, 26)

    line = fast - slow
    signal = ema(line, 9)
    histogram = line - signal

    return line, signal, histogram


def bollinger(series, period=20, multiplier=2):
    middle = series.rolling(
        period,
        min_periods=period,
    ).mean()

    std = series.rolling(
        period,
        min_periods=period,
    ).std()

    upper = middle + (
        multiplier * std
    )

    lower = middle - (
        multiplier * std
    )

    return middle, upper, lower


def stochastic(df, period=14, d_period=3):
    low = df["low"].rolling(
        period,
        min_periods=period,
    ).min()

    high = df["high"].rolling(
        period,
        min_periods=period,
    ).max()

    denominator = (
        high - low
    ).replace(0, np.nan)

    k = (
        100
        * (df["close"] - low)
        / denominator
    )

    d = k.rolling(
        d_period,
        min_periods=d_period,
    ).mean()

    return (
        k.fillna(50),
        d.fillna(50),
    )


def build_features(df, logger=None):
    if logger:
        logger(
            "[FEATURES] Calculating indicators..."
        )

    x = df.copy()

    for period in [
        9,
        20,
        21,
        50,
        100,
        200,
    ]:
        x[f"ema{period}"] = ema(
            x["close"],
            period,
        )

    x["rsi14"] = rsi(
        x["close"],
        14,
    )

    x["atr14"] = atr(
        x,
        14,
    )

    x["atr_pct"] = (
        100
        * x["atr14"]
        / x["close"].replace(
            0,
            np.nan,
        )
    )

    (
        x["adx14"],
        x["plus_di"],
        x["minus_di"],
    ) = adx(
        x,
        14,
    )

    (
        x["macd"],
        x["macd_sig"],
        x["macd_hist"],
    ) = macd(
        x["close"]
    )

    (
        x["bb_mid"],
        x["bb_up"],
        x["bb_lo"],
    ) = bollinger(
        x["close"],
        20,
        2,
    )

    (
        x["stoch_k"],
        x["stoch_d"],
    ) = stochastic(
        x,
        14,
        3,
    )

    conversion = (
        x["high"]
        .rolling(
            9,
            min_periods=9,
        )
        .max()
        +
        x["low"]
        .rolling(
            9,
            min_periods=9,
        )
        .min()
    ) / 2

    base = (
        x["high"]
        .rolling(
            26,
            min_periods=26,
        )
        .max()
        +
        x["low"]
        .rolling(
            26,
            min_periods=26,
        )
        .min()
    ) / 2

    span_b = (
        x["high"]
        .rolling(
            52,
            min_periods=52,
        )
        .max()
        +
        x["low"]
        .rolling(
            52,
            min_periods=52,
        )
        .min()
    ) / 2

    x["ichi_conv"] = conversion
    x["ichi_base"] = base
    x["ichi_a"] = (
        conversion + base
    ) / 2
    x["ichi_b"] = span_b

    candle_range = (
        x["high"] - x["low"]
    ).replace(
        0,
        np.nan,
    )

    x["body_pct"] = (
        (
            x["close"]
            - x["open"]
        ).abs()
        / candle_range
    )

    x["upper_wick_pct"] = (
        x["high"]
        - x[["open", "close"]].max(
            axis=1
        )
    ) / candle_range

    x["lower_wick_pct"] = (
        x[["open", "close"]].min(
            axis=1
        )
        - x["low"]
    ) / candle_range

    x["bull"] = (
        x["close"] > x["open"]
    )

    x["bear"] = (
        x["close"] < x["open"]
    )

    x["hour"] = x.index.hour

    for column in [
        "close",
        "high",
        "low",
        "ema20",
        "ema50",
        "ema100",
        "ema200",
    ]:
        x[f"prev_{column}"] = (
            x[column].shift(1)
        )

    if logger:
        logger(
            "[FEATURES] Indicators ready ✓"
        )

    return x


# ============================================================
# SIGNAL ENGINE
# ============================================================

def session_ok(hour, session):
    if session == "All":
        return True

    if session == "London":
        return 8 <= hour < 17

    if session == "NY":
        return 13 <= hour < 22

    if session == "Both":
        return (
            8 <= hour < 17
            or
            13 <= hour < 22
        )

    return True


def signal_at(
    df,
    index,
    direction,
    params,
    selected,
):
    row = df.iloc[index]
    previous = df.iloc[index - 1]

    if (
        not finite(row["atr14"])
        or row["atr14"] <= 0
    ):
        return False

    if "EMA" in selected:
        fast = params["fast"]
        slow = params["slow"]

        fast_value = row[
            f"ema{fast}"
        ]

        slow_value = row[
            f"ema{slow}"
        ]

        previous_fast = previous[
            f"ema{fast}"
        ]

        if not all(
            finite(v)
            for v in [
                fast_value,
                slow_value,
                previous_fast,
            ]
        ):
            return False

        if direction == "BUY":
            if not (
                fast_value > slow_value
                and
                fast_value > previous_fast
            ):
                return False
        else:
            if not (
                fast_value < slow_value
                and
                fast_value < previous_fast
            ):
                return False

        if abs(
            row["close"] - fast_value
        ) > (
            params["pullback"]
            * row["atr14"]
        ):
            return False

    if "RSI" in selected:
        low = params["rsi_lo"]
        high = params["rsi_hi"]

        value = row["rsi14"]

        if direction == "BUY":
            if not low <= value <= high:
                return False
        else:
            if not (
                100 - high
                <= value
                <= 100 - low
            ):
                return False

    if "MACD" in selected:
        if direction == "BUY":
            if not (
                row["macd"]
                > row["macd_sig"]
                and
                row["macd_hist"] > 0
            ):
                return False
        else:
            if not (
                row["macd"]
                < row["macd_sig"]
                and
                row["macd_hist"] < 0
            ):
                return False

    if "ADX" in selected:
        if row["adx14"] < params["adx"]:
            return False

        if direction == "BUY":
            if row["plus_di"] <= row["minus_di"]:
                return False
        else:
            if row["minus_di"] <= row["plus_di"]:
                return False

    if "ATR" in selected:
        if not (
            params["atr_min"]
            <= row["atr_pct"]
            <= params["atr_max"]
        ):
            return False

    if "Bollinger" in selected:
        if direction == "BUY":
            if not (
                previous["close"]
                <= previous["bb_mid"]
                and
                row["close"]
                > row["bb_mid"]
            ):
                return False
        else:
            if not (
                previous["close"]
                >= previous["bb_mid"]
                and
                row["close"]
                < row["bb_mid"]
            ):
                return False

    if "Stochastic" in selected:
        if direction == "BUY":
            if not (
                row["stoch_k"]
                > row["stoch_d"]
                and
                row["stoch_k"]
                < params["stoch_hi"]
            ):
                return False
        else:
            if not (
                row["stoch_k"]
                < row["stoch_d"]
                and
                row["stoch_k"]
                > 100 - params["stoch_hi"]
            ):
                return False

    if "Ichimoku" in selected:
        cloud_top = max(
            row["ichi_a"],
            row["ichi_b"],
        )

        cloud_bottom = min(
            row["ichi_a"],
            row["ichi_b"],
        )

        if not all(
            finite(v)
            for v in [
                cloud_top,
                cloud_bottom,
            ]
        ):
            return False

        if direction == "BUY":
            if not (
                row["close"] > cloud_top
                and
                row["ichi_conv"]
                > row["ichi_base"]
            ):
                return False
        else:
            if not (
                row["close"] < cloud_bottom
                and
                row["ichi_conv"]
                < row["ichi_base"]
            ):
                return False

    if "Price Action" in selected:
        if row["body_pct"] < params["body"]:
            return False

        if direction == "BUY":
            if not (
                row["bull"]
                and
                row["close"]
                > previous["high"]
            ):
                return False
        else:
            if not (
                row["bear"]
                and
                row["close"]
                < previous["low"]
            ):
                return False

    if "Spread" in selected:
        if (
            safe_float(row["spread"])
            > params["spread"]
        ):
            return False

    if "Session" in selected:
        if not session_ok(
            int(row["hour"]),
            params["session"],
        ):
            return False

    return True


# ============================================================
# BACKTEST
# ============================================================

def summarize_trades(
    trades,
    cfg,
):
    values = np.array(
        [
            t["net_r"]
            for t in trades
        ],
        dtype=float,
    )

    if len(values) == 0:
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
            "trades_data": [],
        }

    gross_profit = float(
        values[values > 0].sum()
    )

    gross_loss = float(
        abs(values[values < 0].sum())
    )

    if gross_loss == 0:
        profit_factor = (
            99.0
            if gross_profit > 0
            else 0.0
        )
    else:
        profit_factor = (
            gross_profit
            / gross_loss
        )

    cumulative = np.cumsum(values)

    peak = np.maximum.accumulate(
        np.maximum(
            cumulative,
            0.0,
        )
    )

    drawdown = peak - cumulative

    max_dd_r = float(
        drawdown.max()
    )

    balance = float(
        cfg.initial_balance
    )

    peak_balance = balance
    max_dd_pct = 0.0

    risk_fraction = (
        cfg.risk_pct / 100.0
    )

    for value in values:
        balance += (
            balance
            * risk_fraction
            * value
        )

        peak_balance = max(
            peak_balance,
            balance,
        )

        if peak_balance > 0:
            dd_pct = (
                (
                    peak_balance
                    - balance
                )
                / peak_balance
                * 100
            )

            max_dd_pct = max(
                max_dd_pct,
                dd_pct,
            )

    current_win = 0
    current_loss = 0
    max_win = 0
    max_loss = 0

    for value in values:
        if value > 0:
            current_win += 1
            current_loss = 0
            max_win = max(
                max_win,
                current_win,
            )
        elif value < 0:
            current_loss += 1
            current_win = 0
            max_loss = max(
                max_loss,
                current_loss,
            )
        else:
            current_win = 0
            current_loss = 0

    return {
        "trades": int(len(values)),
        "win_rate": float(
            (values > 0).mean()
            * 100
        ),
        "profit_factor": float(
            profit_factor
        ),
        "net_r": float(
            values.sum()
        ),
        "expectancy_r": float(
            values.mean()
        ),
        "avg_r": float(
            values.mean()
        ),
        "max_drawdown_r": max_dd_r,
        "max_drawdown_pct": float(
            max_dd_pct
        ),
        "max_win_streak": int(
            max_win
        ),
        "max_loss_streak": int(
            max_loss
        ),
        "avg_hold": float(
            np.mean(
                [
                    t["hold_bars"]
                    for t in trades
                ]
            )
        ),
        "gross_profit_r": gross_profit,
        "gross_loss_r": gross_loss,
        "raw_net_r": float(
            sum(
                t["raw_r"]
                for t in trades
            )
        ),
        "final_balance": float(
            balance
        ),
        "trades_data": trades,
    }


def backtest(
    df,
    direction,
    params,
    selected,
    start_i,
    end_i,
    cfg,
):
    trades = []

    first = max(
        start_i,
        201,
    )

    last = min(
        end_i,
        len(df) - 1,
    )

    i = first

    while i < last - 1:

        if not signal_at(
            df,
            i,
            direction,
            params,
            selected,
        ):
            i += 1
            continue

        signal_bar = df.iloc[i]

        entry_i = i + 1

        entry = safe_float(
            df.iloc[entry_i]["open"],
            np.nan,
        )

        atr_value = safe_float(
            signal_bar["atr14"],
            np.nan,
        )

        if (
            not finite(entry)
            or
            not finite(atr_value)
            or
            atr_value <= 0
        ):
            i += 1
            continue

        stop_distance = (
            atr_value
            * params["sl"]
        )

        if direction == "BUY":
            sl = (
                entry
                - stop_distance
            )
            tp = (
                entry
                + stop_distance
                * params["rr"]
            )
        else:
            sl = (
                entry
                + stop_distance
            )
            tp = (
                entry
                - stop_distance
                * params["rr"]
            )

        exit_i = None
        exit_price = None
        reason = "TIME"

        last_j = min(
            last - 1,
            entry_i
            + params["hold"],
        )

        for j in range(
            entry_i,
            last_j + 1,
        ):
            bar = df.iloc[j]

            high = safe_float(
                bar["high"],
                np.nan,
            )

            low = safe_float(
                bar["low"],
                np.nan,
            )

            if (
                not finite(high)
                or
                not finite(low)
            ):
                continue

            if direction == "BUY":

                hit_sl = (
                    low <= sl
                )

                hit_tp = (
                    high >= tp
                )

                # Conservative assumption:
                # if both happen inside one candle,
                # SL is considered first.
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

                hit_sl = (
                    high >= sl
                )

                hit_tp = (
                    low <= tp
                )

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
                df.iloc[
                    exit_i
                ]["close"],
                entry,
            )

        if direction == "BUY":
            raw_r = (
                exit_price - entry
            ) / stop_distance
        else:
            raw_r = (
                entry - exit_price
            ) / stop_distance

        cost_r = (
            cfg.commission_r_per_trade
            + cfg.slippage_r_per_trade
        )

        spread_points = safe_float(
            df.iloc[
                entry_i
            ]["spread"],
            0,
        )

        if (
            "Spread" in selected
            and
            spread_points
            > params["spread"]
        ):
            i = exit_i + 1
            continue

        if (
            spread_points > 0
            and
            params["spread"] > 0
        ):
            cost_r += min(
                0.15,
                (
                    spread_points
                    / params["spread"]
                )
                * 0.05,
            )

        net_r = (
            raw_r
            - cost_r
        )

        trades.append(
            {
                "signal_time":
                    df.index[i].isoformat(),

                "entry_time":
                    df.index[
                        entry_i
                    ].isoformat(),

                "exit_time":
                    df.index[
                        exit_i
                    ].isoformat(),

                "direction":
                    direction,

                "entry":
                    float(entry),

                "exit":
                    float(exit_price),

                "sl":
                    float(sl),

                "tp":
                    float(tp),

                "raw_r":
                    float(raw_r),

                "net_r":
                    float(net_r),

                "reason":
                    reason,

                "hold_bars":
                    int(
                        exit_i
                        - entry_i
                        + 1
                    ),

                "spread_points":
                    float(
                        spread_points
                    ),
            }
        )

        i = exit_i + 1

    return summarize_trades(
        trades,
        cfg,
    )


# ============================================================
# CANDIDATES
# ============================================================

def parameter_candidates(
    cfg,
    selected,
):
    ema_pairs = (
        [
            (9, 21),
            (20, 50),
            (20, 100),
            (50, 200),
        ]
        if "EMA" in selected
        else [(20, 50)]
    )

    rsi_ranges = (
        [
            (50, 65),
            (52, 68),
            (55, 70),
            (45, 60),
        ]
        if "RSI" in selected
        else [(52, 68)]
    )

    adx_values = (
        [18, 20, 25, 30]
        if "ADX" in selected
        else [20]
    )

    atr_ranges = (
        [
            (0.03, 0.10),
            (0.05, 0.15),
            (0.03, 0.20),
            (0.05, 0.30),
        ]
        if "ATR" in selected
        else [(0.0, 999.0)]
    )

    pullbacks = [
        0.25,
        0.35,
        0.50,
    ]

    sls = list(
        np.arange(
            cfg.sl_min,
            cfg.sl_max + 0.0001,
            cfg.sl_step,
        )
    )

    rrs = list(
        np.arange(
            cfg.rr_min,
            cfg.rr_max + 0.0001,
            cfg.rr_step,
        )
    )

    bodies = (
        [
            0.40,
            0.50,
            0.60,
        ]
        if "Price Action" in selected
        else [0.45]
    )

    sessions = (
        [
            "London",
            "NY",
            "Both",
            "All",
        ]
        if "Session" in selected
        else ["All"]
    )

    spreads = (
        [cfg.max_spread_points]
        if "Spread" in selected
        else [999999.0]
    )

    stochastic_limits = (
        [70, 80]
        if "Stochastic" in selected
        else [80]
    )

    candidates = []

    combinations = product(
        ema_pairs,
        rsi_ranges,
        adx_values,
        atr_ranges,
        pullbacks,
        sls,
        rrs,
        bodies,
        sessions,
        spreads,
        stochastic_limits,
    )

    for (
        ema_pair,
        rsi_range,
        adx_value,
        atr_range,
        pullback,
        sl,
        rr,
        body,
        session,
        spread,
        stochastic_limit,
    ) in combinations:

        candidates.append(
            {
                "fast":
                    ema_pair[0],

                "slow":
                    ema_pair[1],

                "rsi_lo":
                    rsi_range[0],

                "rsi_hi":
                    rsi_range[1],

                "adx":
                    float(adx_value),

                "atr_min":
                    float(
                        atr_range[0]
                    ),

                "atr_max":
                    float(
                        atr_range[1]
                    ),

                "pullback":
                    float(
                        pullback
                    ),

                "sl":
                    float(sl),

                "rr":
                    float(rr),

                "body":
                    float(body),

                "spread":
                    float(spread),

                "session":
                    session,

                "stoch_hi":
                    float(
                        stochastic_limit
                    ),

                "hold":
                    int(
                        cfg.max_hold_bars
                    ),
            }
        )

    rng = random.Random(
        cfg.seed
    )

    rng.shuffle(
        candidates
    )

    return candidates[
        :max(
            1,
            int(
                cfg.max_candidates
            ),
        )
    ]


# ============================================================
# RANKING
# ============================================================

def stability_score(
    train,
    test,
):
    if (
        train["trades"] <= 0
        or
        test["trades"] <= 0
    ):
        return 0.0

    train_pf = min(
        train["profit_factor"],
        5.0,
    )

    test_pf = min(
        test["profit_factor"],
        5.0,
    )

    pf_ratio = min(
        1.0,
        test_pf
        / max(
            train_pf,
            1.0,
        ),
    )

    if train["expectancy_r"] > 0:
        expectancy_ratio = max(
            0.0,
            min(
                1.0,
                test["expectancy_r"]
                /
                train["expectancy_r"],
            ),
        )
    else:
        expectancy_ratio = 0.0

    dd_quality = max(
        0.0,
        1.0
        - test["max_drawdown_pct"]
        / 50.0,
    )

    win_rate_gap = abs(
        train["win_rate"]
        - test["win_rate"]
    )

    consistency = max(
        0.0,
        1.0
        - win_rate_gap / 30.0,
    )

    return 100 * (
        0.35 * pf_ratio
        +
        0.30 * expectancy_ratio
        +
        0.20 * consistency
        +
        0.15 * dd_quality
    )


def overfit_penalty(
    train,
    test,
):
    penalty = 0.0

    if (
        train["trades"] > 0
        and
        test["trades"] > 0
    ):
        pf_gap = max(
            0.0,
            train["profit_factor"]
            - test["profit_factor"],
        )

        penalty += min(
            30.0,
            pf_gap * 8.0,
        )

        expectancy_gap = max(
            0.0,
            train["expectancy_r"]
            - test["expectancy_r"],
        )

        penalty += min(
            20.0,
            expectancy_gap * 20.0,
        )

        win_rate_gap = max(
            0.0,
            train["win_rate"]
            - test["win_rate"]
            - 10.0,
        )

        penalty += min(
            15.0,
            win_rate_gap * 0.5,
        )

    if train["trades"] < 80:
        penalty += 20.0
    elif train["trades"] < 120:
        penalty += 10.0

    if test["trades"] < 40:
        penalty += 12.0

    return min(
        70.0,
        penalty,
    )


def final_score(
    train,
    test,
):
    if (
        train["trades"] == 0
        or
        test["trades"] == 0
    ):
        return -999.0

    pf = min(
        test["profit_factor"],
        4.0,
    )

    expectancy = max(
        -1.0,
        min(
            test["expectancy_r"],
            1.0,
        ),
    )

    drawdown = min(
        test["max_drawdown_pct"],
        50.0,
    )

    trades = min(
        test["trades"],
        300,
    )

    raw = (
        25
        * min(
            pf / 2.0,
            1.0,
        )
        +
        25
        * max(
            0.0,
            expectancy + 0.25,
        )
        +
        15
        * (
            1
            - drawdown / 50.0
        )
        +
        10
        * min(
            test["win_rate"]
            / 70.0,
            1.0,
        )
        +
        10
        * min(
            trades / 100.0,
            1.0,
        )
        +
        15
        * stability_score(
            train,
            test,
        )
        / 100.0
    )

    return (
        raw
        - overfit_penalty(
            train,
            test,
        )
    )


# ============================================================
# RESEARCH ENGINE
# ============================================================

class ResearchEngine:

    def __init__(
        self,
        stop_event,
    ):
        self.stop_event = stop_event

    def run(
        self,
        df,
        cfg,
        selected,
        logger,
        progress,
    ):
        logger(
            "[FEATURES] Starting feature engine..."
        )

        features = build_features(
            df,
            logger,
        )

        split = int(
            len(features)
            * cfg.train_pct
            / 100
        )

        split = max(
            300,
            min(
                split,
                len(features) - 300,
            ),
        )

        candidates = parameter_candidates(
            cfg,
            selected,
        )

        total = (
            len(candidates)
            * 2
        )

        logger(
            f"[RESEARCH] Candidates: "
            f"{len(candidates)}"
        )

        logger(
            f"[RESEARCH] Total tests: "
            f"{total}"
        )

        logger(
            f"[RESEARCH] Train bars: "
            f"{split:,}"
        )

        logger(
            f"[RESEARCH] OOS bars: "
            f"{len(features) - split:,}"
        )

        results = []

        completed = 0

        for candidate_number, params in enumerate(
            candidates,
            1,
        ):

            if self.stop_event.is_set():
                logger(
                    "[RESEARCH] STOP detected."
                )
                break

            for direction in [
                "BUY",
                "SELL",
            ]:

                if self.stop_event.is_set():
                    break

                train = backtest(
                    features,
                    direction,
                    params,
                    selected,
                    0,
                    split,
                    cfg,
                )

                if self.stop_event.is_set():
                    break

                test = backtest(
                    features,
                    direction,
                    params,
                    selected,
                    split,
                    len(features),
                    cfg,
                )

                completed += 1

                progress(
                    completed,
                    total,
                    candidate_number,
                    len(candidates),
                )

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
                    train,
                    test,
                )

                score = final_score(
                    train,
                    test,
                )

                name = (
                    f"{direction} | "
                    f"EMA "
                    f"{params['fast']}/"
                    f"{params['slow']} | "
                    f"RSI "
                    f"{params['rsi_lo']}-"
                    f"{params['rsi_hi']} | "
                    f"ADX "
                    f"{params['adx']:.0f} | "
                    f"SL "
                    f"{params['sl']:.1f} ATR | "
                    f"RR "
                    f"{params['rr']:.1f}"
                )

                results.append(
                    {
                        "name": name,
                        "direction": direction,
                        "params": params,
                        "train": train,
                        "test": test,
                        "stability": stability,
                        "score": score,
                    }
                )

            if (
                candidate_number == 1
                or
                candidate_number
                % max(
                    1,
                    len(candidates)
                    // 10,
                )
                == 0
            ):
                logger(
                    f"[TEST] Candidate "
                    f"{candidate_number}/"
                    f"{len(candidates)} | "
                    f"Accepted="
                    f"{len(results)}"
                )

        results.sort(
            key=lambda item:
                item["score"],
            reverse=True,
        )

        if self.stop_event.is_set():
            logger(
                "[RESEARCH] Stopped by user."
            )
        else:
            logger(
                "[RESEARCH] Finished ✓"
            )

        logger(
            f"[RESULT] Accepted strategies: "
            f"{len(results)}"
        )

        return (
            results,
            features,
            split,
        )


# ============================================================
# EXPORT
# ============================================================

def clean_result(result):
    return {
        "name":
            result["name"],

        "direction":
            result["direction"],

        "params":
            result["params"],

        "stability_score":
            result["stability"],

        "final_score":
            result["score"],

        "train": {
            key: value
            for key, value
            in result["train"].items()
            if key != "trades_data"
        },

        "test": {
            key: value
            for key, value
            in result["test"].items()
            if key != "trades_data"
        },
    }


def export_results(
    results,
    folder,
    symbol,
):
    folder.mkdir(
        parents=True,
        exist_ok=True,
    )

    json_path = (
        folder
        / f"{symbol}_strategy_results.json"
    )

    ranking_path = (
        folder
        / f"{symbol}_strategy_ranking.csv"
    )

    trades_path = (
        folder
        / f"{symbol}_top_strategy_trades.csv"
    )

    json_path.write_text(
        json.dumps(
            [
                clean_result(r)
                for r in results
            ],
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    rows = []

    for rank, result in enumerate(
        results,
        1,
    ):
        train = result["train"]
        test = result["test"]

        rows.append(
            {
                "rank":
                    rank,

                "score":
                    result["score"],

                "stability":
                    result["stability"],

                "direction":
                    result["direction"],

                "name":
                    result["name"],

                "train_trades":
                    train["trades"],

                "train_pf":
                    train["profit_factor"],

                "train_win_rate":
                    train["win_rate"],

                "train_expectancy_r":
                    train["expectancy_r"],

                "train_dd_pct":
                    train["max_drawdown_pct"],

                "test_trades":
                    test["trades"],

                "test_pf":
                    test["profit_factor"],

                "test_win_rate":
                    test["win_rate"],

                "test_expectancy_r":
                    test["expectancy_r"],

                "test_dd_pct":
                    test["max_drawdown_pct"],

                "test_net_r":
                    test["net_r"],
            }
        )

    pd.DataFrame(
        rows
    ).to_csv(
        ranking_path,
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
        ranking_path,
        trades_path,
    )


# ============================================================
# GUI
# ============================================================

class App(tk.Tk):

    def __init__(self):
        super().__init__()

        self.title(
            f"{APP_TITLE} v{VERSION}"
        )

        self.geometry(
            "1400x920"
        )

        self.minsize(
            1150,
            760,
        )

        self.mt5_service = MT5Service()

        self.loaded_data = None
        self.results = []

        self.running = False

        self.stop_event = threading.Event()

        self.vars = {}
        self.indicator_vars = {}
        self.status_vars = {}

        self._build_ui()

        self.protocol(
            "WM_DELETE_WINDOW",
            self.on_close,
        )

        self.after(
            150,
            self.startup_diagnostics,
        )

    # ========================================================
    # UI
    # ========================================================

    def _build_ui(self):
        header = ttk.Frame(
            self,
            padding=10,
        )

        header.pack(
            fill="x"
        )

        ttk.Label(
            header,
            text=(
                f"{APP_TITLE} "
                f"v{VERSION}"
            ),
            font=(
                "Segoe UI",
                18,
                "bold",
            ),
        ).pack(
            side="left"
        )

        ttk.Label(
            header,
            text=(
                "RESEARCH ONLY  |  "
                "NO LIVE ORDERS"
            ),
            foreground="darkred",
            font=(
                "Segoe UI",
                10,
                "bold",
            ),
        ).pack(
            side="right"
        )

        self._build_status_panel()

        self._build_controls()

        main = ttk.Panedwindow(
            self,
            orient="horizontal",
        )

        main.pack(
            fill="both",
            expand=True,
            padx=10,
            pady=(0, 10),
        )

        left = ttk.Frame(
            main,
            padding=8,
        )

        right = ttk.Frame(
            main,
            padding=8,
        )

        main.add(
            left,
            weight=0,
        )

        main.add(
            right,
            weight=1,
        )

        self._build_settings(
            left
        )

        self._build_results(
            right
        )

        self.status_bar = tk.StringVar(
            value="Starting..."
        )

        ttk.Label(
            self,
            textvariable=self.status_bar,
            relief="sunken",
            anchor="w",
        ).pack(
            fill="x",
            side="bottom",
        )

    def _build_status_panel(self):
        box = ttk.LabelFrame(
            self,
            text="MT5 STATUS / DIAGNOSTICS",
            padding=8,
        )

        box.pack(
            fill="x",
            padx=10,
            pady=(0, 8),
        )

        items = [
            (
                "Python",
                "python",
                "CHECKING",
            ),
            (
                "MT5 Package",
                "package",
                "CHECKING",
            ),
            (
                "Terminal",
                "terminal",
                "NOT CONNECTED",
            ),
            (
                "Account",
                "account",
                "-",
            ),
            (
                "Server",
                "server",
                "-",
            ),
            (
                "Symbol",
                "symbol",
                "-",
            ),
            (
                "Timeframe",
                "timeframe",
                "-",
            ),
            (
                "Data",
                "data",
                "NOT LOADED",
            ),
            (
                "Bars",
                "bars",
                "0",
            ),
            (
                "Last Bar",
                "lastbar",
                "-",
            ),
        ]

        for index, (
            label,
            key,
            value,
        ) in enumerate(items):

            row = index // 5
            column = (index % 5) * 2

            ttk.Label(
                box,
                text=f"{label}:",
                font=(
                    "Segoe UI",
                    9,
                    "bold",
                ),
            ).grid(
                row=row,
                column=column,
                sticky="e",
                padx=(5, 3),
                pady=3,
            )

            variable = tk.StringVar(
                value=value
            )

            self.status_vars[key] = variable

            ttk.Label(
                box,
                textvariable=variable,
                width=18,
            ).grid(
                row=row,
                column=column + 1,
                sticky="w",
                padx=(0, 10),
                pady=3,
            )

    def _build_controls(self):
        frame = ttk.Frame(
            self,
            padding=(
                10,
                0,
                10,
                8,
            ),
        )

        frame.pack(
            fill="x"
        )

        self.connect_button = ttk.Button(
            frame,
            text="CONNECT MT5",
            command=self.connect_mt5,
        )

        self.connect_button.pack(
            side="left",
            padx=(0, 5),
        )

        self.load_button = ttk.Button(
            frame,
            text="LOAD DATA",
            command=self.load_data,
        )

        self.load_button.pack(
            side="left",
            padx=5,
        )

        self.start_button = ttk.Button(
            frame,
            text="START RESEARCH",
            command=self.start_research,
        )

        self.start_button.pack(
            side="left",
            padx=5,
        )

        self.stop_button = ttk.Button(
            frame,
            text="STOP",
            command=self.stop_research,
            state="disabled",
        )

        self.stop_button.pack(
            side="left",
            padx=5,
        )

        ttk.Button(
            frame,
            text="COPY LOG",
            command=self.copy_log,
        ).pack(
            side="right",
            padx=5,
        )

        ttk.Button(
            frame,
            text="CLEAR LOG",
            command=self.clear_log,
        ).pack(
            side="right",
            padx=5,
        )

        self.progress_text = tk.StringVar(
            value="Progress: 0%"
        )

        ttk.Label(
            frame,
            textvariable=self.progress_text,
            width=28,
            anchor="e",
        ).pack(
            side="right",
            padx=5,
        )

        self.progress = ttk.Progressbar(
            frame,
            mode="determinate",
            length=260,
        )

        self.progress.pack(
            side="right",
            padx=10,
        )

    def _build_settings(self, parent):
        box = ttk.LabelFrame(
            parent,
            text="Research Settings",
            padding=8,
        )

        box.pack(
            fill="x",
            pady=(0, 8),
        )

        fields = [
            (
                "Symbol",
                "symbol",
                "XAUUSD",
            ),
            (
                "Timeframe",
                "timeframe",
                "M5",
            ),
            (
                "Start",
                "start",
                "2025-01-01",
            ),
            (
                "End",
                "end",
                "2026-08-18",
            ),
            (
                "Train %",
                "train_pct",
                "70",
            ),
            (
                "Max Candidates",
                "max_candidates",
                "300",
            ),
            (
                "Min Train Trades",
                "min_train_trades",
                "80",
            ),
            (
                "Min OOS Trades",
                "min_test_trades",
                "25",
            ),
            (
                "Initial Balance",
                "initial_balance",
                "500",
            ),
            (
                "Risk % / Trade",
                "risk_pct",
                "1.0",
            ),
            (
                "Max Spread",
                "max_spread_points",
                "80",
            ),
            (
                "Commission R",
                "commission_r_per_trade",
                "0.02",
            ),
            (
                "Slippage R",
                "slippage_r_per_trade",
                "0.03",
            ),
            (
                "RR Min",
                "rr_min",
                "1.4",
            ),
            (
                "RR Max",
                "rr_max",
                "2.2",
            ),
            (
                "RR Step",
                "rr_step",
                "0.4",
            ),
            (
                "SL Min ATR",
                "sl_min",
                "1.0",
            ),
            (
                "SL Max ATR",
                "sl_max",
                "2.0",
            ),
            (
                "SL Step",
                "sl_step",
                "0.5",
            ),
            (
                "Max Hold Bars",
                "max_hold_bars",
                "24",
            ),
        ]

        for row, (
            label,
            key,
            default,
        ) in enumerate(fields):

            ttk.Label(
                box,
                text=label,
            ).grid(
                row=row,
                column=0,
                sticky="w",
                pady=2,
            )

            variable = tk.StringVar(
                value=default
            )

            self.vars[key] = variable

            ttk.Entry(
                box,
                textvariable=variable,
                width=17,
            ).grid(
                row=row,
                column=1,
                sticky="ew",
                pady=2,
            )

        box.columnconfigure(
            1,
            weight=1,
        )

        indicators = ttk.LabelFrame(
            parent,
            text="Indicators / Filters",
            padding=8,
        )

        indicators.pack(
            fill="x",
            pady=(0, 8),
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

        for index, name in enumerate(
            INDICATORS
        ):
            variable = tk.BooleanVar(
                value=defaults[name]
            )

            self.indicator_vars[
                name
            ] = variable

            ttk.Checkbutton(
                indicators,
                text=name,
                variable=variable,
            ).grid(
                row=index // 2,
                column=index % 2,
                sticky="w",
                pady=2,
            )

        workflow = ttk.LabelFrame(
            parent,
            text="Workflow",
            padding=8,
        )

        workflow.pack(
            fill="x",
            pady=4,
        )

        ttk.Label(
            workflow,
            text=(
                "1. CONNECT MT5\n"
                "2. LOAD DATA\n"
                "3. Select indicators\n"
                "4. START RESEARCH\n"
                "5. Monitor progress / log\n"
                "6. Review OOS ranking"
            ),
            justify="left",
        ).pack(
            anchor="w"
        )

    def _build_results(self, parent):
        ranking = ttk.LabelFrame(
            parent,
            text="Strategy Ranking",
            padding=6,
        )

        ranking.pack(
            fill="both",
            expand=True,
        )

        columns = (
            "rank",
            "score",
            "stability",
            "direction",
            "train_pf",
            "oos_pf",
            "oos_wr",
            "oos_exp",
            "oos_dd",
            "oos_trades",
            "name",
        )

        self.tree = ttk.Treeview(
            ranking,
            columns=columns,
            show="headings",
        )

        headings = {
            "rank": "#",
            "score": "Score",
            "stability": "Stability",
            "direction": "Dir",
            "train_pf": "Train PF",
            "oos_pf": "OOS PF",
            "oos_wr": "OOS Win%",
            "oos_exp": "OOS Exp",
            "oos_dd": "OOS DD%",
            "oos_trades": "OOS Trades",
            "name": "Strategy",
        }

        widths = {
            "rank": 45,
            "score": 70,
            "stability": 80,
            "direction": 60,
            "train_pf": 75,
            "oos_pf": 75,
            "oos_wr": 80,
            "oos_exp": 80,
            "oos_dd": 75,
            "oos_trades": 90,
            "name": 480,
        }

        for column in columns:

            self.tree.heading(
                column,
                text=headings[column],
            )

            self.tree.column(
                column,
                width=widths[column],
                anchor="center",
            )

        self.tree.column(
            "name",
            anchor="w",
        )

        self.tree.pack(
            side="left",
            fill="both",
            expand=True,
        )

        scrollbar = ttk.Scrollbar(
            ranking,
            orient="vertical",
            command=self.tree.yview,
        )

        scrollbar.pack(
            side="right",
            fill="y",
        )

        self.tree.configure(
            yscrollcommand=scrollbar.set
        )

        self.tree.bind(
            "<<TreeviewSelect>>",
            self.show_selected,
        )

        log_box = ttk.LabelFrame(
            parent,
            text="Diagnostic / Research Log",
            padding=6,
        )

        log_box.pack(
            fill="both",
            expand=False,
            pady=(8, 0),
        )

        self.log_text = tk.Text(
            log_box,
            height=18,
            wrap="word",
            font=(
                "Consolas",
                9,
            ),
        )

        self.log_text.pack(
            side="left",
            fill="both",
            expand=True,
        )

        scrollbar2 = ttk.Scrollbar(
            log_box,
            orient="vertical",
            command=self.log_text.yview,
        )

        scrollbar2.pack(
            side="right",
            fill="y",
        )

        self.log_text.configure(
            yscrollcommand=scrollbar2.set
        )

    # ========================================================
    # LOG
    # ========================================================

    def log(self, message):
        line = (
            f"{now_text()} "
            f"{message}\n"
        )

        def write():
            self.log_text.insert(
                "end",
                line,
            )

            self.log_text.see(
                "end"
            )

        try:
            self.after(
                0,
                write,
            )
        except Exception:
            pass

    def clear_log(self):
        self.log_text.delete(
            "1.0",
            "end",
        )

    def copy_log(self):
        text = self.log_text.get(
            "1.0",
            "end",
        ).strip()

        if not text:
            messagebox.showinfo(
                "COPY LOG",
                "Log is empty.",
            )
            return

        self.clipboard_clear()
        self.clipboard_append(
            text
        )
        self.update()

        self.set_status(
            "Log copied to clipboard."
        )

    def set_status(self, text):
        self.status_bar.set(
            text
        )

    # ========================================================
    # STARTUP DIAGNOSTICS
    # ========================================================

    def startup_diagnostics(self):
        self.log(
            "[INFO] Application started."
        )

        self.log(
            f"[INFO] Python version: "
            f"{sys.version.split()[0]}"
        )

        self.status_vars[
            "python"
        ].set(
            f"OK ✓ {sys.version_info.major}."
            f"{sys.version_info.minor}"
        )

        if mt5 is None:
            self.status_vars[
                "package"
            ].set(
                "MISSING ✗"
            )

            self.log(
                "[ERROR] MetaTrader5 package: MISSING"
            )

            self.log(
                "[INFO] Install with: "
                "python -m pip install MetaTrader5"
            )

            self.set_status(
                "MetaTrader5 package missing."
            )

            return

        self.status_vars[
            "package"
        ].set(
            "OK ✓"
        )

        self.log(
            "[INFO] MetaTrader5 package: OK ✓"
        )

        self.log(
            "[MT5] Running automatic diagnostics..."
        )

        self.connect_mt5(
            automatic=True
        )

    # ========================================================
    # CONFIG
    # ========================================================

    def read_config(self):
        def get_float(key):
            return float(
                self.vars[key]
                .get()
                .strip()
            )

        def get_int(key):
            return int(
                self.vars[key]
                .get()
                .strip()
            )

        cfg = Config(
            symbol=self.vars[
                "symbol"
            ].get().strip(),

            timeframe=self.vars[
                "timeframe"
            ].get().strip().upper(),

            start=self.vars[
                "start"
            ].get().strip(),

            end=self.vars[
                "end"
            ].get().strip(),

            train_pct=get_int(
                "train_pct"
            ),

            max_candidates=get_int(
                "max_candidates"
            ),

            min_train_trades=get_int(
                "min_train_trades"
            ),

            min_test_trades=get_int(
                "min_test_trades"
            ),

            initial_balance=get_float(
                "initial_balance"
            ),

            risk_pct=get_float(
                "risk_pct"
            ),

            max_spread_points=get_float(
                "max_spread_points"
            ),

            commission_r_per_trade=
                get_float(
                    "commission_r_per_trade"
                ),

            slippage_r_per_trade=
                get_float(
                    "slippage_r_per_trade"
                ),

            rr_min=get_float(
                "rr_min"
            ),

            rr_max=get_float(
                "rr_max"
            ),

            rr_step=get_float(
                "rr_step"
            ),

            sl_min=get_float(
                "sl_min"
            ),

            sl_max=get_float(
                "sl_max"
            ),

            sl_step=get_float(
                "sl_step"
            ),

            max_hold_bars=get_int(
                "max_hold_bars"
            ),
        )

        if not cfg.symbol:
            raise ValueError(
                "Symbol cannot be empty."
            )

        if cfg.timeframe not in TIMEFRAMES:
            raise ValueError(
                "Timeframe must be "
                "M1, M5, M15, M30 or H1."
            )

        if not (
            30
            <= cfg.train_pct
            <= 90
        ):
            raise ValueError(
                "Train % must be "
                "between 30 and 90."
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
                "Min OOS Trades must be >= 5."
            )

        if cfg.rr_min <= 0:
            raise ValueError(
                "RR Min must be > 0."
            )

        if cfg.rr_max < cfg.rr_min:
            raise ValueError(
                "RR Max must be >= RR Min."
            )

        if cfg.rr_step <= 0:
            raise ValueError(
                "RR Step must be > 0."
            )

        if cfg.sl_min <= 0:
            raise ValueError(
                "SL Min ATR must be > 0."
            )

        if cfg.sl_max < cfg.sl_min:
            raise ValueError(
                "SL Max ATR must be >= SL Min ATR."
            )

        if cfg.sl_step <= 0:
            raise ValueError(
                "SL Step must be > 0."
            )

        if cfg.max_hold_bars < 1:
            raise ValueError(
                "Max Hold Bars must be >= 1."
            )

        return cfg

    def selected_indicators(self):
        return [
            name
            for name, variable
            in self.indicator_vars.items()
            if variable.get()
        ]

    # ========================================================
    # MT5 CONNECT
    # ========================================================

    def connect_mt5(
        self,
        automatic=False,
    ):
        if self.running:
            return

        self.connect_button.configure(
            state="disabled"
        )

        self.log(
            "[MT5] Initializing terminal..."
        )

        thread = threading.Thread(
            target=self._connect_worker,
            args=(automatic,),
            daemon=True,
        )

        thread.start()

    def _connect_worker(
        self,
        automatic,
    ):
        try:
            symbol = (
                self.vars["symbol"]
                .get()
                .strip()
            )

            diagnostics = (
                self.mt5_service
                .diagnostics(
                    symbol
                )
            )

            terminal = diagnostics[
                "terminal"
            ]

            account = diagnostics[
                "account"
            ]

            symbol_info = diagnostics[
                "symbol"
            ]

            tick = diagnostics[
                "tick"
            ]

            self.after(
                0,
                lambda: self.status_vars[
                    "terminal"
                ].set(
                    "CONNECTED ✓"
                ),
            )

            if account:
                self.after(
                    0,
                    lambda: self.status_vars[
                        "account"
                    ].set(
                        str(
                            getattr(
                                account,
                                "login",
                                "-",
                            )
                        )
                    ),
                )

                self.after(
                    0,
                    lambda: self.status_vars[
                        "server"
                    ].set(
                        str(
                            getattr(
                                account,
                                "server",
                                "-",
                            )
                        )[:22]
                    ),
                )

            self.after(
                0,
                lambda: self.status_vars[
                    "symbol"
                ].set(
                    f"{symbol} AVAILABLE ✓"
                ),
            )

            self.after(
                0,
                lambda: self.status_vars[
                    "timeframe"
                ].set(
                    self.vars[
                        "timeframe"
                    ].get()
                ),
            )

            self.log(
                "[MT5] Connected ✓"
            )

            if terminal:
                self.log(
                    "[MT5] Terminal: "
                    + str(
                        getattr(
                            terminal,
                            "name",
                            "Unknown",
                        )
                    )
                )

            if account:
                self.log(
                    "[MT5] Account: "
                    + str(
                        getattr(
                            account,
                            "login",
                            "Unknown",
                        )
                    )
                )

                self.log(
                    "[MT5] Server: "
                    + str(
                        getattr(
                            account,
                            "server",
                            "Unknown",
                        )
                    )
                )

            self.log(
                f"[MT5] {symbol}: AVAILABLE ✓"
            )

            if symbol_info:
                self.log(
                    "[MT5] Digits: "
                    + str(
                        getattr(
                            symbol_info,
                            "digits",
                            "?",
                        )
                    )
                )

                self.log(
                    "[MT5] Point: "
                    + str(
                        getattr(
                            symbol_info,
                            "point",
                            "?",
                        )
                    )
                )

            if tick:
                self.log(
                    "[MT5] Bid="
                    f"{safe_float(tick.bid):.3f} "
                    "Ask="
                    f"{safe_float(tick.ask):.3f}"
                )

            self.set_status(
                "MT5 connected."
            )

        except Exception as exc:

            error = str(exc)

            self.after(
                0,
                lambda: self.status_vars[
                    "terminal"
                ].set(
                    "NOT CONNECTED ✗"
                ),
            )

            self.after(
                0,
                lambda: self.status_vars[
                    "symbol"
                ].set(
                    "NOT AVAILABLE ✗"
                ),
            )

            self.log(
                "[MT5] NOT CONNECTED ✗"
            )

            self.log(
                f"[ERROR] Reason: {error}"
            )

            self.log(
                f"[ERROR] Last MT5 error: "
                f"{mt5_error_text()}"
            )

            self.set_status(
                "MT5 connection failed."
            )

            if not automatic:
                self.after(
                    0,
                    lambda: messagebox.showerror(
                        "MT5 Connection Error",
                        error,
                    ),
                )

        finally:
            self.after(
                0,
                lambda: self.connect_button.configure(
                    state="normal"
                ),
            )

    # ========================================================
    # LOAD DATA
    # ========================================================

    def load_data(self):
        if self.running:
            return

        try:
            cfg = self.read_config()
        except Exception as exc:
            messagebox.showerror(
                "Configuration Error",
                str(exc),
            )
            return

        self.load_button.configure(
            state="disabled"
        )

        self.set_status(
            "Loading historical data..."
        )

        self.log(
            "[DATA] ======================================="
        )

        self.log(
            "[DATA] LOAD DATA started."
        )

        thread = threading.Thread(
            target=self._load_worker,
            args=(cfg,),
            daemon=True,
        )

        thread.start()

    def _load_worker(
        self,
        cfg,
    ):
        try:
            df = (
                self.mt5_service
                .load_rates(
                    cfg.symbol,
                    cfg.timeframe,
                    cfg.start,
                    cfg.end,
                    self.log,
                )
            )

            self.loaded_data = df

            last_bar = df.index[-1]

            self.after(
                0,
                lambda: self.status_vars[
                    "data"
                ].set(
                    "LOADED ✓"
                ),
            )

            self.after(
                0,
                lambda: self.status_vars[
                    "bars"
                ].set(
                    f"{len(df):,}"
                ),
            )

            self.after(
                0,
                lambda: self.status_vars[
                    "lastbar"
                ].set(
                    last_bar.strftime(
                        "%Y-%m-%d %H:%M"
                    )
                ),
            )

            self.after(
                0,
                lambda: self.status_vars[
                    "symbol"
                ].set(
                    f"{cfg.symbol} ✓"
                ),
            )

            self.after(
                0,
                lambda: self.status_vars[
                    "timeframe"
                ].set(
                    cfg.timeframe
                ),
            )

            self.log(
                "[DATA] Historical Data: "
                "READY ✓"
            )

            self.log(
                f"[DATA] Bars: "
                f"{len(df):,}"
            )

            self.log(
                "[DATA] Last Bar: "
                + last_bar.strftime(
                    "%Y-%m-%d %H:%M:%S UTC"
                )
            )

            self.set_status(
                f"Data ready: "
                f"{len(df):,} bars."
            )

        except Exception as exc:

            self.loaded_data = None

            self.log(
                f"[DATA] LOAD FAILED ✗: "
                f"{exc}"
            )

            self.log(
                f"[ERROR] Last MT5 error: "
                f"{mt5_error_text()}"
            )

            self.after(
                0,
                lambda: self.status_vars[
                    "data"
                ].set(
                    "ERROR ✗"
                ),
            )

            self.after(
                0,
                lambda: self.status_vars[
                    "bars"
                ].set(
                    "0"
                ),
            )

            self.after(
                0,
                lambda: self.status_vars[
                    "lastbar"
                ].set(
                    "-"
                ),
            )

            self.after(
                0,
                lambda: messagebox.showerror(
                    "Data Loading Error",
                    str(exc),
                ),
            )

        finally:
            self.after(
                0,
                lambda: self.load_button.configure(
                    state="normal"
                ),
            )

    # ========================================================
    # RESEARCH
    # ========================================================

    def start_research(self):
        if self.running:
            return

        try:
            cfg = self.read_config()

            selected = (
                self.selected_indicators()
            )

            if not selected:
                raise ValueError(
                    "Select at least one "
                    "indicator/filter."
                )

        except Exception as exc:
            messagebox.showerror(
                "Configuration Error",
                str(exc),
            )
            return

        if self.loaded_data is None:
            answer = messagebox.askyesno(
                "Data Not Loaded",
                (
                    "Historical data is not loaded.\n\n"
                    "Load data now?"
                ),
            )

            if answer:
                self.load_data()

            return

        self.stop_event.clear()
        self.running = True

        self.results = []

        self.start_button.configure(
            state="disabled"
        )

        self.load_button.configure(
            state="disabled"
        )

        self.connect_button.configure(
            state="disabled"
        )

        self.stop_button.configure(
            state="normal"
        )

        self.progress["value"] = 0
        self.progress["maximum"] = 1

        self.clear_log()

        self.log(
            "[RESEARCH] ======================================="
        )

        self.log(
            "[RESEARCH] Started ✓"
        )

        self.log(
            f"[RESEARCH] Symbol: "
            f"{cfg.symbol}"
        )

        self.log(
            f"[RESEARCH] Timeframe: "
            f"{cfg.timeframe}"
        )

        self.log(
            "[RESEARCH] Indicators: "
            + ", ".join(selected)
        )

        self.log(
            f"[RESEARCH] Max Candidates: "
            f"{cfg.max_candidates}"
        )

        self.log(
            "[RESEARCH] NO LIVE ORDERS."
        )

        thread = threading.Thread(
            target=self._research_worker,
            args=(
                cfg,
                selected,
            ),
            daemon=True,
        )

        thread.start()

    def _research_worker(
        self,
        cfg,
        selected,
    ):
        try:
            engine = ResearchEngine(
                self.stop_event
            )

            (
                results,
                features,
                split,
            ) = engine.run(
                self.loaded_data,
                cfg,
                selected,
                self.log,
                self.update_progress,
            )

            self.results = results

            self.after(
                0,
                self.populate_results,
            )

            if self.stop_event.is_set():
                self.log(
                    "[RESEARCH] STOPPED."
                )

                self.set_status(
                    "Research stopped."
                )

            elif not results:

                self.log(
                    "[RESULT] "
                    "No accepted strategies."
                )

                self.log(
                    "[RESULT] Suggestions:"
                )

                self.log(
                    "[RESULT] - Increase history."
                )

                self.log(
                    "[RESULT] - Reduce filters."
                )

                self.log(
                    "[RESULT] - Reduce minimum trade counts."
                )

            else:

                best = results[0]

                self.log(
                    "[RESULT] ======================================="
                )

                self.log(
                    "[RESULT] Research finished ✓"
                )

                self.log(
                    f"[RESULT] Accepted: "
                    f"{len(results)}"
                )

                self.log(
                    f"[RESULT] Best strategy: "
                    f"{best['name']}"
                )

                self.log(
                    f"[RESULT] Score: "
                    f"{best['score']:.2f}"
                )

                self.log(
                    f"[RESULT] Stability: "
                    f"{best['stability']:.1f}/100"
                )

                self.log(
                    f"[RESULT] OOS PF: "
                    f"{best['test']['profit_factor']:.2f}"
                )

                self.log(
                    f"[RESULT] OOS Win Rate: "
                    f"{best['test']['win_rate']:.2f}%"
                )

                self.log(
                    f"[RESULT] OOS Expectancy: "
                    f"{best['test']['expectancy_r']:.4f}R"
                )

                self.log(
                    f"[RESULT] OOS Net R: "
                    f"{best['test']['net_r']:.2f}"
                )

                self.log(
                    f"[RESULT] OOS DD: "
                    f"{best['test']['max_drawdown_pct']:.2f}%"
                )

                self.log(
                    f"[RESULT] OOS Trades: "
                    f"{best['test']['trades']}"
                )

                try:
                    paths = export_results(
                        results,
                        RESULTS_DIR,
                        cfg.symbol,
                    )

                    self.log(
                        "[EXPORT] Results exported ✓"
                    )

                    for path in paths:
                        self.log(
                            f"[EXPORT] {path}"
                        )

                except Exception as export_error:

                    self.log(
                        "[EXPORT] ERROR: "
                        f"{export_error}"
                    )

                self.set_status(
                    "Research finished."
                )

        except Exception as exc:

            self.log(
                "[RESEARCH] ERROR ✗"
            )

            self.log(
                f"[ERROR] {exc}"
            )

            self.log(
                traceback.format_exc()
            )

            self.after(
                0,
                lambda: messagebox.showerror(
                    "Research Error",
                    str(exc),
                ),
            )

        finally:

            self.after(
                0,
                self.research_finished,
            )

    # ========================================================
    # PROGRESS
    # ========================================================

    def update_progress(
        self,
        done,
        total,
        candidate,
        candidate_total,
    ):
        def update():

            self.progress["maximum"] = max(
                1,
                total,
            )

            self.progress["value"] = done

            percentage = (
                done
                / total
                * 100
                if total
                else 0
            )

            self.progress_text.set(
                f"Progress: "
                f"{percentage:.1f}%   |   "
                f"Candidates: "
                f"{candidate}/"
                f"{candidate_total}"
            )

            self.status_bar.set(
                f"Research: "
                f"{percentage:.1f}%"
            )

        try:
            self.after(
                0,
                update,
            )
        except Exception:
            pass

    # ========================================================
    # STOP
    # ========================================================

    def stop_research(self):
        if not self.running:
            return

        self.stop_event.set()

        self.stop_button.configure(
            state="disabled"
        )

        self.progress_text.set(
            "STOP requested..."
        )

        self.set_status(
            "Stopping safely..."
        )

        self.log(
            "[RESEARCH] STOP requested by user."
        )

        self.log(
            "[RESEARCH] Finishing current test safely..."
        )

    def research_finished(self):
        self.running = False

        self.start_button.configure(
            state="normal"
        )

        self.load_button.configure(
            state="normal"
        )

        self.connect_button.configure(
            state="normal"
        )

        self.stop_button.configure(
            state="disabled"
        )

        if self.stop_event.is_set():
            self.progress_text.set(
                "Stopped."
            )
        else:
            self.progress_text.set(
                "Progress: 100%"
            )

    # ========================================================
    # RESULTS
    # ========================================================

    def populate_results(self):
        for item in self.tree.get_children():
            self.tree.delete(
                item
            )

        for rank, result in enumerate(
            self.results,
            1,
        ):
            train = result["train"]
            test = result["test"]

            self.tree.insert(
                "",
                "end",
                iid=str(
                    rank - 1
                ),
                values=(
                    rank,
                    f"{result['score']:.2f}",
                    f"{result['stability']:.1f}",
                    result["direction"],
                    f"{train['profit_factor']:.2f}",
                    f"{test['profit_factor']:.2f}",
                    f"{test['win_rate']:.1f}",
                    f"{test['expectancy_r']:.3f}",
                    f"{test['max_drawdown_pct']:.1f}",
                    test["trades"],
                    result["name"],
                ),
            )

    def show_selected(
        self,
        _event=None,
    ):
        selected = (
            self.tree.selection()
        )

        if (
            not selected
            or
            not self.results
        ):
            return

        index = int(
            selected[0]
        )

        if index >= len(
            self.results
        ):
            return

        result = self.results[
            index
        ]

        self.log(
            "------------------------------------------------"
        )

        self.log(
            "[SELECTED] "
            + result["name"]
        )

        self.log(
            f"[SELECTED] Score="
            f"{result['score']:.2f}"
        )

        self.log(
            f"[SELECTED] Stability="
            f"{result['stability']:.1f}/100"
        )

        self.log(
            "[SELECTED] TRAIN: "
            f"Trades="
            f"{result['train']['trades']} "
            f"PF="
            f"{result['train']['profit_factor']:.2f} "
            f"WR="
            f"{result['train']['win_rate']:.1f}%"
        )

        self.log(
            "[SELECTED] OOS: "
            f"Trades="
            f"{result['test']['trades']} "
            f"PF="
            f"{result['test']['profit_factor']:.2f} "
            f"WR="
            f"{result['test']['win_rate']:.1f}% "
            f"Exp="
            f"{result['test']['expectancy_r']:.3f}R "
            f"DD="
            f"{result['test']['max_drawdown_pct']:.2f}%"
        )

        self.log(
            "[SELECTED] Parameters: "
            +
            json.dumps(
                result["params"],
                ensure_ascii=False,
            )
        )

    # ========================================================
    # CLOSE
    # ========================================================

    def on_close(self):
        if self.running:
            answer = messagebox.askyesno(
                "Research Running",
                (
                    "Research is still running.\n\n"
                    "Stop and close?"
                ),
            )

            if not answer:
                return

            self.stop_event.set()

        try:
            self.mt5_service.shutdown()
        except Exception:
            pass

        self.destroy()


# ============================================================
# MAIN
# ============================================================

def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()