# M23.8 AI Agent Action Preflight

Date: 2026-05-25

## Scope

M23.8 adds a read-only action preflight contract for AI Agent operation. It lets
an agent check an existing action before attempting it, using the already
reviewed AI Agent action contracts instead of inferring readiness from UI text.

This milestone does not execute actions, call providers, store credentials,
write route artifacts, mutate local state, or enable live/private/destructive
capabilities.

## Implementation

- Added `GET /api/agent-actions/{action_id}/preflight`.
- Added Agent Contract top-level `preflight` discovery metadata.
- Added Command Center route/action preflight visibility.
- Updated Settings Command Center UI to show the preflight endpoint.
- Updated Agent Contract and Command Center tests for the preflight contract.

## Contract

The preflight packet includes:

- `action_id`
- `status`
- `allowed_to_attempt`
- `allowed_without_confirmation`
- `reason`
- `action`
- `stop_gates`
- `evidence`
- `safety`

Status values are `ready`, `requires_confirmation`, `disabled_by_safety`, and
`unknown_action`.

## Safety

- The endpoint is read-only.
- `action_executed` and `local_mutation_performed` stay `false`.
- Secret values are not returned.
- External network calls are not made.
- Live trading, broker mutation, real orders, real balances, margin, leverage,
  short exposure, derivatives, destructive artifact actions, Fincept branding,
  commercial copy, installed-source reads, payment, subscription, CR/credits,
  and cloud sync remain excluded.
- Confirmation-required actions are reported as not allowed without
  confirmation.

## Verification

- Focused Agent Contract / Command Center gate
  `.\.venv\Scripts\python.exe -m pytest tests\test_m21_agent_operability_contract.py tests\test_m22_command_center_contract.py -q --basetemp .omx\pytest-tmp\m23-8-focused`
  -> 7 passed.
- Focused ruff
  `.\.venv\Scripts\python.exe -m ruff check src\local_terminal\agent_contract.py src\local_terminal\server.py src\local_terminal\command_center.py tests\test_m21_agent_operability_contract.py tests\test_m22_command_center_contract.py`
  -> passed.
- Frontend `npm run lint` -> passed.
- FastAPI TestClient smoke for `GET /api/agent-actions/{action_id}/preflight`
  -> `portfolio_report` returned `ready`, `code_run_disabled` returned
  `disabled_by_safety`, unknown action returned `unknown_action`, Command Center
  exposed M23.8 and the preflight endpoint, and no local secret store was
  created.
- Frontend `npm run build` -> passed with the existing Vite chunk-size warning.
- Frontend `npm run e2e` -> 15 passed.
- Full backend gate
  `.\.venv\Scripts\python.exe -m pytest -q --basetemp .omx\pytest-tmp\m23-8-full`
  -> 292 passed.
- Full ruff `.\.venv\Scripts\python.exe -m ruff check .` -> passed.
- Safety/source-wall gate
  `.\.venv\Scripts\python.exe -m pytest tests\test_clean_room_source_wall.py tests\test_m16_live_safety.py tests\test_m20_local_secret_gate.py tests\test_m22_mission_ledger.py -q --basetemp .omx\pytest-tmp\m23-8-safety`
  -> 23 passed.
- Browser smoke opened Settings at `http://127.0.0.1:5173/#/settings` and
  confirmed M23.8, the Command Center `Action Preflight` row, the preflight
  endpoint, visible recovery queue state, and no `protected_value` or `api_key=`
  text. Screenshot capture timed out in the in-app browser, but DOM/visible-text
  verification passed.
- Added-line redacted secret scan found zero email literals, private-key
  blocks, bearer-token values, or likely secret assignments; the only
  `protected_value` hits are negative UI/text checks.
- `git diff --check` -> passed with Git CRLF working-copy warnings only.

## Follow-Up Boundary

This preflight contract is a readiness check, not an execution broker. Any
durable action session log, replay, autonomous repair engine, provider signup,
managed LLM call, workflow runtime execution, or live/private path needs a
separate reviewed milestone.
