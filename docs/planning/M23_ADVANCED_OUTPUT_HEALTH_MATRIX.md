# M23.23 Advanced Output Health Matrix

Date: 2026-05-26

## Scope

M23.23 deepens the safe local output supervision surface for AI Chat, Nodes,
Code, Quant Lab, and QuantLib. It extends the metadata-only advanced workflow
output packet with per-route health states, expected artifact kinds, missing
expected artifact kinds, and supervision-ready counts.

This milestone does not add route execution, notebook kernels, workflow runtime,
managed LLM calls, external QuantLib runtime, provider signup, credential reads,
cloud sync, artifact content indexing, route-output mutation, or destructive
artifact recovery.

## Implemented Behavior

- `advanced_workflow_output_packet` now classifies each advanced route as:
  - `complete`
  - `partial`
  - `missing_output`
- Each advanced route row now includes:
  - `health_state`
  - `supervision_ready`
  - `expected_artifact_kinds`
  - `missing_expected_kinds`
  - `health_reason`
- Summary rows now include complete/partial/missing health counts and
  `supervision_ready_count`.
- The recovery queue now includes partial advanced-route outputs when expected
  metadata kinds are missing.
- Command Center advanced-output rows surface the route health state and missing
  expected metadata kinds.
- `/api/agent-contract` advertises Settings state
  `advanced_output_health_matrix` and read-only action
  `advanced_workflow_output_health`.
- Command Center provenance advances to this M23.23 milestone.

## Safety

- The health matrix reads filesystem metadata only.
- It does not open artifact contents, inspect manifest/report JSON or Markdown,
  execute notebooks or workflows, call providers, read credentials, mutate route
  outputs, or perform archive/delete/restore actions.
- It preserves all existing disabled runtime gates for AI Chat, Nodes, Code,
  Quant Lab, and QuantLib.

## Verification

Final verification:

- `.\.venv\Scripts\python.exe -m pytest tests\test_m22_advanced_workflow_outputs.py tests\test_m21_agent_operability_contract.py tests\test_m22_command_center_contract.py -q --basetemp .omx\pytest-tmp\m23-23-focused-initial`
  -> 9 passed.
- `.\.venv\Scripts\python.exe -m ruff check src\local_terminal\advanced_outputs.py src\local_terminal\agent_contract.py src\local_terminal\command_center.py tests\test_m22_advanced_workflow_outputs.py tests\test_m21_agent_operability_contract.py tests\test_m22_command_center_contract.py`
  -> passed.
- Frontend `npm run lint` -> passed.
- `.\.venv\Scripts\python.exe -m pytest tests\test_m22_advanced_workflow_outputs.py tests\test_m21_agent_operability_contract.py tests\test_m22_command_center_contract.py tests\test_m22_mission_ledger.py -q --basetemp .omx\pytest-tmp\m23-23-docs`
  -> 13 passed.
- `.\.venv\Scripts\python.exe -m pytest -q --basetemp .omx\pytest-tmp\m23-23-full`
  -> 318 passed.
- `.\.venv\Scripts\python.exe -m ruff check .` -> passed.
- Frontend `npm run build` -> passed with the existing Vite chunk-size warning.
- Frontend `npm run e2e` -> 15 passed.
- Source-wall/live-safety/local-secret/ledger gate
  `.\.venv\Scripts\python.exe -m pytest tests\test_clean_room_source_wall.py tests\test_m16_live_safety.py tests\test_m20_local_secret_gate.py tests\test_m22_mission_ledger.py -q --basetemp .omx\pytest-tmp\m23-23-safety`
  -> 23 passed.
- FastAPI TestClient smoke confirmed partial health states, missing expected
  kinds, Command Center milestone M23.23, AI Agent action
  `advanced_workflow_output_health`, and no local secret-store creation.
- Changed-diff secret scan found no personal-account email literals,
  password/PIN literals, provider-key assignments, bearer-token values,
  private-key blocks, protected value markers, or credential assignments.
- `git diff --check` -> passed with Git CRLF working-copy warnings only.

## Handoff

Future expansion can add route-specific, metadata-only stale-age or expected-file
details. Actual artifact content indexing, automatic repair, delete/move/restore,
route execution, managed LLM calls, notebook/workflow runtimes, and external
QuantLib runtime still require separate reviewed safety contracts.
