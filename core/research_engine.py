"""Top-level orchestration for the modular research pipeline.

The engine coordinates data, strategy generation, backtesting and ranking;
individual modules remain independently testable.
"""
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import pandas as pd

from .backtester import BacktestConfig, Backtester
from .ranking import StrategyRanker
from .strategy_generator import StrategyGenerator


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
        self.backtester = Backtester(
            BacktestConfig(
                initial_balance=self.config.initial_balance,
                risk_percent=self.config.risk_percent,
            )
        )
        self.ranker = StrategyRanker()

    def generate_candidates(self) -> List[Any]:
        return self.generator.generate()

    def rank_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return self.ranker.rank(results)

    def run_candidate(
        self,
        data: pd.DataFrame,
        signals: pd.Series,
        sl_distance: pd.Series,
        rr: Optional[float] = None,
    ) -> Dict[str, Any]:
        result = self.backtester.run(
            data=data,
            signals=signals,
            sl_distance=sl_distance,
            rr=self.config.default_rr if rr is None else rr,
        )
        trades = result.trades
        wins = sum(1 for t in trades if t.pnl > 0)
        losses = sum(1 for t in trades if t.pnl < 0)
        gross_profit = sum(t.pnl for t in trades if t.pnl > 0)
        gross_loss = abs(sum(t.pnl for t in trades if t.pnl < 0))
        pf = gross_profit / gross_loss if gross_loss > 0 else 0.0
        win_rate = 100.0 * wins / len(trades) if trades else 0.0
        net_r = sum(t.r_multiple for t in trades)
        expectancy = net_r / len(trades) if trades else 0.0
        return {
            "final_balance": result.balance,
            "trade_count": len(trades),
            "win_rate": win_rate,
            "profit_factor": pf,
            "net_r": net_r,
            "expectancy": expectancy,
            "equity_curve": result.equity_curve,
            "trades": [t.to_dict() for t in trades],
        }
