# M23.44 Backtest Momentum Continuation

## Scope

M23.44 deepens the local Backtest/Algo strategy catalog with a fifth
closed-candle strategy: `momentum_continuation`. It is a deterministic local
research strategy that enters long when the close is above the prior momentum
lookback close and above an exit SMA, then exits when the close falls below the
exit SMA.

## Completed Behavior

- Backtest strategy catalog exposes `momentum_continuation` with
  `Momentum Continuation`, `Exit SMA`, and `Momentum Lookback` labels.
- Backtest runner dispatches the strategy through the existing long/flat,
  next-open fill engine.
- Strategy artifacts use `local_momentum_continuation_v1` and include
  `momentum_reference` plus `momentum_return_pct` indicators.
- Algo saved-strategy handoff accepts the new strategy through the shared
  Backtest strategy catalog and writes the same local Backtest artifacts.
- Frontend fallback schema and Playwright coverage verify that the Backtest UI
  can select, run, and inspect the new strategy.
- Command Center current milestone points to this handoff document.

## Boundaries

- No optimizer, parameter fitting, replay engine, deployment, broker routing,
  live order path, real balance read, margin, leverage, short exposure,
  derivatives execution, provider refresh, credential flow, or external runtime
  was added.
- The strategy remains long/flat and closed-candle only; signals are generated
  on candle close and fills occur on the next candle open.
- No Fincept branding, assets, commercial copy, runtime binaries, or installed
  source were read or copied.

## Verification

Verification evidence is recorded in `docs/planning/M22_MISSION_LEDGER.md` under
the M23.44 verification log and in `PROJECT_STATE.md`.
