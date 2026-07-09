# M20.13 Portfolio Report And Risk Workflow

Date: 2026-05-23

## Purpose

Reduce Portfolio empty-shell surface by turning safe local `PERF/RISK`, `QUANTSTATS`, and `REPORTS` controls into a concrete read-only analytics workflow with local artifacts.

## Runtime Surface

- Portfolio Performance now renders NAV and period-return rows instead of reusing the positions table.
- Portfolio Risk tab exposes concentration, volatility, drawdown, beta, largest-sector, and provider-pricing context rows derived from local portfolio state.
- `REPORTS` writes local report artifacts under `artifacts/portfolio/reports/{report_id}/`: `summary.json`, `risk.json`, `performance.csv`, `allocation.csv`, `report.md`, and `manifest.json`.
- Portfolio report state is persisted on the active local portfolio and appears in a Report tab with artifact paths.
- Safe toolbar controls now route locally: `SECTORS` opens Allocation, `PERF/RISK`/`QUANTSTATS`/`RISK` open Risk, and `REPORTS` writes a local report.

## Safety

This milestone adds no optimizer execution, no live/private execution, no broker routing, no real order, no private API key flow, no real balance read, no margin, no leverage, no short exposure, no derivatives execution, no subscription, no billing, no CR/credits, no cloud account, no credential storage, no installed-source read, and no Fincept branding/assets/copy.

## Verification

- Focused Portfolio gate `.\.venv\Scripts\python.exe -m pytest tests\test_m7_portfolio.py -q` with repo-local TEMP/TMP -> 14 passed.
- Focused Python lint `.\.venv\Scripts\python.exe -m ruff check src\local_terminal\portfolio.py src\local_terminal\server.py tests\test_m7_portfolio.py` -> passed.
- Formatting check `.\.venv\Scripts\python.exe -m ruff format --check src\local_terminal\portfolio.py src\local_terminal\server.py tests\test_m7_portfolio.py` -> passed after formatting changed Python files.
- Frontend lint `npm run lint` -> passed.
- Full backend gate `.\.venv\Scripts\python.exe -m pytest -q` with repo-local TEMP/TMP -> 180 passed.
- Focused source-wall/live-safety gate `.\.venv\Scripts\python.exe -m pytest tests\test_clean_room_source_wall.py tests\test_m16_live_safety.py -q` with repo-local TEMP/TMP -> 12 passed.
- Repo lint `.\.venv\Scripts\python.exe -m ruff check .` -> passed.
- Frontend build `npm run build` -> passed.
- Frontend E2E `npm run e2e` -> 15 passed.
- `git diff --check` -> passed with Git CRLF working-copy warnings only.
- E2E captures `artifacts/screenshots/m20-13-portfolio-report-risk.png`.
- Browser/Playwright screenshot was visually inspected for Portfolio Report tab, local report artifacts, enabled safe toolbar actions, and no incoherent overlap.
- Changed-file credential-like string scan found no real credential, PIN, provider-key, private-key, or personal-account literal; matches were existing safety/type/redaction terms only.
- Code-review gate found no CRITICAL/HIGH/BLOCK findings. WATCH: Portfolio optimizer, report builder expansion, and planning/report lifecycle management remain deliberately gated for later local contracts.
