# M23.33 Portfolio Report Index

Date: 2026-05-26

## Scope

M23.33 deepens Portfolio artifact lifecycle supervision with a read-only local
report index. The slice lets AI Agents inspect generated Portfolio report
artifact presence and recovery hints without reading report contents or enabling
destructive lifecycle actions.

Runtime contract:

- Endpoint: `GET /api/portfolio/reports`.
- Embedded payload: `/api/portfolio` `report_index`.
- Mode: `local_portfolio_report_index`.
- Contract: `portfolio_report_index_v1`.
- Root: `artifacts/portfolio/reports`.
- Safe action: `portfolio_report_index`.

Out of scope:

- Report content indexing, automatic repair, archive/prune/delete/move/restore,
  optimizer execution, broker/exchange binding, real orders, real balances,
  margin, leverage, short exposure, derivatives, payment, subscription,
  CR/credits, cloud sync, credential access, Fincept branding/assets/commercial
  copy, runtime binaries, installed-source reads, or live/private behavior.

## Product Behavior

- `portfolio_report_index` scans local Portfolio report directories by file
  presence, file size, and update time only.
- The index reports complete/incomplete counts, active/latest report ids,
  expected artifact paths, per-file existence, and advisory recovery queue rows.
- The index uses active Portfolio `last_report` state for current report
  metadata and does not read `report.md`, JSON, CSV, or manifest contents.
- `/api/portfolio` embeds the index so AI Agents do not need to guess from UI
  text or filesystem paths.
- Portfolio UI `Report` tab exposes stable selector `portfolio-report-index`.
- AI Agent contract exposes `report_index` state and the
  `portfolio_report_index` safe read action.
- Command Center current milestone provenance points to this document.

## Verification

- Focused ruff:
  `.\.venv\Scripts\python.exe -m ruff check src\local_terminal\portfolio.py src\local_terminal\server.py src\local_terminal\agent_contract.py src\local_terminal\command_center.py tests\test_m7_portfolio.py tests\test_m21_agent_operability_contract.py tests\test_m22_command_center_contract.py`
  -> passed.
- Focused Portfolio/agent/Command Center gate:
  `.\.venv\Scripts\python.exe -m pytest tests\test_m7_portfolio.py tests\test_m21_agent_operability_contract.py tests\test_m22_command_center_contract.py -q --basetemp .omx\pytest-tmp\m23-33-focused`
  with repo-local TEMP/TMP -> 24 passed.
- Focused docs/ledger gate:
  `.\.venv\Scripts\python.exe -m pytest tests\test_m7_portfolio.py tests\test_m21_agent_operability_contract.py tests\test_m22_command_center_contract.py tests\test_m22_mission_ledger.py -q --basetemp .omx\pytest-tmp\m23-33-docs-focused`
  with repo-local TEMP/TMP -> 28 passed.
- Frontend typecheck:
  `npm run lint` in `frontend/` -> passed.
- Full backend gate:
  `.\.venv\Scripts\python.exe -m pytest -q --basetemp .omx\pytest-tmp\m23-33-full-final`
  with repo-local TEMP/TMP -> 330 passed.
- Full ruff:
  `.\.venv\Scripts\python.exe -m ruff check .` -> passed.
- Frontend:
  `npm run build` and `npm run e2e` in `frontend/` -> passed; build kept only
  the existing Vite chunk-size warning and E2E result was 15 passed after
  updating the Command Center action count to 56.
- Source-wall/live-safety/local-secret/ledger gate:
  `.\.venv\Scripts\python.exe -m pytest tests\test_clean_room_source_wall.py tests\test_m16_live_safety.py tests\test_m20_local_secret_gate.py tests\test_m22_mission_ledger.py -q --basetemp .omx\pytest-tmp\m23-33-safety`
  with repo-local TEMP/TMP -> 23 passed.
- FastAPI TestClient smoke confirmed `/api/portfolio/reports` returns one
  complete report row, `/api/portfolio` embeds `report_index`, `/api/command-center`
  returns `M23.33 Portfolio report index`, and no local secret-store directory
  is created.
- Changed-diff secret scan found historical verification text, negative
  `api_key=` response assertions, and the pre-existing Portfolio denylist term
  `pin:`; no credential values, provider-key assignments, bearer-token values,
  personal credential literals, PIN assignments, or private-key blocks were
  added.
- `git diff --check` passed with Git CRLF working-copy warnings only.

## Handoff

Future Portfolio artifact work should extend metadata-only supervision before
adding any repair or lifecycle mutation. Do not turn this index into report
content search, automatic repair, destructive cleanup, broker routing, balance
reads, optimizer execution, or live trading capability.
