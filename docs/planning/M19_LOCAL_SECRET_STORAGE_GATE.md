# M19 Local Secret Storage Gate

Purpose: define the gate that must pass before any optional-key data provider can collect or persist a user-owned provider key.

## Current State

- M20.7 adds a read-only gate contract in `src/local_terminal/secret_gate.py`.
- M20.24 enables a reviewed local secret store for eligible optional local-key data providers.
- `/api/secret-gate` and `/api/governance` expose `local_secret_store_ready` when Windows DPAPI storage is available.
- API value reads remain disabled; there is no HTTP endpoint that returns a stored value.
- Secret writes and key entry forms are enabled only for eligible optional local-key data providers.
- Secret persistence uses ignored local path `settings/local_secrets.json`, created only after explicit opt-in.
- Optional-key paid/plan-gated providers may appear in Settings as capability/setup rows, but they still must not expose key inputs or persist credentials.

## Required Before Enablement

1. Choose a local-only storage design with explicit redaction rules. Done in M20.24.
2. Add tests proving values never appear in tracked files, logs, screenshots, docs, diagnostics, reports, or commit messages. Covered by M20.24 tests and source-wall scans.
3. Add provider setup UX with explicit opt-in. Done in M20.24 for eligible optional data providers only.
4. Add source-wall checks for installed source/code/assets boundaries. Existing checks remain required.
5. Run code review and security review. Required before M20.24 commit.

M20.7 satisfied the read-only contract, redaction helper, governance propagation, disabled setup UX, and regression-test portion. M20.24 is the separate security-reviewed enablement milestone for eligible optional data providers only.

## Acceptance Test Shape

- Eligible optional data providers report `form_enabled=true` and paid/plan-gated optional providers report `form_enabled=false`.
- `/api/secret-gate` reports `writes_enabled=true` only for the scoped data-provider store, `reads_enabled=false`, `api_secret_value_reads_enabled=false`, and `secret_persistence_enabled=true`.
- `settings/local_secrets.json` does not exist by default and is created only after explicit opt-in.
- Disabled live/private routes remain disabled.
- Provider setup rows show docs/auth/cache/state metadata without exposing stored values.
