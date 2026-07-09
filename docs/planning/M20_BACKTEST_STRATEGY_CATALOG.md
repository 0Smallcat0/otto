# M20.8 Backtest Strategy Catalog

Date: 2026-05-23

## Purpose

Increase Backtest route depth beyond a single SMA runner by adding a small local strategy catalog and a second closed-candle strategy. This keeps the route aligned with the M19 anti-empty-shell plan without adding external runtime, broker routing, private keys, or live execution.

## Runtime Surface

- Backend catalog: `backtest_strategy_catalog()` originally exposed `sma_cross`
  and `channel_breakout`; M23.15 extends the same contract with
  `sma_mean_reversion`.
- API defaults: `/api/backtest` now returns `strategies` and default `config.strategy`.
- Run API: `/api/backtest/run` accepts `strategy` and rejects unsupported values before artifacts are written.
- UI: Backtest shows a Strategy Catalog panel, a Strategy selector, strategy-specific parameter labels, and the selected strategy in summary output.

## Strategy Contract

- `sma_cross`: existing long/flat SMA crossover using candle close signals and next-open fills.
- `channel_breakout`: long/flat channel breakout using prior-channel highs for entry and prior-channel lows for exit.
- `sma_mean_reversion`: M23.15 long/flat pullback strategy using prior mean
  entries and recovery exits.
- All catalog strategies:
  - require closed candles
  - forbid same-candle fills
  - never short
  - never submit real orders
  - write local artifacts under `artifacts/backtests/{run_id}/`
  - record strategy id, label, engine id, provider, source, cache hash, and provenance

## Safety

This milestone adds no live trading, broker integration, private API flow, real balance read, margin, leverage, short exposure, derivatives execution, subscription, billing, CR/credits, cloud account, credential form, key persistence, installed-source read, or Fincept asset/branding use.

## Verification

- Focused Backtest tests cover catalog defaults, channel breakout artifacts, unsupported strategy rejection, open-candle rejection, and no same-candle fills.
- Frontend E2E selects Channel Breakout, runs a backtest, verifies artifacts/provenance, and captures `artifacts/screenshots/m20-8-backtest-strategy-catalog.png`.
- `.\.venv\Scripts\python.exe -m pytest tests\test_m6_backtest.py -q` with repo-local TEMP/TMP -> 8 passed.
- `.\.venv\Scripts\python.exe -m pytest tests\test_clean_room_source_wall.py tests\test_m16_live_safety.py -q` with repo-local TEMP/TMP -> 12 passed.
- Full gate: `.\.venv\Scripts\python.exe -m pytest -q` -> 171 passed; `.\.venv\Scripts\python.exe -m ruff check .` -> passed; `npm run lint`, `npm run build`, `npm run e2e` -> passed; `git diff --check` -> passed with Git CRLF working-copy warnings only.
- Code-review gate -> pass, no CRITICAL/HIGH/BLOCK findings.
