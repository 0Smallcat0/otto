// M27 細讀模式 — finished research rendered as documents, not panels.

import { useEffect, useState } from "react";
import { ageLabel, fmt, getJson, hhmm, isZhNative, minutesToAge, num, pct } from "./api";

const TRADE_COL_LABELS: Record<string, string> = {
  side: "方向", quantity: "數量", price: "價格", fee: "手續費",
  filled_at: "成交時間", signal_closed_at: "訊號平倉"
};
import { useT } from "./i18n";

/* ── shared doc chrome ── */

function DocShell({ onBack, children }: { onBack: () => void; children: React.ReactNode }) {
  const { t } = useT();
  return (
    <div className="ft-doc-wrap">
      <a className="ft-link ft-mono" onClick={onBack}>{t("← 回任務牆")}</a>
      <div className="ft-doc">{children}</div>
    </div>
  );
}

function Loading({ text }: { text: string }) {
  return <div className="ft-empty">{text}</div>;
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
          <thead><tr>{tradeCols.map((col) => <th key={col}>{t(TRADE_COL_LABELS[col] ?? col)}</th>)}</tr></thead>
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
        <table className="ft-table">
          <thead><tr><th>{t("時間")}</th><th>{t("策略")}</th><th>{t("標的")}</th><th style={{ textAlign: "right" }}>{t("報酬")}</th><th></th></tr></thead>
          <tbody>
            {rows.map((row) => {
              const ret = pct(row.return_pct);
              return (
                <tr key={row.run_id}>
                  <td>{runTime(row.run_id)}</td>
                  <td style={{ fontFamily: "var(--sans)" }}>{row.strategy_label ?? row.strategy ?? "—"}</td>
                  <td>{row.symbol ?? "—"}{row.timeframe ? ` · ${row.timeframe}` : ""}</td>
                  <td className={ret.cls} style={{ textAlign: "right" }}>{ret.text}</td>
                  <td><a className="ft-link" onClick={() => setOpenRun(row.run_id ?? null)}>{t("開報告 →")}</a></td>
                </tr>
              );
            })}
          </tbody>
        </table>
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
  items: { item_id?: string; title?: string; source?: string; age_minutes?: number; url?: string }[];
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
  const translated = readable.slice(0, 25);
  const originals = items.filter((item) => !readable.includes(item));
  return (
    <div className="ft-page" data-testid="workspace-news">
      {heading}
      {(digest?.sections?.length ?? 0) > 0 ? (
        <>
          <div className="ft-h2">{t("今日速覽(AI 整理)")}{digest?.updated_at ? <span className="r ft-dim">{ageLabel(digest.updated_at, lang).text}</span> : null}</div>
          <div style={{ padding: "6px 14px 10px", borderBottom: "1px solid var(--line)" }}>
            {(digest?.sections ?? []).map((section, index) => (
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
          <div className="ft-h2">{t("中文頭條(台股原生+AI 整理)")} <span className="r ft-dim">{translated.length}</span></div>
          {translated.length === 0 ? (
            <div className="ft-note">{t("尚未整理——跟 AI 說「補新聞摘要」即可")}</div>
          ) : (
            translated.map((item) => {
              const entry = digest?.items?.[item.item_id ?? ""];
              return (
                <div className="ft-nw" key={item.item_id ?? item.title}>
                  <div className="h">
                    {entry?.title_zh ?? item.title}
                    {item.url ? (
                      <span className="ft-faint" style={{ fontSize: 11 }}> · <a className="ft-link" href={item.url} target="_blank" rel="noreferrer noopener">{t("原文 ↗")}</a></span>
                    ) : null}
                  </div>
                  {entry?.summary_zh ? <div className="s" style={{ fontFamily: "var(--sans)" }}>{entry.summary_zh}</div> : null}
                  <div className="s">{item.source} · {typeof item.age_minutes === "number" ? minutesToAge(item.age_minutes, lang) : ""}</div>
                </div>
              );
            })
          )}
          <div className="ft-h2" style={{ marginTop: 8 }}>{t("其他原文頭條")} <span className="r ft-dim">
            {originals.length} · {t("要整理哪條跟 AI 說")}
          </span></div>
          {originals.slice(0, 30).map((item) => (
            <div className="ft-nw" key={item.item_id ?? item.title}>
              <div className="h ft-dim" style={{ fontSize: 12 }}>
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
