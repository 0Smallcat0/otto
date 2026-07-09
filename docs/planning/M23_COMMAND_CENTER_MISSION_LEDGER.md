# M23.12 Command Center Mission Ledger Snapshot

Date: 2026-05-26

## Scope

M23.12 makes the anti-stall mission ledger visible to AI Agents and human
supervisors through the existing Command Center and Dashboard surfaces. It
continues from M23.11 and does not reopen provider wiring, route shells,
activity-journal logging, action preflight, or SOFR reference-rate behavior.

This slice is supervision metadata only. It is not an execution engine, planner,
provider signup flow, artifact cleanup flow, goal-completion claim, or live
trading surface.

## Implementation

- Added `mission_ledger` to `GET /api/command-center` with current status,
  resume rule, do-not-redo list, partial gaps, stop gates, status classes,
  commit cadence, provenance paths, and safety flags.
- Added a `mission_ledger` activity timeline event so agents can detect the
  ledger state without parsing UI text or markdown.
- Added Settings UI visibility through stable selector
  `command-center-mission-ledger`.
- Added a Dashboard first-screen Agent Supervision summary through stable
  selector `dashboard-command-center-summary`, sourced from the same read-only
  Command Center payload.
- Updated frontend Command Center types and local fallback data for the new
  contract.

## Safety

- No action execution, provider refresh, external network call, provider signup,
  key collection, secret read, secret write, artifact content read, destructive
  archive/prune/delete/restore, broker/exchange binding, real balance read, or
  live order path was added.
- The ledger snapshot keeps the long goal status `partial` until a future final
  audit proves every non-live requirement is complete.
- Existing source-wall, live-safety, local-secret, and clean-room boundaries
  remain in force.

## Verification

- Focused contract/dashboard/ledger gate:
  `.\.venv\Scripts\python.exe -m pytest tests\test_m22_command_center_contract.py tests\test_m22_mission_ledger.py tests\test_m3_dashboard.py -q --basetemp .omx\pytest-tmp\m23-12-focused-initial` -> 10 passed.
- Focused ruff:
  `.\.venv\Scripts\python.exe -m ruff check src\local_terminal\command_center.py tests\test_m22_command_center_contract.py` -> passed.
- Frontend `npm run lint` -> passed.
- Frontend `npm run build` -> passed with the existing Vite chunk-size warning.
- Frontend `npm run e2e` -> 15 passed.
- Full backend gate initially caught a source-wall failure because runtime code
  used a forbidden product-name string in a partial-gap label. The label was
  changed to neutral installed-app wording, then
  `.\.venv\Scripts\python.exe -m pytest -q --basetemp .omx\pytest-tmp\m23-12-full-rerun` -> 295 passed.
- Safety/source-wall gate after the same fix:
  `.\.venv\Scripts\python.exe -m pytest tests\test_clean_room_source_wall.py tests\test_m16_live_safety.py tests\test_m20_local_secret_gate.py tests\test_m22_mission_ledger.py -q --basetemp .omx\pytest-tmp\m23-12-safety-rerun` -> 23 passed.
- Full ruff `.\.venv\Scripts\python.exe -m ruff check .` -> passed, and
  focused ruff over `src\local_terminal\command_center.py` after the source-wall
  wording fix -> passed.
- FastAPI TestClient smoke for `/api/command-center` and `/api/dashboard` -> all
  200; Command Center reported M23.12, `mission_ledger.goal_status=partial`,
  `destructive_actions_enabled=false`, the `mission_ledger` timeline event and
  selector were present, and no local secret store was created.
- Changed-diff secret scan found zero email literals, provider-key assignments,
  bearer-token values, private-key blocks, `api_key=`, `protected_value`,
  password, or PIN hits.
- `git diff --check` -> passed with Git CRLF working-copy warnings only.

## Residuals

- This improves command-center-first supervision and anti-stall recovery. It
  does not close broad non-crypto executable quote breadth, fresh unrestricted
  installed-Fincept observation, destructive artifact lifecycle execution,
  external workflow runtimes, or global visual polish.
- Future work should continue to choose one residual partial gap at a time and
  preserve the mission-ledger resume rule.
