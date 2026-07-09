# M23.2 Alpha Vantage FX Quote Watchlist

Date: 2026-05-25

## Purpose

M23.2 closes one narrow M22.9 residual by adding bounded optional-key FX quote
watchlist coverage to Markets. It reuses the reviewed Alpha Vantage local-secret
gate and keeps ECB/Federal Reserve reference data separate from non-orderable
FX quote rows.

## Scope

- Provider: `alphavantage_global_quote_optional_key`.
- Official source: Alpha Vantage `CURRENCY_EXCHANGE_RATE`.
- Runtime role: `quote_watchlist`.
- Auth mode: `optional_local_key`.
- Default pairs: `EUR/USD`, `USD/JPY`, `GBP/USD`.
- Cache path: `market_data/fx/alphavantage/currency_exchange/{pair}.json`.
- Quote semantics: `quote_not_orderable`.
- Safe action: `markets_fx_quote_watchlist_refresh`.

Out of scope:

- Live trading, broker/exchange binding, real balances, margin, leverage, short
  exposure, derivatives, payment, subscription, CR/credits, cloud sync, signup,
  or provider-key storage outside the existing local secret gate.
- Treating ECB or Federal Reserve H.10 reference rates as executable quotes.
- Paid bulk quote endpoints or plan-specific realtime entitlement claims.

## Product Behavior

- `alpha_vantage_data.py` normalizes `CURRENCY_EXCHANGE_RATE` responses into
  bounded FX quote rows with bid/ask/rate, source/cache/docs attribution,
  `quote_not_orderable`, and `live_action_enabled=False`.
- `LocalStateStore` reads/writes per-pair Alpha Vantage FX quote caches under
  the local ignored market-data root.
- FastAPI exposes `/api/alpha-vantage/fx-quotes`,
  `/api/alpha-vantage/fx-quotes/refresh`, and
  `/api/markets/fx/quote/refresh`.
- `/api/markets` now includes `fx.quote_watchlist`, and the source coverage
  matrix has an FX `quote_watchlist` row gated by `local_secret_required` until
  a reviewed local Alpha Vantage key exists.
- Provider registry health includes Alpha Vantage FX quote cache states while
  keeping the provider classified as optional local secret data.
- The AI Agent contract exposes `fx_quote_watchlist` state and the
  `markets_fx_quote_watchlist_refresh` action contract.
- The Markets UI adds FX quote status, Provider Stack, Source Contract, and a
  bounded `FX QTE` action while preserving ECB/H.10 reference panels.
- Command Center current milestone provenance points to this document.
- The shell now preserves the active hash route while initial local state is
  loading, preventing late layout restore from remounting the active workspace
  and wiping in-progress AI Agent or user form edits during E2E workflows.

## Official Evidence

- Alpha Vantage documentation:
  `https://www.alphavantage.co/documentation/`
- The reviewed endpoint shape is `function=CURRENCY_EXCHANGE_RATE` with
  `from_currency`, `to_currency`, and user-owned `apikey`. The implementation
  avoids logging or returning credential material and never bundles a key.

## Verification

- `.\.venv\Scripts\python.exe -m pytest tests\test_m20_alpha_vantage_quote_provider.py tests\test_m21_markets_source_coverage_matrix.py tests\test_m21_agent_operability_contract.py tests\test_m19_provider_registry.py tests\test_m2_local_state.py tests\test_m22_command_center_contract.py -q --basetemp .omx\pytest-tmp\m23-2-focused-initial` -> 46 passed.
- `.\.venv\Scripts\python.exe -m ruff check src\local_terminal\alpha_vantage_data.py src\local_terminal\server.py src\local_terminal\markets.py src\local_terminal\providers.py src\local_terminal\storage.py src\local_terminal\agent_contract.py src\local_terminal\advanced_context.py tests\test_m20_alpha_vantage_quote_provider.py tests\test_m21_markets_source_coverage_matrix.py tests\test_m21_agent_operability_contract.py tests\test_m19_provider_registry.py tests\test_m2_local_state.py tests\test_m22_command_center_contract.py` -> passed.
- `npm run lint` from `frontend/` -> passed.
- `npm run build` from `frontend/` -> passed with the existing Vite chunk-size warning.
- FastAPI TestClient probe for `/api/alpha-vantage/fx-quotes`,
  `/api/alpha-vantage/fx-quotes/refresh`, `/api/markets/fx/quote/refresh`,
  `/api/markets`, `/api/agent-contract`, and `/api/providers` returned 200; no
  local key produced `key_required`, `fx.quote_watchlist` row count `0`,
  agent action `/api/markets/fx/quote/refresh`, and provider cache
  `fx_quote_alphavantage_EURUSD`.
- A full backend run initially caught a source-row ordering regression where
  the new FX quote row became the first FX row and changed an existing Algo
  lineage test from reference semantics to quote semantics. The row order was
  restored so ECB/H.10 reference rows remain first and the quote row is additive.
- `.\.venv\Scripts\python.exe -m pytest tests\test_m10_algo.py::test_algo_scan_accepts_markets_source_row_and_persists_lineage tests\test_m21_markets_source_coverage_matrix.py tests\test_m20_alpha_vantage_quote_provider.py -q --basetemp .omx\pytest-tmp\m23-2-roworder` -> 22 passed.
- `.\.venv\Scripts\python.exe -m pytest -q --basetemp .omx\pytest-tmp\m23-2-full-rerun` -> 274 passed.
- `.\.venv\Scripts\python.exe -m ruff check .` -> passed.
- `npm run lint` and `npm run build` from `frontend/` -> passed; build kept
  the existing Vite chunk-size warning.
- `npm run e2e -- --grep "keeps dashboard useful"` -> 1 passed after a
  transient unrelated dashboard-dialog miss in a full E2E attempt.
- A full E2E rerun exposed a real shell restore race: late `/api/local-state`
  startup hydration could overwrite the hash-selected route, remount Crypto or
  Backtest, and reset form state. After preserving the active hash route during
  state restore, `npm run e2e` from `frontend/` -> 15 passed.
- `.\.venv\Scripts\python.exe -m pytest tests\test_clean_room_source_wall.py tests\test_m16_live_safety.py tests\test_m20_local_secret_gate.py tests\test_m22_mission_ledger.py -q --basetemp .omx\pytest-tmp\m23-2-safety` -> 23 passed.
- `git diff --check` -> passed with Git CRLF working-copy warnings only.
- Changed-file secret scan found no known personal credential literals and no
  high-risk assignment-like secret matches outside planning docs.
- Playwright visual smoke opened Markets -> FX, clicked `FX QTE`, and confirmed
  `Alpha Vantage FX Quotes`, `FX QUOTE`, `markets-fx-source-contract`, and
  `key_required` are visible; screenshot captured at
  `artifacts/screenshots/m23-2-markets-fx-quote-watchlist.png`.

## Residuals

- This slice broadens optional-key FX quote coverage only. It does not provide
  broad multi-asset executable quote parity.
- Alpha Vantage free-plan limits and entitlement differences remain visible as
  provider states; no signup, key collection, or paid capability was attempted.
- Fresh installed-Fincept observation remains governed by the M21 observation
  protocol and stop gates.
