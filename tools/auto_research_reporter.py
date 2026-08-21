"""Fully automatic local research-result watcher and GitHub publisher.

The watcher keeps the bulky research JSON local. Whenever the main ranked result
changes, it invokes the compact publisher and then the project-manager package
publisher. Only small audit/decision files are pushed to the current Git branch.

Usage:
    py -3.12 tools/auto_research_reporter.py --once
    py -3.12 tools/auto_research_reporter.py --watch 10
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "results" / "ranked_strategies.json"
PUBLISHER = ROOT / "tools" / "large_result_publisher.py"
MANAGER_PUBLISHER = ROOT / "tools" / "project_manager_reporter.py"
LOG_FILE = ROOT / "results" / "auto_research_publisher.log"
LOCK_FILE = ROOT / "results" / ".auto_research_reporter.lock"


def _log(message: str) -> None:
    line = f"{datetime.now(timezone.utc).isoformat()} [AUTO-PUBLISH] {message}"
    print(line, flush=True)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def _fingerprint() -> tuple[int, int] | None:
    try:
        stat = INPUT.stat()
        return stat.st_mtime_ns, stat.st_size
    except FileNotFoundError:
        return None


def _acquire_lock() -> bool:
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    if LOCK_FILE.exists():
        try:
            state = json.loads(LOCK_FILE.read_text(encoding="utf-8"))
            pid = int(state.get("pid", 0))
            if pid and pid != os.getpid():
                try:
                    os.kill(pid, 0)
                    _log(f"already running with PID={pid}")
                    return False
                except OSError:
                    pass
        except Exception:
            pass
    LOCK_FILE.write_text(json.dumps({"pid": os.getpid(), "started_utc": datetime.now(timezone.utc).isoformat()}, indent=2), encoding="utf-8")
    return True


def _release_lock() -> None:
    try:
        LOCK_FILE.unlink()
    except FileNotFoundError:
        pass


def _run_publisher(command: list[str], label: str, timeout: int = 1800) -> int:
    try:
        completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        _log(f"ERROR: {label} timed out after {timeout // 60} minutes")
        return 3
    if completed.stdout:
        for line in completed.stdout.splitlines():
            _log(line)
    if completed.stderr:
        for line in completed.stderr.splitlines():
            _log("STDERR: " + line)
    if completed.returncode != 0:
        _log(f"ERROR: {label} exit code={completed.returncode}")
    return completed.returncode


def publish_once() -> int:
    if not INPUT.exists():
        _log(f"waiting: {INPUT} does not exist")
        return 0
    if not PUBLISHER.exists():
        _log(f"ERROR: publisher missing: {PUBLISHER}")
        return 2
    if not MANAGER_PUBLISHER.exists():
        _log(f"ERROR: project manager publisher missing: {MANAGER_PUBLISHER}")
        return 2

    _log(f"research result detected: {INPUT.name} size={INPUT.stat().st_size} bytes")
    publisher_command = [sys.executable, str(PUBLISHER), "--once", "--input", str(INPUT)]
    rc = _run_publisher(publisher_command, "large-result publisher")
    if rc != 0:
        return rc

    manager_command = [sys.executable, str(MANAGER_PUBLISHER), "--once"]
    rc = _run_publisher(manager_command, "project-manager publisher")
    if rc != 0:
        return rc

    _log("publish cycle completed successfully")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="publish the current result once")
    parser.add_argument("--watch", type=int, metavar="SECONDS", help="watch for changes until interrupted")
    args = parser.parse_args()
    if not args.once and not args.watch:
        args.watch = 10

    if not _acquire_lock():
        return 0
    try:
        last = None
        # Publish the current result at startup; both downstream publishers are idempotent.
        publish_once()
        last = _fingerprint()
        if args.once:
            return 0
        interval = max(5, args.watch or 10)
        _log(f"watching {INPUT} every {interval}s")
        while True:
            current = _fingerprint()
            if current != last:
                _log(f"change detected: previous={last} current={current}")
                rc = publish_once()
                if rc == 0:
                    last = current
            time.sleep(interval)
    except KeyboardInterrupt:
        _log("stopped by user")
        return 0
    finally:
        _release_lock()


if __name__ == "__main__":
    raise SystemExit(main())
