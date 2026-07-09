# M23.16 Stooq Public Quote Snapshot

Date: 2026-05-26

## Scope

M23.16 adds a bounded public no-key Stooq quote snapshot lane for Markets provider
breadth. It covers `AAPL.US`, `SPY.US`, `^SPX`, and `EURUSD` through the Stooq
current quote CSV surface and stores normalized local caches under
`market_data/quotes/stooq/`.

This is a delayed/reference quote snapshot workflow. It is not an executable quote
feed, broker binding, real balance surface, margin/short/derivatives path, or live
trading signal.

## Provider Gate Evidence

- Official/source pages checked on 2026-05-26:
  - `https://stooq.com/q/?s=^spx`
  - `https://stooq.com/db/h/`
- Live no-secret smoke for the current quote CSV endpoint returned bounded CSV rows
  for `AAPL.US`, `SPY.US`, `^SPX`, and `EURUSD`.
- Stooq historical CSV download returned a `Get your apikey` flow with a CAPTCHA
  instruction. That historical download path is explicitly blocked and not
  implemented in this milestone.

## Implemented Behavior

- `src/local_terminal/stooq_data.py` normalizes bounded Stooq CSV quote snapshots
  into non-orderable local rows with source, provider, cache path, retrieved time,
  and `quote_semantics=quote_not_orderable`.
- `/api/stooq/quote-snapshots` inspects local Stooq caches without network refresh.
- `/api/stooq/quote-snapshots/refresh` refreshes bounded public no-key snapshots and
  writes per-symbol local caches.
- `/api/markets/stooq/quotes/refresh` refreshes the same cache and returns the
  Markets source coverage matrix.
- `/api/markets` includes `research_summary.stooq_quotes` and a
  `Multi-Asset/public_quote_snapshot` source coverage row.
- `/api/agent-contract` advertises `markets_stooq_quote_snapshot_refresh`.
- `/api/providers/refresh-public` includes Stooq in the manual public no-key refresh
  job without reading or writing secrets.

## Clean-Room And Safety

- No Fincept branding, assets, commercial copy, runtime binary, or installed source
  was used.
- No credential value, provider key, broker key, private account, payment, or signup
  flow was stored or requested.
- Historical Stooq download remains blocked because its observed flow requires a
  CAPTCHA/API-link gate.
- Quotes are marked non-orderable and `live_action_enabled=false`.

## Verification

Focused verification before docs:

- `.\.venv\Scripts\python.exe -m pytest tests\test_m23_stooq_quote_provider.py tests\test_m21_markets_source_coverage_matrix.py tests\test_m21_agent_operability_contract.py tests\test_m22_provider_acquisition_gate.py tests\test_m19_provider_registry.py tests\test_m2_local_state.py -q --basetemp .omx\pytest-tmp\m23-16-focused-final` -> 40 passed.
- `.\.venv\Scripts\python.exe -m ruff check src\local_terminal\stooq_data.py src\local_terminal\server.py src\local_terminal\markets.py src\local_terminal\storage.py src\local_terminal\providers.py src\local_terminal\provider_acquisition.py src\local_terminal\provider_refresh.py src\local_terminal\agent_contract.py src\local_terminal\advanced_context.py tests\test_m23_stooq_quote_provider.py tests\test_m19_provider_registry.py tests\test_m21_markets_source_coverage_matrix.py tests\test_m21_agent_operability_contract.py tests\test_m22_provider_acquisition_gate.py tests\test_m2_local_state.py` -> passed.

Final verification before commit:

- `.\.venv\Scripts\python.exe -m pytest tests\test_m23_stooq_quote_provider.py tests\test_m21_markets_source_coverage_matrix.py tests\test_m21_agent_operability_contract.py tests\test_m22_provider_acquisition_gate.py tests\test_m19_provider_registry.py tests\test_m2_local_state.py tests\test_m22_command_center_contract.py tests\test_m22_mission_ledger.py -q --basetemp .omx\pytest-tmp\m23-16-doc-contract` -> 46 passed.
- `.\.venv\Scripts\python.exe -m pytest -q --basetemp .omx\pytest-tmp\m23-16-full-final` -> 304 passed.
- `.\.venv\Scripts\python.exe -m ruff check .` -> passed.
- `npm run lint`, `npm run build`, and `npm run e2e` in `frontend/` -> passed; build kept the existing Vite chunk-size warning and E2E result was 15 passed.
- `.\.venv\Scripts\python.exe -m pytest tests\test_clean_room_source_wall.py tests\test_m16_live_safety.py tests\test_m20_local_secret_gate.py tests\test_m22_mission_ledger.py -q --basetemp .omx\pytest-tmp\m23-16-safety-final` -> 23 passed.
- FastAPI TestClient smoke confirmed Command Center current milestone, Stooq refresh, Markets source coverage, provider freshness, non-orderable quote semantics, and no local secret store creation.
- `git diff --check` -> passed with Git CRLF working-copy warnings only.
- Changed-diff secret scan found no personal-account email literals, password/PIN literals, provider-key assignments, bearer-token values, private-key blocks, protected value markers, or credential assignments.

## Handoff

Do not broaden Stooq symbols, scrape quote pages, or use the historical download
CAPTCHA/API-link path without a separate reviewed provider-entry gate. Continue to
close one residual partial gap at a time from `docs/planning/M22_MISSION_LEDGER.md`.
