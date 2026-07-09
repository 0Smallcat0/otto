# M23.1 Federal Reserve H.10 FX Reference Slice

Date: 2026-05-25

## Purpose

M23.1 closes one narrow M22.9 residual by adding a second public no-key FX
reference source for Markets. It broadens FX reference coverage without
claiming executable spot FX quotes, broker connectivity, balances, live orders,
or paid/provider-key coverage.

## Scope

- Provider: `federal_reserve_h10_ddp_public`.
- Official source: Federal Reserve H.10 Data Download Program.
- Runtime role: `usd_reference_rates`.
- Auth mode: `public_no_key`.
- Cache path: `market_data/fx/federal_reserve/h10_reference_rates.json`.
- Quote semantics: `reference_only`.
- Refresh path: existing FX refresh and public provider refresh surfaces.

Out of scope:

- Tradable spot FX quotes.
- Broker/exchange binding.
- Real balances, orders, margin, leverage, short exposure, or derivatives.
- Provider signup, key storage, paid plans, CR/credits, payment, subscription,
  cloud sync, or Fincept runtime/source/assets.

## Product Behavior

- `fx_data_payload` now returns both ECB EUR-base reference rates and Federal
  Reserve H.10 USD reference rates with separate source/cache/status sections.
- H.10 CSV rows normalize to reference-only pair rows with `rate_basis`,
  attribution, cache path, docs URL, retrieval time, and latest-date summary.
- `LocalStateStore` reads/writes the H.10 cache under the repo-local ignored
  market-data root.
- `/api/fx`, `/api/markets`, `/api/providers`, public provider refresh, and
  `/api/provider-acquisition-gate` expose H.10 provider/cache state.
- Markets source coverage now has distinct FX rows for
  `eur_reference_rates` and `usd_reference_rates`.
- The Markets UI shows an ECB reference panel and a Federal Reserve H.10 panel
  while preserving the premium/optional spot-FX gate.
- The AI Agent contract now reports `fx_h10_reference_rates` and includes
  `fx.h10` in the `markets_fx_refresh` response contract.
- Command Center current milestone provenance points to this document so a
  future agent can resume from the current slice instead of M22.9.

## Official Evidence

- H.10 DDP page:
  `https://www.federalreserve.gov/datadownload/choose.aspx?rel=h10`
- H.10 CSV package shape checked on 2026-05-25 with the public no-key Data
  Download output URL. The observed package includes `Currency:`, `Unique
  Identifier:`, `Time Period`, and daily observation rows.
- Live no-write smoke on 2026-05-25 parsed provider id
  `federal_reserve_h10_ddp_public`, latest date `2026-05-15`, 23 rows, and
  `reference_only=True`.

## Verification

- `.\.venv\Scripts\python.exe -m pytest tests\test_m20_ecb_fx_provider.py tests\test_m19_provider_registry.py tests\test_m21_markets_source_coverage_matrix.py tests\test_m21_agent_operability_contract.py tests\test_m22_provider_acquisition_gate.py tests\test_m2_local_state.py -q --basetemp .omx\pytest-tmp\m23-1-focused-current` -> 36 passed.
- Live no-write H.10 normalization smoke -> provider
  `federal_reserve_h10_ddp_public`, latest date `2026-05-15`, 23 rows, first
  row `AUD/USD usd_per_currency True`.
- Live local FX refresh smoke `POST /api/markets/fx/refresh` -> 200,
  `fx.status.state=live`, ECB row count 29, H.10 row count 23,
  H.10 date `2026-05-15`, local H.10 cache exists, and first H.10 row keeps
  `reference_only=True`.
- `.\.venv\Scripts\python.exe -m pytest tests\test_m20_ecb_fx_provider.py tests\test_m19_provider_registry.py tests\test_m21_markets_source_coverage_matrix.py tests\test_m21_agent_operability_contract.py tests\test_m22_provider_acquisition_gate.py tests\test_m2_local_state.py tests\test_m22_command_center_contract.py tests\test_m22_mission_ledger.py -q --basetemp .omx\pytest-tmp\m23-1-focused-docs` -> 42 passed.
- `.\.venv\Scripts\python.exe -m pytest -q --basetemp .omx\pytest-tmp\m23-1-full` -> 269 passed.
- `.\.venv\Scripts\python.exe -m ruff check .` -> passed.
- `npm run lint`, `npm run build`, and `npm run e2e` from `frontend/` -> passed;
  build kept the existing Vite chunk-size warning and E2E was 15 passed.
- Playwright visual smoke opened Markets -> FX and confirmed the `FED H10 FX`
  card, `FED H10` panel, Provider Stack, and Source Contract are visible;
  screenshot captured at `artifacts/screenshots/m23-1-markets-fx-h10.png`.
- The first safety/source-wall run overlapped with Playwright deleting
  `frontend/test-results/.last-run.json` and hit the known transient
  `FileNotFoundError`; rerun after E2E completed.
- `.\.venv\Scripts\python.exe -m pytest tests\test_clean_room_source_wall.py tests\test_m16_live_safety.py tests\test_m20_local_secret_gate.py tests\test_m22_mission_ledger.py -q --basetemp .omx\pytest-tmp\m23-1-safety-final` -> 23 passed.
- `git diff --check` -> passed with Git CRLF working-copy warnings only.
- Changed-file secret scan matched only historical verification text and
  negative response assertions; no credential values, provider keys, bearer
  tokens, personal credential literals, or private-key blocks were added.

## Residuals

- This slice improves reference-rate breadth only. Broad executable non-crypto
  quote coverage remains partial.
- Optional-key or paid FX providers remain gated behind separate provider-entry
  review, local-secret eligibility, tests, source attribution, and explicit
  quote/reference semantics.
- Fresh installed-Fincept observation remains gated by the M21 observation
  protocol and stop gates.
