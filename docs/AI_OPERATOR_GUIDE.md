# AI Operator Guide

This terminal is designed to be **driven by an AI** (Claude Code, Codex, or any MCP
client). You — the human — give instructions in natural language; the AI operates the
terminal through a small, safe tool surface. This guide explains how.

## 1. Install and connect

Install and register it as the [README](../README.md#try-it) shows:

```bash
uv tool install git+https://github.com/0Smallcat0/otto
claude mcp add otto -- otto-terminal
```

The MCP server is stdlib-only and speaks stdio JSON-RPC. It **starts the backend** if it
is not already running (disable with `LOCAL_TERMINAL_MCP_AUTOSTART=0`), and
`http://127.0.0.1:8765/` is the dashboard where you watch what the AI does. To use
another port, set both `LOCAL_TERMINAL_PORT` (the backend) and `LOCAL_TERMINAL_URL`
(the MCP server). State lives in `~/.otto` unless `LOCAL_TERMINAL_STATE_ROOT` says
otherwise.

### Codex

Add to `~/.codex/config.toml`:

```toml
[mcp_servers.otto]
command = "otto-terminal"
```

### From a clone

`uv run otto` serves the committed dashboard and API; the repo's `.mcp.json` registers
the MCP server against the `.venv` that `uv run` creates. `npm --prefix frontend run dev`
hot-reloads the UI on `:5173` for frontend work only.

## 2. The operator tools

| Tool | Use |
| --- | --- |
| `terminal_status` | Orientation: health, the risk gates, whether this install has positions or journaled calls yet, and what to do first. **Call this first.** |
| `list_routes` | The 16 routes with `route_id` + primary endpoint. |
| `get_route` | Read one route's current state (e.g. `route_id: "markets"`). |
| `list_actions` | The safe operable actions (optionally filtered by `route_id`). |
| `run_action` | Execute one safe action by `action_id` (`body`/`path_params`/`query`/`confirm` as needed). |
| `refresh_public_data` | Convenience: run the public no-key provider refresh job. |

## 3. Typical operating loop

1. `terminal_status` — what this install has and what is gated.
2. `refresh_public_data` — pull fresh public (no-key) market/macro data.
3. `get_route` (`markets`, `dashboard`, `portfolio`, …) — inspect state.
4. `list_actions` (`route_id: "backtest"`) — discover what you can do on a route.
5. `run_action` (e.g. `backtest_run_closed_candle`, then `backtest_run_index`,
   `backtest_comparison_packet`) — act and read the artifacts it wrote. Backtests run
   on BTCUSDT, ETHUSDT or SOLUSDT 15m closed candles.
6. Paper orders (`equity_submit_paper_order`, `tw_equity_submit_paper_order`,
   `crypto_submit_paper_order`) carry a one-line rationale and show on the dashboard's
   activity feed.

Example instructions you can give your AI:

- "Refresh public data, then show me the markets quote/reference coverage."
- "Run the RSI reversion backtest on ETHUSDT and compare it against the last two runs."
- "Use my paper book to buy $5,000 of AAPL, say why in one line, then show me the book."

## 4. What stays gated (by design)

The MCP surface **cannot** reach these — they are refused by `run_action` and enforced
again by the backend:

- Live/real trading, broker or exchange binding, real balances, margin, leverage,
  shorts, derivatives, order routing.
- Secret/credential entry (optional-key providers are configured by a human in the
  Settings UI, never via MCP).
- Disabled runtimes (Nodes execute, Code execute, Quant Lab execute, external
  QuantLib) until a dedicated safety contract exists.
- Destructive artifact lifecycle actions (archive/prune/delete/restore execution).
- Paid/subscription providers and the blocked provider gates
  (Cboe, IEX, Nasdaq Data Link, JPX/J-Quants).

To change any of these, a new reviewed safety contract is required — it is not a bug.

## 5. Fallback: drive the API directly (no MCP)

Everything the MCP server does is a thin wrapper over the HTTP API. An AI (or a
script) can also call it directly:

- `GET /api/agent-contract` — the full machine-readable catalogue of routes, actions,
  selectors, error codes, and safety classes (the single source of truth).
- `GET /api/command-center` — aggregated supervision payload.
- `GET /api/agent-actions/{action_id}/preflight` — check an action before running it.

Start from `/api/agent-contract`; never scrape the UI for structure.
