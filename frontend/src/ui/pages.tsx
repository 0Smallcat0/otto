// M27-R2 route pages — read-only, but every list opens up. Click a row to see
// everything the terminal knows about it; anything deeper is one sentence away
// in the conversation.

import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import {
  type ActivitySlice,
  type CandleRow,
  type CryptoSlice,
  type MarketsSlice,
  type Quoteish,
  type WatchlistSlice,
  fmt,
  getJson,
  hhmm,
  isToday,
  mmddhhmm,
  num,
  pct,
  quotePct,
  usePoll,
  activateOnKey
} from "./api";
import { useT } from "./i18n";
// Same loading shape as the wall — a first fetch in flight must not read as
// "nothing here" on these pages either.
import { Skeleton } from "./wall";

/** Timestamps older than today need their date, or a three-day-old row reads
 *  as if it happened this afternoon. */
function stamp(iso?: string): string {
  return isToday(iso) ? hhmm(iso) : mmddhhmm(iso);
}

/** The theme lives on <html data-theme>, written by the shell. Reading it
 *  during render never re-runs, so the displayed value froze at first paint. */
function useThemeName(): string {
  const [theme, setTheme] = useState(() => document.documentElement.dataset.theme ?? "dark");
  useEffect(() => {
    const observer = new MutationObserver(() =>
      setTheme(document.documentElement.dataset.theme ?? "dark")
    );
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    return () => observer.disconnect();
  }, []);
  return theme;
}

function Table({ cols, children, quote }: { cols: string[]; children: ReactNode; quote?: boolean }) {
  return (
    <table className={quote ? "ft-table ft-qt" : "ft-table"}>
      <thead><tr>{cols.map((col) => <th scope="col" key={col}>{col}</th>)}</tr></thead>
      <tbody>{children}</tbody>
    </table>
  );
}

function Empty({ children }: { children: ReactNode }) {
  return <div className="ft-empty">{children}</div>;
}

/* ── 展開詳情:一列攤開它知道的一切 ── */

const FIELD_LABELS: Record<string, string> = {
  open: "開盤", high: "最高", low: "最低", close: "收盤", price: "價格",
  previous_close: "昨收", change: "漲跌", change_percent: "漲跌%", percent_change: "漲跌%",
  chg: "漲跌", chg_pct: "漲跌%", volume: "成交量", vol: "成交量", value: "成交值",
  transaction_count: "成交筆數", bid: "買價", ask: "賣價", currency: "幣別",
  exchange: "交易所", latest_trading_day: "交易日", date: "日期", name: "名稱",
  source: "來源", provider_id: "供應源", state: "狀態"
};

/* ── 圖:crypto 真 K 線;其餘用日內區間條 ── */

function CandleChart({ symbol, market, row }: { symbol: string; market?: string; row?: Record<string, unknown> }) {
  const { t } = useT();
  const [candles, setCandles] = useState<CandleRow[] | null>(null);
  const [timeframe, setTimeframe] = useState("");
  const [fetching, setFetching] = useState(false);
  useEffect(() => {
    let alive = true;
    const load = () =>
      getJson<{ candles?: CandleRow[]; timeframe?: string }>(`/api/markets/candles/${symbol.replace("/", "")}`);
    void (async () => {
      const first = await load();
      if (!alive) return;
      if (first?.candles?.length) {
        setCandles(first.candles);
        setTimeframe(first.timeframe ?? "");
        return;
      }
      // No cache yet → fetch it ourselves instead of telling the user to ask.
      // crypto = public Binance detail (no key); US/FX = one-symbol history
      // pull through the user's stored Twelve Data key. TW has no source yet.
      if (market === "CRYPTO" || market === "US" || market === "FX" || market === "TW") {
        setFetching(true);
        try {
          if (market === "CRYPTO") {
            await fetch("/api/crypto/refresh", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ symbol, timeframe: "15m" })
            });
          } else {
            await fetch("/api/markets/history/refresh", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ symbols: [symbol] })
            });
          }
        } catch {
          /* fall through to the honest empty state */
        }
        // A cold cache or a backend that just restarted can answer empty for a
        // beat. Retry a couple of times before showing the honest empty state —
        // the chart self-heals instead of asking the user to re-expand.
        let result = await load();
        for (let attempt = 0; attempt < 3 && !result?.candles?.length; attempt++) {
          await new Promise((resolve) => setTimeout(resolve, 2500));
          if (!alive) return;
          result = await load();
        }
        if (!alive) return;
        setFetching(false);
        setCandles(result?.candles ?? []);
        setTimeframe(result?.timeframe ?? "");
        return;
      }
      setCandles([]);
    })();
    return () => {
      alive = false;
    };
  }, [symbol, market]);
  if (candles === null || fetching) {
    return (
      <div className="ft-faint" style={{ padding: "6px 0" }} role="status">
        <span className="ft-spin" aria-hidden="true" />
        {fetching ? t("首次抓取 K 線中…(之後就有快取)") : t("讀取中…")}
      </div>
    );
  }
  const rows = candles.slice(-60).map((candle) => ({
    open: Number.parseFloat(candle.open ?? ""),
    high: Number.parseFloat(candle.high ?? ""),
    low: Number.parseFloat(candle.low ?? ""),
    close: Number.parseFloat(candle.close ?? "")
  })).filter((row) => [row.open, row.high, row.low, row.close].every(Number.isFinite));
  if (rows.length < 2) {
    return (
      <>
        {row ? <DayRangeBar row={row} /> : null}
        <div className="ft-faint" style={{ padding: "2px 0 6px" }}>
          {t("這檔暫時抓不到 K 線(來源忙碌或超出配額)——稍後再展開一次即可。")}
        </div>
      </>
    );
  }
  const min = Math.min(...rows.map((row) => row.low));
  const max = Math.max(...rows.map((row) => row.high));
  const span = max - min || 1;
  const width = 760;
  const step = width / rows.length;
  const y = (value: number) => 8 + (1 - (value - min) / span) * 104;
  return (
    <>
    {timeframe ? <div className="ft-cap" style={{ marginTop: 6 }}>{timeframe === "1d" ? t("日線") : t("15 分 K")} · {rows.length}</div> : null}
    <svg width="100%" height="130" viewBox={`0 0 ${width} 130`} preserveAspectRatio="none"
      style={{ background: "var(--bg)", border: "1px solid var(--line)", margin: "6px 0" }}>
      {rows.map((row, index) => {
        const x = index * step + step / 2;
        const up = row.close >= row.open;
        const color = up ? "var(--up)" : "var(--down)";
        const top = y(Math.max(row.open, row.close));
        const bottom = y(Math.min(row.open, row.close));
        return (
          <g key={index}>
            <line x1={x} x2={x} y1={y(row.high)} y2={y(row.low)} stroke={color} strokeWidth="1" />
            <rect x={x - Math.max(step * 0.3, 1)} y={top} width={Math.max(step * 0.6, 2)}
              height={Math.max(bottom - top, 1)} fill={color} />
          </g>
        );
      })}
    </svg>
    </>
  );
}

