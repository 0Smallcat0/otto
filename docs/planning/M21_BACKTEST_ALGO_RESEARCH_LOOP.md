# M21.21 Backtest + Algo Research Loop

Date: 2026-05-25

## Objective

Implement a bounded clean-room local research loop that follows the observed
Fincept terminal workflow shape without copying Fincept source, branding, assets,
commercial copy, billing, subscriptions, credits, cloud-account behavior, or runtime
binaries:

`Markets source_coverage_matrix row -> Algo scan artifact -> Backtest scan-seeded
run/provenance -> artifact manifest/source attribution -> AI Agent contracts ->
frontend/E2E evidence`.

## Implemented Scope

- Added `src/local_terminal/research_lineage.py` as the canonical local
  `research_lineage` contract.
- Added deterministic `markets_source_row_id` and `markets_source_row_hash` fields
  to Markets source coverage rows.
- Updated Algo scan to bind one validated Markets source row into scan lineage,
  scan reports, and scan manifests.
- Updated Algo run-backtest to consume the latest local scan seed and propagate
  lineage into Backtest config, provenance, manifest, and result payloads.
- Hardened direct Backtest lineage input so it must match the latest local Algo
  scan seed before artifacts are written.
- Updated AI Agent route/action contracts for source-row identity, research
  lineage, scan seed, and scan-seeded provenance.
- Updated artifact lifecycle metadata to advertise metadata-only lineage manifest
  support for Algo and Backtest roots.
- Updated frontend Markets, Algo, and Backtest surfaces and E2E coverage for the
  source-row -> scan -> Backtest lineage loop.

## Safety Boundary

- Backtest candle data provenance remains separate from contextual Markets source
  attribution.
- Context-only rows may enrich lineage but are never treated as Backtest candle
  data.
- Unknown, tampered, unsafe, out-of-root, unsupported, credential-like,
  live/order/broker-like lineage is rejected before Backtest artifacts are written.
- `live_action_enabled` remains false throughout the loop.
- No new provider adapter, provider signup, credential/key acquisition,
  secret-storage change, paid data, live order path, broker/exchange key flow, real
  balance read, margin, leverage, short exposure, derivatives execution,
  optimize/live deployment, archive/prune/delete/restore execution, Fincept
  branding/assets/source copying, commercial copy, cloud behavior, or fixture-primary
  runtime claim was added.

## Verification

- Focused research-loop tests: 50 passed.
- Full backend tests: 254 passed.
- Source-wall/live-safety tests: 12 passed.
- Ruff: passed.
- Frontend lint/build: passed.
- Playwright E2E: 15 passed.
- Screenshot: `artifacts/screenshots/m21-21-research-lineage-loop.png`.
- Visual verdict: pass, score 91, `.omx/state/m21-21/ralph-progress.json`.
- Secret scan: passed for current diff.
- `git diff --check`: passed with Git CRLF working-copy warnings only.
- Code-review gate: APPROVE after fixing direct Backtest lineage tamper risk.
