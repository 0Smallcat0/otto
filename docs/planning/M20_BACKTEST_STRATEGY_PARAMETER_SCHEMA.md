# M20.10 Backtest Strategy Parameter Schema

Date: 2026-05-23

## Purpose

Close the M20.9 architecture watch before adding more strategy engines. Backtest and Algo now consume a strategy parameter schema from the Backtest catalog instead of treating every strategy as an implicit pair of hard-coded window labels.

## Runtime Surface

- Backtest catalog entries include `parameter_schema_version`, parameter defaults, bounds, roles, validation constraints, artifact contract, and execution safety metadata.
- `backtest_strategy_catalog()` returns a deep copy so runtime callers cannot mutate the backend catalog constant.
- `normalize_backtest_config()` and Algo strategy normalization both validate strategy windows through the same Backtest parameter schema.
- Backtest manifests record the selected strategy parameter schema, constraints, and artifact contract.
- Backtest and Algo frontends share one offline fallback strategy schema helper and render labels/defaults/bounds from `parameters`.
- Backtest and Algo E2E now verify the schema text, constraint, and parameter ranges in the browser.
- Repo-local JSON/JSONL writes now use unique temp files plus a short `PermissionError` retry for Windows atomic replace locks observed during repeated Playwright runs.
- Failed repo-local JSON/JSONL writes remove their temporary file after retry exhaustion so locked Windows writes do not leave stale payload fragments.
- Existing Playwright action flows now wait for route sync plus the specific POST response before asserting route-specific results, reducing false negatives from initial-load/action races.

## Safety

This milestone adds no strategy engine, live deployment, broker routing, real order, private API key flow, real balance read, margin, leverage, short exposure, derivatives execution, subscription, billing, CR/credits, cloud account, credential storage, installed-source read, or Fincept branding/assets/copy.

## Verification

- Focused gate `.\.venv\Scripts\python.exe -m pytest tests\test_m2_local_state.py tests\test_m6_backtest.py tests\test_m10_algo.py -q` with repo-local TEMP/TMP -> 27 passed.
- Full backend gate `.\.venv\Scripts\python.exe -m pytest -q` with repo-local TEMP/TMP -> 177 passed.
- Focused source-wall/live-safety gate `.\.venv\Scripts\python.exe -m pytest tests\test_clean_room_source_wall.py tests\test_m16_live_safety.py -q` with repo-local TEMP/TMP -> 12 passed.
- Python lint `.\.venv\Scripts\python.exe -m ruff check .` -> passed.
- Python formatting check `.\.venv\Scripts\python.exe -m ruff format --check src\local_terminal\storage.py src\local_terminal\backtest.py src\local_terminal\algo.py tests\test_m2_local_state.py tests\test_m6_backtest.py tests\test_m10_algo.py` -> passed after formatting changed Python files.
- Frontend `npm run lint`, `npm run build`, and `npm run e2e` -> passed; Playwright reported 15 passed.
- Frontend E2E captures `artifacts/screenshots/m20-10-backtest-strategy-parameter-schema.png` and `artifacts/screenshots/m20-10-algo-strategy-parameter-schema.png`.
- Browser/Playwright screenshots were visually inspected for readable parameter schema, artifact contract, constraints, and no incoherent overlap.
- Changed-file credential-like string scan found no real credential, PIN, provider-key, private-key, or personal-account literal; matches were existing safety/type/redaction terms and test redaction probes only.
- Code-review gate found no CRITICAL/HIGH/BLOCK findings after the temp cleanup and E2E wait-response follow-up. WATCH: backend Backtest catalog remains the source of truth while the frontend helper is an offline fallback mirror.
