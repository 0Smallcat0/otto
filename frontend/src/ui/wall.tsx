// M27 任務牆 — the AI operates; a person watches. Every zone is read-only.

import { Fragment, useEffect, useState } from "react";
import type { ReactNode } from "react";
import {
  activateOnKey,
  getJson,
  type ActivityEvent,
  type ActivitySlice,
  type CryptoSlice,
  type MarketsSlice,
  type NewsSlice,
  type Quoteish,
  ageLabel,
  rankHeadlines,
  sessionSpan,
  fmt,
  hhmm,
  isToday,
  minutesToAge,
  mmddhhmm,
  num,
  pct,
  quotePct
} from "./api";
import { useT } from "./i18n";

/* ── 帳本橫幅(FreqUI 慣例:損益是一級公民)── */

export interface RealBookSlice {
  active_portfolio_id?: string;
  portfolio?: { name?: string; currency?: string };
  positions?: Record<string, string>[];
}

/** Owner's real holdings book, priced off whatever quote caches we hold. */
export function RealBookBanner({ book, markets }: { book: RealBookSlice | null; markets: MarketsSlice | null }) {
  const { t } = useT();
  const positions = book?.positions ?? [];
  // The daily-history cache is often one close fresher than the TWSE quote
  // file (07/07 vs 07/06) — for the money number, always use the freshest
  // close we hold.
  const [historyClose, setHistoryClose] = useState<Record<string, number>>({});
  const symbolsKey = positions.map((position) => position.symbol).join(",");
  useEffect(() => {
    let alive = true;
    void Promise.all(
      symbolsKey.split(",").filter(Boolean).map(async (symbol) => {
        const detail = await getJson<{ candles?: { close?: string }[] }>(
          `/api/markets/candles/${symbol.replace("/", "")}`
        );
        const last = detail?.candles?.[detail.candles.length - 1]?.close;
        const parsed = Number.parseFloat(String(last ?? ""));
        return [symbol, parsed] as const;
      })
    ).then((entries) => {
      if (!alive) return;
      const map: Record<string, number> = {};
      for (const [symbol, price] of entries) if (Number.isFinite(price)) map[symbol] = price;
      setHistoryClose(map);
    });
    return () => {
      alive = false;
    };
  }, [symbolsKey]);
  if (!positions.length) return null;
  const research = markets?.research_summary;
  const priceMap = new Map<string, number>();
  for (const row of [
    ...(markets?.rows ?? []),
    ...(research?.finnhub_quotes?.rows ?? []),
    ...(research?.twse_quotes?.rows ?? []),
    ...(research?.twelve_data_quotes?.rows ?? [])
  ]) {
    const parsed = Number.parseFloat(String(row.price ?? row.close ?? ""));
    if (row.symbol && Number.isFinite(parsed)) priceMap.set(row.symbol, parsed);
  }
  const priced = positions.map((position) => {
    const quantity = Number.parseFloat(String(position.quantity ?? ""));
    const cost = Number.parseFloat(String(position.avg_cost ?? position.avg_price ?? ""));
    // Prefer the book's own live mark (/api/portfolio now prices equities off
    // Yahoo) over the daily-candle cache, which for some symbols is a stale
    // close and was inflating the P&L. Candle/quote-map only fill in when the
    // book has no usable live price.
    const liveLast = Number.parseFloat(String(position.last_price ?? ""));
    const mapped = priceMap.get(String(position.symbol));
    const close = historyClose[String(position.symbol)];
    const price =
      Number.isFinite(liveLast) && liveLast > 0
        ? liveLast
        : Number.isFinite(mapped) && (mapped as number) > 0
          ? (mapped as number)
          : Number.isFinite(close) && close > 0
            ? close
            : cost;
    return { symbol: String(position.symbol), quantity, cost, price };
  }).filter((row) => Number.isFinite(row.quantity) && Number.isFinite(row.cost));
  const value = priced.reduce((sum, row) => sum + row.quantity * row.price, 0);
  const costTotal = priced.reduce((sum, row) => sum + row.quantity * row.cost, 0);
  const pnl = value - costTotal;
  const pnlPct = costTotal > 0 ? (pnl / costTotal) * 100 : NaN;
  // 台灣券商 APP 的「損益」慣例=扣掉預估賣出成本(手續費 0.1425% +
  // 證交稅:股票 0.3%、ETF 0.1%;00 開頭視為 ETF)。券商折扣未計。
  const estimatedExitFees = priced.reduce((sum, row) => {
    const gross = row.quantity * row.price;
    const taxRate = row.symbol.startsWith("00") ? 0.001 : 0.003;
    return sum + gross * (0.001425 + taxRate);
  }, 0);
  const netPnl = pnl - estimatedExitFees;
  const cls = pnl > 0 ? "ft-up" : pnl < 0 ? "ft-down" : "ft-dim";
  const currency = book?.portfolio?.currency ?? "TWD";
  return (
    <div className="ft-book" data-testid="wall-real-book">
      <div>
        <div className="k">{book?.portfolio?.name ?? t("帳本")}({currency})</div>
        <div className="v">{num(value, 0)} <small>{currency}</small></div>
        <div className="s">{t("成本")} {num(costTotal, 0)}</div>
      </div>
      <div>
        <div className="k">{t("未實現(毛)")}</div>
        <div className={`v ${cls}`}>{pnl > 0 ? "+" : ""}{num(pnl, 0)}</div>
        <div className={`s ${cls}`}>
          {Number.isFinite(pnlPct) ? `${pnlPct > 0 ? "+" : ""}${pnlPct.toFixed(2)}%` : ""}
          {" · "}{t("淨(估)")} {netPnl > 0 ? "+" : ""}{num(netPnl, 0)}
        </div>
      </div>
      <div>
        <div className="k">{t("持倉")}</div>
        <div className="v">{priced.length}</div>
        <div className="s">{t("日收盤計價")}</div>
      </div>
      <div className="ft-pos">
        <table>
          <thead><tr><th scope="col">{t("持倉")}</th><th scope="col">{t("數量")}</th><th scope="col">{t("成本")}</th><th scope="col">{t("現價")}</th><th scope="col">{t("未實現")}</th></tr></thead>
          <tbody>
            {priced.map((row) => {
              const rowPnl = row.cost > 0 ? ((row.price - row.cost) / row.cost) * 100 : NaN;
              const view = pct(rowPnl);
              return (
                <tr key={row.symbol}>
                  <td>{row.symbol}</td>
                  <td>{num(row.quantity, 0)}</td>
                  <td>{num(row.cost)}</td>
                  <td>{num(row.price)}</td>
                  <td className={view.cls}>{view.text}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function EquityBanner({ crypto }: { crypto: CryptoSlice | null }) {
  const { t } = useT();
  const account = crypto?.account;
  const positions = crypto?.positions ?? [];
  const marketRows = crypto?.market?.rows ?? [];
  const lastPrice = (symbol: string): number => {
    const row = marketRows.find((item) => item.symbol === symbol);
    const parsed = Number.parseFloat(row?.price ?? "");
    return Number.isFinite(parsed) ? parsed : NaN;
  };
  const equity = Number.parseFloat(account?.equity ?? "");
  const initial = Number.parseFloat(account?.initial_cash ?? "");
  const total = Number.isFinite(equity) && Number.isFinite(initial) ? equity - initial : NaN;
  const totalPct = Number.isFinite(total) && initial > 0 ? (total / initial) * 100 : NaN;
  let unrealized = 0;
  let unrealizedKnown = positions.length > 0;
  for (const position of positions) {
    const price = lastPrice(position.symbol);
    const avg = Number.parseFloat(position.avg_price);
    const quantity = Number.parseFloat(position.quantity);
    if (!Number.isFinite(price) || !Number.isFinite(avg) || !Number.isFinite(quantity)) {
      unrealizedKnown = false;
      continue;
    }
    unrealized += (price - avg) * quantity;
  }
  const workingOrders = (crypto?.orders ?? []).filter((order) => order.status === "WORKING").length;
  const todayTradesFor = (symbol: string) =>
    (crypto?.history ?? []).filter((row) => row.symbol === symbol && isToday(row.created_at)).length;
  const totalCls = !Number.isFinite(total) ? "ft-dim" : total > 0 ? "ft-up" : total < 0 ? "ft-down" : "";
  const unrlCls = !unrealizedKnown ? "ft-dim" : unrealized > 0 ? "ft-up" : unrealized < 0 ? "ft-down" : "";

  return (
    <div className="ft-book" data-testid="wall-equity">
      <div>
        <div className="k">{t("帳戶權益(紙上)")}</div>
        <div className="v">
          {num(equity, 2)} <small>{account?.quote_asset ?? "USDT"}</small>
        </div>
        <div className="s">{t("起始")} {num(initial, 0)}</div>
      </div>
      <div>
        <div className="k">{t("總損益")}</div>
        <div className={`v ${totalCls}`}>{Number.isFinite(total) ? `${total > 0 ? "+" : ""}${num(total, 2)}` : "—"}</div>
        <div className={`s ${totalCls}`}>{Number.isFinite(totalPct) ? `${totalPct > 0 ? "+" : ""}${totalPct.toFixed(2)}%` : ""}</div>
      </div>
      <div>
        <div className="k">{t("未實現")}</div>
        <div className={`v ${unrlCls}`}>
          {unrealizedKnown ? `${unrealized > 0 ? "+" : ""}${num(unrealized, 2)}` : "—"}
        </div>
        <div className="s">
          {positions.length} {t("持倉")} · {workingOrders} {t("掛單")}
        </div>
      </div>
      <div className="ft-pos">
        <table>
          <thead>
            <tr><th scope="col">{t("持倉")}</th><th scope="col">{t("數量")}</th><th scope="col">{t("成本")}</th><th scope="col">{t("現價")}</th><th scope="col">{t("未實現")}</th><th scope="col">{t("今日交易")}</th></tr>
          </thead>
          <tbody>
            {positions.length === 0 ? (
              <tr><td className="ft-faint" colSpan={6}>{t("尚無持倉——AI 下的紙上單會出現在這裡")}</td></tr>
            ) : (
              positions.map((position) => {
                const price = lastPrice(position.symbol);
                const avg = Number.parseFloat(position.avg_price);
                const pnl = Number.isFinite(price) && Number.isFinite(avg) && avg > 0
                  ? ((price - avg) / avg) * 100
                  : NaN;
                const pnlView = pct(pnl);
                return (
                  <tr key={position.symbol}>
                    <td>{position.symbol}</td>
                    <td>{fmt(position.quantity)}</td>
                    <td>{num(position.avg_price, 2)}</td>
                    <td>{Number.isFinite(price) ? num(price, 2) : "—"}</td>
                    <td className={pnlView.cls}>{pnlView.text}</td>
                    <td className="ft-dim">{todayTradesFor(position.symbol)}{t("筆")}</td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/** First poll still in flight — show the shape of what is coming, never the
 *  "nothing here" copy. */
export function Skeleton({ rows = 5 }: { rows?: number }) {
  const { t } = useT();
  return (
    <div className="ft-sk" role="status" aria-label={t("讀取中…")}>
      {Array.from({ length: rows }, (_, index) => <span key={index} />)}
    </div>
  );
}

/* ── 報價監視表(Bloomberg 慣例:密度)── */

function QuoteRow({ row, label }: { row: Quoteish; label?: string }) {
  const change = quotePct(row);
  return (
    <div className="ft-q">
      <span className="n">
        {row.symbol}
        {label ? <small>{label}</small> : null}
      </span>
      <span className="p">{fmt(row.price ?? row.close)}</span>
      <span className={`c ${change.cls}`}>{change.text}</span>
    </div>
  );
}

export function QuoteMonitor({ markets, crypto, watchlist, settled = true }: {
  markets: MarketsSlice | null;
  crypto: CryptoSlice | null;
  watchlist: { groups?: Record<string, string[] | undefined> } | null;
  settled?: boolean;
}) {
  const { t, lang } = useT();
  // Never pass off cached numbers as current: every group carries its age,
  // amber once it is older than an hour.
  const Freshness = ({ iso }: { iso?: string }) => {
    const age = ageLabel(iso, lang);
    if (!age.text) return null;
    return <small className={age.staleMinutes > 60 ? "ft-am" : undefined}> · {age.text}</small>;
  };
  // Fetch age says the cache is being refreshed, not that the market is open:
  // "Finnhub · 1天前" sat above a price that was two sessions old. Prefer the
  // session the quote belongs to, and fall back to fetch age only when the
  // row won't name one.
  // Read the whole group, not rows[0]: TWSE publishes per symbol, so 2330 can
  // carry today's close while 0050 still holds yesterday's. Stamping from the
  // first row certified three stale rows as today's, on a session where 0050
  // had actually fallen 4.24% and the wall read +0.15% (2026-07-28, undoing
  // the same week's group-header commit).
  const Session = ({ rows, iso }: { rows: Quoteish[]; iso?: string }) => {
    const { stamp, mixed } = sessionSpan(rows);
    if (!stamp) return <Freshness iso={iso} />;
    return (
      <small className={mixed ? "ft-am" : undefined}>
        {" "}· {t("資料日")} {stamp} {t("收盤")}{mixed ? ` · ${t("部分較新")}` : ""}
      </small>
    );
  };
  const research = markets?.research_summary;
  const groups = watchlist?.groups ?? {};
  const pick = (wanted: string[] | undefined, rows: Quoteish[], fallback: number): Quoteish[] => {
    if (!wanted || wanted.length === 0) return rows.slice(0, fallback);
    const bySymbol = new Map(rows.map((row) => [row.symbol, row]));
    // Watchlist order wins; symbols the AI added but nothing refreshed yet
    // still show up as pending rows instead of silently vanishing.
    return wanted.map((symbol) => bySymbol.get(symbol) ?? { symbol });
  };
  const cryptoRows = pick(groups.crypto, markets?.rows ?? [], 6);
  const usRows = pick(groups.us, research?.finnhub_quotes?.rows ?? [], 8);
  const twRows = pick(groups.tw, research?.twse_quotes?.rows ?? [], 8);
  const fxRows = pick(groups.fx, (research?.twelve_data_quotes?.rows ?? []).filter((row) => row.symbol.includes("/")), 6);
  const held = new Set((crypto?.positions ?? []).map((position) => position.symbol));
  const heldRows = cryptoRows.filter((row) => held.has(row.symbol));
  const otherCrypto = cryptoRows.filter((row) => !held.has(row.symbol));
  const count = heldRows.length + otherCrypto.length + usRows.length + twRows.length + fxRows.length;

  return (
    <div className="ft-col" data-testid="wall-quotes">
      <div className="ft-h2">{t("報價監視")} <span className="r ft-dim">{count} {lang === "en" ? "symbols" : "檔"} · {t("AI 管理")}</span></div>
      {heldRows.length > 0 ? (
        <>
          <div className="ft-qgrp">{t("紙上持倉")}<Freshness iso={markets?.status?.last_update} /></div>
          {heldRows.map((row) => <QuoteRow key={`h-${row.symbol}`} row={row} />)}
        </>
      ) : null}
      {otherCrypto.length > 0 ? (
        <>
          <div className="ft-qgrp">{t("加密")}<Freshness iso={markets?.status?.last_update} /></div>
          {otherCrypto.map((row) => <QuoteRow key={`c-${row.symbol}`} row={row} />)}
        </>
      ) : null}
      {usRows.length > 0 ? (
        <>
          <div className="ft-qgrp">{t("美股")} <small>· Finnhub</small><Session rows={usRows} iso={usRows[0]?.retrieved_at} /></div>
          {usRows.map((row) => <QuoteRow key={`u-${row.symbol}`} row={row} />)}
        </>
      ) : null}
      {twRows.length > 0 ? (
        <>
          <div className="ft-qgrp">{t("台股")} <small>· TWSE</small><Session rows={twRows} /></div>
          {twRows.map((row) => <QuoteRow key={`t-${row.symbol}`} row={row} label={row.name} />)}
        </>
      ) : null}
      {fxRows.length > 0 ? (
        <>
          <div className="ft-qgrp">FX <small>· Twelve Data</small><Session rows={fxRows} iso={fxRows[0]?.retrieved_at} /></div>
          {fxRows.map((row) => <QuoteRow key={`f-${row.symbol}`} row={row} />)}
        </>
      ) : null}
      {/* R5: FRED macro removed from the wall — monthly/quarterly series are
          context, not quotes. They live at the bottom of Markets, inside news
          速覽 when relevant, and one question away in the conversation. */}
      {count === 0
        ? settled
          ? <div className="ft-empty">{t("尚無報價快取——AI 刷新資料後這裡會亮起來")}</div>
          : <Skeleton rows={6} />
        : null}
      <div className="ft-note">{t("監看清單由 AI 依持倉與研究主題維護——在對話說「幫我盯○○」即可增減")}</div>
    </div>
  );
}

/* ── AI 動態流(單一流;產出=行內卡)── */

const ACTION_VERBS: Record<string, string> = {
  markets_refresh_public: "刷新 公開行情",
  crypto_refresh_public: "刷新 加密行情",
  news_refresh: "刷新 新聞",
  markets_fred_refresh: "刷新 FRED 總經",
  backtest_run_closed_candle: "回測完成",
  backtest_walk_forward_run: "Walk-forward 完成",
  backtest_optimize: "參數優化完成",
  algo_scan: "訊號掃描",
  algo_run_backtest: "策略回測",
  crypto_submit_paper_order: "紙上下單",
  crypto_cancel_paper_order: "紙上撤單",
  portfolio_report: "Portfolio 報告",
  news_research_brief: "新聞簡報",
  local_state_backup_index: "備份檢視",
  store_optional_data_provider_secret: "封存資料 key"
};

const EXTRA_VERBS: Record<string, string> = {
  markets_watchlist_update: "更新 監看清單",
  markets_watchlist_index: "讀取 監看清單",
  markets_finnhub_quote_watchlist_refresh: "刷新 美股報價",
  markets_twelve_data_quote_watchlist_refresh: "刷新 FX 報價",
  markets_twse_quote_snapshot_refresh: "刷新 台股報價",
  markets_stooq_quote_snapshot_refresh: "刷新 Stooq 報價",
  markets_history_refresh: "刷新 歷史 K 線",
  news_digest_write: "撰寫 新聞中文摘要",
  news_brief_detail: "讀取 新聞簡報",
  backtest_run_detail: "讀取 回測報告",
  portfolio_select: "切換 帳本",
  portfolio_book_detail: "讀取 帳本明細",
  algo_select_strategy: "選擇 策略",
  algo_delete_strategy: "刪除 策略",
  markets_candles_read: "讀取 K 線"
};

/** Human fallback: strip route prefixes and underscores so raw action ids
 *  never reach the wall verbatim. */
function humanizeActionId(actionId: string): string {
  return actionId
    .replace(/^(markets|news|crypto|portfolio|algo|backtest|nodes|code|quant_lab|quantlib|forum|ai_chat|local_state)_/, "")
    .replace(/_/g, " ");
}

function eventIcon(state?: string): { glyph: string; cls: string } {
  switch (state) {
    case "running":
    case "planned":
      return { glyph: "⟳", cls: "run" };
    case "failed":
    case "blocked":
      return { glyph: "✕", cls: "warn" };
    case "skipped":
      return { glyph: "⚠", cls: "warn" };
    default:
      return { glyph: "✓", cls: "ok" };
  }
}

function EventRow({ event, onOpenArtifact }: { event: ActivityEvent; onOpenArtifact: (path: string) => void }) {
  const { t } = useT();
  const icon = eventIcon(event.state);
  const actionId = event.action_id ?? "";
  const verb = t(ACTION_VERBS[actionId] ?? EXTRA_VERBS[actionId] ?? humanizeActionId(actionId || "動作"));
  return (
    <div className={`ft-ev${event.state === "running" ? " running" : ""}`}>
      <time>{isToday(event.created_at) ? hhmm(event.created_at) : mmddhhmm(event.created_at)}</time>
      <span className={`ic ${icon.cls}`}>{icon.glyph}</span>
      <div className="t">
        <b>{verb}</b>
        {event.summary ? <div className="m">{event.summary}</div> : null}
        {event.artifact_path ? (
          <div className="ft-art">
            <span className="ft-dim">{event.artifact_path}</span>
            <a className="ft-link open" role="button" tabIndex={0}
              onClick={() => onOpenArtifact(event.artifact_path ?? "")}
              onKeyDown={activateOnKey(() => onOpenArtifact(event.artifact_path ?? ""))}>{t("開 →")}</a>
          </div>
        ) : null}
      </div>
    </div>
  );
}

export function ActivityFeed({ activity, onOpenArtifact, settled = true }: {
  activity: ActivitySlice | null;
  onOpenArtifact: (path: string) => void;
  settled?: boolean;
}) {
  const { t } = useT();
  const events = activity?.events ?? [];
  const todays = events.filter((event) => isToday(event.created_at));
  const ok = todays.filter((event) => event.state === "succeeded" || event.state === "completed").length;
  const warn = todays.filter((event) => ["failed", "blocked", "skipped"].includes(event.state ?? "")).length;
  const runningCount = events.filter((event) => event.state === "running").length;

  return (
    <div className="ft-col" data-testid="wall-activity">
      <div className="ft-h2">{t("AI 動態")}
        {runningCount > 0 ? <span className="r ft-am">⟳ {t("進行中")} {runningCount}</span> : <span className="r ft-dim">{t("閒置")}</span>}
      </div>
      <div className="ft-stat">
        {t("今日")} <b>{todays.length}</b> {t("動作")} · <b className="ft-up">{ok}✓</b> <b className="ft-am">{warn}⚠</b>
      </div>
      {events.length === 0 && !settled ? (
        <Skeleton rows={4} />
      ) : events.length === 0 ? (
        <div className="ft-empty">
          {t("尚無活動——AI 開始操作終端機後,每一步都會出現在這裡。")}<br />
          {t("在 Claude Code 對話下指令即可開始。")}
        </div>
      ) : (
        events.map((event) => (
          <EventRow key={event.event_id ?? `${event.created_at}-${event.action_id}`} event={event} onOpenArtifact={onOpenArtifact} />
        ))
      )}
    </div>
  );
}

/* ── 頭條 + 日曆 ── */

export function Headlines({ news, digest, settled = true }: {
  news: NewsSlice | null;
  digest: {
    items?: Record<string, { title_zh?: string; summary_zh?: string }>;
    sections?: { category?: string; title_zh?: string; summary_zh?: string }[];
    updated_at?: string;
    origin?: string;
  } | null;
  settled?: boolean;
}) {
  const { t, lang } = useT();
  const items = rankHeadlines(news?.items ?? []).slice(0, 10);
  const digestItems = digest?.items ?? {};
  const watchTerms = (news?.layout?.watch_terms ?? []).map((term) => term.toLowerCase()).filter(Boolean);
  const starred = (title?: string) =>
    !!title && watchTerms.some((term) => title.toLowerCase().includes(term));

  return (
    <div className="ft-col" data-testid="wall-news">
      <div className="ft-h2">{t("頭條")} <span className="r ft-dim">{t("★=命中監看詞")}</span></div>
      {(digest?.sections?.length ?? 0) > 0 ? (
        <div style={{ padding: "8px 14px", borderBottom: "1px solid var(--line)", background: "var(--bg2)" }}>
          <div className="ft-cap" style={{ marginBottom: 4 }}>{digest?.origin === "auto" ? t("各版最新(自動)") : t("今日速覽(AI 整理)")}{digest?.updated_at ? <span> · {ageLabel(digest.updated_at, lang).text}</span> : null}</div>
          {(digest?.sections ?? []).map((section, index) => (
            <div key={index} style={{ fontSize: 12.5, margin: "3px 0" }}>
              {section.category ? <span className="ft-dim" style={{ fontSize: 10.5, letterSpacing: ".08em", marginRight: 6 }}>[{t(section.category)}]</span> : null}
              <b className="ft-am">{section.title_zh}</b>
              {section.summary_zh ? <span className="ft-dim"> — {section.summary_zh}</span> : null}
            </div>
          ))}
        </div>
      ) : null}
      {items.length === 0 && !settled ? (
        <Skeleton rows={5} />
      ) : items.length === 0 ? (
        <div className="ft-empty">{t("尚無新聞快取——AI 刷新後會列出頭條")}</div>
      ) : (
        items.map((item) => {
          const entry = item.item_id ? digestItems[item.item_id] : undefined;
          return (
            <div className="ft-nw" key={item.item_id ?? item.title}>
              <div className="h">
                {starred(item.title) ? <span className="star">★</span> : null}
                {entry?.title_zh ?? item.title}
                {entry && item.url ? (
                  <a className="ft-link" href={item.url} target="_blank" rel="noreferrer noopener" style={{ marginLeft: 6, fontSize: 11 }}>
                    {t("原文 ↗")}
                  </a>
                ) : null}
                {!entry && item.url ? (
                  <a className="ft-link" href={item.url} target="_blank" rel="noreferrer noopener" style={{ marginLeft: 6, fontSize: 11 }}>↗</a>
                ) : null}
              </div>
              {entry?.summary_zh ? <div className="s" style={{ fontFamily: "var(--sans)", color: "var(--dim)" }}>{entry.summary_zh}</div> : null}
              <div className="s">
                {item.source} · {typeof item.age_minutes === "number" ? minutesToAge(item.age_minutes, lang) : hhmm(item.published_at)}
              </div>
            </div>
          );
        })
      )}
    </div>
  );
}

/* ── AI 判斷板:蒐集→思考→給看法,寫在人看得到的地方 ── */

interface ResearchCall {
  call_id: string;
  symbol: string;
  name?: string | null;
  stance: string;
  conviction: string;
  thesis: string;
  ref_price: string;
  mark_price?: string | null;
  quote_price?: string | null;
  distributed_per_share?: string | null;
  unrealized_pct?: string | null;
  invalidation?: string | null;
  invalidation_excess_pct?: string | null;
  matures_at: string;
  weight_pct?: string | null;
  mark_weight_pct?: string | null;
  cap_pct?: string | null;
  needs_review?: boolean;
  review_reasons?: string[];
  outcome?: string | null;
  score_price?: string | null;
  realized_pct?: string | null;
  window_honored?: boolean;
  benchmark_symbol?: string | null;
  benchmark_ref_source?: string | null;
  excess_pct?: string | null;
  beat_benchmark?: boolean | null;
}

interface Scorecard {
  scored_count?: number;
  decided_count?: number;
  win_count?: number;
  hit_rate_pct?: string | null;
  avg_favor_pct?: string | null;
  stale_scored_count?: number;
  sizing?: { scored_count?: number; risk_realized_count?: number };
  vs_benchmark?: {
    judged_count?: number;
    beat_count?: number;
    beat_rate_pct?: string | null;
    avg_excess_pct?: string | null;
    unmeasured_count?: number;
    backfilled_count?: number;
  };
}

const OUTCOME_LABEL: Record<string, string> = {
  worked: "說對了",
  failed: "看錯了",
  flat: "沒動(不算分)",
  moved: "走掉了",
  invalidated: "被打臉出場",
  risk_realized: "風險真的發生",
  risk_not_realized: "風險沒發生"
};

const OUTCOME_CLASS: Record<string, string> = {
  worked: "ft-up",
  failed: "ft-down",
  invalidated: "ft-down",
  moved: "ft-down",
  flat: "ft-dim",
  risk_realized: "ft-down",
  risk_not_realized: "ft-dim"
};

const STANCE_LABEL: Record<string, string> = {
  accumulate: "可加碼",
  reduce: "宜減碼",
  avoid: "先避開",
  hold: "續抱觀望",
  size_down: "降集中度"
};

const CONVICTION_LABEL: Record<string, string> = {
  low: "低信心",
  medium: "中信心",
  high: "高信心"
};

const STANCE_CLASS: Record<string, string> = {
  accumulate: "ft-up",
  reduce: "ft-down",
  avoid: "ft-down",
  hold: "ft-dim",
  size_down: "ft-down"
};

/** Open judgments with their reasoning — the thing the whole loop exists to produce. */
export function JudgmentBoard() {
  const { t } = useT();
  const [calls, setCalls] = useState<ResearchCall[]>([]);
  const [scored, setScored] = useState<ResearchCall[]>([]);
  const [card, setCard] = useState<Scorecard | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  useEffect(() => {
    let alive = true;
    const load = () =>
      void getJson<{
        open_calls?: ResearchCall[];
        scored_calls?: ResearchCall[];
        scorecard?: Scorecard;
      }>("/api/research/ledger").then((data) => {
        if (!alive || !data) return;
        setCalls(Array.isArray(data.open_calls) ? data.open_calls : []);
        setScored(Array.isArray(data.scored_calls) ? data.scored_calls : []);
        setCard(data.scorecard ?? null);
      });
    load();
    const timer = setInterval(load, 60_000);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, []);
  if (!calls.length && !scored.length) return null;
  // A concentration warning and a directional view answer different questions,
  // so they stopped sharing a table: crammed into one grid the "失效" column
  // held a price for six rows and "63.50% / 40.00%" for a seventh, and the same
  // symbol appeared twice looking like a bug. The warning is now its own band.
  const sizing = calls.filter((call) => call.stance === "size_down");
  const directional = calls
    .filter((call) => call.stance !== "size_down")
    .sort((a, b) => Number(Boolean(b.needs_review)) - Number(Boolean(a.needs_review)));
  const toggle = (id: string) => setOpen(open === id ? null : id);
  // 63.50% reads like false precision for a position weight; 63.5% is the number.
  const trimPct = (raw?: string | null) =>
    raw ? String(Number.parseFloat(raw)) : "—";
  // "what would prove me wrong" reads as a direction, not a bare number.
  const wrongIf = (call: ResearchCall) => {
    const stayOut = call.stance === "avoid" || call.stance === "reduce";
    const parts: string[] = [];
    if (call.invalidation) {
      parts.push(
        stayOut
          ? `${t("漲過")} ${call.invalidation}`
          : `${t("跌破")} ${call.invalidation}`
      );
    }
    // A relative thesis is not falsified by any absolute level, so the board
    // has to show the condition the engine actually scores it on — otherwise a
    // market-wide rally reads as "this call was wrong".
    if (call.invalidation_excess_pct) {
      const bench = call.benchmark_symbol ?? t("大盤");
      parts.push(
        stayOut
          ? `${t("贏過")} ${bench} ${call.invalidation_excess_pct}%`
          : `${t("輸給")} ${bench} ${call.invalidation_excess_pct}%`
      );
    }
    return parts.length ? parts.join(t("，或")) : "—";
  };
  return (
    <div className="ft-card" data-testid="wall-judgments">
      <div className="ft-card-h">
        <span>{t("AI 判斷")}</span>
        <span className="s" style={{ marginLeft: 10 }}>
          {calls.length} {t("則進行中")}
          {" · "}
          {t("到期用真實價格驗收")}
        </span>
      </div>

      {sizing.map((call) => (
        <div
          key={call.call_id}
          className="ft-note"
          role="button"
          tabIndex={0}
          aria-expanded={open === call.call_id}
          onClick={() => toggle(call.call_id)}
          onKeyDown={(event) => {
            if (event.key === "Enter" || event.key === " ") {
              event.preventDefault();
              toggle(call.call_id);
            }
          }}
          // --ft-down is not a token (the token is --down; ft-down is the class),
          // so this always fell through to a hardcoded off-palette red.
          style={{ cursor: "pointer", borderLeft: "3px solid var(--down)", paddingLeft: 8 }}
        >
          <div>
            <b className="ft-down">{t("集中度提醒")}</b>{" "}
            {call.symbol}
            {call.name ? ` ${call.name}` : ""}
            {/* The directional table has carried this flag from the start; the
                sizing banner is a different block and never showed it, so the
                first review reason a sizing call can raise would have fired in
                the payload and reached nobody. */}
            {call.needs_review ? (
              <small className="ft-down"> ⟳{t("該重想")}</small>
            ) : null}{" "}
            {/* weight_pct is what the position weighed when the warning was
                written. Printing it in the present tense hid a concentration
                that had since grown — which is exactly the case the warning
                exists for. Lead with the live weight; say so when there isn't
                one, rather than passing a stale number off as current. */}
            {call.mark_weight_pct ? t("現佔你帳本") : t("記錄時佔你帳本")}{" "}
            <b className="ft-down">
              {trimPct(call.mark_weight_pct ?? call.weight_pct)}%
            </b>
            {t(",超過建議上限")} {trimPct(call.cap_pct)}%
            {call.mark_weight_pct ? (
              <span className="s">
                {" "}
                ({t("記錄時")} {trimPct(call.weight_pct)}%)
              </span>
            ) : null}
          </div>
          <div className="s">
            {open === call.call_id && call.review_reasons?.length ? (
              <div className="ft-down">
                {t("該重想")}: {call.review_reasons.join(" · ")}
              </div>
            ) : null}
            {open === call.call_id
              ? call.thesis
              : `${call.thesis.slice(0, 46)}… ${t("(點開看完整理由)")}`}
          </div>
        </div>
      ))}

      <div className="ft-pos">
        <table>
          <thead>
            <tr>
              <th scope="col">{t("標的")}</th>
              <th scope="col">{t("我的看法")}</th>
              <th scope="col">{t("記錄時")}</th>
              <th scope="col">{t("現在")}</th>
              <th scope="col">{t("什麼情況算看錯")}</th>
              <th scope="col">{t("驗收日")}</th>
            </tr>
          </thead>
          <tbody>
            {directional.map((call) => {
              const cls = STANCE_CLASS[call.stance] ?? "ft-dim";
              const move = Number.parseFloat(String(call.unrealized_pct ?? ""));
              const view = Number.isFinite(move) ? pct(move) : null;
              return (
                <Fragment key={call.call_id}>
                  <tr onClick={() => toggle(call.call_id)} tabIndex={0} aria-expanded={open === call.call_id}
                    onKeyDown={activateOnKey(() => toggle(call.call_id))} style={{ cursor: "pointer" }}>
                    <td>
                      <span className="ft-faint">{open === call.call_id ? "▾" : "▸"}</span>{" "}
                      {call.symbol}
                      {call.name ? <small> {call.name}</small> : null}
                      {call.needs_review ? (
                        <small className="ft-down"> ⟳{t("該重想")}</small>
                      ) : null}
                    </td>
                    <td className={cls}>
                      {t(STANCE_LABEL[call.stance] ?? call.stance)}
                      <small> {t(CONVICTION_LABEL[call.conviction] ?? call.conviction)}</small>
                    </td>
                    <td className="ft-faint">{call.ref_price}</td>
                    {/* mark_price is what the holder is worth, not what the
                        ticker prints: after a payout the two differ by exactly
                        what was handed over. Showing only the first sends the
                        reader to a quote page that disagrees with the board. */}
                    <td>
                      {call.mark_price ?? "—"}
                      {view ? <small className={view.cls}> {view.text}</small> : null}
                      {call.distributed_per_share && call.quote_price ? (
                        <small
                          className="ft-faint"
                          title={`${t("除權息配發")} ${call.distributed_per_share}`}
                        >
                          <br />
                          {t("盤上")} {call.quote_price} + {t("配發")}{" "}
                          {call.distributed_per_share}
                        </small>
                      ) : null}
                    </td>
                    <td className="s">{wrongIf(call)}</td>
                    <td className="s">{String(call.matures_at).slice(5, 10).replace("-", "/")}</td>
                  </tr>
                  {open === call.call_id ? (
                    <tr>
                      <td colSpan={6} className="s">
                        {call.review_reasons?.length ? (
                          <div className="ft-down">
                            {t("該重想")}: {call.review_reasons.join(" · ")}
                          </div>
                        ) : null}
                        {call.thesis}
                      </td>
                    </tr>
                  ) : null}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
      {scored.length > 0 ? (
        <>
          <div className="ft-card-h" style={{ marginTop: 12 }}>
            <span>{t("已驗收")}</span>
            <span className="s" style={{ marginLeft: 10 }}>
              {card?.hit_rate_pct
                ? `${t("命中率")} ${card.hit_rate_pct}% (${card.win_count}/${card.decided_count})`
                : t("還沒有可計分的判斷")}
              {card?.avg_favor_pct ? ` · ${t("平均")} ${card.avg_favor_pct}%` : ""}
              {card?.sizing?.scored_count
                ? ` · ${t("集中度警示")} ${card.sizing.scored_count} ${t("則,其中風險發生")} ${card.sizing.risk_realized_count}`
                : ""}
              {card?.stale_scored_count
                ? ` · ${card.stale_scored_count} ${t("則因延遲計分不列入")}`
                : ""}
              {card?.vs_benchmark?.beat_rate_pct
                ? ` · ${t("贏過大盤")} ${card.vs_benchmark.beat_count}/${card.vs_benchmark.judged_count}${
                    card.vs_benchmark.avg_excess_pct
                      ? ` (${t("平均超額")} ${card.vs_benchmark.avg_excess_pct}%)`
                      : ""
                  }`
                : ""}
            </span>
          </div>
          <div className="ft-pos">
            <table>
              <thead>
                <tr>
                  <th scope="col">{t("標的")}</th>
                  <th scope="col">{t("我的看法")}</th>
                  <th scope="col">{t("結果")}</th>
                  <th scope="col">{t("記錄時")}</th>
                  <th scope="col">{t("結算價")}</th>
                  <th scope="col">{t("價格變動")}</th>
                  <th scope="col">{t("對大盤")}</th>
                </tr>
              </thead>
              <tbody>
                {scored.slice(-12).reverse().map((call) => (
                  <tr key={call.call_id}>
                    <td>{call.symbol}{call.name ? <small> {call.name}</small> : null}</td>
                    <td className={STANCE_CLASS[call.stance] ?? "ft-dim"}>
                      {t(STANCE_LABEL[call.stance] ?? call.stance)}
                    </td>
                    <td className={OUTCOME_CLASS[call.outcome ?? ""] ?? "ft-dim"}>
                      {t(OUTCOME_LABEL[call.outcome ?? ""] ?? call.outcome ?? "—")}
                      {call.window_honored === false ? (
                        <small className="ft-dim"> {t("(延遲計分)")}</small>
                      ) : null}
                    </td>
                    <td className="ft-faint">{call.ref_price}</td>
                    <td>{call.score_price ?? "—"}</td>
                    <td className={pct(Number.parseFloat(String(call.realized_pct ?? ""))).cls}>
                      {call.realized_pct ? `${call.realized_pct}%` : "—"}
                    </td>
                    {/* Coloured by the verdict, never by the sign: a call that
                        meant to stay out wins WITH a negative excess, so
                        painting this red/green off the number would tell the
                        opposite of the truth for every avoid and reduce. */}
                    <td
                      className={
                        call.beat_benchmark === true
                          ? "ft-up"
                          : call.beat_benchmark === false
                            ? "ft-down"
                            : "ft-dim"
                      }
                    >
                      {call.excess_pct === null || call.excess_pct === undefined ? (
                        <span className="ft-dim">{t("沒有基準")}</span>
                      ) : (
                        <>
                          {`${call.excess_pct}%`}
                          {call.beat_benchmark === null || call.beat_benchmark === undefined ? (
                            <small className="ft-dim"> {t("(它就是大盤)")}</small>
                          ) : null}
                          {call.benchmark_ref_source === "backfill_daily_close" ? (
                            <small className="ft-faint" title={t("基準價是事後用當日收盤補的,不是記錄當下的即時價")}>
                              {" "}
                              {t("*補")}
                            </small>
                          ) : null}
                        </>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : null}
      <div className="ft-note s">
        {t("驗收日到、或價格走到「算我看錯」的位置,就用當下真實價格結算。集中度提醒只看風險有沒有發生,不算方向對錯;延遲太久才計分的也不列入命中率,因為量到的區間已經不是當初說的那段。這是分析,不是叫你買賣。")}
        {" "}
        {t("「對大盤」是同一段期間內,這檔的報酬減掉它所屬大盤的報酬。想抱住的看法要跑贏大盤才算贏,想避開的看法則是大盤跑贏它才算贏——所以負數不一定是輸,看顏色。標「*補」的基準價是事後用當日收盤補回來的,不是記錄當下的即時價;樣本還很少,這個比率先當參考。")}
      </div>
    </div>
  );
}

/* ── 任務牆組合 ── */

export function Wall({ markets, crypto, activity, news, watchlist, digest, book, onOpenArtifact, heading, settled }: {
  markets: MarketsSlice | null;
  crypto: CryptoSlice | null;
  activity: ActivitySlice | null;
  news: NewsSlice | null;
  watchlist: { groups?: Record<string, string[] | undefined> } | null;
  digest: {
    items?: Record<string, { title_zh?: string; summary_zh?: string }>;
    sections?: { category?: string; title_zh?: string; summary_zh?: string }[];
  } | null;
  book: RealBookSlice | null;
  onOpenArtifact: (path: string) => void;
  heading: ReactNode;
  /** Per-column first-fetch state, so a pending poll never reads as "no data". */
  settled?: { markets?: boolean; activity?: boolean; news?: boolean };
}) {
  return (
    <div className="ft-page" data-testid="workspace-dashboard">
      {heading}
      <RealBookBanner book={book} markets={markets} />
      <JudgmentBoard />
      <EquityBanner crypto={crypto} />
      <div className="ft-wall">
        <QuoteMonitor markets={markets} crypto={crypto} watchlist={watchlist} settled={settled?.markets ?? true} />
        <ActivityFeed activity={activity} onOpenArtifact={onOpenArtifact} settled={settled?.activity ?? true} />
        <Headlines news={news} digest={digest} settled={settled?.news ?? true} />
      </div>
    </div>
  );
}
