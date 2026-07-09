# M23.50 Eurostat HICP Macro Context

Date: 2026-05-27

## Scope

M23.50 adds a bounded official public no-key Eurostat HICP macro context lane for
Markets Indexes/Regional supervision.

Implemented surface:

- `eurostat_hicp_public` provider entry and cache state.
- Public cache path `market_data/macro/eurostat/hicp_ea20_cp00_i15.json`.
- `GET /api/eurostat/hicp` and `POST /api/eurostat/hicp/refresh`.
- Markets macro aggregation support through `research_summary.macro`,
  `provider_summaries`, and the existing `markets_macro_refresh` source
  coverage contract.
- Public provider refresh inclusion for the Eurostat HICP cache.
- Command Center provenance update to `M23.50 Eurostat HICP macro context`.

## Source Contract

Source:

- Official Eurostat Statistics API:
  `https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/prc_hicp_midx`
- Official API guidance:
  `https://ec.europa.eu/eurostat/web/user-guides/data-browser/api-data-access/api-detailed-guidelines/api-statistics`
- Dataset browser:
  `https://ec.europa.eu/eurostat/databrowser/view/prc_hicp_midx/default/table`

Bounded request:

- `lastTimePeriod=3`
- `geo=EA20`
- `coicop=CP00`
- `unit=I15`
- `freq=M`

Semantics:

- HICP rows are official macro/reference context.
- `quote_semantics=not_quote`.
- `orderable=false`.
- `live_action_enabled=false`.
- The adapter does not request private account data, broker data, order books,
  realtime feeds, balances, credentials, or paid provider access.

## Verification

Initial focused gate:

- `.\.venv\Scripts\python.exe -m pytest -q tests\test_m23_eurostat_macro_provider.py tests\test_m21_bls_macro_provider.py tests\test_m23_bea_regional_provider.py tests\test_m23_census_regional_provider.py tests\test_m19_provider_registry.py tests\test_m21_markets_source_coverage_matrix.py tests\test_m22_provider_acquisition_gate.py tests\test_m22_command_center_contract.py tests\test_m22_mission_ledger.py tests\test_m2_local_state.py`
  -> 58 passed.

Final gate evidence is recorded in `docs/planning/M22_MISSION_LEDGER.md` and
`docs/planning/FINAL_HANDOFF.md`.

## Non-Goals

M23.50 does not add executable index quotes, trade signals, live trading,
broker/exchange connectivity, private account access, real balances, margin,
leverage, short exposure, derivatives, order routing, provider signup,
credential storage, payment/subscription/CR behavior, cloud sync, Fincept
branding/assets/source copying, installed-source reads, or destructive artifact
actions.
