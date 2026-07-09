# M25 Redesign Spec

## ⚠️ v2 DIRECTION — Warm editorial ("ink & ember"). Supersedes the Apple-minimal v1 below.

Owner rejected v1 (Apple-minimal) as STILL machine-like AND clarified: **do not reduce
information**. Second research round (editorial-density + warm-humane) reframed it:
**warmth + density are not in tension — a broadsheet is extremely dense AND human.** The
v1 problem was COLD (blue-black + clinical blue + neutral sans + rounded cards = the
generic "AI/SaaS dashboard" tells). Fix = temperature + editorial craft + type voice, and
keep ALL data on the page (arranged editorially, not hidden in "Details").

### The reframe (quotable): "The enemy is not density; it is *undifferentiated* density."

### Tokens — Warm dark "ink & ember" (default theme)
```
--bg:#17130F  --s1:#1E1915  --s2:#262019  --s3:#2F2820      /* warm ink, R≥G≥B always */
--hair:#3A322A  --hair-2:#4A4038                            /* rules, not boxes */
--ink:#F2E9DC  --ink-2:#C4B7A6  --ink-3:#8A7E70             /* warm off-white text tiers */
--accent:#E0A458  --accent-deep:#C87A3F                     /* amber / terracotta — replaces cold blue */
--pos:#7FB069  --neg:#D9695A                                /* muted sage / clay, desaturated */
```
Paper light (day/reading mode, later): paper `#F5EFE3`, ink `#1F1A15`, accent copper `#B87333`.

### Type — a SERIF for voice (the single biggest de-machining move)
- serif (headlines, section titles, key metrics, editorial): real app = **Newsreader** or
  **Fraunces** self-hosted; mockup/fallback stack = `"Iowan Old Style", Charter, Georgia, "Times New Roman", serif` (pre-installed, genuinely editorial).
- sans (controls, labels): humanist system (`"Segoe UI", Inter, system-ui, sans-serif`).
- mono (ALL numeric data): `"IBM Plex Mono", "JetBrains Mono", ui-monospace` + `tabular-nums`.
- editorial scale: kicker 11 UPPERCASE/small-caps +0.08em accent · headline 22–24 serif 600 ·
  deck 14 italic muted · body 14 · data 13 mono tabular · caption/source 11 (~60% ink).

### Patterns (editorial density, from Tufte + FT/Economist/Businessweek)
- **Hairlines + whitespace instead of cards/shadows/fills** (kill chartjunk = kill boxes).
- **Kicker / deck / source line** furniture on every panel ("MARKETS · EQUITIES" kicker; a
  one-line deck; "Source: Binance, as of 22:28 UTC" footnote — strongest "authored" signal).
- **small-caps column headers** (`font-variant: small-caps`), not ALL-CAPS shouting.
- **tabular figures, decimal/right-aligned** numerics; **hairline rows** (not zebra-on-cards);
  compact 32–36px rows; sticky header + first column on wide tables.
- **in-cell sparklines + endpoint dot**; **small multiples** grid instead of one hero chart.
- charts: direct labeling > legends; emphasized endpoint; muted, one accent; horizontal
  gridlines only; plain-language left title + source line; annotation layer.
- **Economist signature:** 3–4px accent **top-left tab/rule** on each major panel.
- surgical accent (only the single most important number/state per view is amber).
- craft: faint paper-grain texture (data-URI, on ground only), letterpress-lite heading
  text-shadow, 2–4px radii (not 12–16), thin line icons, organic 150ms motion, human microcopy
  ("Markets are quiet" not "No data available").
- KEEP ALL INFO VISIBLE: provider statuses + supervision live in dense editorial side
  columns/lists, NOT behind a disclosure (reverses v1).

### v2 rollout: build warm-editorial mockup (Dashboard + Crypto, data-dense) → owner approves → refactor real app.

---

# (v1 — superseded) M25 Redesign Spec — Apple-minimal, human-first (research-backed)

Owner feedback (2026-07-06): the phase-2..5 restyle was "差不多的東西" — still
machine-first, too dense, aesthetics insufficient. Wants a GENUINE redesign:
Apple-style minimalism, drastically lower per-page density, human-readable.
This spec captures the research (Apple HIG + minimal-fintech agents) as concrete
tokens/patterns to build a mockup first, then refactor.

