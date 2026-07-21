# Dogfood: can an agent run a full decision loop on Otto? (2026-07-17)

Owner's question, verbatim goal: *let the AI use Otto to imitate a human
decision cycle — watch the market, gather information, judge, and end with an
asset allocation (order)* — on the paper ledger, mechanical rules, no live
anything. This document records one real attempt by a Claude agent over the
MCP surface, unedited outcomes, and the honest verdict. It is an engineering
finding, not investment advice.

## The run (7 tool calls)

1. `terminal_status` — paper mode on, live structurally off. OK.
2. `get_route paper` — account: cash 99,935 / equity 99,999.91, position
   BTCUSDT 0.001 @ 64,226. Universe: BTC/ETH/SOL only. Ticker cache dated
   **2026-07-10** (7 days stale). Response was ~74k chars, truncated.
3. `crypto_refresh_public` — Binance blocked; provider chain fell back to
   **Kraken** and refreshed candles/depth/trades to live 07-17 data. But the
   **ticker snapshot stayed at 07-10** — the fallback path does not cover the
   ticker cache. Response ~267k chars.
4. `news_digest_index` — empty (expired digest auto-cleared). The information
   step comes up empty-handed unless the agent runs a full refresh + reads
   raw items + writes its own digest (3 more heavyweight calls).
5. Judgment (in-agent, transparent rule): with no trustworthy 24h momentum
   (ticker stale), no news signal, and only 3 crypto symbols available, the
   defensible allocation move is a minimal diversification probe sized to
   drill the execution path: BUY 0.01 ETHUSDT (~$18 notional, paper).
6. `crypto_submit_paper_order` BUY 0.01 ETHUSDT MARKET → **FILLED at
   1799.97** — the 07-10 cached price — with `quote_state: "live"` and
   `quote_retrieved_at: 2026-07-10T11:51:32Z` on the fill record.
7. Read-back confirmed: position ETHUSDT 0.01 @ 1799.97 on the ledger.

## Verdict

**The loop completes in form, but the judgment step is starved and the
execution step can lie about price.** Otto today is operationally complete
(safety gates, ledger, artifacts, discoverable actions all worked exactly as
documented) but informationally broken for decision-making:

- the agent could not obtain a trustworthy current price for the thing it
  was about to trade,
- could not obtain any news signal without heavy lifting,
- and the paper engine then filled the order at a 7-day-old price while
  labeling it `live`.

A human at a terminal would refuse to trade under these conditions; the
system happily let the agent do it. That gap — not missing features — is the
real product debt.

## Pain-point backlog (this is the roadmap now)

