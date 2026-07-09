# M23.19 MOEX Delayed Quote Snapshots

Date: 2026-05-26

## Scope

M23.19 adds a bounded public no-key MOEX ISS delayed quote snapshot lane for
Markets provider breadth. It covers `SBER`, `GAZP`, and `MOEX` through the
official ISS shares marketdata JSON surface and stores normalized local caches
under `market_data/quotes/moex/`.

This is a delayed quote snapshot workflow for local research and AI Agent source
state. It is not an executable quote feed, broker/exchange binding, real balance
surface, margin, short, derivatives path, or live trading signal.

## Provider Gate Evidence

- Official/source pages checked on 2026-05-26:
  - `https://www.moex.com/a2920`
  - `https://www.moex.com/files/4be999zbzp80bx2bgmwayrtyx0`
- Live no-secret smoke against the ISS shares marketdata endpoint returned
  bounded `SBER`, `GAZP`, and `MOEX` rows on board `TQBR`.
- The implementation uses only delayed public marketdata snapshots and does not
  request authenticated realtime feeds, orderbooks, private account data, or
  trading connectivity.

## Implemented Behavior

- `src/local_terminal/moex_data.py` normalizes bounded MOEX ISS marketdata rows
  into non-orderable local quote snapshots with provider/source attribution,
  cache path, retrieved time, docs links, and `quote_semantics=quote_not_orderable`.
- `/api/moex/quote-snapshots` inspects local MOEX caches without network refresh.
- `/api/moex/quote-snapshots/refresh` refreshes bounded public no-key snapshots
  and writes per-symbol local caches.
- `/api/markets/moex/quotes/refresh` refreshes the same cache and returns the
  Markets source coverage matrix.
- `/api/markets` includes `research_summary.moex_quotes` and a
  `Multi-Asset/international_delayed_quote_snapshot` source coverage row.
- `/api/agent-contract` advertises `markets_moex_quote_snapshot_refresh`.
- `/api/providers/refresh-public` includes MOEX in the manual public no-key
  refresh job without reading or writing secrets.

## Clean-Room And Safety

- No Fincept branding, assets, commercial copy, runtime binary, or installed
  source was used.
- No credential value, provider key, broker key, private account, payment,
  signup, realtime feed, or orderbook flow was stored or requested.
- Rows are marked non-orderable and `live_action_enabled=false`.
- The milestone does not create broker/exchange connectivity or tradeability.

## Verification

Initial focused verification:

- `.\.venv\Scripts\python.exe -m pytest tests\test_m23_moex_quote_provider.py tests\test_m21_markets_source_coverage_matrix.py tests\test_m21_agent_operability_contract.py tests\test_m19_provider_registry.py tests\test_m22_provider_acquisition_gate.py tests\test_m22_command_center_contract.py -q --basetemp .omx\pytest-tmp\m23-19-focused-final`
  -> 35 passed.
- `.\.venv\Scripts\python.exe -m ruff check src\local_terminal\moex_data.py src\local_terminal\storage.py src\local_terminal\providers.py src\local_terminal\provider_acquisition.py src\local_terminal\markets.py src\local_terminal\server.py src\local_terminal\provider_refresh.py src\local_terminal\agent_contract.py src\local_terminal\command_center.py src\local_terminal\advanced_context.py tests\test_m23_moex_quote_provider.py tests\test_m19_provider_registry.py tests\test_m21_markets_source_coverage_matrix.py tests\test_m21_agent_operability_contract.py tests\test_m22_provider_acquisition_gate.py tests\test_m22_command_center_contract.py`
  -> passed.

Final verification before commit:

- Doc/contract gate
  `.\.venv\Scripts\python.exe -m pytest tests\test_m23_moex_quote_provider.py tests\test_m22_command_center_contract.py tests\test_m22_mission_ledger.py tests\test_m22_provider_acquisition_gate.py tests\test_m21_agent_operability_contract.py tests\test_m21_markets_source_coverage_matrix.py -q --basetemp .omx\pytest-tmp\m23-19-docs`
  -> 27 passed.
- Full backend gate
  `.\.venv\Scripts\python.exe -m pytest -q --basetemp .omx\pytest-tmp\m23-19-full-rerun`
  -> 313 passed.
- Full ruff `.\.venv\Scripts\python.exe -m ruff check .` -> passed.
- Frontend `npm run lint`, `npm run build`, and `npm run e2e` -> passed; build
  kept the existing Vite chunk-size warning and E2E result was 15 passed.
- Safety/source-wall/local-secret gate
  `.\.venv\Scripts\python.exe -m pytest tests\test_clean_room_source_wall.py tests\test_m16_live_safety.py tests\test_m20_local_secret_gate.py tests\test_m22_mission_ledger.py -q --basetemp .omx\pytest-tmp\m23-19-safety`
  -> 23 passed.
- FastAPI TestClient smoke confirmed MOEX refresh returned 3 rows, source
  coverage stayed `quote_not_orderable`, Command Center reported M23.19, AI
  Agent action contract exposed `markets_moex_quote_snapshot_refresh`, and no
  local secret store was created.
- In-app browser smoke opened `http://127.0.0.1:5173/#/markets` and confirmed
  the M23.19 milestone text, `MOEX` action, and MOEX source coverage row.
- `git diff --check` passed with Git CRLF working-copy warnings only.
- Changed-diff secret scan found no personal-account email literals,
  password/PIN literals, provider-key assignments, bearer-token values,
  private-key blocks, protected value markers, or credential assignments.

## Handoff

Do not broaden MOEX symbols, use authenticated realtime endpoints, add orderbook
semantics, or imply tradeability without a separate reviewed provider-entry and
safety gate. Continue to close one residual partial gap at a time from
`docs/planning/M22_MISSION_LEDGER.md`.
