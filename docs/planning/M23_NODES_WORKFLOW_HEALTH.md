# M23.56 Nodes Workflow Health Matrix

## Scope

M23.56 deepens Nodes AI Agent operability by adding a metadata-only workflow
health matrix for stored workflow definitions and local dry-run artifacts.

This slice does not execute workflows, read artifact contents, repair files,
call providers, store credentials, route broker actions, or enable live/private
behavior.

## Product Delta

- `GET /api/nodes/workflow-health` returns local workflow artifact metadata:
  definition, dry-run JSON, report, and manifest file presence, byte size, and
  timestamps.
- `GET /api/nodes` embeds the same `workflow_health` contract so the route is
  self-describing for AI Agent navigation.
- The Nodes UI exposes `nodes-workflow-health` for human supervision of AI
  Agent activity.
- The AI Agent contract exposes `nodes_workflow_health` as a read-only action.
- Command Center provenance moves to this milestone and action count increases
  to `70`.

## Safety Contract

- Metadata-only file stat checks; no report or JSON artifact content is read.
- No workflow execution, deploy, execute, provider calls, secret access,
  automatic repair, destructive lifecycle action, broker mutation, real balance,
  real order, or live trading.
- Recovery queue entries point to the existing local dry-run action only; they
  do not mutate state by themselves.

## Verification Plan

- Focused backend
  `.\.venv\Scripts\python.exe -m pytest -q tests\test_m11_nodes.py tests\test_m21_agent_operability_contract.py tests\test_m22_command_center_contract.py tests\test_m22_mission_ledger.py --basetemp .omx\pytest-tmp\m23-56-focused`
  -> 21 passed.
- Full backend
  `.\.venv\Scripts\python.exe -m pytest -q --basetemp .omx\pytest-tmp\m23-56-full`
  -> 372 passed.
- Ruff `.\.venv\Scripts\python.exe -m ruff check .` -> passed.
- Frontend `npm run lint` -> passed.
- Frontend `npm run build` -> passed with the existing Vite chunk-size warning.
- Frontend focused Nodes E2E
  `npm run e2e -- --grep "loads nodes template"` -> 1 passed.
- Frontend full E2E final rerun `npm run e2e` -> 15 passed.
- Source-wall/live-safety/local-secret/mission-ledger safety gate
  `.\.venv\Scripts\python.exe -m pytest -q tests\test_clean_room_source_wall.py tests\test_m16_live_safety.py tests\test_m20_local_secret_gate.py tests\test_m22_mission_ledger.py --basetemp .omx\pytest-tmp\m23-56-safety`
  -> 23 passed.
- FastAPI smoke confirmed `metadata_only_nodes_workflow_health`, workflow count
  `1`, complete count `1`, embedded health parity, Command Center action count
  `70`, preflight rows `70`, and no local secret-store creation.
- Changed-diff secret scan -> passed.
- `git diff --check` -> passed with Git CRLF working-copy warnings only.