function DayRangeBar({ row }: { row: Record<string, unknown> }) {
  const { t } = useT();
  const low = Number.parseFloat(String(row.low ?? ""));
  const high = Number.parseFloat(String(row.high ?? ""));
  const open = Number.parseFloat(String(row.open ?? ""));
  const price = Number.parseFloat(String(row.price ?? row.close ?? ""));
  if (![low, high, price].every(Number.isFinite) || high <= low) return null;
  const pct = (value: number) => `${Math.min(Math.max(((value - low) / (high - low)) * 100, 0), 100)}%`;
  const up = Number.isFinite(open) ? price >= open : true;
  return (
    <div style={{ margin: "8px 0 4px" }}>
      <div className="ft-faint" style={{ fontSize: 10.5, letterSpacing: ".1em", marginBottom: 3 }}>{t("日內區間")}</div>
      <div style={{ position: "relative", height: 6, background: "var(--line)", borderRadius: 0 }}>
        {Number.isFinite(open) ? (
          <div style={{ position: "absolute", left: pct(open), top: -2, width: 1, height: 10, background: "var(--faint)" }} />
        ) : null}
        <div style={{ position: "absolute", left: pct(price), top: -3, width: 8, height: 12, marginLeft: -4,
          background: up ? "var(--up)" : "var(--down)" }} />
      </div>
      <div className="ft-mono ft-faint" style={{ display: "flex", justifyContent: "space-between", fontSize: 10.5, marginTop: 2 }}>
        <span>{fmt(low)}</span><span>{fmt(high)}</span>
      </div>
    </div>
  );
}

const DETAIL_FIELD_ORDER = [
  "price", "open", "high", "low", "close", "previous_close", "change",
  "change_percent", "percent_change", "chg", "chg_pct", "volume", "vol",
  "value", "transaction_count", "bid", "ask", "currency", "exchange",
  "date", "name", "source", "state"
];

// TWSE dates arrive as ROC yyyMMdd ("1150707"); show them as a real date.
function fmtRocDate(value: unknown): string {
  const raw = String(value ?? "");
  if (/^1\d{2}\d{4}$/.test(raw)) {
    return `${Number(raw.slice(0, 3)) + 1911}/${raw.slice(3, 5)}/${raw.slice(5, 7)}`;
  }
  return raw;
}

function DetailGrid({ row }: { row: Record<string, unknown> }) {
  const { t } = useT();
  // Whitelisted, ordered fields only — provenance noise (cache paths, doc
  // URLs, epoch stamps) stays in the API for the AI, not on the human grid.
  const entries = DETAIL_FIELD_ORDER
    .filter((key) => row[key] !== "" && row[key] != null && typeof row[key] !== "object")
    .map((key) => [key, row[key]] as const);
  return (
    <div style={{ padding: "10px 14px", borderBottom: "1px solid var(--line)", background: "var(--bg2)" }}>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(150px, 1fr))", gap: "6px 18px" }}>
        {entries.map(([key, value]) => (
          <div key={key} style={{ fontSize: 12 }}>
            <span className="ft-faint">{t(FIELD_LABELS[key] ?? key)} </span>
            <span className="ft-mono">
              {key === "date"
                ? fmtRocDate(value)
                : ["name", "source", "state", "currency", "exchange"].includes(key)
                ? String(value)
                : fmt(value)}
            </span>
          </div>
        ))}
      </div>
      <div className="ft-faint" style={{ marginTop: 8, fontSize: 11.5 }}>
        {t("要看更深(歷史、K 線、基本面),在對話跟 AI 說一聲即可。")}
      </div>
    </div>
  );
}