## Governing idea
Replace **visual density** with **informational density**. Keep the data; delete the
decoration. Every border, gradient, nested box, colored bar, and raw machine token
removed is a win. Chrome recedes (Deference); data floats on a calm surface.

## Design tokens (authoritative — from Apple HIG research)

### Type — SF/system stack, size+weight hierarchy (NOT color/borders)
```
--font-sans: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
--font-mono: "SF Mono", ui-monospace, "Cascadia Mono", Menlo, monospace;   /* numbers only */
font-variant-numeric: tabular-nums;   /* REQUIRED on all numeric columns */
```
Weights: 400 / 600 / 700 only. Scale (px @16 base, weight, line-height):
| token | px | weight | lh | use |
|---|---|---|---|---|
| display | 28 | 700 | 34 | page hero / big KPI |
| title | 22 | 700 | 28 | section header |
| title3 | 20 | 600 | 25 | card title / KPI value |
| headline | 15 | 600 | 20 | row title / emphasized |
| body | 15 | 400 | 20 | default |
| callout | 13 | 400 | 18 | secondary / meta |
| footnote | 12 | 400 | 16 | table cells |
| caption | 11 | 500 | 14 | labels (min readable floor) |
`letter-spacing: -0.01em` on display/title only. 11px is the hard floor (no 0.6rem).

### Spacing — 8pt system (4 as sub-step)
`--s1:4 --s2:8 --s3:12 --s4:16 --s5:24 --s6:32 --s7:48 --s8:64`
- card padding 16–24 · gap between cards 16 · between sections 32 · page gutters 24–32
- content max-width ~1280–1440 · text blocks ≤720 · table row height 32 or 40

### Color — layered near-black neutrals, ONE accent, semantic-only
```
--bg-base: #0B0B0C            /* app canvas (near-black, avoid pure #000 bloom) */
--surface-1: #1C1C1E          /* cards */
--surface-2: #2C2C2E          /* nested / hover / elevated */
--surface-3: #3A3A3C          /* popovers / modals */
--separator: rgba(84,84,88,0.60)      /* hairlines — use INSTEAD of boxes */
--text-primary: #FFFFFF
--text-secondary: rgba(235,235,245,0.60)
--text-tertiary: rgba(235,235,245,0.30)
--accent: #0A84FF             /* the ONE accent: primary action, active nav, focus, selection */
--gain: #30D158  --loss: #FF453A  --warn: #FF9F0A   /* meaning only, never tint surfaces */
```
Each elevation step ~+5–8% lightness conveys depth (no thick borders). Light mode is a
later concern; design dark-first but keep tokens swappable.

### Materials (sparingly)
Sticky top bar + popovers only: `background: rgba(28,28,30,0.72); backdrop-filter: blur(20px) saturate(180%)`.
Never blur the main content.

### Components
- radius: cards 10–12 · buttons/inputs 8 · pills 6/full
- prefer surface-contrast + soft shadow (`0 1px 3px rgba(0,0,0,.4)`) over borders; dividers = 1px hairline
- control heights: 36 standard / 28 compact / 44 large-primary; inputs 36 w/ 8–12 h-padding
- buttons: ONE filled accent primary per screen; others tinted-gray or plain text; destructive = loss
- toggles: iOS switch (51×31), on = gain/accent
- tables/lists: hairline row separators only (no vertical gridlines), right-align numerics + tabular-nums, 12–16 cell padding, full-row hover = surface-2

### Complexity reduction
- progressive disclosure ONE level ("Details/Advanced" expander) — never 3 deep
- summary-first → drill-down; lead each route with 3–5 KPIs, hide the rest
- one primary action per screen
- humanize: snake_case → Title Case labels; raw ID/path only on demand (tooltip/expander)
- remove redundant titles, duplicate borders, colored bars, icon clutter

## IA / layout (from fintech-dashboard research)

Information overload is the #1 dashboard failure (46.7% of users). Fix = **disclosed**
data, not less data. Master pattern: **summary-first → drill-down**.

- **5-second rule**: the primary answer of a view must be graspable in 5s. Cap visible
  elements ~7–8; target **3–5 key things per view**, not 30.
