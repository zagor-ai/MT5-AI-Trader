# Large Research Result Publishing

## Purpose
`results/ranked_strategies.json` can become hundreds of MB because it contains bulky trade/equity evidence. It must remain local. `tools/large_result_publisher.py` analyzes that local file and publishes only a compact audit package.

## Published files
- `results/large_result_digest.json` — machine-readable digest with the source SHA-256, all compact strategy metrics, rules, robustness metrics and distributions.
- `results/CHATGPT_LARGE_RESULT_AUDIT.md` — concise human-readable ranking/audit table.

The raw JSON is never staged or pushed.

## One-shot
From the repository root:

```bat
py -3.12 tools\large_result_publisher.py --once
```

or:

```bat
tools\run_large_result_publisher.bat
```

## Automatic schedule
Run:

```bat
tools\install_large_result_scheduler.bat
```

Windows Task Scheduler checks the large file every 5 minutes. The publisher calculates SHA-256 first; if the source has not changed, no Git commit is created.

## Safety
- Only the two compact audit files are staged.
- Existing unrelated local changes are not staged.
- Git authentication is delegated to the user's existing Git configuration/browser authentication.
- If GitHub is temporarily unavailable, the local large result remains untouched and can be published on the next scheduled attempt.
- The source SHA-256 in the digest allows the reviewer to identify exactly which local raw file was summarized.
