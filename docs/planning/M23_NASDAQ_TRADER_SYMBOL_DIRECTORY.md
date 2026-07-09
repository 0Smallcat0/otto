# M23.17 Nasdaq Trader Symbol Directory

Date: 2026-05-26

## Scope

M23.17 adds an official public no-key Nasdaq Trader symbol-directory reference
lane for Markets and AI Agent symbol discovery. It uses only the documented
`nasdaqlisted.txt` and `otherlisted.txt` downloadable text files, writes one
local cache at `market_data/reference/nasdaq_trader/symbol_directory.json`, and
surfaces the data through provider freshness, Markets source coverage, the
advanced context, and the AI Agent action contract.

This is reference data only. It is not a quote feed, not broker availability,
not a real balance source, and not executable market data.

## Official Source Gate

- Official docs checked: `https://www.nasdaqtrader.com/trader.aspx?id=symboldirdefs`.
- Official files checked:
  - `https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt`
  - `https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt`
- The docs describe `nasdaqlisted.txt` and `otherlisted.txt` under the Nasdaq
  Trader Symbol Directory and state that symbol-directory files are updated
  periodically throughout the day.
- No account, signup, payment, API key, broker connection, private account,
  CAPTCHA, 2FA, or credential flow was used.
- Python's default local CA bundle failed this site in the local venv, so the
  adapter uses normal certificate verification with the repo venv's `certifi`
  CA bundle when available. Certificate verification is not disabled.

## Implemented Behavior

- `src/local_terminal/nasdaq_trader_data.py` fetches and normalizes Nasdaq-listed
  and other-listed symbol-directory rows.
- Test issues are filtered from surfaced rows and counted in the summary.
- Rows include source-file attribution, listing exchange/category, ETF flag,
  CQS/Nasdaq symbol metadata, local cache path, provider ID, and
  `quote_semantics=not_quote`.
- Public endpoints:
  - `GET /api/nasdaq-trader/symbol-directory`
  - `POST /api/nasdaq-trader/symbol-directory/refresh`
  - `POST /api/markets/nasdaq-trader/symbols/refresh`
- AI Agent safe action:
  - `markets_nasdaq_symbol_directory_refresh`
- Markets source coverage row:
  - `Stocks / symbol_directory / nasdaq_trader_symbol_directory_public`

## Safety

- No secret store is created or required.
- No optional-key, paid, broker, exchange, live trading, real balance, margin,
  leverage, short, derivative, cloud, payment, subscription, CR/credits, Fincept
  branding, installed-source read, or destructive artifact action is added.
- Rows are `not_quote`, `context_only=true`, `live_action_enabled=false`, and
  `orderable=false`.

## Verification

Focused verification before docs:

- `.\.venv\Scripts\python.exe -m pytest tests\test_m23_nasdaq_trader_symbol_directory.py tests\test_m21_markets_source_coverage_matrix.py tests\test_m21_agent_operability_contract.py tests\test_m22_provider_acquisition_gate.py tests\test_m19_provider_registry.py tests\test_m2_local_state.py tests\test_m22_command_center_contract.py -q --basetemp .omx\pytest-tmp\m23-17-focused-rerun` -> 41 passed.
- Changed-file ruff over Nasdaq Trader adapter, server, Markets, storage,
  provider registry/acquisition/refresh, Agent contract, advanced context, and
  focused tests -> passed.
- Frontend `npm run lint` -> passed.
- No-write live smoke against the official text files normalized 12,649 rows:
  5,463 Nasdaq-listed, 7,186 other-listed, 5,230 ETF rows, first symbol `AACB`,
  and `quote_semantics=not_quote`.

Final verification:

- Initial full backend gate caught a clean-room source-wall issue in the new
  adapter User-Agent string. The runtime string was changed to neutral local
  terminal wording, then
  `.\.venv\Scripts\python.exe -m pytest -q --basetemp .omx\pytest-tmp\m23-17-full-final-rerun`
  -> 308 passed.
- Full ruff `.\.venv\Scripts\python.exe -m ruff check .` -> passed.
- Frontend `npm run build` -> passed with the existing Vite chunk-size warning.
- Frontend `npm run e2e` -> 15 passed.
- Safety/source-wall/local-secret gate
  `.\.venv\Scripts\python.exe -m pytest tests\test_clean_room_source_wall.py tests\test_m16_live_safety.py tests\test_m20_local_secret_gate.py tests\test_m22_mission_ledger.py -q --basetemp .omx\pytest-tmp\m23-17-safety-final-rerun`
  -> 23 passed after rerunning outside the Playwright `test-results` file race.
- FastAPI TestClient smoke confirmed Command Center current milestone, public
  Nasdaq Trader refresh, Markets `symbol_directory` source coverage, provider
  freshness, `not_quote` semantics, and no local secret store creation.
- `git diff --check` -> passed with Git CRLF working-copy warnings only.
- Changed-diff secret scan found no personal-account email literals,
  password/PIN literals, provider-key assignments, bearer-token values,
  private-key blocks, protected value markers, or credential assignments.

## Handoff

Do not treat Nasdaq Trader symbol-directory rows as quotes, orderable
instruments, broker availability, balances, or exchange connectivity. Future
symbol search/filter UI can reuse this cache, but quote/provider routing still
needs separate provider-entry gates.
