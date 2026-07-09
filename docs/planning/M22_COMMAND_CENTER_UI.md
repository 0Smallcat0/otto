# M22.3 Command Center UI Supervision Surface

Date: 2026-05-25

## Scope

M22.3 exposes the M22.2 command-center contract in the existing Settings
governance surface. This is a restrained UI slice, not a global redesign and
not a new route.

## Product Contract

The Settings command-center panel now shows:

- command-center mode, version, current milestone, route count, action count,
  selector count, and shell-match state
- route/action contract rows plus disabled safety-gated action rows
- provider/source counts and representative provider cache/source rows
- artifact inventory counts, provider-refresh recovery queue status, and
  non-destructive recovery visibility
- live-safety, secret-value-read, local-secret, and source-wall risk gates
- provenance evidence paths for the mission ledger and M21 planning artifacts

The UI reads `GET /api/command-center` as the source of truth. It does not add a
second route catalog, provider catalog, artifact inventory, safety model, or
secret state.

## AI Agent Operability

The panel exposes stable selectors that match the backend command-center
selector contract:

- `workspace-command-center`
- `command-center-activity`
- `command-center-route-action-contract`
- `command-center-provider-source-state`
- `command-center-artifact-recovery`
- `command-center-risk-gates`
- `command-center-provenance-evidence`

These selectors let an AI Agent inspect the supervision state without scraping
ambiguous human-facing text.

## Clean-Room And Safety Boundaries

- No Fincept branding, assets, commercial copy, source, runtime binaries, or
  installed-source dependency.
- No provider signup, provider-key acquisition, credential output, secret value
  reads, or secret value logging.
- No live trading, broker/exchange binding, real balance reads, real orders,
  margin, leverage, short exposure, derivatives, billing, subscription, cloud
  sync, or CR/credits.
- No artifact content reads or destructive artifact mutation.

## Implementation

- Added `frontend/src/types/commandCenter.ts`.
- Added `frontend/src/components/CommandCenterPanel.tsx` and mounted it in the
  existing Settings governance grid.
- Updated `frontend/tests/m2-shell.spec.ts` to verify the panel through stable
  test IDs.
- Updated `src/local_terminal/command_center.py` so the active milestone is
  `M22.3 command-center UI supervision surface` and cache paths reuse the
  existing governance cache `path` field. M22.5 later moved the active
  milestone label forward to the SEC XBRL frames Markets reference-breadth
  slice while retaining this UI surface.

## Verification

- `.\.venv\Scripts\python.exe -m pytest tests\test_m22_command_center_contract.py tests\test_m22_mission_ledger.py tests\test_clean_room_source_wall.py -q` -> 12 passed.
- `.\.venv\Scripts\python.exe -m pytest tests\test_m22_command_center_contract.py tests\test_m21_agent_operability_contract.py tests\test_m21_artifact_lifecycle.py tests\test_m21_provider_refresh_lifecycle.py tests\test_clean_room_source_wall.py -q --basetemp .omx\pytest-tmp\m22-3-full` -> 20 passed.
- `.\.venv\Scripts\python.exe -m pytest tests\test_m16_live_safety.py tests\test_m20_local_secret_gate.py -q --basetemp .omx\pytest-tmp\m22-3-safety` -> 12 passed.
- `.\.venv\Scripts\python.exe -m ruff check src\local_terminal\command_center.py tests\test_m22_command_center_contract.py` -> passed.
- `npm run lint` -> passed.
- `npm run build` -> passed.
- `npm run e2e -- --grep "opens all routes"` -> 1 passed.
- `npm run e2e` -> 15 passed.

## Next

M22.4 completed the provider/data acquisition gate in
`docs/planning/M22_PROVIDER_DATA_ACQUISITION_GATE.md`. Provider implementation
started with the bounded SEC XBRL frames public no-key candidate in M22.5. The
next provider/data slice should keep using the command center for current
milestone visibility and preserve the source coverage matrix quote/reference
semantics.
