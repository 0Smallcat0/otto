# M21.6 Alpha Vantage Quote Watchlist

Date: 2026-05-24

## Scope

M21.6 deepens the Markets Stocks and ETF quote workflows by expanding the existing
Alpha Vantage optional-key `GLOBAL_QUOTE` adapter from one default symbol per route
into bounded per-symbol watchlists:

- Stocks: `AAPL`, `MSFT`, `NVDA`
- ETF: `SPY`, `QQQ`, `IWM`
- Agent override: optional `symbols` list or comma-separated string, capped at 5
  sanitized symbols per request

This is an incremental Markets route parity slice. It does not close all M21 route
gaps.

## Reference Evidence

- Official Alpha Vantage documentation was refreshed on 2026-05-24:
  `https://www.alphavantage.co/documentation/`.
- The official `GLOBAL_QUOTE` endpoint remains one ticker per request. Alpha
  Vantage's bulk quote endpoint is premium, so this local terminal uses bounded
  per-symbol requests and per-symbol daily cache files instead of implementing a
  paid bulk dependency.
- Live installed-app observation during this slice was limited to safe application
  launch/foregrounding. No credential/PIN was entered, no new screenshot was
  retained, and no account/commercial surface was used as product evidence.
- Existing sanitized Fincept reference logs show a dense Markets grid with
  multi-symbol rows, quote/state columns, toolbar refresh controls, and global
  market status context. M21.6 uses that behavior shape as evidence, not any
  installed source code or assets.

## Implementation Contract

- Keep Alpha Vantage behind `alphavantage_global_quote_optional_key` and the local
  secret store.
- Never return, log, screenshot, commit, or expose the stored provider key.
- Do not include Alpha Vantage in public no-key refresh jobs.
- Do not use fixture/default quote prices as primary runtime data.
- Return `key_required`, `unavailable`, `rate_limited`, or `stale_cache` explicitly
  when live data is not available.
- Cache each symbol independently under
  `market_data/equities/alphavantage/global_quote/{symbol}.json`.
- Keep `GLOBAL_QUOTE` quote data as market-data context only. It is not a broker
  key, order path, real balance read, exchange entitlement activation, margin,
  leverage, short, derivative, or live trading control.

## Product Changes

- Added bounded watchlist payload assembly in
  `src/local_terminal/alpha_vantage_data.py`.
- Added direct watchlist API endpoints:
  - `GET /api/alpha-vantage/equity-quotes`
  - `POST /api/alpha-vantage/equity-quotes/refresh`
  - `GET /api/alpha-vantage/etf-quotes`
  - `POST /api/alpha-vantage/etf-quotes/refresh`
- Updated Markets route refresh endpoints so existing `QUOTE` / `ETF QTE`
  workflows populate watchlists by default.
- Updated provider freshness secondary cache coverage for `MSFT`, `NVDA`, `QQQ`,
  and `IWM`.
- Updated the AI Agent contract with `markets_stocks_quote_watchlist_refresh` and
  `markets_etf_quote_watchlist_refresh`.
- Updated Markets UI panels to show watchlist rows, cached/live/stale counters,
  quote state, cache path, and provider attribution.

## Verification Status

M21.6 verification evidence:

- `.\.venv\Scripts\python.exe -m pytest tests\test_m20_alpha_vantage_quote_provider.py -q`
  with repo-local `TEMP`/`TMP` -> 10 passed.
- `.\.venv\Scripts\python.exe -m pytest -q` with repo-local `TEMP`/`TMP` ->
  224 passed.
- `.\.venv\Scripts\python.exe -m pytest tests\test_clean_room_source_wall.py tests\test_m16_live_safety.py -q`
  with repo-local `TEMP`/`TMP` -> 12 passed.
- `.\.venv\Scripts\python.exe -m ruff check .` -> passed.
- `npm run lint` in `frontend/` -> passed.
- `npm run build` in `frontend/` -> passed.
- `npm run e2e` in `frontend/` -> first run found the old single-quote e2e
  assertion; after updating the test to the watchlist contract, 15 passed.
- Browser check opened the local Markets route in the in-app browser and confirmed
  `Alpha Vantage Watchlist`, `AAPL,MSFT,NVDA`, `Alpha Vantage ETF Watchlist`, and
  `SPY,QQQ,IWM` were visible.
- Screenshots captured under ignored local artifacts:
  `artifacts/screenshots/m21-alpha-vantage-watchlist-stocks.png` and
  `artifacts/screenshots/m21-alpha-vantage-watchlist-etf.png`.
- Visual verdict passed with score 91 in
  `.omx/state/m21-alpha-vantage-watchlist/ralph-progress.json`.
- `git diff --check` -> passed with Git CRLF working-copy warnings only.
- Exact sensitive-literal scan for known account credential/PIN literals returned
  no matches.
- Local code-review gate -> pass/comment; no CRITICAL/HIGH/BLOCK findings. Watch:
  future quote breadth should use a separate provider comparison/gate before
  adding paid bulk endpoints or more optional-key families.

## Remaining Gaps

- This is still optional-key provider breadth, not a public no-key quote source.
- Alpha Vantage bulk quotes remain premium and are not implemented.
- Non-crypto quote breadth is improved for two route tabs only; Indexes, Regional,
  FX spot quotes, commodities spot/futures quotes, and broader provider comparison
  remain future work.
- Live trading and broker/exchange integration remain future-only under the
  dedicated safety contract.
