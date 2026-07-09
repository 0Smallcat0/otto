# M21.14 Algo Provider Cache Scan Artifacts

Date: 2026-05-25

## Purpose

Deepen the Algo route scanner from a transient dry-run result into an
AI-agent-operable local signal workflow. The scanner now records provider/cache
source state, per-row evidence, local-only safety flags, and scan artifacts while
remaining signal-only and non-executable.

## Fincept Observation Evidence

- Sanitized reference screenshot:
  `docs/reference/fincept-platform-test/screenshots/subfeatures/algo/scanner.png`.
- Sanitized UI log:
  `docs/reference/fincept-platform-test/logs/subfeatures/algo/scanner-ui.json`.
- Observed workflow shape: dense Algo route, Builder/My Strategies/Scanner/Dashboard
  tabs, Scan Conditions, symbols/parameters, timeframe, lookback, `SCAN MARKET`,
  Scan Results table, engine/status strip, and `0 LIVE` state.
- Local replication choice: keep the same scanner workflow order and dense panels,
  but replace account/cloud/live-deployment semantics with provider-cache source
  contracts, local artifacts, and explicit non-actionable research signals.

## Implementation Notes

- `scan_market` now derives signal/match from available public market cache fields
  (`price`, `chg_pct`, `high`, `low`, `vol`) instead of a symbol/name seed.
- Scan results include `data_source`, `data_state`, `provider_id`, `cache_path`,
  `price`, `change_pct`, and `actionable: false`.
- Scan payloads include `source_contract`, `artifact_dir`, and `artifacts` for
  `scan.json`, `scan_report.md`, and `manifest.json`.
- `LocalStateStore.write_algo_state` mirrors the latest scan into
  `artifacts/algo/scans/{scan_id}/`.
- The Algo UI exposes Source Contract and Artifacts panels with stable selectors:
  `algo-scan-source-contract` and `algo-scan-artifacts`.
- `/api/agent-contract` now advertises `scan_source_contract` and `scan_artifacts`
  for the Algo route and includes source/artifact fields in `algo_scan`.

## Safety

- Signals are local research outputs only and are never executable orders.
- No live deployment, broker routing, private API, real balance, margin, leverage,
  short exposure, derivatives, paid provider activation, Fincept branding,
  installed-source read, credential capture, or fixture-primary runtime was added.
- Tampered scan artifact paths are rejected before state mutation and cannot write
  outside the repo-local state root.

## Verification

- Focused backend/contract gate:
  `.\.venv\Scripts\python.exe -m pytest tests\test_m10_algo.py tests\test_m2_local_state.py tests\test_m21_agent_operability_contract.py -q --basetemp .tmp\pytest-m21-14-focused-fix`
  -> 25 passed after adding the missing-symbol provenance regression.
- Targeted Python lint:
  `.\.venv\Scripts\python.exe -m ruff check src\local_terminal\algo.py src\local_terminal\storage.py src\local_terminal\agent_contract.py tests\test_m10_algo.py tests\test_m2_local_state.py tests\test_m21_agent_operability_contract.py`
  -> passed.
- Frontend typecheck: `npm run lint` in `frontend/` -> passed.
- Browser smoke: opened local Algo, saved a strategy, ran Scanner, and confirmed
  `Algo scan source contract` plus `Algo scan artifacts` regions are visible.
- Screenshot evidence:
  `artifacts/screenshots/m21-algo-provider-cache-scan.png` (ignored local artifact).
- Visual verdict: pass, score 91, recorded in
  `.omx/state/m21-algo-provider-cache-scan/ralph-progress.json`.
- Full backend gate:
  `.\.venv\Scripts\python.exe -m pytest -q --basetemp .tmp\pytest-m21-14-full-final`
  with repo-local TEMP/TMP -> 237 passed.
- Source-wall/live-safety gate:
  `.\.venv\Scripts\python.exe -m pytest tests\test_clean_room_source_wall.py tests\test_m16_live_safety.py -q --basetemp .tmp\pytest-m21-14-safety-final`
  with repo-local TEMP/TMP -> 12 passed.
- Full Python lint: `.\.venv\Scripts\python.exe -m ruff check .` -> passed.
- Frontend build: `npm run build` in `frontend/` -> passed.
- Frontend E2E: `npm run e2e` in `frontend/` -> 15 passed.
- Generic high-risk secret scan over changed/untracked files found zero matches
  for API-key assignment, bearer token, OpenAI key, private key, password
  assignment, and PIN assignment patterns.
- `git diff --check` -> passed with Git CRLF working-copy warnings only.
- Code-review gate: COMMENT. The code-reviewer approved after the
  missing-symbol provenance fix, with no unresolved CRITICAL/HIGH/MEDIUM/LOW
  findings. The architecture lane kept a WATCH that scan artifacts are still
  emitted from the broad Algo state writer and should get a dedicated lifecycle
  boundary before archive/replay/prune semantics grow.
