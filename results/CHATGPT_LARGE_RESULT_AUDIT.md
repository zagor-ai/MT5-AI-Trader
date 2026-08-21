# XAU Large Result Audit

This file is an automatically generated compact audit of the local large research JSON. The raw file is never uploaded.

## Source
- Path: `results\ranked_strategies.json`
- Size: `335.14 MB`
- SHA-256: `3eebd2e5c3abe1eee8290f62bb3166991231dbc5a9ac5344557d2d845d4ea0ba`
- Modified UTC: `2026-08-20T20:03:07.658710+00:00`
- Source Git commit: `0b06ef33556cbb40b35bb878ec83893b9197ebba`
- Strategy records: `10`

## Distribution
- OOS PF: min `0.0`, median `0.0`, max `0.0`
- OOS Net R: min `0.0`, median `0.0`, max `0.0`
- Walk-forward positive-window ratio: min `0.6666666666666666`, mean `0.6833333333333333`, max `0.8333333333333334`

## Ranking

| Rank | Strategy | Direction | Validation | WF | MC | Sensitivity | Regime | OOS PF | OOS Net R | WF Positive |
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | `SELL_EMA_RSI_ATR_0166` | SELL | 0.00 | 13.68 | 98.2 | 100.0 | 73.1 | None | None | 0.6666666666666666 |
| 2 | `SELL_EMA_RSI_ATR_0175` | SELL | 0.00 | 14.53 | 98.8 | 100.0 | 73.0 | None | None | 0.6666666666666666 |
| 3 | `SELL_EMA_RSI_ATR_0156` | SELL | 0.00 | 12.37 | 96.8 | 100.0 | 72.9 | None | None | 0.6666666666666666 |
| 4 | `SELL_EMA_RSI_ATR_0222` | SELL | 0.00 | 13.69 | 98.4 | 100.0 | 72.7 | None | None | 0.6666666666666666 |
| 5 | `SELL_EMA_RSI_ATR_0250` | SELL | 0.00 | 15.94 | 99.5 | 100.0 | 72.7 | None | None | 0.8333333333333334 |
| 6 | `SELL_EMA_RSI_ATR_0231` | SELL | 0.00 | 11.84 | 96.9 | 100.0 | 72.6 | None | None | 0.6666666666666666 |
| 7 | `SELL_EMA_RSI_ATR_0165` | SELL | 0.00 | 13.28 | 98.5 | 97.1 | 72.5 | None | None | 0.6666666666666666 |
| 8 | `SELL_EMA_RSI_ATR_0174` | SELL | 0.00 | 14.15 | 99.0 | 100.0 | 72.3 | None | None | 0.6666666666666666 |
| 9 | `SELL_EMA_RSI_ATR_0249` | SELL | 0.00 | 12.39 | 98.0 | 97.1 | 72.2 | None | None | 0.6666666666666666 |
| 10 | `SELL_EMA_RSI_ATR_0221` | SELL | 0.00 | 12.81 | 98.4 | 97.1 | 72.2 | None | None | 0.6666666666666666 |

## Audit Policy
- Full strategy definitions and ranking metrics are retained in the compact JSON.
- Trade arrays, equity curves and other bulky raw fields are removed before publication.
- The source SHA-256 lets the manager detect whether the local large file changed.
- Publishing is idempotent: an unchanged source file creates no new commit.
