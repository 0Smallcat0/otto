# M23.25 Backtest Run Index

Date: 2026-05-26

## Scope

M23.25 adds a read-only Backtest run index so AI Agents can inspect recent
local closed-candle research runs before deciding whether a comparison packet is
ready.

This milestone deepens Backtest workflow supervision without adding optimize,
replay, deployment, broker routing, real orders, private data, balances, margin,
leverage, short exposure, derivatives, or destructive artifact lifecycle
actions.

## Implemented Behavior

- `backtest_run_index_payload` inventories recent local `bt-*` Backtest run
  directories from summary, provenance, and manifest metadata.
- `GET /api/backtest/runs` exposes run count, skipped count, latest run,
  comparison readiness, bounded run rows, recommended next action, and explicit
  safety flags.
- `GET /api/backtest` includes the same `run_index` payload so route defaults
  already contain agent-selectable run state.
- Backtest UI adds a `Run Index` card with stable selector
  `backtest-run-index`, latest run state, comparison readiness, and recent
  strategy/run rows.
- `/api/agent-contract` advertises `backtest_run_index` and Backtest state
  `run_index`.
- Command Center provenance advances to this M23.25 milestone.

## Safety

- The index reads known local Backtest metadata and returns it in memory only.
- It does not create artifacts, rerun strategy code, optimize parameters,
  replay runs, submit orders, read private accounts, route broker/exchange
  actions, or mutate Portfolio state.
- Missing Backtest runs return an empty, read-only index with
  `comparison_ready: false` and no artifact directory creation.

## Verification

Final verification:

- `.\.venv\Scripts\python.exe -m pytest tests\test_m6_backtest.py tests\test_m21_agent_operability_contract.py tests\test_m22_command_center_contract.py -q --basetemp .omx\pytest-tmp\m23-25-focused-after-fix`
  -> 29 passed.
- `.\.venv\Scripts\python.exe -m ruff check src\local_terminal\backtest.py src\local_terminal\server.py src\local_terminal\agent_contract.py src\local_terminal\command_center.py tests\test_m6_backtest.py tests\test_m21_agent_operability_contract.py tests\test_m22_command_center_contract.py`
  -> passed.
- Focused docs/ledger gate
  `.\.venv\Scripts\python.exe -m pytest tests\test_m6_backtest.py tests\test_m21_agent_operability_contract.py tests\test_m22_command_center_contract.py tests\test_m22_mission_ledger.py -q --basetemp .omx\pytest-tmp\m23-25-docs-final`
  -> 33 passed.
- Full backend gate
  `.\.venv\Scripts\python.exe -m pytest -q --basetemp .omx\pytest-tmp\m23-25-full`
  -> 320 passed.
- Full ruff `.\.venv\Scripts\python.exe -m ruff check .` -> passed.
- Frontend `npm run lint`, `npm run build`, and `npm run e2e` in `frontend/`
  -> passed; build kept only the existing Vite chunk-size warning and E2E
  result was 15 passed.
- Source-wall/live-safety/local-secret/ledger gate
  `.\.venv\Scripts\python.exe -m pytest tests\test_clean_room_source_wall.py tests\test_m16_live_safety.py tests\test_m20_local_secret_gate.py tests\test_m22_mission_ledger.py -q --basetemp .omx\pytest-tmp\m23-25-safety`
  -> 23 passed.
- FastAPI TestClient smoke confirmed two local Backtest runs, read-only run
  index readiness, embedded `/api/backtest` run index, Command Center current
  milestone, AI Agent action contract, and no local secret-store creation.
- Changed-diff secret scan found no personal-account email literals,
  password/PIN literals, provider-key assignments, bearer-token values,
  private-key blocks, protected-value payload assignments, or credential
  assignments; the only match was a safety assertion that
  `settings/local_secrets.json` does not exist.
- `git diff --check` passed with Git CRLF working-copy warnings only.

## Handoff

Future Backtest work can add richer filters or Portfolio-facing run selection,
but optimize, replay, live deploy, broker routing, real orders, and destructive
artifact lifecycle actions still require separate reviewed safety contracts.
