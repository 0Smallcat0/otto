# M22.5 SEC XBRL Frames Slice

Date: 2026-05-25

## Purpose

M22.5 implements the first provider/data breadth slice after the M22.4
provider-acquisition gate. It adds a bounded SEC XBRL frames cache for Markets
Stocks so the terminal has cross-company fundamental reference data without
mislabeling fundamentals as executable quotes.

## Scope

- Provider: `sec_xbrl_frames_public`.
- Default frame: `us-gaap / Assets / USD / CY2023Q4I`.
- Cache path:
  `market_data/fundamentals/sec/frames/us-gaap/Assets/USD/CY2023Q4I.json`.
- Runtime role: `fundamental_frames`.
- Quote semantics: `not_quote`.
- Auth mode: `public_no_key`.
- Refresh path: existing `markets_stocks_refresh` / research refresh path.

## Product Behavior

- `research_data_payload` now normalizes bounded SEC frame rows with SEC source
  attribution, cache path, period/tag/unit metadata, entity rows, and
  `reference_only=true`.
- `LocalStateStore` reads/writes the SEC frame cache under the local ignored
  state root.
- `providers_payload` exposes provider/cache freshness for
  `sec_xbrl_frames_public`.
- `markets_payload` exposes the frame in `research_summary.sec_frames`, Stocks
  status lanes, the Markets source coverage matrix, and the Stocks UI.
- `agent_contract.py` exposes `stock_xbrl_frames` and
  `stocks.summary.frame_count` for AI Agent operation.
- The M22 provider acquisition gate marks the SEC frames candidate as
  implemented. M23.1 later implements the Federal Reserve H.10 public no-key FX
  reference candidate as a separate bounded slice.

## Safety

- No live trading, broker/exchange binding, real balances, margin, leverage,
  short exposure, derivatives, payment/subscription/CR, or cloud sync.
- No provider signup, API key, secret storage, credential value, or paid plan.
- No Fincept branding/assets/commercial copy/source/runtime binaries.
- SEC frame rows are source-attributed fundamental context only and are never
  eligible for live action.

## Official Evidence

- SEC EDGAR APIs and XBRL frames documentation:
  `https://www.sec.gov/search-filings/edgar-application-programming-interfaces`
- SEC fair-access guidance:
  `https://www.sec.gov/about/developer-resources`
- Public frame endpoint shape verified on 2026-05-25 with:
  `https://data.sec.gov/api/xbrl/frames/us-gaap/Assets/USD/CY2023Q4I.json`

## Verification

- `.\.venv\Scripts\python.exe -m pytest tests\test_m20_sec_stocks_fundamentals.py tests\test_m21_markets_source_coverage_matrix.py tests\test_m19_provider_registry.py tests\test_m21_agent_operability_contract.py tests\test_m21_bls_macro_provider.py tests\test_m22_provider_acquisition_gate.py -q --basetemp .omx\pytest-tmp\m22-5-focused` -> 35 passed.
- `.\.venv\Scripts\python.exe -m ruff check src\local_terminal\research_data.py src\local_terminal\storage.py src\local_terminal\server.py src\local_terminal\markets.py src\local_terminal\providers.py src\local_terminal\provider_refresh.py src\local_terminal\provider_acquisition.py src\local_terminal\agent_contract.py tests\test_m20_sec_stocks_fundamentals.py tests\test_m21_markets_source_coverage_matrix.py tests\test_m19_provider_registry.py tests\test_m21_agent_operability_contract.py tests\test_m21_bls_macro_provider.py tests\test_m22_provider_acquisition_gate.py` -> passed.
- `npm run lint` from `frontend/` -> passed.
- `npm run build` from `frontend/` -> passed.
- `npm run e2e -- --grep "opens all routes"` from `frontend/` -> 1 passed.
- `.\.venv\Scripts\python.exe -m pytest tests\test_clean_room_source_wall.py tests\test_m16_live_safety.py tests\test_m20_local_secret_gate.py tests\test_m22_mission_ledger.py -q --basetemp .omx\pytest-tmp\m22-5-safety-rerun` -> 22 passed.
- `git diff --check` -> passed with Git CRLF warnings only.
