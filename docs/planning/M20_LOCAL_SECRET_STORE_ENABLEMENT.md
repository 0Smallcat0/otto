# M20.24 Local Secret Store Enablement

Date: 2026-05-23

## Purpose

Unblock optional local-key data-provider milestones without weakening the clean-room or live-safety boundary. This milestone enables a local-only secret store for eligible optional data providers, while keeping paid providers, broker/exchange credentials, live trading, real balances, margin, leverage, short exposure, derivatives execution, billing, cloud accounts, and installed-source access disabled.

## Storage Design

- Store path: `settings/local_secrets.json`.
- Git policy: ignored by `.gitignore`; no values may be committed, logged, screenshot, or copied into docs.
- Storage mode: Windows current-user DPAPI via `CryptProtectData` / `CryptUnprotectData`, with non-interactive UI-forbidden calls.
- Value visibility: API responses expose only redacted status, stored provider ids, timestamps, and sealed ids. There is no HTTP endpoint that returns a secret value.
- Internal read path: `read_local_data_provider_secret()` exists only for future provider adapters after their provider-entry gate passes.
- Explicit opt-in: writes require the consent phrase `STORE_LOCAL_DATA_PROVIDER_SECRET`.

## Provider Scope

Eligible:

- `fred_optional_local_key`, because it is an optional local-key data provider and not a paid/plan-gated provider.

Still blocked:

- `premium_market_data_option`, because it is optional-key and paid/plan-gated.
- Any broker/exchange/private/live-trading provider.
- Any provider not present in the reviewed provider registry.

## Runtime Surface

- `src/local_terminal/local_secrets.py` implements provider classification, DPAPI sealing/opening, redacted status, store, forget, and internal read helpers.
- `src/local_terminal/secret_gate.py` now reports `local_secret_store_ready`, `local-secret-store-v1`, eligible/stored/blocked provider ids, storage mode, and API-value-read-disabled status.
- `/api/local-secrets/status` returns the redacted local secret status.
- `POST /api/local-secrets` stores an eligible data-provider value only with explicit consent.
- `DELETE /api/local-secrets/{provider_id}` removes an eligible data-provider value.
- Settings shows eligible/stored/blocked provider state, a local-only opt-in form, and a forget action. Input values are cleared after write and never returned by the API.

## Safety Invariants

- No private broker/exchange key flow was added.
- No live order path, real balance read, margin, leverage, short, or derivatives path was added.
- No paid provider activation, subscription, billing, credits, or cloud-account path was added.
- No installed Fincept source/code/assets/runtime path was read or referenced.
- The local store is not created by default; it is created only after explicit user opt-in for an eligible data provider.
- Diagnostics and governance artifacts remain redacted and do not include stored values.

## Verification Shape

- Focused tests prove the gate is ready without creating a store by default.
- Store tests prove the raw synthetic value is absent from `settings/local_secrets.json` and can be opened only through the internal helper.
- API tests prove store/governance/help responses do not return the stored value.
- Governance tests prove only eligible optional data providers get forms and paid providers remain blocked.
- Source-wall and live-safety tests remain mandatory before committing the milestone.

## Verification Result

- Focused local secret/governance tests: 12 passed.
- Full pytest: 194 passed.
- Source-wall/live-safety sweep: 12 passed.
- Ruff: passed.
- Frontend lint/build/E2E: passed, including 15 Playwright tests.
- UI evidence: `artifacts/screenshots/m20-24-settings-local-secret-store.png`.
- Code-review/security gate: passed after fixing explicit-consent default behavior before commit.
