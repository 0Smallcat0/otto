# M23.10 Active Task Supervision

Date: 2026-05-26

## Scope

M23.10 turns the M23.9 metadata-only Agent Activity Journal into an explicit
Command Center active-task supervision contract. It derives the currently
declared AI Agent task from the latest journal event when that event is
`planned`, `running`, or `blocked`.

This milestone does not add action execution, request/response logging, tool-call
replay, recovery automation, provider signup, credential storage, external
network calls, artifact mutation execution, or live/private/destructive paths.

## Implementation

- Added `active_task` to `GET /api/agent-activity`.
- Added Command Center top-level `active_task`.
- Added Command Center stable selector `command-center-active-task`.
- Added Settings route state `command_center_active_task` to the AI Agent
  contract.
- Updated the Settings Command Center UI with a compact Active Task panel for
  state, route, action, endpoint, and safety flags.

## Contract

An active task is derived only from the latest metadata event:

- `planned`, `running`, or `blocked` -> `is_active=true`.
- `succeeded`, `failed`, `skipped`, or no event -> `is_active=false`.

The contract repeats only bounded metadata already accepted by the journal:

- route/action identifiers
- state and summary
- repo-local artifact path
- method, endpoint, and safety class from the AI Agent action contract
- `request_body_logged=false`
- `action_executed_by_journal=false`
- `destructive_actions_enabled=false`

## Safety

- No request body is logged.
- No action is executed by the journal or Command Center.
- No secret value is returned or stored.
- The local secret store is not created by active-task inspection.
- Live trading, broker mutation, real orders, real balances, margin, leverage,
  short exposure, derivatives, destructive artifact actions, Fincept branding,
  commercial copy, installed-source reads, payment, subscription, CR/credits,
  and cloud sync remain excluded.

## Verification

- Initial focused Agent Activity / Agent Contract / Command Center gate
  `.\.venv\Scripts\python.exe -m pytest tests\test_m23_agent_activity_journal.py tests\test_m21_agent_operability_contract.py tests\test_m22_command_center_contract.py -q --basetemp .omx\pytest-tmp\m23-10-focused-initial`
  -> 9 passed.
- Focused ruff
  `.\.venv\Scripts\python.exe -m ruff check src\local_terminal\agent_activity.py src\local_terminal\agent_contract.py src\local_terminal\command_center.py tests\test_m23_agent_activity_journal.py tests\test_m21_agent_operability_contract.py tests\test_m22_command_center_contract.py`
  -> passed.
- Doc/contract rerun
  `.\.venv\Scripts\python.exe -m pytest tests\test_m23_agent_activity_journal.py tests\test_m21_agent_operability_contract.py tests\test_m22_command_center_contract.py tests\test_m22_mission_ledger.py -q --basetemp .omx\pytest-tmp\m23-10-doc-contract`
  -> 13 passed.
- Final doc/contract rerun after updating handoff evidence
  `.\.venv\Scripts\python.exe -m pytest tests\test_m23_agent_activity_journal.py tests\test_m21_agent_operability_contract.py tests\test_m22_command_center_contract.py tests\test_m22_mission_ledger.py -q --basetemp .omx\pytest-tmp\m23-10-doc-final`
  -> 13 passed.
- Frontend `npm run lint` -> passed.
- FastAPI TestClient smoke wrote a `portfolio_report` running event, confirmed
  Command Center `active_task.is_active=true`, wrote a `succeeded` event,
  confirmed `active_task.is_active=false`, and created no local secret store.
- Full backend gate
  `.\.venv\Scripts\python.exe -m pytest -q --basetemp .omx\pytest-tmp\m23-10-full`
  -> 294 passed.
- Frontend `npm run build` -> passed with the existing Vite chunk-size warning.
- Full ruff `.\.venv\Scripts\python.exe -m ruff check .` -> passed.
- Safety/source-wall gate
  `.\.venv\Scripts\python.exe -m pytest tests\test_clean_room_source_wall.py tests\test_m16_live_safety.py tests\test_m20_local_secret_gate.py tests\test_m22_mission_ledger.py -q --basetemp .omx\pytest-tmp\m23-10-safety`
  -> 23 passed.
- Frontend `npm run e2e` -> 15 passed after stopping stale local dev listeners
  from the previous run.
- Added-line redacted secret scan found zero email literals, private-key
  blocks, bearer-token values, likely secret assignments, or protected-value
  marker literals.
- `git diff --check` -> passed with Git CRLF working-copy warnings only.

## Follow-Up Boundary

This active-task contract is a supervision view over local metadata. Durable
session replay, full external tool-call logging, automatic recovery, artifact
delete/archive/restore execution, provider signup, managed LLM calls, notebook
runtime execution, or live/private/account behavior requires a separate reviewed
safety milestone.
