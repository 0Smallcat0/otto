# M20 Settings Governance Diagnostics

Date: 2026-05-23

## Scope

M20.20 adds a Settings-owned local diagnostics workflow for provider setup, cache controls, source-wall policy, and local secret-gate status.

This is not a cache cleanup feature and not secret persistence. The workflow is read-only and writes a local artifact bundle under `artifacts/diagnostics/gov-{run_id}/`.

## Runtime Contract

- Endpoint: `POST /api/governance/diagnostics`
- Output mode: `local_governance_cache_diagnostics`
- Artifact files:
  - `governance.json`
  - `provider_cache.json`
  - `source_wall.json`
  - `manifest.json`
  - `report.md`
  - `error.log`

## Safety Contract

- No external network request.
- No cache delete or prune action.
- No secret reads, writes, key forms, or persistence.
- No private API key flow.
- No broker mutation, real order path, real balance read, margin, leverage, short exposure, or derivatives execution.
- No installed-source read.

## UI Evidence

- Settings route screenshot: `artifacts/screenshots/m20-20-settings-governance-diagnostics.png`
- The screenshot shows the run action, `gov-*` artifact directory, manifest path, source-wall verification, and cache/secret safety row.

## Verification

- `.\.venv\Scripts\python.exe -m pytest tests\test_m19_governance_routes.py tests\test_m15_forum_help.py -q` with repo-local TEMP/TMP -> 13 passed.
- `.\.venv\Scripts\python.exe -m ruff check src\local_terminal\support.py src\local_terminal\server.py tests\test_m19_governance_routes.py` -> passed.
- `npm run lint` -> passed.
- `npm run build` -> passed.
- `npm run e2e` -> 15 passed.
- `.\.venv\Scripts\python.exe -m pytest -q` with repo-local TEMP/TMP -> 184 passed.
- `.\.venv\Scripts\python.exe -m pytest tests\test_clean_room_source_wall.py tests\test_m16_live_safety.py -q` with repo-local TEMP/TMP -> 12 passed.
- `.\.venv\Scripts\python.exe -m ruff check .` -> passed.

## Review Notes

The milestone deliberately stops short of destructive cache lifecycle controls, background refresh, and local secret persistence. Those require separate contracts, safety review, and tests.
