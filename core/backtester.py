"""Pure pandas/numpy backtest engine foundation.

No MT5 calls and no GUI dependencies. Orders are simulated only and entries
are evaluated on the next bar open to avoid look-ahead bias.
"""
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

import numpy as np
import pandas as pd

from .strategy_generator import StrategySpec


@dataclass
class BacktestConfig:
    initial_balance: float = 10_000.0
    risk_percent: float = 1.0
    commission_per_trade: float = 0.0
    slippage_points: float = 0.0
    point: float = 0.01
    max_bars: Optional[int] = None


@dataclass
class Trade:
    entry_time: Any
    exit_time: Any
    direction: str
    entry_price: float
    exit_price: float
    stop_loss: float
    take_profit: float
    risk_price: float
    r_multiple: float
    pnl: float
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class BacktestResult:
    balance: float
    trades: List[Trade] = field(default_factory=list)
    equity_curve: List[float] = field(default_factory=list)

    def trades_frame(self) -> pd.DataFrame:
        return pd.DataFrame([t.to_dict() for t in self.trades])


class Backtester:
    """Deterministic OHLC backtester with next-open execution."""

    def __init__(self, config: Optional[BacktestConfig] = None):
        self.config = config or BacktestConfig()

    def run(
        self,
        data: pd.DataFrame,
        signals: pd.Series,
        sl_distance: pd.Series,
        rr: float = 2.0,
    ) -> BacktestResult:
        required = {"open", "high", "low", "close"}
        missing = required.difference(c.lower() for c in data.columns)
        if missing:
            raise ValueError(f"Missing OHLC columns: {sorted(missing)}")
        if len(data) < 2:
            return BacktestResult(self.config.initial_balance)

        df = data.copy()
        df.columns = [str(c).lower() for c in df.columns]
        sig = pd.Series(signals, index=df.index).fillna(0).astype(int)
        sls = pd.Series(sl_distance, index=df.index).astype(float)
        if self.config.max_bars:
            df = df.iloc[-self.config.max_bars :]
            sig = sig.reindex(df.index).fillna(0)
            sls = sls.reindex(df.index)

        balance = float(self.config.initial_balance)
        trades: List[Trade] = []
        equity = [balance]

        i = 0
        while i < len(df) - 1:
            signal = int(sig.iloc[i])
            if signal == 0 or not np.isfinite(sls.iloc[i]) or sls.iloc[i] <= 0:
                equity.append(balance)
                i += 1
                continue

            entry_i = i + 1
            entry = float(df["open"].iloc[entry_i])
            distance = float(sls.iloc[i])
            direction = "BUY" if signal > 0 else "SELL"
            sl = entry - distance if direction == "BUY" else entry + distance
            tp = entry + distance * rr if direction == "BUY" else entry - distance * rr

            risk_cash = balance * (self.config.risk_percent / 100.0)
            risk_unit = max(distance, np.finfo(float).eps)
            units = risk_cash / risk_unit
            exit_i = entry_i
            exit_price = float(df["close"].iloc[-1])
            reason = "END_OF_DATA"

            for j in range(entry_i, len(df)):
                high = float(df["high"].iloc[j])
                low = float(df["low"].iloc[j])
                if direction == "BUY":
                    if low <= sl:
                        exit_price, exit_i, reason = sl, j, "SL"
                        break
                    if high >= tp:
                        exit_price, exit_i, reason = tp, j, "TP"
                        break
                else:
                    if high >= sl:
                        exit_price, exit_i, reason = sl, j, "SL"
                        break
                    if low <= tp:
                        exit_price, exit_i, reason = tp, j, "TP"
                        break

            move = (exit_price - entry) if direction == "BUY" else (entry - exit_price)
            r_multiple = move / distance
            pnl = units * move - self.config.commission_per_trade
            balance += pnl
            trades.append(
                Trade(
                    entry_time=df.index[entry_i],
                    exit_time=df.index[exit_i],
                    direction=direction,
                    entry_price=entry,
                    exit_price=exit_price,
                    stop_loss=sl,
                    take_profit=tp,
                    risk_price=distance,
                    r_multiple=float(r_multiple),
                    pnl=float(pnl),
                    reason=reason,
                )
            )
            equity.append(balance)
            i = exit_i + 1

        return BacktestResult(balance=balance, trades=trades, equity_curve=equity)
