# M23.59 QuantLib Calculation Health Matrix

## Scope

M23.59 deepens QuantLib AI Agent operability by adding a metadata-only
calculation health matrix for stored deterministic local calculations and their
artifact bundles.

This slice does not execute external QuantLib runtimes, call external APIs or
providers, read artifact contents, index artifact text, repair files, store
credentials, route broker actions, enable derivatives execution, or enable
live/private behavior.

## Product Delta

- `GET /api/quantlib/calculation-health` returns local calculation artifact
  metadata: request, response, context, manifest, report, and error-log file
  presence, byte size, and timestamps.
- `GET /api/quantlib`, module selection, action selection, and compute
  responses embed the same `calculation_health` contract so the route is
  self-describing for AI Agent navigation.
- The QuantLib UI exposes `quantlib-calculation-health` for human supervision of
  AI Agent activity.
- The AI Agent contract exposes `quantlib_calculation_health` as a read-only
  action.
- Command Center provenance moves to this milestone and action count increases
  to `73`.

## Safety Contract

- Metadata-only file stat checks; no request, response, context, manifest,
  report, or error-log artifact body is returned by the health endpoint.
- No external QuantLib runtime, external API/provider call, artifact text
  indexing, secret access, automatic repair, destructive lifecycle action,
  derivatives execution, broker mutation, real balance, real order, or live
  trading.
- Recovery queue entries point to the existing deterministic local compute
  action only; they do not mutate state by themselves.

## Verification Plan

- Focused backend
  `.\.venv\Scripts\python.exe -m pytest -q tests\test_m14_quantlib.py tests\test_m21_agent_operability_contract.py tests\test_m22_command_center_contract.py tests\test_m22_mission_ledger.py --basetemp .omx\pytest-tmp\m23-59-focused`
  -> 24 passed.
- Full backend
  `.\.venv\Scripts\python.exe -m pytest -q --basetemp .omx\pytest-tmp\m23-59-full`
  -> 375 passed.
- Ruff `.\.venv\Scripts\python.exe -m ruff check .` -> passed.
- Frontend `npm run lint` -> passed.
- Frontend `npm run build` -> passed with the existing Vite chunk-size warning.
- Frontend focused QuantLib E2E
  `npm run e2e -- --grep "computes quantlib local preset"` -> 1 passed.
- Frontend full E2E final rerun `npm run e2e` -> 15 passed.
- Source-wall/live-safety/local-secret/mission-ledger safety gate
  `.\.venv\Scripts\python.exe -m pytest -q tests\test_clean_room_source_wall.py tests\test_m16_live_safety.py tests\test_m20_local_secret_gate.py tests\test_m22_mission_ledger.py --basetemp .omx\pytest-tmp\m23-59-safety`
  -> 23 passed.
- FastAPI smoke must confirm `metadata_only_quantlib_calculation_health`,
  calculation count `1`, complete count `1`, embedded health parity, Command
  Center action count `73`, preflight rows `73`, and no local secret-store
  creation -> passed.
- Changed-diff secret scan -> passed.
- `git diff --check` -> passed with Git CRLF working-copy warnings only.
