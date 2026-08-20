# -*- coding: utf-8 -*-
"""
XAU Strategy Researcher Pro v2.1.1

Compatibility/patch release built on top of v2.1.
Keeps the existing research engine and GUI intact while replacing the
fragile single-range MT5 history request with a chunked, diagnostic loader.

Research-only: this file never sends trading orders.
"""

from __future__ import annotations

import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path
import math

import numpy as np
import pandas as pd

import MetaTrader5 as mt5

BASE_DIR = Path(__file__).resolve().parent
SOURCE_FILE = BASE_DIR / "XAU_Strategy_Researcher_Pro_v2.1.py"

if not SOURCE_FILE.exists():
    raise FileNotFoundError(
        f"Required base engine not found: {SOURCE_FILE}"
    )

# Load the complete v2.1 engine without executing its main() guard.
spec = importlib.util.spec_from_file_location(
    "xau_strategy_researcher_v21",
    SOURCE_FILE,
)
if spec is None or spec.loader is None:
    raise RuntimeError("Could not load XAU_Strategy_Researcher_Pro_v2.1.py")

engine = importlib.util.module_from_spec(spec)
spec.loader.exec_module(engine)


def _safe_float(value, default=0.0):
    try:
        value = float(value)
        return value if math.isfinite(value) else default
    except Exception:
        return default


def _mt5_error():
    try:
        return str(mt5.last_error())
    except Exception:
        return "Unknown MT5 error"


