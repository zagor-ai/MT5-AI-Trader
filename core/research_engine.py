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
from validation.monte_carlo import MonteCarloConfig, MonteCarloSimulator
from validation.parameter_sensitivity import ParameterSensitivity, SensitivityConfig
from validation.market_regime import detect_regimes, analyze_regimes, regime_robustness_score

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
    monte_carlo_enabled: bool = True
    monte_carlo_simulations: int = 2000
    monte_carlo_seed: int = 42
    sensitivity_enabled: bool = True
    sensitivity_top_n: int = 10
    sensitivity_min_pf: float = 1.0
    sensitivity_min_expectancy: float = 0.0
    sensitivity_min_pass_rate: float = 0.60
    regime_enabled: bool = True
    regime_min_bars: int = 100
    regime_min_trade_count: int = 10
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
        self.last_ranked = self.ranker.rank(results); return self.last_ranked

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

    def _monte_carlo(self, item):
        test_trades = []
        for window in item.get("windows", []): test_trades.extend(window.get("test", {}).get("trades", []))
        if not test_trades: test_trades = item.get("test", {}).get("trades", [])
        if not self.config.monte_carlo_enabled: return None
        try:
            cfg = MonteCarloConfig(simulations=self.config.monte_carlo_simulations, seed=self.config.monte_carlo_seed, risk_fraction=self.config.risk_percent / 100.0)
            return MonteCarloSimulator(cfg).simulate_trades(test_trades)
        except ValueError: return None

    @staticmethod
    def _nearby_values(value: Any, lower: float, upper: float, step: float) -> List[float]:
        try: base = float(value)
        except (TypeError, ValueError): return []
        values = []
        for i in range(-2, 3):
            v = base + i * step
            if lower <= v <= upper: values.append(int(v) if float(v).is_integer() else round(v, 4))
        return values

    def _sensitivity_spec(self, spec: StrategySpec, parameter: str, value: Any) -> StrategySpec:
        if isinstance(value, dict): value = value.get(parameter)
        indicators = dict(spec.indicators); risk = dict(spec.risk); entry = [dict(x) for x in spec.entry_rules]; exit_rules = [dict(x) for x in spec.exit_rules]
        if parameter in indicators: indicators[parameter] = value
        elif parameter in risk: risk[parameter] = value
        for rule in entry:
            if rule.get("type") == "EMA_TREND" and parameter == "ema_fast": rule["fast"] = value
            if rule.get("type") == "EMA_TREND" and parameter == "ema_slow": rule["slow"] = value
            if rule.get("type") == "RSI_RANGE" and parameter == "rsi_period": rule["period"] = value
            if rule.get("type") == "RSI_RANGE" and spec.direction == "BUY" and parameter == "rsi_buy": rule["min"] = value
            if rule.get("type") == "RSI_RANGE" and spec.direction == "SELL" and parameter == "rsi_sell": rule["max"] = value
        for rule in exit_rules:
            if parameter == "atr_sl" and rule.get("type") == "ATR_SL": rule["multiplier"] = value
            if parameter == "rr" and rule.get("type") == "RR_TP": rule["rr"] = value
        return StrategySpec(spec.name, spec.direction, indicators, entry, exit_rules, risk)

    def _run_sensitivity(self, item, test_data, stop_event, log_callback=None):
        if not self.config.sensitivity_enabled: return None
        base = item["candidate"]; params = {**base.indicators, **base.risk}; parameter_grid = {}
        for p, v in params.items():
            if p in ("ema_fast", "ema_slow", "rsi_period"): parameter_grid[p] = self._nearby_values(v, 2, 500, 5 if p != "rsi_period" else 1)
            elif p in ("rsi_buy", "rsi_sell"): parameter_grid[p] = self._nearby_values(v, 20, 80, 2)
            elif p == "atr_sl": parameter_grid[p] = self._nearby_values(v, 0.5, 4.0, 0.25)
            elif p == "rr": parameter_grid[p] = self._nearby_values(v, 0.75, 4.0, 0.25)
        sensitivity = ParameterSensitivity(SensitivityConfig(minimum_pf=self.config.sensitivity_min_pf, minimum_expectancy=self.config.sensitivity_min_expectancy, minimum_pass_rate=self.config.sensitivity_min_pass_rate))
        output = {}
        for parameter, values in parameter_grid.items():
            if stop_event.is_set(): break
            def evaluator(params_variant, p=parameter):
                candidate = self._sensitivity_spec(base, p, params_variant)
                return self.evaluate_spec(test_data, candidate)
            result = sensitivity.run(params, {parameter: values}, evaluator); output[parameter] = result
            if log_callback: log_callback(f"[SENSITIVITY] {base.name} | {parameter} | PassRate={result['pass_rate']:.1%} | Robust={'YES' if result['robust'] else 'NO'}")
        return output

    def _run_regime_analysis(self, item, data, stop_event, log_callback=None):
        if not self.config.regime_enabled or stop_event.is_set(): return None
        try:
            regimes = detect_regimes(data)
            candidate = item["candidate"]
            def evaluator(subset):
                if stop_event.is_set(): return {"trade_count": 0, "net_r": 0.0, "profit_factor": 0.0, "max_drawdown_r": 0.0}
                return self.evaluate_spec(subset, candidate)
            results = analyze_regimes(data, regimes, evaluator)
            valid = [r for r in results if int(r.get("trade_count", 0)) >= self.config.regime_min_trade_count]
            score = regime_robustness_score(valid)
            if log_callback: log_callback(f"[REGIME] {candidate.name} | Score={score:.2f} | Regimes={len(valid)}")
            return {"results": results, "robustness_score": score}
        except Exception as exc:
            if log_callback: log_callback(f"[REGIME] Failed for {item['candidate'].name}: {exc}")
            return {"results": [], "robustness_score": 0.0, "error": str(exc)}

    def run_research(self, data, stop_event=None, progress_callback=None, log_callback=None, walk_forward_progress_callback=None):
        if data is None or len(data) < 100: raise ValueError("Insufficient historical data. Load at least 100 bars before research.")
        stop_event = stop_event or Event(); split = chronological_split(data, self.config.train_ratio); train_data, test_data = split.train, split.test; candidates = self.generate_candidates(); total = len(candidates); results = []
        if log_callback: log_callback(f"Started. Candidates: {total}"); log_callback(f"TRAIN/TEST split: {len(train_data)}/{len(test_data)} bars ({self.config.train_ratio:.0%}/{1-self.config.train_ratio:.0%})")
        for index, candidate in enumerate(candidates, 1):
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
                        train_net, test_net = float(train["net_r"]), float(test["net_r"]); train_dd, test_dd = max(float(train["max_drawdown_r"]), 1e-9), max(float(test["max_drawdown_r"]), 1e-9); validation = {"candidate": candidate, "train": train, "test": test, "oos_to_train_ratio": test_net / train_net if train_net > 0 else 0.0, "dd_ratio": test_dd / train_dd}; validation["validation_score"] = validation_score(validation); validation["candidate_index"] = index; results.append(validation)
                        if log_callback: log_callback(f"Candidate {index}/{total}: TRAIN PF={train['profit_factor']:.2f} OOS PF={test['profit_factor']:.2f} OOS NetR={test_net:.2f} Validation={validation['validation_score']:.2f}")
            except Exception as exc:
                if log_callback: log_callback(f"Candidate {index}/{total} failed: {exc}")
            if progress_callback: progress_callback(index, total)
        self.last_oos = sorted(results, key=lambda x: x["validation_score"], reverse=True); self.last_ranked = self.last_oos[: self.config.top_n_oos]
        if log_callback: log_callback(f"TRAIN/TEST validation finished. Accepted OOS strategies: {len(self.last_oos)}")
        if self.config.walk_forward_enabled and self.last_ranked and not stop_event.is_set():
            wf_candidates = [item["candidate"] for item in self.last_ranked]
            if log_callback: log_callback(f"[WALK-FORWARD] Started for TOP {len(wf_candidates)} strategies")
            def evaluate(spec_data, candidate): return {"trade_count": 0, "net_r": 0.0, "profit_factor": 0.0, "max_drawdown_r": 0.0} if stop_event.is_set() else self.evaluate_spec(spec_data, candidate)
            self.last_walk_forward = evaluate_walk_forward(data, wf_candidates, evaluate, train_bars=self.config.walk_forward_train_bars, test_bars=self.config.walk_forward_test_bars, step_bars=self.config.walk_forward_step_bars, min_test_trades=self.config.walk_forward_min_test_trades, stop_event=stop_event, progress_callback=walk_forward_progress_callback, log_callback=log_callback)
            for item in self.last_walk_forward: item["walk_forward_score"] = walk_forward_score(item)
            self.last_walk_forward.sort(key=lambda x: x["walk_forward_score"], reverse=True); self.last_ranked = self.last_walk_forward[: self.config.top_n_walk_forward]
            if log_callback: log_callback(f"[WALK-FORWARD] Finished. Validated strategies: {len(self.last_walk_forward)}")
        if self.config.monte_carlo_enabled and self.last_ranked and not stop_event.is_set():
            if log_callback: log_callback(f"[MONTE CARLO] Started for TOP {len(self.last_ranked)} strategies | Simulations={self.config.monte_carlo_simulations}")
            for rank, item in enumerate(self.last_ranked, 1):
                if stop_event.is_set(): break
                mc = self._monte_carlo(item); item["monte_carlo"] = mc
                if mc:
                    item["monte_carlo_robustness"] = max(0.0, min(100.0, 100.0 * (0.5 * mc["probability_positive"] + 0.5 * (1.0 - min(1.0, mc["probability_ruin"])))));
                    if log_callback: log_callback(f"[MC {rank}] {item['candidate'].name} | P(Positive)={mc['probability_positive']:.1%} | P(Ruin)={mc['probability_ruin']:.1%} | P05 NetR={mc['p05_net_r']:.2f} | P95 DD={mc['p95_max_drawdown_r']:.2f}")
                else: item["monte_carlo_robustness"] = 0.0
            self.last_ranked.sort(key=lambda x: (x.get("monte_carlo_robustness", 0.0), x.get("walk_forward_score", 0.0)), reverse=True)
            if log_callback: log_callback("[MONTE CARLO] Finished. Ranking updated.")
        if self.config.sensitivity_enabled and self.last_ranked and not stop_event.is_set():
            if log_callback: log_callback(f"[SENSITIVITY] Started for TOP {min(self.config.sensitivity_top_n, len(self.last_ranked))} strategies")
            for item in self.last_ranked[: self.config.sensitivity_top_n]:
                if stop_event.is_set(): break
                item["parameter_sensitivity"] = self._run_sensitivity(item, test_data, stop_event, log_callback)
                values = [float(x.get("pass_rate", 0.0)) for x in item.get("parameter_sensitivity", {}).values()]
                item["sensitivity_robustness"] = 100.0 * sum(values) / len(values) if values else 0.0
            self.last_ranked.sort(key=lambda x: (x.get("sensitivity_robustness", 0.0), x.get("monte_carlo_robustness", 0.0), x.get("walk_forward_score", 0.0)), reverse=True)
            if log_callback: log_callback("[SENSITIVITY] Finished.")
        if self.config.regime_enabled and self.last_ranked and not stop_event.is_set():
            if log_callback: log_callback(f"[REGIME] Started for TOP {len(self.last_ranked)} strategies")
            for item in self.last_ranked:
                if stop_event.is_set(): break
                item["market_regime"] = self._run_regime_analysis(item, data, stop_event, log_callback)
                item["regime_robustness"] = float(item["market_regime"].get("robustness_score", 0.0)) if item.get("market_regime") else 0.0
            self.last_ranked.sort(key=lambda x: (x.get("regime_robustness", 0.0), x.get("sensitivity_robustness", 0.0), x.get("monte_carlo_robustness", 0.0), x.get("walk_forward_score", 0.0)), reverse=True)
            if log_callback: log_callback("[REGIME] Finished. Final robustness ranking updated.")
        self.last_results = results
        if self.config.export_results and not stop_event.is_set() and self.last_ranked:
            try:
                self.last_exports = export_results(self.last_ranked, Path(self.config.results_dir))
                if log_callback: log_callback(f"[EXPORT] Results saved to {self.config.results_dir}/")
            except Exception as exc:
                if log_callback: log_callback(f"[EXPORT] Failed: {exc}")
        if progress_callback: progress_callback(total, total)
        return self.last_ranked
