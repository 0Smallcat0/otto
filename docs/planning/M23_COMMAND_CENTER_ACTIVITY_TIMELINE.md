# M23.3 Command Center Activity Timeline

Date: 2026-05-25

## Purpose

M23.3 improves human supervision of AI Agent activity without adding any new
execution capability. The Command Center now exposes an ordered
`activity_timeline` so an agent and a human operator can inspect the current
milestone, route/action contract, provider state, artifact recovery, advanced
outputs, and risk gates from one machine-readable payload before acting.

## Scope

- Adds `activity_timeline` to `GET /api/command-center`.
- Uses only existing local governance, agent-contract, provider, artifact,
  advanced-output, and safety payloads.
- Adds a stable selector: `command-center-activity-timeline`.
- Surfaces the timeline in the Settings Command Center panel.
- Updates the current milestone provenance to this document.

Out of scope:

- Tool-call capture from external agents.
- Runtime execution, managed LLM calls, notebook/kernel execution, broker or
  exchange binding, real orders, real balances, margin, leverage, short
  exposure, derivatives, destructive artifact actions, payment, subscription,
  CR/credits, cloud sync, provider signup, or credential value reads.
- Fincept branding, assets, commercial copy, installed-source reads, or runtime
  binary copying.

## Product Behavior

- Timeline entries are deterministic summaries derived from existing contracts:
  `current_milestone`, `route_action_contract`, `provider_source_state`,
  `artifact_recovery`, `advanced_outputs`, and `risk_gates`.
- Each entry includes `event_id`, `state`, `risk_level`, `summary`, `evidence`,
  and `recovery_hint`.
- Risk and recovery language stays advisory and read-only. It points agents to
  existing safe endpoints and stop gates rather than creating new actions.
- The UI shows the ordered timeline in the existing Command Center supervision
  surface for human monitoring during agent-driven workflows.

## Verification

- `.\.venv\Scripts\python.exe -m pytest tests\test_m22_command_center_contract.py -q --basetemp .omx\pytest-tmp\m23-3-command-center-focused-initial` -> 2 passed.
- `.\.venv\Scripts\python.exe -m ruff check src\local_terminal\command_center.py tests\test_m22_command_center_contract.py` -> passed.
- `npm run lint` from `frontend/` -> passed.
- FastAPI TestClient probe for `/api/command-center` returned 200 with
  milestone `M23.3 Command Center activity timeline`, 6 timeline entries,
  selector `[data-testid='command-center-activity-timeline']`, and
  `safety.live_trading=False`.
- `.\.venv\Scripts\python.exe -m pytest -q --basetemp .omx\pytest-tmp\m23-3-full` -> 274 passed.
- `.\.venv\Scripts\python.exe -m pytest tests\test_m22_command_center_contract.py tests\test_m22_mission_ledger.py tests\test_clean_room_source_wall.py tests\test_m16_live_safety.py tests\test_m20_local_secret_gate.py -q --basetemp .omx\pytest-tmp\m23-3-safety-docs` -> 25 passed.
- `npm run build` from `frontend/` -> passed with the existing Vite chunk-size warning.
- `npm run e2e` from `frontend/` -> 15 passed, including timeline visibility in the Settings Command Center panel.
- `.\.venv\Scripts\python.exe -m ruff check .` -> passed.
- `.\.venv\Scripts\python.exe -m pytest tests\test_m22_command_center_contract.py tests\test_m22_mission_ledger.py -q --basetemp .omx\pytest-tmp\m23-3-doc-final` -> 6 passed.
- `git diff --check` -> passed with Git CRLF working-copy warnings only.
- Changed-file secret scan found no known personal credential literals and no
  high-risk assignment-like secret matches outside planning docs.

## Residuals

- This is a supervision contract, not a durable live event log. Capturing actual
  external tool calls or autonomous agent session replay requires a separate
  local logging contract and privacy review.
- Global UI polish can continue, but this slice keeps the change surgical and
  tied to existing Command Center data.
