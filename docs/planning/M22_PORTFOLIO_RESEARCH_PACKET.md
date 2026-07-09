# M22.6 Portfolio Research Packet

Date: 2026-05-25

## Objective

Deepen the Backtest / Algo / Portfolio loop without adding optimize, deploy,
live trading, broker binding, real balances, cloud sync, or credential handling.

The bounded workflow is:

`Algo scan lineage -> scan-seeded Backtest artifacts -> Portfolio link -> local
Portfolio report -> lineage + artifact-health research packet`.

## Implemented Scope

- Portfolio reports now write `lineage.json` beside the existing summary, risk,
  performance, allocation, markdown report, and manifest artifacts.
- Portfolio reports now write `artifact_health.json` for linked local artifacts.
- Backtest-linked Portfolio state preserves validated `research_lineage` from
  scan-seeded Backtest manifests.
- Report manifests expose `local_portfolio_report_artifacts_v2`,
  `lineage_summary`, and linked artifact health summary.
- The Portfolio route contract advertises `report_lineage` and
  `report_artifact_health` as AI Agent state fields.
- The `portfolio_report` AI Agent action contract now specifies the new
  lineage and artifact-health outputs.
- The Portfolio UI report tab surfaces the report lineage and missing linked
  artifact count without requiring screenshot scraping.

## Safety Boundary

- Linked artifacts are read-only.
- Health checks only inspect repo-local `artifacts/` paths and ignore unsafe,
  secret-like, absolute, or parent-traversal paths.
- Recovery output is a non-destructive queue of hints; it does not delete,
  move, restore, archive, or rewrite linked artifacts.
- `live_action_enabled`, real orders, real balances, optimizer execution, and
  destructive artifact actions remain false.

## Verification

- Focused tests:
  `.\.venv\Scripts\python.exe -m pytest tests\test_m7_portfolio.py tests\test_m21_agent_operability_contract.py tests\test_m22_command_center_contract.py -q --basetemp .omx\pytest-tmp\m22-6-focused`
  -> 21 passed.
- Ruff:
  `.\.venv\Scripts\python.exe -m ruff check src\local_terminal\portfolio.py src\local_terminal\agent_contract.py src\local_terminal\command_center.py tests\test_m7_portfolio.py tests\test_m21_agent_operability_contract.py tests\test_m22_command_center_contract.py`
  -> passed.
- Full backend:
  `.\.venv\Scripts\python.exe -m pytest -q --basetemp .omx\pytest-tmp\m22-6-full-final-rerun`
  -> 265 passed.
- Frontend:
  `npm run lint`, `npm run build`, and `npm run e2e` from `frontend/` -> passed
  (`npm run build` kept the existing Vite chunk-size warning).
- Safety/source:
  `.\.venv\Scripts\python.exe -m pytest tests\test_clean_room_source_wall.py tests\test_m16_live_safety.py tests\test_m20_local_secret_gate.py tests\test_m22_mission_ledger.py -q --basetemp .omx\pytest-tmp\m22-6-safety-final`
  -> 22 passed.
- `git diff --check` -> passed with Git CRLF warnings only.
- Changed-file secret scan found no real credential, password, PIN, provider key,
  private key, or protected value.
