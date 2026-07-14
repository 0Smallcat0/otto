# M26 — AI 全權操作前置(Agent Readiness)執行計畫

Status: **Phase 0 + Phase 1 COMPLETE(2026-07-07,6 slices,428 pytest 綠)**;Phase 2 部分落地 — S2.1 restore 端點完成(2026-07-14),其餘候選待 owner 排優先序
Created: 2026-07-07 | Owner direction: 對話即介面、AI 全權負責操作、GUI = 人看的儀表板

## 0. 背景與依據

- Owner 於 2026-07-07 拍板終局架構:輸入端全交對話,AI 直接操作後端(HTTP/MCP),GUI 退為「AI 攤開結果給人看」的儀表板。
- 同日完成 agent-contract 全部 100 動作實跑體檢:**96/100 可用**,報告在 `artifacts/healthcheck/m25/hc_final.{md,json}`。
- 體檢揪出 6 個「AI 全權操作」前必須補的缺口(下方 Phase 0/1),並發生一次誤刪 10 本 portfolio 的事故(已復原 9 本;教訓規則見 §2)。
- Authority:`AGENTS.md` 硬閘門優先;本文件是 M26 的唯一進度事實源。M25 UI 工作(`M25_REDESIGN_SPEC.md` 等)獨立進行,不受本計畫影響。

## 1. 防記憶中斷執行協定(每個 session 都要遵守)

1. **本文件 = 唯一進度源。** 每完成一個 slice,**同一個 commit** 必須把 §4 進度表勾上並填 commit hash。禁止「程式改了、進度表沒改」的 commit。
2. **恢復流程**(新 session / compact 後):讀本文件 → `git log --oneline -15` → 對照 §4 找第一個未勾 slice → 讀該 slice 規格 → 直接動工。不需要重新討論方向。
3. **Slice 粒度**:每個 slice 獨立可交付、一個 commit、附測試,約一個工作段可完成;slice 之間任意中斷都安全。
4. **Commit 前門檻**:目標測試檔綠 → `python -m pytest -q` 全量綠(基線 407,只增不減)→ ruff 綠。全量約 18 分鐘,開發中先跑目標檔。
5. **本里程碑純後端**:不碰 `frontend/`(避開 e2e 文案耦合與 styles.css 亮色主題禁區);若某 slice 確需 UI 露出,獨立開 slice 並先讀 memory `m25-ui-overhaul`。
6. **後端不自動 reload**:改 `server.py`/`storage.py` 等之後,`:8765` 必須 kill 重啟(`.venv/Scripts/python.exe -m src.local_terminal`)才吃新 code。

## 2. 破壞性操作鐵則(2026-07-07 事故的直接產物)

- baseline 讀不到/解析為空 ⇒ **abort,零刪除**;絕不用差集推斷「可刪清單」。
- 只刪「創建當下記錄下來的確切 id」;不刪任何推斷出來的 id。
- 對會 mutate 的批次操作,先用 app 自己的 export 端點做快照存檔。
- `artifacts/**/*_state.json` 目前是無備份單點(S0.1 要解掉);在 S0.1 落地前手動 copy .bak 再動。
- `portfolio_delete`、`crypto_reset_paper`、`dashboard_reset`、`*_repair` 不進自動批次。

## 3. Slices

### Phase 0 — 防護網(最優先;AI 全權寫入的前提是可撤銷)

#### S0.1 狀態檔備份輪替
- **改哪**:`src/local_terminal/storage.py` — `_write_json(path, payload, root)`(≈L1311,唯一寫入漏斗,已有 atomic tmp+replace)加 keyword 參數 `keep_backups: int = 0`;寫入前若目標已存在,輪替 `<name>.json.bak1..bakN`(bak1 最新,N=3)。
- **開啟備份的寫入點(使用者狀態,12 類)**:`write_portfolio_state`、`write_paper_state`、`write_algo_state`、`write_nodes_state`、`write_code_state`、`write_quant_lab_state`、`write_quantlib_state`、`write_forum_state`、`write_chat_state`、`write_profile`、`write_settings`、`write_layout`/`write_dashboard_layout`/`write_markets_layout`/`write_news_layout`。
- **不備份**:所有 `write_*_cache`(市場快取可再生且高頻,備份只會製造 IO 噪音)。
- **測試**(新檔 `tests/test_m26_state_backups.py`):首寫無 bak;二寫產 bak1=前一版內容;連寫 N+2 次只留 N 份且順序正確;read 路徑完全不受 bak 檔影響;bak 檔名不被 storage 的其他 glob 掃到(檢查 artifact 索引/supervision 不會把 .bak 當 artifact)。
- **驗收**:改一次 portfolio → 檔案系統看到 bak → 手動用 bak 還原演練一次。

