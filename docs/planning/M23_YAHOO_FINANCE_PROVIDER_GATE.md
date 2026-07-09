# M23.66 Yahoo Finance Provider Gate

## Scope

M23.66 records Yahoo Finance as a blocked provider-entry candidate before any
Yahoo market-data adapter work.

This slice does not implement a Yahoo Finance adapter, use query/chart/quote
endpoints, scrape pages, handle crumb/cookie flows, sign up, collect or store
credentials, call Yahoo APIs, write provider caches, add refresh jobs, add
source coverage rows, route broker actions, or enable live/private behavior.

## Official-Doc Findings

- Yahoo API terms describe Yahoo APIs as licensed API surfaces governed by the
  Yahoo API terms, guidelines, and API-specific implementation documentation.
- Yahoo API use is rate-limited at Yahoo's discretion and can require
  application registration or confirmation that a use case is acceptable.
- Yahoo Developer Network privacy materials say Yahoo Web Services require an
  Application ID and that each request must include that Application ID.
- Yahoo commercial API terms require Yahoo API Credentials for covered API
  access and place responsibility on the credential/account holder.
- The reviewed official materials do not provide a concrete Yahoo Finance
  market-data API contract suitable for unattended local no-key quote caching.

## Product Delta

- Adds provider acquisition candidate `yahoo_finance_market_data_gate`.
- Updates provider acquisition `docs_checked_at=2026-06-01`.
- Keeps `implementation_allowed=false`, `approved_next_count=0`, and
  `resume_state=backlog_exhausted_needs_research`.
- Command Center current milestone/provenance now points to this provider gate.
- No Yahoo cache, refresh endpoint, provider registry row, source coverage row,
  local-secret eligibility, UI quote lane, crumb/cookie flow, or external data
  fetch is added.

## Safety Contract

- Future Yahoo Finance work needs a separate provider-entry slice with a
  concrete official finance API contract, auth mode, route need, cache schema,
  quote semantics, display/retention terms, no-subscription boundary, and tests.
- Do not turn undocumented Yahoo Finance query/chart/quote endpoints, page
  payloads, cookies, crumbs, scripts, or API examples into unattended local
  adapter behavior without that reviewed slice.
- Any future Yahoo quote rows, if ever added, must remain non-orderable unless a
  separate live-trading safety contract exists.

## Verification

- Focused provider/Command Center/ledger gate:
  `.\.venv\Scripts\python.exe -m pytest -q tests\test_m22_provider_acquisition_gate.py tests\test_m22_command_center_contract.py tests\test_m22_mission_ledger.py --basetemp .omx\pytest-tmp\m23-66-focused`
  -> 10 passed.
- Full backend:
  `.\.venv\Scripts\python.exe -m pytest -q --basetemp .omx\pytest-tmp\m23-66-full`
  -> 380 passed.
- Ruff:
  `.\.venv\Scripts\python.exe -m ruff check .`
  -> passed.
- Frontend `npm run lint` -> passed.
- Frontend `npm run build` -> passed with the existing Vite chunk-size warning.
- Frontend focused shell E2E `npm run e2e -- --grep "opens all routes"`
  -> 1 passed.
- Frontend focused Code rerun
  `npm run e2e -- --grep "edits local code notebook"` -> 1 passed after the
  first full E2E run hit a transient Code notebook toast wait.
- Frontend full E2E final rerun `npm run e2e` -> 15 passed.
- Source-wall/live-safety/local-secret/provider safety gate:
  `.\.venv\Scripts\python.exe -m pytest -q tests\test_clean_room_source_wall.py tests\test_m16_live_safety.py tests\test_m20_local_secret_gate.py tests\test_m22_provider_acquisition_gate.py --basetemp .omx\pytest-tmp\m23-66-safety`
  -> 22 passed.
- FastAPI smoke confirmed provider acquisition candidate count `21`, blocked
  count `5`, Yahoo Finance status `blocked_terms_credentials_gate`, auth
  `application_id_or_api_credentials_required`, quote semantics
  `quote_blocked_by_terms_credentials`, `implementation_allowed=false`,
  `resume_state=backlog_exhausted_needs_research`, Command Center milestone
  `M23.66 Yahoo Finance provider gate`, milestone path
  `docs/planning/M23_YAHOO_FINANCE_PROVIDER_GATE.md`, action count `73`,
  preflight rows `73`, and no local secret-store creation.
- Added-line credential scan found zero high-risk value matches.
- `git diff --check` -> passed with Git CRLF working-copy warnings only.
