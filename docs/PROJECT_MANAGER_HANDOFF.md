# Automatic Project Manager Handoff

The research pipeline now publishes a compact evidence handoff after every detected change to `results/ranked_strategies.json`.

## Published files

- `results/large_result_digest.json` — compact audit extracted from the large local result.
- `results/CHATGPT_LARGE_RESULT_AUDIT.md` — human-readable large-result audit.
- `results/CHATGPT_DECISION_PACKAGE.json` — machine-readable decision package for project review.
- `results/PROJECT_MANAGER_STATUS.md` — concise project-manager status page.

## Automatic flow

`Start Research` → `ranked_strategies.json` → large-result publisher → project-manager publisher → Git commit/push.

The watcher runs from Windows Task Scheduler and checks the ranked result every 10 seconds by default. Both publishing stages are idempotent and protected by the source SHA-256.

## Safety policy

The raw large research JSON remains local and is never committed or uploaded. Missing metrics remain `null`/`N/A`; they are not silently converted to zero. The decision package is an evidence handoff and never authorizes live trading.

## Manager decision states

- `NO_VALID_STRATEGY` — no usable ranked strategy was found.
- `REQUIRES_FURTHER_VALIDATION` — deterministic audit flags require more independent validation.
- `READY_FOR_FORWARD_TEST` — the deterministic audit found no blocking quality flags; controlled forward testing is still required.
