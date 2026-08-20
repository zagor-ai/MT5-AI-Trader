"""Top-level orchestration for modular XAU strategy research."""
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import Any, Callable, Dict, List, Optional
import pandas as pd
from .backtester import BacktestConfig, Backtester
from .ranking import StrategyRanker
from .signal_engine import SignalEngine
from .strategy_generator import StrategyGenerator, StrategySpec
from .validation.train_test import chronological_split
from .validation.validator import validation_score
from .validation.walk_forward import evaluate_walk_forward
from .validation.walk_forward_score import walk_forward_score
from .exporter import export_results
from validation.monte_carlo import MonteCarloConfig, MonteCarloSimulator
from validation.parameter_sensitivity import SensitivityConfig, analyze_parameter
from validation.market_regime import RegimeConfig, analyze_regimes, detect_regimes, regime_robustness_score

@dataclass
class ResearchConfig:
    max_candidates: int = 300
    initial_balance: float = 10000.0
    risk_percent: float = 1.0
    default_rr: float = 2.0
    train_ratio: float = 0.70
    min_train_trades: int = 30
    min_oos_trades: int = 10
    top_n_oos: int = 20
    walk_forward_enabled: bool = True
    walk_forward_train_bars: int = 30000
    walk_forward_test_bars: int = 10000
    walk_forward_step_bars: int = 10000
    walk_forward_min_test_trades: int = 10
    top_n_walk_forward: int = 10
    monte_carlo_enabled: bool = True
    monte_carlo_simulations: int = 2000
    monte_carlo_seed: int = 42
    sensitivity_enabled: bool = True
    sensitivity_top_n: int = 10
    sensitivity_min_score_ratio: float = 0.70
    sensitivity_min_profitable_ratio: float = 0.60
    regime_enabled: bool = True
    regime_top_n: int = 10
    regime_min_bars: int = 100
    export_results: bool = True
    results_dir: str = "results"

