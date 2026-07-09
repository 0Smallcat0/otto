# M23.18 Nasdaq Trader Symbol Discovery

Date: 2026-05-26

## Scope

M23.18 turns the M23.17 Nasdaq Trader symbol-directory cache into a small
symbol-discovery workflow for AI Agent and human supervision in Markets Stocks.
It reuses the existing public no-key cache and adds local search/read surfaces;
it does not add a new provider, quote feed, broker/exchange binding, balance
source, or orderability.

## Implemented Behavior

- `nasdaq_trader_symbol_search_payload` searches the existing local
  symbol-directory payload by symbol, CQS/Nasdaq alternate symbol, or security
  name with a capped result limit.
- Public/local read endpoints:
  - `GET /api/nasdaq-trader/symbol-directory/search?query=AAPL&limit=12`
  - `GET /api/markets/nasdaq-trader/symbols/search?query=AAPL&limit=12`
- Markets Stocks now exposes `symbol_directory_status`, `symbols`, and
  `symbol_search` state, plus a `Symbol Discovery` UI panel with stable selector
  `markets-stocks-symbol-discovery`.
- AI Agent contract now exposes `nasdaq_trader_symbol_search` state and safe
  action `markets_nasdaq_symbol_directory_search`.
- The existing `SYMBOLS` toolbar action refreshes only the public no-key
  symbol-directory cache.

## Safety

- Search reads local reference metadata only.
- Search result rows are `not_quote`, `orderable=false`, and
  `live_action_enabled=false`.
- No credential, secret store, provider signup, payment, private account,
  broker/exchange, real balance, live order, margin, leverage, short exposure,
  derivatives, cloud sync, Fincept branding, installed-source read, or
  destructive artifact action is added.

## Verification

Initial focused verification:

- `.\.venv\Scripts\python.exe -m pytest tests\test_m23_nasdaq_trader_symbol_directory.py tests\test_m21_agent_operability_contract.py tests\test_m20_sec_stocks_fundamentals.py -q --basetemp .omx\pytest-tmp\m23-18-focused-rerun`
  -> 15 passed.
- Broader contract gate
  `.\.venv\Scripts\python.exe -m pytest tests\test_m23_nasdaq_trader_symbol_directory.py tests\test_m21_agent_operability_contract.py tests\test_m20_sec_stocks_fundamentals.py tests\test_m20_alpha_vantage_quote_provider.py tests\test_m21_markets_source_coverage_matrix.py tests\test_m22_command_center_contract.py -q --basetemp .omx\pytest-tmp\m23-18-contract-rerun`
  -> 40 passed.
- Changed-file ruff over Nasdaq Trader, server, Markets, Agent contract, and
  focused tests -> passed.
- Frontend `npm run lint` -> passed.
- Doc/contract gate
  `.\.venv\Scripts\python.exe -m pytest tests\test_m23_nasdaq_trader_symbol_directory.py tests\test_m21_agent_operability_contract.py tests\test_m20_sec_stocks_fundamentals.py tests\test_m20_alpha_vantage_quote_provider.py tests\test_m21_markets_source_coverage_matrix.py tests\test_m22_command_center_contract.py tests\test_m22_mission_ledger.py -q --basetemp .omx\pytest-tmp\m23-18-doc-contract`
  -> 44 passed.
- Full backend gate
  `.\.venv\Scripts\python.exe -m pytest -q --basetemp .omx\pytest-tmp\m23-18-full-final`
  -> 308 passed.
- Full ruff `.\.venv\Scripts\python.exe -m ruff check .` -> passed.
- Frontend `npm run build` and `npm run e2e` -> passed; build kept the
  existing Vite chunk-size warning and E2E result was 15 passed.
- Safety/source-wall/local-secret gate
  `.\.venv\Scripts\python.exe -m pytest tests\test_clean_room_source_wall.py tests\test_m16_live_safety.py tests\test_m20_local_secret_gate.py tests\test_m22_mission_ledger.py -q --basetemp .omx\pytest-tmp\m23-18-safety-final`
  -> 23 passed.
- FastAPI TestClient smoke confirmed public symbol refresh, cache-only search
  result `IBM`, Markets default search result `AAPL`, Command Center current
  milestone, AI Agent action contract, `not_quote` semantics,
  `orderable=false`, and no local secret-store creation.
- `git diff --check` passed with Git CRLF warnings only.
- Changed-diff secret scan found no personal-account email literals,
  password/PIN literals, provider-key assignments, bearer-token values,
  private-key blocks, protected value markers, or credential assignments.

## Handoff

Do not treat symbol discovery as quote routing, security master completeness,
broker availability, exchange connectivity, balances, or tradeability. Future
symbol lookup expansion can add sorting/filter facets and local watchlist
handoff, but quote/provider routing still needs separate provider-entry gates.
