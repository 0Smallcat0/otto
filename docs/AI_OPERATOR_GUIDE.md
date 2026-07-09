# AI Operator Guide — Fincept Local Terminal

This terminal is designed to be **driven by an AI** (Claude Code, Codex, or any MCP
client). You — the human — give instructions in natural language; the AI operates the
terminal through a small, safe tool surface. This guide explains how.

## 1. Start the terminal (one command)

```powershell
.\.venv\Scripts\python.exe -m src.local_terminal
```

This serves the UI + API at `http://127.0.0.1:8765/`. Open that URL to watch what the
AI is doing. (If the frontend has not been built yet:
`npm --prefix frontend install && npm --prefix frontend run build`.)

Developer mode (hot-reload UI on `:5173` with a proxy to the API) is still available
via `npm --prefix frontend run dev` alongside the backend — not needed for daily use.

## 2. Connect an AI operator (MCP)

The MCP server is stdlib-only and speaks stdio JSON-RPC. It **auto-starts the local
terminal** if it is not already running (disable with `LOCAL_TERMINAL_MCP_AUTOSTART=0`).
Starting the terminal yourself (step 1) is optional but lets you watch the UI while the
AI works.

### Claude Code

`.mcp.json` in the repo root already registers the server:

```json
{
  "mcpServers": {
    "local-terminal": {
      "command": ".venv/Scripts/python.exe",
      "args": ["-m", "src.local_terminal.mcp_server"],
      "env": { "LOCAL_TERMINAL_URL": "http://127.0.0.1:8765" }
    }
  }
}
```

Open Claude Code in this directory and approve the `local-terminal` MCP server. If the
relative `command` path is not found, use the absolute venv python path
(`D:\FinceptLocalTerminal\.venv\Scripts\python.exe`).

### Codex

Add to `~/.codex/config.toml`:

```toml
[mcp_servers.local-terminal]
command = "D:/FinceptLocalTerminal/.venv/Scripts/python.exe"
args = ["-m", "src.local_terminal.mcp_server"]
env = { LOCAL_TERMINAL_URL = "http://127.0.0.1:8765" }
```

## 3. The operator tools

| Tool | Use |
| --- | --- |
| `terminal_status` | Situational awareness: health, current milestone, active task, risk gates, recovery count. **Call this first.** |
| `list_routes` | The 15 routes with `route_id` + primary endpoint. |
| `get_route` | Read one route's current state (e.g. `route_id: "markets"`). |
| `list_actions` | The safe operable actions (optionally filtered by `route_id`). |
| `run_action` | Execute one safe action by `action_id` (`body`/`path_params`/`query`/`confirm` as needed). |
| `refresh_public_data` | Convenience: run the public no-key provider refresh job. |

## 4. Typical operating loop

1. `terminal_status` — where are we, what is gated.
2. `refresh_public_data` — pull fresh public (no-key) market/macro data.
3. `get_route` (`markets`, `dashboard`, `portfolio`, …) — inspect state.
4. `list_actions` (`route_id: "backtest"`) — discover what you can do on a route.
5. `run_action` (e.g. `backtest_run_local`, then `backtest_run_index`,
   `backtest_comparison_packet`) — act and read the artifacts it wrote.
6. `terminal_status` again — confirm the active task / recovery queue.

Example instructions you can give your AI:

- "Refresh public data, then show me the markets quote/reference coverage."
- "Run the RSI reversion backtest and compare it against the last two runs."
- "Summarize the Command Center: milestone, risk gates, and anything in the recovery queue."

## 5. What stays gated (by design)

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
  (Cboe, IEX, Nasdaq Data Link, JPX/J-Quants, Yahoo Finance).

To change any of these, a new reviewed safety contract is required — it is not a bug.

## 6. Fallback: drive the API directly (no MCP)

Everything the MCP server does is a thin wrapper over the HTTP API. An AI (or a
script) can also call it directly:

- `GET /api/agent-contract` — the full machine-readable catalogue of routes, actions,
  selectors, error codes, and safety classes (the single source of truth).
- `GET /api/command-center` — aggregated supervision payload.
- `GET /api/agent-actions/{action_id}/preflight` — check an action before running it.

Start from `/api/agent-contract`; never scrape the UI for structure.
