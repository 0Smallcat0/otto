# M21.19 Stock Filings Watchlist

Date: 2026-05-25

## Scope

M21.19 expands the Markets Stocks SEC recent-filings lane from a single default
company cache to a bounded `AAPL/MSFT/NVDA` watchlist.

This is a clean-room, local-only provider-depth slice. It uses SEC public
no-key EDGAR submissions metadata, not filing bodies, executable quotes, paid
data, broker state, or Fincept implementation source.

## Evidence

- Official SEC EDGAR API documentation:
  https://www.sec.gov/search-filings/edgar-application-programming-interfaces
  confirms `data.sec.gov/submissions/CIK##########.json` exposes per-CIK
  submissions metadata without authentication or API keys.
- Official SEC EDGAR data-access guidance:
  https://www.sec.gov/edgar/searchedgar/accessing-edgar-data.htm records
  fair-access limits and the declared `User-Agent` requirement.
- Sanitized installed-app observation on 2026-05-25 confirmed only that the
  original terminal exposes dense market/data surfaces; no raw UI text, account
  data, screenshots, credentials, billing, subscription, or commercial copy were
  recorded.

## Implementation

- `research_data` now normalizes a SEC submissions watchlist aggregate while
  preserving the existing single-company payload contract.
- `storage` now reads and writes per-CIK submissions caches under
  `market_data/fundamentals/sec/{cik}/submissions.json`.
- `/api/markets/stocks/refresh` can persist watchlist filings for
  `AAPL/MSFT/NVDA` when the fetcher returns per-symbol SEC submissions payloads.
- Markets Stocks now exposes `filing_symbols`, `filing_company_count`,
  `latest_filing_symbol`, and per-symbol rows in the Recent Filings panel.
- Provider refresh manifests and the AI Agent contract now identify the bounded
  filings watchlist instead of implying a single-company filings cache.

## Safety

- No credentials, provider signup, paid data, billing, subscription, cloud
  account behavior, broker/exchange keys, real balances, order paths, margin,
  leverage, short exposure, derivatives, Fincept branding, installed-source
  reads, runtime copying, or fixture-primary runtime were added.
- SEC rows remain reference-only metadata and cannot trigger live or paper
  orders.
- Missing watchlist caches degrade to explicit unavailable/stale states.

## Verification

- Focused backend/provider/agent tests:
  `.\.venv\Scripts\python.exe -m pytest tests\test_m20_sec_stocks_fundamentals.py tests\test_m19_news_macro_fundamentals.py tests\test_m19_provider_registry.py tests\test_m21_agent_operability_contract.py -q --basetemp .tmp\pytest-m21-19-focused`
  -> 24 passed.
- Targeted ruff over changed backend/tests -> passed.
- Frontend lint/build -> passed.
- Review-fix gate for per-CIK filings cache summaries:
  `.\.venv\Scripts\python.exe -m pytest tests\test_m20_sec_stocks_fundamentals.py tests\test_m2_local_state.py -q --basetemp .tmp\pytest-m21-19-review-fix`
  -> 12 passed.
- Full backend pytest:
  `.\.venv\Scripts\python.exe -m pytest -q --basetemp .tmp\pytest-m21-19-full-final`
  -> 242 passed.
- Source-wall/live-safety:
  `.\.venv\Scripts\python.exe -m pytest tests\test_clean_room_source_wall.py tests\test_m16_live_safety.py -q --basetemp .tmp\pytest-m21-19-safety-final`
  -> 12 passed.
- Full ruff -> passed.
- Frontend e2e -> 15 passed.
- Browser screenshot:
  `artifacts/screenshots/m21-stock-filings-watchlist.png`.
- Visual verdict -> pass, score 91, recorded under
  `.omx/state/m21-stock-filings-watchlist/ralph-progress.json`.
- Secret scan -> 0 high-risk matches.
- `git diff --check` -> passed with Git CRLF working-copy warnings only.
- Local code-review gate -> APPROVE after fixing per-CIK cache summary drift.
