# M20.6 SEC Fund Ticker Registry For Markets ETF

Date: 2026-05-23

## Purpose

Reduce the Markets ETF empty-shell gap with a public no-key SEC fund ticker registry workflow. This milestone is reference data only: it gives the ETF tab real fund CIK, series, class, ticker, cache, source, and provider state while keeping ETF quote feeds disabled until a reviewed market-data provider and local secret gate exist.

## Official Source

- SEC EDGAR data access documentation: `https://www.sec.gov/edgar/searchedgar/accessing-edgar-data.htm`
- SEC fund ticker JSON file: `https://www.sec.gov/files/company_tickers_mf.json`
- Officially documented shape: `company_tickers_mf.json` provides fund CIK, series, class, and ticker.
- Auth mode: no-key.
- Rate/terms gate: daily local cache, declared User-Agent, source attribution, and SEC fair-access behavior.

## Implementation Notes

- Provider id: `sec_fund_ticker_registry_public`.
- Cache id: `funds_sec_tickers`.
- Cache path: `market_data/funds/sec/company_tickers_mf.json`.
- Runtime endpoint: `/api/funds`.
- Refresh endpoints: `/api/funds/refresh` and `/api/markets/etf/refresh`.
- Markets payload: top-level `etf` view plus `research_summary.funds`.
- UI: ETF tab now opens a route-specific fund registry panel instead of a setup-only card.

## Safety

- No ETF quote prices are synthesized or shown.
- ETF quote provider state remains `disabled_until_provider_gate`.
- No private API key, broker account, real balance, real order, margin, leverage, short, or derivatives path was added.
- Data is public read-only SEC reference data and is local-cache backed.

## Verification

- Focused tests added in `tests/test_m20_sec_fund_etf_provider.py`.
- Existing Markets provider tests were updated so ETF is a no-key provider-ready tab rather than setup-only.
- Focused sweep `.\.venv\Scripts\python.exe -m pytest tests\test_m20_sec_fund_etf_provider.py tests\test_m4_markets.py tests\test_m19_provider_registry.py tests\test_m2_local_state.py tests\test_m19_advanced_routes_context.py -q` with repo-local TEMP/TMP -> 22 passed.
- Source-wall sweep `.\.venv\Scripts\python.exe -m pytest tests\test_clean_room_source_wall.py tests\test_m20_sec_fund_etf_provider.py -q` with repo-local TEMP/TMP -> 10 passed.
- Full gate `.\.venv\Scripts\python.exe -m pytest -q` with repo-local TEMP/TMP -> 164 passed.
- `.\.venv\Scripts\python.exe -m ruff check .`, `npm run lint`, `npm run build`, `npm run e2e`, and `git diff --check` passed.
- UI evidence: `artifacts/screenshots/m20-6-markets-etf-fund-registry.png`.