function QuoteDetailRow({ row, market, name }: { row: Quoteish; market: string; name?: string }) {
  const { t } = useT();
  const [open, setOpen] = useState(false);
  const change = quotePct(row);
  return (
    <>
      <tr onClick={() => setOpen(!open)} tabIndex={0} aria-expanded={open}
        onKeyDown={activateOnKey(() => setOpen(!open))}
        style={{ cursor: "pointer" }}>
        <td className="ft-am">{open ? "▾" : "▸"}</td>
        <td>{row.symbol}</td>
        <td className="ft-dim" style={{ fontFamily: "var(--sans)" }}>{name ?? row.name ?? ""}</td>
        <td>{market}</td>
        <td style={{ textAlign: "right" }}>{fmt(row.price ?? row.close)}</td>
        <td className={change.cls} style={{ textAlign: "right" }}>{change.text}</td>
      </tr>
      {open ? (
        <tr><td colSpan={6} style={{ padding: 0 }}>
          <div style={{ padding: "4px 14px 0", background: "var(--bg2)" }}>
            <CandleChart symbol={row.symbol} market={market} row={row as unknown as Record<string, unknown>} />
          </div>
          <DetailGrid row={row as unknown as Record<string, unknown>} />
        </td></tr>
      ) : null}
    </>
  );
}

/* ── Markets:分組報價 + 展開詳情 ──
   (FRED 總經已全面退出 UI——owner 定調:總經是背景不是行情。
    它活在新聞速覽引用、對話問答與未來的日曆警示裡。) */

export function MarketsPage({ heading, markets }: { heading: ReactNode; markets: MarketsSlice | null }) {
  const { t } = useT();
  const { data: watchlist } = usePoll<WatchlistSlice>("/api/markets/watchlist", 60_000);
  const research = markets?.research_summary;
  const wanted = watchlist?.groups ?? {};
  const order = (list: string[] | undefined, rows: Quoteish[]): Quoteish[] => {
    if (!list?.length) return rows;
    const bySymbol = new Map(rows.map((row) => [row.symbol, row]));
    return list.map((symbol) => bySymbol.get(symbol) ?? { symbol });
  };
  // Crypto lives on its own page now (owner call): 行情 = 綜合市場(美股/台股/匯率),
  // 加密行情獨立,不在此重複。
  const groups: Array<{ market: string; label: string; rows: Quoteish[] }> = [
    { market: "US", label: "Finnhub", rows: order(wanted.us, research?.finnhub_quotes?.rows ?? []) },
    { market: "TW", label: `TWSE · ${t("延遲")}`, rows: order(wanted.tw, research?.twse_quotes?.rows ?? []) },
    { market: "FX", label: "Twelve Data", rows: order(wanted.fx, (research?.twelve_data_quotes?.rows ?? []).filter((row) => row.symbol.includes("/"))) }
  ];
  const total = groups.reduce((count, group) => count + group.rows.length, 0);
  // 今日焦點 — strongest/weakest across everything watched, straight from the
  // rows already on screen. This replaced the FRED macro table (owner call:
  // macro is context, not a quote; it now lives in news 速覽 + conversation).
  const movers = groups
    .flatMap((group) => group.rows.map((row) => ({ row, market: group.market })))
    .map((entry) => ({ ...entry, pct: Number.parseFloat(String(entry.row.change_percent ?? entry.row.percent_change ?? entry.row.chg_pct ?? "")) }))
    .filter((entry) => Number.isFinite(entry.pct));
  const best = movers.length >= 2 ? movers.reduce((a, b) => (b.pct > a.pct ? b : a)) : null;
  const worst = movers.length >= 2 ? movers.reduce((a, b) => (b.pct < a.pct ? b : a)) : null;
  return (
    <div className="ft-page" data-testid="workspace-markets">
      {heading}
      {best && worst && best !== worst ? (
        <div className="ft-stat">
          {t("今日焦點")}: {t("最強")} <b className="ft-up">{best.row.symbol} +{best.pct.toFixed(2)}%</b>
          {" · "}{t("最弱")} <b className="ft-down">{worst.row.symbol} {worst.pct.toFixed(2)}%</b>
          {" · "}<span className="ft-dim">{movers.length} {t("檔監看中")}</span>
        </div>
      ) : null}
      <div className="ft-note">{t("點任一列展開它的完整數據;要改監看清單,在對話說「幫我盯○○」(每組最多 20 檔)。")}</div>
      {total === 0 ? (
        <Empty>{t("尚無報價快取——在對話請 AI 刷新公開行情。")}</Empty>
      ) : (
        <Table quote cols={["", t("代號"), t("名稱"), t("市場"), t("價格"), t("漲跌")]}>
          {groups.flatMap((group) =>
            group.rows.map((row) => (
              <QuoteDetailRow key={`${group.market}-${row.symbol}`} row={row} market={group.market} />
            ))
          )}
        </Table>
      )}
    </div>
  );
}

