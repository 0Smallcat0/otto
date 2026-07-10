# Agent-Operability Evals

Otto claims to be *AI-operated*: an agent, not a human, drives the terminal. This
directory turns that claim into a measurable, reproducible benchmark.

## What is measured

An LLM agent receives a plain-language task (for example *"run a walk-forward
validation for BTCUSDT and summarize the consistency verdict"*) and only the
`otto` MCP tool surface — the same `list_routes` / `list_actions` / `run_action`
contract any operator uses. The harness then grades the outcome
**programmatically**:

| Check kind | Grades |
|---|---|
| `state_contains` / `state_not_contains` | terminal HTTP state after the run |
| `artifact_glob` | files the action contract promises (summaries, reports) |
| `state_unchanged` | safety: a gated request must leave state untouched |
| `answer_contains` / `answer_not_contains` | required facts in the final answer |

There is **no LLM judge** — every verdict is a substring, file, or diff check.

## Why the results are trustworthy

- **Isolated sandboxes.** Each task boots a fresh terminal with its own
  `LOCAL_TERMINAL_STATE_ROOT` and port. Tasks are order-independent and never
  touch real user state.
- **Red-baseline smoke mode.** `--smoke` proves every graded check *fails* on
  fresh state before any agent runs, so no task can pass vacuously.
- **Config isolation.** The agent runs `claude -p` headless with
  `--strict-mcp-config` and no user-level settings, so hooks or personal
  config cannot contaminate results.
- **Offline-reproducible.** Tasks rely on the deterministic local data
  provider; no market-data API keys are needed.

## Task categories

| Category | Meaning |
|---|---|
| `read` | inspect the terminal and report grounded facts |
| `mutate` | change local state correctly (including read-merge-write) |
| `artifact` | produce contract-promised artifact files |
| `multi_step` | chain several actions toward one goal |
| `safety` | gated requests must be refused; confirmations must be passed |

## Run it

```bash
# validate the suite without spending tokens
python evals/run_eval.py --smoke

# run the full suite against one or more models
python evals/run_eval.py --model claude-haiku-4-5-20251001 --model claude-sonnet-5 --report
```

Results land in `evals/results/<timestamp>/` (JSONL + summary); `--report`
regenerates [EVAL.md](EVAL.md).

## Files

- `run_eval.py` — stdlib-only harness (sandbox lifecycle, agent invocation, grading, report)
- `tasks/core_tasks.json` — the `otto-core-v1` suite (20 tasks)
- `EVAL.md` — latest committed results snapshot
- `tests/test_m28_agent_eval.py` (repo tests) — suite/schema/grader contract tests
