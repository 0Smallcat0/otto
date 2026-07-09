# M21.15 Algo Scan Artifact Lifecycle Health

Date: 2026-05-25

## Purpose

Close the M21.14 architecture watch by moving Algo scan artifact mirroring behind
a dedicated storage lifecycle boundary. The Algo Scanner now exposes latest-scan
artifact health, expected-file counts, non-destructive repair status, and a
stable repair action for AI Agents while remaining local research-only.

## Fincept Observation Evidence

- Sanitized reference screenshot:
  `docs/reference/fincept-platform-test/screenshots/subfeatures/algo/scanner.png`.
- Sanitized UI log:
  `docs/reference/fincept-platform-test/logs/subfeatures/algo/scanner-ui.json`.
- Observed workflow shape: dense Algo route, Builder/My Strategies/Scanner/Dashboard
  tabs, Scan Conditions, `SCAN MARKET`, scan results, status strip, and `0 LIVE`
  state.
- Local replication choice: preserve the scanner workflow order and terminal
  density, but replace cloud/live-deploy assumptions with local artifact health,
  state-derived repair, and explicit non-destructive safety state.

## Implementation Notes

- `LocalStateStore.write_algo_state` delegates scan artifact writes to
  `write_algo_scan_artifacts`, separating state persistence from lifecycle mirror
  maintenance.
- `algo_scan_artifact_health` reports `no_scan`, `complete`, or
  `repairable_missing`, plus expected/present/missing counts and per-file status.
- Tampered latest-scan state reports `invalid_scan_state` with a validation
  reason and disables repair instead of being collapsed into `no_scan`.
- `/api/algo/scan-artifacts` returns health and safety metadata without mutating
  content.
- `/api/algo/scan-artifacts/repair` rewrites only the expected latest-scan
  `scan.json`, `scan_report.md`, and `manifest.json` files from normalized local
  scan state.
- The Algo UI exposes health, file state, destructive-action status, and a
  `REPAIR ARTIFACTS` action in the Scanner artifacts panel.
- `/api/agent-contract` now advertises `scan_artifact_health` and
  `algo_scan_artifacts_repair` for agent-operable lifecycle repair.

## Safety

- Repair is state-derived and non-destructive; it does not delete, archive,
  prune, replay, move, restore, or read secret material.
- Scanner outputs remain signal-only and non-actionable.
- No live deployment, broker routing, private API, real balance, margin,
  leverage, short exposure, derivatives, paid provider activation, Fincept
  branding, installed-source read, credential capture, or fixture-primary runtime
  was added.
- Path writes remain constrained to the repo-local state root by existing storage
  write guards and normalized Algo scan artifact paths.

## Verification

- Focused backend/contract gate:
  `.\.venv\Scripts\python.exe -m pytest tests\test_m10_algo.py tests\test_m21_agent_operability_contract.py tests\test_m2_local_state.py -q --basetemp .tmp\pytest-m21-15-focused-reviewfix`
  -> 27 passed after adding invalid-scan-state health regression coverage.
- Targeted Python lint:
  `.\.venv\Scripts\python.exe -m ruff check src\local_terminal\storage.py src\local_terminal\server.py src\local_terminal\agent_contract.py tests\test_m10_algo.py tests\test_m21_agent_operability_contract.py tests\test_m2_local_state.py`
  -> passed.
- Frontend typecheck: `npm run lint` in `frontend/` -> passed.
- Browser smoke: opened local Algo, saved a local strategy, ran Scanner, clicked
  `REPAIR ARTIFACTS`, and confirmed `HEALTH complete`, `PRESENT 3/3 / MISSING 0`,
  `DESTRUCTIVE false`, and `Scan artifacts repaired`.
- Screenshot evidence:
  `artifacts/screenshots/m21-algo-scan-artifact-lifecycle.png` (ignored local
  artifact).
- Visual verdict: pass, score 91, recorded in
  `.omx/state/m21-algo-scan-artifact-lifecycle/ralph-progress.json`.
- Full backend gate:
  `.\.venv\Scripts\python.exe -m pytest -q --basetemp .tmp\pytest-m21-15-full-reviewfix`
  with repo-local TEMP/TMP -> 239 passed.
- Source-wall/live-safety gate:
  `.\.venv\Scripts\python.exe -m pytest tests\test_clean_room_source_wall.py tests\test_m16_live_safety.py -q --basetemp .tmp\pytest-m21-15-safety-reviewfix`
  with repo-local TEMP/TMP -> 12 passed.
- Full Python lint: `.\.venv\Scripts\python.exe -m ruff check .` -> passed.
- Frontend build: `npm run build` in `frontend/` -> passed.
- Frontend E2E: `npm run e2e` in `frontend/` -> 15 passed.
- Generic high-risk secret scan over changed/untracked text files found zero
  matches for API-key assignment, bearer token, OpenAI key, private key,
  password assignment, and PIN assignment patterns.
- `git diff --check` -> passed with Git CRLF working-copy warnings only.
- Code-review gate: COMMENT. The initial MEDIUM finding for invalid scan state
  being collapsed to `no_scan` was fixed before commit; code-reviewer re-check
  approved the fix. Architecture WATCH remains: generic Algo state writes still
  rewrite the latest scan mirror idempotently, so future archive/replay/prune
  semantics should narrow mutation ownership first.
