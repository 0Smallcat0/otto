# M23.53 OpenFIGI Identifier Mapping

Date: 2026-05-27

## Scope

M23.53 adds a bounded public no-key OpenFIGI identifier-mapping lane for
Markets and AI Agent symbol resolution. It maps a small default symbol list
`AAPL/MSFT/SPY` through OpenFIGI v3 mapping jobs, writes one local cache at
`market_data/reference/openfigi/mapping.json`, and exposes the result through
provider freshness, public provider refresh, Markets source coverage, Stocks
summary fields, and the AI Agent action contract.

This is identifier/reference data only. It is not a price feed, not broker
availability, not a real balance source, not tradeability evidence, and not
executable market data.

## Official Source Gate

- Official docs checked:
  - `https://www.openfigi.com/api/documentation`
  - `https://api.openfigi.com/v3/mapping`
- The adapter uses OpenFIGI v3 mapping jobs with `idType=TICKER` and
  `exchCode=US`.
- Requests are bounded to a small symbol list and cached daily so the
  unauthenticated public rate limit is not used as a broad quote engine.
- No account, signup, payment, API key, broker connection, private account,
  CAPTCHA, 2FA, or credential flow was used or added.

## Implemented Behavior

- `src/local_terminal/openfigi_data.py` normalizes OpenFIGI mapping rows with
  FIGI, composite FIGI, share-class FIGI, ticker, name, exchange code, market
  sector, and security type metadata.
- Rows include source attribution, local cache path, docs URL, provider ID,
  `quote_semantics=not_quote`, `context_only=true`, `orderable=false`, and
  `live_action_enabled=false`.
- Public endpoints:
  - `GET /api/openfigi/mapping`
  - `POST /api/openfigi/mapping/refresh`
  - `POST /api/markets/openfigi/mapping/refresh`
- AI Agent safe action:
  - `markets_openfigi_mapping_refresh`
- Markets source coverage row:
  - `Stocks / identifier_mapping / openfigi_identifier_mapping_public`

## Safety

- No secret store is created or required.
- No optional-key, paid, broker, exchange, live trading, real balance, margin,
  leverage, short, derivative, cloud, payment, subscription, CR/credits, Fincept
  branding, installed-source read, or destructive artifact action is added.
- OpenFIGI rows are source-linked context metadata; they must not be used as
  prices, orderability, broker availability, or live-trading readiness.

## Verification

Final verification evidence:

- OpenFIGI adapter boundary gate
  `.\.venv\Scripts\python.exe -m pytest -q tests\test_m23_openfigi_identifier_mapping.py --basetemp .omx\pytest-tmp\m23-53-openfigi-boundary`
  -> 6 passed.
- Focused OpenFIGI/provider/agent/docs gate
  `.\.venv\Scripts\python.exe -m pytest -q tests\test_m23_openfigi_identifier_mapping.py tests\test_m19_provider_registry.py tests\test_m21_agent_operability_contract.py tests\test_m21_markets_source_coverage_matrix.py tests\test_m22_provider_acquisition_gate.py tests\test_m22_command_center_contract.py tests\test_m22_mission_ledger.py tests\test_m2_local_state.py --basetemp .omx\pytest-tmp\m23-53-doc-contract-2`
  -> 51 passed.
- Full backend gate
  `.\.venv\Scripts\python.exe -m pytest -q --basetemp .omx\pytest-tmp\m23-53-full-2`
  -> 369 passed.
- Focused ruff over changed backend modules/tests -> passed.
- Frontend `npm run lint` -> passed.
- Frontend `npm run build` -> passed with the existing Vite chunk-size warning.
- Frontend `npm run e2e` -> 15 passed.
- Safety/source-wall/local-secret/ledger gate
  `.\.venv\Scripts\python.exe -m pytest -q tests\test_clean_room_source_wall.py tests\test_m16_live_safety.py tests\test_m20_local_secret_gate.py tests\test_m22_mission_ledger.py --basetemp .omx\pytest-tmp\m23-53-safety-1`
  -> 23 passed.
- No-write live OpenFIGI smoke normalized `AAPL/MSFT/SPY` with
  `row_count=3`, `matched_symbol_count=3`, first ticker `AAPL`, FIGI prefix
  `BBG000`, `quote_semantics=not_quote`, and `orderable=false`.

## Handoff

Future Markets work can reuse OpenFIGI rows for identifier context and symbol
resolution, but quote routing still needs separate provider-entry gates. Do not
represent FIGI rows as prices, tradable inventory, broker availability,
balances, or executable instruments.
