# M20 Nodes Dry-Run Output Bundle

Date: 2026-05-23

## Purpose

M20.15 reduces the Nodes workspace empty-shell surface by turning dry-run planning into a local output bundle. The route still does not execute workflows, deploy agents, mutate external systems, route broker actions, or read private accounts.

## Runtime Surface

- Nodes dry-run responses include `output_summary` with output mode, step count, provider-cache read count, paper-intent count, blocked-external count, context-source count, artifact count, and non-mutating runtime flags.
- Nodes dry-run responses include `artifact_files` for `definition`, `dry_run`, `report`, and `manifest`.
- `LocalStateStore.write_nodes_state()` writes:
  - `artifacts/workflows/{workflow_id}/definition.json`
  - `artifacts/workflows/{workflow_id}/dry_run.json`
  - `artifacts/workflows/{workflow_id}/dry_run_report.md`
  - `artifacts/workflows/{workflow_id}/dry_run_manifest.json`
- The Nodes property panel surfaces output mode, provider reads, context sources, and artifact paths after dry-run.

## Safety

- Deploy and Execute remain disabled in UI and API surfaces.
- Dry-runs remain non-mutating and local-artifact-only.
- No live/private data path, private API key flow, real balance read, real order, margin, leverage, short, derivatives execution, cloud account, billing, subscription, CR/credits, installed-source use, or external mutation was added.
- Artifact paths are normalized to the active workflow artifact directory and limited to JSON/Markdown outputs.

## Verification

- Focused Nodes/context tests: `.\.venv\Scripts\python.exe -m pytest tests\test_m11_nodes.py tests\test_m19_advanced_routes_context.py -q` -> 10 passed.
- Focused Python lint: `.\.venv\Scripts\python.exe -m ruff check src\local_terminal\nodes.py src\local_terminal\storage.py tests\test_m11_nodes.py tests\test_m19_advanced_routes_context.py` -> passed.
- Focused Python format check passed after formatting changed Python files.
- Full pytest: `.\.venv\Scripts\python.exe -m pytest -q` -> 180 passed.
- Source-wall/live-safety tests: `.\.venv\Scripts\python.exe -m pytest tests\test_clean_room_source_wall.py tests\test_m16_live_safety.py -q` -> 12 passed.
- Full Python lint: `.\.venv\Scripts\python.exe -m ruff check .` -> passed.
- Frontend lint/build/e2e: `npm run lint`, `npm run build`, and `npm run e2e` -> passed.
- Diff check: `git diff --check` -> passed with Git CRLF working-copy warnings only.
- UI evidence: `artifacts/screenshots/m20-15-nodes-dry-run-output.png`.
- Code-review gate: no CRITICAL/HIGH/BLOCK findings. Watch item: report/manifest lifecycle, prune, and repair behavior should be added before high-volume workflow use or any executable runtime contract.
