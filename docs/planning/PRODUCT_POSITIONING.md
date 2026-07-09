# Product Positioning — 為什麼有人要用這個終端

*Researched 2026-07-07 against the live market (sources at bottom). This document
drives priority: every roadmap item should serve one of the four selling points.*

## 一句話定位

**你的 AI 的交易沙盒** — the agent-native local terminal: a free, private, paper-only
trading desk that an AI operates end-to-end on your machine, so you can watch what
your agent would do with real market data and zero risk.

## 使用者是誰,痛在哪(真實世界驗證)

| 痛點 | 現實證據 | 我們的答案 |
|---|---|---|
| 專業終端貴到離譜 | Bloomberg 2026 = **$31,980/年**,無個人版,兩年約;Koyfin 等替代品的存在理由就是這個價格 | $0、本地、無帳號 |
| 訂閱陷阱與資料收費牆 | TradingView 免費/低階全是延遲資料,即時行情按交易所加購 $2–25+/月;自動續訂投訴成災 | 無訂閱、無升級推銷;公開資料 + 誠實的新鮮度標示 |
| 開源終端死了 | OpenBB Terminal 已停維護(7–10k 月活撐不起 500+ 依賴);Workspace 轉雲端,免費層 Copilot 限 20 次/日,on-prem 是企業功能 | 本地優先是預設而非企業加購;AI 不限次數(你自帶 Claude/Codex) |
| 2026 的 AI 交易熱潮直連真錢 | Robinhood「open to agents」(2026-05)、Webull/eToro/IG/TradeStation/Alpaca 全在出 broker MCP;FINRA 2026 監管報告點名 AI 代理治理風險 | **先在沙盒練**:同樣的 agent-操作介面(contract + preflight + MCP),但紙上、kill-switch、全程來源可稽核 |
| 回測工具讓人自欺 | 研究:Sharpe 對樣本外表現幾乎無預測力(R²<0.025);AQR 案例 in-sample 1.2 → OOS −0.2;過擬合是散戶量化第一大坑 | 防前視引擎 + walk-forward 內建 + **過擬合紅旗自動警示**(見 roadmap) |
| 不想把持倉餵給雲端 AI | 雲端 AI 資料保留政策反覆變更;GLBA/FTC Safeguards 下非公開財務資訊本就不該過外部 API;local-first 理財工具(Actual Budget 等)明顯增長 | 資料、artifacts、歷史全在 repo 資料夾;唯一外連是抓公開行情 |

## 四個賣點(優先序)

1. **AI 原生** — 不是「有 AI 功能」,而是整個系統為 AI 操作而設計:agent contract
   宣告每個動作的請求格式/安全等級/錯誤目錄,preflight 先問再做,MCP server 開箱即用。
   跟 2026 券商 MCP 浪潮講同一種語言,但這裡是安全的練習場。
2. **零成本零風險** — 免費、紙上、kill-switch 鎖死真錢路徑。學習、實驗、演練策略
   的地方,不是下真單的地方。
3. **誠實研究** — closed-candle 防前視、fill-next-open、walk-forward、來源血統
   (每個報價知道自己從哪來、多舊)、過擬合警示。散戶工具少見的研究紀律。
4. **完全本地** — 你的持倉、策略、對話不出這台機器。

## 反定位(我們不是什麼)

- 不是即時行情終端(公開資料有延遲,但我們誠實標示——對手藏在收費牆後)。
- 不是券商、不下真單(那是 Robinhood/Alpaca MCP 的地盤;我們是它們的前一站)。
- 不是雲端 SaaS(OpenBB Workspace 已佔那格)。

## 據此排序的產品缺口(2026-07-07)

1. **回測可信度包**:Sharpe/Sortino/勝率/獲利因子/曝險 + 過擬合紅旗
   (PF、Sharpe、交易數閾值自動警示)——賣點 3 的直接兌現。
2. **coverage matrix 補 crypto lane**——lineage 稽核鏈的最後一塊(賣點 3)。
3. **投組刪除/整理**——沙盒要能重來(賣點 2)。
4. **無金鑰股票報價開箱即用**(Stooq 公開快照餵 Markets/stocks 預設 watchlist)——
   降低第一次打開的「空」感(賣點 2 的體驗面)。
5. Help/歡迎卡措辭對齊「AI 的交易沙盒」定位。

## Sources

- [Bloomberg Terminal Cost 2026](https://godeldiscount.com/blog/bloomberg-terminal-cost-2026) — $31,980/yr, no retail tier
- [Koyfin: Best Bloomberg Alternatives](https://www.koyfin.com/blog/best-bloomberg-terminal-alternatives/) — founded on the cost pain
- [TradingView Real Cost Breakdown 2026](https://impactwealth.org/how-much-does-tradingview-really-cost-full-pricing-breakdown-2026/) — data add-ons + renewal complaints
- [OpenBB: Sunsetting the Terminal](https://openbb.co/blog/sunsetting-openbb-terminal-why-how-and-what-now/) — open-source terminal maintenance collapse
- [OpenBB Pricing](https://openbb.co/pricing/) — Copilot 20 queries/day on free tier; on-prem = enterprise
- [Brokers race to open trading infra to AI agents via MCP](https://www.leaprate.com/technology/broker-mcp-ai-agent-trading-infrastructure-race-2026) — Webull/Deriv/IG/ThinkMarkets/eToro in a fortnight
- [Robinhood opens to AI agents (May 2026)](https://theplanettools.ai/blog/robinhood-agentic-trading-credit-card-mcp-may-2026) — incl. FINRA 2026 oversight flag
- [Alpaca MCP Server](https://alpaca.markets/mcp-server), [TradeStation MCP](https://www.tradestation.com/platforms-and-tools/mcp/)
- [Backtest overfitting in the ML era (ScienceDirect)](https://www.sciencedirect.com/science/article/abs/pii/S0950705124011110) — Sharpe R²<0.025 OOS
- [Dangers of Backtesting (Portfolio Optimization book)](https://portfoliooptimizationbook.com/book/8.3-dangers-backtesting.html) — AQR 1.2→−0.2 example
- [Stoic: Backtesting metrics guide](https://stoic.ai/blog/backtesting-trading-strategies/) — red-flag thresholds (Sharpe>3, PF>2 suspicious)
- [MindStudio: Local AI vs Cloud AI 2026](https://www.mindstudio.ai/blog/local-ai-vs-cloud-ai-2026), [Prediction Guard: self-hosted AI in regulated industries](https://predictionguard.com/blog/best-self-hosted-ai-models-regulated-industries) — GLBA/FTC Safeguards
- [Decrypt: AI tools that respect privacy](https://decrypt.co/359454/best-ai-tools-respect-privacy)
