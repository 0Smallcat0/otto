# M25 UI Fix Brief — a self-contained plan for a fresh AI to finish the redesign

You are picking up a UI redesign of a locally-run "financial terminal" (FastAPI
backend + React/Vite frontend in `frontend/`). A lot is already done; your job is
the last, most important step. Read this whole brief before touching code. A full
deep-use audit is in `artifacts/ui-review/m25/UX_AUDIT.md` (read it too).

---

## 0. THE governing principle (from the owner — this resolves everything)

> **The UI is for humans; the SYSTEM (backend API / MCP) is for the AI.**

This app is operated by an AI (the owner commands an AI, the AI drives the terminal
through the backend `/api` — NOT through the browser DOM). Therefore **all operator /
diagnostic / machine data must be REMOVED from the UI**, not merely humanized. The AI
still reads it via `/api`, so deleting it from the screen does NOT break AI operability.

The earlier instinct "don't reduce information" was **wrong for the UI**. That info
lives in the system for the AI; the human screen should show only what a *person*
wants. Your mandate: **per route, keep only the human content; delete everything that
exists for the AI operator; then format, de-jargon, de-duplicate, and fix the few real
bugs.**

What counts as "operator/machine content to CUT from the UI":
provider registries & states, "provider freshness" boards, coverage/source-contract/
provider-stack tables, cache file paths, TTLs, raw ISO timestamps, row-ids/hashes,
`snake_case` states/enums, governance diagnostics, `agent_contract.json`/`manifest.json`,
supervision/command-center, "read false / writes false", artifact paths, recovery queues,
book-levels/provider-trades counts, `public_or_cache_runtime`, `inspect_stale_cache`,
"Run Ready true/false", "Fallback Required", provider-name action buttons (FINNHUB/FMP/MOEX).

What to KEEP (human content), per route: the actual numbers a person watches (portfolio
value, P/L, prices), the chart, the watchlist/holdings, the news headlines, the paper-
trade actions, and the few settings a human sets (theme, refresh, profile).

---

## 1. Hard constraints (do NOT break these)

- **Do NOT touch backend Python or `/api`.** No Python changed all session; the full
  `pytest -q` (401 tests) is green and must stay green. Your work is frontend-only.
  Exception you MUST respect: `tests/test_m19_theme_system.py` reads the CSS — keep the
  M19 token names in `theme.css` and the required selectors in `terminal-components.css`,
  and never put the literals `#000/#000000/#030506/#07090b/#ffffff` in `theme.css` or
  `#ff9a13/#cf6e00/#ffffff/"M18 clean-room visual parity layer"` in
  `terminal-components.css` (the test forbids them).
- **AI operability is via `/api` / MCP, not the DOM.** Cutting UI content is safe.
- **The Playwright e2e `frontend/tests/m2-shell.spec.ts` is text-coupled and WILL break**
  as you cut/relabel content. The owner has ACCEPTED this. It is NOT a pytest gate.
  Update it to match the new UI at the end (or leave failing with a note) — do not let
  it constrain the redesign.
- **Clean-room wall** (`AGENTS.md`, `tests/test_clean_room_source_wall.py`): never copy
  from `D:\FinceptTerminal\app\scripts`. Observe structure only.
- **Do NOT delete `frontend/src/styles.css` lines 1–3617** (the "dead light theme"): it
  holds the structural layout (grids/flex) for all routes; only its colours are dead.
  Do visual work in `terminal-components.css` (loaded last, wins).

## 2. How to run + screenshot (this took a while to work out)

- Backend runs on `:8765` (auto-started). Dev server: launch.json config **`frontend-m25`**
  = `npx vite --host 127.0.0.1 --port 5199 --strictPort` (a dedicated port; the shared
  `frontend`/:5173 config is used by another session). Vite proxies `/api`→:8765.
- **`preview_screenshot` HANGS — do not use it.** Use the chrome-devtools MCP
  `take_screenshot` against the dev server. After navigate/reload, wait ~1200–1500ms
  before screenshot/eval (data loads async; too-early reads show the offline fallback).
- Rebuild the backend-served build with `npm --prefix frontend run build` so the owner's
  `:8765` reflects your changes.
- Verify no horizontal overflow after layout changes: `document.documentElement.scrollWidth
  - clientWidth` should be 0 on every route.

## 3. The design system is ALREADY BUILT — reuse it, don't rebuild

