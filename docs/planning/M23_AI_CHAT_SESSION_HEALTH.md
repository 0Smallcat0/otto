# M23.55 AI Chat Session Health Matrix

Date: 2026-05-31

## Scope

M23.55 deepens AI Chat AI Agent supervision without adding managed LLM,
provider, replay, or destructive artifact behavior. It adds a metadata-only
health matrix for local AI Chat sessions and transcript artifacts so an agent
can decide whether a session is ready for supervision before using context
contracts or creating a new local dry-run message.

## Product Behavior

- Added `GET /api/ai-chat/session-health`.
- Embedded `session_health` in `GET /api/ai-chat`.
- Added AI Chat UI selector `ai-chat-session-health`.
- Added AI Agent state field `session_health`.
- Added AI Agent action `ai_chat_session_health`.
- Command Center current milestone and provenance now point to this milestone.

The health matrix inventories local `artifacts/chat/{session_id}` metadata and
`messages.jsonl` file state without opening transcript content. Each row
reports session id, provider, active state, local paths, transcript existence,
byte size, declared message count, linked artifact count, `health_state`,
`supervision_ready`, and a non-mutating recovery hint.

## Safety Boundary

This slice is read-only and metadata-only. It does not read message content,
index transcript text, replay requests or responses, call managed LLMs, call
providers, repair files, delete sessions, persist credentials, route broker
actions, read balances, place orders, or enable live/private trading.

Creating a session or sending a local dry-run message remains an explicit
existing AI Chat action. In-place transcript repair, content indexing, durable
request/response replay, managed LLM execution, and destructive lifecycle
actions remain out of scope.

## Verification Plan

- AI Chat API tests cover empty, complete, and missing-transcript health states.
- Agent-contract tests cover `session_health` state and
  `ai_chat_session_health` action.
- Command Center tests cover current milestone/provenance and action-matrix
  visibility.
- Frontend E2E covers the AI Chat health selector and updated action count.
- Source-wall, live-safety, local-secret, and secret scans must remain clean.

## Verification Evidence

- Focused AI Chat/Agent/Command Center/ledger gate -> 22 passed.
- Full backend gate -> 371 passed.
- Full ruff -> passed.
- Frontend lint/build/e2e -> lint passed, build passed with the existing Vite
  chunk-size warning, E2E 15 passed after widening the two long route/Markets
  workflow test timeouts to 60 seconds.
- Source-wall/live-safety/local-secret/ledger gate -> 23 passed.
- FastAPI TestClient smoke confirmed `metadata_only_ai_chat_session_health`,
  embedded AI Chat health parity, Command Center action count `69`, preflight
  matrix rows `69`, one complete session, action endpoint
  `/api/ai-chat/session-health`, and no local secret-store file creation.
- Refined changed-diff secret scan found no known credential literals,
  credential assignments, bearer-token values, private-key blocks, protected
  value assignments, or provider-key assignments.
- `git diff --check` passed with Git CRLF working-copy warnings only.