/* ── Crypto:純加密市場行情(紙上帳本已拆到 PaperPage)── */

export function CryptoPage({ heading, crypto }: { heading: ReactNode; crypto: CryptoSlice | null }) {
  const { t } = useT();
  const marketRows = crypto?.market?.rows ?? [];
  return (
    <div className="ft-page" data-testid="workspace-crypto">
      {heading}
      <div className="ft-note">{t("加密市場行情(Binance 公開資料)。")}</div>
      <div className="ft-h2">{t("市場行情")} <span className="r ft-dim">Binance · {t("公開資料")}</span></div>
      {marketRows.length === 0 ? (
        <div className="ft-note">{t("尚無行情快取")}</div>
      ) : (
        <Table quote cols={["", t("代號"), t("名稱"), t("市場"), t("價格"), t("漲跌")]}>
          {marketRows.map((row) => (
            <QuoteDetailRow key={row.symbol} row={row} market="CRYPTO" />
          ))}
        </Table>
      )}
    </div>
  );
}

/* ── Paper:AI 的紙上交易帳本(從 Crypto 拆出,獨立成頁)── */

interface EquityPaperSlice {
  account?: { quote_asset?: string; cash?: string; equity?: string; initial_cash?: string; total_pnl?: string };
  positions?: Record<string, string>[];
  recent_orders?: Record<string, string>[];
}

/** One equity paper book. Two of the three books had no UI at all: the terminal
 *  ran a TW book with a real position and six figures of P&L that could only be
 *  seen through the API, so the discipline the agent actually practises — the
 *  cap, the staged trims, the rationale on every order — was invisible. */
function EquityPaperBook({ path, label }: { path: string; label: string }) {
  const { t } = useT();
  const { data, settled } = usePoll<EquityPaperSlice>(path, 60_000);
  const account = data?.account;
  const positions = data?.positions ?? [];
  const orders = (data?.recent_orders ?? []).slice(0, 6);
  if (!settled && !data) return <><div className="ft-h2">{label}</div><Skeleton rows={3} /></>;
  if (!account) return <><div className="ft-h2">{label}</div><div className="ft-note">{t("讀不到這本帳")}</div></>;
  const pnl = Number.parseFloat(String(account.total_pnl ?? ""));
  const initial = Number.parseFloat(String(account.initial_cash ?? ""));
  const pnlPct = Number.isFinite(pnl) && initial > 0 ? (pnl / initial) * 100 : NaN;
  const pnlView = Number.isFinite(pnlPct) ? pct(pnlPct) : null;
  return (
    <>
      <div className="ft-h2" style={{ marginTop: 10 }}>{label}</div>
      <div className="ft-stat">
        {t("權益")} <b>{num(account.equity, 0)}</b> {account.quote_asset} · {t("現金")} <b>{num(account.cash, 0)}</b>
        {Number.isFinite(pnl) ? (
          <>
            {" · "}{t("損益")} <b className={pnlView?.cls}>{pnl > 0 ? "+" : ""}{num(pnl, 0)}</b>
            {pnlView ? <span className={pnlView.cls}> {pnlView.text}</span> : null}
          </>
        ) : null}
      </div>
      {positions.length === 0 ? (
        <div className="ft-note">{t("此帳本無持倉")}</div>
      ) : (
        <Table cols={[t("代號"), t("數量"), t("成本"), t("現價"), t("未實現"), t("已實現")]}>
          {positions.map((position) => {
            const view = pct(
              Number.parseFloat(String(position.avg_price ?? "")) > 0
                ? ((Number.parseFloat(String(position.last_price ?? "")) -
                    Number.parseFloat(String(position.avg_price ?? ""))) /
                    Number.parseFloat(String(position.avg_price ?? ""))) * 100
                : NaN
            );
            return (
              <tr key={position.symbol}>
                <td>{position.symbol}</td>
                <td>{fmt(position.quantity)}</td>
                <td>{num(position.avg_price)}</td>
                <td>{num(position.last_price)}</td>
                <td className={view.cls}>{view.text}</td>
                <td className="ft-dim">{num(position.realized_pnl, 0)}</td>
              </tr>
            );
          })}
        </Table>
      )}
      {orders.length === 0 ? null : (
        <Table cols={[t("時間"), t("代號"), t("方向"), t("數量"), t("狀態"), t("理由")]}>
          {orders.map((order) => (
            <tr key={order.order_id}>
              <td>{mmddhhmm(order.created_at)}</td>
              <td>{order.symbol}</td>
              <td className={order.side === "BUY" ? "ft-up" : "ft-down"}>{order.side}</td>
              <td>{fmt(order.quantity)}</td>
              <td className="ft-dim">{order.status}</td>
              {/* The rationale is the whole point of a journaled paper book. */}
              <td className="s" style={{ maxWidth: 420 }}>{order.rationale ?? "—"}</td>
            </tr>
          ))}
        </Table>
      )}
    </>
  );
}