The warm-editorial "ink & ember" system exists and the owner approved its *look*. Reuse:
- **`frontend/src/theme.css`** — tokens: warm surfaces (`--terminal-bg:#17130f` … ), one
  amber accent (`--terminal-accent:#e0a458`), muted sage/clay semantics
  (`--terminal-green/#7fb069`, `--terminal-red/#d9695a`), 8pt spacing, self-hosted
  **Fraunces** variable serif (`--font-serif`), sans + mono. Excellence tokens
  (`--terminal-hi` top-highlight, easing, focus ring).
- **`frontend/src/terminal-components.css`** — the winning CSS layer. Contains the M25
  editorial layer (serif headings, small-caps labels, hairlines), the left-sidebar nav,
  the excellence pass (tabular-nums, press `scale(.97)`, surface-depth-not-shadow), a
  site-wide rule that **hides operator diagnostic panels** via `data-testid` selectors
  (`[data-testid*="coverage"|"provider-stack"|"source-contract"|…]`), and table-bounding.
  **Extend this file** (append) rather than editing earlier rules.
- **`frontend/src/humanize.ts`** — USE THESE, don't reinvent:
  `humanizeKey/humanizeName/humanizeState` (snake_case→Title Case + acronym map),
  `formatCurrency`, `formatMaybePrice`, `formatMaybeNumber` (parse numeric strings →
  `$63,683.60`, group, magnitude-decimals; passthrough non-numeric), `formatPercent`
  (signed, real −), `formatCompactNumber` (K/M/B), `relativeTime` (ISO → "3h ago"),
  `shortPath`, `humanizeBool` (Yes/No).
- The **Dashboard is already redesigned as the template** (`Dashboard.tsx`): 30-source
  board collapsed to a one-line summary; supervision panel removed; each widget = title +
  status pill + KPIs + a few humanized rows; hero KPIs `$`-formatted. Match this pattern
  everywhere.

Design rules to hold (research-backed, already in the CSS): one accent (amber) for
chrome only; green/red for *data* only; `tabular-nums` on all numbers; hairlines/space
not boxes/shadows; small-caps eyebrows; big serif for the one hero number; em-dash `—`
for empty (never `null/NaN/0`-as-nothing); status as pills; cut columns; ≤ a handful of
things per view.

## 4. Global fixes (do these first — they cascade)

