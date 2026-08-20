"""Top-level orchestration for the modular XAU research pipeline."""
from dataclasses import dataclass
from threading import Event
from typing import Any, Callable, Dict, List, Optional

import pandas as pd

from .backtester import BacktestConfig, Backtester
from .ranking import StrategyRanker
from .signal_engine import SignalEngine
from .strategy_generator import StrategyGenerator, StrategySpec


@dataclass
class ResearchConfig:
    max_candidates: int = 300
    initial_balance: float = 10_000.0
    risk_percent: float = 1.0
    default_rr: float = 2.0


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
        candidates = self.generate_candidates()
        total = len(candidates)
        results: List[Dict[str, Any]] = []
        if log_callback:
            log_callback(f"Started. Candidates: {total}")
        for index, candidate in enumerate(candidates, start=1):
            if stop_event.is_set():
                if log_callback:
                    log_callback(f"STOP detected at candidate {index - 1}/{total}")
                break
            try:
                result = self.evaluate_spec(data, candidate)
                result["candidate_index"] = index
                results.append(result)
                if log_callback:
                    log_callback(
                        f"Candidate {index}/{total}: "
                        f"trades={result['trade_count']} "
                        f"PF={result['profit_factor']:.2f} "
                        f"WinRate={result['win_rate']:.1f}% "
                        f"NetR={result['net_r']:.2f} "
                        f"DD={result['max_drawdown_pct']:.2f}%"
                    )
            except Exception as exc:
                if log_callback:
                    log_callback(f"Candidate {index}/{total} failed: {exc}")
            if progress_callback:
                progress_callback(index, total)
        self.last_results = results
        self.last_ranked = self.rank_results(results) if results else []
        if log_callback:
            log_callback(f"Finished. Processed results: {len(results)}")
            if self.last_ranked:
                for rank, item in enumerate(self.last_ranked[:5], start=1):
                    log_callback(
                        f"TOP {rank}: {item.get('strategy_name', 'N/A')} | "
                        f"Score={item.get('ranking_score', 0):.2f} | "
                        f"PF={item.get('profit_factor', 0):.2f} | "
                        f"NetR={item.get('net_r', 0):.2f} | "
                        f"DD={item.get('max_drawdown_pct', 0):.2f}%"
                    )
        return self.last_ranked
