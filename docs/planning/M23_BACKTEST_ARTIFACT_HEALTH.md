# M23.52 Backtest Artifact Health Matrix

Date: 2026-05-27

## Scope

M23.52 deepens Backtest AI Agent supervision without adding execution breadth.
It adds a metadata-only health matrix for local closed-candle Backtest run
directories so an agent can verify whether expected artifacts exist before using
the run index, comparison packet, Portfolio lineage, or human review surfaces.

## Product Behavior

- Added `GET /api/backtest/artifact-health`.
- Embedded `artifact_health` in `GET /api/backtest`.
- Added Backtest UI selector `backtest-artifact-health`.
- Added AI Agent state field `artifact_health`.
- Added AI Agent action `backtest_artifact_health`.
- Command Center current milestone and provenance now point to this milestone.

The health matrix inventories expected Backtest run files for `bt-*` local
closed-candle runs:

- `config.json`
- `data_snapshot.json`
- `summary.json`
- `trades.csv`
- `signals.csv`
- `indicators.json`
- `returns_analysis.json`
- `returns_curve.csv`
- `provenance.json`
- `report.md`
- `manifest.json`

Each row reports expected, present, and missing artifact counts, latest artifact
path, manifest path, `supervision_ready`, and a non-mutating recovery hint.

## Safety Boundary

This slice is read-only and metadata-only. It does not read artifact contents,
repair files, rerun Backtests, optimize parameters, replay actions, deploy
strategies, route broker orders, read balances, touch credentials, call
providers, or enable live/private trading.

Walk-forward `wfa-*` bundles and comparison bundles are intentionally out of
scope for this matrix. They have different artifact contracts and should get a
separate bounded health slice if needed.

## Verification Plan

- Backtest API tests cover complete and partial run health states.
- Agent-contract tests cover `artifact_health` state and
  `backtest_artifact_health` action.
- Command Center tests cover current milestone/provenance and action-matrix
  visibility.
- Frontend E2E covers the Backtest health selector and updated action count.
- Source-wall, live-safety, local-secret, and secret scans must remain clean.
