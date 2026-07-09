# M20 Code Static Analysis Artifacts

Date: 2026-05-23

## Purpose

M20.16 reduces the Code workspace empty-shell surface by adding a local static notebook analysis workflow. It produces useful notebook/report artifacts from local notebook state and provider/cache/artifact context without enabling Python execution.

## Runtime Surface

- The Code toolbar adds `ANALYZE`.
- `/api/code/analyze` saves the selected notebook context and writes a static analysis result.
- `LocalStateStore.write_code_state()` writes:
  - `artifacts/code_workspace/{notebook_id}.ipynb`
  - `artifacts/code_workspace/{notebook_id}/analysis.json`
  - `artifacts/code_workspace/{notebook_id}/analysis_report.md`
  - `artifacts/code_workspace/{notebook_id}/analysis_manifest.json`
- The Code side panel shows output mode, cell count, source-line count, context-source count, and artifact paths from the latest analysis.

## Safety

- This is static analysis only. Notebook cells are not executed.
- RUN and RUN ALL remain disabled.
- No kernel process, external network, broker mutation, credential persistence, real balance read, real order, margin, leverage, short exposure, derivatives execution, cloud account, billing, subscription, CR/credits, installed-source use, or external mutation was added.
- Durable notebook state and artifact path metadata remain normalized as untrusted input.

## Verification

- Focused Code/context tests: `.\.venv\Scripts\python.exe -m pytest tests\test_m12_code_workspace.py tests\test_m19_advanced_routes_context.py -q` -> 11 passed.
- Focused Python lint: `.\.venv\Scripts\python.exe -m ruff check src\local_terminal\code_workspace.py src\local_terminal\storage.py src\local_terminal\server.py tests\test_m12_code_workspace.py` -> passed.
- Focused Python format check passed after formatting changed Python files.
- Full pytest: `.\.venv\Scripts\python.exe -m pytest -q` -> 181 passed.
- Source-wall/live-safety tests: `.\.venv\Scripts\python.exe -m pytest tests\test_clean_room_source_wall.py tests\test_m16_live_safety.py -q` -> 12 passed.
- Full Python lint: `.\.venv\Scripts\python.exe -m ruff check .` -> passed.
- Frontend lint/build/e2e: `npm run lint`, `npm run build`, and `npm run e2e` -> passed.
- UI evidence: `artifacts/screenshots/m20-16-code-analysis-artifacts.png`.
- Code-review gate: no CRITICAL/HIGH/BLOCK findings. Watch item: real notebook execution still requires a separate sandbox/runtime contract, artifact lifecycle policy, and security review.
