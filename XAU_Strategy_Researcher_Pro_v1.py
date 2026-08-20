# -*- coding: utf-8 -*-
"""XAU Strategy Researcher Pro v1.0
Rule-based research lab for MetaTrader 5 historical data.
NO live orders are sent.

Install:
    python -m pip install MetaTrader5 pandas numpy
Run:
    python XAU_Strategy_Researcher_Pro_v1.py
"""
from __future__ import annotations

import math
import os
import threading
from itertools import product
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import numpy as np
import pandas as pd

try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None

APP_TITLE = "XAU Strategy Researcher Pro"
VERSION = "1.0"

INDICATORS = [
    "EMA", "RSI", "MACD", "ADX", "ATR", "Bollinger",
    "Stochastic", "Ichimoku", "Price Action", "Spread", "Session"
]

EXPECTED_TF = {"M1": "TIMEFRAME_M1", "M5": "TIMEFRAME_M5", "M15": "TIMEFRAME_M15", "M30": "TIMEFRAME_M30", "H1": "TIMEFRAME_H1"}

@dataclass
class Config:
    symbol: str = "XAUUSD"
    timeframe: str = "M5"
    start: str = "2025-01-01"
    end: str = "2026-08-18"
    mode: str = "Balanced"
    max_candidates: int = 300
    min_train_trades: int = 80
    train_pct: int = 70
    max_spread: float = 80.0
    rr_min: float = 1.4
    rr_max: float = 2.2
    rr_step: float = 0.4
    sl_min: float = 1.0
    sl_max: float = 2.0
    sl_step: float = 0.5
    initial_balance: float = 500.0
    risk_pct: float = 1.0

@dataclass
class Candidate:
    name: str
    direction: str
    params: dict
    train: dict
    test: dict
    stability: float
    score: float

# -----------------------------------------------------------------------------
# MT5
# -----------------------------------------------------------------------------

def mt5_connect():
    if mt5 is None:
        raise RuntimeError("MetaTrader5 Python package is missing. Run: python -m pip install MetaTrader5 pandas numpy")
    if not mt5.initialize():
        raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()}")

def mt5_shutdown():
    if mt5 is not None:
        try: mt5.shutdown()
        except Exception: pass

def tf_value(name):
    if mt5 is None: raise RuntimeError("MetaTrader5 package missing")
    return getattr(mt5, EXPECTED_TF[name])

