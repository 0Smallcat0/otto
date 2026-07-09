# M21.16 SEC Company Submissions

Date: 2026-05-25

## Scope

Add official SEC EDGAR company submissions as a public no-key, read-only Stocks
reference provider. The slice deepens the Stocks route with recent filing metadata
while keeping quote, broker, account, and trading execution paths separate.

## Official Source

- SEC EDGAR APIs: `https://www.sec.gov/search-filings/edgar-application-programming-interfaces`
- Endpoint shape: `https://data.sec.gov/submissions/CIK##########.json`
- Auth mode: no-key.
- Safety class: public read-only company filings.

## Fincept Observation Boundary

The installed app was opened for safe workflow observation and remained at the
recover-session screen. No login, credential entry, account screenshot, or sensitive
state capture was performed. Existing sanitized Markets and News evidence showed the
target workflow shape: dense multi-panel route layout, source/provider status rows,
quick action buttons, and reference/news-like filing context rather than a sparse
single-card view.

## Implementation

- Added `sec_company_submissions_public` to provider research metadata and provider
  freshness/cache state.
- Added SEC submissions fetch/normalize/cache support using the default public AAPL
  CIK path `market_data/fundamentals/sec/0000320193/submissions.json`.
- Added normalized filing rows with form, filing date, report date, accession number,
  primary document, SEC filing URL, source/docs/cache attribution, and
  `reference_only: true`.
- Added Markets Stocks `filings_status`, filing summary fields, and a dense Recent
  Filings panel with `data-testid="markets-stocks-sec-filings"`.
- Added AI Agent state field `stock_company_filings` and provider refresh lifecycle
  result coverage.

## Out Of Scope

- No real-time stock quotes, paid bulk quotes, private provider keys, broker/exchange
  keys, real balances, live orders, margin, leverage, short exposure, derivatives, or
  trading controls.
- No Fincept source, branding, assets, commercial copy, subscription, CR/credits, or
  runtime binaries.
- No fixture/default filing rows as primary runtime. Test fixtures are used only in
  automated tests.

## Verification

- Focused backend gate:
  `.\.venv\Scripts\python.exe -m pytest tests\test_m20_sec_stocks_fundamentals.py tests\test_m19_news_macro_fundamentals.py tests\test_m19_provider_registry.py tests\test_m21_bls_macro_provider.py tests\test_m21_agent_operability_contract.py tests\test_m2_local_state.py -q`
  -> 33 passed; the first Windows default TEMP run emitted a pytest atexit cleanup
  warning after pass, so full gates used repo-local TEMP/TMP and `--basetemp`.
- Full backend gate:
  `.\.venv\Scripts\python.exe -m pytest -q --basetemp .tmp\pytest-m21-16-full`
  with repo-local TEMP/TMP -> 240 passed.
- Source-wall/live-safety gate:
  `.\.venv\Scripts\python.exe -m pytest tests\test_clean_room_source_wall.py tests\test_m16_live_safety.py -q --basetemp .tmp\pytest-m21-16-safety`
  with repo-local TEMP/TMP -> 12 passed.
- Full ruff: `.\.venv\Scripts\python.exe -m ruff check .` -> passed.
- Frontend lint/build/e2e: `npm run lint`, `npm run build`, and `npm run e2e`
  in `frontend/` -> passed; E2E passed 15 tests after stopping manual
  Browser-smoke dev servers that occupied ports 8765 and 5173.
- Browser smoke opened Markets Stocks after public refresh and confirmed
  `SEC_COMPANY_SUBMISSIONS RECENT FILINGS 12 rows` with SEC filing rows visible.
- Screenshot evidence: `artifacts/screenshots/m21-sec-company-submissions-stocks.png`
  after Playwright/browser verification.
- Visual verdict evidence:
  `.omx/state/m21-sec-company-submissions/ralph-progress.json` with pass score 91.
- Generic high-risk secret scan over changed/untracked text files returned zero
  matches for credential assignment, bearer token, provider key prefix, and private
  key block patterns.
- `git diff --check` -> passed with Git CRLF working-copy warnings only.
- Code-review gate -> COMMENT with code-reviewer APPROVE and no
  CRITICAL/HIGH/MEDIUM/LOW findings. Architecture WATCH: filings can currently
  become the Stocks route gateway/headline status when no quote/fundamental lane
  is primary, the submissions cache is intentionally fixed to the default AAPL
  CIK slice, and provider refresh still reports `cache_written` from cache
  availability rather than a strict this-run write.
