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
