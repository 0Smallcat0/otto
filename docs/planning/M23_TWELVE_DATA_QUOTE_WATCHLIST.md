# M23.4 Twelve Data Quote Watchlist

Date: 2026-05-25

## Purpose

M23.4 closes one narrow non-live quote-breadth residual by adding a second
comparison-gated optional-key quote provider. It does not expand Alpha Vantage,
does not add public no-key refresh work, and does not make any quote row
orderable.

## Scope

- Provider: `twelve_data_quote_optional_key`.
- Official source: Twelve Data `/quote`.
- Runtime role: `quote_watchlist_secondary`.
- Auth mode: `optional_local_key`.
- Default symbols: `AAPL`, `SPY`, `EUR/USD`.
- Cache path: `market_data/quotes/twelve_data/{symbol}.json`.
- Quote semantics: `quote_not_orderable`.
- Safe action: `markets_twelve_data_quote_watchlist_refresh`.

Out of scope:

- Signup, provider-key acquisition, unused key collection, payment, subscription,
  CR/credits, cloud sync, broker/exchange binding, real balances, live orders,
  margin, leverage, short exposure, derivatives, or destructive actions.
- Batch, bulk, paid, realtime-entitlement, or private-account endpoints.
- Treating reference, macro, filing, registry, or fundamental data as quotes.

## Product Behavior

- `twelve_data.py` normalizes Twelve Data `/quote` payloads into bounded
  multi-asset quote rows with source/cache/docs attribution,
  `quote_not_orderable`, and `live_action_enabled=False`.
- `LocalStateStore` reads/writes per-symbol Twelve Data quote caches under the
  local ignored market-data root.
- FastAPI exposes `/api/twelve-data/quotes`,
  `/api/twelve-data/quotes/refresh`, and
  `/api/markets/twelve-data/quotes/refresh`.
- `/api/markets` now includes `research_summary.twelve_data_quotes`, and the
  source coverage matrix adds a `Multi-Asset / quote_watchlist_secondary` row
  gated by `local_secret_required` until a reviewed local Twelve Data key exists.
- Provider registry health includes `twelve_data_quote_AAPL`,
  `twelve_data_quote_SPY`, and `twelve_data_quote_EURUSD` cache states while the
  provider stays classified as optional local secret data.
- The AI Agent contract exposes `twelve_data_quote_watchlist` state and the
  `markets_twelve_data_quote_watchlist_refresh` action contract.
- Command Center current milestone provenance points to this document.

## Official Evidence

- Twelve Data LLM documentation: `https://twelvedata.com/docs/llms`
- Twelve Data market-data documentation:
  `https://twelvedata.com/docs/llms/market-data`

The reviewed endpoint shape is `/quote` with `symbol`, JSON format, and a
user-owned API key. The official docs state that quote requests cost one API
credit per symbol, so the implementation stays bounded to a small watchlist and
daily local caches.

## Verification

- `.\.venv\Scripts\python.exe -m pytest tests\test_m23_twelve_data_quote_provider.py -q --basetemp .omx\pytest-tmp\m23-4-twelve-rerun` -> 5 passed.
- `.\.venv\Scripts\python.exe -m pytest tests\test_m21_markets_source_coverage_matrix.py tests\test_m21_agent_operability_contract.py tests\test_m19_provider_registry.py tests\test_m2_local_state.py tests\test_m22_provider_acquisition_gate.py tests\test_m22_command_center_contract.py -q --basetemp .omx\pytest-tmp\m23-4-contracts-rerun` -> 34 passed.
- `.\.venv\Scripts\python.exe -m pytest -q --basetemp .omx\pytest-tmp\m23-4-full-current` -> 279 passed.
- `.\.venv\Scripts\python.exe -m ruff check .` -> passed.
- `npm run lint`, `npm run build`, and `npm run e2e` in `frontend/` -> passed; build kept only the existing Vite chunk-size warning and E2E result was 15 passed.
- FastAPI TestClient smoke for `/api/twelve-data/quotes`, `/api/twelve-data/quotes/refresh`, `/api/markets/twelve-data/quotes/refresh`, `/api/markets`, `/api/agent-contract`, `/api/providers`, and `/api/command-center` -> all 200; state was `key_required`, source row was `quote_not_orderable`, and Command Center reported `M23.4 Twelve Data quote watchlist`.
- Changed-file redacted secret scan found only existing verification text and negative `api_key=`/`protected_value` assertions; no credential values, personal email literals, or provider keys were added.
- `git diff --check` -> passed with Git CRLF working-copy warnings only.

## Residuals

- This adds a bounded secondary quote provider only. Broad multi-asset quote
  parity is still partial and should continue one provider-entry gate at a time.
- Twelve Data remains optional-key and quota/plan-sensitive. No signup, key
  generation, payment activation, or secret storage outside the existing local
  secret gate was attempted.
