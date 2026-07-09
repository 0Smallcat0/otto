# M27 — AI-First UI 重建:施工計畫

Status: **S1–S5 + R2 + R3 + R4 + 深用修正 全部完成(2026-07-07,445 pytest + 6 e2e 全綠,contract 113 動作)— 待 owner 驗收**;S6 日曆選配;R5 起點=FRED 撤出任務牆(1524645)
上游:`M27_AI_FIRST_UI_BRIEF.md`(方向決策)+ `artifacts/ui-review/m27/mockup-v2.html`(視覺定案)
協定:同 M26 —— 本文件=唯一進度源;每 slice 一 commit 並同步勾 §5;恢復=讀本文件+`git log -15`。

## 0. Owner 驗收基準(v2 mockup 六點回饋已消化)

高密度報價表(分組)、單一 AI 動態流(產出行內卡,不重複)、無信任面板(頂條一行)、
所有產出卡可開、去 AI 感美學(直角/單一琥珀強調/細線分欄/等寬數字)、
帳本橫幅置頂(FreqUI 慣例)+ 總經日曆(Bloomberg 慣例)+ AI 用量統計行。

## 1. 架構策略(重要,勿偏離)

- **保留 15 個 hash 路由殼**:route_id/path/`workspace-*` testid/heading 與 `agent_contract.py ROUTE_CONTRACTS` 一致 —— 後端 contract/selectors 層零改動,428 pytest 不受影響。
- **路由內容全部重蓋**:舊 workspace 元件(26,475 行)最終全刪;新內容=任務牆+讀者頁。
- 前端結構現況:hash 路由(`#/route_id`)、`main.tsx` App 殼、`workspaces.tsx` 分發、
  `shellData.ts` fallback 路由表(15 路由)、`AI_OPERATOR_ROUTES` 已隱藏 6 路由。
- e2e 只有一檔 `frontend/tests/m2-shell.spec.ts` —— 隨新 UI 重寫。
- 後端 `:8765` 服 dist;`npm --prefix frontend run build` 後要重啟後端驗證。

## 2. 資料接線表(任務牆各區 → 現有 API,除日曆外零新後端)

| 區塊 | 來源 |
|---|---|
| 頂條:實盤/外部執行閘門 | `/api/agent-contract` `safety` 或 governance payload |
| 頂條:備份 | `GET /api/local-state/backups`(M26 S0.2) |
| 頂條:KEYS n/8 | `GET /api/local-secrets/status` |
| 帳本橫幅:權益/今日損益/未實現/持倉/今日交易 | `/api/crypto`(paper `account`/`positions`/`orders`/`history`) |
| 報價監視:加密 | `/api/markets` cache rows(Binance 公開) |
| 報價監視:美股(Finnhub)/FX(TwelveData) | `research_summary.finnhub_quotes` / `.twelve_data_quotes` |
| 報價監視:台股 | `research_summary.twse_quotes` |
| 報價監視:利率/總經 | `research_summary.fred_macro` + treasury rates |
| AI 動態流 | `GET /api/agent-activity`(journal:action_id/state/summary/artifact_path/時間) |
| 今日統計行 | journal 客端聚合(N 動作/✓/⚠;per-key 呼叫數後端未記錄→先不顯示) |
| 頭條 | `/api/news` rows;★=客端以 news layout `watch_terms` 關鍵字比對 |
| 回測讀者 | `/api/backtest`(latest run:metrics/trades/equity_curve/artifacts)+ run index |
| 新聞簡報讀者 | `/api/news` research_brief / brief index |
| 總經日曆 | **缺資料源** → S6 用 FRED releases/dates(同 fred key);S2-S5 期間顯示「下次 FRED 刷新對象」替代或留空 |

## 3. 新前端檔案規劃

