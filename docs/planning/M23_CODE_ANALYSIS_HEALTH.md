# M23.57 Code Analysis Health Matrix

## Scope

M23.57 deepens Code AI Agent operability by adding a metadata-only analysis
health matrix for stored local notebooks and static-analysis artifacts.

This slice does not execute notebooks, start kernels, return notebook source,
read artifact contents, index artifact text, repair files, call providers,
store credentials, route broker actions, or enable live/private behavior.

## Product Delta

- `GET /api/code/analysis-health` returns local notebook artifact metadata:
  notebook, analysis JSON, report, and manifest file presence, byte size, and
  timestamps.
- `GET /api/code` and Code mutation responses embed the same `analysis_health`
  contract so the route is self-describing for AI Agent navigation.
- The Code UI exposes `code-analysis-health` for human supervision of AI Agent
  activity.
- The AI Agent contract exposes `code_analysis_health` as a read-only action.
- Command Center provenance moves to this milestone and action count increases
  to `71`.

## Safety Contract

- Metadata-only file stat checks; no notebook source, report text, JSON artifact
  body, or manifest body is returned by the health endpoint.
- No notebook execution, kernel process, provider calls, secret access,
  automatic repair, destructive lifecycle action, broker mutation, real balance,
  real order, or live trading.
- Recovery queue entries point to the existing local static-analysis action
  only; they do not mutate state by themselves.

## Verification Plan

- Focused backend
  `.\.venv\Scripts\python.exe -m pytest -q tests\test_m12_code_workspace.py tests\test_m21_agent_operability_contract.py tests\test_m22_command_center_contract.py tests\test_m22_mission_ledger.py --basetemp .omx\pytest-tmp\m23-57-focused`
  -> 22 passed.
- Full backend
  `.\.venv\Scripts\python.exe -m pytest -q --basetemp .omx\pytest-tmp\m23-57-full`
  -> 373 passed.
- Ruff `.\.venv\Scripts\python.exe -m ruff check .` -> passed.
- Frontend `npm run lint` -> passed.
- Frontend `npm run build` -> passed with the existing Vite chunk-size warning.
- Frontend focused Code E2E
  `npm run e2e -- --grep "edits local code notebook"` -> 1 passed.
- Frontend full E2E final rerun `npm run e2e` -> 15 passed.
- Source-wall/live-safety/local-secret/mission-ledger safety gate
  `.\.venv\Scripts\python.exe -m pytest -q tests\test_clean_room_source_wall.py tests\test_m16_live_safety.py tests\test_m20_local_secret_gate.py tests\test_m22_mission_ledger.py --basetemp .omx\pytest-tmp\m23-57-safety`
  -> 23 passed.
- FastAPI smoke must confirm `metadata_only_code_analysis_health`, notebook
  count `1`, complete count `1`, embedded health parity, Command Center action
  count `71`, preflight rows `71`, and no local secret-store creation -> passed.
- Changed-diff secret scan -> passed.
- `git diff --check` -> passed with Git CRLF working-copy warnings only.
