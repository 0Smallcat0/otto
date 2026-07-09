# M20.25 FRED Optional-Key Provider

Date: 2026-05-23

## Scope

M20.25 implements the first optional-key data-provider adapter behind the M20.24 local secret store. The adapter covers one FRED macro series (`DGS10`) as a source-attributed local cache and UI workflow. It does not add a public HTTP endpoint that returns key values, does not request or bundle a key, and does not create any broker, exchange, live-trading, balance, margin, leverage, short, or derivatives path.

## Official Docs Checked

- FRED API key docs: `https://fred.stlouisfed.org/docs/api/api_key.html`
- FRED series observations docs: `https://fred.stlouisfed.org/docs/api/fred/series_observations.html`
- FRED API terms: `https://fred.stlouisfed.org/docs/api/terms_of_use.html`

Observed requirements used for implementation:

- FRED web service requests require a user-owned API key.
- `fred/series/observations` supports JSON output and `series_id`.
- FRED terms can impose request limits, require source notice, and disallow logo/trademark/endorsement misuse.

## Runtime Behavior

- `GET /api/fred` returns redacted provider status and any existing local FRED cache.
- `POST /api/fred/refresh` refreshes only when `fred_optional_local_key` is already stored through the local secret gate.
- Without a stored key, FRED returns `key_required` and does not call the network or create fixture runtime data.
- With a stored key, the server reads the sealed value internally, calls FRED, normalizes observations, writes `market_data/macro/fred/DGS10.json`, and returns only redacted data.
- News and Markets expose FRED refresh controls and source/cache/status attribution.
- Research, Dashboard, Markets, and advanced context can consume cached FRED macro rows through the existing macro summary path.

## Provider Entry Gate

- Provider id: `fred_optional_local_key`
- Auth mode: `optional-local-key`
- Safety class: `optional_local_secret_data_provider`
- Cache path: `market_data/macro/fred/DGS10.json`
- TTL: `86400`
- Schema: `series observations -> latest macro observation and recent observation rows`
- Fallback: show `key_required`, `rate_limited`, `unavailable`, or last local cache with source attribution; never fixture values as primary runtime.
- Secret handling: local DPAPI store only; no repo/log/screenshot/docs/commit exposure, no HTTP value read endpoint.

## Verification Notes

Focused M20.25 checks:

- `.\.venv\Scripts\python.exe -m pytest tests\test_m20_fred_optional_provider.py tests\test_m19_news_macro_fundamentals.py tests\test_m2_local_state.py tests\test_m19_provider_registry.py -q` -> 23 passed.
- `.\.venv\Scripts\python.exe -m ruff check src\local_terminal\fred_data.py src\local_terminal\research_data.py src\local_terminal\storage.py src\local_terminal\providers.py src\local_terminal\server.py src\local_terminal\advanced_context.py tests\test_m20_fred_optional_provider.py` -> passed.
- `npm run lint` in `frontend/` -> passed.

Full gate results are recorded in `PROJECT_STATE.md` and `docs/planning/FINAL_HANDOFF.md` after the milestone verification run.
