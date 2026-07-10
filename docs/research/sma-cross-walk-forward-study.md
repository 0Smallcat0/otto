# Walk-Forward Study: SMA Cross on BTCUSDT 15m (Methodology Walkthrough)

**Purpose.** Demonstrate Otto's research pipeline end-to-end — run, walk-forward,
grid search, and the honesty rails around them. The dataset is the terminal's
**deterministic offline fixture (40 closed 15m candles)**, so every number below
reproduces exactly on any machine with no API keys. This is a methodology
walkthrough, **not** a tradable signal; with a 40-candle sample the engine's own
overfitting flags fire, which is precisely the behavior worth showing.

Reproduce (fresh sandbox, offline):

```bash
LOCAL_TERMINAL_STATE_ROOT=evals/.sandbox/research LOCAL_TERMINAL_PORT=8888 \
  python -m src.local_terminal
# then POST /api/backtest/run, /api/backtest/walk-forward, /api/backtest/optimize
# with the configs shown in each section.
```

## 1. Baseline runs

Engine guarantees for every run: closed candles only, signals computed on close
and filled at the **next open** (lookahead guard), Decimal money math, explicit
economics (fee 10 bps, slippage 2 bps), self-describing artifact directory.

| Run | Params | Return | MaxDD | Trades | Run id |
|---|---|---|---|---|---|
| A | fast 3 / slow 5 | +1.58% | 0.29% | 3 | `bt-20260710100323-d2b9917b` |
| B | fast 5 / slow 12 | +1.77% | 0.12% | 1 | `bt-20260710100323-cf54a805` |

The engine annualizes Sharpe/Sortino from 15m periods and then **refuses to let
those numbers stand alone**. Run A reports:

> only 1 completed round trips — far too few for any statistic to mean much;
> annualized Sharpe 112.34 is implausibly high — a classic overfitting tell

That flag is emitted by `_risk_metrics` in `src/local_terminal/backtest.py`,
because a Sharpe computed from a handful of periods is noise, and a retail
backtest that prints it as an achievement is lying to its author.

## 2. Fixed-parameter walk-forward (`wfa-20260710100323-47b5642a`)

Config: fast 3 / slow 5, `fold_count 3`. Mode is
`fixed_parameter_walk_forward` with `train_usage:
metadata_only_no_fit_no_warmup` — folds are contiguous out-of-sample slices
(10 train / 10 test candles each), so this tests **window dependence**, not
parameter re-fitting.

| Fold | Test window return | Positive? |
|---|---|---|
| fold-1 | +0.07% | ✅ |
| fold-2 | +0.27% | ✅ |
| fold-3 | +0.20% | ✅ |

- Full-window headline: **+1.58%**
- Average fold return: **+0.18%** → in-sample/OOS gap **1.40pp**
- Verdict (engine-issued): **`mixed`** — *"3 of 3 folds profitable with a
  1.40pp gap to the full window — treat the headline with care."*

The point: all folds green is **not** a pass. The engine compares the headline
against the OOS average and downgrades the verdict when the gap is large
relative to the claim.

## 3. Bounded grid search (`local_grid_search`, objective `return_pct`)

Grid: fast ∈ {2,3,4,5} × slow ∈ {5,8,12,20} → 15 valid combinations evaluated
(fast < slow enforced; combination count capped by the API).

| Rank | fast | slow | Return | MaxDD | Trades |
|---|---|---|---|---|---|
| 1 | 2 | 12 | +1.77% | 0.12% | 1 |
| 2 | 3 | 12 | +1.77% | 0.12% | 1 |
| 3 | 4 | 12 | +1.77% | 0.12% | 1 |
| 4 | 5 | 12 | +1.77% | 0.12% | 1 |

Every `slow 12` cell ties at +1.77% with a single trade: on 40 candles the
"optimum" is one entry timed the same way regardless of the fast window. A
plateau of identical scores is the classic signature of an **undersized sample,
not a robust parameter region** — and the full-window reference result stays
the headline precisely so a cherry-picked grid cell cannot replace it.

## 4. What this pipeline enforces (the actual takeaway)

1. **No lookahead by construction** — `signals_on_close_fills_next_open` is a
   contract field on every artifact, not a code comment.
2. **Economics are explicit** — fees and slippage are inputs recorded in the
   run config, so "before costs" results cannot masquerade as tradable.
3. **Statistics carry their own health warnings** — implausible Sharpe and
   thin trade counts are flagged in words in the artifact and the UI.
4. **Out-of-sample discipline is one action away** — walk-forward is a
   first-class API with an engine-issued consistency verdict.
5. **Everything is an artifact** — config, data snapshot hash, trades,
   signals, returns analysis, provenance, and a human-readable report per run,
   so any claim traces back to files.

*Generated 2026-07-10 from real runs against the deterministic provider
(`deterministic_local_closed_candle`, initial cash 100,000.00, fee_rate 0.001,
slippage 2 bps).*
