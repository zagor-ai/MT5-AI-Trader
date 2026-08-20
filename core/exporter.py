"""Export research results without any trading side effects."""
from __future__ import annotations
import csv
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List


def _safe(value: Any) -> Any:
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if isinstance(value, dict):
        return {str(k): _safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(v) for v in value]
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    return value if isinstance(value, (str, int, float, bool)) or value is None else str(value)


def _final_metrics(item: Dict[str, Any]) -> Dict[str, float]:
    """Expose every final ranking component without changing the ranking algorithm."""
    return {
        "walk_forward_score": float(item.get("walk_forward_score", 0.0)),
        "monte_carlo_robustness": float(item.get("monte_carlo_robustness", 0.0)),
        "sensitivity_robustness": float(item.get("sensitivity_robustness", 0.0)),
        "regime_robustness": float(item.get("regime_robustness", 0.0)),
    }


def _ranking_basis(item: Dict[str, Any]) -> str:
    """Document the exact lexicographic order used by ResearchEngine."""
    return "regime_robustness > sensitivity_robustness > monte_carlo_robustness > walk_forward_score"


def export_results(results: Iterable[Dict[str, Any]], output_dir: str | Path = "results") -> Dict[str, str]:
    """Write ranked results, trades and strategy rules to separate files."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    items = [_safe(x) for x in results]

    json_path = out / "ranked_strategies.json"
    json_path.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")

    csv_path = out / "ranked_strategies.csv"
    columns = [
        "rank", "strategy_name", "final_ranking_basis", "score", "walk_forward_score",
        "monte_carlo_robustness", "sensitivity_robustness", "regime_robustness",
        "validation_score", "oos_pf_mean", "oos_net_r_sum", "positive_windows", "window_count"
    ]
    with csv_path.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns)
        writer.writeheader()
        for rank, item in enumerate(items, 1):
            candidate = item.get("candidate", {})
            name = candidate.get("name", item.get("strategy_name", "")) if isinstance(candidate, dict) else str(candidate)
            metrics = _final_metrics(item)
            writer.writerow({
                "rank": rank,
                "strategy_name": name,
                "final_ranking_basis": _ranking_basis(item),
                "score": item.get("ranking_score", metrics["walk_forward_score"]),
                "walk_forward_score": metrics["walk_forward_score"],
                "monte_carlo_robustness": metrics["monte_carlo_robustness"],
                "sensitivity_robustness": metrics["sensitivity_robustness"],
                "regime_robustness": metrics["regime_robustness"],
                "validation_score": item.get("validation_score", 0),
                "oos_pf_mean": item.get("oos_pf_mean", 0),
                "oos_net_r_sum": item.get("oos_net_r_sum", 0),
                "positive_windows": item.get("positive_windows", 0),
                "window_count": item.get("window_count", 0),
            })

    trades_path = out / "best_strategy_trades.csv"
    trades: List[Dict[str, Any]] = []
    if items:
        best = items[0]
        if isinstance(best.get("trades"), list):
            trades.extend(best["trades"])
        for window in best.get("windows", []):
            test = window.get("test", {})
            if isinstance(test.get("trades"), list):
                for trade in test["trades"]:
                    row = dict(trade)
                    row["window"] = window.get("window", {}).get("index")
                    trades.append(row)
    if trades:
        keys = sorted({k for row in trades for k in row.keys()})
        with trades_path.open("w", newline="", encoding="utf-8-sig") as fh:
            writer = csv.DictWriter(fh, fieldnames=keys)
            writer.writeheader()
            writer.writerows(trades)
    else:
        trades_path.write_text("No trades available for export.\n", encoding="utf-8")

    rules_path = out / "best_strategy_rules.json"
    rules = items[0].get("candidate", items[0].get("strategy", {})) if items else {}
    rules_path.write_text(json.dumps(_safe(rules), indent=2, ensure_ascii=False), encoding="utf-8")
    return {"json": str(json_path), "csv": str(csv_path), "trades": str(trades_path), "rules": str(rules_path)}
