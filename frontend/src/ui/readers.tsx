// M27 細讀模式 — finished research rendered as documents, not panels.

import { useEffect, useState } from "react";
import { activateOnKey, ageLabel, fmt, getJson, hhmm, isZhNative, minutesToAge, num, pct } from "./api";

const TRADE_COL_LABELS: Record<string, string> = {
  side: "方向", quantity: "數量", price: "價格", fee: "手續費",
  filled_at: "成交時間", signal_closed_at: "訊號平倉"
};
import { useT } from "./i18n";

/* ── shared doc chrome ── */

/** Full-page reader chrome.
 *
 *  The back link used to read 回任務牆 in every reader, but onBack returns to
 *  whatever opened it — the backtest index, the news index, whichever route
 *  was active. Opening a report from 回測 and being told the way out was the
 *  mission wall was simply false; the click stayed on 回測 (2026-07-27
 *  dogfood). Naming a destination is not an option either: NewsBriefReader is
 *  reached both from the news page and from the artifact router, so any name
 *  would be wrong from one of them. A label that cannot go stale it is.
 */
function DocShell({ onBack, children }: { onBack: () => void; children: React.ReactNode }) {
  const { t } = useT();
  return (
    <div className="ft-doc-wrap">
      <a className="ft-link ft-mono" role="button" tabIndex={0} onClick={onBack} onKeyDown={activateOnKey(onBack)}>{t("← 返回")}</a>
      <div className="ft-doc">{children}</div>
    </div>
  );
}

function Loading({ text }: { text: string }) {
  // Same words as before, but no longer wearing the empty state's clothes.
  return (
    <div className="ft-empty" role="status">
      <span className="ft-spin" aria-hidden="true" />
      {text}
    </div>
  );
}

/* ── 回測報告 ── */

interface BacktestDetail {
  run_id?: string;
  artifact_dir?: string;
  summary?: Record<string, unknown>;
  config?: Record<string, unknown>;
  returns_analysis?: Record<string, unknown>;
  trades?: Record<string, string>[];
  equity_curve?: Record<string, string>[];
  report_md?: string;
}

export interface SampleSufficiency {
  verdict: string;
  round_trip_count?: number;
  floor_round_trips?: number;
  span?: string;
  fragile_metrics?: string[];
}

const SAMPLE_VERDICT_LABEL: Record<string, string> = {
  not_a_verdict: "樣本太小,這些數字不是結論",
  directional_only: "剛過推論門檻,只能當方向參考",
  reliable: "樣本可用,仍要看涵蓋幾種盤勢",
};

/** Whether a backtest's headline numbers need qualifying, and with what.
 *
 * The KPI row — return, drawdown, win rate, trade count — is the surface that
 * reads as a verdict, and 11 round trips over twenty hours renders identically
 * to 400 over three years. The engine computes the difference; this decides
 * whether the screen says it. Exported so the decision has a guard: the
 * previous round shipped the engine half and left the render step dropping it,
 * which is the defect this file's test suite exists for.
 */
export function sampleCaveat(
  summary: Record<string, unknown> | undefined
): SampleSufficiency | null {
  const sample = summary?.sample as SampleSufficiency | undefined;
  if (!sample || typeof sample.verdict !== "string") return null;
  // A defensible sample needs no banner; anything else does.
  return sample.verdict === "defensible" ? null : sample;
}

function metricOf(detail: BacktestDetail, key: string): unknown {
  const analysis = detail.returns_analysis ?? {};
  const metrics = (analysis as { metrics?: Record<string, unknown> }).metrics ?? analysis;
  return (detail.summary?.[key] ?? (metrics as Record<string, unknown>)[key]);
}

function EquityCurve({ rows }: { rows: Record<string, string>[] }) {
  const { t } = useT();
  const valueKey = rows.length
    ? Object.keys(rows[0]).find((key) => /equity|value/i.test(key)) ?? ""
    : "";
  const values = rows
    .map((row) => Number.parseFloat(row[valueKey] ?? ""))
    .filter((value) => Number.isFinite(value));
  if (values.length < 2) return <div className="ft-empty">{t("無權益曲線資料")}</div>;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const points = values
    .map((value, index) => `${(index / (values.length - 1)) * 800},${120 - ((value - min) / span) * 104 - 8}`)
    .join(" ");
  const start = 120 - ((values[0] - min) / span) * 104 - 8;
  const rising = values[values.length - 1] >= values[0];
  return (
    <svg width="100%" height="130" viewBox="0 0 800 130" preserveAspectRatio="none"
      style={{ background: "var(--bg)", border: "1px solid var(--line)" }}>
      <line x1="0" y1={start} x2="800" y2={start} stroke="var(--down)" strokeWidth="1" strokeDasharray="3 5" />
      <polyline fill="none" stroke={rising ? "var(--up)" : "var(--down)"} strokeWidth="1.5" points={points} />
    </svg>
  );
}

