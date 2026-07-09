# M23.54 Portfolio Report Health Matrix

Date: 2026-05-27

## Scope

M23.54 deepens Portfolio AI Agent supervision without adding optimizer, live,
broker, balance, or destructive artifact behavior. It adds a metadata-only
health matrix for local Portfolio report directories so an agent can verify
expected report files before selecting reports, reading provenance summaries, or
asking a human to review generated artifacts.

## Product Behavior

- Added `GET /api/portfolio/report-health`.
- Embedded `report_health` in `GET /api/portfolio`.
- Added Portfolio UI selector `portfolio-report-health`.
- Added AI Agent state field `report_health`.
- Added AI Agent action `portfolio_report_health`.
- Command Center current milestone and provenance now point to this milestone.

The health matrix inventories expected Portfolio report files for
`portfolio-report-*` directories:

- `summary.json`
- `risk.json`
- `performance.csv`
- `allocation.csv`
- `exposure.csv`
- `lineage.json`
- `artifact_health.json`
- `report.md`
- `manifest.json`

Each row reports expected, present, and missing artifact counts, manifest,
lineage, artifact-health paths, `supervision_ready`, and a non-mutating recovery
hint.

## Safety Boundary

This slice is read-only and metadata-only. It does not read report contents,
index artifact text, repair files, rerun reports, optimize portfolios, import
real balances, route broker orders, touch credentials, call providers, or enable
live/private trading.

Report regeneration remains the existing explicit local `POST
/api/portfolio/report` action. In-place repair, archive, prune, delete, restore,
and content indexing remain out of scope.

## Verification Plan

- Portfolio API tests cover complete and partial report health states.
- Agent-contract tests cover `report_health` state and
  `portfolio_report_health` action.
- Command Center tests cover current milestone/provenance and action-matrix
  visibility.
- Frontend E2E covers the Portfolio health selector and updated action count.
- Source-wall, live-safety, local-secret, and secret scans must remain clean.

## Verification Evidence

- Focused Portfolio/Agent/Command Center/ledger gate -> 30 passed.
- Full backend gate -> 370 passed.
- Full ruff -> passed.
- Frontend lint/build/e2e -> lint passed, build passed with the existing Vite
  chunk-size warning, E2E 15 passed.
- Source-wall/live-safety/local-secret/ledger gate -> 23 passed.
- FastAPI TestClient smoke confirmed `metadata_only_portfolio_report_health`,
  embedded Portfolio health parity, Command Center action count `68`, and no
  local secret-store file creation.
- `git diff --check` passed with Git CRLF working-copy warnings only.