1. **Kill the leftover system chrome.** The top `File/Navigate/View/Help` menu bar
   (`main.tsx` `.topbar` `.global-menu`) is desktop-app cruft — remove or reduce to a
   real human action set. The "Provider freshness" one-liner (`ProviderFreshness.tsx`,
   rendered in `main.tsx`) is operator framing ("15 ACTIVE / 3 STALE / 10 GATED / SHOW 34
   SOURCES") — replace with a quiet human "Data updated 3h ago · Refresh" or remove; keep
   only the refresh action if a human needs it. The command-center strip is already
   removed; the drawer (`ShellCommandCenterDrawer`) is now dead — delete it + its state.
2. **De-jargon status lines.** Delete "X synced" / "State loaded" status text; if a
   status is needed make it human ("Updated 3h ago").
3. **Format every number** via `humanize.ts` (many are done; sweep the rest: the
   `DashboardPanelCard` metric/row values, Algo/News/Nodes/Code/QuantLab numbers). No
   raw `100000.00`, no 8-decimal, no raw ISO, no `true/false` (→ Yes/No or a pill).
4. **Fix the real bugs:** Crypto BID/ASK KPI truncates ("$6…") — let it wrap or shrink;
   Markets status cache-path text overlaps the message; Crypto chart axis (76,378–77,354)
   disagrees with the KPI quote ($63,683.60) — investigate the data mapping (chart uses a
   different symbol/source than the quote) and make them consistent or clearly labelled.

## 5. Per-route plan (KEEP vs CUT)

Route components live in `frontend/src/components/` (+ `markets/`); routing is in
`workspaces.tsx`. For each, **cut the operator panels/status, keep the human content,
format + de-jargon.** Screenshot before/after; commit per route.

- **Dashboard** (`Dashboard.tsx`) — mostly done. Remaining: the "Provider Freshness /
  Provider Registry" widget is operator data → drop it from the default widget set;
  format the `DashboardPanelCard` values; dedupe (CASH/EQUITY already in the hero row).
- **Markets** (`markets/MarketsWorkspace.tsx` + sub-panels) — diagnostic panels already
  CSS-hidden; now **cut them from JSX** (SourceCoverageMatrix/QuoteReferenceCoverage/
  ProviderStack/SourceContract usages ~lines 1880-1881 + per-tab pairs) and their imports.
  Slash the ~26-button toolbar to a few human actions (provider-name buttons are operator
  concepts — remove). Remove the cache path + overlapping text from the status line.
  Humanize asset-tab subtitles or drop them. KEEP: asset tabs, the actual price/quote
  tables (formatted), charts.
- **Crypto** (`Crypto.tsx`) — CUT the "Provider Snapshot" panel and the system status
  dateline (cache path, multiple source/state). KEEP: the KPI row (fix BID/ASK truncation,
  drop CANDLES/redundant QUOTE), the chart (fix quote/axis mismatch), the watchlist, the
  paper order ticket + order book. Format all prices (mostly done).
- **Portfolio** (`Portfolio.tsx`) — CUT the pricing-provider/status plumbing. KEEP:
  value/positions/exposure/allocation/transactions tables (numbers formatted, done) + the
  clean first-use empty state. Humanize the remaining source columns (done) — verify.
- **News** (`News.tsx`) — **invert the priority**: headlines first. CUT the machine block
  ("body read false / writes false / artifacts/... / missing artifacts / recovery") and
  the cryptic intel strip (FEEDS/ARTS/CLST/SRCS/SENT) or make it human words. Collapse the
  ~25-control filter row into a few clear filters (spell out NRG/CRPT/GEO/REL/WIRE). KEEP:
  the article list + a readable filter set.
- **Backtest** (`Backtest.tsx`) — CUT the "PROVIDER SOURCE / DATA READINESS" panels and the
  per-symbol cache readiness list (paths, ISO, true/false). KEEP: strategy catalog, run,
  and the results tables (format numbers; the `KeyValueTable` humanizes keys already).
- **Algo** (`Algo.tsx`) — CUT provider/broker/artifact readiness rows. KEEP: strategy
  builder form, my-strategies, scanner, run.
- **AI Chat** (`AiChat.tsx`) — CUT the CONTEXT CONTRACT / SESSION HEALTH / provider dumps
  (already de-emphasized; now remove). KEEP: sessions list, the chat transcript area, the
  composer, a minimal "local, dry-run" note.
- **Nodes / Code / Quant Lab / QuantLib** (`Nodes.tsx`, `Code.tsx`, `QuantLab.tsx`,
  `QuantLib.tsx`) — these are developer/quant tools; CUT provider/source/safety/library
  status panels and paths; KEEP the actual tool (canvas/editor/module runner) and its
  human inputs/outputs.
- **Forum** (`Forum.tsx`) — CUT artifact/kind/channel plumbing; KEEP posts + composer.
- **Settings** (in `workspaces.tsx`) — **the worst offender**: CUT the three big panels
  (PROVIDER SETUP, CACHE CONTROLS, GOVERNANCE DIAGNOSTICS — all operator config w/ raw
  keys + file paths). KEEP only the human block: Theme, Default Route, Refresh Seconds,
  Compact Mode, Save. (The AI configures providers/cache/governance via `/api`.)
- **Profile** (in `workspaces.tsx`) — CUT governance/usage-stats plumbing; KEEP display
  name + the human profile fields.
- **Help / Live Safety / Command Center** (`HelpCenter.tsx`, `LiveSafety.tsx`,
  `CommandCenterPanel.tsx`) — Command Center + most of Live Safety are operator/AI; keep
  Help human, and a minimal "live trading disabled" safety note; cut the rest.

## 6. Cadence & verification

- Work route by route. After each: `npm --prefix frontend run build` (must stay green),
  screenshot the route (chrome-devtools) to confirm it looks human + clean + 0 overflow,
  commit (narrative Lore-style message; end with `Co-Authored-By: Claude Opus 4.8
  <noreply@anthropic.com>`; commit to `main`, local self-use, no remote).
- At the end: rebuild dist, update `frontend/tests/m2-shell.spec.ts` to the new UI (or
  document the deltas), and do a final full-app screenshot pass.
- North star: open each route and ask "would a *person* want to look at this?" If any
  element is there for the AI operator, delete it.