export function BacktestRunReader({ runId, onBack }: { runId: string; onBack: () => void }) {
  const { t } = useT();
  const [detail, setDetail] = useState<BacktestDetail | null>(null);
  const [missing, setMissing] = useState(false);
  useEffect(() => {
    setDetail(null);
    setMissing(false);
    void getJson<BacktestDetail>(`/api/backtest/runs/${runId}`).then((value) => {
      if (value) setDetail(value);
      else setMissing(true);
    });
  }, [runId]);

  if (missing) {
    return <DocShell onBack={onBack}><h1>{t("找不到這筆回測")}</h1><div className="sub">{runId}</div></DocShell>;
  }
  if (!detail) return <DocShell onBack={onBack}><Loading text={t("讀取回測報告中…")} /></DocShell>;

  const summary = detail.summary ?? {};
  const returnView = pct(metricOf(detail, "return_pct") ?? metricOf(detail, "total_return_pct"));
  const drawdown = metricOf(detail, "max_drawdown_pct");
  // Win rate and the overfit verdict are only persisted inside the engine's
  // own report.md — quote the engine rather than recomputing.
  const report = detail.report_md ?? "";
  const winRate = metricOf(detail, "win_rate_pct")
    ?? report.match(/Win rate:\s*([\d.]+)%/)?.[1];
  const overfit = String(
    metricOf(detail, "overfit_warning")
    ?? report.match(/Overfit check:\s*(.+)/)?.[1]
    ?? ""
  );
  const sample = sampleCaveat(summary);
  const trades = detail.trades ?? [];
  const tradeCols = trades.length
    ? Object.keys(trades[0]).filter((key) =>
        ["side", "quantity", "price", "fee", "filled_at", "signal_closed_at"].includes(key)
      )
    : [];

  return (
    <DocShell onBack={onBack}>
      <h1>
        {t("回測報告")}:{String(summary.strategy_label ?? summary.strategy ?? "")} · {String(summary.symbol ?? "")} {String(summary.timeframe ?? "")}
      </h1>
      <div className="sub">{detail.run_id} · {String(summary.run_state ?? "")} · {t("收盤K回測")}</div>
      <div className="ft-kpis">
        <div className="ft-kpi"><div className="k">{t("總報酬")}</div><div className={`n ${returnView.cls}`}>{returnView.text}</div></div>
        <div className="ft-kpi"><div className="k">{t("最大回撤")}</div><div className="n ft-down">{drawdown != null ? `-${String(drawdown).replace(/^-/, "")}%` : "—"}</div></div>
        <div className="ft-kpi"><div className="k">{t("勝率")}</div><div className="n">{winRate != null ? `${winRate}%` : "—"}</div></div>
        <div className="ft-kpi"><div className="k">{t("交易數")}</div><div className="n">{String(summary.trade_count ?? trades.length)}</div></div>
      </div>
      {/* The KPIs above are the surface that reads as a verdict, so the caveat
          belongs directly under them. A run of 11 round trips over twenty hours
          produces a win rate and a Sharpe that look exactly like a run of 400
          over three years; the engine knows the difference and the screen used
          to drop it. */}
      {sample ? (
        <div className="ft-ainote">
          <div className="who">{t("樣本足夠性")}</div>
          {t(SAMPLE_VERDICT_LABEL[sample.verdict] ?? sample.verdict)}
          {" — "}
          {sample.round_trip_count} {t("個來回")}
          {sample.floor_round_trips ? ` / ${t("統計推論門檻")} ${sample.floor_round_trips}` : ""}
          {sample.span ? ` · ${sample.span}` : ""}
          {sample.fragile_metrics?.length ? (
            <div className="s" style={{ marginTop: 4 }}>
              {t("最不可信的指標")}: {sample.fragile_metrics.join(", ")}
            </div>
          ) : null}
        </div>
      ) : null}
      {overfit ? (
        <div className="ft-ainote"><div className="who">{t("過擬合警示(引擎判定)")}</div>{overfit}</div>
      ) : null}
      <h3>{t("權益曲線")}</h3>
      <EquityCurve rows={detail.equity_curve ?? []} />
      <h3>{t("交易(前 12 筆)")}</h3>
      {trades.length === 0 ? (
        <div className="ft-empty">{t("此回測無成交")}</div>
      ) : (
        <table>
          <thead><tr>{tradeCols.map((col) => <th scope="col" key={col}>{t(TRADE_COL_LABELS[col] ?? col)}</th>)}</tr></thead>
          <tbody>
            {trades.slice(0, 12).map((trade, index) => (
              <tr key={index}>
                {tradeCols.map((col) => (
                  <td key={col} className={col === "side" ? (trade[col] === "BUY" ? "ft-up" : "ft-down") : ""}>
                    {/at$/.test(col) ? hhmm(trade[col]) : col === "side" ? trade[col] : fmt(trade[col])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {detail.report_md ? (
        <>
          <h3>{t("引擎報告全文")}</h3>
          <div className="ft-ainote" style={{ whiteSpace: "pre-wrap", fontFamily: "var(--mono)", fontSize: 11.5 }}>
            {detail.report_md}
          </div>
        </>
      ) : null}
      <div className="ft-foot">artifact:<code>{detail.artifact_dir}</code> · {t("想調參數重跑或做 walk-forward,在對話跟 AI 說即可。")}</div>
    </DocShell>
  );
}

/* ── 新聞簡報 ── */

interface BriefDetail {
  brief_id?: string;
  artifact_dir?: string;
  brief?: {
    created_at?: string;
    summary?: unknown;
    topics?: unknown[];
    items?: unknown[];
    intel?: { article_count?: number; feed_count?: number };
  };
  brief_md?: string;
}

export function NewsBriefReader({ briefId, onBack }: { briefId: string; onBack: () => void }) {
  const { t, lang } = useT();
  const [detail, setDetail] = useState<BriefDetail | null>(null);
  const [missing, setMissing] = useState(false);
  useEffect(() => {
    setDetail(null);
    setMissing(false);
    void getJson<BriefDetail>(`/api/news/briefs/${briefId}`).then((value) => {
      if (value) setDetail(value);
      else setMissing(true);
    });
  }, [briefId]);

  if (missing) {
    return <DocShell onBack={onBack}><h1>{t("找不到這份簡報")}</h1><div className="sub">{briefId}</div></DocShell>;
  }
  if (!detail) return <DocShell onBack={onBack}><Loading text={t("讀取新聞簡報中…")} /></DocShell>;

  const brief = detail.brief ?? {};
  const topics = Array.isArray(brief.topics) ? brief.topics : [];
  return (
    <DocShell onBack={onBack}>
      <h1>{t("新聞研究簡報")}</h1>
      <div className="sub">
        {detail.brief_id} · {(brief.created_at ?? "").slice(0, 10)} · {brief.intel?.article_count ?? "—"}{t("篇")} · {brief.intel?.feed_count ?? "—"} {lang === "en" ? "sources" : t("來源")}
      </div>
      {topics.length > 0 ? (
        <>
          <h3>{t("簡報主題")}</h3>
          {topics.map((topic, index) => {
            const record = (topic ?? {}) as Record<string, unknown>;
            const title = String(record.title ?? record.label ?? record.topic ?? `${t("主題")} ${index + 1}`);
            const count = record.count ?? record.item_count;
            return (
              <div key={index} style={{ margin: "8px 0" }}>
                <b>{title}</b>{count != null ? <span className="ft-dim ft-mono"> · {String(count)}{t("篇")}</span> : null}
              </div>
            );
          })}
        </>
      ) : null}
      <h3>{t("簡報全文")}</h3>
      {detail.brief_md ? (
        <div style={{ whiteSpace: "pre-wrap", fontFamily: "var(--mono)", fontSize: 12, lineHeight: 1.65 }}>
          {detail.brief_md}
        </div>
      ) : (
        <div className="ft-empty">{t("此簡報沒有 brief.md 全文")}</div>
      )}
      <div className="ft-foot">artifact:<code>{detail.artifact_dir}</code> · {t("要追任何一條線索,在對話跟 AI 說即可。")}</div>
    </DocShell>
  );
}

/* ── Backtest / News 路由頁(索引 → 讀者)── */

interface RunIndexRow {
  run_id?: string;
  artifact_dir?: string;
  health_state?: string;
  created_at?: string;
  strategy_label?: string;
  strategy?: string;
  symbol?: string;
  timeframe?: string;
  return_pct?: string | number;
  /** Provenance of the candles the run was computed on. Never drop these:
   *  an offline_fallback run is priced off locally generated candles, so its
   *  return is not a market result at all. */
  data_state?: string;
  data_source?: string;
}

/** How much a run's return is worth, given the candles behind it.
 *
 *  Three of eight runs on this machine were `offline_fallback` off
 *  `local_deterministic_candle_generator` — the provenance the backtester
 *  writes when real data could not be fetched — and they were the three
 *  best-looking rows in the table, styled identically to the one live run
 *  (2026-07-27 dogfood). The number stays visible; what changes is that it
 *  stops claiming to be performance.
 */
export function runProvenance(row: { data_state?: string }): {
  label: string;
  cls: string;
  trusted: boolean;
} {
  const state = String(row.data_state ?? "").toLowerCase();
  if (state === "offline_fallback") return { label: "合成資料", cls: "ft-down", trusted: false };
  if (state === "stale") return { label: "過期快取", cls: "ft-am", trusted: true };
  if (state === "live") return { label: "即時", cls: "ft-dim", trusted: true };
  return { label: state || "—", cls: "ft-dim", trusted: true };
}

export function BacktestPage({ heading }: { heading: React.ReactNode }) {
  const { t } = useT();
  const [rows, setRows] = useState<RunIndexRow[] | null>(null);
  const [openRun, setOpenRun] = useState<string | null>(null);
  useEffect(() => {
    void getJson<{ run_index?: { runs?: RunIndexRow[] } }>("/api/backtest").then((value) => {
      setRows(value?.run_index?.runs ?? []);
    });
  }, [openRun]);

  if (openRun) return <BacktestRunReader runId={openRun} onBack={() => setOpenRun(null)} />;
  const runTime = (runId?: string): string => {
    const match = (runId ?? "").match(/^bt-(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})/);
    return match ? `${match[2]}/${match[3]} ${match[4]}:${match[5]}` : "—";
  };
  return (
    <div className="ft-page" data-testid="workspace-backtest">
      {heading}
      <div className="ft-note">{t("這裡是所有回測的索引——不論你在對話直接請 AI 跑,或 AI 從 Algo 策略觸發,每一次 run 都會留在這裡。點「開報告」看完整文件。")}</div>
      {rows === null ? (
        <Loading text={t("讀取回測索引中…")} />
      ) : rows.length === 0 ? (
        <div className="ft-empty">{t("尚無回測——在對話請 AI「幫我回測○○」,完成的報告會列在這裡。")}</div>
      ) : (
        <>
        {rows.some((row) => !runProvenance(row).trusted) ? (
          <div className="ft-note ft-down">
            {t("標「合成資料」的 run 是在抓不到市場資料時,用本機生成的 K 線跑的——那個報酬不是市場結果,不能當績效看。")}
          </div>
        ) : null}
        <table className="ft-table">
          <thead><tr><th scope="col">{t("時間")}</th><th scope="col">{t("策略")}</th><th scope="col">{t("標的")}</th><th scope="col">{t("資料")}</th><th scope="col" style={{ textAlign: "right" }}>{t("報酬")}</th><th scope="col"></th></tr></thead>
          <tbody>
            {rows.map((row) => {
              const prov = runProvenance(row);
              const ret = pct(row.return_pct);
              return (
                <tr key={row.run_id}>
                  <td>{runTime(row.run_id)}</td>
                  <td style={{ fontFamily: "var(--sans)" }}>{row.strategy_label ?? row.strategy ?? "—"}</td>
                  <td>{row.symbol ?? "—"}{row.timeframe ? ` · ${row.timeframe}` : ""}</td>
                  <td className={prov.cls} style={{ fontFamily: "var(--sans)" }}>{t(prov.label)}</td>
                  {/* An untrusted run keeps its number but loses the up/down
                      colour: green on a synthetic candle reads as a result. */}
                  <td className={prov.trusted ? ret.cls : "ft-dim"} style={{ textAlign: "right" }}>{ret.text}</td>
                  <td><a className="ft-link" role="button" tabIndex={0}
                    onClick={() => setOpenRun(row.run_id ?? null)}
                    onKeyDown={activateOnKey(() => setOpenRun(row.run_id ?? null))}>{t("開報告 →")}</a></td>
                </tr>
              );
            })}
          </tbody>
        </table>
        </>
      )}
    </div>
  );
}

interface BriefIndexRow {
  brief_id?: string;
  created_at?: string;
}

export function NewsPage({ heading, items, digest }: {
  heading: React.ReactNode;
  items: {
    item_id?: string;
    title?: string;
    source?: string;
    age_minutes?: number;
    url?: string;
    held_symbols?: string[];
    watched_symbols?: string[];
    relevance?: string;
  }[];
  digest: {
    items?: Record<string, { title_zh?: string; summary_zh?: string }>;
    sections?: { category?: string; title_zh?: string; summary_zh?: string }[];
    updated_at?: string;
  } | null;
}) {
  const { t, lang } = useT();
  const [briefs, setBriefs] = useState<BriefIndexRow[]>([]);
  const [openBrief, setOpenBrief] = useState<string | null>(null);
  useEffect(() => {
    void getJson<{ research_brief_index?: { briefs?: BriefIndexRow[] } | BriefIndexRow[] }>("/api/news").then((value) => {
      const index = value?.research_brief_index;
      setBriefs(Array.isArray(index) ? index : index?.briefs ?? []);
    });
  }, [openBrief]);

  if (openBrief) return <NewsBriefReader briefId={openBrief} onBack={() => setOpenBrief(null)} />;
  // Owner call (R3): no brief index here — headlines with AI summaries ARE the
  // page. Finished briefs stay reachable from the wall's activity feed.
  void briefs;
  void setOpenBrief;
  // 中文可讀 = AI 已整理 ∪ 台股原生中文源(不需要翻譯),一律最新在前。
  const readable = items
    .filter((item) => (item.item_id && digest?.items?.[item.item_id]) || isZhNative(item))
    .sort((a, b) => (a.age_minutes ?? 9e9) - (b.age_minutes ?? 9e9));
  // A flat list of ninety-nine headlines made the reader do the sorting: a
  // third of it was crypto for someone who holds none, beside a Turkish bank
  // licence and the receipt-lottery numbers. Grouping by what it is worth to
  // him puts his own positions first and folds the rest away with a count —
  // nothing is deleted, so "irrelevant" stays checkable.
  const bucket = (name: string) => readable.filter((item) => (item.relevance ?? "global") === name);
  const mine = bucket("mine");
  const twNews = bucket("tw").slice(0, 20);
  const global = bucket("global").slice(0, 12);
  const noise = bucket("noise");
  const translated = readable.slice(0, 25);
  // A "summary" that is a raw headline in a language nobody asked for is not a
  // summary; the section claims to be AI-organised, so only show the ones that
  // actually were.
  // A section whose "title" is verbatim one of the headlines below it was
  // pasted, not summarised — and the block claims to be AI-organised. Lottery
  // draws are dropped for the same reason they are dropped from the list.
  const headlineSet = new Set(items.map((item) => String(item.title ?? "").trim()));
  const realSections = (digest?.sections ?? []).filter((section) => {
    const title = String(section.title_zh ?? "").trim();
    if (!title || headlineSet.has(title)) return false;
    if (/統一發票|開獎|中獎|今彩|威力彩/.test(title + String(section.summary_zh ?? ""))) return false;
    return /[一-鿿]/.test(title);
  });
  const originals = items.filter((item) => !readable.includes(item));
  const otherHeadlines = [
    ...originals.filter((item) => (item.held_symbols?.length ?? 0) + (item.watched_symbols?.length ?? 0) > 0),
    ...originals.filter((item) => (item.held_symbols?.length ?? 0) + (item.watched_symbols?.length ?? 0) === 0)
  ];

  return (
    <div className="ft-page" data-testid="workspace-news">
      {heading}
      {realSections.length > 0 ? (
        <>
          <div className="ft-h2">{t("今日速覽(AI 整理)")}{digest?.updated_at ? <span className="r ft-dim">{ageLabel(digest.updated_at, lang).text}</span> : null}</div>
          <div style={{ padding: "6px 14px 10px", borderBottom: "1px solid var(--line)" }}>
            {realSections.map((section, index) => (
              <div key={index} style={{ fontSize: 13, margin: "4px 0" }}>
                <b className="ft-am">{section.title_zh}</b>
                {section.summary_zh ? <span className="ft-dim"> — {section.summary_zh}</span> : null}
              </div>
            ))}
          </div>
        </>
      ) : null}
      {items.length === 0 ? (
        <div className="ft-empty">{t("尚無新聞快取")}</div>
      ) : (
        <>
          {([
            ["跟你有關(持股與追蹤中)", mine],
            ["台股與總經", twNews],
            ["國際與其他", global]
          ] as Array<[string, typeof mine]>).map(([label, group]) =>
            group.length === 0 ? null : (
              <div key={label}>
                <div className="ft-h2">{t(label)} <span className="r ft-dim">{group.length}</span></div>
                {group.map((item) => {
                  const entry = digest?.items?.[item.item_id ?? ""];
                  return (
                    <div className="ft-nw" key={item.item_id ?? item.title}>
                      <div className="h">
                        {(item.held_symbols?.length ?? 0) > 0 ? (
                          <b className="ft-am">[{t("我的持股")} {item.held_symbols!.join(" ")}] </b>
                        ) : null}
                        {(item.watched_symbols?.length ?? 0) > 0 ? (
                          <b className="ft-dim">[{t("追蹤中")} {item.watched_symbols!.join(" ")}] </b>
                        ) : null}
                        {entry?.title_zh ?? item.title}
                        {item.url ? (
                          <span className="ft-faint" style={{ fontSize: 11 }}> · <a className="ft-link" href={item.url} target="_blank" rel="noreferrer noopener">{t("原文 ↗")}</a></span>
                        ) : null}
                      </div>
                      {entry?.summary_zh ? <div className="s" style={{ fontFamily: "var(--sans)" }}>{entry.summary_zh}</div> : null}
                      <div className="s">{item.source} · {typeof item.age_minutes === "number" ? minutesToAge(item.age_minutes, lang) : ""}</div>
                    </div>
                  );
                })}
              </div>
            )
          )}
          {mine.length === 0 ? (
            <div className="ft-note">{t("今天沒有直接提到你持股或追蹤標的的新聞——這是事實,不是漏抓。")}</div>
          ) : null}
          {noise.length > 0 ? (
            <div className="ft-note s">
              {t("另收起")} {noise.length} {t("則沒有投資內容的(開獎號碼、論壇板塊頁之類)。要看就跟 AI 說「把收起來的新聞也show出來」。")}
            </div>
          ) : null}
          {/* Thirty untranslated headlines, most of them crypto for someone who
              holds none, was the tail end of the same problem the grouping
              above fixes. Anything touching his positions is lifted out of the
              dump; the rest is trimmed to a readable few and the true count is
              stated rather than quietly hidden. */}
          <div className="ft-h2" style={{ marginTop: 8 }}>{t("其他原文頭條")} <span className="r ft-dim">
            {t("顯示")} {Math.min(otherHeadlines.length, 8)} / {originals.length} · {t("要整理哪條跟 AI 說")}
          </span></div>
          {otherHeadlines.slice(0, 8).map((item) => (
            <div className="ft-nw" key={item.item_id ?? item.title}>
              <div className="h ft-dim" style={{ fontSize: 12 }}>
                {(item.held_symbols?.length ?? 0) > 0 ? (
                  <b className="ft-am">[{t("我的持股")} {item.held_symbols!.join(" ")}] </b>
                ) : null}
                {(item.watched_symbols?.length ?? 0) > 0 ? (
                  <b className="ft-dim">[{t("追蹤中")} {item.watched_symbols!.join(" ")}] </b>
                ) : null}
                {item.title}
                {item.url ? (
                  <a className="ft-link" href={item.url} target="_blank" rel="noreferrer noopener" style={{ marginLeft: 6, fontSize: 11 }}>↗</a>
                ) : null}
              </div>
              <div className="s">{item.source} · {typeof item.age_minutes === "number" ? minutesToAge(item.age_minutes, lang) : ""}</div>
            </div>
          ))}
        </>
      )}
    </div>
  );
}
