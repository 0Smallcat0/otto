# M21 Observation And Comparison Protocol

Date: 2026-05-24

## Purpose

M21 must improve replication depth from observed Fincept behavior without copying
Fincept source, identity, assets, or commercial mechanics. Observation is workflow
evidence, not implementation material.

## Allowed Evidence

- Safe operation of the installed Fincept app for the selected route or workflow.
- De-identified screenshots and behavior notes.
- Existing copied research evidence under `docs/reference/fincept-platform-test/`.
- Existing JSON UI logs and screenshot indexes in the reference evidence bundle.
- Public provider documentation and primary-source API docs.
- Local app screenshots, Playwright traces, API payloads, and generated artifacts.

## Forbidden Evidence

- `D:\FinceptTerminal\app\scripts`.
- Installed package source.
- Runtime binaries as implementation inputs.
- Fincept branding, logo, trademark, commercial copy, subscription, billing, CR/credits,
  payment, cloud-account mechanics, or private account state.
- Screenshots containing credentials, PINs, payment details, provider keys, account
  identifiers, or personal data.

## Observation Record Schema

For each selected workflow, write a sanitized note with:

- `route`
- `source_evidence`
- `observation_time`
- `navigation_path`
- `interaction_steps`
- `state_transitions`
- `inputs`
- `outputs`
- `errors_or_empty_states`
- `data_sources_visible`
- `artifact_or_export_behavior`
- `terminal_density_notes`
- `panel_structure_notes`
- `agent_operable_contract`
- `clean_room_exclusions`
- `local_gap`
- `verification_plan`

## Screenshot Index Schema

For every retained screenshot:

- `screenshot_id`
- `route`
- `source`: `fincept_observed` or `local_comparison`
- `path`
- `captured_at`
- `sanitized`: true or false
- `sensitive_content_removed`: true or false
- `workflow_step`
- `notes`

Any screenshot that cannot be sanitized must be deleted and replaced by text-only notes.

## Local Comparison Protocol

1. Start the backend and frontend with documented commands from
   `docs/planning/FINAL_HANDOFF.md`.
2. Open the local app in the browser.
3. Capture route/workflow screenshots for changed surfaces.
4. Compare against Fincept evidence for workflow order, state naming, panel density,
   source attribution, and error/empty states.
5. Use visual-verdict for material visual changes.
6. Do not claim parity from visual resemblance alone. Require API state, artifacts,
   tests, and source-wall/live-safety evidence.

## AI Agent Operability Bar

Every touched workflow should expose stable machine-operable surfaces:

- predictable API endpoints
- explicit state and error fields
- source/cache/artifact paths
- redacted credential status
- stable selectors or test ids where frontend changes occur
- machine-readable artifacts and manifests

## Current M21 Slice

The initial M21 slice is governance, route-gap, provider-matrix, observation-protocol,
and bounded lifecycle planning. Fresh Fincept operation is required before any later
route-specific UI or behavior implementation that lacks adequate existing evidence.

## M21.2 Observation Artifact

News route observation and comparison evidence for the GDELT DOC slice is recorded in
`docs/planning/M21_NEWS_GDELT_DOC.md`. No Fincept screenshot was retained because the
running app included account/credit toolbar surfaces; the artifact keeps text-only,
sanitized workflow evidence.

## M21.3 Observation Artifact

Markets Commodities observation and comparison evidence for the EIA energy-context
slice is recorded in `docs/planning/M21_EIA_ENERGY_CONTEXT.md`. A live installed-app
attempt on 2026-05-24 reached a locked terminal state; no credentials were entered
and no new Fincept screenshot was retained. The slice uses existing sanitized
Markets UI logs and local comparison evidence.

## M21.4 Observation Artifact

AI Agent operability and advanced route observation for the contract slice is recorded
in `docs/planning/M21_AGENT_OPERABILITY_CONTRACT.md`. A live installed-app observation
on 2026-05-24 used authorized unlock input without logging or saving credential
material, reached a commercial/account-like gate that is excluded from the local
product, then continued to Dashboard and QuantLib route surfaces. No Fincept
screenshot was retained because account/commercial toolbar content was visible. The
local contract uses only sanitized route/action/panel behavior and independent
implementation.

## M21.5 Observation Artifact

Provider refresh lifecycle observation for M21.5 is recorded in
`docs/planning/M21_PROVIDER_REFRESH_LIFECYCLE.md`. The installed app was launched on
2026-05-24 but stopped at the locked terminal screen before refresh/settings lifecycle
workflows were reachable. No credential or PIN was entered for this slice, no
screenshot was retained, and existing sanitized M21 Markets/News/Agent observations
were used only for abstract workflow-state guidance.

## M21.7 Observation Artifact

Backtest walk-forward observation and comparison evidence is recorded in
`docs/planning/M21_BACKTEST_WALK_FORWARD.md`. Existing sanitized Backtest UI logs were
used to confirm the dense provider/command/result structure and enabled
`Walk-Forward` command. The installed app process/window was present on 2026-05-24,
but no screenshot or account/commercial toolbar state was retained, and no credential
or PIN material was saved, logged, or output.

## M21.11 Observation Artifact

Markets macro panel split observation and comparison evidence is recorded in
`docs/planning/M21_MARKETS_MACRO_PANEL_SPLIT.md`. The installed app was launched on
2026-05-25, confirmed responsive, and stopped without entering credentials or PIN.
No new Fincept screenshot was retained. The slice uses existing sanitized Markets
screenshot and UI-log evidence for dense route/panel/source-state behavior, then
compares against local browser screenshots for the independently implemented
Provider Stack and Source Contract panels.

## M21.12 Observation Artifact

Markets non-macro provider/source contract observation and comparison evidence is
recorded in `docs/planning/M21_MARKETS_PROVIDER_SOURCE_CONTRACTS.md`. The installed
app was launched on 2026-05-25, confirmed responsive, and stopped without entering
credentials or PIN. No new Fincept screenshot was retained. Existing sanitized
Markets UI logs were parsed for the route controls, table headers, and panel names
that shape the local dense provider/source contract panels.
