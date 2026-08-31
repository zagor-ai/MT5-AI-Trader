"""TPB-M5-001: Trend Pullback + Structure Break research engine.

Research only: never sends orders.
Requires a running MT5 terminal and MetaTrader5/pandas/numpy packages.
"""
from __future__ import annotations
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd
import MetaTrader5 as mt5

@dataclass
class Config:
    symbol: str = "XAUUSD"
    start: str = "2020-01-01"
    end: str = "2026-08-31"
    swing_left: int = 2
    swing_right: int = 2
    ema_fast: int = 20
    ema_mid: int = 50
    ema_slow: int = 200
    atr_period: int = 14
    min_impulse_atr: float = 1.0
    min_pullback: float = 0.25
    max_pullback: float = 0.786
    bos_atr: float = 0.05
    sl_buffer_atr: float = 0.15
    min_sl_atr: float = 0.50
    max_sl_atr: float = 2.00
    rr: float = 2.0
    max_hold_bars: int = 72
    diagnostic_bars: int = 1000
    max_bars_m5: int = 100000
    max_bars_h1: int = 50000
    max_bars_h4: int = 20000

CFG = Config()


def _find_symbol():
    candidates = [CFG.symbol, "XAUUSDm", "XAUUSD.a", "XAUUSD.", "GOLD", "GOLDm"]
    for name in candidates:
        info = mt5.symbol_info(name)
        if info is not None and mt5.symbol_select(name, True):
            return name, info
    symbols = mt5.symbols_get()
    matches = [] if symbols is None else [s for s in symbols if "XAU" in s.name.upper() or "GOLD" in s.name.upper()]
    for info in matches:
        if mt5.symbol_select(info.name, True):
            return info.name, info
    return None, None


def rates(tf, tf_name, count):
    """Load recent bars by position; avoids copy_rates_range parameter issues."""
    print(f"[MT5-DATA] Requesting {count} recent {tf_name} bars...", flush=True)
    a = mt5.copy_rates_from_pos(CFG.symbol, tf, 0, int(count))
    err = mt5.last_error()
    if a is None:
        raise RuntimeError(f"MT5 data request failed for {CFG.symbol} {tf_name}: {err}")
    if len(a) == 0:
        raise RuntimeError(f"Zero MT5 bars for {CFG.symbol} {tf_name}: {err}")
    x = pd.DataFrame(a)
    if "time" not in x.columns:
        raise RuntimeError(f"Unexpected MT5 response for {CFG.symbol} {tf_name}")
    x["time"] = pd.to_datetime(x["time"], unit="s", utc=True)
    x = x.drop_duplicates("time").sort_values("time").set_index("time")
    print(f"[MT5-DATA] {tf_name}: bars={len(x)} range={x.index.min()} -> {x.index.max()}", flush=True)
    return x


def integrity(x, tf):
    required = ["open", "high", "low", "close"]
    bad = ((x.high < x[["open", "close"]].max(axis=1)) | (x.low > x[["open", "close"]].min(axis=1))).sum()
    return {
        "timeframe": tf,
        "bars": int(len(x)),
        "duplicates": int(x.index.duplicated().sum()),
        "nan_ohlc": int(x[required].isna().any(axis=1).sum()),
        "bad_ohlc": int(bad),
        "healthy": bool(bad == 0 and x.index.is_monotonic_increasing),
        "first_bar_utc": str(x.index.min()),
        "last_bar_utc": str(x.index.max()),
    }


def add_features(x):
    x = x.copy()
    x["ema20"] = x.close.ewm(span=20, adjust=False, min_periods=20).mean()
    x["ema50"] = x.close.ewm(span=50, adjust=False, min_periods=50).mean()
    x["ema200"] = x.close.ewm(span=200, adjust=False, min_periods=200).mean()
    pc = x.close.shift(1)
    tr = pd.concat([(x.high-x.low), (x.high-pc).abs(), (x.low-pc).abs()], axis=1).max(axis=1)
    x["atr14"] = tr.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    L, R = CFG.swing_left, CFG.swing_right
    ph, pl = np.full(len(x), np.nan), np.full(len(x), np.nan)
    h, l = x.high.to_numpy(), x.low.to_numpy()
    for i in range(L, len(x)-R):
        if h[i] > h[i-L:i].max() and h[i] >= h[i+1:i+R+1].max(): ph[i] = h[i]
        if l[i] < l[i-L:i].min() and l[i] <= l[i+1:i+R+1].min(): pl[i] = l[i]
    x["pivot_high"] = pd.Series(ph, index=x.index).shift(R)
    x["pivot_low"] = pd.Series(pl, index=x.index).shift(R)
    return x


