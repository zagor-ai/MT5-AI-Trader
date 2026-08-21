"""Analyze bulky local research JSON and publish a compact audit package to GitHub.

The raw JSON never leaves the user's machine. This tool reads the large file,
extracts only audit-relevant evidence, writes compact Markdown/JSON, and then
uses the user's existing Git authentication to commit/push the compact files.

Usage:
    py -3.12 tools/large_result_publisher.py --once
    py -3.12 tools/large_result_publisher.py --watch 60
"""
from __future__ import annotations

import argparse
import hashlib
import json
from math import isfinite
from pathlib import Path
import subprocess
import time
from datetime import datetime, timezone
from typing import Any

DEFAULT_INPUT = Path("results/ranked_strategies.json")
DEFAULT_OUTPUT = Path("results/large_result_digest.json")
DEFAULT_MARKDOWN = Path("results/CHATGPT_LARGE_RESULT_AUDIT.md")
STATE_FILE = Path("results/.large_result_publish_state.json")


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True, stderr=subprocess.STDOUT).strip()


def _git_sha() -> str | None:
    try:
        return _git("rev-parse", "HEAD") or None
    except Exception:
        return None


def _optional_number(value: Any) -> float | None:
    try:
        number = float(value)
        return number if isfinite(number) else None
    except (TypeError, ValueError):
        return None


def _safe_number(value: Any, default: float = 0.0) -> float:
    number = _optional_number(value)
    return default if number is None else number


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2.0


