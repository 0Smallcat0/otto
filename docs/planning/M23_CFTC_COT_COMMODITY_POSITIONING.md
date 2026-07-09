# M23.14 CFTC COT Commodity Positioning

Date: 2026-05-26

## Scope

M23.14 adds a public no-key CFTC Commitments of Traders positioning-context
source for Markets Commodities. It continues from M23.13 and does not reopen
World Bank monthly reference prices, EIA optional-key energy context, provider
refresh architecture, command-center shell supervision, or any completed
Markets source-panel behavior.

This slice is positioning context only. CFTC COT rows are labeled `not_quote`;
they are not executable spot prices, futures quotes, balances, orders, margin,
leverage, short exposure, or derivatives execution data.

## Official Sources

Checked on 2026-05-26:

- CFTC Commitments of Traders reports:
  https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm
- CFTC Public Reporting Environment Socrata API:
  https://dev.socrata.com/foundry/publicreporting.cftc.gov/6dca-aqww
- Bounded public endpoint:
  https://publicreporting.cftc.gov/resource/6dca-aqww.json

The selected Legacy Futures Only endpoint returns public rows for configured
commodity contracts with report date, open interest, commercial positions, and
noncommercial positions. No signup, CAPTCHA, key creation, payment, credential
storage, private account access, broker binding, or live trading flow is
involved.

## Implementation

- Added CFTC COT fetch/normalize/cache support to
  `src/local_terminal/commodity_data.py`.
- Added local cache path
  `market_data/commodities/cftc/cot_legacy_futures.json`.
- Added storage/provider registry/freshness coverage for
  `cftc_cot_legacy_public`.
- Added CFTC COT to `/api/commodities`, `/api/cftc/cot`,
  `/api/cftc/cot/refresh`, `/api/markets/cftc-cot/refresh`,
  `/api/markets`, and public no-key provider refresh results.
- Added a Commodities `positioning_context` row to the Markets source coverage
  matrix with safe action `markets_cftc_cot_refresh`.
- Added Markets Commodities UI visibility for CFTC COT rows, Provider Stack,
  and Source Contract while preserving World Bank and EIA behavior.
- Added AI Agent contract coverage through
  `commodity_cftc_cot_positioning` and `markets_cftc_cot_refresh`.
- Updated provider acquisition gate status to include the implemented public
  no-key CFTC candidate.
- Updated Command Center provenance to this milestone.

## Safety

- No provider signup, key collection, optional-key use, payment, subscription,
  credits, cloud sync, broker/exchange binding, real balance read, or live
  order path was added.
- CFTC rows remain source-attributed positioning context and are not marked
  orderable.
- Existing source-wall, live-safety, local-secret, and clean-room boundaries
  remain in force.

## Verification

- Focused backend gate:
  `.\.venv\Scripts\python.exe -m pytest tests\test_m20_world_bank_commodities_provider.py tests\test_m21_markets_source_coverage_matrix.py tests\test_m19_provider_registry.py tests\test_m21_agent_operability_contract.py tests\test_m22_provider_acquisition_gate.py tests\test_m2_local_state.py tests\test_m22_command_center_contract.py -q --basetemp .omx\pytest-tmp\m23-14-focused-initial`
  -> 41 passed.
- Focused doc/contract gate after ledger/handoff updates:
  `.\.venv\Scripts\python.exe -m pytest tests\test_m22_mission_ledger.py tests\test_m22_command_center_contract.py tests\test_m21_agent_operability_contract.py tests\test_m21_markets_source_coverage_matrix.py tests\test_m20_world_bank_commodities_provider.py tests\test_m19_provider_registry.py tests\test_m22_provider_acquisition_gate.py tests\test_m2_local_state.py -q --basetemp .omx\pytest-tmp\m23-14-doc-contract`
  -> 45 passed.
- Focused ruff over changed backend/tests -> passed.
- Frontend `npm run lint`, `npm run build`, and `npm run e2e` from
  `frontend/` -> passed; build kept the existing Vite chunk-size warning and
  E2E was 15 passed after stopping stale local dev listeners.
- Full backend gate:
  `.\.venv\Scripts\python.exe -m pytest -q --basetemp .omx\pytest-tmp\m23-14-full`
  -> 296 passed.
- Full ruff `.\.venv\Scripts\python.exe -m ruff check .` -> passed.
- Safety/source-wall gate:
  `.\.venv\Scripts\python.exe -m pytest tests\test_clean_room_source_wall.py tests\test_m16_live_safety.py tests\test_m20_local_secret_gate.py tests\test_m22_mission_ledger.py -q --basetemp .omx\pytest-tmp\m23-14-safety`
  -> 23 passed.
- FastAPI TestClient smoke for `/api/health`, `/api/commodities`,
  `/api/cftc/cot`, `/api/cftc/cot/refresh`,
  `/api/markets/cftc-cot/refresh`, `/api/markets`, `/api/providers`,
  `/api/provider-acquisition-gate`, `/api/agent-contract`,
  `/api/command-center`, and `/api/local-state` -> all 200. Command Center
  reported M23.14 and CFTC temp-cache state reported 4 rows for 2026-05-19.
- Live no-write normalization smoke against the official public CFTC endpoint
  returned provider `cftc_cot_legacy_public`, 4 rows, report date
  `2026-05-19`, and noncommercial net values for Gold, Wheat SRW, WTI crude,
  and Copper.
- `git diff --check` -> passed with Git CRLF working-copy warnings only.
- Changed-diff secret scan found no personal-account email literals,
  provider-key assignments, bearer-token values, private-key blocks, protected
  value markers, PIN assignments, or credential assignments.

## Residuals

- This improves Commodities research breadth only. It does not complete broad
  executable commodity quote coverage.
- EIA remains optional-key and local-secret gated.
- Fresh unrestricted installed-Fincept observation remains governed by the M21
  observation protocol and stop gates.
