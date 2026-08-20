from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "XAU_Strategy_Researcher_Pro_v2.1.py"
OUT = ROOT / "XAU_Strategy_Researcher_Pro_v2.1.1.py"

if not SRC.exists():
    raise SystemExit(f"Source not found: {SRC}")

text = SRC.read_text(encoding="utf-8")

# Preserve the complete application and change only version + load_rates().
text = re.sub(r'(?m)^VERSION\s*=\s*["\']2\.1["\']', 'VERSION = "2.1.1"', text, count=1)

start_marker = "    def load_rates(self, symbol, timeframe, start, end, logger):"
end_marker = "\n\n# ============================================================\n# INDICATORS\n# ============================================================"
start = text.find(start_marker)
end = text.find(end_marker, start)
if start < 0 or end < 0:
    raise SystemExit("Could not locate the complete load_rates() block; refusing to create a partial file.")

method = '''    def load_rates(self, symbol, timeframe, start, end, logger):
        """Load MT5 history in bounded chunks; research-only, no orders."""
        self.initialize()

        logger("[MT5] Initializing terminal...")
        terminal = mt5.terminal_info()
        account = mt5.account_info()

        if terminal:
            logger(f"[MT5] Terminal: {getattr(terminal, 'name', 'Unknown')}")
            logger(f"[MT5] Build: {getattr(terminal, 'build', 'Unknown')}")
        if account:
            logger(f"[MT5] Account: {getattr(account, 'login', 'Unknown')}")
            logger(f"[MT5] Server: {getattr(account, 'server', 'Unknown')}")

        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            raise RuntimeError(f"Symbol '{symbol}' is not available.\\nMT5 error: {mt5_error_text()}")
        if not mt5.symbol_select(symbol, True):
            raise RuntimeError(f"Cannot select {symbol}.\\nMT5 error: {mt5_error_text()}")

        logger(f"[MT5] Symbol: {symbol} AVAILABLE ✓")
        tick = mt5.symbol_info_tick(symbol)
        if tick:
            logger(f"[MT5] Tick: Bid={safe_float(tick.bid):.3f} Ask={safe_float(tick.ask):.3f}")

        try:
            start_dt = datetime.strptime(start, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            end_dt = (datetime.strptime(end, "%Y-%m-%d") + timedelta(days=1)).replace(tzinfo=timezone.utc)
        except ValueError:
            raise RuntimeError("Date format must be YYYY-MM-DD.")

        if timeframe not in TIMEFRAMES:
            raise RuntimeError(f"Unsupported timeframe: {timeframe}")
        tf = getattr(mt5, TIMEFRAMES[timeframe])

        logger(f"[DATA] Requested range: {start} -> {end}")

        # Keep requests small enough for terminals with limited history settings.
        chunk_days = 30
        retry_days = 7
        chunks = []
        cursor = start_dt
        total_chunks = max(1, ((end_dt - start_dt).days + chunk_days - 1) // chunk_days)
        chunk_no = 0

        while cursor < end_dt:
            chunk_no += 1
            chunk_end = min(cursor + timedelta(days=chunk_days), end_dt)
            logger(f"[DATA] Chunk {chunk_no}/{total_chunks}: {cursor.date()} -> {chunk_end.date()}")

            rates = mt5.copy_rates_range(symbol, tf, cursor, chunk_end)
            if rates is not None and len(rates):
                chunks.append(rates)
                logger(f"[DATA] Chunk {chunk_no}: {len(rates):,} bars ✓")
            else:
                logger(f"[WARN] Chunk {chunk_no} failed: {mt5_error_text()}")
                sub = cursor
                while sub < chunk_end:
                    sub_end = min(sub + timedelta(days=retry_days), chunk_end)
                    sub_rates = mt5.copy_rates_range(symbol, tf, sub, sub_end)
                    if sub_rates is not None and len(sub_rates):
                        chunks.append(sub_rates)
                        logger(f"[DATA] Retry {sub.date()} -> {sub_end.date()}: {len(sub_rates):,} bars ✓")
                    else:
                        logger(f"[WARN] Retry {sub.date()} -> {sub_end.date()}: {mt5_error_text()}")
                    sub = sub_end

            cursor = chunk_end

        if not chunks:
            raise RuntimeError(
                "No historical data returned from MT5.\\n"
                f"Last error: {mt5_error_text()}\\n"
                "Check that the requested history is available in the MT5 terminal."
            )

        logger("[DATA] Combining historical chunks...")
        df = pd.DataFrame(np.concatenate(chunks))
        if df.empty:
            raise RuntimeError("Combined historical dataset is empty.")

        required = ["time", "open", "high", "low", "close"]
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise RuntimeError("MT5 data missing columns: " + ", ".join(missing))

        raw_count = len(df)
        df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
        df = df.drop_duplicates(subset=["time"]).sort_values("time").set_index("time")

        for col in ["open", "high", "low", "close"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        if "spread" in df.columns:
            df["spread"] = pd.to_numeric(df["spread"], errors="coerce").fillna(0.0)
            spread_available = True
        else:
            df["spread"] = 0.0
            spread_available = False
        df["spread_available"] = spread_available

        before_clean = len(df)
        df = df.dropna(subset=["open", "high", "low", "close"])
        df = df[
            (df["high"] >= df["low"])
            & (df["high"] >= df["open"])
            & (df["high"] >= df["close"])
            & (df["low"] <= df["open"])
            & (df["low"] <= df["close"])
        ]

        logger(f"[DATA] Raw bars collected: {raw_count:,}")
        logger(f"[DATA] Duplicate/invalid rows removed: {before_clean - len(df):,}")
        logger(f"[DATA] Valid bars: {len(df):,} ✓")

        if len(df) < 1000:
            raise RuntimeError(
                f"Only {len(df):,} valid bars available. At least 1000 bars are recommended."
            )

        logger("[DATA] First bar: " + df.index[0].strftime("%Y-%m-%d %H:%M:%S UTC"))
        logger("[DATA] Last bar: " + df.index[-1].strftime("%Y-%m-%d %H:%M:%S UTC"))
        logger("[DATA] Historical spread: " + ("AVAILABLE ✓" if spread_available else "NOT AVAILABLE"))
        logger("[DATA] Historical data load completed ✓")

        return df
'''

text = text[:start] + method + text[end:]
OUT.write_text(text, encoding="utf-8")

lines = len(text.splitlines())
if lines < 1000:
    OUT.unlink(missing_ok=True)
    raise SystemExit(f"Generated file is suspiciously short: {lines} lines")

print(f"Generated {OUT.name}: {lines} lines")
