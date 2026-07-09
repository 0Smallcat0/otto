# M20.18 QuantLib Provenance Bundle

Date: 2026-05-23

## Intent

Reduce QuantLib's calculator-shell risk by making each deterministic local calculation carry provider/cache and artifact provenance. This satisfies the M19 advanced-route requirement that QuantLib calculators save results and show input/output provenance when market or local artifact context is used.

## Scope

- Add source provenance rows to QuantLib response output from the shared advanced context.
- Add local artifact input rows so calculations expose which local artifacts were available as read-only context.
- Write `context.json` and `manifest.json` in each calculation directory beside `request.json`, `response.json`, `report.md`, and `error.log`.
- Surface output mode, context source counts, source rows, artifact input rows, and bundle artifact paths in the QuantLib UI.
- Keep external QuantLib runtime and external API execution gated.

## Safety

- No external QuantLib runtime.
- No external API execution or external network execution.
- No broker mutation, real orders, real balances, margin, leverage, short exposure, or derivatives execution.
- No credential, provider key, token, PIN, private key, personal account detail, cloud, billing, subscription, or CR/credits path was added.
- No installed Fincept implementation source, runtime, asset, branding, commercial copy, or exact UI copy was used.

## Verification

- `.\.venv\Scripts\python.exe -m pytest tests\test_m14_quantlib.py tests\test_m19_advanced_routes_context.py -q` with repo-local TEMP/TMP -> 12 passed.
- `.\.venv\Scripts\python.exe -m pytest -q` with repo-local TEMP/TMP -> 181 passed.
- `.\.venv\Scripts\python.exe -m pytest tests\test_clean_room_source_wall.py tests\test_m16_live_safety.py -q` with repo-local TEMP/TMP -> 12 passed.
- `.\.venv\Scripts\python.exe -m ruff check .` -> passed.
- `npm run lint` -> passed.
- `npm run build` -> passed.
- `npm run e2e` -> 15 passed.
- `git diff --check` -> passed with Git CRLF working-copy warnings only.
- Screenshot evidence: `artifacts/screenshots/m20-18-quantlib-provenance-bundle.png`.

## Watch

QuantLib remains deterministic stdlib calculation plus provenance. External QuantLib runtime, broader calculator lifecycle management, and executable/sandboxed expansion require separate contracts and review.
