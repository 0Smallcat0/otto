# M23.58 Quant Lab Preview Health Matrix

## Scope

M23.58 deepens Quant Lab AI Agent operability by adding a metadata-only preview
health matrix for stored local preview runs and their artifact bundles.

This slice does not execute scripts, start external runtimes, run deep-agent
flows, train models, read artifact contents, index artifact text, repair files,
call providers, store credentials, route broker actions, or enable live/private
behavior.

## Product Delta

- `GET /api/quant-lab/preview-health` returns local preview artifact metadata:
  input, output, context, manifest, report, and error-log file presence, byte
  size, and timestamps.
- `GET /api/quant-lab`, module selection, and preview responses embed the same
  `preview_health` contract so the route is self-describing for AI Agent
  navigation.
- The Quant Lab UI exposes `quant-lab-preview-health` for human supervision of
  AI Agent activity.
- The AI Agent contract exposes `quant_lab_preview_health` as a read-only
  action.
- Command Center provenance moves to this milestone and action count increases
  to `72`.

## Safety Contract

- Metadata-only file stat checks; no input/output/context/manifest/report/error
  artifact body is returned by the health endpoint.
- No script execution, external runtime, deep-agent execution, model training,
  provider calls, secret access, automatic repair, destructive lifecycle action,
  broker mutation, real balance, real order, or live trading.
- Recovery queue entries point to the existing local preview action only; they
  do not mutate state by themselves.

## Verification Plan

- Focused backend
  `.\.venv\Scripts\python.exe -m pytest -q tests\test_m13_quant_lab.py tests\test_m21_agent_operability_contract.py tests\test_m22_command_center_contract.py tests\test_m22_mission_ledger.py --basetemp .omx\pytest-tmp\m23-58-focused`
  -> 21 passed.
- Full backend
  `.\.venv\Scripts\python.exe -m pytest -q --basetemp .omx\pytest-tmp\m23-58-full`
  -> 374 passed.
- Ruff `.\.venv\Scripts\python.exe -m ruff check .` -> passed.
- Frontend `npm run lint` -> passed.
- Frontend `npm run build` -> passed with the existing Vite chunk-size warning.
- Frontend focused Quant Lab E2E
  `npm run e2e -- --grep "runs quant lab local preview"` -> 1 passed.
- Frontend full E2E final rerun `npm run e2e` -> 15 passed.
- Source-wall/live-safety/local-secret/mission-ledger safety gate
  `.\.venv\Scripts\python.exe -m pytest -q tests\test_clean_room_source_wall.py tests\test_m16_live_safety.py tests\test_m20_local_secret_gate.py tests\test_m22_mission_ledger.py --basetemp .omx\pytest-tmp\m23-58-safety`
  -> 23 passed.
- FastAPI smoke must confirm `metadata_only_quant_lab_preview_health`, run count
  `1`, complete count `1`, embedded health parity, Command Center action count
  `72`, preflight rows `72`, and no local secret-store creation -> passed.
- Changed-diff secret scan -> passed.
- `git diff --check` -> passed with Git CRLF working-copy warnings only.