def _file_fingerprint(path: Path) -> dict[str, Any]:
    h = hashlib.sha256()
    size = 0
    with path.open("rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            h.update(chunk)
    stat = path.stat()
    return {"path": str(path), "bytes": size, "sha256": h.hexdigest(), "modified_utc": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat()}


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _find_records(obj: Any) -> list[dict[str, Any]]:
    if isinstance(obj, list):
        return [x for x in obj if isinstance(x, dict)]
    if isinstance(obj, dict):
        for key in ("ranked", "results", "strategies", "top_strategies", "data"):
            value = obj.get(key)
            if isinstance(value, list) and value and all(isinstance(x, dict) for x in value[: min(20, len(value))]):
                return value
        for value in obj.values():
            if isinstance(value, list) and value and isinstance(value[0], dict):
                return value
    return []


def _candidate_name(row: dict[str, Any]) -> str:
    candidate = row.get("candidate", row.get("strategy", {}))
    if isinstance(candidate, dict):
        return str(candidate.get("name", row.get("strategy_name", "unknown")))
    return str(row.get("strategy_name", candidate))


def _first_number(*values: Any) -> float | None:
    for value in values:
        number = _optional_number(value)
        if number is not None:
            return number
    return None


def _compact_strategy(row: dict[str, Any], rank: int) -> dict[str, Any]:
    candidate = row.get("candidate", row.get("strategy", {}))
    if hasattr(candidate, "to_dict"):
        candidate = candidate.to_dict()
    if not isinstance(candidate, dict):
        candidate = {"name": str(candidate)}

    test = row.get("test", {}) if isinstance(row.get("test", {}), dict) else {}
    wf = row.get("walk_forward", {}) if isinstance(row.get("walk_forward", {}), dict) else {}
    mc = row.get("monte_carlo", {}) if isinstance(row.get("monte_carlo", {}), dict) else {}

    # Final ranked records may contain only Walk-Forward results. In that case
    # the WF aggregate is the authoritative OOS evidence and must not become 0.
    oos_pf = _first_number(test.get("profit_factor"), wf.get("oos_pf_mean"), row.get("oos_pf_mean"))
    oos_net_r = _first_number(test.get("net_r"), wf.get("oos_net_r_sum"), row.get("oos_net_r_sum"))
    oos_net_r_mean = _first_number(wf.get("oos_net_r_mean"), row.get("oos_net_r_mean"))
    oos_trade_count = test.get("trade_count")
    oos_win_rate = test.get("win_rate")
    oos_expectancy = test.get("expectancy")
    oos_dd = _first_number(test.get("max_drawdown_r"), wf.get("p95_max_drawdown_r"))

    evidence = {
        "oos_source": "test" if _optional_number(test.get("profit_factor")) is not None or _optional_number(test.get("net_r")) is not None else ("walk_forward" if oos_pf is not None or oos_net_r is not None else "unavailable"),
        "test_metrics_available": bool(test),
    }

    return {
        "rank": rank,
        "name": _candidate_name(row),
        "direction": candidate.get("direction"),
        "candidate": candidate,
        "validation_score": _optional_number(row.get("validation_score")),
        "walk_forward_score": _optional_number(row.get("walk_forward_score")),
        "monte_carlo_robustness": _optional_number(row.get("monte_carlo_robustness")),
        "sensitivity_robustness": _optional_number(row.get("sensitivity_robustness")),
        "regime_robustness": _optional_number(row.get("regime_robustness")),
        "oos_to_train_ratio": _optional_number(row.get("oos_to_train_ratio")),
        "dd_ratio": _optional_number(row.get("dd_ratio")),
        "evidence": evidence,
        "oos": {
            "trade_count": oos_trade_count,
            "win_rate": oos_win_rate,
            "profit_factor": oos_pf,
            "net_r": oos_net_r,
            "net_r_mean": oos_net_r_mean,
            "expectancy": oos_expectancy,
            "max_drawdown_r": oos_dd,
        },
        "walk_forward": {
            "window_count": wf.get("window_count", row.get("window_count")),
            "positive_windows": wf.get("positive_windows", row.get("positive_windows")),
            "positive_window_ratio": wf.get("positive_window_ratio", row.get("positive_window_ratio")),
            "oos_net_r_sum": wf.get("oos_net_r_sum", row.get("oos_net_r_sum")),
            "oos_net_r_mean": wf.get("oos_net_r_mean", row.get("oos_net_r_mean")),
            "oos_pf_mean": wf.get("oos_pf_mean", row.get("oos_pf_mean")),
        },
        "monte_carlo": {k: mc.get(k) for k in ("simulations", "probability_positive", "probability_ruin", "p05_net_r", "p50_net_r", "p95_net_r", "p95_max_drawdown_r") if k in mc},
    }


def _quality_checks(strategies: list[dict[str, Any]]) -> list[str]:
    warnings: list[str] = []
    missing_base_oos = sum(1 for x in strategies if x["evidence"]["oos_source"] == "walk_forward")
    unavailable_oos = sum(1 for x in strategies if x["evidence"]["oos_source"] == "unavailable")
    missing_validation = sum(1 for x in strategies if x.get("validation_score") is None)
    if missing_base_oos:
        warnings.append(f"Base TRAIN/TEST OOS metrics unavailable for {missing_base_oos}/{len(strategies)} ranked strategies; Walk-Forward OOS aggregates were used instead.")
    if unavailable_oos:
        warnings.append(f"No OOS metrics were found for {unavailable_oos}/{len(strategies)} ranked strategies.")
    if missing_validation:
        warnings.append(f"Validation score is unavailable for {missing_validation}/{len(strategies)} ranked strategies in the final export.")
    if not warnings:
        warnings.append("No report-consistency warnings detected in the compacted ranking evidence.")
    return warnings


def build_digest(path: Path) -> tuple[dict[str, Any], str]:
    fingerprint = _file_fingerprint(path)
    raw = _load_json(path)
    records = _find_records(raw)
    if not records:
        raise ValueError("Could not locate a strategy-record list in the large JSON file")

    compact = [_compact_strategy(row, i) for i, row in enumerate(records, 1)]
    pfs = [x["oos"]["profit_factor"] for x in compact if x["oos"]["profit_factor"] is not None]
    nets = [x["oos"]["net_r"] for x in compact if x["oos"]["net_r"] is not None]
    positives = [float(x["walk_forward"]["positive_window_ratio"]) for x in compact if _optional_number(x["walk_forward"].get("positive_window_ratio")) is not None]
    best = compact[0] if compact else None
    warnings = _quality_checks(compact)
    digest = {
        "schema_version": "1.1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "source": fingerprint,
        "git_commit_sha": _git_sha(),
        "raw_file_policy": "local_only; never committed or uploaded",
        "record_count": len(compact),
        "quality": {
            "status": "WARNING" if any(not x.startswith("No report-consistency") for x in warnings) else "OK",
            "warnings": warnings,
            "oos_metric_policy": "prefer final test metrics; otherwise use Walk-Forward OOS aggregates; never convert missing values to zero",
        },
        "summary": {
            "best_strategy": best,
            "oos_profit_factor": {"min": min(pfs) if pfs else None, "median": _median(pfs), "max": max(pfs) if pfs else None},
            "oos_net_r": {"min": min(nets) if nets else None, "median": _median(nets), "max": max(nets) if nets else None},
            "walk_forward_positive_ratio": {"min": min(positives) if positives else None, "mean": sum(positives) / len(positives) if positives else None, "max": max(positives) if positives else None},
        },
        "strategies": compact,
    }
    markdown = _markdown(digest)
    del raw
    return digest, markdown


def _fmt(value: Any, digits: int = 2) -> str:
    number = _optional_number(value)
    return "N/A" if number is None else f"{number:.{digits}f}"


def _markdown(digest: dict[str, Any]) -> str:
    s = digest["source"]
    summary = digest["summary"]
    quality = digest["quality"]
    lines = [
        "# XAU Large Result Audit",
        "",
        "Automatically generated compact audit of the local large research JSON. The raw file is never uploaded.",
        "",
        "## Source",
        f"- Path: `{s['path']}`",
        f"- Size: `{s['bytes'] / (1024 * 1024):.2f} MB`",
        f"- SHA-256: `{s['sha256']}`",
        f"- Modified UTC: `{s['modified_utc']}`",
        f"- Source Git commit: `{digest.get('git_commit_sha')}`",
        f"- Strategy records: `{digest['record_count']}`",
        "",
        "## Report Quality",
        f"- Status: **{quality['status']}**",
        f"- OOS policy: `{quality['oos_metric_policy']}`",
    ]
    lines.extend(f"- ⚠ {warning}" for warning in quality["warnings"] if not warning.startswith("No report-consistency"))
    if quality["status"] == "OK":
        lines.append("- ✓ No report-consistency warnings detected.")
    lines += [
        "",
        "## Distribution",
        f"- OOS PF: min `{summary['oos_profit_factor']['min']}`, median `{summary['oos_profit_factor']['median']}`, max `{summary['oos_profit_factor']['max']}`",
        f"- OOS Net R: min `{summary['oos_net_r']['min']}`, median `{summary['oos_net_r']['median']}`, max `{summary['oos_net_r']['max']}`",
        f"- Walk-forward positive-window ratio: min `{summary['walk_forward_positive_ratio']['min']}`, mean `{summary['walk_forward_positive_ratio']['mean']}`, max `{summary['walk_forward_positive_ratio']['max']}`",
        "",
        "## Ranking",
        "",
        "| Rank | Strategy | Dir | Validation | WF | MC | Sensitivity | Regime | OOS Source | OOS PF | OOS Net R | WF Positive |",
        "|---:|---|:---:|---:|---:|---:|---:|---:|---|---:|---:|---:|",
    ]
    for x in digest["strategies"]:
        lines.append(
            f"| {x['rank']} | `{x['name']}` | {x.get('direction','')} | {_fmt(x['validation_score'])} | {_fmt(x['walk_forward_score'])} | {_fmt(x['monte_carlo_robustness'],1)} | {_fmt(x['sensitivity_robustness'],1)} | {_fmt(x['regime_robustness'],1)} | `{x['evidence']['oos_source']}` | {_fmt(x['oos'].get('profit_factor'))} | {_fmt(x['oos'].get('net_r'))} | {_fmt(x['walk_forward'].get('positive_window_ratio'),3)} |"
        )
    lines += [
        "",
        "## Best Strategy Evidence",
        f"- Strategy: `{digest['strategies'][0]['name']}`" if digest["strategies"] else "- Strategy: N/A",
        f"- OOS source: `{digest['strategies'][0]['evidence']['oos_source']}`" if digest["strategies"] else "- OOS source: N/A",
        f"- Walk-Forward: `{digest['strategies'][0]['walk_forward'].get('positive_windows')}/{digest['strategies'][0]['walk_forward'].get('window_count')}` positive windows" if digest["strategies"] else "- Walk-Forward: N/A",
        f"- OOS Net R: `{digest['strategies'][0]['oos'].get('net_r')}`" if digest["strategies"] else "- OOS Net R: N/A",
        f"- OOS PF: `{digest['strategies'][0]['oos'].get('profit_factor')}`" if digest["strategies"] else "- OOS PF: N/A",
        "",
        "## Audit Policy",
        "- Full strategy definitions and ranking metrics are retained in the compact JSON.",
        "- Trade arrays, equity curves and other bulky raw fields are removed before publication.",
        "- Missing metrics remain `null`/`N/A`; they are never silently converted to zero.",
        "- When final TRAIN/TEST OOS metrics are absent, Walk-Forward OOS aggregates are used and the report explicitly warns about it.",
        "- The source SHA-256 lets the manager detect whether the local large file changed.",
        "- Publishing is idempotent: an unchanged source file creates no new commit.",
        "",
    ]
    return "\n".join(lines)


def _load_state() -> dict[str, Any]:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def publish_once(input_path: Path = DEFAULT_INPUT) -> bool:
    if not input_path.exists():
        raise FileNotFoundError(f"Large result file not found: {input_path}")
    digest, markdown = build_digest(input_path)
    source_hash = digest["source"]["sha256"]
    state = _load_state()
    if state.get("source_sha256") == source_hash and DEFAULT_OUTPUT.exists() and DEFAULT_MARKDOWN.exists():
        print(f"[PUBLISH] unchanged source: {source_hash[:12]} — nothing to publish")
        return False

    DEFAULT_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_OUTPUT.write_text(json.dumps(digest, indent=2, ensure_ascii=False), encoding="utf-8")
    DEFAULT_MARKDOWN.write_text(markdown, encoding="utf-8")
    STATE_FILE.write_text(json.dumps({"source_sha256": source_hash, "published_utc": datetime.now(timezone.utc).isoformat()}, indent=2), encoding="utf-8")

    subprocess.run(["git", "add", "--", str(DEFAULT_OUTPUT), str(DEFAULT_MARKDOWN)], check=True)
    status = subprocess.check_output(["git", "status", "--porcelain"], text=True)
    if not status.strip():
        print("[PUBLISH] no Git changes")
        return False
    message = f"Publish large research audit {digest['generated_utc'][:19].replace(':', '')}Z"
    subprocess.run(["git", "commit", "-m", message], check=True)
    subprocess.run(["git", "push", "origin", _git("branch", "--show-current")], check=True)
    print(f"[PUBLISH] uploaded compact audit for {input_path} | SHA256={source_hash}")
    return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="analyze and publish once")
    parser.add_argument("--watch", type=int, metavar="SECONDS", help="repeat until interrupted")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    args = parser.parse_args()
    if not args.once and not args.watch:
        args.once = True
    if args.once:
        publish_once(args.input)
        return
    while True:
        try:
            publish_once(args.input)
        except Exception as exc:
            print(f"[PUBLISH] ERROR: {exc}")
        time.sleep(max(5, args.watch))


if __name__ == "__main__":
    main()