export function PaperPage({ heading, crypto }: { heading: ReactNode; crypto: CryptoSlice | null }) {
  const { t } = useT();
  const orders = (crypto?.orders ?? []) as Record<string, string>[];
  const history = ((crypto?.history ?? []) as Record<string, string>[]).slice(0, 30);
  const account = crypto?.account;
  return (
    <div className="ft-page" data-testid="workspace-paper">
      {heading}
      <div className="ft-note">{t("AI 的紙上交易帳本(模擬,非實盤;實盤閘門由後端鎖定)。三本各自獨立計價,不換匯。")}</div>
      <EquityPaperBook path="/api/equity/tw/summary?refresh=true" label={t("台股紙上帳(TWD)")} />
      <EquityPaperBook path="/api/equity/summary?refresh=true" label={t("美股紙上帳(USD)")} />
      <div className="ft-h2" style={{ marginTop: 10 }}>{t("加密紙上帳(USDT)")}</div>
      <div className="ft-stat">
        {t("權益")} <b>{num(account?.equity)}</b> {account?.quote_asset ?? "USDT"} · {t("現金")} <b>{num(account?.cash)}</b> · {t("起始")} {num(account?.initial_cash, 0)}
      </div>
      <div className="ft-h2">{t("掛單")}</div>
      {orders.filter((order) => order.status === "WORKING").length === 0 ? (
        <div className="ft-note">{t("無掛單")}</div>
      ) : (
        <Table cols={["order", t("方向"), t("型態"), t("數量"), t("限價"), t("狀態")]}>
          {orders.filter((order) => order.status === "WORKING").map((order) => (
            <tr key={order.order_id}>
              <td>{order.order_id}</td>
              <td className={order.side === "BUY" ? "ft-up" : "ft-down"}>{order.side}</td>
              <td>{order.order_type ?? order.type}</td>
              <td>{fmt(order.quantity)}</td>
              <td>{order.limit_price ? num(order.limit_price) : "—"}</td>
              <td className="ft-am">{order.status}</td>
            </tr>
          ))}
        </Table>
      )}
      <div className="ft-h2" style={{ marginTop: 8 }}>{t("近 30 筆委託紀錄")} <span className="r ft-dim">{t("含測試探針")}</span></div>
      {history.length === 0 ? (
        <Empty>{t("尚無交易——AI 下的每一筆紙上單都會留在這裡。")}</Empty>
      ) : (
        <Table cols={[t("時間"), "order", t("方向"), t("型態"), t("數量"), t("狀態")]}>
          {history.map((row) => (
            <tr key={row.order_id ?? row.created_at}>
              <td>{mmddhhmm(row.created_at)}</td>
              <td>{row.order_id}</td>
              <td className={row.side === "BUY" ? "ft-up" : "ft-down"}>{row.side}</td>
              <td>{row.order_type ?? row.type}</td>
              <td>{fmt(row.quantity)}</td>
              <td className="ft-dim">{row.status}</td>
            </tr>
          ))}
        </Table>
      )}
    </div>
  );
}

/* ── Portfolio:帳本展開 ── */

interface PortfolioSlice {
  active_portfolio_id?: string;
  portfolios?: { portfolio_id?: string; name?: string; owner?: string; currency?: string; source?: string }[];
  positions?: Record<string, string>[];
}

interface BookDetail {
  book?: {
    positions?: Record<string, string>[];
    transactions?: Record<string, string>[];
  };
}

