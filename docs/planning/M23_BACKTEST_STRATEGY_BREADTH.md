# M23.15 Backtest Strategy Breadth

Date: 2026-05-26

## Purpose

Close one narrow Backtest/Algo strategy-depth gap without reopening completed
provider, command-center, or artifact-lifecycle work. This milestone adds a
third local closed-candle Backtest strategy family and lets Algo save and run it
through the existing strategy handoff.

## Runtime Surface

- Backtest catalog now includes `sma_mean_reversion` alongside `sma_cross` and
  `channel_breakout`.
- The new strategy remains long/flat, closed-candle-only, and next-open-fill.
- The same schema contract is reused: `fast_window` is labeled `Exit SMA`,
  `slow_window` is labeled `Mean SMA`, and `slow_window > fast_window` remains
  required.
- Backtest artifacts record `local_sma_mean_reversion_v1`, strategy label,
  schema, constraints, provenance, returns, indicators, and signals.
- Algo can save a strategy with `backtest.strategy=sma_mean_reversion` and run
  it through `/api/algo/run-backtest`.

## Safety

This milestone adds no optimize workflow, live deployment, broker routing, real
orders, real balances, private provider keys, margin, leverage, short exposure,
derivatives, cloud sync, subscription, billing, CR/credits, Fincept branding,
installed-source reads, or destructive artifact actions.

## Verification

- Focused Backtest tests cover catalog exposure, artifact writes,
  `local_sma_mean_reversion_v1`, mean-reversion indicators, closed-candle
  rejection, and no same-candle fills.
- Focused Algo tests cover saved-strategy handoff into the new Backtest engine.
- Command Center reports `M23.15 Backtest strategy breadth` and points to this
  milestone document as current provenance.
- Focused gate
  `.\.venv\Scripts\python.exe -m pytest tests\test_m6_backtest.py tests\test_m10_algo.py tests\test_m22_command_center_contract.py -q --basetemp .omx\pytest-tmp\m23-15-focused`
  -> 41 passed.
- Doc/contract gate
  `.\.venv\Scripts\python.exe -m pytest tests\test_m6_backtest.py tests\test_m10_algo.py tests\test_m21_agent_operability_contract.py tests\test_m22_command_center_contract.py tests\test_m22_mission_ledger.py -q --basetemp .omx\pytest-tmp\m23-15-doc-contract`
  -> 50 passed.
- Full backend pytest -> 299 passed; full ruff -> passed.
- Frontend `npm run lint`, `npm run build`, and `npm run e2e` -> passed; build
  kept the existing Vite chunk-size warning and E2E result was 15 passed.
- Safety/source-wall/local-secret gate -> 23 passed.
- FastAPI TestClient smoke confirmed Command Center current milestone,
  Backtest `local_sma_mean_reversion_v1`, Algo handoff
  `sma_mean_reversion`, and no local secret store creation.
- `git diff --check` passed with Git CRLF warnings only; changed-diff secret
  scan found no personal email, password, PIN, provider key, private key,
  bearer token, or protected-value marker literals.
