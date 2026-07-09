# M22.7 News Research Brief

Date: 2026-05-25

## Objective

Deepen News/Research and artifact lifecycle output without adding article-body
scraping, AI summary calls, cloud/news subscriptions, provider signup, credentials,
or destructive archive/recovery behavior.

The bounded workflow is:

`News RSS/GDELT metadata cache -> current News layout -> public research summaries
-> local News research brief artifacts -> source-health recovery hints`.

## Implemented Scope

- Added `POST /api/news/research-brief`.
- The endpoint writes a metadata-only local artifact bundle under
  `artifacts/news/research_briefs/{brief_id}/`.
- The bundle contains `brief.json`, `source_health.json`, `manifest.json`, and
  `brief.md`.
- `brief.json` includes visible News items, topic rows, provider states, current
  layout, public research summaries, and safety flags.
- `source_health.json` records cache availability and non-destructive recovery
  hints for News provider cache paths.
- The News UI adds a `BRIEF` control and exposes the latest brief id, topic/item
  counts, missing cache count, and artifact path.
- The AI Agent contract advertises `research_brief`, `source_health`, and the
  `news_research_brief` action contract.

## Safety Boundary

- No full article pages are fetched.
- No article body is copied or stored.
- No AI summary call is made.
- No paid GDELT Cloud, NewsAPI, provider signup, credential, broker, live trading,
  cloud sync, or subscription path is added.
- Source-health recovery output is advisory and non-destructive; it does not
  delete, archive, move, restore, rewrite provider state, or mutate caches.

## Verification

- Focused tests:
  `.\.venv\Scripts\python.exe -m pytest tests\test_m8_news.py tests\test_m21_agent_operability_contract.py tests\test_m22_command_center_contract.py -q --basetemp .omx\pytest-tmp\m22-7-focused`
  -> 14 passed.
- Ruff:
  `.\.venv\Scripts\python.exe -m ruff check src\local_terminal\news.py src\local_terminal\server.py src\local_terminal\agent_contract.py src\local_terminal\command_center.py tests\test_m8_news.py tests\test_m21_agent_operability_contract.py tests\test_m22_command_center_contract.py`
  -> passed.
- Frontend typecheck:
  `npm run lint` from `frontend/` -> passed.
- Full backend:
  `.\.venv\Scripts\python.exe -m pytest -q --basetemp .omx\pytest-tmp\m22-7-full`
  -> 266 passed.
- Frontend build/e2e:
  `npm run build` and `npm run e2e` from `frontend/` -> passed
  (`npm run build` kept the existing Vite chunk-size warning).
- Safety/source:
  `.\.venv\Scripts\python.exe -m pytest tests\test_clean_room_source_wall.py tests\test_m16_live_safety.py tests\test_m20_local_secret_gate.py tests\test_m22_mission_ledger.py -q --basetemp .omx\pytest-tmp\m22-7-safety`
  -> 22 passed.
- `.\.venv\Scripts\python.exe -m ruff check .` -> passed.
- `git diff --check` -> passed with Git CRLF warnings only.
- Changed-file secret scan found no real credential, password, PIN, provider key,
  private key, or protected value.
