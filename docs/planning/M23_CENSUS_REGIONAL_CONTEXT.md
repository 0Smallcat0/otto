# M23.6 Census Regional Context

Date: 2026-05-25

## Scope

M23.6 adds a bounded U.S. Census ACS 5-year Data Profile regional context
provider for Markets Regional. It continues the M23 provider-depth sequence
from the current local terminal baseline and does not reopen completed M21-M23
surfaces.

This slice is non-trading research context only. Census rows are labeled
`not_quote`; they are not executable quotes, balances, trade instructions,
signals, orders, margin, leverage, short exposure, or derivatives data.

## Official Sources

Checked on 2026-05-25:

- U.S. Census Data API key guide:
  https://www.census.gov/data/developers/guidance/api-user-guide.API_Key.html
- ACS 5-year Data Profile dataset:
  https://api.census.gov/data/2023/acs/acs5/profile.html
- ACS 5-year Data Profile variables:
  https://api.census.gov/data/2023/acs/acs5/profile/variables.html

The current Census guide says Census API data queries require an API key. This
implementation therefore uses the existing local secret gate only after the
user has stored a user-owned key. The agent must not sign up, request keys,
store unused keys, expose key values, or include key material in logs, docs,
screenshots, tests, or commits.

## Implementation

- Added `src/local_terminal/census_data.py`.
- Added local cache path
  `market_data/regional/census/acs5_profile_state_2023.json`.
- Added storage/provider registry/freshness coverage for
  `census_api_optional_key`.
- Added `/api/census/acs-profile` and
  `/api/census/acs-profile/refresh`.
- Added `/api/markets/census/refresh`.
- Added Census ACS rows into the shared macro aggregation contract after
  DBnomics, FRED, BLS, and BEA.
- Added Markets Regional source coverage with
  `safe_action_id=markets_census_refresh`.
- Added AI Agent route/action contract coverage for
  `regional_census_context` and `markets_census_refresh`.
- Added a Markets toolbar `CENSUS` action and regional macro source-contract
  text.
- Updated provider acquisition gate status from deferred to implemented
  bounded optional-key.
- Updated Command Center provenance to this milestone.

## Bounded Dataset

The adapter requests a small state-level ACS profile slice:

- `DP05_0001E`: total population.
- `DP03_0062E`: median household income.
- `DP03_0009PE`: unemployment rate.
- `DP03_0128PE`: poverty rate.
- geography: `for=state:*`.

The normalized runtime caps output to 12 series and stores only source,
provider, geography, variable, value, period, cache, and attribution metadata.

## Safety

- No public no-key refresh job includes Census.
- No provider signup is performed.
- No secret value read endpoint exists.
- Refresh returns `key_required` without a stored local key and creates no
  `settings/local_secrets.json`.
- Cached values are regional context only and remain out of any order path.
- Live trading, broker/exchange binding, real balances, margin, leverage,
  short exposure, derivatives, payment, subscription, CR/credits, cloud sync,
  Fincept branding/assets/source, and installed-source reads remain excluded.

## Verification

- `.\.venv\Scripts\python.exe -m pytest tests\test_m23_census_regional_provider.py tests\test_m21_bls_macro_provider.py tests\test_m22_provider_acquisition_gate.py tests\test_m21_agent_operability_contract.py tests\test_m2_local_state.py tests\test_m21_markets_source_coverage_matrix.py tests\test_m19_provider_registry.py tests\test_m20_local_secret_gate.py tests\test_m22_command_center_contract.py -q --basetemp .omx\pytest-tmp\m23-6-focused-current` -> 52 passed.
- `.\.venv\Scripts\python.exe -m ruff check src\local_terminal\census_data.py src\local_terminal\research_data.py src\local_terminal\server.py src\local_terminal\markets.py src\local_terminal\providers.py src\local_terminal\storage.py src\local_terminal\agent_contract.py src\local_terminal\provider_acquisition.py src\local_terminal\command_center.py tests\test_m23_census_regional_provider.py tests\test_m21_bls_macro_provider.py tests\test_m22_provider_acquisition_gate.py tests\test_m21_agent_operability_contract.py tests\test_m2_local_state.py tests\test_m21_markets_source_coverage_matrix.py tests\test_m19_provider_registry.py tests\test_m20_local_secret_gate.py tests\test_m22_command_center_contract.py` -> passed.
- `.\.venv\Scripts\python.exe -m pytest -q --basetemp .omx\pytest-tmp\m23-6-full-current` -> 291 passed.
- `.\.venv\Scripts\python.exe -m ruff check .` -> passed.
- Frontend `npm run lint`, `npm run build`, and `npm run e2e` from
  `frontend/` -> passed; build kept the existing Vite chunk-size warning and
  E2E result was 15 passed.
- FastAPI TestClient smoke for Census, Markets, agent-contract, providers,
  provider-acquisition, Command Center, and local-state endpoints -> all 200;
  no-key Census stayed `key_required`, Census summary stayed `not_quote`,
  provider registry and AI Agent action contract exposed Census, provider
  acquisition `implemented_count` stayed 5 with no next candidate, and no local
  secret store was created.
- Browser smoke opened Markets -> Regional, confirmed the `CENSUS` action,
  Census provider/cache text, Regional Macro Context panel, and safe
  key-required state after clicking `CENSUS`.
- `.\.venv\Scripts\python.exe -m pytest tests\test_clean_room_source_wall.py tests\test_m16_live_safety.py tests\test_m20_local_secret_gate.py tests\test_m22_mission_ledger.py -q --basetemp .omx\pytest-tmp\m23-6-safety-current` -> 23 passed.
- Changed-file redacted secret scan found only existing verification text and
  negative `api_key=`/`protected_value` assertions; no credential values,
  personal email literals, provider keys, bearer tokens, or private-key blocks
  were added.
- `git diff --check` -> passed with Git CRLF working-copy warnings only.

## Follow-Up Boundary

Census ACS context does not complete broad Regional market-data parity. Future
Regional work should add only concrete, bounded provider slices with official
docs and immediate route need; do not broaden Census variables/geographies or
collect keys without a new provider-entry gate.
