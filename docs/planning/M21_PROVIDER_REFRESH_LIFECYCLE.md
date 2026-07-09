# M21.5 Provider Refresh Lifecycle Slice

Date: 2026-05-24

## Scope

M21.5 adds read-only lifecycle and recovery visibility for the manual public
provider refresh jobs introduced in M20.23. This is a bounded lifecycle slice,
not an all-provider breadth milestone and not an automatic refresh scheduler.

## Sanitized Fincept Observation

- `route/workflow`: global refresh / diagnostics / settings-style lifecycle surfaces.
- `source_evidence`: installed app was launched on 2026-05-24 through the UI only.
- `observation_result`: the app reached a locked terminal screen before the selected
  workflow was reachable.
- `credential_handling`: no password, PIN, token, provider key, or personal data was
  entered, echoed, logged, screenshotted, or stored for this slice.
- `retained_outputs`: text-only sanitized note in this document. No Fincept
  screenshot was retained.
- `prior_evidence_used`: existing sanitized M21 News, Markets, and Agent Contract
  observations establish the dense terminal pattern of command rows, explicit
  status/error states, provider/source attribution, and agent-operable routes.
- `clean_room_exclusions`: no installed source, app scripts, package source, assets,
  branding, commercial copy, billing, subscription, credits, or runtime binaries
  were inspected or copied.

## Local Product Requirement

The local terminal should let an AI Agent inspect provider refresh history without
inferring state from scattered directories. It must show:

- current lifecycle mode and stale thresholds;
- queued/running/completed/failed provider refresh runs;
- stale interrupted queued/running jobs;
- manifest-only historical runs;
- corrupt status metadata;
- recovery recommendations that are non-mutating;
- disabled prune/archive/delete/status-rewrite controls.

## Implementation Result

- Added `provider_refresh_lifecycle_payload()` in
  `src/local_terminal/provider_refresh.py`.
- Added `/api/providers/refresh-public/lifecycle`.
- Included `refresh_lifecycle` in `/api/providers`.
- Included provider refresh lifecycle in governance, Help diagnostics, governance
  diagnostic bundles, the Settings UI, and the global Provider Freshness strip.
- Updated the AI Agent contract with a read-only
  `provider_refresh_lifecycle_inspect` action.
- Recovery rows point only to the read-only lifecycle endpoint and do not advertise
  the mutating refresh-job POST endpoint as safe.
- Artifact links are reconstructed from known files that exist under each refresh
  run directory; raw artifact metadata from `job_status.json` or `manifest.json`
  is not echoed back into the lifecycle API.
- Added `tests/test_m21_provider_refresh_lifecycle.py`.

## Safety

- Read-only metadata/status inspection only.
- No provider cache mutation.
- No `job_status.json` repair/write path.
- No prune, archive, delete, recover, or cleanup mutation.
- No external network call.
- No credentials, secret values, private API keys, real orders, real balances, live
  trading, margin, leverage, short exposure, derivatives, or installed-source reads.

## Verification

- Focused lifecycle/governance/agent tests:
  `tests/test_m21_provider_refresh_lifecycle.py`,
  `tests/test_m19_provider_registry.py`,
  `tests/test_m19_governance_routes.py`,
  `tests/test_m21_artifact_lifecycle.py`, and
  `tests/test_m21_agent_operability_contract.py` -> 24 passed.
- Full `.\.venv\Scripts\python.exe -m pytest -q` -> 221 passed.
- Source-wall/live-safety tests -> 12 passed.
- `.\.venv\Scripts\python.exe -m ruff check .` -> passed.
- Frontend `npm run lint`, `npm run build`, and `npm run e2e` -> passed; e2e
  covered 15 workflows.
- Browser check confirmed the Settings Provider Refresh Lifecycle panel and
  `Status Writes` false state.
- Screenshot: `artifacts/screenshots/m21-provider-refresh-lifecycle-settings.png`.
- Visual verdict: score 91, pass.
- `git diff --check` -> passed with Git CRLF working-copy warnings only.
- Sensitive scan across changed/new text files -> `SENSITIVE_SCAN_NO_MATCH`.
- Code-review gate follow-up: initial artifact metadata and read-only recovery
  endpoint findings were fixed; final code-review recommendation APPROVE and
  architecture status CLEAR.

## Remaining Gaps

- Automatic scheduling remains out of scope.
- Durable mutation-based repair of interrupted jobs remains out of scope.
- Prune/archive/delete UX remains disabled until a dedicated lifecycle safety
  contract exists.
- Further Markets provider breadth and panel splitting remain separate M21 choices.
