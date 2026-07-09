# M23.28 Advanced Output IO Contract

Date: 2026-05-26

## Scope

M23.28 extends the existing advanced local workflow output packet with a
metadata-only IO contract for AI Chat, Nodes, Code, Quant Lab, and QuantLib. The
slice does not execute workflows, run notebooks, call managed LLMs, call
providers, read artifact contents, or change any route output behavior. It only
describes the safe inputs, expected output artifact kinds, error surfaces,
latest output paths, safe local action, blocked runtime actions, and safety
flags that an AI Agent needs before choosing an advanced-route action.

## Product Behavior

- `GET /api/advanced-workflows/output-packet` now returns
  `summary.io_contract_route_count`.
- Each advanced route row now includes `io_contract` with:
  - `contract_id`
  - `input_contract`
  - `output_contract`
  - `error_contract`
  - `latest_output_paths`
  - `safe_action`
  - `blocked_runtime_actions`
  - `read_mode=metadata_only`
  - safety flags proving no content read, execution, external network,
    credentials, broker mutation, or live trading.
- `GET /api/command-center` sanitizes and surfaces the same IO contract under
  `advanced_outputs.routes[].io_contract`.
- Settings Command Center UI shows the IO route count and per-route contract id.
- AI Agent contract now advertises Settings state
  `advanced_output_io_contract` and action `advanced_workflow_io_contract`.

## Current Baseline Evidence

With seeded AI Chat and Nodes artifacts, the packet reports:

- 5 advanced route IO contracts.
- Nodes `input_contract` for local workflow id/definition/context metadata.
- Nodes `output_contract` for dry-run data, manifest, and report artifacts.
- Nodes latest output paths for manifest/report metadata without reading files.
- Code partial-health rows still expose the IO contract and latest analysis path.
- Safety flags remain metadata-only with content reads and execution disabled.

This improves AI Agent operability for safe local outputs while preserving the
existing dry-run/static/local-preview/deterministic-calculator boundaries.

## Clean-Room And Safety Boundaries

- No Fincept branding, assets, commercial copy, runtime binaries, installed
  source, or `D:\FinceptTerminal\app\scripts` were used.
- No provider signup, CAPTCHA bypass, payment, identity verification,
  credential flow, or external account access was started.
- No secret value is read or returned, and no local secret store is created.
- No live trading, broker/exchange binding, real balances, margin, leverage,
  short exposure, derivatives, order submission, workflow execution, notebook
  runtime, managed LLM execution, artifact content indexing, or destructive
  lifecycle action is reachable.

## Verification Evidence

- Focused advanced-output/agent/command-center gate:
  `.\.venv\Scripts\python.exe -m pytest tests\test_m22_advanced_workflow_outputs.py tests\test_m21_agent_operability_contract.py tests\test_m22_command_center_contract.py -q --basetemp .omx\pytest-tmp\m23-28-focused-initial`
  -> 9 passed.
- Focused docs/ledger gate:
  `.\.venv\Scripts\python.exe -m pytest tests\test_m22_advanced_workflow_outputs.py tests\test_m21_agent_operability_contract.py tests\test_m22_command_center_contract.py tests\test_m22_mission_ledger.py -q --basetemp .omx\pytest-tmp\m23-28-docs`
  -> 13 passed.
- Focused ruff:
  `.\.venv\Scripts\python.exe -m ruff check src\local_terminal\advanced_outputs.py src\local_terminal\agent_contract.py src\local_terminal\command_center.py tests\test_m22_advanced_workflow_outputs.py tests\test_m21_agent_operability_contract.py tests\test_m22_command_center_contract.py`
  -> passed.
- Full backend gate:
  `.\.venv\Scripts\python.exe -m pytest -q --basetemp .omx\pytest-tmp\m23-28-full`
  with repo-local TEMP/TMP -> 323 passed; full ruff passed.
- Frontend `npm run lint`, `npm run build`, and `npm run e2e` passed; build
  kept the existing Vite chunk-size warning and E2E result was 15 passed.
- Source-wall/live-safety/local-secret/ledger gate:
  `.\.venv\Scripts\python.exe -m pytest tests\test_clean_room_source_wall.py tests\test_m16_live_safety.py tests\test_m20_local_secret_gate.py tests\test_m22_mission_ledger.py -q --basetemp .omx\pytest-tmp\m23-28-safety`
  -> 23 passed.
- FastAPI TestClient smoke confirmed advanced output packet
  `io_contract_route_count=5`, Nodes `nodes_advanced_output_io_v1`, IO safety
  flags denying content read/execution, Command Center current milestone and IO
  route count, AI Agent action contract, and no local secret-store creation.
- Changed-diff secret scan found no credential literals or assignments.
- `git diff --check` passed with Git CRLF working-copy warnings only.

## Handoff

Future Nodes, Code, Quant Lab, and QuantLib work should consult the IO contract
before adding richer local outputs. Do not add workflow execution, notebook
runtime, managed LLM calls, external QuantLib runtime, artifact content indexing,
durable request/response replay, credentials, broker binding, or live behavior
without a separate reviewed safety contract and tests.