#### S0.2 備份可見性(唯讀)
- **新端點**:`GET /api/local-state/backups` — 列出每個受保護狀態檔的 bak 清單(相對路徑、mtime、size、對應狀態檔)。純 metadata,不讀內容。
- **agent-contract**:註冊 read-only action(safety_class `metadata_only_state_backup_index`),讓 AI 能自己確認「有沒有退路」。
- **明確不做**:寫入型 restore 端點。還原武器本身就是新的破壞性面;第一版文件化手動還原流程(stop server → copy bak → start)寫進本文件 §5。undo 端點等 Phase 2 再議。
- **測試**:端點回應 shape;無 bak 時空清單;bak 存在時列出正確 metadata。

### Phase 1 — AI 操作面補全(體檢缺口 A–D)

#### S1.1 portfolio select 端點(缺口 A)
- **背景**:目前 create/import/link/demo 都會劫持 active 指標,卻沒有任何「切回去」的手段——事故當天無法即時還原 active 的根因。
- **改哪**:`src/local_terminal/portfolio.py` 加 `select_portfolio(state, portfolio_id)`(unknown id → `PortfolioError`);`server.py` 加 `POST /api/portfolio/select` + `PortfolioSelectUpdate(BaseModel)`(`model_config = ConfigDict(extra="forbid")`,`portfolio_id: str = Field(min_length=1)`);`agent_contract.py` 註冊 action(safety_class `local_portfolio_state_only`)。
- **測試**(`tests/test_m26_portfolio_select.py`):select 存在的 book → active 變更且持久化;unknown id → 400;select 後 GET /api/portfolio 與 dashboard 讀取跟隨。
- **注意**:回應 payload 直接複用現有 portfolio route payload 組裝函式,response_contract 照實寫(吃 S1.3 的教訓)。

#### S1.2 algo strategy delete(缺口 B)
- **背景**:策略庫只能建不能刪,只增不減。
- **改哪**:`POST /api/algo/strategy/delete` + model(`strategy_id`、`confirm: bool`,confirm=false → 400);`active_strategy_id` 被刪時仿 portfolio delete 語義移轉到最近剩餘;內建 catalog 策略不可刪(實作時確認 algo state 的 `catalog` vs `strategies` 結構,只允許刪使用者庫)。
- **agent-contract**:註冊 action,`requires_confirmation: true`。
- **測試**:刪除成功/需 confirm/刪 active 的移轉/unknown id 400/catalog 策略拒刪。

#### S1.3 contract drift 修復 + 「地圖=實地」防再犯測試(缺口 C;本里程碑價值最高的一條)
- **背景**:agent-contract 是 AI 的地圖;體檢發現 8 處 response_contract 與實際回應不符。
- **8 處清單**(來自 hc_final,實作時以此為準逐一核對):
  1. `backtest_run_closed_candle`:contract 寫 `result`,實際頂層是 `run_id/config/summary/metrics/trades/.../artifacts/research_lineage`
  2. `quantlib_select_action`:寫 `request_template`,實際叫 `request_body`
  3. `algo_scan`:寫 `scanner/source_contract/research_lineage/artifacts`,實際巢狀在 `scan_result` 內
  4. `algo_run_backtest`:同上,巢狀在 `backtest_result` 內
  5. `crypto_refresh_public`:寫 `detail`,實際巢狀位置不同
  6. `quant_lab_select_module`:寫 `inputs`,實際巢狀在 `controls`/`active_module`
  7. `profile_save_local_preferences`:寫 `profile`,實際欄位攤平在頂層(`profile_id/display_name/...`)
  8. `portfolio_link_backtest`:寫 `backtest_context/linked_artifacts`,實際巢狀更深
- **修法**:預設「contract 遷就現實」(回應已被前端依賴,改回應風險大);逐條改 `agent_contract.py` 的 response_contract 為實際可 resolve 的 dotted path。
- **防再犯測試**(`tests/test_m26_contract_response_truth.py`):用 FastAPI TestClient 實跑每個可安全執行的 action(GET 全部 + 無害 POST;destructive/secret 跳過),對 response_contract 每個 key 用 dotted-path resolver(`a.b.c` 與 `arr[].field` 語義)驗證存在。此測試讓 contract 從此不可能再無聲漂移。
- **參考**:體檢用的 resolver 實作在事故 session 的 `reverdict.py`(scratchpad),語義已驗證,搬進測試即可。

#### S1.4 contract 文檔補強(缺口 D)
- `agent_activity_event` 的 request_contract 補上:`state` 枚舉 = `planned/running/succeeded/failed/blocked/skipped`;`action_id` 必須是真實 action id;`route_id` 需與 action 相符。
- 順掃全部 request_contract 與對應 pydantic model 欄位是否一致(欄位名、必填、枚舉),不符處修 contract 文字。
- S1.3 實作時發現:`POST /api/algo/select` 有路由但**沒有對應 contract 動作**(AI 無法透過 contract 發現「選擇策略」)——S1.4 一併補註冊 `algo_select_strategy` 動作,並加進真值測試的 algo 鏈。
- 測試:activity event 用合法/非法 state 各一;contract 文字掃描以人工 review 為主(不強求自動化)。

