# M23.29 QuantLib Fixed-Income Calculator

Date: 2026-05-26

## Scope

M23.29 adds one bounded deterministic QuantLib calculator example for
fixed-income supervision: a local bond duration/convexity preset. This closes a
small part of the QuantLib calculator-breadth gap without adding external
QuantLib runtime, provider calls, notebook execution, broker/exchange behavior,
credential access, derivatives execution, or live/private trading.

## Product Behavior

- `GET /api/quantlib` now reports 5 quick actions.
- The new quick action is `bond-duration` with module `instruments` and endpoint
  combo `instruments/bonds/duration`.
- `POST /api/quantlib/select-action` loads the fixed-income request body:
  `face_value`, `coupon_rate`, `yield_rate`, `years_to_maturity`, and
  `payments_per_year`.
- `POST /api/quantlib/compute` writes the existing local QuantLib artifact bundle:
  `request.json`, `response.json`, `context.json`, `manifest.json`, `report.md`,
  and `error.log`.
- The response body includes deterministic `fixed_income_duration` fields:
  price, Macaulay duration, modified duration, convexity, basis-point value,
  periods, payment frequency, and `runtime=local_stdlib_math`.
- The frontend offline fallback advertises the fixed-income preset so the route
  remains understandable if the API is unavailable.
- Command Center current milestone and provenance point at this document.

## Safety

- The calculation uses stdlib math only.
- The request validator still blocks credential-like keys/values, live/private
  runtime intent, invalid numerics, path traversal, unsafe stored state, and run
  limit bypass.
- The milestone does not execute external QuantLib, call providers, read or
  index artifact contents, mutate route outputs outside the existing local
  calculation bundle, submit orders, read balances, route broker/exchange
  actions, enable margin/leverage/short exposure, execute derivatives, or add
  destructive lifecycle behavior.

## Verification

- Focused QuantLib gate:
  `.\.venv\Scripts\python.exe -m pytest tests\test_m14_quantlib.py -q`
  -> 11 passed; first run also exposed a non-blocking Windows temp cleanup
  warning because the repo-local temp directory was not pre-created.
- Focused QuantLib/Command Center gate:
  `.\.venv\Scripts\python.exe -m pytest tests\test_m14_quantlib.py tests\test_m22_command_center_contract.py -q --basetemp .omx\pytest-tmp\m23-29-focused`
  with repo-local TEMP/TMP -> 13 passed.
- Focused docs/ledger gate:
  `.\.venv\Scripts\python.exe -m pytest tests\test_m14_quantlib.py tests\test_m22_command_center_contract.py tests\test_m22_mission_ledger.py -q --basetemp .omx\pytest-tmp\m23-29-docs`
  with repo-local TEMP/TMP -> 17 passed.
- Focused ruff:
  `.\.venv\Scripts\python.exe -m ruff check src\local_terminal\quantlib.py src\local_terminal\command_center.py tests\test_m14_quantlib.py tests\test_m22_command_center_contract.py`
  -> passed.
- Full backend gate:
  `.\.venv\Scripts\python.exe -m pytest -q --basetemp .omx\pytest-tmp\m23-29-full`
  with repo-local TEMP/TMP -> 324 passed.
- Full ruff `.\.venv\Scripts\python.exe -m ruff check .` -> passed.
- Frontend `npm run lint`, `npm run build`, and `npm run e2e` in `frontend/`
  -> passed; build kept only the existing Vite chunk-size warning and E2E
  result was 15 passed after updating milestone text assertions.
- Source-wall/live-safety/local-secret/ledger gate:
  `.\.venv\Scripts\python.exe -m pytest tests\test_clean_room_source_wall.py tests\test_m16_live_safety.py tests\test_m20_local_secret_gate.py tests\test_m22_mission_ledger.py -q --basetemp .omx\pytest-tmp\m23-29-safety`
  with repo-local TEMP/TMP -> 23 passed.
- FastAPI TestClient smoke confirmed `quick_actions=5`, `bond-duration`
  response kind `fixed_income_duration`, Command Center current milestone
  `M23.29 QuantLib fixed-income calculator`, and no local secret store creation.
- Changed-diff secret scan found no personal-account email literals,
  password/PIN literals, provider-key assignments, bearer-token values,
  private-key blocks, protected-value payload assignments, or credential
  assignments.
- `git diff --check` passed with Git CRLF working-copy warnings only.

## Handoff

Future QuantLib work can add another bounded deterministic calculator only when
it preserves the same local artifact contract and safety checks. External
QuantLib runtime, provider calls, notebook execution, managed runtime expansion,
artifact content indexing, archive/prune/restore mutation, credentials,
broker/exchange binding, real balances, derivatives execution, and live trading
still require separate reviewed safety contracts before they become reachable.
