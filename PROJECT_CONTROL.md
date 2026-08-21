# Project Control & Research Access Contract

## Purpose
This document defines how the XAU Strategy Researcher exposes its state and research evidence so the project can be reviewed safely and reproducibly.

## Repository of record
- Repository: `zagor-ai/MT5-AI-Trader`
- Active research branch: `xau-researcher-v2.1.1-clean`
- Default branch: `main`

The GitHub repository is the source of truth for source code, configuration, tests, research reports and small derived result files.

## What can be reviewed from GitHub
1. Complete committed source code and configuration.
2. Research configuration and strategy-generation rules.
3. Validation pipeline: train/test, walk-forward, Monte Carlo, sensitivity and regime analysis.
4. Small, structured research reports and ranked result tables.
5. Commit history and exact code revision associated with a research run.

## What must NOT be committed
Large raw result files, caches, virtual environments, Python bytecode and temporary files remain local. In particular, `results/ranked_strategies.json`, `results/full/` and `results/raw/` are intentionally excluded from Git history.

## Required research identity
Every published research run should contain:
- `research_id`
- UTC/local start and finish timestamps
- git commit SHA (captured at runtime with `git rev-parse HEAD`)
- application version
- Python version
- package versions
- MT5 terminal/build/server information when available
- symbol and timeframe
- data bar count and first/last bar timestamps
- full research configuration

## Required evidence
A published run should include a compact report containing:
- candidate generation counts
- rejection counts and reasons
- train/test statistics
- all walk-forward windows for accepted strategies
- Monte Carlo summary
- parameter sensitivity summary
- market-regime summary
- final ranking and score components
- best strategy rules
- runtime metadata and warnings

## Manager workflow
Before changing strategy logic:
1. Inspect current branch and recent commits.
2. Inspect the research engine and validators.
3. Inspect the latest research report.
4. Check reproducibility and data-leakage risks.
5. Make the smallest safe code change.
6. Compile/test before requesting a new research run.
7. Publish a new report tied to the resulting commit SHA.

## Runtime limitation
GitHub gives the reviewer access to committed project state. It does not provide a live connection to the user's local MT5 terminal or uncommitted local files. The application therefore publishes a compact, machine-readable research snapshot after each run.

## Research reporting interface
After a successful ResearchEngine run, `results/` contains:
- `CHATGPT_RESEARCH_REPORT.md` — human-readable audit summary.
- `research_report.json` — structured compact report for programmatic analysis.
- `run_manifest.json` — identity and large-file policy.
- `ranked_strategies.csv` — ranked table.
- `best_strategy_rules.json` — winning strategy specification.
- `best_strategy_trades.csv` — trade evidence for the winner.

The raw `results/ranked_strategies.json` remains local and gitignored. The compact reports deliberately omit raw equity curves and full trade arrays so GitHub remains below its file-size limits.

## Completed implementation
The ResearchEngine now generates the three compact audit files automatically when research results are exported. The report records candidate/rejection counts, data shape, full ResearchConfig, runtime/package/MT5 metadata when available, walk-forward summaries, robustness components, final ranking and the winning strategy specification. It also captures the exact Git commit present when the report is generated.
