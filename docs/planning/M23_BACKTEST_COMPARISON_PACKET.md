# M23.20 Backtest Comparison Packet

Date: 2026-05-26

## Scope

M23.20 adds a local Backtest comparison packet for AI Agent inspection of recent
closed-candle research runs. It compares existing `bt-*` artifacts only and
writes a bounded packet under `artifacts/backtests/comparisons/`.

This milestone deepens Backtest/Algo/Portfolio research-output usability without
adding optimize, live deploy, broker routing, real orders, private data,
balances, margin, leverage, short exposure, or derivatives.

## Implemented Behavior

- `write_backtest_comparison_packet` reads the latest local `bt-*` backtest
  artifacts, extracts summary/provenance/returns/manifest metadata, ranks runs by
  return percentage, and writes:
  - `comparison.json`
  - `rows.csv`
  - `manifest.json`
  - `report.md`
- `POST /api/backtest/comparison-packet` exposes the packet writer with bounded
  `max_runs` 2-8.
- Backtest UI adds `Compare Runs`, a `Comparison` result tab, artifact paths, and
  stable selector `backtest-comparison-packet`.
- `/api/agent-contract` advertises `backtest_comparison_packet` and Backtest
  state `comparison_packet`.
- Command Center provenance advances to this M23.20 milestone.

## Safety

- The packet reads existing local Backtest metadata and writes new comparison
  artifacts only.
- It does not rerun strategy code, optimize parameters, submit orders, read
  private accounts, route broker/exchange actions, or mutate Portfolio state.
- At least two local backtest runs are required; otherwise the action fails
  without creating comparison artifacts.

## Verification

Final verification:

- `.\.venv\Scripts\python.exe -m pytest tests\test_m6_backtest.py tests\test_m21_agent_operability_contract.py tests\test_m22_command_center_contract.py tests\test_m22_mission_ledger.py -q --basetemp .omx\pytest-tmp\m23-20-docs`
  -> 31 passed.
- `.\.venv\Scripts\python.exe -m pytest -q --basetemp .omx\pytest-tmp\m23-20-full`
  -> 315 passed.
- `.\.venv\Scripts\python.exe -m ruff check .` -> passed.
- `.\.venv\Scripts\python.exe -m ruff check src\local_terminal\backtest.py src\local_terminal\server.py src\local_terminal\agent_contract.py src\local_terminal\command_center.py tests\test_m6_backtest.py tests\test_m21_agent_operability_contract.py tests\test_m22_command_center_contract.py`
  -> passed.
- Frontend `npm run lint`, `npm run build`, and `npm run e2e` -> passed; build
  kept only the existing Vite chunk-size warning and E2E result was 15 passed.
- Source-wall/live-safety/local-secret gate
  `.\.venv\Scripts\python.exe -m pytest tests\test_clean_room_source_wall.py tests\test_m16_live_safety.py tests\test_m20_local_secret_gate.py tests\test_m22_mission_ledger.py -q --basetemp .omx\pytest-tmp\m23-20-safety`
  -> 23 passed.
- FastAPI TestClient smoke confirmed two local Backtest runs, comparison packet
  run count 2, four comparison artifacts, Command Center current milestone, AI
  Agent action contract, and no local secret-store creation.
- Playwright browser smoke confirmed Backtest `Compare Runs` produces a visible
  comparison packet with `comparison.json`.
- Changed-diff secret scan passed, and `git diff --check` passed with Git CRLF
  working-copy warnings only.

## Handoff

Future expansion can add compare filters or Portfolio handoff, but optimize,
replay, live deploy, broker routing, real orders, and destructive artifact
lifecycle actions still require separate reviewed safety contracts.
