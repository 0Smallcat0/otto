# Changelog

## Unreleased

- The daily refresh ran every morning and the owner's own holdings never moved
  (2026-08-06). Same class as the two one-shot sources, inverted: nothing was
  being lost, something was silently frozen.
  - `markets_history_refresh` took the first `MAX_HISTORY_SYMBOLS` of the
    watchlist concatenated as US + FX + TW. Eleven symbols against a budget of
    eight meant the last three fell off every single time, and TW is last. The
    caches told the whole story: eight symbols stamped that morning, and 0050,
    00982A and 2834 still stamped 2026-07-28 — nine sessions stale, the owner's
    two real positions and the index his TW calls are graded against.
  - Every result in the response read `live` and `count` said 8. The three that
    were never attempted appeared nowhere in it, so a refresh that covered
    two-thirds of the list was indistinguishable from a complete one.
  - The budget is Twelve Data's free tier — eight requests a minute
    (<https://support.twelvedata.com/en/articles/5615854-credits>). TW listings
    ride TWSE's keyless endpoint and spend none of it, so they were being
    dropped to protect a quota they never touched. The key budget now binds
    only the symbols that spend it.
  - Real positions, then symbols carrying an open call, then the indices those
    calls are graded against, and only then the watch list. Whatever still
    exceeds a budget comes back by name in `skipped`, with the reason.
  - `2834.TW` and `2834` are one cache file; the refresh now agrees. Left
    unnormalised a held name asked for by suffix neither matched the cache nor
    routed to TWSE, and would have been billed to the key.
  - Measured after: twelve symbols live, nothing skipped, every cache at
    2026-08-05. 2834's chart gained the nine sessions it was missing, and the
    deleveraging read on the wall stopped being blocked by an uncovered window.

- The margin series reached no screen, and the number it would have shown was
  the wrong one (2026-08-06). `/api/research/tw-margin` had zero references in
  the entire frontend — the store shipped the round before was invisible.
  - Taiwan desks do not read deleveraging off a streak. The comparison is
    whether margin's cumulative unwind has run further than the fall that
    caused it: on 2026-07-28 the weighted index was 12.86% off its wave high
    against margin's 9.93%, and the read was that it had further to go
    (<https://www.setn.com/news/1880517>).
  - `consecutive_reducing_sessions` counts days and cannot see distance. Three
    sessions of −0.1% is a streak of three that gives back 0.3% against a
    market down 12% — a number that reads on a screen like progress and is
    close to none. `deleveraging_progress` measures both legs peak-to-latest
    over the window the margin store itself spans.
  - The index leg is `0050`, the series this terminal already keeps and already
    benchmarks calls against. It is a large-cap ETF and not the weighted index,
    and the payload says so rather than letting the reader assume.
  - A cache that stops short of the window is reported as an uncovered window,
    never compared anyway. Removing that check made the stale case answer
    `margin_led` — deleveraging complete, the bullish read — off dates that
    were never covered.
  - `tw_margin_read` / `GET /api/research/tw-margin-history` reads the stored
    sessions without going to TWSE, the same split as `tw_announcements_read`.
    The fetching endpoint hits the exchange on every call and cannot back
    anything that renders on a screen left open.
  - The real book banner on the wall carries one line for holders of TW
    listings, and nothing at all for anyone else — the whole statistic is about
    one exchange's leverage.

- Margin balance is the second one-shot source, and it was keeping nothing
  (2026-08-06). Sweeping the class the filing store belonged to: what else here
  is published once, never archived, and permanently gone if a day is missed?
  - `/api/research/tw-margin` returned today's snapshot — 1,291 issues, 515
    reducing — and stored none of it. Every session nobody fetched was already
    unrecoverable, with every test green and the endpoint healthy.
  - A snapshot also cannot answer the question the data exists for. Price
    cannot separate capitulation from continuation; both close at the low. A
    run of sessions where forced sellers stop being forced can. On 2026-07-30
    the market-wide balance fell 0.72% while 406 issues *added* margin and
    0050's own rose 15.99% — visible only as a series, and there was no series.
  - Sessions accumulate on the call that already goes to TWSE, keyed on the
    HTTP `Last-Modified` stamp because the rows say 今日餘額 and carry no date
    at all. A payload without one is refused rather than filed under a guess.
  - Only the aggregate plus the symbols the caller asked about are stored: the
    full 1,291-issue file is not worth keeping daily, and the two questions —
    is deleveraging slowing, is my own holding still being forced out — need
    neither.
  - `trend.consecutive_reducing_sessions` resets the moment a session stops
    reducing, because that reset *is* the signal; burying it inside a streak
    would hide the only thing the series is for.
  - A published balance is a fact: an existing session is never rewritten, and
    a gap in `sessions_held` reads as a day nobody fetched, not a quiet market.

- The owner's own companies' filings now reach the page the owner reads
  (2026-08-06). The filing store and the agent's news packet were wired together
  first, which served the agent and nobody else.
  - Measured on the running terminal: `/api/news` returned 103 headlines —
    CoinDesk, SEC, an ETF explainer — while the same terminal held 720 TWSE
    filings and surfaced none. Nothing failed; the data was one API away from
    the wrong screen. That is the third time in four rounds the render step was
    the gap.
  - Filings for held TW symbols are merged into the news feed as items marked
    `relevance: "mine"`, so they ride the ranking the feed already has, where a
    holding outranks anything merely fresher. Yahoo cannot resolve a Taiwan
    ticker at all, so for a TW holding the company's own disclosure is the only
    single-name news there is.
  - **No frontend change was needed.** Getting the item shape right meant the
    existing relevance renderer picked them up: the news page now opens with
    「跟你有關(持股與追蹤中)」 and two 「我的持股 2317」 rows above every
    headline. Verified in the DOM.
  - The owner's two current holdings filed nothing on the sessions the store
    holds, so the live check used an isolated instance seeded with 2317 rather
    than pretending his feed had changed.

- Swept the class the previous change found, and stopped where a fix would have
  been fake (2026-08-06). Adding a reader for the holdings raised the obvious
  question: how many other routes can an agent not read?
  - Measured across all sixteen: three core routes had no param-free GET reader
    at all — `dashboard`, `crypto` and `profile`. The shell routes
    (`ai_chat`, `nodes`, `code`, `quant_lab`, `quantlib`, `forum`) are excluded
    by standing decision and were not counted.
  - Only `dashboard` gets one. `/api/dashboard` is 10,440 characters compact,
    comfortably inside the tool result limit, so `dashboard_read` returns the
    overview an agent asked for.
  - `crypto` and `profile` deliberately do not. `/api/crypto` is 64,633
    characters and `/api/governance` 365,060 — both far past the limit, so a
    catalogue entry there would hand back a truncation notice instead of the
    state. An action that cannot answer is not a fix, and the crypto book is
    already readable through `paper_account_summary` at ~1.5KB.
  - The first sweep was run against a backend still holding pre-`portfolio_read`
    code and reported 16 of 16; restarting first gave 15. Measurements taken
    against stale processes are not measurements.

- The holdings had no reader in the action catalogue (2026-08-06). "What do you
  make of my holdings?" is the third of three prompts the README offers a
  newcomer, and it was the one with no way in.
  - Measured on an empty install: the portfolio route exposes twelve actions and
    not one of them read the portfolio. create, load_demo, select, import,
    delete, link_backtest, link_paper and report all mutate; report_index and
    report_health describe reports rather than positions; export needs an active
    portfolio and `book_detail` needs a `{portfolio_id}` obtainable only by
    reading the portfolio first.
  - The state was reachable the whole time — `get_route portfolio` returns it —
    but an agent looking for what it can *do* looks at `list_actions`, and there
    the holdings had no reader. Nothing failed; the path simply was not where
    anyone would look.
  - `portfolio_read` exposes the existing `GET /api/portfolio`. No new endpoint;
    a catalogue entry so the read is discoverable where the agent searches.
  - On a fresh install it answers `first_use: true` with create / import / demo
    rather than an empty payload, so "no holdings" is a starting point instead
    of a dead end.

- The backtest page shows whether its own headline numbers mean anything
  (2026-08-06). Sample sufficiency was computed one round earlier and only ever
  reached the API — the screen kept rendering 總報酬 / 最大回撤 / 勝率 / 交易數
  as four large figures with nothing to qualify them, so 11 round trips over
  twenty hours looked exactly like 400 over three years.
  - That is the same defect this repo has now shipped fifteen times, and this
    one was mine, one commit old: the engine computed the qualifying fact, put
    it in the payload, and the render step dropped it.
  - The caveat sits directly under the KPI row, because that row is the surface
    that reads as a verdict. It names the round trips, the inference floor, the
    real span, and the metrics least able to bear weight — one of which is the
    win rate shown immediately above it.
  - `sampleCaveat` is a pure exported function so the decision has a guard in
    `rendering-rules.test.ts`, the suite that exists for exactly this shape.
    Confirmed by making it always return null and watching two tests fail.
  - Verified in the DOM on a real run, not through the API.

- The TWSE filing store catches itself up instead of waiting for a scheduler
  (2026-08-06). Every other cache here can be rebuilt by asking again; this one
  cannot. TWSE serves exactly one session of `t187ap04_L` and keeps no history,
  so a day nobody fetched is a day permanently absent.
  - Measured: the store held 2026-08-04 with 345 filings while TWSE was already
    serving 375 dated 2026-08-05 — a whole session hours from being lost, with
    nothing having failed and no error anywhere.
  - Leaving it to a scheduled task means it is lost whenever the schedule is not
    running, which is most of the time. The catch-up now happens on the refresh
    a decision round already makes, so it turns "somebody must remember" into
    "it happens whenever the terminal is used".
  - Only on an explicit refresh, only for Taiwan symbols, and only when a cheap
    local check says the store is behind today — a burst of rounds cannot hammer
    TWSE. An unreachable TWSE degrades to what is stored, and `sessions_held`
    then reports the gap, which is the whole reason that field exists.
  - Live: 345 filings across one session → 720 across two, as a side effect of
    one packet refresh.

- A backtest now says whether its sample can carry the question (2026-08-06).
  Ran the README's own three example prompts against a genuinely empty state
  root — the first time that has been checked. All three work; the second one
  lies by omission.
  - "Backtest an SMA cross on BTCUSDT and tell me if it's any good" returns
    −3.29%, a Sharpe of −68.81 and a 0% win rate. Those come from 79
    fifteen-minute candles and 11 round trips: about twenty hours of one market
    in one regime, 02:45 to 22:29 on a single day. Nothing in the response said
    the sample could not support a verdict, and the figures read exactly like
    one.
  - `summary.sample` reports round trips, candles, the real span in wall-clock
    terms, a verdict band, and which metrics are worst affected. Thresholds are
    external: 30 round trips is the floor at which sample means begin to
    behave, 100 where metrics are called reliable, 200+ what institutional
    practice asks across regimes.
    <https://www.backtestbase.com/education/how-many-trades-for-backtest>
  - The numbers are not suppressed — they are the run's real output. What
    changes is that a weak measurement no longer renders identically to a
    strong one, the same rule the quote and benchmark layers already follow.
  - A sample that clears 200 is still told to check its span covers more than
    one regime; trade count alone is not sufficiency.
  - Provenance checked while there: the fresh-install backtest runs on real
    Binance candles with hashes, not the deterministic generator.

- A relative thesis can now name a relative invalidation (2026-08-06). Some
  calls make no claim about where a price goes — "the index is the better
  vehicle for the same exposure" is true or false whether the market rallies or
  crashes — and an absolute level cannot express that. The 00982A reduce struck
  at 21.61 named 23.4, 4.8% away; a market-wide 5% move reaches it with the
  index rising just as much, excess unchanged, and the board would mark a thesis
  that never failed as 看錯了. Not hypothetical: the 2026-07-30 reduce died the
  next session to a market-wide limit-up, +10% on the index it was measured
  against.
  - `invalidation_excess_pct` names the threshold in percentage points of excess
    return against the call's benchmark. The losing direction comes from the
    stance — reduce and avoid are wrong when the thing they stepped away from
    outruns its market, accumulate and hold when the thing they own lags it — so
    only a positive magnitude is accepted.
  - Without both benchmark ends it reports nothing rather than guessing, the
    same rule the rest of the scorer runs on.
  - The board renders the condition it is actually scored on: the 00982A row now
    reads 贏過 0050.TW 8.00% instead of 漲過 23.4.
  - The guard drill caught a weak test before the code: the first version used a
    5% market-wide rally against an 8-point threshold, so it passed even with
    the benchmark leg removed and proved nothing. Rewritten to the real event —
    2026-07-31's +10% limit-up — which fails loudly without the benchmark.

- The TWSE filing store is now wired into the packet the decision loop reads
  (2026-08-06). Accumulating those filings closed nothing on its own: asked for
  context on 2834 and 2317, `/api/news/packet` still returned `matched_count: 0`
  — eight items comprising a target-price note on an unrelated stock, a lottery
  draw and three CoinDesk pieces — while the terminal already held two real 鴻海
  filings it never offered.
  - A company's own material disclosure leads the packet, above any headline
    that merely mentions it. Keyword matching over a general feed cannot reach
    a Taiwan single name; the filing can.
  - Filings take their slots off the top but headlines keep a floor, so a packet
    is never all filings and never drops them for a lottery result.
  - `filings_note` says that an absent filing means nothing about whether the
    company filed — that answer lives in `tw_announcements_read` and its
    `sessions_held`.
  - Live, same call as before: `matched_count` 0 → 2, with the buyback progress
    note and the 8/12 board meeting on top.

- A benchmark that never ran reported itself as a score of zero (2026-08-05).
  Re-running the agent-operability suite to check the README's headline claim
  still held after four rounds of MCP-surface changes, every task came back
  failed: `claude-sonnet-5: 0/21 (0%)`. The cause was not the terminal — each
  task cost $0, used no tokens, lasted 945ms and reported
  `OAuth access token has expired`. No agent ever reached the terminal.
  - `summarize` now separates tasks that ran from tasks that errored before
    starting. `success_rate` is `None`, not `0.0`, when nothing was graded, and
    a partly-errored run scores only what actually executed rather than letting
    an authentication bounce dilute the rate.
  - `--report` refuses to write EVAL.md when any task never ran. Publishing a
    benchmark from a run whose agents never started is the strongest version of
    the lie this suite exists to prevent.
  - The failure reason travels with the non-result, quoted from the agent's own
    output, so "the terminal could not be operated" and "the agent never
    reached the terminal" cannot be mistaken for each other.
  - Same run, after the fix: `no score — 0 of 21 tasks ran`.
  - `--smoke` was clean throughout: 21/21 tasks still have a sound red baseline,
    so the harness and the graded checks survived the surface changes.
  - README numbers corrected: 137 → 139 actions (two added this week and never
    reflected), and the eval table is now dated and marked as covering the
    20-task suite it actually measured, rather than presented as current.

- An oversize response is now a map, not a severed string (2026-08-05).
  Truncating serialised JSON at a character count guarantees the tail is
  invalid, and a sweep of the core surface found how widespread that was: **7 of
  16 routes** came back unparseable through `get_route` — markets, crypto,
  paper, news, quant_lab, settings, profile — plus two read-only actions
  (`provider_refresh_lifecycle_inspect`, `command_center_preflight_matrix`).
  Asking what a route holds returned a blob the agent could not parse.
  - The truncation notice is the one response that must never be malformed,
    because it is what the agent acts on to recover. It now returns the
    payload's shape instead of a prefix: which keys exist and what each weighs,
    largest first.
  - When a single key holds over 80% of the payload the notice descends one
    level, because `get_route`'s wrapper is `{route_id, endpoint, status,
    state}` and naming `state` as the large one tells the agent nothing it did
    not know. markets now reports `research_summary` 99,384, `stocks` 60,905,
    `quote_reference_coverage` 29,655 — enough to choose a narrower action.
  - Plain strings still truncate as text; an error message has no structure to
    preserve.
  - markets went from 40,108 characters of unparseable prose to 504 characters
    of actionable JSON, and all 16 routes now parse.

- The catalogue an agent reads to learn the terminal arrived truncated into
  prose (2026-08-05). `list_actions` unfiltered returned every field of all 134
  actions: 40,106 characters, roughly 10,000 tokens, past `MAX_RESULT_CHARS` and
  cut mid-structure. The second call an agent makes handed it a blob that no
  longer parsed as JSON. Restoring the old behaviour today produces 49,957 — the
  defect was getting worse with every action added.
  - Measured, not assumed: each MCP tool definition reportedly costs 200-500
    tokens and a handful of servers can burn 30,000-60,000 before the first user
    message. <https://thenewstack.io/how-to-reduce-mcp-token-bloat/>
    Otto's own tool definitions are fine — 6 tools, 2,805 chars, ~700 tokens —
    so the bloat was entirely in responses.
  - Progressive disclosure applied to responses: unfiltered is now an index
    (action_id, route, method, plus the write and confirm flags, which are what
    an agent needs *before* choosing), with `route_ids` and a hint for drilling
    in. `route_id=` returns the full contract for that route.
  - Tool results are serialised compactly. Indentation carries no information
    and cost 13.5%-22.4% of every payload — 80,282 characters of whitespace on
    the markets page alone, about 20,000 tokens.
  - Net: `list_actions` 40,106 → 19,367 and it parses; `list_routes` 7,231 →
    5,191; `research_ledger_read` 23,132 → 18,284; `terminal_status` 1,780 →
    1,482.

- Every failed action was reported to the client as a successful tool call
  (2026-08-05). `run_action` hands back the terminal's own response with its
  HTTP status inside, and `isError` was hardcoded false — so a 422 for malformed
  arguments, a 404 for a mistyped action id, or a 400 refusing an order on a
  stale quote all arrived as successes, with the failure buried in JSON the
  model had to notice unaided. That is the difference between an agent retrying
  with corrected arguments and an agent confidently building on a result it
  never received, and it is the most-cited complaint about this whole category
  of server: the protocol works, the data does not.
  <https://shibui.finance/guide-best-mcp-server-stock-data>
  - Found by timing every tool against the client timeouts people actually hit
    (10s in the Python SDK, 60s elsewhere) and noticing two calls returning in
    0.0s. One was a genuinely queued job; the other was a 422 wearing a success.
  - A queued job is not a failure: `status` is an integer for HTTP and a string
    for job state, so only integers outside 2xx mark the call as an error.
  - Timing itself came back clean — the slowest call is the first
    `terminal_status` at 9.7s, which includes starting the backend, and
    `refresh_public_data` already returns a job id instead of blocking.

- Two things a stranger hits in the first minute (2026-08-05). Setup friction is
  the most-cited reason people abandon MCP servers before seeing what one does,
  and "different clients support different protocol versions, so a server might
  work with one client but completely fail with another" is the most-cited way
  they break. <https://mbsamuel.substack.com/p/how-can-the-model-context-protocol>
  <https://dev.to/sky98/the-real-story-what-nobody-tells-you-about-mcp-server-setup-2o3f>
  - **Protocol version negotiation was a spec violation.** `initialize` echoed
    whatever version the client asked for, so a client on a version this server
    does not implement was told yes, never got its chance to disconnect, and hit
    the mismatch later as some unrelated call misbehaving. The spec: "If the
    server supports the requested protocol version, it MUST respond with the
    same version. Otherwise, the server MUST respond with another protocol
    version it supports." `SUPPORTED_PROTOCOL_VERSIONS` now names the three
    releases whose wire surface is actually implemented — the common core of
    inputSchema plus text content, no outputSchema or structuredContent — and
    anything else gets the latest supported version back.
  - **The entry point handed strangers the maintainer's backlog.**
    `terminal_status`, the tool that tells you to call it first, returned this
    project's milestone tracker: "M23.68 Final non-live completion audit", a
    mission-ledger path under `docs/planning/`, a do_not_redo count, and a
    resume_rule pointing at `PROJECT_STATE.md` — files a wheel does not contain.
    It now answers what a first call should: health, the risk gates, whether
    this install has anything in it yet, and what to try first, with the fact
    that nothing needs an API key stated rather than left to be discovered.

- Taiwan single-name filings, accumulated (2026-08-05). Asked for context on the
  owner's two Taiwan holdings, the news layer returned `matched_count: 0`
  against 120 stories, all Federal Reserve orders and CoinDesk. On the only two
  names holding real money, the agent was blind — and the 7% "crash" that turned
  out to be an ex-dividend was found by reading TWSE's raw API by hand.
  - Surveying the field first rather than assuming: 116 finance MCP servers on
    one directory, and every comparison of the leading ones describes the same
    shape — an API passthrough with "no discussion of Taiwan, Asia-specific
    data, portfolio tracking, paper trading functionality, or AI agents making
    investment judgments — only data retrieval".
    <https://shibui.finance/guide-best-mcp-server-stock-data>
  - Taiwan is uncovered for a reason visible in the data: TWSE's open endpoints
    "serve only the current period so historical data must be accumulated over
    time". <https://blog.itick.org/en/stock-api/taiwan-stock-api-comparison-guide>
    One fetch of `t187ap04_L` returns one session — 345 filings across 241
    companies, and nothing from the day before. Accumulating turns the same free
    endpoint into a history no passthrough can answer from.
  - `tw_announcements_refresh` folds a session in, append-only and de-duplicated;
    `tw_announcements_read` answers for the owner's TW holdings and every TW
    symbol with an open call. `sessions_held` travels with every answer so an
    empty result reads as "no filing on the days we hold" rather than "the
    company said nothing".
  - TWSE ships the subject column as `"主旨 "` with a trailing space. Reading the
    obvious key raises KeyError, and swallowing that would have stored every
    filing with a blank subject while reporting a full row count.
  - A fetch failure raises rather than returning an empty list: "the free tier
    silently returns incomplete data without an error" is the most-cited
    complaint about this whole category, and silence-as-success reproduces it.

- The wheel carries the dashboard (2026-08-05). It never had: the built UI lived
  in `frontend/dist`, outside the `otto` package, so every wheel shipped 75
  Python files and no screen. A `uvx` install got a working MCP server, a
  working API, nothing at `/`, and a README instructing it to run
  `npm --prefix frontend install` inside a directory the install does not
  contain. Nothing failed — the API was right, there was simply no screen.
  - Vite builds into `otto/local_terminal/ui`, `package-data` ships it, and the
    server resolves the packaged UI first with `frontend/dist` kept as a
    fallback so an older checkout does not lose its screen.
  - The bundle is committed, deliberately. `uvx --from git+https://…` builds the
    wheel on the user's machine, which has no node, so an uncommitted bundle is
    an absent one. Committing a build artefact is only honest if it cannot
    drift, so CI rebuilds it and fails on any diff or untracked file.
  - `tests/test_packaged_ui.py` pins the three parts to each other: the build
    writes into the package, packaging ships what it writes, and `index.html`
    references assets that are actually committed — a half-committed build
    installs cleanly and then serves a blank page.
  - Verified by installing the wheel into an empty venv with no checkout and no
    node: `GET /` returns the dashboard and the referenced bundle serves.

- A dividend stopped reading as a loss (2026-08-04). 台企銀 (2834), a holding of
  the owner's, closed at 16.90 against an 18.20 previous close. Every surface
  called it −7.14%, the largest fall in the universe, and sorted it to the top
  of the research queue on a day the index fell 1.32%. It had gone
  ex-rights-and-dividend that morning for 1.471029 per share; against TWSE's own
  16.72 reference price it rose 1.08% and beat the index by 2.4 points.
  - `twse_corporate_actions` reads TWSE's 除權除息計算結果表 (TWT49U): the
    pre-event close, the value distributed, and the reference price the exchange
    opened against. No key, no account. Columns are resolved by TWSE's own
    `fields` header rather than by position — a reordered column would otherwise
    be applied as if it were a price.
  - Scoring measures the holder, not the print. The payout is added to the price
    before the return AND before the invalidation test: a level written against
    a pre-payout series is otherwise silently tightened and closes a thesis on a
    step the thesis never claimed anything about. The 2834 hold struck at 18.00
    reads −6.11% and invalidated without this, and +2.06% with it — an 8.17
    point error, on a call that beat the index.
  - The scan measures the same move against the reference price and says so. The
    match is made by reversing the quote's own reported change to recover the
    previous close it was measured from, not by asking whether the ex-date is
    today: a closed market reports the last session, and the UTC date disagrees
    with Taipei for eight hours a day.
  - An unreachable TWSE degrades to the price-only reading rather than refusing
    to score, and the call then carries no distribution, so nothing is invented.
  - `score_price` stays the raw print; `distributed_per_share` and
    `price_only_pct` are recorded beside it so the adjustment is never silent.

- The judgment ledger can finally answer the question it was built for
  (2026-08-03). Benchmark stamping shipped 2026-07-30; every call journaled
  before it carried no index level on either end, so `vs_benchmark` reported the
  whole existing record as unmeasured — a scorecard that could state a hit rate
  and not the thing the hit rate cannot say.
  - `backfill_benchmarks` reconstructs the missing levels from published daily
    closes. A live quote genuinely cannot recover a past level, which is what
    the record path warns about; a close the exchange printed can.
  - Reconstruction is never disguised as a live stamp: filled calls carry
    `benchmark_ref_source` and the session actually used, the scorecard reports
    `backfilled_count`, and the board flags each one.
  - A call struck on a non-trading day takes the previous session, named rather
    than implied.
  - A call ON its own benchmark takes both legs from itself. Pricing BTC-USD
    against BTC-USD's daily close would have compared 65,338 at strike to
    64,098 at close and manufactured 1.9% of excess return for an instrument
    against itself, then fed it into `avg_excess_pct`.
  - Yahoo daily closes round the float64 artefact away: 101.69999694824219 is
    not a price the exchange published.
  - **The board now renders it.** The scorecard's benchmark block, `excess_pct`
    and `beat_benchmark` were computed and dropped at the render step — the same
    shape as twelve of the last thirteen defects. The scored table gains a VS
    INDEX column, coloured by the verdict and never by the sign, because a call
    that meant to stay out wins with a negative excess.
  - Applied to the real ledger: hit rate stays 0 of 4, and 2 of 3 measurable
    calls beat their index. The 2330 hold graded a 6.58% loss beat 0050 by
    1.29 points over the same window.

- Distribution renamed to `otto-terminal` (2026-08-03). Both `otto` and
  `otto-mcp` are already owned on PyPI by unrelated projects, so the release
  that the roadmap called "only a publish action away" could never have
  succeeded. The import package is unchanged — no source moved.
  - New console script `otto-terminal` (same entry point as `otto-mcp`) so the
    install line needs no `--from`: `claude mcp add otto -- uvx otto-terminal`.
    Documenting `uvx otto-mcp` would install a stranger's package.
  - `/api/health` and MCP `serverInfo` looked up `version("otto")`. On a machine
    with the unrelated `otto` installed that returns *their* version instead of
    raising, so the app would have reported a false version rather than falling
    back. Both now ask for `otto-terminal`.
  - `server.json` added for the official MCP registry (stdio, PyPI package).
    Its schema pin is unvalidated — run `mcp-publisher validate` before
    submitting.

- Owner fix-it round (2026-07-22): disclosed limitations are now fixed
  capabilities, not caveats.
  - News matching uses official security names from local reference caches
    (Nasdaq Trader directory for US listings, TWSE daily quotes for Chinese
    names) on top of tickers and the small alias table — 2317.TW now matches
    鴻海 headlines and AVGO matches "Broadcom" without hand-curated entries.
  - TW odd-lot fills price against the real TWSE odd-lot session data
    (TWT53U): BUY pays the odd-lot ask, SELL hits the odd-lot bid, with a
    ±5% band guard against mixed-vintage data and a stated fallback to the
    regular-session quote when the dataset is unreachable.
  - Resting crypto orders now check the price PATH between processing runs
    against cached closed candles: a LIMIT touched by a candle range fills
    at the limit price, a triggered STOP fills at that candle's close (never
    at the stop level itself); STOP_LIMIT stays trigger-at-processing only.
  - GDELT news refresh accepts the article payload GDELT serves alongside
    its 429 rate-limit code, retries once, and gets a 20s timeout (a
    throttled GDELT stalls the TLS handshake past 8s) — a throttle no longer
    reads as an outage. BLS macro fetch collapses three per-series GETs into
    one multi-series POST (the unregistered quota is 25 requests/day) and a
    same-session BLS cache reads as live-with-age instead of stale_cache.
  - Stooq is retired: the upstream closed its no-key CSV quote endpoint, so
    the provider registry and the refresh sweep now report `retired` with
    the successor (`markets_quote_lookup`, Yahoo) instead of a daily
    failure. New `retired` provider state in the catalog.

