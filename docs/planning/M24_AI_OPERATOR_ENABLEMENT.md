# M24 — AI Operator Enablement + Self-Use Polish

Date opened: 2026-07-05

## Goal

The owner operates this terminal by instructing an AI (Claude Code / Codex), not by
clicking the UI. After the M23.68 non-live completion audit, the remaining self-use
work is to (1) make the terminal trivially runnable and (2) make it genuinely
*AI-operable* through a native tool surface — while every existing safety gate stays
closed. Commercial/subscription/billing parity is intentionally excluded.

Authority unchanged: `AGENTS.md`, approved PRD/test-spec/execution-plan, and the
non-live safety boundaries. No live trading, broker binding, real balances, margin,
leverage, shorts, derivatives, payments, subscription, cloud sync, branding/asset or
installed-source copying, secrets, or destructive lifecycle actions are added by M24.

## Slices

### M24.1 — One-command launch + serve built frontend (done)

- `create_app(frontend_dist=None)` mounts the built `frontend/dist` as static UI at
  `/` when it exists; `/api/*` routes keep precedence over the catch-all mount.
- When the UI is not built, `/` still redirects to `/api/health` (API-only mode).
- `python -m src.local_terminal` (`src/local_terminal/__main__.py`) starts one
  process serving UI + API at `http://127.0.0.1:8765/`, with a clear startup line.
- Dev mode (`npm --prefix frontend run dev` + backend, Vite proxy) is unchanged.
- Tests: `tests/test_m24_frontend_serving.py` (UI served + API coexistence;
  redirect fallback when dist absent).

### M24.2 — Zero-dependency MCP server (done)

- `src/local_terminal/mcp_server.py`: a stdio JSON-RPC 2.0 MCP server, standard
  library only (no new dependency), aligned with the terminal's minimal/offline
  design. Launch: `python -m src.local_terminal.mcp_server`.
- Six operator tools: `terminal_status`, `list_routes`, `get_route`, `list_actions`,
  `run_action`, `refresh_public_data`. The action catalogue is derived from the
  terminal's own `/api/agent-contract` (single source of truth).
- Safety: `run_action` and `list_actions` refuse any action that is
  `disabled_by_safety` or secret-related (`is_mcp_safe`). This is defence in depth —
  the backend enforces the same gates. Live/secret/disabled runtimes are unreachable
  through MCP.
- Transport is injectable: stdlib `urllib` HTTP at runtime; in-process `TestClient`
  for tests. `.mcp.json` registers the server for Claude Code.
- Tests: `tests/test_m24_mcp_server.py` (handshake, tool list, safe/unsafe action
  gating, unavailable-terminal handling, unknown-method error).

### M24.2b — MCP auto-start (done)

- `ensure_backend()` in the MCP server auto-starts a **local** terminal
  (`python -m src.local_terminal`, detached) when the API is unreachable, then waits
  for `/api/health`. Zero manual steps: the AI client launches the MCP server, which
  brings the terminal up. Disable with `LOCAL_TERMINAL_MCP_AUTOSTART=0`; only loopback
  hosts are ever auto-started.
- Verified: with `:8765` stopped, launching the MCP server alone booted the backend and
  answered `terminal_status` (route_count 15, milestone M23.68). Tests inject fake
  reachable/spawn/sleep so no real process starts in the suite.

### M24.3 — AI operator guide / runbook (done)

- `docs/AI_OPERATOR_GUIDE.md`: how an AI drives the terminal end-to-end (start it,
  connect MCP for Claude Code and Codex, core workflows, and the gates that stay
  closed).

### M24.4 — Backtest parameter Optimize (done, backend + UI)

- The observed terminal exposes an "Optimize" command that the local version had
  deferred (for pacing, not safety). `run_optimize()` in `backtest.py` adds a local,
  deterministic grid search over a strategy's own parameter schema: it normalizes the
  config + loads one shared closed-candle snapshot, runs the strategy for each bounded
  combination, ranks by return, and writes `optimize.json/rows.csv/report.md/manifest.json`
  under `artifacts/backtests/optimizations/btopt-*`.
- Bounds: `OPTIMIZE_MAX_VALUES_PER_PARAM` per parameter and `OPTIMIZE_MAX_COMBINATIONS`
  total; each combination is validated against the strategy schema (e.g. slow > fast),
  invalid combos skipped. A caller `parameter_grid` overrides the default grid.
- `POST /api/backtest/optimize` (`BacktestOptimizeUpdate`) + agent-contract action
  `backtest_optimize` (`closed_candle_local_research`, not disabled) — so it is
  **operable by an AI today via the MCP `run_action` tool**. No optimize-then-deploy,
  broker routing, shorts, derivatives, or live path.
- Tests: `tests/test_m24_backtest_optimize.py` (ranking, bounds/constraint, combination
  cap, endpoint, agent-contract exposure).
- UI: the Backtest workspace `Optimize` command is now enabled and an `Optimize`
  result tab (best-parameter metrics + a ranked table) is wired in
  `frontend/src/components/Backtest.tsx`. Verified in-browser: clicking Optimize runs
  the grid search and renders the ranked results. This closes the observed "Optimize"
  command parity gap.

### M24.5 — Clean .omx ephemeral clutter (deferred)

- ~368 gitignored `.omx/playwright-state-*` / browser / screenshot scratch dirs remain.
  The destructive-command hook blocks the `rm` sweep even with facts, and they have zero
  repo/test impact, so this is left as an owner-run one-liner:
  `find .omx -maxdepth 1 -type d -name 'playwright-state-*' -exec rm -rf {} +`.

### M24.next — Self-use workflow-depth parity vs reference (open)

- Continue closing self-use workflow depth route-by-route vs
  `docs/reference/.../FEATURE_MATRIX.md`, each slice small, tested, committed.
  Commercial/subscription/live excluded.

## Verification cadence

Every slice: focused pytest for the slice + `ruff check` on changed files; full
`pytest -q` before relying on the tree; MCP changes verified with an in-process
TestClient transport and a real stdio smoke against the running terminal.
