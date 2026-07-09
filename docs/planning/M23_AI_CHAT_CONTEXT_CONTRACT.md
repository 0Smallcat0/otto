# M23.27 AI Chat Context Contract

Date: 2026-05-26

## Scope

M23.27 turns the existing local AI Chat context brief into a tool-readable
context contract for AI Agent supervision. The slice does not add a managed LLM,
does not call providers, does not index artifact contents, and does not change
the existing dry-run assistant behavior. It only exposes the limits, source
citations, artifact provenance, output state, and safety flags that an agent or
human operator needs before using AI Chat as local context.

## Product Behavior

- `GET /api/ai-chat` now includes `context_contract`.
- `GET /api/ai-chat/context-contract` returns the same read-only contract
  without creating sessions, appending messages, calling providers, or reading
  artifact contents.
- The contract exposes prompt/session/artifact limits, active transcript state,
  metadata-only source citations, linked artifact provenance, indexed context
  artifact metadata, context summary, and explicit safety flags.
- AI Chat UI now exposes stable selector `ai-chat-context-contract` beside the
  existing Local Context panel.
- AI Agent contract now exposes route state `context_contract` and action
  `ai_chat_context_contract`.

## Current Baseline Evidence

With a seeded market cache and one linked Backtest summary artifact, the
contract reports:

- `mode=metadata_only_ai_chat_context_contract`.
- 4000 prompt characters and 8 linked-artifact limit.
- Two transcript messages after one user prompt and one local dry-run assistant
  reply.
- Source citation `ctx-source-1` for `market_ticker_cache`.
- Linked artifact provenance for
  `artifacts/backtests/run-1/summary.json`.
- Context artifact rows marked `read_mode=metadata_only`.
- Safety flags proving no provider calls, managed LLM, artifact content read,
  artifact content indexing, broker mutation, real orders, real balances, or
  live trading.

This keeps AI Chat richer for AI Agent operation while still bounded to local
dry-run context. Managed LLM behavior, full request/response replay, artifact
content indexing, and deep-agent workflow execution remain separate blocked
safety contracts.

## Clean-Room And Safety Boundaries

- No Fincept branding, assets, commercial copy, runtime binaries, installed
  source, or `D:\FinceptTerminal\app\scripts` were used.
- No provider signup, CAPTCHA bypass, payment, identity verification,
  credential flow, or external account access was started.
- No secret value is read or returned, and the endpoint does not create
  `settings/local_secrets.json`.
- No live trading, broker/exchange binding, real balances, margin, leverage,
  short exposure, derivatives, order submission, or destructive artifact
  lifecycle action is reachable.
- Artifact provenance is metadata-only. Chat transcript state is read to report
  output state, but external/local artifact contents are not indexed or read by
  this contract.

## Verification Plan

- Focused backend: AI Chat contract, AI Agent contract, Command Center contract.
- Frontend: TypeScript build, lint, and E2E selector checks.
- Safety: source wall, live safety, local secret gate, mission ledger.
- Full sweep: full backend pytest, full ruff, frontend build/lint/e2e,
  API smoke, diff check, and changed-diff secret scan.

## Verification Evidence

- Focused AI Chat/agent/command-center gate:
  `.\.venv\Scripts\python.exe -m pytest tests\test_m9_ai_chat.py tests\test_m21_agent_operability_contract.py tests\test_m22_command_center_contract.py -q --basetemp .omx\pytest-tmp\m23-27-focused-initial`
  -> 16 passed.
- Focused docs/ledger gate:
  `.\.venv\Scripts\python.exe -m pytest tests\test_m9_ai_chat.py tests\test_m21_agent_operability_contract.py tests\test_m22_command_center_contract.py tests\test_m22_mission_ledger.py -q --basetemp .omx\pytest-tmp\m23-27-docs`
  -> 20 passed.
- Full backend gate:
  `.\.venv\Scripts\python.exe -m pytest -q --basetemp .omx\pytest-tmp\m23-27-full`
  with repo-local TEMP/TMP -> 323 passed; full ruff passed.
- Frontend `npm run lint`, `npm run build`, and `npm run e2e` passed; build
  kept the existing Vite chunk-size warning and E2E result was 15 passed.
- Source-wall/live-safety/local-secret/ledger gate:
  `.\.venv\Scripts\python.exe -m pytest tests\test_clean_room_source_wall.py tests\test_m16_live_safety.py tests\test_m20_local_secret_gate.py tests\test_m22_mission_ledger.py -q --basetemp .omx\pytest-tmp\m23-27-safety`
  -> 23 passed.
- FastAPI TestClient smoke confirmed embedded AI Chat `context_contract`,
  dedicated context-contract endpoint, two local transcript messages after one
  dry-run prompt, safety flags denying provider calls / managed LLM / artifact
  content read / real orders, Command Center current milestone, AI Agent action
  contract, and no local secret-store creation.
- Changed-diff secret scan found no credential literals or assignments.
- `git diff --check` passed with Git CRLF working-copy warnings only.

## Handoff

Future AI Chat work should use this contract before making assistant behavior
richer. Do not add managed LLM calls, external provider calls, artifact content
indexing, durable request/response replay, autonomous recovery, notebook or
workflow execution, or live/private account access without a separate reviewed
safety contract and tests.
