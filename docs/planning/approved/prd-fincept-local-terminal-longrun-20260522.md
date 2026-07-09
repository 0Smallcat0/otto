# PRD: Fincept Local Terminal Longrun

Status: Approved by RALPLAN Critic.

## Decision

Build a clean-room local self-use Fincept Terminal functional/workflow parity application in `D:\FinceptLocalTerminal`, using `AGENTS.md` as the highest project contract.

This is not a fork, clone of source code, branding copy, or continuation of `D:\Crypto-Trading`.

## Source Authority

1. `AGENTS.md`
2. This PRD, the paired test spec, and the execution plan under `docs/planning/approved/`
3. Raw `docs/reference/` evidence, screenshots, UI logs, and safe live Fincept UI observations
4. Older planning/spec docs only when they do not conflict with the first three

If raw observation evidence conflicts with this PRD, pause the affected implementation slice and patch the PRD/test spec or create a clarifying planning note before implementing. Do not silently override observed behavior.

## Product Goal

Create a local terminal for personal financial research, public market-data exploration, crypto paper trading, portfolio inspection, backtesting, and local research tooling. It should approximate Fincept's observed workflow, density, hierarchy, menu structure, and route layout while replacing branding, commercial copy, cloud/subscription requirements, and unsafe execution paths with local equivalents.

## Required Routes

The application must expose these 15 entries:

- Dashboard
- Markets
- Crypto
- Portfolio
- News
- AI Chat
- Backtest
- Algo
- Nodes
- Code
- Quant Lab
- QuantLib
- Forum
- Settings
- Profile

Each route must have either a working first-use state or an explicit local disabled/gated state with evidence-backed controls, local safety rationale, and a link to its future milestone.

## Required Global Menus

- File: local layout/window/file actions and refresh.
- Navigate: route groups and observed workspace groupings.
- View: component browser, focus/fullscreen, float panel, quick switch, screenshot.
- Help: local docs, diagnostics, about, local profile lock/switch, update placeholder.

## Must-Have Workspace Behavior

- Dashboard reads local/public/paper state, data freshness, alerts, widget catalog, layout save/reset.
- Markets uses public read-only crypto data where available, panel add/edit/delete, column chooser, cache/freshness/offline state.
- Crypto supports public market data, paper-only order ticket, paper ledger, positions, orders, fills/history, fees, depth/market/stats views.
- Backtest runs at least one local closed-candle strategy and writes reproducible artifacts.
- Portfolio supports create/import/demo/export and links to paper/backtest artifacts.
- News, AI Chat, Algo, Nodes, Code, Quant Lab, QuantLib, Forum, Settings, and Profile expose useful local/dry-run/read-only or disabled-gated equivalents.

## Clean-Room Scope

Allowed:

- Existing repo evidence under `docs/reference/`.
- Safe live UI behavior observation through the installed app.
- Public documentation for high-level product or stack context.
- Independent implementation, independent naming, local copy, and local assets.

Forbidden:

- Reading, copying, porting, adapting, or importing `D:\FinceptTerminal\app\scripts`.
- Reading/copying/adapting installed package implementation source, runtime binaries, or assets.
- Fincept logo, branding, trademarks, commercial claims, subscription copy, CR/billing mechanics.
- `D:\Crypto-Trading` roadmap or goals.
- Reachable real order, private API key, real balance read, margin, leverage, short exposure, or derivatives execution before the live safety contract is approved.

## Live Trading Parity

Live trading parity is a long-term parity target, not an MVP implementation path. Before any live path becomes reachable, a separate safety PRD/test spec must exist and pass review. It must include local secret storage, explicit opt-in, confirmations, audit logs, kill switch behavior, static reachability checks, paper/live isolation tests, and security review.

## Data Policy

Runtime user-visible data should prefer public read-only sources. Deterministic fixtures, cached data, and sample data are allowed for tests, reproducible CI, and offline fallback only; stale/offline state must be visible to the user.

## Visual Policy

Visual parity means semantic terminal layout/workflow/category parity, not pixel-perfect copying. Visual checks must ignore or replace exact Fincept branding, commercial copy, logo, icon identity, color identity, and assets.

Screenshots committed or referenced as deliverable evidence must redact account/email/CR regions and remove or inspect metadata for secrets or personal information.

## Technology Decision

Do not hard-lock web versus native until M1. M1 must produce a stack ADR with a scored table covering delivery speed, semantic UI/workflow parity, local runtime ergonomics, testability, packaging, offline/local storage, browser/playwright compatibility, and maintainability.

Default assumption if no stronger evidence emerges: Python backend plus React/TypeScript/Vite frontend.

## Acceptance Criteria

- All 15 routes open and show working or explicitly gated first-use states.
- File/Navigate/View/Help menus work.
- Dashboard, Markets, Crypto paper, Backtest, Portfolio, Settings, and Profile have useful local functionality.
- Public read-only data works where network is available; tests/offline use deterministic fixtures/cache.
- Paper broker cannot submit real orders and enforces ledger safety invariants.
- Backtest outputs reproducible local artifacts.
- Optional tools cannot bypass safety gates.
- Clean-room static checks pass.
- No secrets or personal account details are persisted.
- Every milestone ends with tests, UI/artifact evidence, code review, handoff update, and one Lore commit.

## ADR

Decision: choose contract-locked shell plus high-value workspaces incrementally.

Drivers:

- Keep clean-room and legal boundaries explicit.
- Deliver terminal workflow parity without empty pages.
- Preserve autonomous `/goal` execution quality through concrete DoD and verification.

Alternatives considered:

- Broad visual shell first: faster visual feedback, but high hollow-page and unsafe-control risk.
- Domain engines first: strong business logic, but delays terminal-shape parity.
- Reuse `D:\Crypto-Trading`: rejected as explicitly forbidden contamination.

Consequences:

- Slower full breadth than a pure shell clone.
- Higher confidence that each route's first useful state is real.
- Live parity remains gated by safety contract.

Follow-ups:

- M0 stale-doc correction.
- M1 stack ADR.
- M10 live safety PRD/test spec before live implementation.
