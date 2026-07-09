# AGENTS.md

> **Product name: Otto** (renamed 2026-07-08 from "Fincept Local Terminal"). The vision
> is an *effortless*, AI-operated local finance terminal — the user just gives commands.
> The "Fincept" references below are the clean-room **heritage and boundary** (the original
> product that was observed, never copied); they are intentionally kept, not the product name.

## Purpose

This repository is a clean-room local rebuild of Fincept Terminal for local self-use. The governing product goal is functional and workflow parity with the observed Fincept Terminal experience while avoiding Fincept branding, assets, commercial copy, runtime binaries, and implementation-source copying. The source of truth is the research evidence under `docs/reference/`, direct observation of the installed app's behavior, and this file; it is not another project roadmap.

## Non-Negotiable Boundary

- Do not implement or reference `D:\Crypto-Trading` goals unless the user explicitly asks.
- Do not treat `FINCEPT_TO_CRYPTO_TRADING_HANDOFF.md` as this repo's roadmap.
- Do not copy Fincept branding, logo, trademarks, commercial copy, subscription mechanics, CR/credits, billing flows, or installer/runtime binaries.
- Do not read, copy, port, or adapt implementation source from `D:\FinceptTerminal\app\scripts` or any installed Fincept package source into executable paths. Use observed UI behavior, screenshots, JSON logs, public documentation, and independent implementation.
- Live trading parity is in scope only through independently implemented, explicitly planned local modules. No live order path, private API key flow, real balance read, margin, leverage, short exposure, or derivatives execution may be reachable until a dedicated safety contract exists with local secret storage, explicit live-mode opt-in, confirmation gates, audit logs, kill switch behavior, and tests proving paper/live isolation.
- Keep all user data, layouts, logs, reports, backtests, screenshots, and settings local by default.

## Working Rules

- Prefer small, reviewable changes.
- Keep implementation aligned with `docs/planning/PRE_IMPLEMENTATION.md` unless it conflicts with this AGENTS.md. When older planning documents conflict with the local Fincept parity objective, update the stale document before using it as an implementation contract.
- Use `docs/reference/fincept-platform-test/LOCAL_TERMINAL_PRODUCT_SPEC.md` and `LOCAL_TERMINAL_ENGINEERING_SPEC.md` as the main product/engineering references.
- Use screenshots and JSON logs as evidence for UI behavior, not as assets to copy.
- When adding code, add tests for domain rules and local storage contracts before claiming completion.

## CodeGraph

- This repo has been initialized with CodeGraph (`.codegraph/`) for read-only semantic code lookup.
- For architecture exploration, symbol discovery, caller/callee tracing, call-flow analysis, and impact analysis, prefer CodeGraph MCP tools first: `codegraph_search`, `codegraph_context`, `codegraph_callers`, `codegraph_callees`, `codegraph_impact`, `codegraph_files`, and `codegraph_status`.
- Do not start those exploration tasks with broad full-repo grep/read when CodeGraph is available and current.
- Read concrete source files only after CodeGraph has narrowed the target area, or when preparing to modify or verify specific files.
- If the CodeGraph MCP tools are unavailable, stale, incomplete, or not loaded in the current session, run `codegraph sync` or `codegraph index` from `D:\FinceptLocalTerminal`, then fall back to `rg` for anything still missing.
- Treat CodeGraph as an index over this clean-room repo only. Do not use it to inspect, copy, or adapt implementation source from `D:\FinceptTerminal\app\scripts` or installed Fincept package source.

## Initial Architecture Intent

The first usable version should expose the terminal shape before deep feature execution:

1. shell/navigation
2. global menus
3. local settings/profile/layouts
4. dashboard with public/local state, using deterministic fixtures only for tests and offline fallback
5. markets/watchlist backed by public read-only data where available
6. crypto workspace with public market data, paper runtime first, and live-mode surfaces only after the dedicated safety contract exists
7. portfolio local workspace
8. backtest artifact workspace

Optional tools such as AI Chat, Nodes execution, Code execution, Quant Lab execution, and QuantLib computation should remain local, dry-run, or disabled until their safety contracts exist.

## 後續 AI 執勤守則(2026-07-08 追加;為較弱模型而寫,違反=停手)

1. **動工前必讀**:`docs/planning/M27_AI_FIRST_UI_PLAN.md`(現況與進度表)+ memory 索引。不重新發明方向。
2. **小步走**:一次一個 slice;改完 → `npm --prefix frontend run build` + `npx playwright test` + 目標 pytest 檔;commit 前跑全量 pytest。**驗證鏈禁止用 pipe 遮蔽退出碼**(`cmd | tail` 會吞失敗;用 `cmd && echo OK`)。
3. **零破壞原則**:不刪除/重寫你不理解的檔案;baseline 讀不到 ⇒ 什麼都不刪;含 delete/reset 的動作不進自動批次。
4. **壞了先還原**:17 個狀態檔各有 `.json.bak1..3` 三層備份;`git log` 每步可回。修不動就回滾,不要硬改。
5. **改後端必重啟** `:8765`(不會自動 reload);改前端必 rebuild。跨午夜改 Python 後若行為詭異,先清 `__pycache__`。
6. **護欄是朋友**:445+ pytest、真值測試(contract=實地)、清潔室之牆(品牌/秘密掃描)會擋住錯誤——測試紅了是在救你,不要繞過或刪測試。
7. **錢的數字**:一律用手上最新收盤;來源與資料日必須標示;對不上 owner 的券商 APP 時先對口徑(毛/淨、費用、資料日),不要亂改資料。
