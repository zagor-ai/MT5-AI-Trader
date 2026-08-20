"""Strategy candidate generation for XAU Strategy Researcher v2.2."""
from dataclasses import dataclass, field
from itertools import product
from typing import Any, Dict, Iterable, List, Optional


@dataclass(frozen=True)
class StrategySpec:
    """A serializable description of one research candidate."""
    name: str
    direction: str
    indicators: Dict[str, Any] = field(default_factory=dict)
    entry_rules: List[Dict[str, Any]] = field(default_factory=list)
    exit_rules: List[Dict[str, Any]] = field(default_factory=list)
    risk: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "direction": self.direction, "indicators": dict(self.indicators), "entry_rules": list(self.entry_rules), "exit_rules": list(self.exit_rules), "risk": dict(self.risk)}


class StrategyGenerator:
    """Generate bounded, reproducible candidate specifications."""

    def __init__(self, max_candidates: int = 300):
        self.max_candidates = max(1, int(max_candidates))

    def generate(self, directions: Iterable[str] = ("BUY", "SELL"), indicator_options: Optional[Dict[str, Iterable[Any]]] = None, risk_options: Optional[Dict[str, Iterable[Any]]] = None) -> List[StrategySpec]:
        indicator_options = indicator_options or {
            "ema_fast": (20, 50), "ema_slow": (100, 200), "rsi_period": (14,),
            "rsi_buy": (50, 55), "rsi_sell": (45, 50), "atr_period": (14,),
        }
        # Keep candidate generation consistent with the ResearchConfig RR ceiling.
        risk_options = risk_options or {"atr_sl": (1.0, 1.5, 2.0), "rr": (1.5, 2.0, 2.2)}

        indicator_keys = list(indicator_options)
        indicator_values = [tuple(indicator_options[k]) for k in indicator_keys]
        risk_keys = list(risk_options)
        risk_values = [tuple(risk_options[k]) for k in risk_keys]

        candidates: List[StrategySpec] = []
        seen = set()
        for direction, ivals, rvals in product(tuple(directions), product(*indicator_values), product(*risk_values)):
            indicators = dict(zip(indicator_keys, ivals))
            risk = dict(zip(risk_keys, rvals))
            entry = self._default_entry_rules(direction, indicators)
            exit_rules = [{"type": "ATR_SL", "multiplier": risk["atr_sl"]}, {"type": "RR_TP", "rr": risk["rr"]}]
            key = (direction, tuple(sorted(indicators.items())), tuple(sorted(risk.items())), tuple(tuple(sorted(r.items())) for r in entry), tuple(tuple(sorted(r.items())) for r in exit_rules))
            if key in seen:
                continue
            seen.add(key)
            name = f"{direction}_EMA_RSI_ATR_{len(candidates) + 1:04d}"
            candidates.append(StrategySpec(name, direction, indicators, entry, exit_rules, risk))
            if len(candidates) >= self.max_candidates:
                return candidates
        return candidates

    @staticmethod
    def _default_entry_rules(direction: str, p: Dict[str, Any]) -> List[Dict[str, Any]]:
        if direction == "BUY":
            return [
                {"type": "EMA_TREND", "fast": p["ema_fast"], "slow": p["ema_slow"], "relation": ">"},
                {"type": "RSI_RANGE", "period": p["rsi_period"], "min": p["rsi_buy"], "max": 70},
            ]
        return [
            {"type": "EMA_TREND", "fast": p["ema_fast"], "slow": p["ema_slow"], "relation": "<"},
            {"type": "RSI_RANGE", "period": p["rsi_period"], "min": 30, "max": p["rsi_sell"]},
        ]
