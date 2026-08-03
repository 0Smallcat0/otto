# Otto

[![CI](https://github.com/0Smallcat0/otto/actions/workflows/ci.yml/badge.svg)](https://github.com/0Smallcat0/otto/actions/workflows/ci.yml)

A local financial terminal your AI agent operates for you. Market data, backtests, paper
books, news — driven in plain language, running entirely on your machine.

![A real agent operating Otto: a plain-language command goes in, the agent runs a backtest through MCP, and the run lands on the dashboard](docs/screenshots/otto-demo.gif)

## Try it

Needs [uv](https://docs.astral.sh/uv/) and Python 3.12. No clone, no build, no server to start:

```bash
claude mcp add otto -- uvx --from git+https://github.com/0Smallcat0/otto otto-mcp
```

Then ask for things:

- *"Refresh market data and show me the BTC snapshot."*
- *"Backtest an SMA cross on BTCUSDT and tell me if it's any good."*
- *"What do you make of my holdings?"*

Want the dashboard as well: `npm --prefix frontend install && npm --prefix frontend run build`,
then `uv run otto` → <http://127.0.0.1:8765/>

## Why this one

**It keeps score.** The agent records dated calls — a stance, the reasoning, the price level
that would prove it wrong, a horizon — and every call is later graded against the price the
market actually printed. Calls without reasoning are refused rather than guessed, moves
inside a flat band don't count as skill, and a call graded long after it matured is excluded
because it measured a window its thesis never claimed. The hit rate is whatever the market
says it is.

**"An AI can operate it" is a benchmark here, not a tagline.** A real headless agent gets 20
plain-language tasks in hermetic sandboxes, graded programmatically on terminal state and
artifacts — never by an LLM judge:

| Model | Passed | Avg turns |
|---|---|---|
| `claude-sonnet-5` | 20 / 20 | 6.5 |
| `claude-haiku-4-5` | 19 / 20 | 6.8 |

Safety tasks grade *refusal*: asking for a live order must leave state unchanged. Live
trading, credential entry and code execution aren't switched off — they're unreachable
through the surface the agent has.

## Under the hood

One typed contract (137 actions across 16 routes) is the single source of truth; the MCP
tools, the UI capability catalog and the eval suite are all derived from it. 680 tests on
Windows + Linux CI.

- [Architecture](docs/architecture/ARCHITECTURE.md) · [ADRs](docs/architecture/)
- [AI operator guide](docs/AI_OPERATOR_GUIDE.md)
- [Eval methodology and full results](evals/EVAL.md)
- [Clean-room boundary](AGENTS.md) — built by observing a reference terminal's workflow,
  never by reading or porting its code; a [test](tests/test_clean_room_source_wall.py) fails
  the build if that wall is crossed.

```bash
python -m pytest -q && python -m ruff check .
```

## License

[MIT](LICENSE).