- Equity LIMIT orders on both books (129 actions): a LIMIT already at or
  better than the live quote fills immediately at the market price; anything
  else rests WORKING until `equity_process_paper_orders` /
  `tw_equity_process_paper_orders` re-fetches live quotes for the resting
  symbols and fills the crossed ones — at the live quote, never at the limit
  price itself, with the same guards as submit (currency, freshness,
  daily-limit band; TW fee/tax and lot labeling carry through). Resting BUY
  cash is checked against the limit (worst case) at submit and re-checked at
  processing, not reserved — stated in the summary scope. WORKING orders can
  be cancelled (`equity_cancel_paper_order` / `tw_equity_cancel_paper_order`).
  The agent can finally express "buy on a pullback to X" and "sell into
  strength at Y" on stocks instead of polling.
- Crypto fills now cross the spread: MARKET and resting fills BUY at the
  ask and SELL at the bid (the real order book, not a slippage model),
  falling back to the last trade price when no book side is available or
  when the book side sits more than 2% from the last price (mixed-vintage
  data — e.g. a cached depth ladder next to a newer candle close — would
  otherwise fill at a phantom level). Every fill records `fill_basis`
  (`ask`/`bid`/`last_price_no_book`/`last_price_book_out_of_band`) so the
  convention is auditable per fill. Filling at the last print
  flattered every fill by half the spread — the same direction of optimism
  as the stale-quote bug, just smaller. Resting orders still trigger on the
  last price; the summary states the whole convention (`fill_convention`).
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
