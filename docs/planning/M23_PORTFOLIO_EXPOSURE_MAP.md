# M23.45 Portfolio Exposure Map

Date: 2026-05-26

## Scope

Deepen Portfolio report and supervision output without reopening completed
Portfolio local flows or adding any live/private behavior.

This slice adds a local exposure map derived from existing active portfolio
positions and pricing state. It is intended for AI Agent and human supervision
before report generation, not for optimizer, broker routing, real-balance
import, or live execution.

## Implemented

- Added `exposure_map` rows to `/api/portfolio`.
- Added the Portfolio `Exposure` tab with stable selector
  `portfolio-exposure-map`.
- Added `exposure.csv` to generated local Portfolio reports.
- Upgraded the report artifact contract to
  `local_portfolio_report_artifacts_v3`.
- Added `exposure_row_count` to report manifests and active report state.
- Extended the Portfolio AI Agent contract with `exposure_map`,
  `report.artifact_files.exposure`, and `report.exposure_row_count`.
- Updated Command Center milestone provenance to this handoff.

## Safety

- No external provider call.
- No provider signup, credential capture, or secret read.
- No real order, broker/exchange binding, real balance import, margin,
  leverage, short exposure, derivatives, optimizer execution, deployment, or
  live/private behavior.
- Exposure rows are derived from existing local Portfolio state and existing
  pricing attribution only.

## Verification

- Focused Portfolio/Agent/Command Center gate
  `.\.venv\Scripts\python.exe -m pytest tests\test_m7_portfolio.py tests\test_m21_agent_operability_contract.py tests\test_m22_command_center_contract.py -q --basetemp .omx\pytest-tmp\m23-45-focused-initial`
  -> 24 passed.
- Focused Portfolio/Agent/Command Center/docs gate after final report-state fix
  `.\.venv\Scripts\python.exe -m pytest tests\test_m7_portfolio.py tests\test_m21_agent_operability_contract.py tests\test_m22_command_center_contract.py tests\test_m22_mission_ledger.py -q --basetemp .omx\pytest-tmp\m23-45-docs-final`
  -> 28 passed.
- Focused ruff
  `.\.venv\Scripts\python.exe -m ruff check src\local_terminal\portfolio.py src\local_terminal\agent_contract.py src\local_terminal\command_center.py tests\test_m7_portfolio.py tests\test_m21_agent_operability_contract.py tests\test_m22_command_center_contract.py`
  -> passed.
- Frontend `npm run lint` -> passed.
- Frontend `npm run build` -> passed with the existing Vite chunk-size warning.
- Frontend `npm run e2e` -> 15 passed.
- Portfolio-focused Playwright rerun
  `npm run e2e -- --grep "loads portfolio demo"`
  -> 1 passed.
- Source-wall/live-safety/local-secret/Portfolio/Agent gate
  `.\.venv\Scripts\python.exe -m pytest tests\test_clean_room_source_wall.py tests\test_m16_live_safety.py tests\test_m20_local_secret_gate.py tests\test_m22_mission_ledger.py tests\test_m7_portfolio.py tests\test_m21_agent_operability_contract.py -q --basetemp .omx\pytest-tmp\m23-45-safety`
  -> 45 passed.
- Full backend gate
  `.\.venv\Scripts\python.exe -m pytest -q --basetemp .omx\pytest-tmp\m23-45-full-final`
  -> 350 passed.
- Full ruff `.\.venv\Scripts\python.exe -m ruff check .` -> passed.
- Final ledger docs gate
  `.\.venv\Scripts\python.exe -m pytest tests\test_m22_mission_ledger.py -q --basetemp .omx\pytest-tmp\m23-45-ledger-final2`
  -> 4 passed.
- FastAPI TestClient smoke confirmed Command Center milestone
  `M23.45 Portfolio exposure map`, milestone path
  `docs/planning/M23_PORTFOLIO_EXPOSURE_MAP.md`, demo Portfolio
  `exposure_rows=12`, report `exposure.csv`, report
  `exposure_row_count=12`, report index artifact count `9`, Portfolio agent
  state `exposure_map`, Portfolio report response contract
  `report.artifact_files.exposure`, `real_orders=false`, and
  `real_balance=false`.
- Exact personal-account/password/PIN scan found no literal matches for the
  provided Gmail, password, or PIN. Broader changed-file secret scan found only
  historical verification text, negative response assertions, and the existing
  Portfolio denylist term `private_key`; no credential values were added.
- `git diff --check` passed with Git CRLF working-copy warnings only.

## Resume Note

Continue one residual partial at a time. Do not treat the exposure map as
optimizer output, recommendation, real balance evidence, broker availability,
or live trading readiness.
