# M20.11 Backtest Indicator, Signal, And Returns Artifacts

Date: 2026-05-23

## Purpose

Reduce Backtest empty-shell surface by implementing the reference-observed Indicators, Indicator Signals, and Returns Analysis workflow as local clean-room analytics derived from the same closed-candle data used by the strategy runner.

## Runtime Surface

- Backtest runs now return and persist indicator rows for each closed candle.
- Strategy signal rows are written separately from fills so the UI can inspect signal timing before next-open execution.
- Returns analysis records period counts, positive/negative periods, best/worst/average period returns, total return, max drawdown, and a returns curve.
- New local artifacts are written under `artifacts/backtests/{run_id}/`: `signals.csv`, `indicators.json`, `returns_analysis.json`, and `returns_curve.csv`.
- Backtest result tabs now include Indicators, Signals, and Returns Analysis in addition to the existing Summary/Metrics/Trades/Equity/Drawdown/Data Source/Artifacts/Raw JSON tabs.

## Safety

This milestone adds no provider, no optimizer execution, no walk-forward execution, no live deployment, no broker routing, no real order, no private API key flow, no real balance read, no margin, no leverage, no short exposure, no derivatives execution, no subscription, no billing, no CR/credits, no cloud account, no credential storage, no installed-source read, and no Fincept branding/assets/copy.

## Verification

- Focused Backtest gate `.\.venv\Scripts\python.exe -m pytest tests\test_m6_backtest.py -q` with repo-local TEMP/TMP -> 10 passed.
- Full backend gate `.\.venv\Scripts\python.exe -m pytest -q` with repo-local TEMP/TMP -> 178 passed.
- Focused source-wall/live-safety gate `.\.venv\Scripts\python.exe -m pytest tests\test_clean_room_source_wall.py tests\test_m16_live_safety.py -q` with repo-local TEMP/TMP -> 12 passed.
- Python lint `.\.venv\Scripts\python.exe -m ruff check .` -> passed.
- Frontend `npm run lint`, `npm run build`, and `npm run e2e` -> passed; Playwright reported 15 passed.
- Frontend E2E captures `artifacts/screenshots/m20-11-backtest-indicator-signals-returns.png`.
- Browser/Playwright screenshot was visually inspected for readable Backtest artifacts, Returns Analysis rows, tab layout, and no incoherent overlap.
- Changed-file credential-like string scan found no real credential, PIN, provider-key, private-key, or personal-account literal; matches were existing safety/type/redaction terms only.
- Code-review gate found no CRITICAL/HIGH/BLOCK findings. WATCH: Optimize, Walk-Forward, and broader strategy families remain deliberately gated until separate local contracts exist.
