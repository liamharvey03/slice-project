# Slice Phase 3 – Quant Engine (Dev A)

## Purpose of Phase 3
- Add a minimal quant engine on top of the Phase 2 Postgres data layer, enabling backtests driven by previously backfilled price and econ data.

## Components Delivered in Phase 3
- StrategyBase abstraction for Backtrader strategies with weight-based portfolio logic.
- Backtrader Cerebro wrapper (`build_cerebro`, `run_cerebro`) to spin up engines with standard analyzers.
- Example macro strategies: `gold_real_yields`, `usd_divergence`, `curve_steepener`.
- Data loaders for econ (`load_econ_series`) and price (`load_price_data`) backed by `econ_data` and `market_data`.
- `SlicePandasData` feed mapping to align pandas OHLCV frames with Backtrader.
- `run_backtest()` interface returning JSON suitable for LLM / API consumption.

## Expected Developer Surface (Dev A)
- Strategies receive data via `symbols` feeds added to Cerebro and econ series loaded through the data loaders.
- Required params include `tickers` (for price data) and strategy-specific fields (e.g., `price_symbol`, series ids, window lengths, target weights).
- `compute_target_weights()` returns `{symbol: weight}` for each bar; weights are converted to orders via `order_target_percent` inside `StrategyBase.next()`.
- `run_backtest()` resolves a strategy id, loads price data from Postgres, runs Cerebro, and returns:
  - `metrics`: `total_return`, `sharpe`, `max_drawdown`, `max_drawdown_len`
  - `returns`: dated return series
  - `orders`, `trades`: executed logs
  - `period`: start/end dates of the backtest
  - `params`, `strategy_id`, `tickers`

## How to Run Tests
```bash
export SLICE_DB_URL="postgresql+psycopg2://slice_user:slice_password@localhost:5432/slice"
PYTHONPATH=src python3 scripts/test_run_backtest_full.py
PYTHONPATH=src python3 scripts/test_run_backtest_gold_real_yields.py
PYTHONPATH=src python3 scripts/test_run_backtest_usd_divergence.py
PYTHONPATH=src python3 scripts/test_run_backtest_curve_steepener.py
```

## Statement of Completion
- Phase 3 quant engine is complete and working with real backfilled data.
