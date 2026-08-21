# XAU Large Result Audit

Automatically generated compact audit of the local large research JSON. The raw file is never uploaded.

## Source
- Path: `results\ranked_strategies.json`
- Size: `335.14 MB`
- SHA-256: `3eebd2e5c3abe1eee8290f62bb3166991231dbc5a9ac5344557d2d845d4ea0ba`
- Modified UTC: `2026-08-20T20:03:07.658710+00:00`
- Source Git commit: `f7455ccfa43482ac3d708510367f12a1ee957a4f`
- Strategy records: `10`

## Report Quality
- Status: **WARNING**
- OOS policy: `prefer final test metrics; otherwise use Walk-Forward OOS aggregates; never convert missing values to zero`
- ⚠ Base TRAIN/TEST OOS metrics unavailable for 10/10 ranked strategies; Walk-Forward OOS aggregates were used instead.
- ⚠ Validation score is unavailable for 10/10 ranked strategies in the final export.

## Distribution
- OOS PF: min `1.0685872333659532`, median `1.0784919909842092`, max `1.121562299889794`
- OOS Net R: min `91.08894374797805`, median `112.43285939324383`, max `139.63285939324462`
- Walk-forward positive-window ratio: min `0.6666666666666666`, mean `0.6833333333333333`, max `0.8333333333333334`

## Ranking

| Rank | Strategy | Dir | Validation | WF | MC | Sensitivity | Regime | OOS Source | OOS PF | OOS Net R | WF Positive |
|---:|---|:---:|---:|---:|---:|---:|---:|---|---:|---:|---:|
| 1 | `SELL_EMA_RSI_ATR_0166` | SELL | N/A | 13.68 | 98.2 | 100.0 | 73.1 | `walk_forward` | 1.09 | 114.83 | 0.667 |
| 2 | `SELL_EMA_RSI_ATR_0175` | SELL | N/A | 14.53 | 98.8 | 100.0 | 73.0 | `walk_forward` | 1.10 | 125.83 | 0.667 |
| 3 | `SELL_EMA_RSI_ATR_0156` | SELL | N/A | 12.37 | 96.8 | 100.0 | 72.9 | `walk_forward` | 1.07 | 98.09 | 0.667 |
| 4 | `SELL_EMA_RSI_ATR_0222` | SELL | N/A | 13.69 | 98.4 | 100.0 | 72.7 | `walk_forward` | 1.10 | 114.83 | 0.667 |
| 5 | `SELL_EMA_RSI_ATR_0250` | SELL | N/A | 15.94 | 99.5 | 100.0 | 72.7 | `walk_forward` | 1.12 | 139.63 | 0.833 |
| 6 | `SELL_EMA_RSI_ATR_0231` | SELL | N/A | 11.84 | 96.9 | 100.0 | 72.6 | `walk_forward` | 1.07 | 91.09 | 0.667 |
| 7 | `SELL_EMA_RSI_ATR_0165` | SELL | N/A | 13.28 | 98.5 | 97.1 | 72.5 | `walk_forward` | 1.08 | 110.03 | 0.667 |
| 8 | `SELL_EMA_RSI_ATR_0174` | SELL | N/A | 14.15 | 99.0 | 100.0 | 72.3 | `walk_forward` | 1.08 | 121.53 | 0.667 |
| 9 | `SELL_EMA_RSI_ATR_0249` | SELL | N/A | 12.39 | 98.0 | 97.1 | 72.2 | `walk_forward` | 1.07 | 98.53 | 0.667 |
| 10 | `SELL_EMA_RSI_ATR_0221` | SELL | N/A | 12.81 | 98.4 | 97.1 | 72.2 | `walk_forward` | 1.07 | 104.03 | 0.667 |

## Best Strategy Evidence
- Strategy: `SELL_EMA_RSI_ATR_0166`
- OOS source: `walk_forward`
- Walk-Forward: `4/6` positive windows
- OOS Net R: `114.83285939324415`
- OOS PF: `1.0946467287925543`

## Audit Policy
- Full strategy definitions and ranking metrics are retained in the compact JSON.
- Trade arrays, equity curves and other bulky raw fields are removed before publication.
- Missing metrics remain `null`/`N/A`; they are never silently converted to zero.
- When final TRAIN/TEST OOS metrics are absent, Walk-Forward OOS aggregates are used and the report explicitly warns about it.
- The source SHA-256 lets the manager detect whether the local large file changed.
- Publishing is idempotent: an unchanged source file creates no new commit.
