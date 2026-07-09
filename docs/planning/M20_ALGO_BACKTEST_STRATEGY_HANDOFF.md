# M20.9 Algo Backtest Strategy Handoff

Date: 2026-05-23

## Purpose

Connect Algo strategy definitions to the Backtest strategy catalog so "Run backtest from strategy" carries a real local strategy engine choice into the Backtest artifact set. This reduces route-shell behavior by making Algo Builder state drive Backtest execution, rather than always using the default runner.

## Runtime Surface

- Algo payload now exposes `backtest_strategies` from the Backtest catalog.
- Algo strategy `backtest` settings include a validated `strategy` field.
- `/api/algo/strategy` rejects unsupported backtest strategy ids before writing Algo or Backtest artifacts.
- `/api/algo/run-backtest` passes the saved strategy choice into `/api/backtest` execution and rejects mismatched runtime strategy overrides.
- Algo `last_backtest` and `backtest_result.strategy_definition` record the selected Backtest strategy id and label.
- Algo UI adds a Backtest Strategy selector and strategy-specific parameter labels.

## Safety

Algo remains local signal-only. This milestone adds no live deployment, broker routing, real order, private API key flow, real balance read, margin, leverage, short exposure, derivatives execution, subscription, billing, CR/credits, cloud account, credential storage, installed-source read, or Fincept branding/assets/copy.

## Verification

- Focused gate `.\.venv\Scripts\python.exe -m pytest tests\test_m10_algo.py tests\test_m6_backtest.py tests\test_clean_room_source_wall.py tests\test_m16_live_safety.py -q` with repo-local TEMP/TMP -> 32 passed.
- Full backend gate `.\.venv\Scripts\python.exe -m pytest -q` with repo-local TEMP/TMP -> 174 passed.
- Python lint `.\.venv\Scripts\python.exe -m ruff check .` -> passed.
- Python formatting check `.\.venv\Scripts\python.exe -m ruff format --check src\local_terminal\algo.py tests\test_m10_algo.py` -> passed.
- Frontend `npm run lint`, `npm run build`, and `npm run e2e` -> passed; Playwright reported 15 passed.
- Frontend E2E selects Channel Breakout in Algo, saves the strategy, runs Backtest, verifies artifacts, runs Scanner dry-run, and captures `artifacts/screenshots/m20-9-algo-backtest-strategy-handoff.png`.
- Changed-file credential-like string scan found no real credential, PIN, provider-key, private-key, or personal-account literal; matches were existing safety/type/redaction terms only.
- Code-review gate: no CRITICAL/HIGH/BLOCK findings after fixing the saved-strategy override mismatch. Architecture WATCH: before adding a third Backtest strategy family, promote catalog metadata into a parameter schema so Algo and Backtest do not keep growing around two hard-coded window fields.
