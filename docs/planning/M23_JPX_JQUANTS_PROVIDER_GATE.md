# M23.64 JPX/J-Quants Provider Gate

## Scope

M23.64 records JPX/J-Quants as a blocked provider-entry candidate before any
Japan equity adapter work.

This slice does not implement a JPX or J-Quants adapter, sign up, collect or
store API keys, call APIs, crawl the JPxData Portal, download CSV bulk files,
parse monthly quotation files, write provider caches, add refresh jobs, add
source coverage rows, route broker actions, or enable live/private behavior.

## Official-Doc Findings

- JPX/J-Quants API V2 uses API-key authentication.
- J-Quants pricing shows the Free plan has API limits and delayed stock OHLC
  coverage, but CSV download is not included in Free.
- JPX's January 19, 2026 release says CSV bulk delivery is available for Light
  Plan or higher, and minute/tick equity data is a paid add-on for Light Plan or
  higher.
- JPxData Portal is a beta catalog/search portal for paid and free JPX Group and
  partner data. It can list data properties and download the latest listed
  securities CSV, but it is not a reviewed stable public no-key quote adapter.
- JPX monthly quotations are file/statistics pages with monthly update cadence,
  not current executable quote data.

## Product Delta

- Adds provider acquisition candidate `jpx_jquants_market_data_gate`.
- Keeps provider acquisition `docs_checked_at=2026-05-31`.
- Keeps `implementation_allowed=false`, `approved_next_count=0`, and
  `resume_state=backlog_exhausted_needs_research`.
- Command Center current milestone/provenance now points to this provider gate.
- No provider cache, refresh endpoint, provider registry row, source coverage
  row, local-secret eligibility, UI quote lane, or external data fetch is added.

## Safety Contract

- Future JPX/J-Quants work needs a separate provider-entry slice with a concrete
  allowed dataset, auth mode, route need, cache schema, quote semantics,
  no-subscription boundary, and tests.
- Do not turn JPxData Portal pages, monthly quotation files, API examples, CSV
  bulk delivery, API-key account flows, or paid/add-on data into unattended local
  adapter behavior without that reviewed slice.
- Japan equity rows, if ever added, must remain non-orderable unless a separate
  live-trading safety contract exists.

## Verification

- Focused provider/Command Center/ledger gate:
  `.\.venv\Scripts\python.exe -m pytest -q tests\test_m22_provider_acquisition_gate.py tests\test_m22_command_center_contract.py tests\test_m22_mission_ledger.py --basetemp .omx\pytest-tmp\m23-64-focused`
  -> 10 passed.
- Full backend:
  `.\.venv\Scripts\python.exe -m pytest -q --basetemp .omx\pytest-tmp\m23-64-full`
  -> 379 passed.
- Ruff:
  `.\.venv\Scripts\python.exe -m ruff check .`
  -> passed.
- Frontend `npm run lint` -> passed.
- Frontend `npm run build` -> passed with the existing Vite chunk-size warning.
- Frontend focused shell E2E
  `npm run e2e -- --grep "opens all routes"` -> 1 passed after updating a
  stale M23.62 Command Center assertion.
- Frontend full E2E `npm run e2e` -> 15 passed.
- Source-wall/live-safety/local-secret/provider safety gate:
  `.\.venv\Scripts\python.exe -m pytest -q tests\test_clean_room_source_wall.py tests\test_m16_live_safety.py tests\test_m20_local_secret_gate.py tests\test_m22_provider_acquisition_gate.py --basetemp .omx\pytest-tmp\m23-64-safety`
  -> 22 passed.
- FastAPI smoke confirmed provider acquisition candidate count `20`, blocked
  count `4`, JPX/J-Quants status `blocked_account_plan_gate`, auth
  `api_key_or_plan_required`, quote semantics `quote_blocked_by_account_plan`,
  `implementation_allowed=false`, `resume_state=backlog_exhausted_needs_research`,
  Command Center milestone `M23.64 JPX/J-Quants provider gate`, milestone path
  `docs/planning/M23_JPX_JQUANTS_PROVIDER_GATE.md`, action count `73`,
  preflight rows `73`, and no local secret-store creation.
- Added-line credential scan found zero high-risk value matches.
- `git diff --check` -> passed with Git CRLF working-copy warnings only.
