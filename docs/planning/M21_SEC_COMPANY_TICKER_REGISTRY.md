# M21.13 SEC Company Ticker Registry For Markets Stocks

Date: 2026-05-25

## Purpose

Reduce the Markets Stocks parity gap by adding a public no-key SEC company ticker registry workflow. This gives the Stocks tab a broader issuer universe with ticker, CIK, company name, cache state, provider state, and source attribution while keeping stock quote refresh behind the existing optional local Alpha Vantage key gate.

This is reference data only. It must not be treated as realtime stock quotes, orderable instruments, account holdings, or broker/exchange connectivity.

## Fincept Observation Evidence

- Existing sanitized Fincept evidence: `docs/reference/fincept-platform-test/screenshots/subfeatures/markets/main-visual.png`.
- Existing sanitized UI log: `docs/reference/fincept-platform-test/logs/markets-deep-ui-elements.json`.
- Relevant observed pattern: a dense Markets workspace with multiple asset panels, compact source/status row, configurable panels, `[F5] REFRESH`, `[F9] AUTO`, `[+] PANEL`, `[COLS]`, `[EDIT]`, `[DEL]`, and broad categories including Stock Indices, ETFs, Bonds, Forex, Commodities, Cryptocurrencies, China, India, and United States.
- Local replication choice: expand the Stocks route from single-company SEC facts into a registry-backed issuer table plus separate fundamentals and quote-provider panels.

## Official Source

- SEC EDGAR APIs: `https://www.sec.gov/search-filings/edgar-application-programming-interfaces`
- SEC EDGAR data access: `https://www.sec.gov/edgar/searchedgar/accessing-edgar-data.htm`
- SEC company ticker JSON file: `https://www.sec.gov/files/company_tickers.json`
- Officially documented shape: `company_tickers.json` provides ticker, CIK, and EDGAR conformed company name associations.
- Auth mode: no-key.
- Rate/terms gate: daily local cache, declared User-Agent, source attribution, and SEC fair-access behavior.

## Implementation Notes

- Provider id: `sec_company_ticker_registry_public`.
- Cache id: `equities_sec_company_tickers`.
- Cache path: `market_data/fundamentals/sec/company_tickers.json`.
- Runtime refresh: `/api/markets/stocks/refresh` refreshes both SEC companyfacts and the SEC company ticker registry.
- Markets payload: `stocks.registry`, `stocks.registry_status`, `stocks.summary.registry_*`, and `research_summary.equity_registry`.
- Provider lifecycle: `/api/providers` and `/api/providers/refresh-public` now track the company ticker registry as a public no-key provider.
- UI: Stocks column 1 is now a registry table; column 2 keeps SEC company facts; column 3 keeps Alpha Vantage quote state plus Provider Stack and Source Contract panels.

## Safety

- No stock quote prices are synthesized or shown from the SEC registry.
- No provider key collection, broker/exchange key flow, real balance read, real order path, margin, leverage, short exposure, derivatives, cloud account, billing, subscription, CR/credits, Fincept branding, runtime binary, installed-source read, or fixture-primary runtime was added.
- The Alpha Vantage quote workflow remains optional-key and local-secret gated.

## Verification

- Focused backend gate: `.\.venv\Scripts\python.exe -m pytest tests\test_m20_sec_stocks_fundamentals.py tests\test_m19_news_macro_fundamentals.py tests\test_m2_local_state.py tests\test_m19_provider_registry.py tests\test_m21_bls_macro_provider.py tests\test_m21_agent_operability_contract.py -q` -> 32 passed.
- Targeted Python lint: `.\.venv\Scripts\python.exe -m ruff check ...` -> passed.
- Frontend typecheck: `npm run lint` in `frontend/` -> passed.
- Frontend build: `npm run build` in `frontend/` -> passed.
- Full backend gate: `.\.venv\Scripts\python.exe -m pytest -q --basetemp .tmp\pytest-m21-13-full` with repo-local TEMP/TMP -> 235 passed.
- Source-wall/live-safety gate: `.\.venv\Scripts\python.exe -m pytest tests\test_clean_room_source_wall.py tests\test_m16_live_safety.py -q --basetemp .tmp\pytest-m21-13-safety` with repo-local TEMP/TMP -> 12 passed.
- Full Python lint: `.\.venv\Scripts\python.exe -m ruff check .` -> passed.
- Frontend E2E: `npm run e2e` in `frontend/` -> 15 passed.
- Browser smoke: Markets Stocks showed `SEC Company Registry`, `markets-stocks-provider-stack`, and `markets-stocks-source-contract` after live SEC public refresh.
- Visual verdict: pass, score 92, recorded in `.omx/state/m21-sec-company-ticker-registry/ralph-progress.json`.
- Generic high-risk secret scan over changed/untracked files -> zero matches.
- `git diff --check` -> passed with Git CRLF working-copy warnings only.
- Code-review gate -> APPROVE with architectural status CLEAR and no CRITICAL/HIGH/MEDIUM/LOW findings after stale handoff wording was corrected.
