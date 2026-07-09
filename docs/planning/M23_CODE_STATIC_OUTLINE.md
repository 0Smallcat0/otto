# M23.30 Code Static Outline

Date: 2026-05-26

## Scope

M23.30 deepens the Code workspace without enabling notebook execution. The Code
`ANALYZE` action now produces a static notebook outline from local source text:
imports, function/class definitions, calls, and syntax-error markers. This is
for AI Agent inspection and human supervision only.

The milestone does not run cells, start a kernel, call providers, read artifact
contents, store secrets, route broker/exchange actions, submit orders, read
balances, enable margin/leverage/short exposure, execute derivatives, or add
cloud/subscription behavior.

## Product Behavior

- `POST /api/code/analyze` still writes the existing local artifact bundle:
  `analysis.json`, `analysis_report.md`, and `analysis_manifest.json`.
- `analysis_result.static_outline` and `last_analysis.static_outline` now expose:
  - `imports`
  - `definitions`
  - `calls`
  - `syntax_errors`
  - safety flags proving static parse only, execution disabled, and source not
    returned.
- The summary now includes `import_count`, `definition_count`, `call_count`, and
  `syntax_error_count`.
- The manifest records the same outline so agents can inspect analysis artifacts
  without reading notebook source or executing code.
- The report includes a compact `Static Outline` section.
- The Code UI shows outline counts and the first imports/definitions in the
  Notebook Analysis supervision panel.
- The AI Agent contract and advanced-output IO contract advertise the static
  outline field for `code_analyze`.
- Command Center current milestone and provenance point at this document.

## Safety

- The outline uses Python `ast.parse` only.
- Notebook source is not returned in the outline, manifest, or report.
- Existing validators still reject credential-like content, live/private runtime
  intent, invalid notebook state, path traversal, unsafe stored state, and run
  limit bypass.
- Runtime routes remain disabled through `code_run_disabled` and
  `code_run_all_disabled`.

## Verification

- Focused Code gate:
  `.\.venv\Scripts\python.exe -m pytest tests\test_m12_code_workspace.py -q --basetemp .omx\pytest-tmp\m23-30-code-focused`
  with repo-local TEMP/TMP -> 9 passed.
- Focused Code/Agent/advanced-output/Command Center gate:
  `.\.venv\Scripts\python.exe -m pytest tests\test_m12_code_workspace.py tests\test_m21_agent_operability_contract.py tests\test_m22_advanced_workflow_outputs.py tests\test_m22_command_center_contract.py -q --basetemp .omx\pytest-tmp\m23-30-focused`
  with repo-local TEMP/TMP -> 18 passed.
- Focused ruff:
  `.\.venv\Scripts\python.exe -m ruff check src\local_terminal\code_workspace.py src\local_terminal\agent_contract.py src\local_terminal\advanced_outputs.py src\local_terminal\command_center.py tests\test_m12_code_workspace.py tests\test_m21_agent_operability_contract.py tests\test_m22_advanced_workflow_outputs.py tests\test_m22_command_center_contract.py`
  -> passed.
- Frontend typecheck:
  `npm run lint` in `frontend/` -> passed.
- Focused docs/ledger gate:
  `.\.venv\Scripts\python.exe -m pytest tests\test_m12_code_workspace.py tests\test_m21_agent_operability_contract.py tests\test_m22_advanced_workflow_outputs.py tests\test_m22_command_center_contract.py tests\test_m22_mission_ledger.py -q --basetemp .omx\pytest-tmp\m23-30-docs`
  with repo-local TEMP/TMP -> 22 passed.
- Full backend gate:
  `.\.venv\Scripts\python.exe -m pytest -q --basetemp .omx\pytest-tmp\m23-30-full-final`
  with repo-local TEMP/TMP -> 324 passed.
- Full ruff:
  `.\.venv\Scripts\python.exe -m ruff check .` -> passed.
- Frontend:
  `npm run lint`, `npm run build`, and `npm run e2e` in `frontend/` -> passed;
  build kept only the existing Vite chunk-size warning and E2E result was
  15 passed.
- Source-wall/live-safety/local-secret/ledger gate:
  `.\.venv\Scripts\python.exe -m pytest tests\test_clean_room_source_wall.py tests\test_m16_live_safety.py tests\test_m20_local_secret_gate.py tests\test_m22_mission_ledger.py -q --basetemp .omx\pytest-tmp\m23-30-safety`
  with repo-local TEMP/TMP -> 23 passed.
- FastAPI TestClient smoke confirmed Code `static_outline`
  imports/definitions/calls, Command Center current milestone/provenance, and no
  local secret-store creation.
- Changed-diff secret scan found no personal-account email literals,
  password/PIN literals, provider-key assignments, bearer-token values,
  private-key blocks, protected-value payload assignments, or credential
  assignments.
- `git diff --check` passed with Git CRLF working-copy warnings only.

## Handoff

Future Code work can add more static notebook metadata only if it keeps source
redaction, execution disabled, and artifact content reads disabled. Real
notebook execution, kernels, sandbox expansion, external network calls, provider
calls, artifact content indexing, durable request/response replay, credentials,
broker/exchange binding, real balances, derivatives execution, and live trading
still require separate reviewed safety contracts before they become reachable.
