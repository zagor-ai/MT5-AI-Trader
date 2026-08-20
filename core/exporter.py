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


def export_results(results: Iterable[Dict[str, Any]], output_dir: str | Path = "results") -> Dict[str, str]:
    """Write ranked results, trades and strategy rules to separate files."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    items = [_safe(x) for x in results]

    json_path = out / "ranked_strategies.json"
    json_path.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")

    csv_path = out / "ranked_strategies.csv"
    columns = ["rank", "strategy_name", "score", "walk_forward_score", "validation_score", "oos_pf_mean", "oos_net_r_sum", "positive_windows", "window_count"]
    with csv_path.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns)
        writer.writeheader()
        for rank, item in enumerate(items, 1):
            candidate = item.get("candidate", {})
            name = candidate.get("name", item.get("strategy_name", "")) if isinstance(candidate, dict) else str(candidate)
            writer.writerow({
                "rank": rank,
                "strategy_name": name,
                "score": item.get("ranking_score", item.get("walk_forward_score", item.get("validation_score", 0))),
                "walk_forward_score": item.get("walk_forward_score", 0),
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
