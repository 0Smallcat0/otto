# M21.17 Provider Refresh Result Semantics

Date: 2026-05-25

## Scope

Clarify manual public-provider refresh results so AI Agents can distinguish a
cache written by the current refresh from a stale or previously available cache.
This closes the M21.16 architecture watch on `cache_written` being too close to
cache availability.

## Fincept Observation Boundary

The installed app was opened for safe UI observation only. It first showed a
recover-session prompt with non-destructive skip/restore choices; `SKIP` was used
because the prompt stated that skipping does not delete snapshots. The Settings
route was then opened and observed as a dense left-category configuration center
with Data Sources and Storage/Cache style workflow categories. Account, billing,
credit, and toolbar identity details were not retained as artifacts or copied into
the local product.

No Fincept source, package code, runtime binary, screenshot, credential, token,
PIN, payment, or personal data was saved.

## Implementation

- Added explicit provider refresh result fields:
  - `cache_written_this_run`
  - `cache_available`
  - `cache_reused`
  - `cache_write_status`
- Kept `cache_written` as a compatibility alias for `cache_written_this_run`.
- Updated refresh summaries with `cache_written_this_run`, `cache_available`, and
  `cache_reused` counts.
- Updated lifecycle run summaries and refresh reports so historical manifests
  expose the same cache semantics when present.
- Updated Provider Freshness UI to show written / available / reused counts.
- Updated the AI Agent Settings contract with `provider_refresh_public_start` and
  `provider_refresh_result_semantics`.

## Safety

- No provider signup, credential entry, provider-key read/write, paid provider,
  optional-key refresh, broker/exchange key flow, real balance read, live order,
  margin, leverage, short exposure, derivatives, Fincept branding, installed-source
  read, or fixture-primary runtime path was added.
- The refresh remains manual, public no-key, local-artifact-producing, and bounded
  by the existing provider refresh job lifecycle.

## Verification

- Focused provider/agent tests:
  `.\.venv\Scripts\python.exe -m pytest tests\test_m19_provider_registry.py tests\test_m21_agent_operability_contract.py -q --basetemp .tmp\pytest-m21-17-focused`
  -> 16 passed.
- Targeted ruff:
  `.\.venv\Scripts\python.exe -m ruff check src\local_terminal\provider_refresh.py src\local_terminal\agent_contract.py tests\test_m19_provider_registry.py tests\test_m21_agent_operability_contract.py`
  -> passed.
- Frontend lint: `npm run lint` in `frontend/` -> passed.
- Frontend build: `npm run build` in `frontend/` -> passed.
- Playwright E2E: `npm run e2e` in `frontend/` -> 15 passed.
- Browser smoke opened the local Dashboard, ran manual public source refresh, and
  confirmed Provider Freshness showed separate written / available / reused counts.
- Screenshot evidence:
  `artifacts/screenshots/m21-provider-refresh-result-semantics.png`.
- Visual verdict evidence:
  `.omx/state/m21-provider-refresh-result-semantics/ralph-progress.json`.
- Full backend gate:
  `.\.venv\Scripts\python.exe -m pytest -q --basetemp .tmp\pytest-m21-17-full-final`
  with repo-local TEMP/TMP -> 241 passed.
- Source-wall/live-safety gate:
  `.\.venv\Scripts\python.exe -m pytest tests\test_clean_room_source_wall.py tests\test_m16_live_safety.py -q --basetemp .tmp\pytest-m21-17-safety-final`
  with repo-local TEMP/TMP -> 12 passed.
- Full ruff: `.\.venv\Scripts\python.exe -m ruff check .` -> passed.
- Generic high-risk secret scan over changed/untracked text files returned zero
  matches for credential assignment, bearer token, provider key prefix, and private
  key block patterns.
- `git diff --check` -> passed with Git CRLF working-copy warnings only.
- Code-review gate -> APPROVE with no CRITICAL/HIGH/MEDIUM/LOW findings and
  architectural status CLEAR.
