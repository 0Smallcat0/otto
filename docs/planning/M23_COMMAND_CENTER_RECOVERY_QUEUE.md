# M23.7 Command Center Recovery Queue

Date: 2026-05-25

## Scope

M23.7 adds a read-only Command Center recovery queue for AI Agent supervision.
It does not execute recovery, delete files, mutate artifact roots, start live
trading, read credentials, or call external providers.

The queue aggregates already-reviewed local recovery surfaces:

- provider refresh lifecycle recovery hints;
- advanced-route missing-output recommendations for AI Chat, Nodes, Code,
  Quant Lab, and QuantLib;
- existing AI Agent action-contract metadata for method, endpoint, and safety
  class.

## Implementation

- Added top-level `recovery_queue` to `GET /api/command-center`.
- Added a `recovery_queue` event to the Command Center activity timeline.
- Added stable selector
  `[data-testid='command-center-recovery-queue']`.
- Added Settings AI Agent state field `command_center_recovery_queue`.
- Added frontend Command Center panel rows for queued non-destructive recovery
  actions.
- Updated Command Center provenance to this milestone.

## Contract

Each recovery item includes:

- `queue_id`
- `source`
- `route_id`
- `state`
- `recommended_action`
- `method`
- `endpoint`
- `reason`
- `artifact_path`
- `safety_class`
- `writes_local_artifacts`
- `requires_confirmation`
- `destructive_actions_enabled`

The queue summary records total item count, provider-refresh count,
advanced-output count, destructive-action count, and local-artifact write count.

## Safety

- Queue generation is read-only.
- Artifact contents are not read.
- Secret values are not returned.
- Live trading, broker mutation, real orders, real balances, margin, leverage,
  short exposure, derivatives, payment, subscription, CR/credits, cloud sync,
  Fincept branding/assets/source, and installed-source reads remain excluded.
- `destructive_actions_enabled` stays `false` for the queue and every item.

## Verification

- `.\.venv\Scripts\python.exe -m pytest tests\test_m22_command_center_contract.py tests\test_m21_agent_operability_contract.py -q --basetemp .omx\pytest-tmp\m23-7-contract-initial` -> 6 passed.
- `.\.venv\Scripts\python.exe -m ruff check src\local_terminal\command_center.py src\local_terminal\agent_contract.py tests\test_m22_command_center_contract.py tests\test_m21_agent_operability_contract.py` -> passed.
- Frontend `npm run lint` -> passed.
- `.\.venv\Scripts\python.exe -m pytest tests\test_m22_command_center_contract.py tests\test_m21_agent_operability_contract.py tests\test_m22_mission_ledger.py -q --basetemp .omx\pytest-tmp\m23-7-doc-contract` -> 10 passed.
- FastAPI TestClient smoke for `/api/command-center` -> 200; milestone
  `M23.7 Command Center recovery queue`, 7 activity timeline events including
  `recovery_queue`, 5 read-only queue items in a fresh state, all items
  `destructive_actions_enabled=false`, no local secret store created, and no
  secret-like response text.
- `.\.venv\Scripts\python.exe -m pytest -q --basetemp .omx\pytest-tmp\m23-7-full` -> 291 passed.
- `.\.venv\Scripts\python.exe -m ruff check .` -> passed.
- Frontend `npm run lint`, `npm run build`, and `npm run e2e` from
  `frontend/` -> passed; build kept the existing Vite chunk-size warning and
  E2E result was 15 passed.
- Browser smoke opened Settings and confirmed the M23.7 milestone, 7-event
  activity timeline with `recovery_queue` and `risk_gates`, recovery queue rows
  with advanced/provider actions, mutation count 0, and no secret-like text.
- `.\.venv\Scripts\python.exe -m pytest tests\test_clean_room_source_wall.py tests\test_m16_live_safety.py tests\test_m20_local_secret_gate.py tests\test_m22_mission_ledger.py -q --basetemp .omx\pytest-tmp\m23-7-safety` -> 23 passed.
- Changed-file redacted secret scan found only existing verification text and
  negative `api_key=`/`protected_value` assertions; no credential values,
  personal email literals, provider keys, bearer tokens, or private-key blocks
  were added.
- `git diff --check` -> passed with Git CRLF working-copy warnings only.

## Follow-Up Boundary

This queue is a supervision/indexing contract, not an autonomous recovery
engine. Any archive/prune/delete/restore execution, workflow runtime execution,
managed LLM call, provider signup, credential flow, live/private trading, or
mutation-based recovery needs a separate safety-reviewed milestone.
