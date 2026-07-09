# M23.32 Backtest Volatility Reversion

Date: 2026-05-26

## Scope

M23.32 deepens Backtest and Algo strategy breadth with one additional local
closed-candle strategy family. The slice extends the existing Backtest strategy
catalog; it does not introduce an optimizer, deployment flow, broker route,
provider key, or live trading path.

Strategy contract:

- Strategy id: `volatility_reversion`.
- Strategy label: `Volatility Reversion`.
- Engine: `local_volatility_reversion_v1`.
- Runtime role: local research-only Backtest strategy.
- Fill model: long/flat positions with next-open fills after closed-candle
  signals.
- Parameter schema: `fast_window` as `Exit SMA`, `slow_window` as
  `Band Window`, with the existing `slow_window > fast_window` constraint.

Out of scope:

- Optimize, live deployment, broker/exchange binding, real orders, real
  balances, margin, leverage, short exposure, derivatives, payment,
  subscription, CR/credits, cloud sync, provider signup, credential storage,
  Fincept branding/assets/commercial copy, runtime binaries, installed-source
  reads, or destructive artifact lifecycle actions.

## Product Behavior

- The Backtest catalog includes `volatility_reversion` beside `sma_cross`,
  `channel_breakout`, and `sma_mean_reversion`.
- The strategy buys when the current closed candle pulls below the rolling
  volatility band and exits when price recovers above the exit SMA.
- Backtest artifacts record the new engine id, strategy label, schema,
  constraints, provenance, signals, trades, indicators, returns curve, and
  returns analysis.
- Indicators include `exit_sma`, `band_mid`, `lower_band`, `upper_band`, and
  `lower_band_distance_pct`.
- Algo saved strategies can set `backtest.strategy=volatility_reversion` and
  run the existing `/api/algo/run-backtest` handoff without adding execution or
  deployment behavior.
- The frontend fallback strategy catalog and Playwright workflow expose the new
  strategy and indicator columns.
- Command Center current milestone provenance points to this document.

## Verification

- Focused ruff:
  `.\.venv\Scripts\python.exe -m ruff check src\local_terminal\backtest.py src\local_terminal\command_center.py tests\test_m6_backtest.py tests\test_m10_algo.py tests\test_m22_command_center_contract.py tests\test_m22_mission_ledger.py`
  -> passed.
- Focused Backtest/Algo/Command Center/docs gate:
  `.\.venv\Scripts\python.exe -m pytest tests\test_m6_backtest.py tests\test_m10_algo.py tests\test_m22_command_center_contract.py tests\test_m22_mission_ledger.py -q --basetemp .omx\pytest-tmp\m23-32-focused`
  with repo-local TEMP/TMP -> 52 passed.
- Full backend gate:
  `.\.venv\Scripts\python.exe -m pytest -q --basetemp .omx\pytest-tmp\m23-32-full-final-rerun`
  with repo-local TEMP/TMP -> 328 passed.
- Full ruff:
  `.\.venv\Scripts\python.exe -m ruff check .` -> passed.
- Frontend:
  `npm run lint`, `npm run build`, and `npm run e2e` in `frontend/` -> passed;
  build kept only the existing Vite chunk-size warning and E2E result was
  15 passed after tightening the new `lower_band` header assertion to exact
  matching.
- Source-wall/live-safety/local-secret/ledger gate:
  `.\.venv\Scripts\python.exe -m pytest tests\test_clean_room_source_wall.py tests\test_m16_live_safety.py tests\test_m20_local_secret_gate.py tests\test_m22_mission_ledger.py -q --basetemp .omx\pytest-tmp\m23-32-safety`
  with repo-local TEMP/TMP -> 23 passed.
- FastAPI TestClient smoke confirmed `/api/backtest` exposes
  `volatility_reversion`, `/api/backtest/run` and `/api/algo/run-backtest`
  both write `local_volatility_reversion_v1`, `/api/command-center` returns
  `M23.32 Backtest volatility reversion`, and no local secret-store directory
  is created.
- Changed-diff secret scan found only historical verification text and
  pre-existing negative secret-blocking test fixtures; no credential values,
  provider-key assignments, bearer-token values, personal credential literals,
  PIN assignments, or private-key blocks were added.
- `git diff --check` passed with Git CRLF working-copy warnings only.

## Handoff

Future Backtest strategy additions should stay closed-candle, long/flat, and
next-open-fill until a separate reviewed safety contract exists. Do not treat
this catalog breadth as optimizer parity, deployable strategy execution, broker
routing, short exposure, derivatives execution, or live trading capability.
