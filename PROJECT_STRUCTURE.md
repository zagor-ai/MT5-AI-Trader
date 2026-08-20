# XAU Strategy Researcher Pro — Project Structure

Branch: `xau-researcher-v2.1.1-clean`

## Runtime entry points

- `XAU_Strategy_Researcher_Pro_v2.1.py` — legacy/compatibility entry point
- `app.py` — modular application entry point
- `Run_XAU_Strategy_Researcher_Pro_v2.1.bat` — Windows launcher

## GUI

- `gui/main_window.py` — main desktop window and orchestration
- `gui/status_panel.py` — MT5/application status panel
- `gui/progress.py` — progress state and progress widgets
- `gui/log_panel.py` — copyable application log
- `gui/controls.py` — GUI controls/buttons

## Core research engine

- `core/research_engine.py` — research orchestration
- `core/research_pipeline.py` — single-candidate evaluation pipeline
- `core/strategy_generator.py` — StrategySpec generation
- `core/strategy_families.py` — constrained strategy families
- `core/strategy_adapter.py` — Candidate → StrategySpec adapter
- `core/signal_engine.py` — deterministic signal generation
- `core/backtester.py` — read-only historical backtest
- `core/ranking.py` — strategy ranking
- `core/metrics.py` — metrics
- `core/risk_manager.py` — risk calculations

## Indicators

- `core/indicators/technical.py` — technical indicators
- `core/indicators/price_action.py` — price-action features

## Validation

- `core/validation/train_test.py` — chronological train/test split
- `core/validation/oos.py` — OOS evaluation
- `core/validation/validator.py` — validation/overfitting score
- `core/validation/walk_forward.py` — rolling walk-forward engine
- `core/validation/walk_forward_score.py` — walk-forward robustness score

## Researcher / MT5 services

- `researcher/config.py` — researcher configuration
- `researcher/data_loader.py` — historical data loading
- `researcher/mt5_connector.py` — MT5 connection/data interface
- `researcher/indicators.py` — researcher indicator utilities
- `researcher/metrics.py` — researcher metrics
- `researcher/logger.py` — logging utilities
- `researcher/utils.py` — utilities
- `services/mt5_connector.py` — service-level MT5 connector

## Additional validation modules

- `validation/train_test.py`
- `validation/out_of_sample.py`
- `validation/walk_forward.py`
- `validation/monte_carlo.py`
- `validation/parameter_sensitivity.py`
- `validation/regime_detection.py`
- `validation/robustness.py`
- `validation/validation_report.py`

## Exporters

- `exporters/__init__.py`

## Automation

- `.github/workflows/build-xau-researcher-v2-1-1.yml` — GitHub Actions build workflow

## Documentation

- `README.md`
- `V2.2_MODULAR_ARCHITECTURE.md`
- `PROJECT_STRUCTURE.md`

## Design rule

The researcher is strictly read-only with respect to MetaTrader 5. It may initialize the terminal, inspect account/symbol information and retrieve historical data, but it must never submit, modify or close live orders.

## Intended research flow

MT5 → Historical Data → Strategy Families → Candidates → Signal Engine → Backtest → Train/Test → OOS → Walk Forward → Robustness/Ranking → Export Strategy → Future MQL5 EA generation.
