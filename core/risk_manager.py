"""Risk sizing and stop/target helpers for research-only backtests."""
from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass(frozen=True)
class RiskConfig:
    risk_percent: float = 1.0
    min_risk_percent: float = 0.1
    max_risk_percent: float = 5.0
    min_rr: float = 1.0
    max_rr: float = 5.0


class RiskManager:
    def __init__(self, config: Optional[RiskConfig] = None):
        self.config = config or RiskConfig()

    def normalize_risk_percent(self, value: float) -> float:
        return min(self.config.max_risk_percent, max(self.config.min_risk_percent, float(value)))

    def normalize_rr(self, value: float) -> float:
        return min(self.config.max_rr, max(self.config.min_rr, float(value)))

    def position_units(self, balance: float, entry: float, stop: float, risk_percent: Optional[float] = None) -> float:
        distance = abs(float(entry) - float(stop))
        if balance <= 0 or distance <= 0:
            return 0.0
        rp = self.normalize_risk_percent(self.config.risk_percent if risk_percent is None else risk_percent)
        return (float(balance) * rp / 100.0) / distance

    def target_from_rr(self, entry: float, stop: float, rr: float) -> float:
        rr = self.normalize_rr(rr)
        distance = abs(float(entry) - float(stop))
        return float(entry) + distance * rr if stop < entry else float(entry) - distance * rr

    def stop_target(self, direction: str, entry: float, atr: float, atr_multiplier: float, rr: float) -> Tuple[float, float]:
        distance = abs(float(atr)) * float(atr_multiplier)
        if distance <= 0:
            raise ValueError("ATR distance must be positive")
        direction = direction.upper()
        if direction == "BUY":
            stop = float(entry) - distance
            target = float(entry) + distance * self.normalize_rr(rr)
        elif direction == "SELL":
            stop = float(entry) + distance
            target = float(entry) - distance * self.normalize_rr(rr)
        else:
            raise ValueError("direction must be BUY or SELL")
        return stop, target
