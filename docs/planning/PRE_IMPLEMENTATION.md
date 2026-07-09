# Pre-Implementation Preparation

## Project Objective

Build a local, clean-room terminal from the Fincept research evidence in this repository.

This is not a continuation of any other trading-system roadmap. The active source material is the copied Fincept platform research package.

`AGENTS.md` is the controlling project contract. If this preparation document conflicts
with `AGENTS.md` or the approved artifacts under `docs/planning/approved/`, update this
document before using it as an implementation contract.

## Active References

- `docs/reference/fincept-platform-test/PLATFORM_RESEARCH_COMPLETION_AUDIT.md`
- `docs/reference/fincept-platform-test/COVERAGE_AUDIT.md`
- `docs/reference/fincept-platform-test/FUNCTION_INVENTORY.md`
- `docs/reference/fincept-platform-test/FEATURE_MATRIX.md`
- `docs/reference/fincept-platform-test/GLOBAL_MENU_AUDIT.md`
- `docs/reference/fincept-platform-test/LOCAL_TERMINAL_PRODUCT_SPEC.md`
- `docs/reference/fincept-platform-test/LOCAL_TERMINAL_ENGINEERING_SPEC.md`
- `docs/reference/fincept-platform-test/LOCAL_VERSION_IMPLEMENTATION_BACKLOG.md`
- `docs/reference/fincept-platform-test/evidence/`
- `docs/reference/fincept-platform-test/screenshots/`
- `docs/reference/root-captures/`

## Inactive Historical Reference

- `docs/reference/fincept-platform-test/FINCEPT_TO_CRYPTO_TRADING_HANDOFF.md`

This file belongs to a previous cross-project mapping. It is retained only so the copied research package remains complete. It must not be used as this project's roadmap.

## Clean-Room Rules

- Use observed behavior, screenshots, inventories, and JSON evidence as requirements.
- Do not copy Fincept executable/runtime binaries into implementation paths.
- Do not copy Fincept branding assets into implementation paths.
- Do not read, copy, port, or adapt installed Fincept implementation source into executable paths.
- Replace subscription, CR, billing, and cloud account behavior with local settings, local usage, and local artifacts.
- Prefer public read-only runtime data where available. Deterministic fixtures/cache are
  allowed for tests and offline fallback only.
- Live trading parity is allowed only after a dedicated safety contract, local secret
  storage design, explicit opt-in, confirmation gates, audit logs, kill switch behavior,
  and paper/live isolation tests exist.

## MVP Entry Set

The shell should expose these entries:

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

The global menu should expose:

- File
- Navigate
- View
- Help

## First Build Slice

Build the product shell and local persistence first:

1. Shell navigation with all 15 entries.
2. File / Navigate / View / Help menu structure.
3. Local profile and settings files.
4. Workspace layout save/load.
5. Dashboard with public/local state and deterministic fixtures only for tests/offline fallback.
6. Markets watchlist with public read-only data where available.
7. Crypto workspace shell with public market data and paper runtime first.
8. Portfolio local demo/import/export shell.
9. Backtest workspace with local result artifacts.

## Done For Preparation

- New repo folder exists.
- Research evidence is copied into `docs/reference/`.
- Active/inactive references are separated.
- Clean-room boundaries are documented.
- Python project scaffold exists.
- Local virtual environment can run the placeholder tests.

## Phase 0 Implementation Acceptance Criteria

- The shell exposes exactly the 15 main local terminal routes listed in the MVP entry set.
- File, Navigate, View, and Help menu contracts exist before UI implementation begins.
- Settings, workspace layouts, and artifacts resolve to repo-local paths by default.
- Local profile setup does not require cloud account, billing, subscription, CR, or credits.
- Safety flags keep reachable real orders, private exchange API requirements, real balance
  reads, margin, leverage, short exposure, and derivatives live execution disabled until a
  dedicated safety contract exists.
- Contract tests cover the route set, menu minimums, local profile policy, safety flags, and
  storage path locality.

## Phase 0 Non-Goals

- No full product UI, dashboard widgets, trading screens, or visual clone work.
- No Fincept branding, logo, commercial copy, subscription, billing, CR, or runtime binaries.
- No reachable live broker integration, private API key flow, real balances, margin,
  leverage, short exposure, derivatives live execution, or real order submission until a
  dedicated live safety contract is approved.
- No cloud persistence; settings, layouts, logs, screenshots, reports, and backtest artifacts
  remain local by default.
