"""Unified validation result and conservative acceptance policy."""
from dataclasses import dataclass, asdict
from typing import Any, Dict


@dataclass
class ValidationReport:
    strategy_name: str = ""
    train_pass: bool = False
    oos_pass: bool = False
    walk_forward_pass_rate: float = 0.0
    sensitivity_pass_rate: float = 0.0
    monte_carlo_p05_net_r: float = 0.0
    max_drawdown_r: float = 0.0
    robustness_score: float = 0.0
    accepted: bool = False
    rejection_reasons: list[str] | None = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def evaluate_acceptance(report: ValidationReport) -> ValidationReport:
    reasons = []
    if not report.train_pass:
        reasons.append("TRAIN_FAILED")
    if not report.oos_pass:
        reasons.append("OOS_FAILED")
    if report.walk_forward_pass_rate < 0.60:
        reasons.append("WALK_FORWARD_WEAK")
    if report.sensitivity_pass_rate < 0.60:
        reasons.append("PARAMETER_SENSITIVITY_WEAK")
    if report.monte_carlo_p05_net_r < -5.0:
        reasons.append("MONTE_CARLO_TAIL_RISK")
    if report.max_drawdown_r > 10.0:
        reasons.append("DRAWDOWN_TOO_HIGH")
    report.rejection_reasons = reasons
    report.accepted = len(reasons) == 0
    return report
