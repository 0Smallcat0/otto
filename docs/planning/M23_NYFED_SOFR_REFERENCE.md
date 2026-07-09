# M23.11 NY Fed SOFR Reference Rates

Date: 2026-05-26

## Scope

M23.11 adds a second public no-key Bonds/Rates reference source through the New
York Fed SOFR API. It continues from the M23.10 baseline and does not reopen
completed command-center, activity-journal, provider-refresh, Treasury, FX,
Regional, or optional-key quote-watchlist work.

This slice is reference-rate context only. SOFR rows are labeled
`reference_only`; they are not executable quotes, balances, funding trades,
orders, margin, leverage, short exposure, or derivatives data.

## Official Sources

Checked on 2026-05-26:

- SOFR reference-rate page:
  https://www.newyorkfed.org/markets/reference-rates/sofr
- New York Fed Markets Data APIs:
  https://markets.newyorkfed.org/static/docs/markets-api.html
- Public no-key SOFR endpoint:
  https://markets.newyorkfed.org/api/rates/secured/sofr/last/10.json

The public endpoint returns `refRates` rows with `effectiveDate`,
`percentRate`, percentile fields, volume, type, and revision indicator. No
signup, CAPTCHA, key creation, payment, secret storage, private account access,
or live trading flow is involved.

## Implementation

- Added NY Fed SOFR normalization/fetching to `src/local_terminal/rates_data.py`.
- Added local cache path `market_data/rates/nyfed/sofr.json`.
- Added storage/provider registry/freshness coverage for `nyfed_sofr_public`.
- Added SOFR to `/api/rates`, `/api/rates/refresh`,
  `/api/markets/rates/refresh`, `/api/markets`, and public no-key provider
  refresh results.
- Added a Bonds/Rates `overnight_reference_rate` row to the Markets source
  coverage matrix.
- Added Markets UI visibility for SOFR rows, source contract, and provider
  stack while preserving Treasury yield-curve behavior.
- Added AI Agent contract coverage through `rates_sofr_reference` and
  `rates.sofr` on `markets_rates_refresh`.
- Updated provider acquisition gate status to include the implemented public
  no-key SOFR candidate.
- Updated Command Center provenance to this milestone.

## Safety

- No provider signup, key collection, optional-key use, payment, subscription,
  CR/credits, cloud sync, broker/exchange binding, real balance read, or live
  order path was added.
- SOFR remains source-attributed reference data and is not marked orderable.
- Existing source-wall, live-safety, local-secret, and clean-room boundaries
  remain in force.

## Verification

- Focused gate:
  `.\.venv\Scripts\python.exe -m pytest tests\test_m20_treasury_rates_provider.py tests\test_m21_markets_source_coverage_matrix.py tests\test_m19_provider_registry.py tests\test_m21_agent_operability_contract.py tests\test_m22_provider_acquisition_gate.py tests\test_m2_local_state.py -q --basetemp .omx\pytest-tmp\m23-11-focused-initial` -> 39 passed.
- Focused doc/contract gate:
  `.\.venv\Scripts\python.exe -m pytest tests\test_m20_treasury_rates_provider.py tests\test_m21_markets_source_coverage_matrix.py tests\test_m19_provider_registry.py tests\test_m21_agent_operability_contract.py tests\test_m22_provider_acquisition_gate.py tests\test_m2_local_state.py tests\test_m22_command_center_contract.py tests\test_m22_mission_ledger.py -q --basetemp .omx\pytest-tmp\m23-11-focused-docs` -> 45 passed.
- Focused ruff over changed backend/tests -> passed.
- Frontend `npm run lint` -> passed.
- Live no-write SOFR normalization smoke against the official public endpoint
  returned provider `nyfed_sofr_public`, latest date `2026-05-21`, rate `3.51`,
  and 10 rows.
- Full backend gate:
  `.\.venv\Scripts\python.exe -m pytest -q --basetemp .omx\pytest-tmp\m23-11-full` -> 295 passed.
- Full ruff `.\.venv\Scripts\python.exe -m ruff check .` -> passed.
- Frontend `npm run build` -> passed with the existing Vite chunk-size warning.
- Frontend `npm run e2e` -> 15 passed after stopping stale local dev listeners
  on ports 8765 and 5173.
- Safety/source-wall gate:
  `.\.venv\Scripts\python.exe -m pytest tests\test_clean_room_source_wall.py tests\test_m16_live_safety.py tests\test_m20_local_secret_gate.py tests\test_m22_mission_ledger.py -q --basetemp .omx\pytest-tmp\m23-11-safety` -> 23 passed.
- FastAPI TestClient smoke for `/api/rates`, `/api/rates/refresh`,
  `/api/markets/rates/refresh`, `/api/markets`, `/api/providers`,
  `/api/provider-acquisition-gate`, `/api/agent-contract`,
  `/api/command-center`, and `/api/local-state` -> all 200; SOFR stayed
  `reference_only`, Command Center reported M23.11, and no local secret store
  was created.
- Browser smoke opened Markets -> Bonds/Rates, clicked `RATES`, and confirmed
  visible Treasury and SOFR panels, `nyfed_sofr_public`, reference-only text,
  and no secret-like UI text.
- Changed-file redacted secret scan found zero user credential literals,
  provider-key assignments, bearer-token values, private-key blocks,
  `api_key=`, or `protected_value` hits.
- `git diff --check` -> passed with Git CRLF working-copy warnings only.

## Residuals

- This improves Bonds/Rates reference breadth only. It does not complete broad
  executable non-crypto quote coverage.
- FRED remains optional-key and local-secret gated.
- Fresh unrestricted installed-Fincept observation remains governed by the M21
  observation protocol and stop gates.
