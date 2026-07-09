# M20.12 Portfolio Backtest Context

Date: 2026-05-23

## Purpose

Improve cross-route data flow by making Portfolio consume the richer Backtest artifacts added in M20.11 instead of linking only manifest, summary, trades, data snapshot, and provenance paths.

## Runtime Surface

- Backtest-linked portfolios now store a sanitized `backtest_context` with run id, strategy, engine, provider, data state, equity, total return, drawdown, best/worst period returns, trade count, signal count, returns curve rows, and read-only safety metadata.
- Portfolio payloads add a Backtest tab only when the active portfolio is backed by a local Backtest artifact.
- The Portfolio Backtest tab renders context rows plus the linked signal, indicator, returns analysis, and returns curve artifact paths.
- Linked Backtest artifacts now include `signals.csv`, `indicators.json`, `returns_analysis.json`, and `returns_curve.csv` when those files are present in the Backtest manifest.
- Backtest manifest artifact paths are treated as untrusted display metadata; Portfolio only links files that resolve inside the selected Backtest run directory and exist on disk.

## Safety

This milestone adds no provider, no live/private execution, no broker routing, no real order, no private API key flow, no real balance read, no margin, no leverage, no short exposure, no derivatives execution, no subscription, no billing, no CR/credits, no cloud account, no credential storage, no installed-source read, and no Fincept branding/assets/copy.

## Verification

- Focused Portfolio/Backtest gate `.\.venv\Scripts\python.exe -m pytest tests\test_m7_portfolio.py tests\test_m6_backtest.py -q` with repo-local TEMP/TMP -> 23 passed.
- Python lint `.\.venv\Scripts\python.exe -m ruff check src\local_terminal\portfolio.py tests\test_m7_portfolio.py` -> passed.
- Frontend lint `npm run lint` -> passed.
- Full backend gate `.\.venv\Scripts\python.exe -m pytest -q` with repo-local TEMP/TMP -> 179 passed.
- Focused source-wall/live-safety gate `.\.venv\Scripts\python.exe -m pytest tests\test_clean_room_source_wall.py tests\test_m16_live_safety.py -q` with repo-local TEMP/TMP -> 12 passed.
- Repo lint `.\.venv\Scripts\python.exe -m ruff check .` -> passed.
- Formatting check `.\.venv\Scripts\python.exe -m ruff format --check src\local_terminal\portfolio.py tests\test_m7_portfolio.py` -> passed after formatting changed Python files.
- Frontend build `npm run build` -> passed.
- Frontend E2E `npm run e2e` -> 15 passed.
- E2E captures `artifacts/screenshots/m20-12-portfolio-backtest-context.png`.
- Browser/Playwright screenshot was visually inspected for Portfolio Backtest context, linked signal/indicator/returns artifacts, read-only local safety status, and no incoherent overlap.
- Changed-file credential-like string scan found no real credential, PIN, provider-key, private-key, or personal-account literal; matches were existing safety/type/redaction terms only.
- Code-review gate found no CRITICAL/HIGH/BLOCK findings. WATCH: broader Portfolio risk analytics, optimizer, report, and planning toolbar actions remain gated or unchanged.