def htf_regime(x):
    x = x.copy()
    x["ema20"] = x.close.ewm(span=20, adjust=False, min_periods=20).mean()
    x["ema50"] = x.close.ewm(span=50, adjust=False, min_periods=50).mean()
    x["ema200"] = x.close.ewm(span=200, adjust=False, min_periods=200).mean()
    x["bull"] = (x.close > x.ema200) & (x.ema20 > x.ema50)
    x["bear"] = (x.close < x.ema200) & (x.ema20 < x.ema50)
    return x[["bull","bear"]]


def run_backtest(m5, h1, h4):
    m5 = add_features(m5)
    h1 = htf_regime(h1).rename(columns={"bull":"h1_bull","bear":"h1_bear"})
    h4 = htf_regime(h4).rename(columns={"bull":"h4_bull","bear":"h4_bear"})
    m5 = pd.merge_asof(m5.sort_index(), h1.sort_index(), left_index=True, right_index=True, direction="backward")
    m5 = pd.merge_asof(m5.sort_index(), h4.sort_index(), left_index=True, right_index=True, direction="backward")
    m5 = m5.dropna(subset=["ema20","ema50","ema200","atr14"])
    trades, highs, lows = [], [], []
    last_exit = -1
    for i in range(len(m5)-CFG.max_hold_bars-1):
        if i <= last_exit: continue
        r = m5.iloc[i]
        if not np.isfinite(r.atr14): continue
        if np.isfinite(r.pivot_high): highs.append((i,float(r.pivot_high)))
        if np.isfinite(r.pivot_low): lows.append((i,float(r.pivot_low)))
        long_ok = bool(r.h1_bull and r.h4_bull and r.ema20 > r.ema50 > r.ema200 and r.close > r.ema200)
        short_ok = bool(r.h1_bear and r.h4_bear and r.ema20 < r.ema50 < r.ema200 and r.close < r.ema200)
        def execute(direction, swing, level):
            nonlocal last_exit
            ei=i+1; entry=float(m5.iloc[ei].open); atr=float(r.atr14)
            sl = swing - CFG.sl_buffer_atr*atr if direction=="LONG" else swing + CFG.sl_buffer_atr*atr
            risk = entry-sl if direction=="LONG" else sl-entry
            if not (CFG.min_sl_atr*atr <= risk <= CFG.max_sl_atr*atr): return False
            tp = entry + CFG.rr*risk if direction=="LONG" else entry-CFG.rr*risk
            result, rr, hold = "OPEN",0.0,0
            for j in range(ei+1,min(len(m5),ei+1+CFG.max_hold_bars)):
                b=m5.iloc[j]; hold=j-ei
                hit_sl=b.low<=sl if direction=="LONG" else b.high>=sl
                hit_tp=b.high>=tp if direction=="LONG" else b.low<=tp
                if hit_sl and hit_tp or hit_sl: result,rr="LOSS",-1.0; break
                if hit_tp: result,rr="WIN",CFG.rr; break
            else:
                b=m5.iloc[min(len(m5)-1,ei+CFG.max_hold_bars)]
                rr=((b.close-entry)/risk) if direction=="LONG" else ((entry-b.close)/risk); result="TIME"
            trades.append({"signal_time":m5.index[i],"entry_time":m5.index[ei],"direction":direction,"entry":entry,"sl":sl,"tp":tp,"result":result,"r":rr,"hold_bars":hold})
            last_exit=ei+hold
            return True
        if long_ok and lows and highs:
            li, pl = lows[-1]; prior=[z for z in highs if z[0]<li]
            if prior and highs[-1][0]>li:
                hi, ih=prior[-1]; bh, level=highs[-1]; full=ih-float(m5.iloc[hi].low)
                retr=(ih-pl)/full if full>0 else 0
                if full>=CFG.min_impulse_atr*r.atr14 and CFG.min_pullback<=retr<=CFG.max_pullback and i>bh and r.close>level and r.close-level>=CFG.bos_atr*r.atr14:
                    if execute("LONG",pl,level): continue
        if short_ok and highs and lows:
            hi, ph=highs[-1]; prior=[z for z in lows if z[0]<hi]
            if prior and lows[-1][0]>hi:
                li, il=prior[-1]; bl, level=lows[-1]; full=float(m5.iloc[li].high)-il
                retr=(ph-il)/full if full>0 else 0
                if full>=CFG.min_impulse_atr*r.atr14 and CFG.min_pullback<=retr<=CFG.max_pullback and i>bl and r.close<level and level-r.close>=CFG.bos_atr*r.atr14:
                    if execute("SHORT",ph,level): continue
    t=pd.DataFrame(trades)
    if t.empty: return m5,t,{"trades":0,"verdict":"NO_TRADES"}
    gp=t.loc[t.r>0,"r"].sum(); gl=-t.loc[t.r<0,"r"].sum(); eq=t.r.cumsum(); dd=(eq.cummax()-eq).max()
    pf=float(gp/gl) if gl else float("inf")
    metrics={"trades":len(t),"wins":int((t.r>0).sum()),"losses":int((t.r<0).sum()),"win_rate_pct":round(100*(t.r>0).mean(),2),"profit_factor":pf,"expectancy_R":float(t.r.mean()),"net_R":float(t.r.sum()),"max_drawdown_R":float(dd),"verdict":"PROMISING" if t.r.mean()>0 else "WEAK"}
    return m5,t,metrics


