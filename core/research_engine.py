"""Top-level orchestration for the modular XAU research pipeline."""
from dataclasses import dataclass
from threading import Event
from typing import Any, Callable, Dict, List, Optional

import pandas as pd

from .backtester import BacktestConfig, Backtester
from .ranking import StrategyRanker
from .signal_engine import SignalEngine
from .strategy_generator import StrategyGenerator, StrategySpec
from .validation.train_test import chronological_split
from .validation.validator import validation_score


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


class ResearchEngine:
    def __init__(self, config: Optional[ResearchConfig] = None):
        self.config = config or ResearchConfig()
        self.generator = StrategyGenerator(self.config.max_candidates)
        self.signal_engine = SignalEngine()
        self.backtester = Backtester(BacktestConfig(
            initial_balance=self.config.initial_balance,
            risk_percent=self.config.risk_percent,
        ))
        self.ranker = StrategyRanker()
        self.last_results: List[Dict[str, Any]] = []
        self.last_ranked: List[Dict[str, Any]] = []
        self.last_oos: List[Dict[str, Any]] = []

    def generate_candidates(self) -> List[StrategySpec]:
        return self.generator.generate()

    def rank_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        ranked = self.ranker.rank(results)
        self.last_ranked = ranked
        return ranked

    def run_candidate(self, data: pd.DataFrame, signals: pd.Series, sl_distance: pd.Series, rr: Optional[float] = None) -> Dict[str, Any]:
        result = self.backtester.run(data, signals, sl_distance, self.config.default_rr if rr is None else rr)
        trades = result.trades
        wins = sum(1 for t in trades if t.pnl > 0)
        gross_profit = sum(t.pnl for t in trades if t.pnl > 0)
        gross_loss = abs(sum(t.pnl for t in trades if t.pnl < 0))
        pf = gross_profit / gross_loss if gross_loss > 0 else (float("inf") if gross_profit > 0 else 0.0)
        win_rate = 100.0 * wins / len(trades) if trades else 0.0
        net_r = sum(t.r_multiple for t in trades)
        expectancy = net_r / len(trades) if trades else 0.0
        peak = self.config.initial_balance
        max_dd_cash = 0.0
        for equity in result.equity_curve:
            peak = max(peak, equity)
            max_dd_cash = max(max_dd_cash, peak - equity)
        max_dd_pct = (100.0 * max_dd_cash / self.config.initial_balance) if self.config.initial_balance else 0.0
        return {
            "final_balance": result.balance,
            "trade_count": len(trades),
            "win_rate": win_rate,
            "profit_factor": pf,
            "net_r": net_r,
            "expectancy": expectancy,
            "max_drawdown": max_dd_cash,
            "max_drawdown_pct": max_dd_pct,
            "max_drawdown_r": max_dd_cash / max(self.config.initial_balance * self.config.risk_percent / 100.0, 1e-9),
            "equity_curve": result.equity_curve,
            "trades": [t.to_dict() for t in trades],
        }

    def evaluate_spec(self, data: pd.DataFrame, spec: StrategySpec) -> Dict[str, Any]:
        signals, sl_distance = self.signal_engine.build(data, spec)
        metrics = self.run_candidate(data, signals, sl_distance, rr=float(spec.risk["rr"]))
        metrics["strategy_name"] = spec.name
        metrics["direction"] = spec.direction
        metrics["strategy"] = spec.to_dict()
        return metrics

    def run_research(
        self,
        data: pd.DataFrame,
        stop_event: Optional[Event] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        log_callback: Optional[Callable[[str], None]] = None,
    ) -> List[Dict[str, Any]]:
        if data is None or len(data) < 100:
            raise ValueError("Insufficient historical data. Load at least 100 bars before research.")
        stop_event = stop_event or Event()
        split = chronological_split(data, self.config.train_ratio)
        train_data, test_data = split.train, split.test
        candidates = self.generate_candidates()
        total = len(candidates)
        results: List[Dict[str, Any]] = []
        if log_callback:
            log_callback(f"Started. Candidates: {total}")
            log_callback(f"TRAIN/TEST split: {len(train_data)}/{len(test_data)} bars ({self.config.train_ratio:.0%}/{1-self.config.train_ratio:.0%})")

        for index, candidate in enumerate(candidates, start=1):
            if stop_event.is_set():
                if log_callback:
                    log_callback(f"STOP detected at candidate {index - 1}/{total}")
                break
            try:
                train = self.evaluate_spec(train_data, candidate)
                if train["trade_count"] < self.config.min_train_trades:
                    if log_callback:
                        log_callback(f"Candidate {index}/{total}: rejected TRAIN trades={train['trade_count']} < {self.config.min_train_trades}")
                else:
                    test = self.evaluate_spec(test_data, candidate)
                    if test["trade_count"] < self.config.min_oos_trades:
                        if log_callback:
                            log_callback(f"Candidate {index}/{total}: rejected OOS trades={test['trade_count']} < {self.config.min_oos_trades}")
                    else:
                        train_net = float(train["net_r"])
                        test_net = float(test["net_r"])
                        train_dd = max(float(train["max_drawdown_r"]), 1e-9)
                        test_dd = max(float(test["max_drawdown_r"]), 1e-9)
                        validation = {
                            "candidate": candidate,
                            "train": train,
                            "test": test,
                            "oos_to_train_ratio": test_net / train_net if train_net > 0 else 0.0,
                            "dd_ratio": test_dd / train_dd,
                        }
                        validation["validation_score"] = validation_score(validation)
                        validation["candidate_index"] = index
                        results.append(validation)
                        if log_callback:
                            log_callback(
                                f"Candidate {index}/{total}: TRAIN PF={train['profit_factor']:.2f} "
                                f"OOS PF={test['profit_factor']:.2f} OOS NetR={test_net:.2f} "
                                f"Validation={validation['validation_score']:.2f}"
                            )
            except Exception as exc:
                if log_callback:
                    log_callback(f"Candidate {index}/{total} failed: {exc}")
            if progress_callback:
                progress_callback(index, total)

        self.last_oos = sorted(results, key=lambda x: x["validation_score"], reverse=True)
        self.last_results = self.last_oos
        self.last_ranked = self.last_oos[: self.config.top_n_oos]
        if log_callback:
            log_callback(f"TRAIN/TEST validation finished. Accepted OOS strategies: {len(self.last_oos)}")
            for rank, item in enumerate(self.last_ranked[:5], start=1):
                s = item["test"]
                log_callback(
                    f"[OOS TOP {rank}] {s['strategy_name']} | "
                    f"Score={item['validation_score']:.2f} | PF={s['profit_factor']:.2f} | "
                    f"NetR={s['net_r']:.2f} | WR={s['win_rate']:.1f}% | DD={s['max_drawdown_pct']:.2f}%"
                )
        return self.last_ranked
