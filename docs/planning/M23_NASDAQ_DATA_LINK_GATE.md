# M23.60 Nasdaq Data Link Provider Gate

## Scope

M23.60 deepens provider-entry discipline by recording Nasdaq Data Link as a
blocked, dataset-specific provider candidate before any adapter work.

This slice does not implement a Nasdaq Data Link adapter, sign up for an
account, collect or store API keys, call catalog or dataset APIs, write provider
caches, activate premium datasets, route broker actions, or enable live/private
behavior.

## Official-Doc Findings

- Nasdaq Data Link offers free and premium datasets through streaming,
  real-time/delayed REST, and tables REST APIs.
- The current documentation says most datasets are premium and subscription
  gated, while some free/open datasets exist.
- Dataset product pages define which API route applies and whether the product
  is free or premium.
- Legacy Quandl/Nasdaq Data Link API documentation describes API-key
  authentication through user account settings.

## Product Delta

- Adds provider acquisition candidate `nasdaq_data_link_dataset_gate`.
- Updates provider acquisition `docs_checked_at` to `2026-05-31`.
- Keeps `implementation_allowed=false`, `approved_next_count=0`, and
  `resume_state=backlog_exhausted_needs_research`.
- Command Center now shows the Nasdaq Data Link blocked row before an AI Agent
  can select provider work.
- Command Center provenance moves to this milestone without changing the action
  count.

## Safety Contract

- No adapter, no signup, no bundled key, no catalog crawling, no data cache, no
  provider refresh entry, and no source-coverage row are added.
- A future implementation requires a separate provider-entry slice with a
  concrete free dataset product page, auth mode, API route, cache schema, quote
  semantics, route need, tests, and local-secret behavior if a user-owned key is
  required.
- Direct official public sources remain preferred when they satisfy the route
  need without Nasdaq Data Link account/key handling.

## Verification Plan

- Focused provider/Command Center/ledger gate
  `.\.venv\Scripts\python.exe -m pytest -q tests\test_m22_provider_acquisition_gate.py tests\test_m22_command_center_contract.py tests\test_m22_mission_ledger.py --basetemp .omx\pytest-tmp\m23-60-focused`
  -> 10 passed.
- Full backend
  `.\.venv\Scripts\python.exe -m pytest -q --basetemp .omx\pytest-tmp\m23-60-full-rerun`
  -> 375 passed after one tool timeout rerun.
- Ruff `.\.venv\Scripts\python.exe -m ruff check .` -> passed.
- Frontend `npm run lint` -> passed.
- Frontend `npm run build` -> passed with the existing Vite chunk-size warning.
- Frontend focused Command Center E2E
  `npm run e2e -- --grep "opens all routes"` -> 1 passed.
- Frontend full E2E final rerun `npm run e2e` -> 15 passed after one
  retry; the first run had a transient Help dialog sync assertion miss and 14
  other tests passed.
- Source-wall/live-safety/local-secret/provider safety gate
  `.\.venv\Scripts\python.exe -m pytest -q tests\test_clean_room_source_wall.py tests\test_m16_live_safety.py tests\test_m20_local_secret_gate.py tests\test_m22_provider_acquisition_gate.py --basetemp .omx\pytest-tmp\m23-60-safety`
  -> 22 passed.
- FastAPI smoke must confirm provider acquisition candidate count `19`, blocked
  count `3`, Nasdaq Data Link status `blocked_dataset_specific_gate`, Command
  Center milestone `M23.60 Nasdaq Data Link provider gate`, milestone path
  `docs/planning/M23_NASDAQ_DATA_LINK_GATE.md`, action count `73`, and no local
  secret-store creation -> passed.
- Changed-diff secret scan -> passed.
- `git diff --check` -> passed with Git CRLF working-copy warnings only.
