# M23.46 Command Center Action Matrix

Date: 2026-05-26

## Scope

Deepen the command-center-first supervision surface for AI Agent operation
without executing any local action.

This slice exposes existing `/api/agent-contract` action rows through
`GET /api/command-center` and the Settings Command Center UI. It is a
read-only action inventory for human supervision and AI preflight routing.

## Implemented

- Added `route_action_contract.actions[]` to `/api/command-center`.
- Added action-matrix summary counts for local mutations, local artifact
  writers, and confirmation-required actions.
- Added per-action `preflight_endpoint` rows derived from the existing
  `/api/agent-actions/{action_id}/preflight` contract.
- Added Command Center UI selector `command-center-action-matrix`.
- Updated frontend Command Center types and Playwright assertions.
- Updated Command Center current milestone provenance to this handoff.

## Safety

- No action execution.
- No request body logging.
- No provider signup, credential capture, secret read, external fetch, artifact
  content read, destructive recovery, broker/exchange binding, real balance
  read, order submission, or live/private behavior.
- Action rows are generated from existing contract metadata.

## Verification

- Focused Command Center/Agent gate
  `.\.venv\Scripts\python.exe -m pytest tests\test_m22_command_center_contract.py tests\test_m21_agent_operability_contract.py -q --basetemp .omx\pytest-tmp\m23-46-focused-initial`
  -> 7 passed.
- Focused ruff
  `.\.venv\Scripts\python.exe -m ruff check src\local_terminal\command_center.py tests\test_m22_command_center_contract.py`
  -> passed.
- Frontend `npm run lint` -> passed.
- Focused Command Center/Agent/docs gate
  `.\.venv\Scripts\python.exe -m pytest tests\test_m22_command_center_contract.py tests\test_m21_agent_operability_contract.py tests\test_m22_mission_ledger.py -q --basetemp .omx\pytest-tmp\m23-46-docs-initial`
  -> 11 passed.
- Frontend `npm run build` -> passed with the existing Vite chunk-size warning.
- Command Center Playwright rerun
  `npm run e2e -- --grep "opens all routes"` -> 1 passed.
- Source-wall/live-safety/local-secret/Command Center/Agent gate
  `.\.venv\Scripts\python.exe -m pytest tests\test_clean_room_source_wall.py tests\test_m16_live_safety.py tests\test_m20_local_secret_gate.py tests\test_m22_mission_ledger.py tests\test_m22_command_center_contract.py tests\test_m21_agent_operability_contract.py -q --basetemp .omx\pytest-tmp\m23-46-safety`
  -> 30 passed.
- Full backend gate
  `.\.venv\Scripts\python.exe -m pytest -q --basetemp .omx\pytest-tmp\m23-46-full`
  -> 350 passed.
- Full ruff `.\.venv\Scripts\python.exe -m ruff check .` -> passed.
- Frontend `npm run e2e` -> 15 passed.
- FastAPI TestClient smoke confirmed Command Center milestone
  `M23.46 Command Center action matrix`, milestone path
  `docs/planning/M23_COMMAND_CENTER_ACTION_MATRIX.md`, action count `61`,
  matrix rows `61`, artifact writer count `39`, local mutation count `42`,
  per-action preflight endpoints for `markets_refresh_public` and
  `portfolio_report`, `provider_acquisition_gate_inspect.method=GET`,
  `action_executed=false`, `live_trading=false`, and
  `secret_values_returned=false`.
- Final ledger docs gate
  `.\.venv\Scripts\python.exe -m pytest tests\test_m22_mission_ledger.py -q --basetemp .omx\pytest-tmp\m23-46-ledger-final`
  -> 4 passed.
- Exact personal-account/password/PIN scan found no literal matches for the
  provided Gmail, password, or PIN. Broader changed-file secret scan found only
  historical verification text, negative response assertions, and the existing
  Portfolio denylist term `private_key`; no credential values were added.
- `git diff --check` passed with Git CRLF working-copy warnings only.

## Resume Note

Continue one residual partial at a time. Do not treat action-matrix visibility
as action execution, confirmation, provider approval, recovery authorization,
or live/private readiness.
