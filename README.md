# MT5-AI-Trader

## Research outputs

After a successful XAU Strategy Research run, the application publishes a compact audit package in `results/`:

- `CHATGPT_RESEARCH_REPORT.md` — human-readable summary.
- `research_report.json` — structured report for programmatic review.
- `run_manifest.json` — report identity and large-file policy.
- `ranked_strategies.csv` — ranked strategy table.
- `best_strategy_rules.json` — winning strategy specification.
- `best_strategy_trades.csv` — trade evidence for the winner.

The large raw `results/ranked_strategies.json` file remains local and is gitignored. This keeps GitHub within its file-size limits while preserving the evidence needed to audit each run.