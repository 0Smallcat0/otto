# Changelog

## Unreleased

- `POST /api/crypto/orders/process` (`crypto_process_paper_orders`, 125
  actions): resting LIMIT/STOP/STOP_LIMIT orders can now actually fill —
  until this existed a WORKING order rested forever, which made "the book
  supports LIMIT orders" quietly false. Each processing run checks every
  WORKING order against the current quote: fills happen at the current
  market price when the trigger condition holds (never at the limit price
  itself, price paths between runs are not simulated — stated in the
  response), the 900s freshness gate applies per symbol (a stale quote
  skips its orders instead of filling them), and an order that cannot fill
  safely (insufficient cash, shrunken position) stays WORKING with the
  reason reported. Stop-losses on the paper book are now real.
- TW odd-lot trading: any whole-share quantity now fills — multiples of the
  1000-share board lot are labeled `board_lot`, everything else `odd_lot`
  with the caveat stamped on the fill that odd-lot session pricing is not
  modeled (regular-session live quote, same fee rules, NT$20 minimum bites
  hard on small notionals — stated, not hidden). Fractional shares are
  refused, never rounded. A NT$3M paper account is no longer locked to
  three board-lot positions.
- Eval task #21 `decision_loop_full` (otto-core-v1 is now 21 tasks): one
  complete paper investing cycle — refresh, read the account summary and
  news packet, place a MARKET order whose `rationale` must be grounded in
  what was read, record a net-value snapshot, read the history back. Graded
  programmatically like every other task: the rationale tag must persist on
  the ledger, a real position must exist, and the snapshot note must appear
  in the history; red-baseline verified (all checks start red on a fresh
  sandbox) and the full chain replay-verified against a sandbox instance.
- `POST /api/dashboard/reset` now requires `"confirm": true` (the last M26
  Phase 2 residual): it overwrites the whole dashboard layout, so like every
  other overwrite of user state it must be asked for twice. The refusal
  message points at the undo path (backup slot 1 + `local_state_restore`).
- Backtest optimization artifacts now record data `provenance` like run
  artifacts always did — `write_optimize_artifacts` accepted the field and
  silently dropped it, so an optimize.json could not say where its candles
  came from.
- Performance measurement layer (124 actions): the loop can run — this
  measures whether running it is any good. `POST /api/paper/snapshot`
  (`paper_snapshot_record`) records all three books' net value in one row
  together with benchmark prices (BTC-USD / SPY / 0050.TW) fetched current
  by default; every row stores how stale its marks were, and unavailable
  benchmarks are recorded, never dropped. `GET /api/paper/history`
  (`paper_history`) returns the series plus a window performance block:
  per-book equity change vs per-benchmark buy-and-hold change over the same
  window, per-currency, never converted or ranked — a null change is labeled
  missing data, not zero. History lives in backup-protected
  `paper_history.json` (20 protected files) capped at 2000 rows.
- Decision journal: every paper order (crypto / US / TW) accepts an optional
  `rationale` (≤500 chars) stored on the order record, and all three book
  summaries return `recent_orders` with it — the agent's "why" is captured
  at decision time so a later review can compare stated reasoning against
  what actually happened, instead of reconstructing intent from fills.
- Equity summaries accept `?refresh=true`, fetching current prices for held
  symbols only. Without it a book read after a restart marked positions at
  their own cost basis and reported no unrealized P&L — quiet, but the same
  class of error as a stale fill. The default read stays a cheap local read.
- Ticker rows now name the provider that actually served them (dogfood P3):
  the fetcher chain stamps provenance and the markets status/rows carry it,
  so Kraken-supplied quotes stop being labeled `binance_public` with
  `fallback_used: false`. Fetchers that return bare rows keep the previous
  Binance defaults.
- `POST /api/news/packet` (`news_information_packet`, dogfood P2): the
  judgment step in one ~4KB read — bounded headlines with age, the operator
  digest when written, feed freshness including failed sources, and items
  tagged with the held symbols they mention (matched first, then freshest).
  The tagging declares itself keyword-based, so an unmatched item is never
  reported as irrelevant. Live probe: 6 of 63 items returned, 16 matched
  across BTC/ETH/AAPL/2330.TW including Chinese-language coverage.
- TW-equity paper ledger (`tw_equity_submit_paper_order` /
  `tw_equity_paper_summary`, 121 actions): the honest answer to "why was
  2330.TW refused" — not silent FX into the USD book, but a real TWD book
  with real market rules: 1000-share board lots (odd lots refused, never
  rounded), 0.1425% brokerage per side with the NT$20 minimum, 0.3%
  transaction tax on sells, and a ±10% daily-limit sanity guard against
  the previous close. Fills at a live Yahoo quote like the US book; third
  independent ledger (TWD / USD / USDT), backup-protected and restorable.
- US-equity paper ledger (`equity_submit_paper_order` /
  `equity_paper_summary`, 119 actions): cross-asset allocation closes the
  loop on stocks. The fill price is fetched live at submit (Yahoo public
  quote) so there is no stale-fill window at all; failed, non-USD, or stale
  quotes refuse the order. v1 scope stated, not implied: MARKET-only,
  USD-only (no silent FX), zero-commission assumption on every fill record.
  Separate USD book from the crypto USDT book; state file backup-protected
  and restorable like every other ledger.
- `POST /api/crypto/refresh` accepts `"view":"summary"`: refresh and read
  the decision-loop state in one ~1.4KB call instead of the 180KB full
  refresh response.
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
