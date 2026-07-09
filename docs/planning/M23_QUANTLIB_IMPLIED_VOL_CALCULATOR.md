# M23.61 QuantLib Implied-Volatility Calculator

## Scope

M23.61 deepens QuantLib calculator breadth by adding one bounded deterministic
local `implied-volatility` quick action. The calculator solves Black-Scholes
implied volatility from a supplied option market price using stdlib math and a
bounded bisection loop.

This slice does not execute external QuantLib runtimes, call external APIs or
providers, fetch market prices, store credentials, route broker actions, enable
derivatives execution, or enable live/private behavior.

## Product Delta

- Adds `implied-volatility` to the QuantLib quick-action presets.
- Computes `black_scholes_implied_volatility` with local request validation,
  bounded volatility range, model price, pricing error, iteration count, and
  `local_stdlib_math` runtime metadata.
- Writes the existing QuantLib request, response, context, manifest, report,
  and error-log artifact bundle under `artifacts/quantlib/{calculation_id}/`.
- Exposes the preset through frontend fallback state and focused Playwright
  selection coverage.
- Moves Command Center provenance to this milestone without adding a new Agent
  action or changing action count.

## Safety Contract

- The calculation is analytics-only and local-only.
- The `market_price` input is caller supplied; no provider, exchange, broker,
  or account price is fetched.
- The output is not an order ticket, tradable derivative, hedge instruction,
  broker route, balance read, margin/leverage/short workflow, or live-trading
  capability.
- Existing request guards still reject credential-like keys/values and
  forbidden runtime intent before writing artifacts.

## Verification Evidence

- Focused backend
  `.\.venv\Scripts\python.exe -m pytest -q tests\test_m14_quantlib.py tests\test_m21_agent_operability_contract.py tests\test_m22_command_center_contract.py tests\test_m22_mission_ledger.py --basetemp .omx\pytest-tmp\m23-61-focused`
  -> 25 passed after fixing near-zero pricing-error formatting.
- Full backend
  `.\.venv\Scripts\python.exe -m pytest -q --basetemp .omx\pytest-tmp\m23-61-full`
  -> 376 passed.
- Ruff `.\.venv\Scripts\python.exe -m ruff check .` -> passed.
- Frontend `npm run lint` -> passed.
- Frontend `npm run build` -> passed with the existing Vite chunk-size warning.
- Focused QuantLib E2E
  `npm run e2e -- --grep "computes quantlib local preset"` -> 1 passed.
- Frontend full E2E final rerun `npm run e2e` -> 15 passed after updating
  stale M23.60 milestone assertions.
- Source-wall/live-safety/local-secret/provider gate
  `.\.venv\Scripts\python.exe -m pytest -q tests\test_clean_room_source_wall.py tests\test_m16_live_safety.py tests\test_m20_local_secret_gate.py tests\test_m22_provider_acquisition_gate.py --basetemp .omx\pytest-tmp\m23-61-safety`
  -> 22 passed.
- FastAPI smoke confirmed `quick_actions=6`,
  `black_scholes_implied_volatility`, implied volatility `0.200000`, one
  complete health row, Command Center milestone path, action count `73`,
  preflight rows `73`, and no local secret-store creation.
- Changed-diff secret scan -> passed with no matches and Git CRLF
  working-copy warnings only.
- `git diff --check` -> passed with Git CRLF working-copy warnings only.