function BookRow({ book, active }: {
  book: { portfolio_id?: string; name?: string; owner?: string; currency?: string; source?: string };
  active: boolean;
}) {
  const { t } = useT();
  const [open, setOpen] = useState(false);
  const [detail, setDetail] = useState<BookDetail | null>(null);
  useEffect(() => {
    if (open && !detail && book.portfolio_id) {
      void getJson<BookDetail>(`/api/portfolio/books/${book.portfolio_id}`).then(setDetail);
    }
  }, [open, detail, book.portfolio_id]);
  const positions = detail?.book?.positions ?? [];
  const transactions = (detail?.book?.transactions ?? []).slice(0, 10);
  return (
    <>
      <tr onClick={() => setOpen(!open)} tabIndex={0} aria-expanded={open}
        onKeyDown={activateOnKey(() => setOpen(!open))}
        style={{ cursor: "pointer" }}>
        {/* The active dot used to replace the expand chevron, so an owner with a
            single (always-active) book saw a one-row table with no hint that it
            opens onto his holdings. Show both: state and affordance. */}
        <td className="ft-am" style={{ whiteSpace: "nowrap" }}>
          {active ? "●" : ""}
          <span className="ft-faint">{open ? "▾" : "▸"}</span>
        </td>
        <td style={{ fontFamily: "var(--sans)" }}>{book.name}</td>
        <td className="ft-dim">{book.owner}</td>
        <td>{book.currency}</td>
        <td className="ft-dim">{t(SOURCE_ZH[book.source ?? ""] ?? book.source ?? "")}</td>
      </tr>
      {open ? (
        <tr><td colSpan={5} style={{ padding: "10px 14px", background: "var(--bg2)" }}>
          {!detail ? (
            <span className="ft-faint" role="status"><span className="ft-spin" aria-hidden="true" />{t("讀取中…")}</span>
          ) : (
            <>
              <div className="ft-cap" style={{ marginBottom: 4 }}>{t("持倉")}</div>
              {positions.length === 0 ? (
                <div className="ft-faint" style={{ marginBottom: 8 }}>{t("此帳本無持倉")}</div>
              ) : (
                <Table cols={[t("代號"), t("數量"), t("成本"), t("現價"), t("未實現"), t("市值")]}>
                  {positions.map((position) => {
                    // Cost and price without the P&L made the reader do the
                    // arithmetic on his own holdings; the money is the point.
                    const cost = Number.parseFloat(String(position.avg_cost ?? position.avg_price ?? ""));
                    const last = Number.parseFloat(String(position.last_price ?? ""));
                    const qty = Number.parseFloat(String(position.quantity ?? ""));
                    const gainPct = Number.isFinite(cost) && cost > 0 && Number.isFinite(last)
                      ? ((last - cost) / cost) * 100
                      : NaN;
                    const view = Number.isFinite(gainPct) ? pct(gainPct) : null;
                    const value = Number.isFinite(qty) && Number.isFinite(last) ? qty * last : NaN;
                    return (
                      <tr key={position.symbol}>
                        <td>{position.symbol}</td>
                        <td>{fmt(position.quantity)}</td>
                        <td>{num(position.avg_cost ?? position.avg_price)}</td>
                        <td>
                          {num(position.last_price)}
                          {position.price_basis === "cost_basis" ? <small className="ft-faint"> {t("(成本)")}</small>
                            : position.price_basis === "stale_history_close" ? <small className="ft-am"> {t("(舊)")}</small>
                            : null}
                        </td>
                        <td className={view?.cls}>{view ? view.text : "—"}</td>
                        <td>{Number.isFinite(value) ? num(value, 0) : "—"}</td>
                      </tr>
                    );
                  })}
                </Table>
              )}
              <div className="ft-cap" style={{ margin: "10px 0 4px" }}>{t("近 10 筆交易")}</div>
              {transactions.length === 0 ? (
                <div className="ft-faint">{t("無交易紀錄")}</div>
              ) : (
                <Table cols={[t("時間"), t("代號"), t("方向"), t("數量"), t("價格")]}>
                  {transactions.map((txn, index) => (
                    <tr key={txn.transaction_id ?? index}>
                      <td>{mmddhhmm(txn.executed_at ?? txn.created_at)}</td>
                      <td>{txn.symbol}</td>
                      <td className={txn.side === "BUY" ? "ft-up" : "ft-down"}>{txn.side}</td>
                      <td>{txn.quantity}</td>
                      <td>{num(txn.price)}</td>
                    </tr>
                  ))}
                </Table>
              )}
            </>
          )}
        </td></tr>
      ) : null}
    </>
  );
}

const SOURCE_ZH: Record<string, string> = {
  demo: "示範資料",
  paper_ledger: "紙上帳本鏡像",
  backtest: "回測結果鏡像",
  import_json: "匯入",
  manual: "手動建立"
};

export function PortfolioPage({ heading }: { heading: ReactNode }) {
  const { t } = useT();
  const { data, settled } = usePoll<PortfolioSlice>("/api/portfolio", 60_000);
  const books = data?.portfolios ?? [];
  return (
    <div className="ft-page" data-testid="workspace-portfolio">
      {heading}
      <div className="ft-note">{t("「帳本」=一組持倉的紀錄簿。AI 可建立、鏡像紙上或回測結果、依對話切換 active(●)。")}</div>
      <div className="ft-h2">{t("帳本(active 由 AI 依對話切換)")}</div>
      {books.length === 0 && !settled ? (
        <Skeleton rows={4} />
      ) : books.length === 0 ? (
        <Empty>{t("尚無帳本——在對話請 AI 建立或連結。")}</Empty>
      ) : (
        <Table cols={["", t("名稱"), t("擁有者"), t("幣別"), t("來源")]}>
          {books.map((book) => (
            <BookRow key={book.portfolio_id} book={book} active={book.portfolio_id === data?.active_portfolio_id} />
          ))}
        </Table>
      )}
    </div>
  );
}

/* ── Algo ── */

interface AlgoSlice {
  active_strategy_id?: string;
  strategies?: { strategy_id?: string; name?: string; symbol?: string; timeframe?: string; updated_at?: string }[];
  last_scan?: { scan_id?: string; artifact_dir?: string } | null;
  last_backtest?: { artifact_dir?: string } | null;
}