| # | Severity | Finding | Direction |
|---|---|---|---|
| 1 | **P0** | Paper MARKET fill used a 7-day-stale cached quote (1799.97) and stamped it `quote_state: live` (the state the cache had *when captured*, silently carried forward) | Freshness gate at submit: if `quote_retrieved_at` older than a TTL (e.g. 15 min), refuse the fill with a clear error telling the agent to refresh first; label carried state `stale_cache`, never `live` |
| 2 | **P0** | Provider fallback (Kraken) refreshed candles/depth/trades but not the ticker snapshot — mixed-freshness market view with no single "is my data current?" answer | Extend the fallback chain to the ticker cache; expose one per-symbol `data_age_seconds` the agent can trust |
| 3 | **P1** | Route/refresh payloads are 74k–267k chars — unusable for agent context; the useful facts fit in ~20 lines | Summary-mode responses for agent consumption (account + positions + per-symbol quote age); details on request |
| 4 | **P1** | Decision universe: only 3 crypto pairs are tradeable; equities (US/TW) are bookkeeping-only in portfolio — "asset allocation" cannot close the loop on stocks | Either extend paper fills to equity symbols using the same quote infrastructure, or state the crypto-only scope explicitly in the contract |
| 5 | **P2** | Information step is empty by default (digest auto-expired); assembling fresh news costs 3 heavyweight calls | A single "current information packet" read: freshest headlines + digest in one bounded response |
| 6 | **P2** | Account equity is marked-to-stale prices (same root as #1/#2) | Falls out of fixing #1/#2 |

## Iteration 2 (2026-07-18): fix, use again, verify

Both P0s fixed and re-drilled live the next day, use-fix-use:

1. **Freshness gate** (`QUOTE_FRESHNESS_TTL_SECONDS = 900` in `crypto.py`):
   a MARKET paper order on a quote older than 15 minutes is refused with
   `Refusing MARKET fill on a stale quote ... Refresh public crypto data
   first`, and a carried-forward quote past the TTL is demoted to
   `stale_cache` everywhere it is recorded — never labeled `live` again.
   Replaying yesterday's trade against the same stale cache: **HTTP 400,
   quote age 645004s** — the phantom fill is now impossible.
2. **Ticker fallback chain** (`fetch_public_crypto_tickers` in
   `crypto_data.py`): the ticker snapshot now rides the same
   Binance-then-Kraken chain as depth/trades/candles, with Kraken rows
   normalized to the Binance ticker shape. Immediately after the gate
   landed, this gap surfaced live exactly as predicted: refresh returned
   200 but the ticker stayed at 07-10 and the gate blocked ALL paper
   trading. With the chain fixed: refresh → ticker current
   (2026-07-17T23:04Z) → MARKET SOL fill at 74.99, `quote_state: live`,
   fresh timestamp.

Measured damage from the original bug: ETH's real price at drill time was
1837.68 vs the phantom fill at 1799.97 — a **2.1% fictitious price** on the
ledger.

New finding from iteration 2 (added to the backlog): when Kraken supplies
the ticker rows, the pipeline still stamps them `source: binance_public` —
the fetcher abstraction drops the provenance label (P3; honesty nit, not a
trading hazard).

## Iteration 3 (2026-07-19): the whole loop, re-run and measured

All six findings closed; the same decision cycle re-run end to end against
live public data.

| | First run (07-17) | Third run (07-19) |
|---|---|---|
| Calls to see state + information | 2 (starved) | 4 (complete) |
| Bytes the agent must read | ~250,000 | **7,289** |
| Tradeable universe | 3 crypto pairs | 3 crypto pairs + any US symbol + TW board lots |
| Quote trust | 7-day-old price labeled `live` | every quote carries age; fills refuse stale |
| Information step | empty (digest expired) | 17 of 63 items matched to holdings, newest 142 min |
| Provider labeling | Kraken data labeled Binance | status names the provider that served |

The loop now reads: crypto book (refresh+summary, 1,445 B) → US book
(759 B) → TW book (863 B) → information packet (4,714 B). Positions across
three currencies, every quote age-stamped, headlines tagged to holdings
including Chinese-language coverage of 2330.TW.

**New finding from this run (fixed same day):** the equity summaries marked
positions against whatever lookup quote happened to be cached, so a book
read after a restart valued positions at their own cost basis and reported
no unrealized P&L. Both equity summaries now accept `?refresh=true`, which
fetches current prices for held symbols only; the default read stays a
cheap local read. Marking a position at its own cost and calling the result
equity is the same class of error as the stale fill — it just fails quietly
instead of loudly.

One display artifact confirmed *not* a bug: replacement characters in a
headline appeared in the terminal, but the payload bytes were clean UTF-8
(the console codepage mangles the display, not the data).

## Iteration 4 — 2026-07-21: measurement layer (the loop can run; is it any good?)

Every prior iteration fixed the loop's *inputs* (fresh quotes, honest
labels, agent-sized payloads). This one fixes its *accountability*: nothing
recorded net value over time or the agent's reasoning at decision time, so
"the AI can run the decision loop" was unfalsifiable as an investing claim.

Two additions, both dogfooded live:

- **Decision journal.** All three order endpoints accept `rationale`
  (≤500 chars) stored on the order record; book summaries return
  `recent_orders` with it. Live probe: ETH fill `paper-f42758b87d07`
  carries "ETH quote fresh (age<15m); adding 0.01 ETH ~1.8% of free cash…"
  and the crypto summary (2,272 B) returns it. Stated reasoning is now
  comparable against outcomes, not reconstructed from fills.
- **Net-value history vs benchmarks.** `paper_snapshot_record` writes one
  row: three books' equity with mark staleness, plus BTC-USD / SPY /
  0050.TW reference prices (fetched current by default; failures recorded
  as `unavailable`, never dropped). `paper_history` returns the series and
  a window performance block. Live probe minutes apart: crypto book 0.00%,
  US book 0.00%, TW book +0.16% (a real 2330.TW mark move × the 1000-share
  lot), BTC-USD +0.03% — 3,635 B for the whole readout.

The honest-marking rules carry into the series: a snapshot taken on cold
caches says so (`oldest_quote_age_seconds`, `unmarked_position_count`), a
missing benchmark yields a null change labeled "missing data, not zero
performance", and books/benchmarks are never currency-converted or ranked.
What this enables next: run the loop on a schedule, snapshot after each
step, and let the window numbers — not the agent's self-report — say
whether the decisions beat buy-and-hold.

## Method note

Chain: status → ledger → market refresh → news read → transparent mechanical
judgment → minimal paper order → read-back. All actions discovered through
the agent contract; nothing hand-wired. The stale-fill evidence is on the
ledger: order `paper-31e67683b32a`, fill `fill-1eed1dbd100e`
(`artifacts/paper/paper_state.json`).
