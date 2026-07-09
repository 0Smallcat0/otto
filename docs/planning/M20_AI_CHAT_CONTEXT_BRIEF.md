# M20.14 AI Chat Local Context Brief

Date: 2026-05-23

## Purpose

Reduce AI Chat empty-shell feel while preserving the local dry-run safety boundary. The route should answer from the existing provider/cache and local artifact context instead of only acknowledging that a message was stored.

## Runtime Surface

- Assistant responses now produce a local context brief with request digest, provider/cache readiness, primary cache path, latest price when available, focused source rows, linked artifact metadata, indexed local artifacts, and explicit safety text.
- Focused source selection ranks provider/cache sources by prompt terms such as backtest, portfolio, crypto, macro, and news, then falls back to ready sources.
- AI Chat side context now lists indexed local artifacts alongside provider/cache sources so users can see what the local assistant can inspect.
- Linked artifacts remain read-only and must stay under allowed local artifact/cache paths with allowed extensions and hash/size validation.

## Safety

This milestone adds no managed LLM, cloud account, subscription, CR/credits, private API key flow, credential persistence, broker mutation, ledger mutation, real balance read, real order, margin, leverage, short exposure, derivatives execution, billing, installed-source read, or Fincept branding/assets/copy.

## Verification

- Focused AI Chat/context gate `.\.venv\Scripts\python.exe -m pytest tests\test_m9_ai_chat.py tests\test_m19_advanced_routes_context.py -q` with repo-local TEMP/TMP -> 10 passed.
- Focused Python lint `.\.venv\Scripts\python.exe -m ruff check src\local_terminal\chat.py tests\test_m9_ai_chat.py tests\test_m19_advanced_routes_context.py` -> passed.
- Format check `.\.venv\Scripts\python.exe -m ruff format --check src\local_terminal\chat.py tests\test_m9_ai_chat.py tests\test_m19_advanced_routes_context.py` -> passed after formatting changed Python files.
- Frontend lint `npm run lint` -> passed.
- Full backend gate `.\.venv\Scripts\python.exe -m pytest -q` with repo-local TEMP/TMP -> 180 passed.
- Source-wall/live-safety gate `.\.venv\Scripts\python.exe -m pytest tests\test_clean_room_source_wall.py tests\test_m16_live_safety.py -q` with repo-local TEMP/TMP -> 12 passed.
- Repo lint `.\.venv\Scripts\python.exe -m ruff check .` -> passed.
- Frontend build `npm run build` -> passed.
- Frontend E2E `npm run e2e` -> 15 passed.
- `git diff --check` -> passed with Git CRLF working-copy warnings only.
- E2E captures `artifacts/screenshots/m20-14-ai-chat-context-brief.png`.
- Browser/Playwright screenshot was visually inspected for local context brief, provider/cache source rows, context artifacts, linked artifact metadata, and no incoherent overlap.
- Changed-file credential-like string scan found no real credential, PIN, provider-key, private-key, or personal-account literal; matches were existing safety wording and synthetic redaction-test probes only.
- Code-review gate found no CRITICAL/HIGH/BLOCK findings. WATCH: AI Chat remains a deterministic local context brief; future richer assistant behavior should add a structured local answer schema and artifact lifecycle before any optional external/provider-key path.