def load_rates(symbol, timeframe, start, end):
    mt5_connect()
    try:
        if not mt5.symbol_select(symbol, True):
            raise RuntimeError(f"Cannot select {symbol}: {mt5.last_error()}")
        a = datetime.strptime(start, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        b = (datetime.strptime(end, "%Y-%m-%d") + timedelta(days=1)).replace(tzinfo=timezone.utc)
        rates = mt5.copy_rates_range(symbol, tf_value(timeframe), a, b)
        if rates is None or len(rates) == 0:
            raise RuntimeError(f"No bars returned by MT5: {mt5.last_error()}")
        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
        df.set_index("time", inplace=True)
        return df
    finally:
        mt5_shutdown()

# -----------------------------------------------------------------------------
# Indicators
# -----------------------------------------------------------------------------

def EMA(s, n): return s.ewm(span=n, adjust=False).mean()

def RSI(s, n=14):
    d = s.diff(); up = d.clip(lower=0); dn = -d.clip(upper=0)
    au = up.ewm(alpha=1/n, adjust=False).mean(); ad = dn.ewm(alpha=1/n, adjust=False).mean()
    rs = au / ad.replace(0, np.nan)
    return (100 - 100/(1+rs)).fillna(50)

def TR(df):
    pc = df.close.shift(1)
    return pd.concat([df.high-df.low, (df.high-pc).abs(), (df.low-pc).abs()], axis=1).max(axis=1)

def ATR(df, n=14): return TR(df).ewm(alpha=1/n, adjust=False).mean()

def ADX(df, n=14):
    up = df.high.diff(); down = -df.low.diff()
    pdm = pd.Series(np.where((up>down)&(up>0), up, 0.0), index=df.index)
    mdm = pd.Series(np.where((down>up)&(down>0), down, 0.0), index=df.index)
    avtr = TR(df).ewm(alpha=1/n, adjust=False).mean()
    pdi = 100*pdm.ewm(alpha=1/n, adjust=False).mean()/avtr.replace(0,np.nan)
    mdi = 100*mdm.ewm(alpha=1/n, adjust=False).mean()/avtr.replace(0,np.nan)
    dx = 100*(pdi-mdi).abs()/(pdi+mdi).replace(0,np.nan)
    return dx.ewm(alpha=1/n, adjust=False).mean().fillna(0), pdi.fillna(0), mdi.fillna(0)

def MACD(s):
    m = EMA(s,12)-EMA(s,26); sig = EMA(m,9); return m, sig, m-sig

def BB(s, n=20, k=2):
    mid=s.rolling(n).mean(); sd=s.rolling(n).std(); return mid, mid+k*sd, mid-k*sd

def STOCH(df, n=14, d=3):
    lo=df.low.rolling(n).min(); hi=df.high.rolling(n).max(); k=100*(df.close-lo)/(hi-lo).replace(0,np.nan); return k.fillna(50), k.rolling(d).mean().fillna(50)

def build_features(df):
    x=df.copy()
    for n in (9,12,20,21,26,50,100,200): x[f"ema{n}"]=EMA(x.close,n)
    x["rsi14"]=RSI(x.close,14); x["atr14"]=ATR(x,14)
    x["atr_pct"]=x.atr14/x.close.replace(0,np.nan)*100
    x["adx14"],x["plus_di"],x["minus_di"]=ADX(x,14)
    x["macd"],x["macd_sig"],x["macd_hist"]=MACD(x.close)
    x["bb_mid"],x["bb_up"],x["bb_lo"]=BB(x.close)
    x["stoch_k"],x["stoch_d"]=STOCH(x)
    conv=(x.high.rolling(9).max()+x.low.rolling(9).min())/2
    base=(x.high.rolling(26).max()+x.low.rolling(26).min())/2
    x["ichi_conv"]=conv; x["ichi_base"]=base
    x["ichi_a"]=(conv+base)/2; x["ichi_b"]=(x.high.rolling(52).max()+x.low.rolling(52).min())/2
    x["body_pct"]=((x.close-x.open).abs()/(x.high-x.low).replace(0,np.nan)).fillna(0)
    x["bull"]=x.close>x.open; x["bear"]=x.close<x.open; x["hour"]=x.index.hour
    if "spread" not in x: x["spread"]=0.0
    return x

# -----------------------------------------------------------------------------
# Candidate rules
# -----------------------------------------------------------------------------

def session_ok(h, mode):
    if mode=="All": return True
    if mode=="London": return 8<=h<17
    if mode=="NY": return 13<=h<22
    return (8<=h<17) or (13<=h<22)

def signal(df, i, direction, p, selected):
    r=df.iloc[i]; prev=df.iloc[i-1]
    if "EMA" in selected:
        ef=r[f"ema{p['fast']}"].item() if hasattr(r[f"ema{p['fast']}"], 'item') else r[f"ema{p['fast']}" ]
        es=r[f"ema{p['slow']}"].item() if hasattr(r[f"ema{p['slow']}"], 'item') else r[f"ema{p['slow']}" ]
        pef=prev[f"ema{p['fast']}" ]
        if direction=="BUY":
            if not (ef>es and ef>pef): return False
            if abs(r.close-ef)>p["pullback"]*r.atr14: return False
        else:
            if not (ef<es and ef<pef): return False
            if abs(r.close-es)>p["pullback"]*r.atr14: return False
    if "RSI" in selected:
        if direction=="BUY" and not (p["rsi_lo"]<=r.rsi14<=p["rsi_hi"]): return False
        if direction=="SELL" and not (100-p["rsi_hi"]<=r.rsi14<=100-p["rsi_lo"]): return False
    if "MACD" in selected:
        if direction=="BUY" and not (r.macd>r.macd_sig and r.macd_hist>0): return False
        if direction=="SELL" and not (r.macd<r.macd_sig and r.macd_hist<0): return False
    if "ADX" in selected:
        if r.adx14<p["adx"]: return False
        if direction=="BUY" and r.plus_di<=r.minus_di: return False
        if direction=="SELL" and r.minus_di<=r.plus_di: return False
    if "ATR" in selected and not (p["atr_min"]<=r.atr_pct<=p["atr_max"]): return False
    if "Bollinger" in selected:
        if direction=="BUY" and not (prev.close<=prev.bb_mid and r.close>r.bb_mid): return False
        if direction=="SELL" and not (prev.close>=prev.bb_mid and r.close<r.bb_mid): return False
    if "Stochastic" in selected:
        if direction=="BUY" and not (r.stoch_k>r.stoch_d and r.stoch_k<p["stoch_hi"]): return False
        if direction=="SELL" and not (r.stoch_k<r.stoch_d and r.stoch_k>100-p["stoch_hi"]): return False
    if "Ichimoku" in selected:
        top=max(r.ichi_a,r.ichi_b); bot=min(r.ichi_a,r.ichi_b)
        if direction=="BUY" and not (r.close>top and r.ichi_conv>r.ichi_base): return False
        if direction=="SELL" and not (r.close<bot and r.ichi_conv<r.ichi_base): return False
    if "Price Action" in selected:
        if r.body_pct<p["body"]: return False
        if direction=="BUY" and not (r.bull and r.close>prev.high): return False
        if direction=="SELL" and not (r.bear and r.close<prev.low): return False
    if "Spread" in selected and r.spread>p["spread"]: return False
    if "Session" in selected and not session_ok(int(r.hour),p["session"]): return False
    return True

def backtest(df, direction, p, selected, a, b):
    out=[]; i=max(a,200)
    while i<b-1:
        if not signal(df,i,direction,p,selected): i+=1; continue
        sig=df.iloc[i]; entry=float(df.iloc[i+1].open); av=float(sig.atr14)
        if not math.isfinite(av) or av<=0: i+=1; continue
        dist=av*p["sl"]
        if direction=="BUY": sl=entry-dist; tp=entry+dist*p["rr"]
        else: sl=entry+dist; tp=entry-dist*p["rr"]
        exit_price=None; exit_i=None
        for j in range(i+1,min(b,i+p["hold"]+1)):
            bar=df.iloc[j]
            if direction=="BUY":
                if bar.low<=sl: exit_price=sl; exit_i=j; break
                if bar.high>=tp: exit_price=tp; exit_i=j; break
            else:
                if bar.high>=sl: exit_price=sl; exit_i=j; break
                if bar.low<=tp: exit_price=tp; exit_i=j; break
        if exit_price is None: i+=1; continue
        rr=(exit_price-entry)/dist if direction=="BUY" else (entry-exit_price)/dist
        # Conservative small spread penalty in R, capped.
        sp=float(df.iloc[i+1].get("spread",0.0)); rr-=min(0.10, sp/max(p["spread"],1.0)*0.05) if sp>0 else 0
        out.append(rr); i=exit_i+1
    return np.array(out,dtype=float)

def summary(arr):
    if len(arr)==0: return {"trades":0,"win":0,"pf":0.0,"net":0.0,"exp":0.0,"dd":0.0}
    gp=float(arr[arr>0].sum()); gl=float(abs(arr[arr<0].sum())); pf=(math.inf if gp>0 and gl==0 else (gp/gl if gl else 0.0))
    eq=np.cumsum(arr); peak=np.maximum.accumulate(np.maximum(eq,0)); dd=float(np.max(peak-eq))
    return {"trades":int(len(arr)),"win":float((arr>0).mean()*100),"pf":pf,"net":float(arr.sum()),"exp":float(arr.mean()),"dd":dd}

# -----------------------------------------------------------------------------
# Research
# -----------------------------------------------------------------------------

def parameter_candidates(cfg, selected):
    if cfg.mode=="Conservative":
        ema_pairs=[(20,50),(50,200)]; rsi=[(52,65),(55,68)]; adx=[20,25]; pull=[.25,.35]; sls=[cfg.sl_min]; rrs=[cfg.rr_min]
    elif cfg.mode=="Aggressive":
        ema_pairs=[(9,21),(20,50),(20,100),(50,200)]; rsi=[(50,65),(52,68),(55,70),(45,60)]; adx=[18,20,25,30]; pull=[.2,.3,.5,.7]
        sls=list(np.arange(cfg.sl_min,cfg.sl_max+.001,cfg.sl_step)); rrs=list(np.arange(cfg.rr_min,cfg.rr_max+.001,cfg.rr_step))
    else:
        ema_pairs=[(9,21),(20,50),(20,100),(50,200)]; rsi=[(50,65),(52,68),(55,68),(45,60)]; adx=[18,20,25]; pull=[.25,.35,.5]
        sls=list(np.arange(cfg.sl_min,cfg.sl_max+.001,cfg.sl_step)); rrs=list(np.arange(cfg.rr_min,cfg.rr_max+.001,cfg.rr_step))
    if "EMA" not in selected: ema_pairs=[(20,50)]
    if "RSI" not in selected: rsi=[(52,68)]
    if "ADX" not in selected: adx=[20]
    if "ATR" not in selected: atr_ranges=[(0.0,999.0)]
    else: atr_ranges=[(0.03,0.10),(0.05,0.15),(0.03,0.20),(0.05,0.30)]
    res=[]
    for ep,rrng,adx_v,atr_rng,pb,rr_v,sl_v in product(ema_pairs,rsi,adx,atr_ranges,pull,rrs,sls):
        p={"fast":ep[0],"slow":ep[1],"rsi_lo":rrng[0],"rsi_hi":rrng[1],"adx":float(adx_v),"atr_min":float(atr_rng[0]),"atr_max":float(atr_rng[1]),"pullback":float(pb),"sl":float(sl_v),"rr":float(rr_v),"body":.45,"spread":cfg.max_spread,"session":"London+NY","hold":36,"stoch_hi":70}
        res.append(p)
    return res

def research(df,cfg,selected,log):
    params_list=parameter_candidates(cfg,selected)
    if len(params_list)>cfg.max_candidates: params_list=params_list[:cfg.max_candidates]
    n=len(df); split=int(n*cfg.train_pct/100); directions=["BUY","SELL"]
    if selected.intersection({"BUY_ONLY"}): directions=["BUY"]
    if selected.intersection({"SELL_ONLY"}): directions=["SELL"]
    results=[]
    log(f"Bars={n:,} | candidates={len(params_list)} | train={cfg.train_pct}% / OOS={100-cfg.train_pct}%")
    for k,p in enumerate(params_list,1):
        for d in directions:
            tr=backtest(df,d,p,selected,0,split); te=backtest(df,d,p,selected,split,n)
            ts=summary(tr); es=summary(te)
            if ts["trades"]<cfg.min_train_trades or es["trades"]<max(10,cfg.min_train_trades//4): continue
            if es["pf"]<=0: continue
            stability=max(0,min(100,(min(es["pf"]/max(ts["pf"],.01),1.0)*70)+(max(0,min(es["exp"]/0.25,1.0))*30)))
            score=min(100,max(0,(0 if math.isinf(es["pf"]) else max(0,(es["pf"]-0.75)*32)) + max(0,(ts["pf"]-0.9)*18) + max(0,es["exp"]*50) + min(10,es["trades"]/50) + max(0,10-es["dd"]*.75) + stability*.10))
            name=f"{d} | EMA {p['fast']}/{p['slow']} | RSI {p['rsi_lo']:.0f}-{p['rsi_hi']:.0f} | ADX {p['adx']:.0f} | SL {p['sl']:.1f} | RR {p['rr']:.1f}"
            results.append(Candidate(name,d,p,ts,es,stability,score))
        if k%20==0: log(f"Progress {k}/{len(params_list)}")
    results.sort(key=lambda x:x.score,reverse=True)
    return results

# -----------------------------------------------------------------------------
# GUI
# -----------------------------------------------------------------------------

class App(tk.Tk):
    def __init__(self):
        super().__init__(); self.title(f"{APP_TITLE} v{VERSION}"); self.geometry("1400x900"); self.minsize(1100,700)
        self.df=None; self.results=[]; self.selected=None
        self.vars={n:tk.BooleanVar(value=n in {"EMA","RSI","ATR","Price Action","Spread","Session"}) for n in INDICATORS}
        self.build()
    def build(self):
        style=ttk.Style(self)
        try: style.theme_use("clam")
        except tk.TclError: pass
        style.configure("Title.TLabel",font=("Segoe UI",20,"bold")); style.configure("Treeview",rowheight=28)
        top=ttk.Frame(self,padding=10); top.pack(fill="x")
        ttk.Label(top,text=APP_TITLE,style="Title.TLabel").pack(side="left")
        ttk.Label(top,text="MT5 research only — NO live trading",foreground="#777").pack(side="left",padx=20)
        pan=ttk.Panedwindow(self,orient="horizontal"); pan.pack(fill="both",expand=True,padx=8,pady=5)
        left=ttk.Frame(pan,padding=8); right=ttk.Frame(pan,padding=8); pan.add(left,weight=0); pan.add(right,weight=1)
        self.settings(left); self.results_ui(right)
    def settings(self,p):
        box=ttk.LabelFrame(p,text="MT5 Data",padding=8); box.pack(fill="x",pady=4)
        self.symbol=tk.StringVar(value="XAUUSD"); self.tf=tk.StringVar(value="M5"); self.start=tk.StringVar(value="2025-01-01"); self.end=tk.StringVar(value="2026-08-18")
        for label,var in [("Symbol",self.symbol),("Start UTC",self.start),("End UTC",self.end)]:
            ttk.Label(box,text=label).pack(anchor="w"); ttk.Entry(box,textvariable=var).pack(fill="x",pady=2)
        ttk.Label(box,text="Timeframe").pack(anchor="w"); ttk.Combobox(box,textvariable=self.tf,values=list(EXPECTED_TF),state="readonly").pack(fill="x",pady=2)
        ttk.Button(box,text="Test MT5",command=self.test_mt5).pack(fill="x",pady=2); ttk.Button(box,text="Load MT5 Data",command=self.load_data).pack(fill="x",pady=2)
        ib=ttk.LabelFrame(p,text="Indicators / Filters",padding=8); ib.pack(fill="x",pady=4)
        for n in INDICATORS: ttk.Checkbutton(ib,text=n,variable=self.vars[n]).pack(anchor="w")
        db=ttk.LabelFrame(p,text="Direction",padding=8); db.pack(fill="x",pady=4); self.direction=tk.StringVar(value="BUY + SELL")
        for x in ("BUY + SELL","BUY ONLY","SELL ONLY"): ttk.Radiobutton(db,text=x,value=x,variable=self.direction).pack(anchor="w")
        rb=ttk.LabelFrame(p,text="Research",padding=8); rb.pack(fill="x",pady=4)
        self.mode=tk.StringVar(value="Balanced"); self.maxcand=tk.StringVar(value="300"); self.mintr=tk.StringVar(value="80"); self.trainpct=tk.StringVar(value="70"); self.maxspread=tk.StringVar(value="80"); self.slmin=tk.StringVar(value="1.0"); self.slmax=tk.StringVar(value="2.0")
        ttk.Label(rb,text="Mode").pack(anchor="w"); ttk.Combobox(rb,textvariable=self.mode,values=("Conservative","Balanced","Aggressive"),state="readonly").pack(fill="x",pady=2)
        for label,var in [("Max Candidates",self.maxcand),("Min Train Trades",self.mintr),("Train %",self.trainpct),("Max Spread",self.maxspread),("SL ATR Min",self.slmin),("SL ATR Max",self.slmax)]:
            ttk.Label(rb,text=label).pack(anchor="w"); ttk.Entry(rb,textvariable=var).pack(fill="x",pady=2)
        ttk.Button(p,text="▶ START STRATEGY RESEARCH",command=self.start).pack(fill="x",pady=10,ipady=7); ttk.Button(p,text="Export Selected",command=self.export).pack(fill="x",pady=2)
    def results_ui(self,p):
        nb=ttk.Notebook(p); nb.pack(fill="both",expand=True)
        page=ttk.Frame(nb); detail=ttk.Frame(nb); log=ttk.Frame(nb); nb.add(page,text="Strategy Ranking"); nb.add(detail,text="Selected Strategy"); nb.add(log,text="Log"); self.nb=nb
        cols=("rank","strategy","train","trainpf","oospf","oosnet","oosdd","ooswin","stability","score")
        self.tree=ttk.Treeview(page,columns=cols,show="headings")
        heads={"rank":"#","strategy":"Strategy","train":"Train","trainpf":"Train PF","oospf":"OOS PF","oosnet":"OOS Net R","oosdd":"OOS DD R","ooswin":"OOS Win %","stability":"Stability","score":"Score"}
        widths={"rank":40,"strategy":500,"train":70,"trainpf":70,"oospf":70,"oosnet":80,"oosdd":80,"ooswin":80,"stability":80,"score":70}
        for c in cols: self.tree.heading(c,text=heads[c]); self.tree.column(c,width=widths[c],anchor="center")
        y=ttk.Scrollbar(page,orient="vertical",command=self.tree.yview); self.tree.configure(yscrollcommand=y.set); self.tree.grid(row=0,column=0,sticky="nsew"); y.grid(row=0,column=1,sticky="ns"); page.rowconfigure(0,weight=1); page.columnconfigure(0,weight=1); self.tree.bind("<<TreeviewSelect>>",self.select)
        self.detail=tk.Text(detail,font=("Consolas",10)); self.detail.pack(fill="both",expand=True)
        self.logbox=tk.Text(log,font=("Consolas",9)); self.logbox.pack(fill="both",expand=True)
    def cfg(self):
        return Config(symbol=self.symbol.get().strip(),timeframe=self.tf.get(),start=self.start.get().strip(),end=self.end.get().strip(),mode=self.mode.get(),max_candidates=max(1,int(self.maxcand.get())),min_train_trades=max(10,int(self.mintr.get())),train_pct=min(90,max(50,int(self.trainpct.get()))),max_spread=float(self.maxspread.get()),sl_min=float(self.slmin.get()),sl_max=float(self.slmax.get()))
    def selected_inds(self):
        s={n for n,v in self.vars.items() if v.get()}
        if self.direction.get()=="BUY ONLY": s.add("BUY_ONLY")
        if self.direction.get()=="SELL ONLY": s.add("SELL_ONLY")
        return s
    def test_mt5(self):
        try:
            mt5_connect(); info=mt5.terminal_info(); acc=mt5.account_info(); text=f"MT5 OK\nTerminal: {info.name if info else 'Unknown'}\nLogin: {acc.login if acc else 'N/A'}\nBalance: {acc.balance:.2f} {acc.currency}" if acc else "MT5 OK\nAccount info unavailable"; messagebox.showinfo("MT5",text)
        except Exception as e: messagebox.showerror("MT5",str(e))
        finally: mt5_shutdown()
    def load_data(self):
        try:
            self.log("Downloading historical data from MT5..."); raw=load_rates(self.symbol.get().strip(),self.tf.get(),self.start.get().strip(),self.end.get().strip()); self.df=build_features(raw); self.log(f"Loaded {len(self.df):,} bars."); messagebox.showinfo("Data",f"Loaded {len(self.df):,} bars")
        except Exception as e: messagebox.showerror("Data",str(e))
    def start(self):
        try: cfg=self.cfg()
        except Exception as e: messagebox.showerror("Settings",str(e)); return
        inds=self.selected_inds(); real=inds-{"BUY_ONLY","SELL_ONLY"}
        if not real: messagebox.showwarning("Indicators","Select at least one indicator/filter."); return
        if self.df is None: self.load_data()
        if self.df is None: return
        self.logbox.delete("1.0","end"); self.results=[]; self.selected=None
        threading.Thread(target=self.worker,args=(cfg,inds),daemon=True).start()
    def worker(self,cfg,inds):
        try:
            self.log(f"Research started on {len(self.df):,} bars.")
            res=research(self.df,cfg,inds,self.thread_log)
            self.after(0,lambda:self.finish(res))
        except Exception as e: self.after(0,lambda:messagebox.showerror("Research",str(e)))
    def finish(self,res):
        self.results=res
        for i in self.tree.get_children(): self.tree.delete(i)
        for i,c in enumerate(res[:100]):
            self.tree.insert("","end",iid=str(i),values=(i+1,c.name,c.train["trades"],pf(c.train["pf"]),pf(c.test["pf"]),f"{c.test['net']:.2f}",f"{c.test['dd']:.2f}",f"{c.test['win']:.1f}",f"{c.stability:.1f}",f"{c.score:.2f}"))
        if res: self.show(res[0])
        self.log(f"Finished. Valid strategies: {len(res)}")
    def select(self,event=None):
        s=self.tree.selection()
        if s: self.selected=self.results[int(s[0])]; self.show(self.selected); self.nb.select(1)
    def show(self,c):
        self.selected=c; self.detail.delete("1.0","end"); lines=["XAU STRATEGY RESEARCH RESULT","="*90,f"Strategy: {c.name}",f"Score: {c.score:.2f}",f"Stability: {c.stability:.1f}","","PARAMETERS","-"*90]
        lines += [f"{k} = {v}" for k,v in c.params.items()]; lines += ["","TRAIN","-"*90,f"Trades: {c.train['trades']}",f"PF: {pf(c.train['pf'])}",f"Win: {c.train['win']:.1f}%",f"Net R: {c.train['net']:.3f}",f"DD R: {c.train['dd']:.3f}","","OUT OF SAMPLE","-"*90,f"Trades: {c.test['trades']}",f"PF: {pf(c.test['pf'])}",f"Win: {c.test['win']:.1f}%",f"Net R: {c.test['net']:.3f}",f"DD R: {c.test['dd']:.3f}","","STATUS","-"*90]
        lines.append("PROMISING" if c.test["pf"]>=1.2 and c.stability>=70 else ("BORDERLINE" if c.test["pf"]>=1 else "WEAK")); lines += ["","This is a research ranking only; it does not guarantee future profit.","Backtest model: signal on closed bar, entry next bar open, SL-first if SL and TP are both touched in the same bar."]
        self.detail.insert("1.0","\n".join(lines))
    def export(self):
        if not self.selected: messagebox.showinfo("Export","Select a strategy first."); return
        p=filedialog.asksaveasfilename(defaultextension=".txt",initialfile="XAU_Best_Strategy.txt",filetypes=[("Text","*.txt"),("All files","*.*")])
        if not p:return
        c=self.selected; text=self.detail.get("1.0","end-1c"); Path(p).write_text(text,encoding="utf-8"); messagebox.showinfo("Export",f"Saved:\n{p}")
    def log(self,text): self.logbox.insert("end",f"{datetime.now().strftime('%H:%M:%S')} | {text}\n"); self.logbox.see("end"); self.update_idletasks()
    def thread_log(self,text): self.after(0,lambda:self.log(text))

def pf(v): return "∞" if math.isinf(v) else f"{v:.2f}"

if __name__=="__main__":
    app=App(); app.mainloop()
