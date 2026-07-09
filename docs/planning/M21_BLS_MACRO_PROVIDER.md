# M21 BLS Macro Provider

Date: 2026-05-24

## Scope

M21.9 adds a public no-key U.S. Bureau of Labor Statistics macro/labor provider
for the local Markets Indexes and Regional context panels.

The slice expands official non-crypto provider breadth without adding paid data,
provider signup, optional keys, private broker/exchange credentials, live trading,
real balances, or fixture/default macro values as primary runtime data.

## Official Source Evidence

- BLS developer getting-started page states that the Public Data API exposes BLS
  economic data and supports JSON retrieval through `GET` and `POST`.
- BLS API signature v2 documents latest-series retrieval with
  `GET https://api.bls.gov/publicAPI/v2/timeseries/data/{series_id}?latest=true`.
- BLS Unix sample docs confirm no-key public `GET` single-series and JSON `POST`
  multi-series examples.

Official docs checked:

- https://www.bls.gov/developers/home.htm
- https://www.bls.gov/developers/api_signature_v2.htm
- https://www.bls.gov/developers/api_unix_v2.htm

## Clean-Room Observation Note

The installed Fincept app was launched from `D:\FinceptTerminal\app\FinceptTerminal.exe`
only as safe observation context. The process became responsive, but no screenshot
was retained, no login credentials or PIN were entered, and no installed source,
runtime package source, assets, branding, commercial copy, billing, subscription,
CR/credits, or account data were inspected.

Existing sanitized M21 Markets evidence remains the workflow reference: dense
provider/source panels, route-specific refresh actions, visible cache/source state,
and quote-provider gates for non-executable context data.

## Implementation

- Added `src/local_terminal/bls_data.py`.
- Added public no-key BLS cache path:
  `market_data/macro/bls/latest_series.json`.
- Added BLS payload/status/cache integration to `research_data_payload`.
- Added `/api/bls`, `/api/bls/refresh`, `/api/research-data/bls/refresh`, and
  `/api/markets/bls/refresh`.
- Added BLS to the public provider registry, provider freshness cache states, and
  manual public provider refresh manifests.
- Kept manual refresh results provider-specific: DBnomics refresh status is read
  from the DBnomics cache payload, so a BLS-only success cannot mark DBnomics as
  live/cache-written.
- Counted `stale_cache` as usable cached runtime in provider refresh diagnostics.
- Added a Markets `BLS` action, public macro source card copy, and BLS-aware macro
  docs/auth labels.
- Added AI Agent action contract `markets_bls_macro_refresh`.

Default no-key series:

- `LNS14000000`: Civilian unemployment rate.
- `CES0000000001`: All employees, total nonfarm.
- `CUSR0000SA0`: CPI-U all items, seasonally adjusted.

## Safety Boundaries

- No credential, API key, account signup, payment, subscription, CR/credits, or
  cloud account path was added.
- BLS data is context-only macro/labor reference data, not executable quotes.
- Index and Regional quote rows remain disabled behind provider gates.
- No live order path, real balance read, margin, leverage, short exposure,
  derivatives execution, or broker/exchange key flow was added.
- No Fincept branding, assets, commercial copy, installed source, or runtime binary
  was copied or adapted.
- Tests use synthetic provider payloads only as tests; user-visible runtime fetches
  the official public BLS API or shows explicit unavailable/stale cache state.

## Verification

Current focused evidence:

- `.\.venv\Scripts\python.exe -m pytest tests\test_m19_provider_registry.py tests\test_m21_bls_macro_provider.py tests\test_m20_dbnomics_markets_macro_context.py tests\test_m21_agent_operability_contract.py -q`
  with repo-local TEMP/TMP -> 20 passed.
- `.\.venv\Scripts\python.exe -m pytest tests\test_m19_provider_registry.py tests\test_m21_bls_macro_provider.py -q`
  with repo-local TEMP/TMP -> 14 passed after adding the BLS-only/DBnomics-unavailable
  provider-refresh regression.
- BLS live smoke:
  `fetch_bls_latest_series(series_ids=["LNS14000000"])` normalized to `live`, one
  series, latest period `April 2026`.
- Targeted Ruff for changed backend/provider tests -> passed.
- Full backend `.\.venv\Scripts\python.exe -m pytest -q` with repo-local TEMP/TMP
  -> 233 passed.
- Frontend `npm run lint`, `npm run build`, and `npm run e2e` -> passed; e2e was
  stabilized by waiting for Code route sync before clicking `NEW`.
- Browser and visual evidence: `artifacts/screenshots/m21-bls-macro-provider.png`;
  visual verdict pass, score 91.
- Code-review gate -> APPROVE. Remaining architecture watch: macro aggregation still
  uses provider list order for headline latest fields and should be formalized in a
  future provider-breadth slice.

Full M21.9 verification is recorded in `docs/planning/FINAL_HANDOFF.md`.
