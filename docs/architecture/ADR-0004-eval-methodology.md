# ADR-0004: Programmatic Agent-Operability Evaluation

Status: Accepted
Date: 2026-07-10

## Context

"An AI can operate this app" is a claim, not a property. M28 needed a way to
measure operability that is cheap to rerun, honest, and immune to the common
failure modes of agent benchmarks: LLM judges grading LLM output, tasks that
pass vacuously, and state bleeding between runs.

## Decision

`evals/` implements a benchmark with these methodological rules:

1. **Programmatic grading only.** Success is defined by HTTP state substrings,
   contract-promised artifact files, state-diff checks, and required facts in
   the final answer. No LLM judge anywhere.
2. **Red-baseline guarantee.** A smoke mode boots every task's sandbox and
   asserts each graded check FAILS before any agent runs. A task that is
   already green on fresh state is rejected as vacuous.
3. **Hermetic sandboxes.** Each task gets a fresh `LOCAL_TERMINAL_STATE_ROOT`
   and dedicated port; the agent runs headless with strict MCP config and no
   user-level settings, so personal hooks cannot contaminate results.
4. **Offline reproducibility.** Tasks use the deterministic local data
   provider; no API keys are required to reproduce published numbers.
5. **Honest reporting.** `EVAL.md` records model IDs, dates, task counts,
   single-run caveats, and per-task failures. No extrapolation.

## Consequences

- Operability regressions become visible: a contract change that strands
  agents fails tasks, not just vibes.
- Programmatic checks cap task expressiveness (no "was the summary insightful"
  tasks); accepted — subjective quality is out of scope for this benchmark.
- Single-run-per-task keeps cost low but adds variance; the report says so.
