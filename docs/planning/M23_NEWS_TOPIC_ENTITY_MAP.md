# M23.41 News Topic Entity Map

Date: 2026-05-26

## Scope

Add metadata-only News topic/entity supervision for AI Agents without adding a
provider, reading full article bodies, copying article content, calling AI
summarizers, writing artifacts, or enabling destructive recovery.

## Product Behavior

- `GET /api/news/topic-entity-map` returns a read-only
  `news_topic_entity_map_v1` contract derived from the current News payload.
- `GET /api/news` embeds `topic_entity_map` beside the existing intel strip and
  research brief index.
- The map reports topic rows, entity rows, topic/entity edges, provider states,
  recommended next actions, and explicit safety flags.
- The News UI exposes `data-testid="news-topic-entity-map"` and a `MAP` action
  for human supervision of what the AI Agent is inspecting.
- The AI Agent contract exposes News state field `topic_entity_map` and action
  `news_topic_entity_map`.

## Boundaries

- No provider refresh is performed by the topic/entity endpoint.
- No News research brief, source-health, or manifest artifact is written.
- No article body, article page, artifact content, credential, paid/cloud news,
  subscription, live trading, broker/exchange, balance, margin, leverage, short,
  derivatives, or destructive lifecycle path is enabled.

## Verification

- Focused News/agent/Command Center gate
  `.\.venv\Scripts\python.exe -m pytest tests\test_m8_news.py tests\test_m21_agent_operability_contract.py tests\test_m22_command_center_contract.py -q --basetemp .omx\pytest-tmp\m23-41-focused-initial`
  -> 19 passed.
- Focused ruff over News topic map, server, agent contract, Command Center, and
  focused tests -> passed.
- Frontend `npm run lint` -> passed.
- Docs/ledger gate
  `.\.venv\Scripts\python.exe -m pytest tests\test_m8_news.py tests\test_m21_agent_operability_contract.py tests\test_m22_command_center_contract.py tests\test_m22_mission_ledger.py -q --basetemp .omx\pytest-tmp\m23-41-docs`
  -> 23 passed.
- Frontend `npm run build` -> passed with the existing Vite chunk-size warning.
- Frontend `npm run e2e` -> 15 passed.
- Source-wall/live-safety/local-secret/ledger gate
  `.\.venv\Scripts\python.exe -m pytest tests\test_clean_room_source_wall.py tests\test_m16_live_safety.py tests\test_m20_local_secret_gate.py tests\test_m22_mission_ledger.py -q --basetemp .omx\pytest-tmp\m23-41-safety`
  -> 23 passed.
- Full backend gate
  `.\.venv\Scripts\python.exe -m pytest -q --basetemp .omx\pytest-tmp\m23-41-full`
  -> 347 passed.
- Full ruff `.\.venv\Scripts\python.exe -m ruff check .` -> passed.
- Local smoke confirmed backend health 200, frontend root 200,
  `/api/news/topic-entity-map` payload `news_topic_entity_map_v1`, and
  browser-visible News selector `news-topic-entity-map` with shell milestone
  `M23.41 News topic/entity map`.
