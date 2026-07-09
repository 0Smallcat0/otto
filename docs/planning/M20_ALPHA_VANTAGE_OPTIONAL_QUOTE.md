# M20.26 Alpha Vantage Optional Equity Quote

Status: implementation milestone.

## Scope

Add the first optional-key equity quote adapter for the Markets Stocks workspace, behind the reviewed M20.24 local secret store.

This milestone reduces the M20.4 Stocks gap: SEC companyfacts remain the no-key fundamentals source, and Alpha Vantage `GLOBAL_QUOTE` becomes the first local-key quote source for a single default stock symbol (`AAPL`). Without a stored local key, the runtime returns `key_required` and does not inject fixture/default stock prices.

## Provider Entry Gate

- Provider: Alpha Vantage Global Quote.
- Provider id: `alphavantage_global_quote_optional_key`.
- Official docs checked: 2026-05-23.
- Official docs:
  - https://www.alphavantage.co/documentation/
  - https://www.alphavantage.co/premium/
  - https://www.alphavantage.co/terms_of_service/
- Endpoint: `GLOBAL_QUOTE`, one ticker per request.
- Auth mode: optional local key.
- Rate-limit policy: official premium page states standard free usage is 25 API requests per day; the adapter uses a daily local cache and does not run in public no-key refresh jobs.
- Data freshness: official docs state the quote endpoint defaults to end-of-day data unless realtime or delayed entitlement is configured by the user. This milestone does not request or activate realtime entitlements.
- Cache path: `market_data/equities/alphavantage/global_quote/AAPL.json`.
- TTL: 86400 seconds.
- Runtime fallback: local stale cache or explicit `key_required`, `rate_limited`, or `unavailable`; never fixture quotes as primary runtime.
- UI attribution: Markets Stocks source card, quote panel rows, provider freshness strip, local-state storage path, and advanced context source.
- Safety class: `optional_local_secret_data_provider`.

## Safety Boundaries

- No bundled key.
- No HTTP endpoint returns the stored value.
- No value is written to repo, logs, screenshots, docs, or commits.
- No broker/exchange private API flow.
- No live order, real balance read, margin, leverage, short, or derivatives path.
- Not included in `/api/providers/refresh-public` or the manual public provider refresh job.

## Verification

Focused gate:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_m20_alpha_vantage_quote_provider.py tests\test_m20_sec_stocks_fundamentals.py tests\test_m2_local_state.py tests\test_m19_provider_registry.py -q
.\.venv\Scripts\python.exe -m ruff check src\local_terminal\alpha_vantage_data.py src\local_terminal\markets.py src\local_terminal\server.py src\local_terminal\storage.py src\local_terminal\providers.py src\local_terminal\advanced_context.py tests\test_m20_alpha_vantage_quote_provider.py tests\test_m20_sec_stocks_fundamentals.py tests\test_m2_local_state.py
```

Milestone completion also requires full pytest, source-wall/live-safety tests, frontend lint/build/e2e, browser screenshot evidence for Markets Stocks quote state, `git diff --check`, code review, and Lore commit.
