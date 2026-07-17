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

## Method note

Chain: status → ledger → market refresh → news read → transparent mechanical
judgment → minimal paper order → read-back. All actions discovered through
the agent contract; nothing hand-wired. The stale-fill evidence is on the
ledger: order `paper-31e67683b32a`, fill `fill-1eed1dbd100e`
(`artifacts/paper/paper_state.json`).
