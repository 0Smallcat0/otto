# M22.4 Provider Data Acquisition Gate

Date: 2026-05-25

## Scope

M22.4 turns provider expansion into a read-only, ranked acquisition gate before
the next adapter is implemented. The goal is to prevent random provider
additions, unused key collection, and quote/reference confusion.

This slice does not fetch provider data, request keys, sign up for providers,
store secrets, or add route UI.

## Official-Source Refresh

The following official or primary sources were checked on 2026-05-25:

- SEC EDGAR Application Programming Interfaces:
  https://www.sec.gov/search-filings/edgar-application-programming-interfaces
- SEC XBRL frames endpoint family:
  https://data.sec.gov/api/xbrl/frames/
- Federal Reserve H.10 Data Download Program:
  https://www.federalreserve.gov/datadownload/choose.aspx?rel=h10
- Alpha Vantage API documentation:
  https://www.alphavantage.co/documentation/
- Twelve Data LLM/market-data documentation:
  https://twelvedata.com/docs/llms and
  https://twelvedata.com/docs/llms/market-data
- BEA Web Service API User Guide:
  https://apps.bea.gov/api/_pdf/bea_web_service_api_user_guide.pdf
- U.S. Census Data API User Guide API-key page:
  https://www.census.gov/data/developers/guidance/api-user-guide.API_Key.html
- U.S. Census 2023 ACS 5-year Data Profile dataset and variables:
  https://api.census.gov/data/2023/acs/acs5/profile.html and
  https://api.census.gov/data/2023/acs/acs5/profile/variables.html

## Candidate Decisions

| Candidate | Status | Auth | Route need | Semantics | Decision |
| --- | --- | --- | --- | --- | --- |
| SEC XBRL frames | implemented bounded slice in M22.5 | public no-key | Stocks cross-company fundamental context | not quote | Keep bounded cache/tests; do not expand to generic SEC crawling without a new gate. |
| Federal Reserve H.10 DDP | implemented bounded slice in M23.1 | public no-key | FX USD reference-rate breadth | reference only | Keep bounded cache/tests; do not present H.10 as executable spot FX quotes. |
| Alpha Vantage FX `CURRENCY_EXCHANGE_RATE` | implemented bounded slice in M23.2 | optional local key | FX non-orderable quote watchlist | quote not orderable | Reuse local secret gate; keep bounded per-pair caches and do not present as live-executable spot FX. |
| Twelve Data `/quote` | implemented bounded slice in M23.4 | optional local key | Secondary multi-asset quote provider for comparison-gated breadth | quote not orderable | Reuse local secret gate; keep bounded `AAPL/SPY/EURUSD` caches, stay outside public refresh, and do not use batch/paid endpoints. |
| BEA Regional API | implemented bounded slice in M23.5 | optional local key | Regional state GDP macro context | not quote | Reuse local secret gate; keep bounded `SAGDP9N` state rows, stay outside public refresh, and do not expose UserID values. |
| U.S. Census Data API | implemented bounded slice in M23.6 | optional local key | Regional state demographic/economic context | not quote | Reuse local secret gate; keep bounded 2023 ACS 5-year Data Profile state rows, stay outside public refresh, and do not expose API key values. |

## Provider Priority Rules

1. Public no-key sources come first when they satisfy an immediate route
   workflow.
2. Optional personal/free keys are allowed only through the local secret gate
   and only when the route has a concrete use for that provider.
3. Paid, plan-gated, entitlement-gated, broker, exchange, private-account, and
   live-execution providers remain recorded-only or forbidden.
4. Reference data must stay labeled as `reference_only` or `not_quote`; do not
   reuse it as executable quotes, order prices, balances, margin, leverage, short
   exposure, or derivative execution input.

## Implementation

- Added `src/local_terminal/provider_acquisition.py`.
- Added `GET /api/provider-acquisition-gate`.
- Added `provider_acquisition_gate` to the Settings AI Agent state fields and
  `provider_acquisition_gate_inspect` to the AI Agent action contract.
- Added `tests/test_m22_provider_acquisition_gate.py`.

## Verification

- `.\.venv\Scripts\python.exe -m pytest tests\test_m22_provider_acquisition_gate.py tests\test_m21_agent_operability_contract.py tests\test_m22_command_center_contract.py tests\test_clean_room_source_wall.py -q --basetemp .omx\pytest-tmp\m22-4` -> 16 passed.
- `.\.venv\Scripts\python.exe -m pytest tests\test_m22_provider_acquisition_gate.py tests\test_m22_mission_ledger.py tests\test_m21_agent_operability_contract.py tests\test_clean_room_source_wall.py tests\test_m16_live_safety.py tests\test_m20_local_secret_gate.py -q --basetemp .omx\pytest-tmp\m22-4-docs` -> 29 passed.
- `.\.venv\Scripts\python.exe -m ruff check src\local_terminal\provider_acquisition.py src\local_terminal\agent_contract.py src\local_terminal\server.py tests\test_m22_provider_acquisition_gate.py` -> passed.
- Changed-file generic secret scan for `gmail.com`, `api_key=`, `protected_value`,
  `password=`, and `private_key` found only negative API response assertions and
  existing verification text; no credential values were added.

## Next

M22.5 implemented the bounded SEC XBRL frames cache described here. M23.1 then
implemented the Federal Reserve H.10 public no-key FX reference slice for USD
reference-rate breadth. M23.2 reused the existing Alpha Vantage optional-key
gate for bounded FX quote watchlists. M23.4 adds Twelve Data as a bounded
secondary optional-key quote provider. M23.5 adds BEA Regional as bounded
optional-key Regional macro context. M23.6 adds Census ACS as bounded
optional-key Regional demographic/economic context. The next provider/data
implementation should select a new concrete route residual from the current
audit instead of reopening SEC frames, H.10, Alpha Vantage FX, Twelve Data
symbol breadth, BEA Regional rows, or Census ACS variables/geographies, and it
must preserve quote/reference separation.
