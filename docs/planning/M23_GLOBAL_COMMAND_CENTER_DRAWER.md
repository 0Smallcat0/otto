# M23.62 Global Command Center Drawer

## Scope

M23.62 improves command-center-first supervision by making the existing
read-only Command Center payload available from the global shell strip on every
route. This is a UI operability slice for human supervision of AI Agent
activity; it does not add a route or backend action.

This slice does not execute actions, approve recovery, mutate artifacts, call
providers, read artifact contents, expose credentials, route broker actions, or
enable live/private behavior.

## Product Delta

- Adds a shell-strip `CENTER` control with selector
  `shell-command-center-open`.
- Adds a route-independent drawer with selector
  `global-command-center-drawer`.
- Surfaces active task, mission ledger, recovery summary, risk gates, activity
  timeline, preflight rows, recovery queue, and provenance evidence from the
  existing `/api/command-center` payload.
- Keeps Settings `CommandCenterPanel` as the deep inspection surface and does
  not duplicate backend contracts.
- Moves Command Center provenance to this milestone without changing the AI
  Agent action count.

## Safety Contract

- The drawer is read-only display state.
- No action execution, confirmation, provider refresh, artifact lifecycle
  mutation, request-body logging, credential access, broker/exchange binding,
  real balance read, real order, or live/private behavior is reachable from the
  drawer.
- Recovery rows remain informational and non-destructive unless a future
  dedicated safety-reviewed milestone creates a separate action.

## Verification Evidence

- Focused backend
  `.\.venv\Scripts\python.exe -m pytest -q tests\test_m22_command_center_contract.py tests\test_m22_mission_ledger.py --basetemp .omx\pytest-tmp\m23-62-focused`
  -> 7 passed.
- Frontend `npm run lint` -> passed.
- Frontend `npm run build` -> passed with the existing Vite chunk-size warning.
- Focused shell E2E
  `npm run e2e -- --grep "opens all routes"` -> 1 passed.
- Focused Code E2E
  `npm run e2e -- --grep "edits local code notebook"` -> 1 passed after
  renaming the global drawer button from `OPEN` to `CENTER` to avoid selector
  collision with the Code toolbar.
- Full backend
  `.\.venv\Scripts\python.exe -m pytest -q --basetemp .omx\pytest-tmp\m23-62-full-rerun`
  -> 376 passed after the first full run timed out while parallelized.
- Ruff `.\.venv\Scripts\python.exe -m ruff check .` -> passed.
- Frontend full E2E final rerun `npm run e2e` -> 15 passed.
- Source-wall/live-safety/local-secret/provider gate
  `.\.venv\Scripts\python.exe -m pytest -q tests\test_clean_room_source_wall.py tests\test_m16_live_safety.py tests\test_m20_local_secret_gate.py tests\test_m22_provider_acquisition_gate.py --basetemp .omx\pytest-tmp\m23-62-safety`
  -> 22 passed.
- FastAPI smoke confirmed Command Center milestone
  `M23.62 Global Command Center drawer`, milestone path
  `docs/planning/M23_GLOBAL_COMMAND_CENTER_DRAWER.md`, timeline rows `10`,
  action count `73`, preflight rows `73`, live/secret gates disabled, and no
  local secret-store creation.
- Changed-diff secret scan -> passed with no matches and Git CRLF
  working-copy warnings only.
- `git diff --check` -> passed with Git CRLF working-copy warnings only.
