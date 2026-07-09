# M23.65 QuantLib Option Scenario Grid

## Scope

M23.65 deepens QuantLib local calculator breadth with a deterministic
Black-Scholes option scenario grid.

This slice does not execute external QuantLib, call providers, fetch market
prices, use notebooks or workflow runtimes, access credentials, route broker
actions, read balances, execute derivatives, submit orders, or enable
live/private behavior.

## Product Delta

- Adds quick action `option-scenario-grid`.
- Uses bounded request fields: `spot`, `strike`, `risk_free_rate`,
  `volatility`, `time_to_maturity`, `option_type`, and 3-9 numeric
  `scenario_shocks`.
- Writes the existing QuantLib local artifact bundle:
  `request.json`, `response.json`, `context.json`, `manifest.json`,
  `report.md`, and `error.log`.
- Returns `black_scholes_scenario_grid` response rows with scenario spot,
  model price, and model P&L versus the base model price.
- Updates frontend fallback presets and E2E coverage so the Scenario Grid
  action is visible to human supervisors and AI Agents through the normal
  route flow.
- Moves Command Center current milestone/provenance to this slice.

## Safety Contract

- Scenario rows are local analytics only. They are not quotes, not orderable
  prices, not strategy signals, not broker availability, and not derivative
  execution.
- Input validation rejects credential-like request keys, forbidden live/runtime
  intent, invalid scenario arrays, non-finite values, and scenario shocks that
  would make the underlying non-positive.
- Existing QuantLib calculation health remains metadata-only and does not read
  artifact contents or run automatic repair.

## Verification

- Focused QuantLib scenario gate:
  `.\.venv\Scripts\python.exe -m pytest -q tests\test_m14_quantlib.py::test_quantlib_option_scenario_grid_preset_writes_local_artifacts tests\test_m14_quantlib.py::test_quantlib_all_quick_action_defaults_compute_locally tests\test_m14_quantlib.py::test_quantlib_initial_payload_reports_module_tree_presets_and_safety --basetemp .omx\pytest-tmp\m23-65-quantlib-focused`
  -> 3 passed.
- Focused QuantLib/Command Center/ledger gate:
  `.\.venv\Scripts\python.exe -m pytest -q tests\test_m14_quantlib.py tests\test_m22_command_center_contract.py tests\test_m22_mission_ledger.py --basetemp .omx\pytest-tmp\m23-65-focused`
  -> 21 passed.
- Full backend:
  `.\.venv\Scripts\python.exe -m pytest -q --basetemp .omx\pytest-tmp\m23-65-full-rerun`
  -> 380 passed.
- Ruff:
  `.\.venv\Scripts\python.exe -m ruff check .`
  -> passed.
- Frontend `npm run lint` -> passed.
- Frontend `npm run build` -> passed with the existing Vite chunk-size warning.
- Frontend focused QuantLib E2E
  `npm run e2e -- --grep "computes quantlib local preset"` -> 1 passed.
- Frontend full E2E `npm run e2e` -> 15 passed.
- Source-wall/live-safety/local-secret/provider safety gate:
  `.\.venv\Scripts\python.exe -m pytest -q tests\test_clean_room_source_wall.py tests\test_m16_live_safety.py tests\test_m20_local_secret_gate.py tests\test_m22_provider_acquisition_gate.py --basetemp .omx\pytest-tmp\m23-65-safety`
  -> 22 passed.
- FastAPI smoke confirmed `quick_actions=7`, `option-scenario-grid`, response
  kind `black_scholes_scenario_grid`, scenario count `5`, one complete health
  row, Command Center milestone `M23.65 QuantLib option scenario grid`,
  milestone path `docs/planning/M23_QUANTLIB_OPTION_SCENARIO_GRID.md`, action
  count `73`, preflight rows `73`, and no local secret-store creation.
- Added-line credential scan found zero high-risk value matches.
- `git diff --check` -> passed with Git CRLF working-copy warnings only.