def robust_load_rates(self, symbol, timeframe, start, end, logger):
    """Load MT5 history in bounded chunks and validate the result."""
    self.initialize()

    logger("[MT5] Initializing terminal...")

    terminal = mt5.terminal_info()
    account = mt5.account_info()

    if terminal:
        logger(f"[MT5] Terminal: {getattr(terminal, 'name', 'Unknown')}")
        logger(f"[MT5] Build: {getattr(terminal, 'build', 'Unknown')}")
        maxbars = getattr(terminal, "maxbars", None)
        if maxbars:
            logger(f"[MT5] Max bars setting: {maxbars:,}")

    if account:
        logger(f"[MT5] Account: {getattr(account, 'login', 'Unknown')}")
        logger(f"[MT5] Server: {getattr(account, 'server', 'Unknown')}")

    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        raise RuntimeError(
            f"Symbol '{symbol}' is not available.\n"
            f"Last error: {_mt5_error()}"
        )

    if not mt5.symbol_select(symbol, True):
        raise RuntimeError(
            f"Cannot select {symbol}.\nMT5 error: {_mt5_error()}"
        )

    logger(f"[MT5] Symbol: {symbol} AVAILABLE ✓")

    tick = mt5.symbol_info_tick(symbol)
    if tick:
        logger(
            f"[MT5] Tick: Bid={_safe_float(tick.bid):.3f} "
            f"Ask={_safe_float(tick.ask):.3f}"
        )

    try:
        start_dt = datetime.strptime(start, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        end_dt = (
            datetime.strptime(end, "%Y-%m-%d") + timedelta(days=1)
        ).replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise RuntimeError("Date format must be YYYY-MM-DD.") from exc

    if timeframe not in engine.TIMEFRAMES:
        raise RuntimeError(f"Unsupported timeframe: {timeframe}")

    tf = getattr(mt5, engine.TIMEFRAMES[timeframe])

    logger(
        f"[DATA] Requested: {symbol} {timeframe}: "
        f"{start} -> {end}"
    )
    logger("[DATA] Using chunked historical loader v2.1.1...")

    # Chunk length is deliberately bounded. This avoids a large single
    # copy_rates_range() request and makes failures diagnosable.
    chunk_days = {
        "M1": 14,
        "M5": 60,
        "M15": 120,
        "M30": 180,
        "H1": 365,
    }.get(timeframe, 60)

    total_days = max(1, (end_dt - start_dt).days)
    chunks = []
    cursor = start_dt
    chunk_number = 0
    expected_chunks = max(1, math.ceil(total_days / chunk_days))

    while cursor < end_dt:
        chunk_number += 1
        chunk_end = min(cursor + timedelta(days=chunk_days), end_dt)

        logger(
            f"[DATA] Chunk {chunk_number}/{expected_chunks}: "
            f"{cursor.strftime('%Y-%m-%d')} -> "
            f"{(chunk_end - timedelta(seconds=1)).strftime('%Y-%m-%d')}"
        )

        rates = mt5.copy_rates_range(
            symbol,
            tf,
            cursor,
            chunk_end,
        )

        if rates is None:
            error = _mt5_error()
            logger(
                f"[WARN] Chunk {chunk_number} returned None. "
                f"MT5 error: {error}"
            )
            logger(
                "[DATA] Retrying this chunk with a smaller window..."
            )

            # One-hour fallback window scan. This is only used when the
            # broker/terminal rejects the normal chunk request.
            retry_cursor = cursor
            retry_parts = []
            retry_step = timedelta(days=max(1, chunk_days // 4))

            while retry_cursor < chunk_end:
                retry_end = min(retry_cursor + retry_step, chunk_end)
                retry_rates = mt5.copy_rates_range(
                    symbol,
                    tf,
                    retry_cursor,
                    retry_end,
                )
                if retry_rates is not None and len(retry_rates) > 0:
                    retry_parts.append(retry_rates)
                retry_cursor = retry_end

            if retry_parts:
                rates = np.concatenate(retry_parts)
            else:
                rates = None

        if rates is None:
            logger(
                f"[WARN] No data available for chunk {chunk_number}."
            )
        elif len(rates) == 0:
            logger(
                f"[WARN] Chunk {chunk_number}: 0 bars returned."
            )
        else:
            logger(
                f"[DATA] Chunk {chunk_number}: "
                f"{len(rates):,} bars ✓"
            )
            chunks.append(rates)

        cursor = chunk_end

    if not chunks:
        raise RuntimeError(
            "MT5 returned no historical bars for the requested range.\n"
            f"Last error: {_mt5_error()}\n\n"
            "Check that XAUUSD history is downloaded in MT5 and that "
            "the requested dates are available from the broker."
        )

    logger("[DATA] Combining historical chunks...")

    rates = np.concatenate(chunks)
    df = pd.DataFrame(rates)

    required = ["time", "open", "high", "low", "close"]
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise RuntimeError(
            "MT5 data missing columns: " + ", ".join(missing)
        )

    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)

    raw_count = len(df)
    duplicate_count = int(df.duplicated(subset=["time"]).sum())

    df = (
        df.drop_duplicates(subset=["time"])
        .sort_values("time")
        .set_index("time")
    )

    for column in ["open", "high", "low", "close"]:
        df[column] = pd.to_numeric(df[column], errors="coerce")

    if "spread" in df.columns:
        df["spread"] = pd.to_numeric(
            df["spread"], errors="coerce"
        ).fillna(0.0)
        spread_available = True
    else:
        df["spread"] = 0.0
        spread_available = False

    df["spread_available"] = spread_available

    before_validation = len(df)
    df = df.dropna(subset=["open", "high", "low", "close"])

    valid_ohlc = (
        (df["high"] >= df["low"])
        & (df["high"] >= df["open"])
        & (df["high"] >= df["close"])
        & (df["low"] <= df["open"])
        & (df["low"] <= df["close"])
    )
    df = df[valid_ohlc]

    invalid_count = before_validation - len(df)

    if len(df) < 1000:
        raise RuntimeError(
            f"Only {len(df):,} valid bars are available. "
            "At least 1,000 bars are recommended for research."
        )

    logger(f"[DATA] Raw bars collected: {raw_count:,}")
    logger(f"[DATA] Duplicate bars removed: {duplicate_count:,}")
    logger(f"[DATA] Invalid rows removed: {invalid_count:,}")
    logger(f"[DATA] Valid bars: {len(df):,} ✓")
    logger(
        "[DATA] First bar: "
        + df.index[0].strftime("%Y-%m-%d %H:%M:%S UTC")
    )
    logger(
        "[DATA] Last bar: "
        + df.index[-1].strftime("%Y-%m-%d %H:%M:%S UTC")
    )

    if spread_available:
        logger("[DATA] Historical spread: AVAILABLE ✓")
    else:
        logger(
            "[WARN] Historical spread column unavailable; "
            "spread filter will use the engine's fallback behavior."
        )

    # Basic continuity diagnostic. We report gaps but do not reject the
    # dataset because market closures and broker history gaps are normal.
    if len(df) > 1:
        deltas = df.index.to_series().diff().dropna()
        expected = {
            "M1": timedelta(minutes=1),
            "M5": timedelta(minutes=5),
            "M15": timedelta(minutes=15),
            "M30": timedelta(minutes=30),
            "H1": timedelta(hours=1),
        }[timeframe]
        large_gap_count = int((deltas > expected * 3).sum())
        if large_gap_count:
            logger(
                f"[WARN] Large history gaps detected: "
                f"{large_gap_count:,}"
            )
        else:
            logger("[DATA] Continuity check: OK ✓")

    logger("[DATA] Historical data load completed ✓")

    return df


# Patch only the data-loading method; all v2.1 GUI, research, ranking,
# export and backtest logic remains unchanged.
engine.MT5Service.load_rates = robust_load_rates

# Make the patched release visible in the existing GUI/logging.
engine.VERSION = "2.1.1"
engine.APP_TITLE = "XAU Strategy Researcher Pro v2.1.1"


if __name__ == "__main__":
    engine.main()
