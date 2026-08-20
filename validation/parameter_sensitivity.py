"""Parameter sensitivity analysis for detecting fragile optimizations.

A robust strategy should retain acceptable performance across a neighborhood of
parameter values rather than only at one optimized point.
"""
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Sequence


@dataclass(frozen=True)
class SensitivityConfig:
    minimum_pf: float = 1.0
    minimum_expectancy: float = 0.0
    minimum_pass_rate: float = 0.60


class ParameterSensitivity:
    def __init__(self, config: SensitivityConfig | None = None):
        self.config = config or SensitivityConfig()

    def run(
        self,
        base_params: Dict[str, Any],
        parameter_grid: Dict[str, Sequence[Any]],
        evaluator: Callable[[Dict[str, Any]], Dict[str, Any]],
    ) -> Dict[str, Any]:
        keys = list(parameter_grid)
        results: List[Dict[str, Any]] = []
        total = 1
        for key in keys:
            total *= max(1, len(parameter_grid[key]))

        def recurse(index: int, params: Dict[str, Any]) -> None:
            if index == len(keys):
                metrics = dict(evaluator(dict(params)))
                row = {"parameters": dict(params), **metrics}
                row["pass"] = bool(
                    float(metrics.get("profit_factor", 0.0)) >= self.config.minimum_pf
                    and float(metrics.get("expectancy", 0.0)) >= self.config.minimum_expectancy
                )
                results.append(row)
                return
            key = keys[index]
            for value in parameter_grid[key]:
                params[key] = value
                recurse(index + 1, params)
            params.pop(key, None)

        recurse(0, dict(base_params))
        passed = sum(bool(r["pass"]) for r in results)
        pass_rate = passed / len(results) if results else 0.0
        return {
            "base_parameters": dict(base_params),
            "total_tests": total,
            "evaluated": len(results),
            "passed": passed,
            "pass_rate": pass_rate,
            "robust": pass_rate >= self.config.minimum_pass_rate,
            "results": results,
        }
