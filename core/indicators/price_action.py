"""Conservative price-action features for research signals."""
import pandas as pd


def features(df: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(index=df.index)
    o, h, l, c = df["open"], df["high"], df["low"], df["close"]
    body = (c - o).abs()
    rng = (h - l).replace(0, pd.NA)
    upper = h - pd.concat([o, c], axis=1).max(axis=1)
    lower = pd.concat([o, c], axis=1).min(axis=1) - l
    out["bullish_engulfing"] = (c > o) & (c.shift(1) < o.shift(1)) & (c >= o.shift(1)) & (o <= c.shift(1))
    out["bearish_engulfing"] = (c < o) & (c.shift(1) > o.shift(1)) & (c <= o.shift(1)) & (o >= c.shift(1))
    out["bullish_wick"] = (lower / rng) >= 0.55
    out["bearish_wick"] = (upper / rng) >= 0.55
    out["body_ratio"] = body / rng
    return out
