# M23.63 Backtest RSI Reversion

## Scope

M23.63 expands the local Backtest/Algo research catalog with one additional
closed-candle strategy family: `rsi_reversion`.

This is a bounded research-output slice. It does not add optimizer behavior,
deployment, broker/exchange routing, real orders, real balances, short exposure,
derivatives, credentials, provider calls, or live/private behavior.

## Product Delta

- Adds `RSI Reversion` to the backend-owned Backtest strategy catalog.
- Runs a long/flat RSI mean-reversion strategy using candle-close signals and
  next-open fills through the existing local Backtest artifact writer.
- Persists the existing `config.json`, `data_snapshot.json`, `summary.json`,
  `trades.csv`, `signals.csv`, `indicators.json`, `returns_analysis.json`,
  `returns_curve.csv`, `provenance.json`, `report.md`, and `manifest.json`
  contract with engine `local_rsi_reversion_v1`.
- Adds indicator rows for `exit_sma`, `rsi`, `rsi_entry_threshold`,
  `rsi_exit_threshold`, and `rsi_distance`.
- Exposes the strategy through Algo saved-strategy backtest handoff and the
  frontend fallback strategy schema.
- Moves Command Center provenance to this milestone so AI Agents can see the
  current resume point without reopening prior completed surfaces.

## Safety Contract

- Positioning remains long/flat only.
- Signals are generated on candle close and filled at the next candle open.
- Same-candle fills remain false.
- No optimization, walk-forward fitting, deployment, live order, broker routing,
  real balance read, margin, leverage, short exposure, derivatives execution,
  credential access, provider refresh, or destructive artifact lifecycle action
  is enabled.

## Verification Evidence

- Focused RSI smoke
  `.\.venv\Scripts\python.exe -m pytest -q tests\test_m6_backtest.py::test_rsi_reversion_strategy_writes_artifacts tests\test_m6_backtest.py::test_rsi_reversion_rejects_open_candles_and_prevents_same_candle_fills tests\test_m10_algo.py::test_algo_runs_rsi_reversion_backtest_from_saved_strategy --basetemp .omx\pytest-tmp\m23-63-rsi-focused-rerun`
  -> 3 passed after fixing the RSI rolling-window helper.
- Focused Backtest/Algo/Command Center/ledger gate
  `.\.venv\Scripts\python.exe -m pytest -q tests\test_m6_backtest.py tests\test_m10_algo.py tests\test_m22_command_center_contract.py tests\test_m22_mission_ledger.py --basetemp .omx\pytest-tmp\m23-63-focused-rerun`
  -> 64 passed.
- Agent operability contract gate
  `.\.venv\Scripts\python.exe -m pytest -q tests\test_m21_agent_operability_contract.py --basetemp .omx\pytest-tmp\m23-63-agent-contract`
  -> 5 passed.
- Full backend
  `.\.venv\Scripts\python.exe -m pytest -q --basetemp .omx\pytest-tmp\m23-63-full`
  -> 379 passed.
- Ruff `.\.venv\Scripts\python.exe -m ruff check .` -> passed.
- Frontend `npm run lint` -> passed.
- Frontend `npm run build` -> passed with the existing Vite chunk-size
  warning.
- Focused Backtest E2E
  `npm run e2e -- --grep "runs closed-candle backtest"` -> 1 passed after
  tightening the RSI column assertion to exact matching.
- Frontend full E2E `npm run e2e` -> 15 passed after updating stale M23.62
  milestone assertions in shell, drawer, and dashboard Command Center checks.
- Source-wall/live-safety/local-secret/provider gate
  `.\.venv\Scripts\python.exe -m pytest -q tests\test_clean_room_source_wall.py tests\test_m16_live_safety.py tests\test_m20_local_secret_gate.py tests\test_m22_provider_acquisition_gate.py --basetemp .omx\pytest-tmp\m23-63-safety`
  -> 22 passed.
- FastAPI smoke confirmed Backtest strategy count `6`, `rsi_reversion`
  present, artifact engine `local_rsi_reversion_v1`, indicator keys
  `exit_sma,rsi,rsi_distance,rsi_entry_threshold,rsi_exit_threshold`,
  same-candle fills false, strategy live orders false, strategy broker routing
  false, Command Center milestone `M23.63 Backtest RSI reversion`, milestone
  path `docs/planning/M23_BACKTEST_RSI_REVERSION.md`, action count `73`,
  preflight rows `73`, and no local secret-store file was created.
- Added-line credential scan found zero high-risk value matches.
- `git diff --check` -> passed with Git CRLF working-copy warnings only.
