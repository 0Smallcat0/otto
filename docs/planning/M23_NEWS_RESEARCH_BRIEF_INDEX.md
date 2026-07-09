# M23.21 News Research Brief Index

Date: 2026-05-26

## Scope

M23.21 adds a metadata-only local index for News research brief artifacts. It
lets a human supervisor or AI Agent see which local brief bundles exist, whether
the expected files are present, and which non-destructive action can regenerate a
missing bundle.

This milestone deepens News/Research artifact lifecycle visibility without
fetching full articles, copying article bodies, calling AI summary providers,
using paid/cloud news APIs, or enabling destructive archive/recovery actions.

## Implemented Behavior

- `news_research_brief_index` inventories `artifacts/news/research_briefs/`
  directories named `news-brief-*` using directory entries and file stats only.
- `GET /api/news/research-briefs` exposes the index with summary counts, brief
  rows, missing-artifact recovery hints, and safety flags.
- `/api/news`, `/api/news/layout`, `/api/news/refresh`, and
  `/api/news/research-brief` include `research_brief_index` in the public News
  payload.
- News UI shows a `news-research-brief-index` supervision strip and an `INDEX`
  control for refreshing the index without writing artifacts.
- `/api/agent-contract` advertises News state `research_brief_index` and action
  `news_research_brief_index`.
- Command Center provenance advances to this M23.21 milestone.

## Safety

- The index reads no article bodies and no brief JSON/Markdown content.
- It inspects only local directory names and file stats under the repository.
- Recovery output is advisory: regenerate the metadata-only brief with
  `news_research_brief`; no delete, move, restore, archive, provider signup,
  credential read, cloud sync, or live trading path is enabled.

## Verification

Final verification:

- `.\.venv\Scripts\python.exe -m pytest tests\test_m8_news.py tests\test_m21_agent_operability_contract.py tests\test_m22_command_center_contract.py tests\test_m22_mission_ledger.py -q --basetemp .omx\pytest-tmp\m23-21-docs`
  -> 21 passed.
- `.\.venv\Scripts\python.exe -m pytest -q --basetemp .omx\pytest-tmp\m23-21-full-rerun`
  -> 317 passed.
- `.\.venv\Scripts\python.exe -m ruff check .` -> passed.
- Changed-file ruff over News, server, Agent contract, Command Center, and
  focused tests -> passed.
- Frontend `npm run lint`, `npm run build`, and `npm run e2e` -> passed; build
  kept only the existing Vite chunk-size warning and E2E result was 15 passed.
- Source-wall/live-safety/local-secret gate
  `.\.venv\Scripts\python.exe -m pytest tests\test_clean_room_source_wall.py tests\test_m16_live_safety.py tests\test_m20_local_secret_gate.py tests\test_m22_mission_ledger.py -q --basetemp .omx\pytest-tmp\m23-21-safety`
  -> 23 passed.
- FastAPI TestClient smoke confirmed empty-index recovery queue, one generated
  News brief index, file/content-read safety flags, embedded News payload index,
  Command Center current milestone, AI Agent action contract, and no local
  secret-store creation.
- Changed-diff secret scan passed, and `git diff --check` passed with Git CRLF
  working-copy warnings only.

## Handoff

Future expansion can aggregate the News brief index into the global Command
Center recovery queue, but actual artifact repair, delete/move/restore, full
article copying, AI summarization, paid/cloud news providers, and automatic
recovery execution still require separate reviewed safety contracts.
