# M23.9 Agent Activity Journal

Date: 2026-05-25

## Scope

M23.9 adds a local metadata-only activity journal so humans can supervise what an
AI Agent is doing inside the terminal. It records bounded action status events,
not request bodies, tool transcripts, secret material, provider payloads, or
execution replay.

This milestone does not execute actions, call providers, store credentials,
read artifact contents, mutate broker/exchange state, or enable live/private/
destructive paths.

## Implementation

- Added `GET /api/agent-activity`.
- Added `POST /api/agent-activity/events`.
- Added local JSONL artifact path `artifacts/agent_activity/activity.jsonl`.
- Added AI Agent action contract `agent_activity_event`.
- Added Settings route state `agent_activity_journal`.
- Added Command Center top-level `agent_activity`, activity timeline
  `agent_activity` event, stable selector `command-center-agent-activity`, and
  Settings UI panel.

## Contract

Activity events require:

- `action_id`
- `state`

Optional metadata:

- `route_id`
- `summary`
- `artifact_path`

The journal derives route, method, endpoint, safety class, and artifact-write
flags from the existing AI Agent action contract. Accepted states are `planned`,
`running`, `succeeded`, `failed`, `blocked`, and `skipped`.

## Safety

- Request bodies are not logged.
- Secret-like metadata is rejected before writing.
- Artifact paths must be repo-local `artifacts/` paths.
- The journal does not execute the referenced action.
- The journal does not create or read the local secret store.
- Live trading, broker mutation, real orders, real balances, margin, leverage,
  short exposure, derivatives, destructive artifact actions, Fincept branding,
  commercial copy, installed-source reads, payment, subscription, CR/credits,
  and cloud sync remain excluded.

## Verification

- Initial focused Agent Activity / Agent Contract / Command Center gate
  `.\.venv\Scripts\python.exe -m pytest tests\test_m23_agent_activity_journal.py tests\test_m21_agent_operability_contract.py tests\test_m22_command_center_contract.py -q --basetemp .omx\pytest-tmp\m23-9-focused-initial`
  -> 9 passed.
- Focused ruff
  `.\.venv\Scripts\python.exe -m ruff check src\local_terminal\agent_activity.py src\local_terminal\agent_contract.py src\local_terminal\server.py src\local_terminal\command_center.py tests\test_m23_agent_activity_journal.py tests\test_m21_agent_operability_contract.py tests\test_m22_command_center_contract.py`
  -> passed.
- Frontend `npm run lint` -> passed.
- FastAPI TestClient smoke wrote a `portfolio_report` running event, rejected
  secret-like summary metadata with 400, returned one recent activity event from
  `GET /api/agent-activity`, exposed M23.9 through Command Center
  `agent_activity`, and created no local secret store.
- Doc/contract rerun
  `.\.venv\Scripts\python.exe -m pytest tests\test_m23_agent_activity_journal.py tests\test_m21_agent_operability_contract.py tests\test_m22_command_center_contract.py tests\test_m22_mission_ledger.py -q --basetemp .omx\pytest-tmp\m23-9-doc-after-secret-fixture`
  -> 13 passed after replacing a high-confidence secret-like test fixture with
  a lower-risk validator trigger.
- Frontend `npm run build` -> passed with the existing Vite chunk-size warning.
- Frontend `npm run e2e` -> 15 passed.
- Full backend gate
  `.\.venv\Scripts\python.exe -m pytest -q --basetemp .omx\pytest-tmp\m23-9-full-rerun`
  -> 294 passed.
- Full ruff `.\.venv\Scripts\python.exe -m ruff check .` -> passed.
- Safety/source-wall gate
  `.\.venv\Scripts\python.exe -m pytest tests\test_clean_room_source_wall.py tests\test_m16_live_safety.py tests\test_m20_local_secret_gate.py tests\test_m22_mission_ledger.py -q --basetemp .omx\pytest-tmp\m23-9-safety-rerun`
  -> 23 passed.
- Final doc/contract rerun
  `.\.venv\Scripts\python.exe -m pytest tests\test_m23_agent_activity_journal.py tests\test_m21_agent_operability_contract.py tests\test_m22_command_center_contract.py tests\test_m22_mission_ledger.py -q --basetemp .omx\pytest-tmp\m23-9-doc-final`
  -> 13 passed.
- Added-line redacted secret scan found zero email literals, private-key
  blocks, bearer-token values, likely secret assignments, or protected-value
  marker literals.
- `git diff --check` -> passed with Git CRLF working-copy warnings only.

## Follow-Up Boundary

This journal is a metadata status channel. Durable full tool-call replay,
request/response capture, automated recovery execution, provider signup,
managed LLM calls, workflow runtime execution, artifact mutation execution, or
live/private/account flows require separate reviewed milestones.
