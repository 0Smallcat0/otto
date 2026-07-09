# M22.2 Command Center AI Supervision Contract

Date: 2026-05-25

## Scope

M22.2 adds the first command-center contract for human supervision of AI Agent
activity. This slice is backend/API-first: it gives future UI work a stable
machine-readable surface before any broad visual redesign.

## Product Contract

`GET /api/command-center` returns a read-only supervision payload with:

- current non-live goal and milestone status
- route/action contract summary from the existing AI Agent contract
- provider/source setup and cache state from governance provider rows
- artifact lifecycle and provider-refresh recovery state
- risk gates for live safety, local secrets, and source-wall status
- provenance evidence paths for the mission ledger and M21 planning artifacts
- stable selectors for the future command-center UI surface

The payload is intentionally an aggregator over existing contracts. It does not
create a second source of truth for providers, artifacts, live safety, source
wall, local secrets, or route actions.

## Clean-Room And Safety Boundaries

- No Fincept branding, assets, commercial copy, source, or runtime binaries.
- No `D:\FinceptTerminal\app\scripts` read or installed-source dependency.
- No provider signup, credential collection, secret value reads, or secret value
  output.
- No live trading, broker/exchange binding, real balance reads, real orders,
  margin, leverage, short exposure, derivatives, cloud sync, billing, or
  subscription flow.
- No artifact content reads, destructive cleanup, archive, prune, delete, move,
  or restore execution.

## Implementation

- Added `src/local_terminal/command_center.py`.
- Added `GET /api/command-center`.
- Added `tests/test_m22_command_center_contract.py`.

## Verification

- `.\.venv\Scripts\python.exe -m pytest tests\test_m22_command_center_contract.py tests\test_m21_agent_operability_contract.py tests\test_m21_artifact_lifecycle.py tests\test_m21_provider_refresh_lifecycle.py -q` -> 13 passed.
- `.\.venv\Scripts\python.exe -m ruff check src\local_terminal\command_center.py tests\test_m22_command_center_contract.py src\local_terminal\server.py` -> passed.

## Next

M22.3 exposed this contract in a restrained Settings UI surface documented in
`docs/planning/M22_COMMAND_CENTER_UI.md`. Later command-center work should keep
the same payload as the source of truth and avoid a full frontend redesign until
route/data depth gaps are narrower.