### Phase 2 — 對話介面強化(方向保留,Phase 0/1 完成後才細化成 slices)

候選(**尚未承諾**,屆時與 owner 再確認優先序):
- GUI「agent activity feed」:把 `agent_activity_event` 的資料層顯示在儀表板,人可即時看 AI 剛做了什麼(對話架構下「人即時觀察」的正解)。
- custom watchlist:讓對話能改 Finnhub/Twelve Data 的看盤清單(接 memory `optional-key-data-sources` 的遺留項)。
- `dashboard_reset` 加 confirm 或先快照(缺口 F 的正式解)。
- ~~undo/restore 端點(接 S0.2 留下的門)~~ → **S2.1 完成(2026-07-14)**:`POST /api/local-state/restore`,confirm 閘;restore 前現狀輪替進 slot 1(restore 本身可 undo);bak 壞檔零寫入;只認 protected 清單;contract 動作 `local_state_restore`(`confirm_gated_state_backup_restore`)。

**明確不在 M26**:in-app chat 接真實 LLM(費用/安全另議)、M25 剩餘 UI 美化、niche 資料源(EIA/BEA/Census)。

## 4. 進度表(每 slice 的 commit 必須同步更新這裡)

| Slice | 內容 | 狀態 | Commit | 驗證 |
|---|---|---|---|---|
| S0.1 | 狀態檔備份輪替 | ☑ 完成 2026-07-07 | `Give every state file a three-deep undo trail` | 8 新測試;全量 415 綠;ruff 綠;實機 bak+還原演練通過 |
| S0.2 | 備份唯讀端點 + contract action | ☑ 完成 2026-07-07 | `Let the agent see its own safety net` | 2 新測試;全量 417 綠;實機端點驗證(15 檔/1 bak/safety 區塊) |
| S1.1 | portfolio select | ☑ 完成 2026-07-07 | `Give the active-book pointer a way home` | 4 新測試;全量 421 綠;實機切換 demo↔真帳本+400 驗證 |
| S1.2 | algo strategy delete | ☑ 完成 2026-07-07 | `Let the strategy library shrink as well as grow` | 5 新測試;全量 426 綠;實機 confirm 閘+指標移轉演練;三新動作補進 recommended_actions |
| S1.3 | contract drift ×8 修復 + 真值測試 | ☑ 完成 2026-07-07 | `Make the agent's map answer to the territory` | 真值測試跑 28 GET+40 本地 POST 全 resolve;完整性守衛上膛;全量 427 綠;m21 兩處舊 pin 同步更新 |
| S1.4 | contract 文檔補強 | ☑ 完成 2026-07-07 | `Teach the contract to tell the whole truth` | 4 處 request 文字修正;algo_select_strategy 註冊(104 動作);枚舉鎖定測試;全量 428 綠 |
| S2.1 | restore 端點(undo 閉環) | ☑ 完成 2026-07-14 | `feat: confirm-gated state restore endpoint` | 8 新測試;truth test 實跑 restore;實機演練(400 閘/未知 kind 拒絕/restore+輪替驗證);contract 115 動作,preflight 自動標 requires_confirmation |

基線:407 pytest 通過(2026-07-07)。每 slice 淨增測試,不得減。

## 5. 還原流程

**首選(S2.1 起)**:`POST /api/local-state/restore` body `{"kind": "<protected kind>", "slot": 1..3, "confirm": true}` — 不必停後端;restore 前會把現狀輪替進 slot 1,再 restore 一次 slot 1 即 undo。kind 清單看 `GET /api/local-state/backups` 的 `rows[].kind`。

**手動 fallback**(端點不可用或檔案系統層問題時):
1. 停後端(kill `:8765` process)。
2. `<name>.json.bak1` 是最近一版;copy 蓋回 `<name>.json`。
3. 重啟 `.venv/Scripts/python.exe -m src.local_terminal`,GET 對應路由確認。

## 6. 風險與緩解

| 風險 | 緩解 |
|---|---|
| bak 檔被 artifact 掃描/supervision 誤認 | S0.1 測試明確覆蓋;bak 命名 `.json.bak1` 不符合現有 `*.json` glob 才算過 |
| S1.3 改 contract 影響依賴 contract 的既有測試(test_m21_agent_operability_contract 等) | 先跑該測試檔定位斷言,遷就現實地同步更新 |
| 全量測試 18 分鐘拖節奏 | slice 內跑目標檔,commit 前全量一次 |
| context compact 中斷 | §1 協定;本文件+git log 可完全重建進度 |