class ResearchEngine:
    def __init__(self, config: Optional[ResearchConfig] = None):
        self.config = config or ResearchConfig()
        self.generator = StrategyGenerator(self.config.max_candidates)
        self.signal_engine = SignalEngine()
        self.backtester = Backtester(BacktestConfig(initial_balance=self.config.initial_balance, risk_percent=self.config.risk_percent))
        self.ranker = StrategyRanker()
        self.last_results: List[Dict[str, Any]] = []
        self.last_ranked: List[Dict[str, Any]] = []
        self.last_oos: List[Dict[str, Any]] = []
        self.last_walk_forward: List[Dict[str, Any]] = []
        self.last_exports: Dict[str, str] = {}

    def generate_candidates(self):
        return self.generator.generate()

    def run_candidate(self, data, signals, sl_distance, rr=None):
        result = self.backtester.run(data, signals, sl_distance, self.config.default_rr if rr is None else rr)
        trades = result.trades
        wins = sum(1 for t in trades if t.pnl > 0)
        gp = sum(t.pnl for t in trades if t.pnl > 0)
        gl = abs(sum(t.pnl for t in trades if t.pnl < 0))
        pf = gp / gl if gl > 0 else (float("inf") if gp > 0 else 0.0)
        net_r = sum(t.r_multiple for t in trades)
        expectancy = net_r / len(trades) if trades else 0.0
        peak = self.config.initial_balance
        max_dd_cash = 0.0
        for equity in result.equity_curve:
            peak = max(peak, equity)
            max_dd_cash = max(max_dd_cash, peak - equity)
        return {"final_balance": result.balance, "trade_count": len(trades), "win_rate": 100*wins/len(trades) if trades else 0.0, "profit_factor": pf, "net_r": net_r, "expectancy": expectancy, "max_drawdown": max_dd_cash, "max_drawdown_pct": 100*max_dd_cash/self.config.initial_balance if self.config.initial_balance else 0.0, "max_drawdown_r": max_dd_cash/max(self.config.initial_balance*self.config.risk_percent/100, 1e-9), "equity_curve": result.equity_curve, "trades": [t.to_dict() for t in trades]}

    def evaluate_spec(self, data, spec):
        signals, sl_distance = self.signal_engine.build(data, spec)
        metrics = self.run_candidate(data, signals, sl_distance, float(spec.risk["rr"]))
        metrics.update({"strategy_name": spec.name, "direction": spec.direction, "strategy": spec.to_dict()})
        return metrics

    def _mc(self, item):
        trades = []
        for window in item.get("windows", []):
            trades.extend(window.get("test", {}).get("trades", []))
        if not trades:
            trades = item.get("test", {}).get("trades", [])
        if len(trades) < 2:
            return None
        cfg = MonteCarloConfig(simulations=self.config.monte_carlo_simulations, seed=self.config.monte_carlo_seed, risk_fraction=self.config.risk_percent/100.0)
        return MonteCarloSimulator(cfg).simulate_trades(trades)

    def _nearby(self, value, step, lo, hi):
        try: base = float(value)
        except (TypeError, ValueError): return []
        return [int(v) if float(v).is_integer() else round(v, 4) for v in [base+i*step for i in range(-2, 3)] if lo <= v <= hi]

    def _sensitivity_spec(self, spec, parameter, value):
        indicators = dict(spec.indicators); risk = dict(spec.risk)
        if parameter in indicators: indicators[parameter] = value
        if parameter in risk: risk[parameter] = value
        entry = [dict(x) for x in spec.entry_rules]; exits = [dict(x) for x in spec.exit_rules]
        for r in entry:
            if r.get("type") == "EMA_TREND" and parameter == "ema_fast": r["fast"] = value
            if r.get("type") == "EMA_TREND" and parameter == "ema_slow": r["slow"] = value
            if r.get("type") == "RSI_RANGE" and parameter == "rsi_period": r["period"] = value
            if r.get("type") == "RSI_RANGE" and spec.direction == "BUY" and parameter == "rsi_buy": r["min"] = value
            if r.get("type") == "RSI_RANGE" and spec.direction == "SELL" and parameter == "rsi_sell": r["max"] = value
        for r in exits:
            if r.get("type") == "ATR_SL" and parameter == "atr_sl": r["multiplier"] = value
            if r.get("type") == "RR_TP" and parameter == "rr": r["rr"] = value
        return StrategySpec(spec.name, spec.direction, indicators, entry, exits, risk)

    def _sensitivity(self, item, test_data, stop_event, log=None):
        spec = item["candidate"]
        params = {**spec.indicators, **spec.risk}
        output = {}
        cfg = SensitivityConfig(min_score_ratio=self.config.sensitivity_min_score_ratio, min_profitable_ratio=self.config.sensitivity_min_profitable_ratio)
        for p, base in params.items():
            if stop_event.is_set(): break
            if p in ("ema_fast", "ema_slow"): values = self._nearby(base, 5, 2, 500)
            elif p == "rsi_period": values = self._nearby(base, 1, 2, 100)
            elif p in ("rsi_buy", "rsi_sell"): values = self._nearby(base, 2, 20, 80)
            elif p == "atr_sl": values = self._nearby(base, .25, .5, 4)
            elif p == "rr": values = self._nearby(base, .25, .75, 4)
            else: continue
            def evaluator(v, parameter=p): return self.evaluate_spec(test_data, self._sensitivity_spec(spec, parameter, v))
            output[p] = analyze_parameter(p, float(base), values, evaluator, cfg)
            if log: log(f"[SENSITIVITY] {spec.name} | {p} | Stable={output[p]['stable_ratio']:.1%} | Robustness={output[p]['robustness_score']:.1f}")
        return output

    def _regime(self, data, item, stop_event, log=None):
        if not self.config.regime_enabled or stop_event.is_set(): return None
        regimes = detect_regimes(data)
        spec = item["candidate"]
        def evaluator(subset): return self.evaluate_spec(subset, spec)
        results = analyze_regimes(data, regimes, evaluator, RegimeConfig(min_bars_per_regime=self.config.regime_min_bars))
        score = regime_robustness_score(results)
        if log:
            log(f"[REGIME] {spec.name} | Robustness={score:.1f} | Regimes={len(results)}")
            for r in results: log(f"[REGIME] {r['regime']} | Bars={r['bars']} | Trades={r['trade_count']} | PF={r['profit_factor']:.2f} | NetR={r['net_r']:.2f} | Acceptable={'YES' if r['acceptable'] else 'NO'}")
        return {"score": score, "regimes": results}

    def run_research(self, data, stop_event=None, progress_callback=None, log_callback=None, walk_forward_progress_callback=None):
        if data is None or len(data) < 100: raise ValueError("Insufficient historical data. Load at least 100 bars before research.")
        stop_event = stop_event or Event(); split = chronological_split(data, self.config.train_ratio); train, test = split.train, split.test; candidates = self.generate_candidates(); total = len(candidates); results=[]
        if log_callback: log_callback(f"Started. Candidates: {total}"); log_callback(f"TRAIN/TEST split: {len(train)}/{len(test)} bars")
        for i, spec in enumerate(candidates, 1):
            if stop_event.is_set(): break
            try:
                tr = self.evaluate_spec(train, spec)
                if tr["trade_count"] >= self.config.min_train_trades:
                    te = self.evaluate_spec(test, spec)
                    if te["trade_count"] >= self.config.min_oos_trades:
                        item={"candidate":spec,"train":tr,"test":te,"validation_score":validation_score({"train":tr,"test":te,"oos_to_train_ratio":te["net_r"]/tr["net_r"] if tr["net_r"]>0 else 0.0,"dd_ratio":max(te["max_drawdown_r"],1e-9)/max(tr["max_drawdown_r"],1e-9)}),"candidate_index":i}; results.append(item)
                        if log_callback: log_callback(f"Candidate {i}/{total}: OOS PF={te['profit_factor']:.2f} NetR={te['net_r']:.2f} Validation={item['validation_score']:.2f}")
            except Exception as exc:
                if log_callback: log_callback(f"Candidate {i}/{total} failed: {exc}")
            if progress_callback: progress_callback(i,total)
        self.last_oos=sorted(results,key=lambda x:x["validation_score"],reverse=True); self.last_ranked=self.last_oos[:self.config.top_n_oos]
        if self.config.walk_forward_enabled and self.last_ranked and not stop_event.is_set():
            specs=[x["candidate"] for x in self.last_ranked]
            def ev(d,s): return self.evaluate_spec(d,s) if not stop_event.is_set() else {"trade_count":0,"net_r":0,"profit_factor":0,"max_drawdown_r":0}
            self.last_walk_forward=evaluate_walk_forward(data,specs,ev,self.config.walk_forward_train_bars,self.config.walk_forward_test_bars,self.config.walk_forward_step_bars,self.config.walk_forward_min_test_trades,stop_event,walk_forward_progress_callback,log_callback)
            for x in self.last_walk_forward: x["walk_forward_score"]=walk_forward_score(x)
            self.last_ranked=sorted(self.last_walk_forward,key=lambda x:x["walk_forward_score"],reverse=True)[:self.config.top_n_walk_forward]
        for stage_name, enabled in (("MONTE CARLO",self.config.monte_carlo_enabled),("SENSITIVITY",self.config.sensitivity_enabled),("REGIME",self.config.regime_enabled)):
            if enabled and not stop_event.is_set() and log_callback: log_callback(f"[{stage_name}] Started")
            if enabled and not stop_event.is_set():
                for rank,item in enumerate(self.last_ranked[:self.config.regime_top_n],1):
                    if stop_event.is_set(): break
                    if stage_name=="MONTE CARLO":
                        mc=self._mc(item); item["monte_carlo"]=mc; item["monte_carlo_robustness"]=100*(.5*mc["probability_positive"]+.5*(1-min(1,mc["probability_ruin"]))) if mc else 0
                    elif stage_name=="SENSITIVITY": item["parameter_sensitivity"]=self._sensitivity(item,test,stop_event,log_callback); vals=[v["robustness_score"] for v in item["parameter_sensitivity"].values()]; item["sensitivity_robustness"]=sum(vals)/len(vals) if vals else 0
                    else: item["market_regime"]=self._regime(data,item,stop_event,log_callback); item["regime_robustness"]=item["market_regime"]["score"] if item["market_regime"] else 0
                self.last_ranked=sorted(self.last_ranked,key=lambda x:(x.get("regime_robustness",0),x.get("sensitivity_robustness",0),x.get("monte_carlo_robustness",0),x.get("walk_forward_score",0)),reverse=True)
            if enabled and log_callback and not stop_event.is_set(): log_callback(f"[{stage_name}] Finished")
        self.last_results=results
        if self.config.export_results and self.last_ranked and not stop_event.is_set(): self.last_exports=export_results(self.last_ranked,Path(self.config.results_dir))
        if progress_callback: progress_callback(total,total)
        return self.last_ranked
