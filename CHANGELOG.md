# Changelog

## Unreleased

- Zero-clone install mode: running from a wheel (pip/uvx, no repo checkout)
  now keeps state under `~/.otto` instead of assuming a repository around the
  package, and the MCP autostart runs the backend from there. Quickstart is
  now one line:
  `claude mcp add otto -- uvx --from git+https://github.com/0Smallcat0/otto otto-mcp`.
- Console entry points `otto` (terminal server) and `otto-mcp` (stdio MCP
  server), so a fresh clone is one `uv sync` away from
  `claude mcp add otto -- uv --directory <repo> run otto-mcp`. README leads
  with a verified 90-second quickstart.
- `POST /api/local-state/restore` (M26 S2.1): confirm-gated restore of any
  protected state file from its rotating backup slots. The pre-restore
  version rotates into slot 1 first, so every restore is itself undoable;
  an unreadable backup aborts with zero writes. Registered in the agent
  contract as `local_state_restore` (115 actions) — the agent can now undo
  a bad state write without human filesystem surgery.

## 1.0.0 — 2026-07-10

First complete release: Otto is a local, AI-operated financial terminal with a
measured operator surface.

### Agent operability (M28)

- Agent-operability eval harness (`evals/`): 20-task benchmark
  (`otto-core-v1`) driving a real headless agent through the MCP surface in
  hermetic sandboxes, graded programmatically (state, artifacts, refusals) —
  no LLM judge. Red-baseline smoke mode rejects vacuous tasks.
- `LOCAL_TERMINAL_HOST` / `LOCAL_TERMINAL_PORT` env overrides for parallel
  sandboxed instances.
- Architecture documentation: `docs/architecture/ARCHITECTURE.md` + ADR-0002
  (agent contract), ADR-0003 (structural safety gates), ADR-0004 (eval
  methodology).

### Core (M1–M27 arc, highlights)

- 16 terminal routes (dashboard, markets, crypto, paper, portfolio, news,
  AI chat, backtest, algo, nodes, code, quant lab, quantlib, forum, settings,
  profile) behind one typed agent contract (113 safe actions).
- Zero-dependency stdio MCP server derived from the contract; safety-disabled
  and secret actions structurally unreachable.
- Paper-only trading ledger; no live execution paths by design.
- Conservative backtest engine: closed candles, next-open fills (lookahead
  guard), Decimal economics with fees + slippage, walk-forward validation,
  bounded grid-search optimization, self-describing artifact directories.
- Market data: public no-key providers (Binance, Yahoo, SEC, TWSE, Nasdaq
  Trader, ECB/Fed/BoC FX, World Bank, CFTC, BLS, GDELT news, ...) plus
  optional sealed-key providers (Finnhub, Twelve Data, FRED, Alpha Vantage,
  ...), all with deterministic offline fallbacks.
- Local-first state: settings/layouts/profiles under the repo with rotating
  backups; artifact lifecycle is metadata-only (no destructive cleanup).
- React/TypeScript dashboard UI with capability catalog generated from the
  contract; zh-TW/EN i18n.
- 450+ pytest tests, Playwright e2e, ruff, GitHub Actions CI.
