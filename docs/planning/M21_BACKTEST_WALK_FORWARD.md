# M21.7 Backtest Walk-Forward

Date: 2026-05-24

## Scope

M21.7 implements the observed Backtest `Walk-Forward` command as a local,
fixed-parameter validation workflow. It extends the existing closed-candle Backtest
engine without enabling optimize, live trading, broker routing, leverage, short
selling, derivatives, private provider keys, real balances, or paid data.

## Fincept Observation Evidence

- Source: `docs/reference/fincept-platform-test/logs/backtest-deep-ui-elements.json`
- Source: `docs/reference/fincept-platform-test/FEATURE_MATRIX.md`
- Current installed-app check: `FinceptTerminal` process and main window were present
  on 2026-05-24, but no screenshot or account/commercial toolbar state was retained.
- Observed Backtest shape: dense route with provider buttons, command strip, parameter
  panels, result tabs, export action, and enabled command names including `Run Backtest`,
  `Optimize`, `Walk-Forward`, `Indicators`, `Indicator Signals`, `ML Labels`,
  `CV Splits`, `Returns Analysis`, `Signal Generators`, `Labels -> Signals`, and
  `Indicator Sweep`.

## Local Implementation

- Added `POST /api/backtest/walk-forward`.
- Added `run_walk_forward()` using the same normalized strategy config, public
  closed-candle cache when available, deterministic offline fallback only when no
  public cache is available, and the same no-lookahead next-open fill rule.
- Added bounded `fold_count` validation from 2 to 8, with default 3.
- Added `train_usage: metadata_only_no_fit_no_warmup` to make clear that this slice
  is fixed-parameter fold replay, not optimizer training or indicator warm-up.
- Added local artifacts under `artifacts/backtests/{run_id}/`:
  - `config.json`
  - `data_snapshot.json`
  - `walk_forward_summary.json`
  - `walk_forward_folds.csv`
  - `walk_forward_folds.json`
  - `provenance.json`
  - `report.md`
  - `manifest.json`
- Added Backtest UI command/button behavior and a `Walk-Forward` results tab.
- Updated the AI Agent contract with `backtest_walk_forward_run`.

## Clean-Room Exclusions

- No installed source was read or adapted.
- No Fincept branding, logo, commercial copy, subscription, credits, billing, or cloud
  account behavior was copied.
- No credential, PIN, provider key, account identifier, payment, or personal data was
  saved, logged, committed, screenshotted, or output.
- Optimize remains gated; the workflow is fixed-parameter validation only.
- Train windows are recorded for split provenance only; they are not used for
  fitting, parameter selection, or indicator warm-up in this slice.
- Live trading, broker/exchange keys, real balances, margin, leverage, short exposure,
  derivatives, and live controls remain unreachable.

## Verification Plan

- Focused Backtest and agent contract tests: 17 passed.
- Full pytest with repo-local TEMP/TMP: 227 passed.
- Ruff: passed.
- Frontend lint/build: passed.
- Playwright E2E: 15 passed.
- Source-wall/live-safety tests: 12 passed.
- Browser check: Backtest `Walk-Forward` completed, fold table and artifact path visible.
- Screenshot evidence: `artifacts/screenshots/m21-backtest-walk-forward.png`.
- Visual verdict: pass, score 91, recorded in
  `.omx/state/m21-backtest-walk-forward/ralph-progress.json`.
- Exact sensitive-literal scan for known account credential/PIN literals: no matches.
- `git diff --check`: passed with Git CRLF working-copy warnings only.
- Code-review gate: COMMENT with no CRITICAL/HIGH/MEDIUM/LOW findings; architecture
  WATCH items were addressed by adding explicit train-usage semantics and aligning the
  AI Agent response contract with the returned manifest.
