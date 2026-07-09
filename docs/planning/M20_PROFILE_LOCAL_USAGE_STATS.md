# M20 Profile Local Usage Stats

Date: 2026-05-23

## Scope

M20.21 replaces Profile's account-like billing/credits gap with local build and usage stats.

The route now reads `profile_usage` from the governance payload and displays local artifact metadata for backtests, paper ledger, portfolio, diagnostics, forum notes, chat, code workspace, Quant Lab, and QuantLib.

## Runtime Contract

- Source endpoint: `GET /api/governance`
- Payload branch: `profile_usage`
- Mode: `local_usage_stats`
- Build channel: `local_git_worktree`
- Inputs: repo-local artifact root metadata only.

## Safety Contract

- No cloud account identity.
- No billing identity.
- No subscription or credits.
- No private API identity.
- No artifact content reads.
- No secret scan.
- No external network.

## UI Evidence

- Profile route screenshot: `artifacts/screenshots/m20-21-profile-local-usage-stats.png`
- The screenshot shows build version/channel, local file counts, latest activity, per-artifact-root rows, billing/credits disabled state, and content-read safety.

## Verification

- `.\.venv\Scripts\python.exe -m pytest tests\test_m19_governance_routes.py tests\test_m2_local_state.py -q` with repo-local TEMP/TMP -> 11 passed.
- `.\.venv\Scripts\python.exe -m ruff check src\local_terminal\governance.py tests\test_m19_governance_routes.py` -> passed.
- `npm run lint` -> passed.
- `npm run build` -> passed.
- `npm run e2e` -> 15 passed.
- `.\.venv\Scripts\python.exe -m pytest -q` with repo-local TEMP/TMP -> 185 passed.
- `.\.venv\Scripts\python.exe -m pytest tests\test_clean_room_source_wall.py tests\test_m16_live_safety.py -q` with repo-local TEMP/TMP -> 12 passed.
- `.\.venv\Scripts\python.exe -m ruff check .` -> passed.

## Review Notes

This milestone intentionally avoids content indexing, secret scanning, account sync, billing analytics, and usage export. Those require separate reviewed contracts.