- `src/ui/tokens.css` — v2 設計系統(直角、琥珀 #d9a441、細線 #1b212b、mono 數字)
- `src/ui/App.tsx`(取代 main.tsx 內容)— 頂條+警示行+路由分發(15 路由,保 testid/heading)
- `src/ui/api.ts` — fetchJson + 各 payload hooks(輪詢 data_refresh_seconds)
- `src/ui/wall/` — `Wall.tsx`(=dashboard 路由)、`EquityBanner.tsx`、`QuoteMonitor.tsx`、`ActivityFeed.tsx`、`Headlines.tsx`、`CalendarStub.tsx`
- `src/ui/readers/` — `BacktestReport.tsx`、`NewsBrief.tsx`、`ArtifactDoc.tsx`(通用)
- `src/ui/routes/` — 各路由頁(見 S4 清單)
- 保留:`types.ts`(S4 才修剪)、`humanize.ts`;刪除(S4):舊 components/*、styles.css、terminal-components.css(theme.css 併入 tokens)

## 4. 路由頁內容(S4;全部唯讀,零表單零操作鈕)

dashboard=任務牆 | markets=報價總表(全組全欄)| crypto=paper 帳本+成交/掛單紀錄 |
portfolio=帳本清單+active 明細 | news=頭條全列+簡報列表→讀者 | backtest=run index→報告讀者 |
algo=策略庫+最新 scan/backtest 產出 | settings=系統狀態(閘門/備份/keys/providers)|
profile=顯示偏好(唯一可寫:主題切換)| forum=筆記列表讀者 | help=說明 |
ai_chat/nodes/code/quant_lab/quantlib=AI 操作紀錄+最新 artifact 讀者(隱藏於側欄,同現行 AI_OPERATOR_ROUTES)

## 5. Slices 與進度

| Slice | 內容 | 狀態 | Commit | 驗證 |
|---|---|---|---|---|
| S1 | 施工計畫(本文件) | ☑ 完成 2026-07-07 | `Draw up the teardown before swinging the hammer` | — |
| S2 | tokens+App 殼+任務牆全資料接線+e2e 最小改寫 | ☑ 完成 2026-07-07 | `Raise the mission wall on live data` | build 綠;e2e 6/6 新 spec;:8765 實機真資料截圖 s2-real-wall.png |
| S3 | 細讀模式:回測+簡報讀者(含 2 個新唯讀 detail 端點,contract 106 動作) | ☑ 完成 2026-07-07 | `Let a person open what the AI finished` | 4 新後端測試;真值測試涵蓋 2 新動作;e2e 6/6;實機真報告截圖 s3-real-report.png |
| S4 | 15 路由頁重建+舊件全刪(26,475 行→6 檔) | ☑ 完成 2026-07-07 | `Tear out the cockpit, keep the view` | build+e2e 6/6 綠;實機 crypto 頁截圖;順手清掉體檢遺留掛單 |
| S5 | 全閘門+主題測試改寫+清潔室品牌修正 | ☑ 完成 2026-07-07 | `Pass the wall wearing our own name` | 432 pytest+6 e2e+lint+build 全綠;品牌改 LOCAL TERMINAL(清潔室之牆攔截);截圖包 s2/s3/s4/s5-*.png |
| S6(選) | FRED 總經日曆(後端 releases/dates+接線) | ☐ | — | 驗收後與 owner 確認要不要 |

## R2 — Owner 首輪驗收回饋(2026-07-07,七點)+ dogfood 修訂

Owner 原話重點:15 檔要能跟 AI 說改就改;新聞要系統語言(中文);UI 要能切中英;
Markets 每檔要能展開詳情(參考業界做法);Crypto 頁與 Crypto 關聯不明;
所有列表都要能互動看細節(news 至少要總結);Settings 存在意義不明;
**「你實際帶入使用者身份用一次就知道問題在哪」——深度使用、找出問題、全部修完再驗收。**

| Slice | 內容 | 狀態 | Commit | 驗證 |
|---|---|---|---|---|
| R2.1 | i18n(zh/en,localStorage)+ 頭條開原文連結 | ☑ 2026-07-07 | `Speak both languages and link every headline` | e2e 6/6 |
| R2.2 | watchlist 可變(state+備份+action+refresh 預設+牆渲染) | ☑ 2026-07-07 | `Let the watchlist obey the conversation` | 4 測試;dogfood:加 TSLA→真 key 刷出 419.77 |
| R2.3 | 全列可展開詳情 + Crypto 頁重構(市場+紙上帳本)+ Settings=系統狀態頁 | ☑ 2026-07-07 | `Open every row the user asked to open` | e2e 6/6;實機展開截圖 |
| R2.4 | 新聞中文管道(digest state+action+UI 併示) | ☑ 2026-07-07 | `Give the operator a pen for headlines…` | 3 測試;operator 實寫 12 條中文摘要上牆 |
| R2.5 | portfolio book 詳情端點 + UI 展開 | ☑ 2026-07-07 | (同 R2.4 commit) | truth test 涵蓋;book 展開持倉/交易 |
| R2.6 | dogfood 修 friction:讀取路徑寫死清單→改讀 watchlist;crypto cache 部分失敗被整檔覆寫→改 symbol 合併;M25 legacy panel 過濾 rows→watchlist 同步;詳情欄白名單防溢出 | ☑ 2026-07-07 | `Fix what only a real user would trip on` | 目標測試 17 綠;全量+e2e 見下 |

## R3 — Owner 二輪回饋(2026-07-07,九點)

1 原始小數未格式化(61876.00000000)→ 全域智慧格式化;2 Markets 展開要有圖 → crypto=真 K 線(detail cache+新唯讀端點),其餘=日內區間條;3 FRED 難懂 → 中文名+白話數值;4 Crypto 同 2+委託紀錄來源說明;5 Portfolio 難懂 → 來源中文徽章+頁首解釋;6 News 移除簡報區(讀者仍可從動態流開),保留中文摘要;7 Backtest 來源不明 → 頁首解釋+時間欄;8 Settings 重整=偏好+四行系統摘要(參考同類專案);9 Profile 併入偏好區(路由保留)。+ 第三輪 dogfood。

**R3 完成(2026-07-07)**:contract 109 動作(+markets_candles_read);九點全修;實機截圖 r3-markets-charts.png(BTC 60 根真 K 線)、r3-settings.png。R3 誠實註記:美股/台股/FX 無本地歷史 K 線(僅日內區間條——要歷史圖得先建每日快照累積,另立);Settings「資料源 0 即時」是靜置時的誠實狀態(快取制,刷新當下才 live)。

## R4 — Owner 三輪回饋(2026-07-07,九點)

1 動態流機器文字 → 補全動詞表+通用人話 fallback+操作日誌改中文;2 數字未對齊 → tabular-nums+表頭對齊+hover;3 每標的要圖+要申請哪些 API → **答案:不用新 key**,Twelve Data(已存)time_series 拉 US/FX 日線 → 新 history 快取+refresh action,candles 端點 fallback,圖全面點亮;TW 日線=TWSE 免鑰(下輪);4 中文摘要只兩條(item_id 隨 feed 輪替而失配)→ digest 加「分類速覽 sections」(對整份 feed 穩定)+operator 重寫本日 digest;5 Algo 頁加白話用法;6 Settings 列出可改項+例句;7 Profile 移出側欄(路由保留);8 功能可見性 → 側欄「AI 能做什麼」能力目錄(讀 agent-contract 動態生成);9 美感 polish(對齊/hover/節奏)。

**R4 完成(2026-07-07)**:contract 110 動作(+markets_history_refresh);TSLA 等 6 檔真日線實測上牆(r4-tsla-history.png);digest sections 對 feed 輪替免疫;能力目錄=contract 即目錄(第 8 點的解:功能清單自動與實作同步,人用瀏覽的、AI 用執行的,同一份)。誠實註記:TW 歷史日線未接(TWSE 免鑰可做,另立);EN 模式下例句仍以中文思維直譯。

## R5 — 自驅深用輪(2026-07-07,owner 令 AI 自己找)

以「早上打開終端機的人」心智流程走查,抓到並修掉(commits 2d0308e+efa2de0):
①能力目錄改「可以照唸的 26 句話」(點擊複製),113 動作收進技術明細摺疊;②**信任級:報價全是快取但畫面不標時間** → 每組掛「N分/小時前」年齡戳,>1h 轉琥珀;③crypto 快取 >5min 自動靜默刷新(免鑰 Binance,localStorage 節流防多分頁踩踏);④側欄改中文(任務牆/行情/…,title 保英文原名);⑤動態流跨日事件補日期;⑥頭條「508m」→「8小時前」人性化;⑦速覽掛更新時間;⑧持倉「今日交易」改按標的計數。
未修候選(下輪):行情帶大字報價區(mockup 有、實作無)、活動流 running 狀態的預估時間、Backtest 索引補策略欄。

**R2 已知未修(誠實清單):** 新聞來源偶有壞 unicode 代理字元(前端渲染安全,僅影響原始 console 輸出);crypto 監看仍限 BTC/ETH/SOL(provider 對映擴充另立);K 線圖未做(詳情展開先以欄位格呈現)。

閘門:每 slice `npm --prefix frontend run build` 綠 + e2e 綠(S2 起用新 spec);S5 加全量 pytest(428 基線)+ `:8765` 實機截圖。

## 6. 風險備忘

- `sessionStorage autoload` 行為保留(避免每次載入打外部 API)。
- 舊 css 在 S4 前與新 tokens 並存 —— 新元件 className 全走 `ft-` 前綴避免污染。
- `types.ts` 3,988 行在 S4 前不動,舊檔案才能持續編譯。
- e2e 若依賴 dev server 設定(playwright config),S2 首先確認啟動方式再改 spec。

## R6(2026-07-08)— 數據信任修復

- **病根**:TWSE 免費行情檔(STOCK_DAY_ALL)比個股歷史(STOCK_DAY)慢一個交易日 → 報價監視區 00982A 顯示 07/06 的 25.28,券商 APP 已是 07/07 的 24.09。
- **修法**:後端咽喉點 `_apply_history_close_overlay`(server.py)——凡台股報價列,若手上歷史快取最後一根 K 比行情檔新,直接以歷史收盤覆寫 price/close、重算漲跌%、更新資料日,標 `price_basis: history_close_overlay`。全站(任務牆/行情頁/展開列)一次矯正;絕不向舊值回退(有測試釘住)。
- **弱模型守則**:AGENTS.md 新增〈後續 AI 執勤守則〉7 條。
- **已知未修(誠實清單)**:台股「盤中」價需付費源,目前一律日收盤(已標示資料日);券商手續費折扣未參數化(淨損益為估算);FRED 行事曆 S6 仍為選配。

## R7(2026-07-08)— 六點驗收:結構清晰 + 資料誠實

驗收回饋六點,除 #1 外全數修復(一輪改完):

1. **#4 數據信任(25.28→24.09)收尾** — R6 的 overlay 生效,00982A 全站顯示 24.09/-4.71%/資料日07/07,與券商一致。
2. **加密撤出行情、紙上交易獨立成頁** — 行情頁=綜合市場(美股/台股/匯率),加密行情自成一頁,**新增第 16 條路由 `paper`**(紙上交易)承接紙上帳戶/掛單/近30筆歷史;三個紙上動作(submit/cancel/reset)route_id 由 crypto 改掛 paper;crypto 契約收斂為純行情。契約/計數 pin 全站 15→16、selectors 31→33。
3. **#3 圖表病根=後端會死** — 診斷:先前用 subshell `&` 背景啟動,工具呼叫結束即被回收 → 使用者展開圖表時後端已死 → 自抓落空顯 fallback。改用 run_in_background 持續存活;另給 CandleChart **自動重試 3 次(2.5s 間隔)**,瞬斷自癒不再要人手動再展開。
4. **#4 新聞未審核** — 病根:GDELT 廣撈把波蘭謀殺/秘魯政治/Io火山/ET Fashion 多語垃圾灌進 feed。加 `_is_finance_relevant` 財經相關性閘門(中英關鍵詞),**只擋 GDELT,策展 5 RSS 直通**。
5. **#5 今日速覽不變** — 病根:sections 是 AI 手寫,沒人寫就凍結。加 `build_live_sections`:沒有 AI sections 時,後端即時從當前 feed 按分類彙整(標 `origin:auto`,前端顯「自動彙整」+分類標籤),永遠跟著新聞動。
6. **#6 資料源指示燈「0·0全暗」** — 病根 A:後端當時死掉回空;病根 B:前端讀每筆 `state`(全 None)把 34 目錄項全當「有快取」。改讀 `/api/providers.summary` 精確數字:20 活躍/4 快取偏舊/5 待接key/30 實作/34 目錄。

**弱模型可運作性(#2 前一輪)**:AGENTS.md 已有執勤守則;本輪新增路由走完整契約鏈(contracts+agent_contract+shellData+App+pages+測試)即為範本。

**已知未修(誠實清單)**:台股盤中價仍需付費源(日收盤+標資料日);GDELT 相關性用關鍵詞比對,極少數多語財經新聞可能被誤擋(寧缺勿濫);券商手續費折扣未參數化。
