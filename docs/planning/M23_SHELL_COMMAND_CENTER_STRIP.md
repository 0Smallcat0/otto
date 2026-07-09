# M23.13 Shell Command Center Strip

Date: 2026-05-26

## Scope

M23.13 makes Command Center supervision visible across the whole local terminal,
not only inside Dashboard or Settings. It continues from M23.12 and does not
reopen provider wiring, route shells, action preflight, activity-journal
semantics, mission-ledger content, or SOFR reference data.

This slice is read-only UI chrome. It is not an action executor, automatic
provider refresh trigger, recovery runner, planner, credential flow, or
live-trading surface.

## Implementation

- The frontend shell now fetches `GET /api/command-center` with shell/local
  state and provider freshness during startup and refreshes it when provider
  state refreshes.
- Added global selector `shell-command-center-strip` above every workspace.
- The strip shows current milestone, goal status, active task, recovery item
  count, live/secret risk gates, and source-wall state.
- Updated Command Center current milestone/provenance to this document.
- Updated E2E coverage so the shell strip is verified before route navigation.

## Safety

- No action execution, request logging, provider refresh trigger, provider signup,
  key collection, secret read, secret write, artifact content read, destructive
  archive/prune/delete/restore, broker/exchange binding, real balance read, or
  live order path was added.
- The strip displays supervision state only; users and agents must still use
  declared action preflight and route/action contracts before any local action.
- Existing source-wall, live-safety, local-secret, and clean-room boundaries
  remain in force.

## Verification

- Focused contract/ledger gate
  `.\.venv\Scripts\python.exe -m pytest tests\test_m22_command_center_contract.py tests\test_m22_mission_ledger.py -q --basetemp .omx\pytest-tmp\m23-13-focused-initial`
  -> 6 passed.
- Focused rerun after E2E selector/text collision fixes
  `.\.venv\Scripts\python.exe -m pytest tests\test_m22_command_center_contract.py tests\test_m22_mission_ledger.py -q --basetemp .omx\pytest-tmp\m23-13-focused-after-e2e-fix`
  -> 6 passed.
- Full backend `.\.venv\Scripts\python.exe -m pytest -q --basetemp .omx\pytest-tmp\m23-13-full`
  -> 295 passed.
- Frontend `npm run lint`, `npm run build`, and `npm run e2e` from
  `frontend/` -> passed; build kept the existing Vite chunk-size warning and
  E2E rerun was 15 passed.
- Full ruff `.\.venv\Scripts\python.exe -m ruff check .` -> passed.
- Safety/source-wall rerun
  `.\.venv\Scripts\python.exe -m pytest tests\test_clean_room_source_wall.py tests\test_m16_live_safety.py tests\test_m20_local_secret_gate.py tests\test_m22_mission_ledger.py -q --basetemp .omx\pytest-tmp\m23-13-safety-rerun`
  -> 23 passed. The first attempt had a transient concurrent Playwright
  `frontend/test-results` race, so the gate was rerun after E2E completed.
- FastAPI TestClient smoke for `/api/command-center`, `/api/dashboard`, and
  `/api/local-state` -> 200 responses; Command Center reported M23.13 with
  live mode disabled, secret value reads disabled, and installed-source reads
  disabled.
- Changed-diff secret scan found no email literals, provider-key assignments,
  private-key blocks, token-like credential literals, or protected-value markers.
- `git diff --check` -> passed with Git CRLF working-copy warnings only.

## Residuals

- This improves command-center-first human supervision. It does not close broad
  non-crypto executable quote breadth, fresh unrestricted installed-app
  observation, destructive artifact lifecycle execution, external workflow
  runtimes, or broader visual-system polish.
