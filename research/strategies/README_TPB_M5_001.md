# TPB-M5-001 — Trend Pullback + Structure Break

Research-only XAUUSD M5 strategy.

## Base hypothesis

`H4/H1 trend alignment -> M5 impulse -> pullback -> confirmed swing -> closed-candle BOS -> next-bar entry -> swing/ATR SL -> fixed 2R TP`

## Rules

- Symbol: `XAUUSD`
- Execution timeframe: `M5`
- HTF: `H1`, `H4`
- EMA trend: 20/50/200
- Confirmed pivot: 2 bars left + 2 bars right
- Impulse: at least 1.0 ATR(14)
- Pullback: 25% to 78.6%
- BOS: closed M5 candle beyond the pullback swing by at least 0.05 ATR
- Entry: next M5 bar open
- SL: pullback swing +/- 0.15 ATR
- SL distance: 0.50 to 2.00 ATR
- TP: 2R
- Max holding period: 72 M5 bars

## Look-ahead protection

A pivot becomes usable only after the right-side confirmation bars have closed. The engine never uses an unconfirmed future swing as a signal.

## Safety

The engine does not send trading orders. It only reads MT5 market data and writes research evidence.

## First experiment

Do **not** optimize parameters yet. Establish whether the base structural hypothesis has positive out-of-sample expectancy before adding RSI, ADX, MACD, news filters, or other features.

## Local run

From the repository root:

```text
python research/strategies/TPB_M5_001.py
```

Requirements:

```text
pip install MetaTrader5 pandas numpy
```

MetaTrader 5 must be running and the `XAUUSD` symbol must be available.
