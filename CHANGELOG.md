# Changelog

## Unreleased

- `GET /api/crypto/summary` (`paper_account_summary`, dogfood P1): the
  decision-loop view in ~1.5KB instead of the 74k-char full paper payload —
  account with total P&L, positions marked to the freshest known price with
  unrealized P&L, open orders, and per-symbol quote age against the 900s
  fill gate with the refresh action to run when stale.
- Paper-fill honesty (dogfood P0s): a MARKET paper order on a quote older
  than 15 minutes is refused with a "refresh first" error instead of
  filling at a phantom price, and a carried-forward quote past the TTL is
  demoted to `stale_cache` — never relabeled `live`. The crypto ticker
  snapshot now rides the same Binance→Kraken fallback chain as
  depth/trades/candles, so a blocked primary no longer strands the ticker
  (and, with the gate, all paper trading) on week-old data.
- `POST /api/markets/quotes/lookup` (`markets_quote_lookup`, 116 actions):
  ask for live quotes on ANY Yahoo Finance symbol — US/TW stocks, indices,
  FX, crypto — not just the stored watchlists. Explicit symbols only: an
  all-invalid request is refused instead of silently answered with the
  default watchlist. Flat response (status/quotes/summary) an agent can
  read without spelunking the markets payload.
- Package renamed `src.local_terminal` → `otto.local_terminal`: the project
  now installs a proper top-level `otto` package instead of squatting the
  generic `src` name, clearing the path to a PyPI release. Checkout
  invocations change to `python -m otto.local_terminal`; the `otto` /
  `otto-mcp` entry points and the uvx one-liner are unaffected.
- Health and MCP `serverInfo` now report the real project version
  (single-sourced from dist metadata, pyproject fallback) instead of a
  hard-coded `0.1.0`.
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
