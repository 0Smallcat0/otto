# M20.19 Forum Artifact Health

Date: 2026-05-23

## Intent

Reduce Forum/Help governance drift by making Forum derivative artifacts inspectable and repairable from local state. `forum_state.json` remains the source of truth, while per-thread `post.json`, `replies.json`, and `thread.md` files are treated as derivative artifacts that can be checked and rewritten.

## Scope

- Add Forum artifact health to `/api/forum`: expected artifact count, missing artifacts, orphan directory review rows, and repair safety metadata.
- Add `/api/forum/repair-artifacts` to rewrite Forum derivative artifacts from validated local state.
- Add Forum artifact health to Help diagnostics and diagnostics reports.
- Surface artifact health, missing/orphan counts, and repair action in the Forum UI.
- Keep prune/delete behavior disabled pending a separate lifecycle contract.

## Safety

- Repair is non-destructive: it rewrites derivative files from local state and does not delete orphan directories.
- Invalid or corrupt `forum_state.json` blocks repair without overwriting state.
- No external network, cloud/community publishing, credential persistence, billing, subscription, CR/credits, private API, live order, real balance, margin, leverage, short, derivatives execution, installed source, runtime, asset, branding, or commercial-copy path was added.

## Verification

- `.\.venv\Scripts\python.exe -m pytest tests\test_m15_forum_help.py tests\test_m19_governance_routes.py -q` with repo-local TEMP/TMP -> 12 passed.
- `.\.venv\Scripts\python.exe -m pytest -q` with repo-local TEMP/TMP -> 183 passed.
- `.\.venv\Scripts\python.exe -m pytest tests\test_clean_room_source_wall.py tests\test_m16_live_safety.py -q` with repo-local TEMP/TMP -> 12 passed.
- `.\.venv\Scripts\python.exe -m ruff check .` -> passed.
- `npm run lint` -> passed.
- `npm run build` -> passed.
- `npm run e2e` -> 15 passed.
- `git diff --check` -> passed with Git CRLF working-copy warnings only.
- Screenshot evidence: `artifacts/screenshots/m20-19-forum-artifact-health.png`.

## Watch

Forum prune/archive deletion remains disabled. Add it only as a separate reviewed lifecycle milestone with confirmation gates, audit artifacts, and tests proving deletion stays under `artifacts/forum`.
