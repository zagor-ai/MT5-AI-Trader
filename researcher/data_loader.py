"""Historical market-data loader.

This module is deliberately isolated so MT5 history bugs can be fixed without
changing the backtester or GUI. It never sends trading orders.
"""

from datetime import datetime, timedelta, timezone

import pandas as pd

from .mt5_connector import MT5Connector, mt5, mt5_error_text

TIMEFRAMES = {
    "M1": "TIMEFRAME_M1",
    "M5": "TIMEFRAME_M5",
    "M15": "TIMEFRAME_M15",
    "M30": "TIMEFRAME_M30",
    "H1": "TIMEFRAME_H1",
}


class HistoricalDataLoader:
    def __init__(self, connector: MT5Connector):
        self.connector = connector

    @staticmethod
    def _parse_date(value: str, end=False):
        dt = datetime.strptime(value, "%Y-%m-%d")
        if end:
            dt += timedelta(days=1)
        return dt.replace(tzinfo=timezone.utc)

    def load(self, symbol: str, timeframe: str, start: str, end: str, logger=print):
        if mt5 is None:
            raise RuntimeError("MetaTrader5 package is not installed.")
        if timeframe not in TIMEFRAMES:
            raise ValueError(f"Unsupported timeframe: {timeframe}")

        self.connector.ensure_symbol(symbol)
        tf = getattr(mt5, TIMEFRAMES[timeframe])
        start_dt = self._parse_date(start)
        end_dt = self._parse_date(end, end=True)

        logger(f"[DATA] Requesting {symbol} {timeframe}: {start} -> {end}")
        logger("[DATA] Using chunked history loader.")

        # The old monolithic request can return (-2, Invalid params). Keep
        # requests small and retry a failing chunk at 7-day granularity.
        chunk_days = 60
        frames = []
        cursor = start_dt
        total_chunks = max(1, (end_dt - start_dt).days // chunk_days + 1)
        chunk_no = 0

        while cursor < end_dt:
            chunk_no += 1
            chunk_end = min(cursor + timedelta(days=chunk_days), end_dt)
            rates = mt5.copy_rates_range(symbol, tf, cursor, chunk_end)

            if rates is None:
                logger(
                    f"[DATA] Chunk {chunk_no}/{total_chunks} failed: "
                    f"{mt5_error_text()}"
                )
                frames.extend(self._load_small_chunks(
                    symbol, tf, cursor, chunk_end, logger, chunk_no
                ))
            elif len(rates):
                logger(f"[DATA] Chunk {chunk_no}: {len(rates):,} bars ✓")
                frames.append(pd.DataFrame(rates))
            else:
                logger(f"[DATA] Chunk {chunk_no}: 0 bars")

            cursor = chunk_end

        if not frames:
            raise RuntimeError(
                "No historical data returned by MT5. "
                f"Last error: {mt5_error_text()}"
            )

        df = pd.concat(frames, ignore_index=True)
        if "time" not in df.columns:
            raise RuntimeError("MT5 data does not contain a time column.")

        df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
        before = len(df)
        df = df.drop_duplicates(subset=["time"]).sort_values("time")

        required = ["open", "high", "low", "close"]
        for col in required:
            if col not in df.columns:
                raise RuntimeError(f"MT5 data missing column: {col}")
            df[col] = pd.to_numeric(df[col], errors="coerce")

        df = df.dropna(subset=required)
        df = df.set_index("time")
        removed = before - len(df)

        if "spread" not in df.columns:
            df["spread"] = 0.0
            df["spread_available"] = False
        else:
            df["spread"] = pd.to_numeric(df["spread"], errors="coerce").fillna(0.0)
            df["spread_available"] = True

        if len(df) == 0:
            raise RuntimeError("No valid OHLC bars remained after validation.")

        logger(f"[DATA] Raw combined bars: {before:,}")
        logger(f"[DATA] Duplicate/invalid rows removed: {removed:,}")
        logger(f"[DATA] Valid bars: {len(df):,} ✓")
        logger(f"[DATA] First bar: {df.index[0].strftime('%Y-%m-%d %H:%M:%S UTC')}")
        logger(f"[DATA] Last bar: {df.index[-1].strftime('%Y-%m-%d %H:%M:%S UTC')}")
        return df

    def _load_small_chunks(self, symbol, tf, start, end, logger, parent_no):
        frames = []
        cursor = start
        step = timedelta(days=7)
        part = 0
        while cursor < end:
            part += 1
            part_end = min(cursor + step, end)
            rates = mt5.copy_rates_range(symbol, tf, cursor, part_end)
            if rates is None:
                logger(
                    f"[DATA] Retry {parent_no}.{part} failed: "
                    f"{mt5_error_text()}"
                )
            elif len(rates):
                logger(f"[DATA] Retry {parent_no}.{part}: {len(rates):,} bars ✓")
                frames.append(pd.DataFrame(rates))
            cursor = part_end
        return frames
