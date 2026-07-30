# M28 — Agent Eval Harness + v1.0 Release Packaging

Date started: 2026-07-10. Owner directive: package Otto as a complete, presentable
project (grad-school / internship portfolio) without breaking the clean-room boundary.

## Goal

Turn the "AI-operated terminal" claim into a measurable, reproducible result, and
ship the repo as a coherent v1.0 with real documentation, demo media, and an honest
evaluation report.

## Phases

### Phase 1 — Agent evaluation harness (`evals/`)

The core upgrade: a benchmark that measures how well an LLM agent operates Otto
through the MCP tool surface.

- Task suite: natural-language tasks in `evals/tasks/*.json`, each with
  programmatic success checks (HTTP state assertions / artifact existence /
  answer substring). No LLM judge — objective checks only.
- Runner: `evals/run_eval.py` (stdlib only).
  - Per task: fresh sandbox state root (`LOCAL_TERMINAL_STATE_ROOT` under
    `evals/.sandbox/`), dedicated server port, `claude -p` headless with an
    explicit `--mcp-config` pointing at the sandboxed server
    (`LOCAL_TERMINAL_URL`, autostart off), `--setting-sources ""` and
    `--strict-mcp-config` so user-level config cannot leak in.
  - Records: pass/fail per check, num_turns, token usage, duration, cost.
- Report: `evals/EVAL.md` regenerated from results; committed snapshot with
  model IDs, dates, task counts, and a limitations section.
- Safety tasks: gated actions (live trading etc.) must be refused — refusal is
  the pass condition.
- Server change required: `LOCAL_TERMINAL_PORT` / `LOCAL_TERMINAL_HOST` env
  overrides (with tests) so eval instances don't collide with a running
  terminal on 8765.
- Harness gets its own pytest coverage (task schema validation, check
  evaluator, report rendering) without spawning claude.

### Phase 2 — Demo media + public README front door

- Playwright screenshot wall + one hero GIF (command → AI drives terminal),
  assembled with ffmpeg.
- Public mirror README: hero media at top, eval results table, architecture
  diagram, quickstart.

### Phase 3 — Quant metrics completion

- Add Sharpe / Sortino / turnover to backtest returns analysis (Decimal math,
  tests). Walk-forward, fee/slippage, lookahead guard already exist.
- One polished example research report (walk-forward SMA study) under
  `docs/research/`, generated from a real deterministic run.

### Phase 4 — Architecture docs + release packaging

- `docs/architecture/ARCHITECTURE.md` + mermaid system diagram.
- ADR-0002 agent contract as single source of truth; ADR-0003 safety gates;
  ADR-0004 eval methodology.
- CI: add ubuntu job (skip DPAPI-bound governance tests via marker), keep
  windows job authoritative.
- `CHANGELOG.md`, bump version to 1.0.0.

### Phase 5 — Public mirror sync

- Re-export to 0Smallcat0/otto per the established curated-export procedure
  (exclude `docs/reference/`, artifacts, sandboxes). Tag v1.0.0.

## Honesty rules

- EVAL.md reports what actually ran (models, dates, N). No extrapolated claims.
- Anything not finished stays listed as not finished in this file.

## Status log

- 2026-07-10: plan created; Phase 1 started.
- 2026-07-10: Phase 1 done — harness + otto-core-v1 (20 tasks), smoke 20/20 red
  baselines, pilot results claude-sonnet-5 20/20, claude-haiku-4-5 19/20
  (route-inventory task blew its 8-turn budget), avg 6.5–6.8 turns; EVAL.md
  committed.
- 2026-07-10: Phase 3 re-scoped — Sharpe/Sortino/profit-factor/overfit flags
  already existed in `_risk_metrics` (no code change needed); shipped the
  walk-forward methodology study instead (docs/research/).
- 2026-07-10: Phase 4 done — ARCHITECTURE.md, ADR-0002..0004, CHANGELOG,
  version 1.0.0, CI Linux lane (3 governance truths skip via dpapi_available
  marker; enumerated by simulating no-DPAPI across the suite).
- 2026-07-10: Phase 2 done — EN/dark screenshot wall + real-agent demo GIF
  (unscripted haiku run captured live; caption numbers verified against the
  run's summary.json).
- 2026-07-10: Phase 5 — public mirror overlay (M28 paths + stale markets.py
  catch-up), README front door (GIF, measured-operability table, architecture
  links), 475 tests green on the export, committed 99298d2 + tag v1.0.0.
  Not done: nothing outstanding for M28.
