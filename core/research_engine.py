"""Top-level orchestration for modular XAU strategy research."""
from dataclasses import dataclass
from threading import Event
from typing import Any, Callable, Dict, List, Optional
from pathlib import Path
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

@dataclass
class ResearchConfig:
    max_candidates: int = 300
    initial_balance: float = 10_000.0
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

    def generate_candidates(self) -> List[StrategySpec]: return self.generator.generate()
    def rank_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        ranked = self.ranker.rank(results); self.last_ranked = ranked; return ranked

    def run_candidate(self, data: pd.DataFrame, signals: pd.Series, sl_distance: pd.Series, rr: Optional[float] = None) -> Dict[str, Any]:
        result = self.backtester.run(data, signals, sl_distance, self.config.default_rr if rr is None else rr)
        trades = result.trades; wins = sum(1 for t in trades if t.pnl > 0); gp = sum(t.pnl for t in trades if t.pnl > 0); gl = abs(sum(t.pnl for t in trades if t.pnl < 0))
        pf = gp / gl if gl > 0 else (float("inf") if gp > 0 else 0.0); win_rate = 100.0 * wins / len(trades) if trades else 0.0; net_r = sum(t.r_multiple for t in trades); expectancy = net_r / len(trades) if trades else 0.0
        peak = self.config.initial_balance; max_dd_cash = 0.0
        for equity in result.equity_curve: peak = max(peak, equity); max_dd_cash = max(max_dd_cash, peak - equity)
        return {"final_balance": result.balance, "trade_count": len(trades), "win_rate": win_rate, "profit_factor": pf, "net_r": net_r, "expectancy": expectancy, "max_drawdown": max_dd_cash, "max_drawdown_pct": 100.0 * max_dd_cash / self.config.initial_balance if self.config.initial_balance else 0.0, "max_drawdown_r": max_dd_cash / max(self.config.initial_balance * self.config.risk_percent / 100.0, 1e-9), "equity_curve": result.equity_curve, "trades": [t.to_dict() for t in trades]}

    def evaluate_spec(self, data: pd.DataFrame, spec: StrategySpec) -> Dict[str, Any]:
        signals, sl_distance = self.signal_engine.build(data, spec); metrics = self.run_candidate(data, signals, sl_distance, rr=float(spec.risk["rr"]))
        metrics["strategy_name"] = spec.name; metrics["direction"] = spec.direction; metrics["strategy"] = spec.to_dict(); return metrics

    def run_research(self, data: pd.DataFrame, stop_event: Optional[Event] = None, progress_callback: Optional[Callable[[int, int], None]] = None, log_callback: Optional[Callable[[str], None]] = None, walk_forward_progress_callback: Optional[Callable[[int, int, int, int], None]] = None) -> List[Dict[str, Any]]:
        if data is None or len(data) < 100: raise ValueError("Insufficient historical data. Load at least 100 bars before research.")
        stop_event = stop_event or Event(); split = chronological_split(data, self.config.train_ratio); train_data, test_data = split.train, split.test; candidates = self.generate_candidates(); total = len(candidates); results: List[Dict[str, Any]] = []
        if log_callback: log_callback(f"Started. Candidates: {total}"); log_callback(f"TRAIN/TEST split: {len(train_data)}/{len(test_data)} bars ({self.config.train_ratio:.0%}/{1-self.config.train_ratio:.0%})")
        for index, candidate in enumerate(candidates, start=1):
            if stop_event.is_set():
                if log_callback: log_callback(f"STOP detected at candidate {index - 1}/{total}")
                break
            try:
                train = self.evaluate_spec(train_data, candidate)
                if train["trade_count"] < self.config.min_train_trades:
                    if log_callback: log_callback(f"Candidate {index}/{total}: rejected TRAIN trades={train['trade_count']} < {self.config.min_train_trades}")
                else:
                    test = self.evaluate_spec(test_data, candidate)
                    if test["trade_count"] < self.config.min_oos_trades:
                        if log_callback: log_callback(f"Candidate {index}/{total}: rejected OOS trades={test['trade_count']} < {self.config.min_oos_trades}")
                    else:
                        train_net, test_net = float(train["net_r"]), float(test["net_r"]); train_dd, test_dd = max(float(train["max_drawdown_r"]), 1e-9), max(float(test["max_drawdown_r"]), 1e-9)
                        validation = {"candidate": candidate, "train": train, "test": test, "oos_to_train_ratio": test_net / train_net if train_net > 0 else 0.0, "dd_ratio": test_dd / train_dd}; validation["validation_score"] = validation_score(validation); validation["candidate_index"] = index; results.append(validation)
                        if log_callback: log_callback(f"Candidate {index}/{total}: TRAIN PF={train['profit_factor']:.2f} OOS PF={test['profit_factor']:.2f} OOS NetR={test_net:.2f} Validation={validation['validation_score']:.2f}")
            except Exception as exc:
                if log_callback: log_callback(f"Candidate {index}/{total} failed: {exc}")
            if progress_callback: progress_callback(index, total)
        self.last_oos = sorted(results, key=lambda x: x["validation_score"], reverse=True); self.last_ranked = self.last_oos[: self.config.top_n_oos]
        if log_callback: log_callback(f"TRAIN/TEST validation finished. Accepted OOS strategies: {len(self.last_oos)}")
        if self.config.walk_forward_enabled and self.last_ranked and not stop_event.is_set():
            wf_candidates = [item["candidate"] for item in self.last_ranked]
            if log_callback: log_callback(f"[WALK-FORWARD] Started for TOP {len(wf_candidates)} strategies")
            def evaluate(spec_data: pd.DataFrame, candidate: StrategySpec) -> Dict[str, Any]:
                if stop_event.is_set(): return {"trade_count": 0, "net_r": 0.0, "profit_factor": 0.0, "max_drawdown_r": 0.0}
                return self.evaluate_spec(spec_data, candidate)
            self.last_walk_forward = evaluate_walk_forward(data, wf_candidates, evaluate, train_bars=self.config.walk_forward_train_bars, test_bars=self.config.walk_forward_test_bars, step_bars=self.config.walk_forward_step_bars, min_test_trades=self.config.walk_forward_min_test_trades, stop_event=stop_event, progress_callback=walk_forward_progress_callback, log_callback=log_callback)
            for item in self.last_walk_forward: item["walk_forward_score"] = walk_forward_score(item)
            self.last_walk_forward.sort(key=lambda x: x["walk_forward_score"], reverse=True); self.last_ranked = self.last_walk_forward[: self.config.top_n_walk_forward]
            if log_callback:
                log_callback(f"[WALK-FORWARD] Finished. Validated strategies: {len(self.last_walk_forward)}")
                for rank, item in enumerate(self.last_ranked[:5], 1): log_callback(f"[WF TOP {rank}] {item['candidate'].name} | Score={item['walk_forward_score']:.2f} | PositiveWindows={item['positive_windows']}/{item['window_count']} | OOS NetR={item['oos_net_r_sum']:.2f} | AvgPF={item['oos_pf_mean']:.2f}")
            if stop_event.is_set() and log_callback: log_callback("[WALK-FORWARD] Stopped by user.")
        self.last_results = results
        if self.config.export_results and not stop_event.is_set() and self.last_ranked:
            try:
                self.last_exports = export_results(self.last_ranked, Path(self.config.results_dir))
                if log_callback: log_callback(f"[EXPORT] Results saved to {self.config.results_dir}/")
            except Exception as exc:
                if log_callback: log_callback(f"[EXPORT] Failed: {exc}")
        if progress_callback: progress_callback(total, total)
        return self.last_ranked