def main():
    if not mt5.initialize(): raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()}")
    terminal = mt5.terminal_info()
    print(f"[MT5] Connected. Terminal={getattr(terminal,'name','?')} Build={getattr(terminal,'build','?')}")
    actual, info = _find_symbol()
    if actual is None:
        names = mt5.symbols_get(group="*XAU*") or []
        names += mt5.symbols_get(group="*GOLD*") or []
        sample = [s.name for s in names[:30]]
        raise RuntimeError(f"No XAU/GOLD symbol found. Requested={CFG.symbol}. Candidates={sample}. last_error={mt5.last_error()}")
    if actual != CFG.symbol:
        print(f"[MT5] Requested {CFG.symbol}; using available symbol {actual}")
        CFG.symbol = actual
    print(f"[MT5] Symbol={CFG.symbol} digits={info.digits} point={info.point}")
    print("[TPB] Research only; no orders will be sent.")
    m5 = rates(mt5.TIMEFRAME_M5,"M5",CFG.max_bars_m5)
    h1 = rates(mt5.TIMEFRAME_H1,"H1",CFG.max_bars_h1)
    h4 = rates(mt5.TIMEFRAME_H4,"H4",CFG.max_bars_h4)
    reports={"M5":integrity(m5,"M5"),"H1":integrity(h1,"H1"),"H4":integrity(h4,"H4")}
    for k,v in reports.items(): print(f"[INTEGRITY] {k}: bars={v['bars']} healthy={v['healthy']} range={v['first_bar_utc']} -> {v['last_bar_utc']}")
    if not all(v["healthy"] for v in reports.values()): raise RuntimeError(f"Data integrity failed: {reports}")
    m5,t,metrics=run_backtest(m5,h1,h4)
    run=Path("research_runs")/("R"+datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")); run.mkdir(parents=True,exist_ok=True)
    m5.reset_index().to_csv(run/"XAUUSD_M5_features.csv",index=False); t.to_csv(run/"TPB_M5_001_trades.csv",index=False)
    report={"strategy_id":"TPB-M5-001","version":"1.2","config":asdict(CFG),"data_integrity":reports,"metrics":metrics,"research_only":True,"live_orders_sent":False}
    (run/"TPB_M5_001_report.json").write_text(json.dumps(report,indent=2,default=str),encoding="utf-8")
    print(json.dumps(metrics,indent=2,default=str)); print(f"[EXPORT] {run.resolve()}")
    mt5.shutdown()

if __name__=="__main__": main()
