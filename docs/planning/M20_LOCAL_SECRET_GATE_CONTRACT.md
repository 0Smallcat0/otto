# M20.7 Local Secret Gate Contract

Date: 2026-05-23

## Purpose

Create a concrete, testable local secret-storage gate before any optional-key data provider can move beyond setup status. This milestone does not collect, read, or persist user keys. It makes the blocked state explicit, adds redaction helpers, and exposes a read-only governance/API surface so future optional-key work has a contract to satisfy.

## Runtime Surface

- Contract module: `src/local_terminal/secret_gate.py`.
- Read-only endpoint: `/api/secret-gate`.
- Governance integration: `/api/governance`, `/api/help`, and Help diagnostics now report `contract_ready_disabled`, `local-secret-gate-v1`, blocked optional-key providers, redaction marker, forbidden surfaces, and enablement requirements.
- Settings UI: Local Secret Status now shows the policy version, blocked provider count, and enablement gate status.

## Safety

- `writes_enabled=false`.
- `reads_enabled=false`.
- `key_entry_forms_enabled=false`.
- `secret_persistence_enabled=false`.
- The planned local path remains `settings/local_secrets.json`, but current runtime does not create it.
- The storage contract is limited to optional local-key data providers and explicitly forbids broker/exchange private or live-trading use.
- No credential, token, private key, PIN, or provider key value is present in tracked files, docs, tests, screenshots, or commits.

## Verification

- `tests/test_m20_local_secret_gate.py` covers the read-only gate, redaction helpers, `/api/secret-gate`, governance/help propagation, and the absence of `settings/local_secrets.json`.
- Existing governance tests continue proving optional-key provider rows keep `form_enabled=false` and `secret_persistence_enabled=false`.
- Frontend E2E checks the Settings route for `contract_ready_disabled` and `local-secret-gate-v1`.
- Focused sweep `.\.venv\Scripts\python.exe -m pytest tests\test_m20_local_secret_gate.py tests\test_m19_governance_routes.py tests\test_m16_live_safety.py tests\test_clean_room_source_wall.py -q` with repo-local TEMP/TMP -> 18 passed.
- Full gate `.\.venv\Scripts\python.exe -m pytest -q` with repo-local TEMP/TMP -> 167 passed.
- `.\.venv\Scripts\python.exe -m ruff check .`, `npm run lint`, `npm run build`, `npm run e2e`, and `npm audit --audit-level=high` passed.
- UI evidence: `artifacts/screenshots/m20-7-settings-secret-gate.png`.

## M20.24 Enablement Addendum

M20.24 keeps this contract's redaction and clean-room requirements, but changes the runtime from read-only planning status to a scoped local store for eligible optional data providers.

- New policy version: `local-secret-store-v1`.
- New state when available: `local_secret_store_ready`.
- Store path: `settings/local_secrets.json`, still ignored by git and absent by default.
- Storage mode: Windows current-user DPAPI.
- Eligible provider class: `optional_local_secret_data_provider`.
- API value reads remain disabled through `api_secret_value_reads_enabled=false`.
- HTTP write/delete actions are limited to eligible data-provider ids and require explicit local-only consent.
- Paid/plan-gated optional providers and all broker/exchange/live-trading providers remain blocked.

Implementation details and verification are recorded in `docs/planning/M20_LOCAL_SECRET_STORE_ENABLEMENT.md`.