export function AlgoPage({ heading, onOpenArtifact }: { heading: ReactNode; onOpenArtifact: (path: string) => void }) {
  const { t } = useT();
  const { data, settled } = usePoll<AlgoSlice>("/api/algo", 60_000);
  const strategies = data?.strategies ?? [];
  return (
    <div className="ft-page" data-testid="workspace-algo">
      {heading}
      <div className="ft-note">{t("Algo=AI 的策略研究循環:一句話描述想法(例:「建一個 BTC 均線交叉策略」),AI 會建立策略→掃描訊號→跑回測,產出都留在這頁,報告可點開。")}</div>
      <div className="ft-h2">{t("策略庫(建/刪/選都在對話)")}</div>
      {strategies.length === 0 && !settled ? (
        <Skeleton rows={4} />
      ) : strategies.length === 0 ? (
        <Empty>{t("尚無策略——在對話請 AI「幫我建一個○○策略」。")}</Empty>
      ) : (
        <Table cols={["", t("名稱"), t("標的"), t("週期"), t("更新")]}>
          {strategies.map((strategy) => (
            <tr key={strategy.strategy_id}>
              <td className="ft-am">{strategy.strategy_id === data?.active_strategy_id ? "●" : ""}</td>
              <td style={{ fontFamily: "var(--sans)" }}>{strategy.name}</td>
              <td>{strategy.symbol}</td>
              <td>{strategy.timeframe}</td>
              <td className="ft-dim">{stamp(strategy.updated_at)}</td>
            </tr>
          ))}
        </Table>
      )}
      <div className="ft-h2" style={{ marginTop: 8 }}>{t("最新研究產出")}</div>
      <div className="ft-note ft-lede">
        {data?.last_scan?.artifact_dir ? (
          <>{t("訊號掃描")} <span className="ft-mono">{data.last_scan.scan_id}</span> · <a className="ft-link" role="button" tabIndex={0} onClick={() => onOpenArtifact(data.last_scan?.artifact_dir ?? "")} onKeyDown={activateOnKey(() => onOpenArtifact(data.last_scan?.artifact_dir ?? ""))}>{t("開掃描 →")}</a><br /></>
        ) : t("尚無掃描。")}
        {data?.last_backtest?.artifact_dir ? (
          <>{t("策略回測")} · <a className="ft-link" role="button" tabIndex={0} onClick={() => onOpenArtifact(data.last_backtest?.artifact_dir ?? "")} onKeyDown={activateOnKey(() => onOpenArtifact(data.last_backtest?.artifact_dir ?? ""))}>{t("開報告 →")}</a></>
        ) : t(" 尚無策略回測。")}
      </div>
    </div>
  );
}

/* ── Settings:偏好 + 四行系統摘要(細節問 AI,不倒資料表)── */

function PrefsBlock() {
  const { t, lang } = useT();
  const theme = useThemeName();
  const { data } = usePoll<{ profile?: Record<string, unknown>; settings?: Record<string, unknown> }>("/api/local-state", 120_000);
  const profile = (data?.profile ?? {}) as Record<string, unknown>;
  const settings = (data?.settings ?? {}) as Record<string, unknown>;
  return (
    <>
      <div className="ft-h2">{t("偏好")}</div>
      <div className="ft-note">
        {t("顯示名稱")} <b>{String(profile.display_name ?? "Local User")}</b> ·
        {" "}{t("主題")} <b>{theme === "light" ? t("亮") : t("暗")}</b> ·
        {" "}{t("語言")} <b>{lang === "zh" ? "中" : "EN"}</b> ·
        {" "}{t("資料刷新")} <b>{String(settings.data_refresh_seconds ?? 60)}s</b>
        <br />{t("要改任何偏好,在對話說即可;主題與語言也可用頂條即時切換。")}
      </div>
    </>
  );
}

