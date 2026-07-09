# M20.17 Quant Lab Context Bundle

Date: 2026-05-23

## Intent

Reduce Quant Lab's empty-shell risk by turning each safe local preview into a provider/cache and artifact-backed bundle. This keeps the route aligned with the M19 advanced-route requirement that Quant Lab modules consume provider/artifact inputs and write local outputs.

## Scope

- Add source provenance rows to Quant Lab preview output from the shared advanced context.
- Add local artifact input rows so previews can show which local artifacts were available as read-only context.
- Write `context.json` and `manifest.json` in each preview run directory beside the existing `input.json`, `output.json`, `report.md`, and `error.log`.
- Surface output mode, context source counts, source rows, artifact input rows, and bundle artifact paths in the Quant Lab UI.
- Keep deferred modules and runtime actions gated.

## Safety

- No script execution.
- No external runtime or external network execution.
- No deep-agent execution or model training.
- No broker mutation, real orders, real balances, margin, leverage, short exposure, or derivatives execution.
- No credential, provider key, token, PIN, private key, personal account detail, cloud, billing, subscription, or CR/credits path was added.
- No installed Fincept implementation source, runtime, asset, branding, commercial copy, or exact UI copy was used.

## Verification

- `.\.venv\Scripts\python.exe -m pytest tests\test_m13_quant_lab.py tests\test_m19_advanced_routes_context.py -q` with repo-local TEMP/TMP -> 10 passed.
- `.\.venv\Scripts\python.exe -m pytest -q` with repo-local TEMP/TMP -> 181 passed.
- `.\.venv\Scripts\python.exe -m pytest tests\test_clean_room_source_wall.py tests\test_m16_live_safety.py -q` with repo-local TEMP/TMP -> 12 passed.
- `.\.venv\Scripts\python.exe -m ruff check .` -> passed.
- `npm run lint` -> passed.
- `npm run build` -> passed.
- `npm run e2e` -> 15 passed.
- `git diff --check` -> passed with Git CRLF working-copy warnings only.
- Screenshot evidence: `artifacts/screenshots/m20-17-quant-lab-context-bundle.png`.

## Watch

Quant Lab remains preview/bundle-only. Any executable module runner, deep-agent behavior, model training, or external runtime must be handled by a separate sandbox/runtime/security contract and review.
