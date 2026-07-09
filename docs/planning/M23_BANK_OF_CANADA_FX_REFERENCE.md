# M23.31 Bank of Canada FX Reference

Date: 2026-05-26

## Scope

M23.31 deepens Markets FX reference coverage with a public no-key Bank of
Canada Valet source. The slice adds bounded daily CAD reference-rate rows while
preserving the existing ECB EUR reference, Federal Reserve H.10 USD reference,
and optional-key FX quote watchlist separation.

Provider contract:

- Provider: `bank_of_canada_valet_fx_reference_public`.
- Official source: Bank of Canada Valet observations API.
- Runtime role: `cad_reference_rates`.
- Auth mode: `public_no_key`.
- Cache path: `market_data/fx/bank_of_canada/valet_fx_reference_rates.json`.
- Quote semantics: `reference_only`.
- Safe action: existing `markets_fx_refresh`.

Out of scope:

- Tradable spot FX quotes, order routing, broker/exchange binding, balances,
  margin, leverage, short exposure, derivatives, payment, subscription,
  CR/credits, cloud sync, provider signup, credential storage, Fincept branding,
  assets, commercial copy, runtime binaries, or installed-source reads.

## Product Behavior

- `fx_data_payload` now returns `boc` beside `ecb`, `h10`, and the optional-key
  quote watchlist surfaces.
- Bank of Canada Valet JSON normalizes to bounded `USD/CAD`, `EUR/CAD`,
  `GBP/CAD`, `JPY/CAD`, and `CHF/CAD` rows with `cad_per_currency`,
  `reference_only=True`, source attribution, cache path, docs URL, and retrieval
  time.
- `LocalStateStore` reads and writes the Bank of Canada FX cache under the
  ignored repo-local market-data root.
- `/api/markets`, `/api/providers`, public provider refresh, local state, and
  `/api/provider-acquisition-gate` expose the provider/cache state.
- Markets source coverage now has an FX `cad_reference_rates` row.
- The Markets FX UI shows a Bank of Canada CAD Reference panel and includes BoC
  reference rows in Provider Stack and Source Contract panels.
- The AI Agent contract reports `fx_bank_of_canada_reference_rates` and includes
  `fx.boc` in the `markets_fx_refresh` response contract.
- Command Center current milestone provenance points to this document.

## Official Evidence

- Bank of Canada Valet API docs:
  `https://www.bankofcanada.ca/valet/docs`
- Bank of Canada exchange-rate page:
  `https://www.bankofcanada.ca/rates/exchange/`
- Bank of Canada exchange-rate background:
  `https://www.bankofcanada.ca/rates/exchange/background-information-on-foreign-exchange-rates/`
- Live no-secret smoke on 2026-05-26 used the bounded Valet observations URL
  for `FXUSDCAD,FXEURCAD,FXGBPCAD,FXJPYCAD,FXCHFCAD` with `recent=1` and
  returned daily observation rows dated 2026-05-25.

## Verification

- Focused ruff:
  `.\.venv\Scripts\python.exe -m ruff check src\local_terminal\fx_data.py src\local_terminal\storage.py src\local_terminal\server.py src\local_terminal\markets.py src\local_terminal\providers.py src\local_terminal\provider_acquisition.py src\local_terminal\provider_refresh.py src\local_terminal\agent_contract.py tests\test_m20_ecb_fx_provider.py tests\test_m21_markets_source_coverage_matrix.py tests\test_m19_provider_registry.py tests\test_m22_provider_acquisition_gate.py tests\test_m21_agent_operability_contract.py tests\test_m2_local_state.py`
  -> passed.
- Focused provider/source/agent/storage gate:
  `.\.venv\Scripts\python.exe -m pytest tests\test_m20_ecb_fx_provider.py tests\test_m21_markets_source_coverage_matrix.py tests\test_m19_provider_registry.py tests\test_m22_provider_acquisition_gate.py tests\test_m21_agent_operability_contract.py tests\test_m2_local_state.py -q --basetemp .omx\pytest-tmp\m23-31-focused`
  with repo-local TEMP/TMP -> 42 passed.
- Focused provider/docs/command-center/ledger gate:
  `.\.venv\Scripts\python.exe -m pytest tests\test_m20_ecb_fx_provider.py tests\test_m21_markets_source_coverage_matrix.py tests\test_m19_provider_registry.py tests\test_m22_provider_acquisition_gate.py tests\test_m21_agent_operability_contract.py tests\test_m2_local_state.py tests\test_m22_command_center_contract.py tests\test_m22_mission_ledger.py -q --basetemp .omx\pytest-tmp\m23-31-docs`
  with repo-local TEMP/TMP -> 48 passed.
- Full backend gate:
  `.\.venv\Scripts\python.exe -m pytest -q --basetemp .omx\pytest-tmp\m23-31-full-final`
  with repo-local TEMP/TMP -> 325 passed.
- Full ruff:
  `.\.venv\Scripts\python.exe -m ruff check .` -> passed.
- Frontend:
  `npm run lint`, `npm run build`, and `npm run e2e` in `frontend/` -> passed;
  build kept only the existing Vite chunk-size warning and E2E result was
  15 passed.
- Source-wall/live-safety/local-secret/ledger gate:
  `.\.venv\Scripts\python.exe -m pytest tests\test_clean_room_source_wall.py tests\test_m16_live_safety.py tests\test_m20_local_secret_gate.py tests\test_m22_mission_ledger.py -q --basetemp .omx\pytest-tmp\m23-31-safety`
  with repo-local TEMP/TMP -> 23 passed.
- Live no-write BoC normalization smoke parsed provider
  `bank_of_canada_valet_fx_reference_public`, date `2026-05-25`, 5 rows, and
  first row `CHF/CAD reference_only=True`.
- FastAPI TestClient smoke confirmed `/api/command-center` returns
  `M23.31 Bank of Canada FX reference` and `/api/markets` exposes FX
  `cad_reference_rates` for `bank_of_canada_valet_fx_reference_public`.
- Changed-diff secret scan found only historical verification text and negative
  `api_key=` style response assertions; no credential values, provider-key
  assignments, bearer-token values, personal credential literals, PIN
  assignments, or private-key blocks were added.
- `git diff --check` passed with Git CRLF working-copy warnings only.

## Handoff

Future FX work must keep ECB, Federal Reserve H.10, and Bank of Canada reference
rates separate from optional-key or paid spot-FX quote providers. Bank of Canada
rows are useful CAD reference context only; they are not executable quotes,
broker availability, balances, order routing, margin/funding input, derivatives
execution data, or a reason to collect unused provider keys.