- **Hierarchy per route: Role → Metric → Density → Action.**
  - Hero: ONE dominant metric + delta (▲/▼ %), one line.
  - Secondary: 3–4 supporting stats, smaller/lighter, grouped.
  - Hidden: provenance, config, raw keys, IDs, source paths → behind Details (≤3 levels).
- **Status plumbing** (freshness, source, run status, paths) is reassurance, not a
  headline → small muted single line ("Updated 2 min ago · Binance"), or in Details.

### Uniform page skeleton (every route)
```
Header:   Human title + one-line context + primary action (right)
Metrics:  3–5 hero/secondary stat cards (one KPI row)
Content:  ONE focused block — the chart / table / list this page is about
Details:  collapsed "Raw data / system status" disclosure (all machine detail)
```

### Navigation
Persistent **left sidebar** (top tabs break past ~7 items). Group 15 routes into 3–4
labeled sections with whitespace between groups:
- **Markets** — Markets, Crypto, News
- **Portfolio** — Portfolio, Backtest, Algo
- **Research** — AI Chat, Quant Lab, QuantLib, Nodes, Code, Forum
- **System** — Dashboard(home), Settings, Profile
(final grouping TBD; keep every route's accessible name so e2e `getByRole(button,name)` still resolves.)

### Content sizing
Reading/analysis columns max-width ~1100–1200px, centered on wide monitors. Cards for
KPIs + heterogeneous summaries; **tables only** for comparing many rows across identical
columns (holdings, transactions), stripped to 5–8 essential columns; **lists** for
homogeneous items (news, alerts). Whitespace (2× intra-group) is the grouping device, not borders.

### Humanizer + formatters (global layer)
- labels: `snake_case`/`camelCase` → Title Case, strip trailing `_id`, `_` → space
  (`market_cap`→"Market Cap", `pnl_pct`→"P/L %"); small override map for domain terms
  (`ohlcv`, `ema`, `rsi`, `sofr`, `cftc`…).
- numbers: round hard, abbreviate ($1.2M), fixed decimals for prices, +/- + color on
  deltas, tabular-nums, thin-space thousands.
- dates: relative for recency ("3 min ago"), absolute on hover/detail.
- identity: friendly NAME as label; raw ID/path only on demand (tooltip / Details).

## Reconciled decisions (where the two briefs differ)
- **Base color**: soft near-black `#0E0F12` (not pure `#000`) for calm; card ladder
  `#17181B → #1F2024 → #292B30`. (Blend of Apple #1C1C1E and the "desaturated #141416".)
- **Separators**: low-contrast **1px hairline borders** as the primary divider
  (`rgba(255,255,255,.08)`); **soft shadows only** for floating layers (menus/modals).
- **Radius**: **10px** cards, **8px** controls (mid of 6–8 vs 10–12).
- Everything else the briefs agree on (type, 8pt spacing, one accent, semantic-only,
  tabular nums, progressive disclosure).

## Rollout plan
1. **Mockup first** — build a static self-contained HTML mockup (Artifact) of the new
   shell + Dashboard + Crypto in the new system, using REAL observed data. Owner reviews
   and approves the direction before any app refactor.
2. **Foundation** — once approved, rewrite theme.css tokens to this spec; add a shared
   `humanize.ts` (labels + number/date formatters) and shared primitives (StatCard,
   Section, Details disclosure, Sidebar).
3. **Shell** — convert nav to grouped left sidebar; apply the page skeleton wrapper.
4. **Route-by-route** — reshape each route to skeleton (hero → KPIs → one block →
   Details), moving machine detail into Details. Keep e2e/MCP DOM contract (raw tokens
   stay reachable, just relocated/humanized-with-raw-on-demand). Screenshot-verify each.
5. **Verify** — frontend build + full `pytest` + spot e2e; adjust e2e only if the owner
   accepts DOM changes (some deep restructures may require updating the text-coupled e2e).

Risk note: a true redesign (sidebar regroup, moving raw tokens into Details) will likely
break parts of the text-coupled Playwright e2e (`m2-shell.spec.ts`) even though pytest
(401) stays green. Decide with owner: update the e2e to match the new UX (recommended) vs
constrain the redesign to keep every asserted string inline (limits the density win).

**Sources:** Apple HIG (design-principles, foundations, typography, dark-mode, materials, SF Pro), iOS dark system hex (Sarunw), 8pt grid, NN/g progressive disclosure.
