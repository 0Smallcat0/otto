# M21.3 EIA Energy Context Slice

Date: 2026-05-24

## Selected Scope

M21.3 adds optional-key EIA Open Data energy context to Markets Commodities. The
slice covers WTI spot, Brent spot, and Henry Hub natural gas daily reference
series as local context only.

This is not an executable commodity quote feed, futures feed, broker feed, or live
trading surface.

## Observation Evidence

Safe live Fincept observation was attempted on 2026-05-24. The installed app opened
to a locked terminal state, so no credentials were typed, logged, echoed, or
screenshotted.

The implementation uses existing clean-room evidence instead:

- `docs/reference/fincept-platform-test/logs/markets-deep-ui-elements.json`
- `docs/reference/fincept-platform-test/logs/high-priority-flows/markets-initial-ui-elements.json`
- `docs/reference/fincept-platform-test/logs/high-priority-flows/markets-add-panel-ui-elements.json`

Sanitized behavior notes: the observed Markets workflow is a dense multi-panel
terminal grid with a top command row, refresh/auto/panel controls, explicit last
update state, route-specific market panels, source/status text, and table-style
provider attribution.

No new Fincept screenshot was retained.

## Provider Research

Official EIA sources were checked on 2026-05-24:

- EIA Open Data documentation: https://www.eia.gov/opendata/documentation.php
- EIA API key registration: https://www.eia.gov/opendata/v1/register.php

EIA APIv2 requires a user-owned key. The adapter therefore runs only behind the
existing local secret store as `eia_open_data_optional_key`. Without a stored local
key or cache, the runtime returns `key_required` and does not create fixture energy
values.

## Implementation

- Added `src/local_terminal/eia_data.py`.
- Added local cache path `market_data/commodities/eia/energy_series.json`.
- Added provider registry/freshness coverage for `eia_open_data_optional_key`.
- Added `/api/eia/energy`, `/api/eia/energy/refresh`, and
  `/api/markets/eia/refresh`.
- Added Markets Commodities `ENERGY` action, EIA Energy Context panel, source/cache
  rows, and route summary state.
- Added EIA context into advanced routes as read-only provider context.
- Hardened frontend route-loading races found by full Playwright E2E: Backtest and
  Algo now avoid late initial-load form overwrites, and Nodes keeps Templates
  disabled until templates are loaded.

## Safety

- No EIA key is returned by HTTP, written to provider cache, logged, screenshotted,
  or committed.
- No public no-key refresh job includes EIA.
- No paid provider, subscription, cloud account, broker/exchange key, real balance,
  margin, leverage, short exposure, derivative execution, or live trading control
  was added.
- EIA rows are reference context only and must not be reused as executable spot,
  futures, or order-routing data without a separate provider and safety contract.

## Verification

- Focused provider/UI gate:
  `.\.venv\Scripts\python.exe -m pytest tests\test_m21_eia_energy_provider.py tests\test_m20_world_bank_commodities_provider.py tests\test_m20_local_secret_gate.py tests\test_m19_provider_registry.py tests\test_m2_local_state.py -q`
  -> 32 passed.
- Full pytest with repo-local TEMP/TMP: 215 passed.
- Source-wall/live-safety:
  `.\.venv\Scripts\python.exe -m pytest tests\test_clean_room_source_wall.py tests\test_m16_live_safety.py -q`
  -> 12 passed.
- Ruff: `.\.venv\Scripts\python.exe -m ruff check .` -> passed.
- Frontend lint/build: `npm run lint`, `npm run build` -> passed.
- Playwright E2E: `npm run e2e` -> 15 passed.
- Browser check: local Markets route opened in the in-app browser; Commodities
  displayed `EIA Energy Context` with the local-key/cache requirement state.
- Screenshot evidence: `artifacts/screenshots/m21-eia-energy-context.png`
  (ignored local artifact).
- `git diff --check`: passed with Git CRLF working-copy warnings only.
- Exact sensitive-literal scan for known account credential/PIN literals: no matches.

## Remaining Watch

Successful live EIA refresh with a real user key was not run in this slice. Parser,
redacted endpoint, cache, key-required, and route behavior are covered by tests.
