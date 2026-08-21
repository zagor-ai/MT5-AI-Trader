"""Compact, deterministic research reports for project auditing and ChatGPT review."""
from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
import importlib.metadata
import json
from pathlib import Path
import platform
from typing import Any, Dict, Iterable, List, Optional


def _safe(value: Any) -> Any:
    if hasattr(value, "to_dict"):
        return _safe(value.to_dict())
    if is_dataclass(value):
        return _safe(asdict(value))
    if isinstance(value, dict):
        return {str(k): _safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(v) for v in value]
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _metric(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _runtime_info() -> Dict[str, Any]:
    """Collect lightweight runtime metadata without initializing or trading on MT5."""
    packages: Dict[str, str] = {}
    for name in ("numpy", "pandas", "MetaTrader5"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = "not-installed"
    info: Dict[str, Any] = {
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "packages": packages,
    }
    try:
        import MetaTrader5 as mt5
        terminal = mt5.terminal_info()
        account = mt5.account_info()
        if terminal is not None:
            info["mt5_terminal"] = {
                "name": getattr(terminal, "name", None),
                "build": getattr(terminal, "build", None),
                "company": getattr(terminal, "company", None),
                "path": getattr(terminal, "path", None),
            }
        if account is not None:
            info["mt5_account"] = {
                "login": getattr(account, "login", None),
                "server": getattr(account, "server", None),
                "currency": getattr(account, "currency", None),
            }
    except Exception as exc:
        info["mt5_runtime_note"] = f"metadata unavailable: {exc}"
    return _safe(info)


def _candidate_summary(candidate: Any) -> Dict[str, Any]:
    if hasattr(candidate, "to_dict"):
        candidate = candidate.to_dict()
    return _safe(candidate) if isinstance(candidate, dict) else {"name": str(candidate)}


def _compact_metrics(metrics: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(metrics, dict):
        return {}
    keep = ("trade_count", "win_rate", "profit_factor", "net_r", "expectancy", "max_drawdown", "max_drawdown_pct", "max_drawdown_r", "final_balance")
    return {k: _safe(metrics.get(k)) for k in keep if k in metrics}


def _compact_window(item: Dict[str, Any]) -> Dict[str, Any]:
    return {"window": _safe(item.get("window", {})), "train": _compact_metrics(item.get("train")), "test": _compact_metrics(item.get("test"))}


def _compact_sensitivity(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    output: Dict[str, Any] = {}
    for parameter, result in value.items():
        if not isinstance(result, dict):
            output[str(parameter)] = _safe(result)
            continue
        output[str(parameter)] = {
            "pass_rate": _safe(result.get("pass_rate")),
            "robust": _safe(result.get("robust")),
            "minimum_pf": _safe(result.get("minimum_pf")),
            "minimum_expectancy": _safe(result.get("minimum_expectancy")),
            "tested_values": _safe(result.get("tested_values", result.get("values", []))),
        }
    return output


def _compact_regime(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    regimes = []
    for row in value.get("results", []) or []:
        if isinstance(row, dict):
            regimes.append({k: _safe(row.get(k)) for k in ("regime", "trade_count", "net_r", "profit_factor", "max_drawdown_r", "win_rate") if k in row})
    return {"robustness_score": _metric(value.get("robustness_score")), "results": regimes, "error": value.get("error")}


def _compact_mc(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    keys = ("simulations", "probability_positive", "probability_ruin", "p05_net_r", "p50_net_r", "p95_net_r", "p05_max_drawdown_r", "p50_max_drawdown_r", "p95_max_drawdown_r", "mean_net_r", "std_net_r")
    return {k: _safe(value[k]) for k in keys if k in value}


def _compact_item(item: Dict[str, Any], rank: int) -> Dict[str, Any]:
    candidate = item.get("candidate", item.get("strategy", {}))
    compact = {
        "rank": rank,
        "candidate": _candidate_summary(candidate),
        "candidate_index": item.get("candidate_index"),
        "validation_score": _metric(item.get("validation_score")),
        "walk_forward_score": _metric(item.get("walk_forward_score")),
        "monte_carlo_robustness": _metric(item.get("monte_carlo_robustness")),
        "sensitivity_robustness": _metric(item.get("sensitivity_robustness")),
        "regime_robustness": _metric(item.get("regime_robustness")),
        "oos_to_train_ratio": _metric(item.get("oos_to_train_ratio")),
        "dd_ratio": _metric(item.get("dd_ratio")),
        "train": _compact_metrics(item.get("train")),
        "test": _compact_metrics(item.get("test")),
    }
    windows = item.get("windows")
    if isinstance(windows, list):
        compact["walk_forward"] = {
            "window_count": item.get("window_count", len(windows)),
            "positive_windows": item.get("positive_windows"),
            "positive_window_ratio": item.get("positive_window_ratio"),
            "oos_net_r_sum": item.get("oos_net_r_sum"),
            "oos_net_r_mean": item.get("oos_net_r_mean"),
            "oos_pf_mean": item.get("oos_pf_mean"),
            "windows": [_compact_window(w) for w in windows],
        }
    if item.get("monte_carlo") is not None:
        compact["monte_carlo"] = _compact_mc(item.get("monte_carlo"))
    if item.get("parameter_sensitivity") is not None:
        compact["parameter_sensitivity"] = _compact_sensitivity(item.get("parameter_sensitivity"))
    if item.get("market_regime") is not None:
        compact["market_regime"] = _compact_regime(item.get("market_regime"))
    return _safe(compact)


def _markdown(report: Dict[str, Any]) -> str:
    run, data, cfg, pipeline = report["run"], report["data"], report["config"], report["pipeline"]
    ranked = report["ranking"]["top_strategies"]
    best = ranked[0] if ranked else None
    lines = [
        "# XAU Strategy Research Report", "",
        "> Machine-readable companion: `research_report.json`. Raw bulky research files are intentionally not included in this report.", "",
        "## Executive Summary",
        f"- Research ID: `{run['research_id']}`",
        f"- Generated UTC: `{run['generated_utc']}`",
        f"- Code version: `{run.get('code_version')}`",
        f"- Symbol: `{data.get('symbol', 'unknown')}`",
        f"- Timeframe: `{data.get('timeframe', 'unknown')}`",
        f"- Bars: `{data.get('bars', 'unknown')}`",
        f"- Candidates generated: `{pipeline['candidates_generated']}`",
        f"- Accepted OOS strategies: `{pipeline['accepted_oos']}`",
        f"- Final ranked strategies: `{pipeline['final_ranked']}`",
    ]
    if best:
        bc = best["candidate"]
        lines += ["", "### Best Strategy", f"- Name: `{bc.get('name', 'unknown')}`", f"- Direction: `{bc.get('direction', 'unknown')}`", f"- Validation score: `{best.get('validation_score', 0):.4f}`", f"- Walk-forward score: `{best.get('walk_forward_score', 0):.4f}`", f"- Monte Carlo robustness: `{best.get('monte_carlo_robustness', 0):.2f}`", f"- Sensitivity robustness: `{best.get('sensitivity_robustness', 0):.2f}`", f"- Regime robustness: `{best.get('regime_robustness', 0):.2f}`", f"- OOS Net R: `{best.get('test', {}).get('net_r', 0)}`", f"- OOS Profit Factor: `{best.get('test', {}).get('profit_factor', 0)}`"]
    lines += ["", "## Runtime", f"```json\n{json.dumps(report['runtime'], indent=2, ensure_ascii=False)}\n```", "", "## Data", f"- Start: `{data.get('start')}`", f"- End: `{data.get('end')}`", f"- Train bars: `{data.get('train_bars')}`", f"- Test bars: `{data.get('test_bars')}`", "", "## Research Configuration"]
    for k, v in cfg.items():
        lines.append(f"- `{k}`: `{json.dumps(v, ensure_ascii=False)}`")
    lines += ["", "## Pipeline", ""]
    for k, v in pipeline.items():
        lines.append(f"- **{k}**: `{v}`")
    lines += ["", "## Top Strategies", "", "| Rank | Strategy | Validation | WF | MC | Sensitivity | Regime | OOS PF | OOS Net R |", "|---:|---|---:|---:|---:|---:|---:|---:|---:|"]
    for item in ranked:
        c, test = item["candidate"], item.get("test", {})
        lines.append(f"| {item['rank']} | `{c.get('name','')}` | {item.get('validation_score',0):.2f} | {item.get('walk_forward_score',0):.2f} | {item.get('monte_carlo_robustness',0):.1f} | {item.get('sensitivity_robustness',0):.1f} | {item.get('regime_robustness',0):.1f} | {test.get('profit_factor',0)} | {test.get('net_r',0)} |")
    lines += ["", "## Audit Notes", "- Ranking components are exported separately so the final decision can be audited.", "- Raw trades/equity curves are deliberately excluded from this compact report to prevent GitHub file-size problems.", "- A positive historical result is not a guarantee of future profitability; forward testing remains required.", ""]
    return "\n".join(lines)


def export_research_report(output_dir: str | Path, *, research_id: str, data_info: Dict[str, Any], config: Any, pipeline: Dict[str, Any], ranked: Iterable[Dict[str, Any]], code_version: Optional[str] = None) -> Dict[str, str]:
    """Write the compact JSON/Markdown/manifest research package."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    ranked_items = [_compact_item(item, i) for i, item in enumerate(ranked, 1)]
    cfg = _safe(config)
    generated = datetime.now(timezone.utc).isoformat()
    runtime = _runtime_info()
    report = {
        "schema_version": "1.1",
        "run": {"research_id": research_id, "generated_utc": generated, "code_version": code_version},
        "runtime": runtime,
        "data": _safe(data_info),
        "config": cfg,
        "pipeline": _safe(pipeline),
        "ranking": {"final_order": "regime_robustness > sensitivity_robustness > monte_carlo_robustness > walk_forward_score", "top_strategies": ranked_items},
    }
    json_path = out / "research_report.json"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path = out / "CHATGPT_RESEARCH_REPORT.md"
    md_path.write_text(_markdown(report), encoding="utf-8")
    manifest = {
        "schema_version": "1.1", "research_id": research_id, "generated_utc": generated,
        "code_version": code_version, "report_schema": report["schema_version"],
        "files": ["research_report.json", "CHATGPT_RESEARCH_REPORT.md", "run_manifest.json"],
        "raw_large_files": ["ranked_strategies.json"], "raw_large_files_policy": "local_only_and_gitignored", "report_is_compact": True,
    }
    manifest_path = out / "run_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"report": str(json_path), "markdown": str(md_path), "manifest": str(manifest_path)}