export function SettingsPage({ heading }: { heading: ReactNode }) {
  const { t } = useT();
  const backups = usePoll<{ summary?: { protected_file_count?: number; backup_file_count?: number }; rows?: { backup_count?: number }[] }>("/api/local-state/backups", 60_000);
  const secrets = usePoll<{ stored_provider_ids?: string[]; eligible_provider_ids?: string[] }>("/api/local-secrets/status", 120_000);
  const providers = usePoll<{ summary?: { provider_count?: number; implemented_count?: number; active?: number; stale_cache?: number; key_required?: number } }>("/api/providers", 60_000);
  const stored = secrets.data?.stored_provider_ids?.length ?? 0;
  const eligible = secrets.data?.eligible_provider_ids?.length ?? 0;
  const backupSummary = backups.data?.summary;
  const withBak = (backups.data?.rows ?? []).filter((row) => (row.backup_count ?? 0) > 0).length;
  // Honest counts straight from the provider catalog summary — not "every
  // catalog row is cached", which is what the old per-row read implied.
  const provSummary = providers.data?.summary;
  const activeProviders = provSummary?.active ?? 0;
  const staleCache = provSummary?.stale_cache ?? 0;
  const keyRequired = provSummary?.key_required ?? 0;
  const implemented = provSummary?.implemented_count ?? 0;
  const catalog = provSummary?.provider_count ?? 0;
  return (
    <div className="ft-page" data-testid="workspace-settings">
      {heading}
      <PrefsBlock />
      <div className="ft-h2" style={{ marginTop: 8 }}>{t("系統摘要")}</div>
      <div className="ft-note ft-lede" style={{ lineHeight: 2 }}>
        <span className="ft-up">●</span> {t("安全閘門")}: {t("實盤交易")}/{t("外部執行")}/{t("憑證明文讀取")} {t("全部")} <b className="ft-down">{t("關")}</b>({t("後端鎖定")})<br />
        <span className="ft-up">●</span> {t("資料 Keys")}: <b>{stored}/{eligible}</b> {t("已接")}<br />
        <span className={withBak > 0 ? "ft-up" : "ft-dim"}>●</span> {t("狀態備份")}: <b>{backupSummary?.protected_file_count ?? "—"}</b> {t("檔受保護")} · <b>{withBak}</b> {t("檔已有還原點")}<br />
        <span className={activeProviders > 0 ? "ft-up" : "ft-dim"}>●</span> {t("資料源")}: <b>{activeProviders}</b> {t("活躍")} · <b>{staleCache}</b> {t("快取偏舊")} · <b>{keyRequired}</b> {t("待接 key")} <span className="ft-faint">({implemented} {t("家已實作")} / {catalog} {t("目錄")})</span>
      </div>
      <div className="ft-h2" style={{ marginTop: 8 }}>{t("可以改什麼(對 AI 說的例句)")}</div>
      <Table cols={[t("可改項"), t("例句")]}>
        {[
          ["顯示名稱", "「把顯示名稱改成 Boss」"],
          ["主題", "「幫我預設用亮色主題」"],
          ["語言", "「介面改英文」"],
          ["預設頁", "「打開時直接進 Markets」"],
          ["資料刷新頻率", "「把刷新改成 30 秒」"],
          ["監看清單", "「幫我盯 TSLA 和 2454」"],
          ["新聞監看詞", "「新聞幫我盯『台積電』和『Fed』」"]
        ].map(([what, say]) => (
          <tr key={what}>
            <td style={{ fontFamily: "var(--sans)" }}>{t(what)}</td>
            <td className="ft-dim" style={{ fontFamily: "var(--sans)" }}>{t(say)}</td>
          </tr>
        ))}
      </Table>
      <div className="ft-note ft-faint">{t("想看任一項的完整明細(哪個來源多舊、哪個檔的備份在哪),在對話問 AI 就會攤開給你。")}</div>
    </div>
  );
}

/* ── Profile:已併入 Settings 偏好區(路由保留給 agent-contract)── */

export function ProfilePage({ heading }: { heading: ReactNode }) {
  const { t } = useT();
  return (
    <div className="ft-page" data-testid="workspace-profile">
      {heading}
      <PrefsBlock />
      <div className="ft-note ft-faint">{t("Profile 已與 Settings 合併;此路由保留給 AI 契約與深連結。")}</div>
    </div>
  );
}

/* ── Forum ── */

interface ForumSlice {
  posts?: { post_id?: string; title?: string; created_at?: string; reply_count?: number; channel_id?: string }[];
}

export function ForumPage({ heading }: { heading: ReactNode }) {
  const { t } = useT();
  const { data, settled } = usePoll<ForumSlice>("/api/forum", 120_000);
  const posts = data?.posts ?? [];
  return (
    <div className="ft-page" data-testid="workspace-forum">
      {heading}
      {posts.length === 0 && !settled ? (
        <Skeleton rows={5} />
      ) : posts.length === 0 ? (
        <Empty>{t("尚無研究筆記——AI 的研究記錄與你要求的備忘會存在這裡。")}</Empty>
      ) : (
        <Table cols={[t("時間"), t("標題"), t("頻道"), t("回覆")]}>
          {posts.slice(0, 40).map((post) => (
            <tr key={post.post_id}>
              <td>{stamp(post.created_at)}</td>
              <td style={{ fontFamily: "var(--sans)" }}>{post.title}</td>
              <td className="ft-dim">{post.channel_id}</td>
              <td>{post.reply_count ?? 0}</td>
            </tr>
          ))}
        </Table>
      )}
    </div>
  );
}

/* ── AI 操作路由 ── */

export function AiRoutePage({ heading, routeId, testId, activity }: {
  heading: ReactNode;
  routeId: string;
  testId: string;
  activity: ActivitySlice | null;
}) {
  const { t } = useT();
  const events = (activity?.events ?? []).filter((event) => event.route_id === routeId).slice(0, 20);
  return (
    <div className="ft-page" data-testid={testId}>
      {heading}
      <div className="ft-note">
        {t("這是 AI 專用工作區(不在側欄)。人不需要操作它;下面是 AI 在此路由的最近動作。")}
      </div>
      {events.length === 0 ? (
        <Empty>{t("此路由尚無 AI 活動。")}</Empty>
      ) : (
        <Table cols={[t("時間"), t("動作"), t("狀態"), t("摘要")]}>
          {events.map((event) => (
            <tr key={event.event_id}>
              <td>{stamp(event.created_at)}</td>
              <td>{event.action_id}</td>
              <td className={event.state === "succeeded" ? "ft-up" : "ft-am"}>{event.state}</td>
              <td className="ft-dim" style={{ fontFamily: "var(--sans)" }}>{event.summary}</td>
            </tr>
          ))}
        </Table>
      )}
    </div>
  );
}
