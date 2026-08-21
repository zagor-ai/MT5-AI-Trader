"""Build and publish the compact project-manager package for each research run.

This layer consumes the already-compacted large-result digest, so it never
re-reads or uploads the bulky ranked_strategies.json. It creates a deterministic
machine-readable decision package and a human-readable status page, then pushes
only those small files to the current Git branch.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
from datetime import datetime, timezone
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DIGEST = ROOT / "results" / "large_result_digest.json"
PACKAGE = ROOT / "results" / "CHATGPT_DECISION_PACKAGE.json"
STATUS = ROOT / "results" / "PROJECT_MANAGER_STATUS.md"


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True, stderr=subprocess.STDOUT).strip()


def _num(value: Any) -> float | None:
    try:
        number = float(value)
        return number if number == number and number not in (float("inf"), float("-inf")) else None
    except (TypeError, ValueError):
        return None


def _best(digest: dict[str, Any]) -> dict[str, Any]:
    rows = digest.get("strategies") or []
    return rows[0] if rows else {}


def build_decision_package(digest: dict[str, Any]) -> dict[str, Any]:
    best = _best(digest)
    quality = digest.get("quality") or {}
    oos = best.get("oos") or {}
    wf = best.get("walk_forward") or {}
    mc = best.get("monte_carlo") or {}

    flags: list[str] = []
    if quality.get("status") == "WARNING":
        flags.extend(quality.get("warnings") or [])
    if best.get("validation_score") is None:
        flags.append("Validation score is unavailable in the final ranked export.")
    pf = _num(oos.get("profit_factor"))
    wf_positive = _num(wf.get("positive_window_ratio"))
    mc_positive = _num(mc.get("probability_positive"))
    regime = _num(best.get("regime_robustness"))
    if pf is not None and pf < 1.10:
        flags.append(f"Best OOS profit factor is only {pf:.2f}; edge is modest.")
    if wf_positive is not None and wf_positive < 0.80:
        flags.append(f"Only {wf_positive:.1%} of Walk-Forward windows are positive.")
    if mc_positive is not None and mc_positive < 0.80:
        flags.append(f"Monte Carlo positive-outcome probability is {mc_positive:.1%}.")
    if regime is not None and regime < 70:
        flags.append(f"Market-regime robustness is {regime:.1f}/100.")

    if not best:
        recommendation = "NO_VALID_STRATEGY"
        next_action = "Inspect research pipeline and data quality before further research."
    elif flags:
        recommendation = "REQUIRES_FURTHER_VALIDATION"
        next_action = "Run another independent research sample and forward-test the leading candidates; do not treat the ranking as production-ready."
    else:
        recommendation = "READY_FOR_FORWARD_TEST"
        next_action = "Run controlled forward testing on the leading candidates before any live deployment decision."

    return {
        "schema_version": "1.0",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "source": {
            "path": digest.get("source", {}).get("path"),
            "bytes": digest.get("source", {}).get("bytes"),
            "sha256": digest.get("source", {}).get("sha256"),
            "modified_utc": digest.get("source", {}).get("modified_utc"),
            "digest_schema_version": digest.get("schema_version"),
        },
        "quality": quality,
        "decision": {
            "recommendation": recommendation,
            "next_action": next_action,
            "risk_flags": flags,
        },
        "best_strategy": {
            "rank": best.get("rank"),
            "name": best.get("name"),
            "direction": best.get("direction"),
            "candidate": best.get("candidate"),
            "validation_score": best.get("validation_score"),
            "walk_forward_score": best.get("walk_forward_score"),
            "monte_carlo_robustness": best.get("monte_carlo_robustness"),
            "sensitivity_robustness": best.get("sensitivity_robustness"),
            "regime_robustness": best.get("regime_robustness"),
            "oos": oos,
            "walk_forward": wf,
            "monte_carlo": mc,
        },
        "research_snapshot": {
            "record_count": digest.get("record_count"),
            "distribution": digest.get("summary"),
            "top_strategies": [
                {
                    "rank": row.get("rank"),
                    "name": row.get("name"),
                    "direction": row.get("direction"),
                    "oos_source": (row.get("evidence") or {}).get("oos_source"),
                    "oos_pf": (row.get("oos") or {}).get("profit_factor"),
                    "oos_net_r": (row.get("oos") or {}).get("net_r"),
                    "wf_positive": (row.get("walk_forward") or {}).get("positive_window_ratio"),
                    "wf_score": row.get("walk_forward_score"),
                    "mc_robustness": row.get("monte_carlo_robustness"),
                    "sensitivity_robustness": row.get("sensitivity_robustness"),
                    "regime_robustness": row.get("regime_robustness"),
                }
                for row in (digest.get("strategies") or [])[:10]
            ],
        },
        "audit_policy": {
            "raw_large_file_uploaded": False,
            "raw_large_file_kept_local": True,
            "missing_metrics_preserved": True,
            "oos_fallback_policy": "test metrics first, otherwise Walk-Forward aggregates",
        },
    }


def _markdown(package: dict[str, Any]) -> str:
    source = package["source"]
    decision = package["decision"]
    best = package["best_strategy"]
    oos = best.get("oos") or {}
    wf = best.get("walk_forward") or {}
    lines = [
        "# XAU Project Manager Status",
        "",
        "Automatically generated from the compact research digest. The raw 300+ MB research JSON remains local.",
        "",
        "## Decision",
        f"- **Recommendation:** `{decision['recommendation']}`",
        f"- **Next action:** {decision['next_action']}",
        f"- Generated UTC: `{package['generated_utc']}`",
        "",
        "## Best Strategy",
        f"- Strategy: `{best.get('name', 'N/A')}`",
        f"- Direction: `{best.get('direction', 'N/A')}`",
        f"- OOS source: `{(oos.get('profit_factor') is not None and 'test') or 'walk_forward'}`",
        f"- OOS PF: `{oos.get('profit_factor', 'N/A')}`",
        f"- OOS Net R: `{oos.get('net_r', 'N/A')}`",
        f"- Walk-Forward positive windows: `{wf.get('positive_windows', 'N/A')}/{wf.get('window_count', 'N/A')}`",
        f"- Walk-Forward score: `{best.get('walk_forward_score', 'N/A')}`",
        f"- Monte Carlo robustness: `{best.get('monte_carlo_robustness', 'N/A')}`",
        f"- Sensitivity robustness: `{best.get('sensitivity_robustness', 'N/A')}`",
        f"- Regime robustness: `{best.get('regime_robustness', 'N/A')}`",
        "",
        "## Risk Flags",
    ]
    flags = decision.get("risk_flags") or []
    lines.extend(f"- ⚠ {flag}" for flag in flags) if flags else lines.append("- ✓ No deterministic risk flags were raised by the audit layer.")
    lines += [
        "",
        "## Top 10 Snapshot",
        "",
        "| Rank | Strategy | Dir | OOS PF | OOS Net R | WF+ | WF | MC | Sens | Regime |",
        "|---:|---|:---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in package["research_snapshot"]["top_strategies"]:
        lines.append(f"| {row.get('rank','')} | `{row.get('name','')}` | {row.get('direction','')} | {row.get('oos_pf','N/A')} | {row.get('oos_net_r','N/A')} | {row.get('wf_positive','N/A')} | {row.get('wf_score','N/A')} | {row.get('mc_robustness','N/A')} | {row.get('sensitivity_robustness','N/A')} | {row.get('regime_robustness','N/A')} |")
    lines += [
        "",
        "## Source Integrity",
        f"- Source: `{source.get('path')}`",
        f"- Size: `{source.get('bytes')}` bytes",
        f"- SHA-256: `{source.get('sha256')}`",
        f"- Modified UTC: `{source.get('modified_utc')}`",
        "- Raw result policy: local only; never uploaded.",
        "",
        "## Manager Note",
        "This package is an evidence handoff for project review. It does not authorize live trading and does not replace independent forward validation.",
        "",
    ]
    return "\n".join(lines)


def publish_once() -> bool:
    if not DIGEST.exists():
        raise FileNotFoundError(f"Digest not found: {DIGEST}")
    digest = json.loads(DIGEST.read_text(encoding="utf-8"))
    source_sha = (digest.get("source") or {}).get("sha256")
    if not source_sha:
        raise ValueError("Digest has no source SHA-256")
    if PACKAGE.exists():
        try:
            existing = json.loads(PACKAGE.read_text(encoding="utf-8"))
            if (existing.get("source") or {}).get("sha256") == source_sha and STATUS.exists():
                print(f"[MANAGER] unchanged source: {source_sha[:12]} — nothing to publish")
                return False
        except Exception:
            pass

    package = build_decision_package(digest)
    PACKAGE.write_text(json.dumps(package, indent=2, ensure_ascii=False), encoding="utf-8")
    STATUS.write_text(_markdown(package), encoding="utf-8")
    subprocess.run(["git", "add", "--", str(PACKAGE), str(STATUS)], cwd=ROOT, check=True)
    status = subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True)
    if not status.strip():
        print("[MANAGER] no Git changes")
        return False
    message = f"Publish project manager package {package['generated_utc'][:19].replace(':', '')}Z"
    subprocess.run(["git", "commit", "-m", message], cwd=ROOT, check=True)
    branch = _git("branch", "--show-current")
    subprocess.run(["git", "push", "origin", branch], cwd=ROOT, check=True)
    print(f"[MANAGER] published decision package | SHA256={source_sha}")
    return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    if not args.once:
        args.once = True
    publish_once()


if __name__ == "__main__":
    main()
