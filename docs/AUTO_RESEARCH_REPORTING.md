# Automatic Research Reporting

The project now supports a fully automatic local watcher for research results.

## What happens automatically

1. Windows starts the watcher at user logon.
2. The watcher monitors `results/ranked_strategies.json` every 10 seconds.
3. A completed Research run changes that file.
4. The watcher invokes `tools/large_result_publisher.py --once`.
5. The large JSON is analyzed locally and is never uploaded.
6. Only compact `results/large_result_digest.json` and `results/CHATGPT_LARGE_RESULT_AUDIT.md` are committed and pushed to the current Git branch.
7. SHA-256 and an idempotent state file prevent duplicate publishes.
8. Activity is recorded in `results/auto_research_publisher.log`.

## One-time installation

From the repository root run:

```bat
tools\install_auto_research_reporting.bat
```

The installer replaces the older five-minute polling task with an ONLOGON watcher.

## Manual verification

```bat
py -3.12 -m unittest tests.test_auto_research_reporter -v
py -3.12 -m unittest tests.test_large_result_publisher -v
py -3.12 -m compileall -q .
```

To run the watcher manually:

```bat
py -3.12 tools\auto_research_reporter.py --watch 10
```

Press `Ctrl+C` to stop the manually started watcher.

## Safety and data policy

- No real trading orders are sent by the reporting layer.
- The raw large result remains local.
- The publisher stages only its two compact audit outputs.
- Existing Git authentication is reused; no token is stored by the watcher.
- A publisher failure is logged and does not alter the local research result.
