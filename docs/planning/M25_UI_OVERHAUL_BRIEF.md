# M25 — Full UI/UX Overhaul Brief (for a dedicated session)

Date opened: 2026-07-06. Owner wants a genuine UI/UX redesign — the current UI feels
cramped and "code-dumped" (raw data pasted on the page), not just an aesthetic nit.
This brief sets up a clean session to do it properly, with working visual feedback.

## Do this FIRST: get visual feedback working

Screenshots timed out repeatedly in the prior session (`preview_screenshot` hangs);
`preview_inspect` (computed styles) and `preview_eval` did work. Before any design
work, restore a reliable screenshot loop:

- Preview config is `.claude/launch.json` → `frontend` runs `npm run dev` on :5173
  (Vite proxies `/api` → backend :8765). Start the backend first
  (`.venv/Scripts/python.exe -m src.local_terminal`) so data loads.
- Try a fresh `preview_start` + `preview_screenshot`; if it still hangs, try the
  backend-served build at :8765, a smaller viewport (`preview_resize`), or screenshot
  a specific element. Do not design blind.

## The core problem to fix: 3 layered CSS systems (tech debt)

`main.tsx` imports `theme.css`, then `styles.css`, then `terminal-components.css`.
- `theme.css` (50 lines): design tokens. Spacing maxes at 12px, fonts 0.66–1rem — too
  tight, weak hierarchy. Expand into a real scale.
- `styles.css` (~4100 lines): contains a **dead light theme** (~lines 1–3600, white
  cards `#fff`) plus a dark override block (~3644–4170). The light theme is fully
  overridden and should be removed.
- `terminal-components.css` (~1550 lines): the **final winning layer**. Edits to
  `.workspace-surface`/`.workspace-header`/`h1` must go here (styles.css copies are
  overridden — learned the hard way in phase 1).

**Consolidation is the highest-leverage cleanup**: delete the dead light theme, unify
into ONE coherent dark design system, so future changes have a single source of truth.

## "Code-dumped" data is literal — fix the rendering

Components print raw `snake_case` keys and `JSON.stringify(value)` in tables. Phase 1
added `humanizeKey()` + `.kv-key/.kv-value` styling to Backtest's `KeyValueTable`
(commit 6f94ab6). Each route currently has its own rendering (KeyValueTable is NOT
shared). Plan: a shared `humanizeKey` util + shared KV/table/card components, applied
across Dashboard, Markets, Crypto, Portfolio, News, etc.

## Design direction

Dark financial terminal, dense but organized (Bloomberg-grade density WITH hierarchy):
- Typographic hierarchy: distinct H1 / section header / label / value scales.
- Spacing: breathing room BETWEEN groups, tight WITHIN data tables.
- Color: restrained amber accent (exists), semantic green/red/cyan/yellow (exist) used
  meaningfully; not decorative.
- **Data freshness is a first-class UI concern** (see data findings below): every route
  should make live / stale / gated state and the refresh action obvious.

## Approach (each step screenshot-verified)

1. Restore screenshots. 2. Consolidate CSS into one design system + expand tokens.
3. Redesign shared components (header, cards, panels, tables, KV, badges, buttons).
4. Route-by-route layout pass, highest daily-use first (Dashboard → Markets → Crypto →
   Backtest → Portfolio → …). 5. Screenshot each; iterate.

## Hard constraints — do NOT break these

- **Stable selectors**: `data-testid`, `route-button-*`, `workspace-*`, and the
  AI-agent selectors are load-bearing for the MCP operability (M24) and Playwright
  e2e. Keep them. Restyle, don't rename/remove.
- Clean-room wall (`AGENTS.md` / `tests/test_clean_room_source_wall.py`): observe the
  original's structure, never port `D:\FinceptTerminal\app\scripts`.
- Keep the 401 backend tests + frontend build green; keep safety gates closed.

## Data reality (verified 2026-07-06) — design for real data

NOT a shell. A live refresh pulled real Binance data (BTCUSDT live, `fallback_used:
false`); network reaches Binance/Treasury/ECB (HTTP 200). 30 real provider adapters;
0 active / 14 stale / 10 unavailable / 8 key-required at rest. **Populate before
screenshotting**: run the public refresh (MCP `refresh_public_data`, or
`POST /api/providers/refresh-public/jobs`, or per-route refresh) so routes show real
data, not empty states.

## The 15 routes

Dashboard, Markets, Crypto, Portfolio, News, AI Chat, Backtest, Algo, Nodes, Code,
Quant Lab, QuantLib, Forum, Settings, Profile.

## Already done (phase 1, commit 6f94ab6) — build on it

Workspace padding 12→18/20px, h1 1.18→1.42rem (+weight/letter-spacing) in
`terminal-components.css`; Backtest `KeyValueTable` key humanization + `.kv-*` styling.
