# M23.40 Algo Scan Readiness

## Scope

M23.40 adds a read-only Algo scan readiness contract so an AI Agent can inspect
whether the scanner has an active strategy, useful provider/cache rows, latest
scan artifact health, and Backtest handoff seed state before running local scan
or backtest actions.

This milestone does not run Algo scans, refresh providers, write scan artifacts,
repair artifacts automatically, optimize/deploy strategies, route broker or
exchange orders, read balances, access credentials, or enable live/private
behavior.

## Product Behavior

- `GET /api/algo/scan-readiness` returns `algo_scan_readiness_v1`.
- `GET /api/algo` embeds the same payload as `scan_readiness`.
- The payload reports active strategy readiness, default scan symbols, current
  provider/cache state, source-row counts, per-symbol expected signal state,
  latest scan summary, scan artifact health, Backtest handoff readiness, and
  safe recommended actions.
- The Algo UI exposes selector `algo-scan-readiness`.
- The AI Agent contract exposes state field `scan_readiness` and action
  `algo_scan_readiness`.
- Command Center current milestone points to this document.

## Safety Contract

- Read-only and metadata-only.
- No scan execution and no provider refresh are performed.
- No Algo scan artifact directory or local secret store is created.
- Recommendations distinguish safe action availability from useful current data;
  no recommendation authorizes live deployment or broker routing.
- Live orders, broker routing, real balances, margin, leverage, short exposure,
  and derivatives remain disabled.

## Verification

- Focused Algo/agent/Command Center gate:
  `.\.venv\Scripts\python.exe -m pytest tests\test_m10_algo.py tests\test_m21_agent_operability_contract.py tests\test_m22_command_center_contract.py -q --basetemp .omx\pytest-tmp\m23-40-focused-initial`
  -> 31 passed.
- Focused ruff:
  `.\.venv\Scripts\python.exe -m ruff check src\local_terminal\algo.py src\local_terminal\server.py src\local_terminal\agent_contract.py src\local_terminal\command_center.py tests\test_m10_algo.py tests\test_m21_agent_operability_contract.py tests\test_m22_command_center_contract.py`
  -> passed.
- Frontend build:
  `npm run build` in `frontend/` -> passed with the existing Vite chunk-size
  warning.
- Frontend lint:
  `npm run lint` in `frontend/` -> passed.
- Frontend E2E:
  `npm run e2e` in `frontend/` -> 15 passed after updating stale M23.39 shell
  milestone/action-count assertions to M23.40 / 60 actions.
- Source-wall/live-safety/local-secret/ledger gate:
  `.\.venv\Scripts\python.exe -m pytest tests\test_clean_room_source_wall.py tests\test_m16_live_safety.py tests\test_m20_local_secret_gate.py tests\test_m22_mission_ledger.py -q --basetemp .omx\pytest-tmp\m23-40-safety-rerun`
  -> 23 passed. The first attempt was invalidated by a concurrent Playwright
  `frontend/test-results` file race and was rerun sequentially.
- Docs/ledger gate:
  `.\.venv\Scripts\python.exe -m pytest tests\test_m10_algo.py tests\test_m21_agent_operability_contract.py tests\test_m22_command_center_contract.py tests\test_m22_mission_ledger.py -q --basetemp .omx\pytest-tmp\m23-40-docs`
  -> 35 passed.
- Full backend gate:
  `.\.venv\Scripts\python.exe -m pytest -q --basetemp .omx\pytest-tmp\m23-40-full`
  -> 345 passed.
- Full ruff:
  `.\.venv\Scripts\python.exe -m ruff check .` -> passed.
- Local smoke/browser:
  backend health and frontend root returned 200; `/api/algo/scan-readiness`
  returned `algo_scan_readiness_v1`; in-app browser verified the Algo route
  selector `algo-scan-readiness`, `WRITES false`, `REFRESH false`, and shell
  milestone `M23.40 Algo scan readiness`.

## Resume Rule

Do not redo Algo strategy save/select, signal-only scanner artifacts, scan
artifact repair, Backtest strategy handoff, or Backtest data readiness. Resume
by selecting another concrete residual partial from
`docs/planning/M22_FINAL_NON_LIVE_PARITY_AUDIT.md`; provider work still requires
fresh official-doc provider-entry research before another adapter.
