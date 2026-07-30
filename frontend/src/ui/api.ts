// M27 API layer — thin typed slices over the local terminal's read endpoints.
// The AI operates the terminal through these same endpoints; this UI only reads.

import { useEffect, useRef, useState } from "react";
import type { KeyboardEvent } from "react";

/** Enter/Space activation for things that are clickable but are not buttons.
 *  Always pair with tabIndex={0}, or the element never enters the tab order
 *  and the handler can never fire. */
export function activateOnKey(run: () => void) {
  return (event: KeyboardEvent<Element>) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      run();
    }
  };
}

export async function getJson<T>(path: string): Promise<T | null> {
  try {
    const response = await fetch(path, { headers: { Accept: "application/json" } });
    if (!response.ok) return null;
    return (await response.json()) as T;
  } catch {
    return null;
  }
}

/** Poll an endpoint; refetch on an interval and on demand.
 *  `settled` flips once the first fetch resolves — success or failure — so a
 *  column can tell "still loading" from "genuinely empty" instead of claiming
 *  there is no data while the very first request is still in flight. */
export function usePoll<T>(path: string, intervalMs: number): { data: T | null; settled: boolean; reload: () => void } {
  const [data, setData] = useState<T | null>(null);
  const [settled, setSettled] = useState(false);
  const [tick, setTick] = useState(0);
  const alive = useRef(true);
  useEffect(() => {
    alive.current = true;
    void getJson<T>(path).then((value) => {
      if (!alive.current) return;
      if (value !== null) setData(value);
      setSettled(true);
    });
    const timer = intervalMs > 0
      ? window.setInterval(() => {
          void getJson<T>(path).then((value) => {
            if (alive.current && value !== null) setData(value);
          });
        }, intervalMs)
      : 0;
    return () => {
      alive.current = false;
      if (timer) window.clearInterval(timer);
    };
  }, [path, intervalMs, tick]);
  return { data, settled, reload: () => setTick((n) => n + 1) };
}

/* ── payload slices actually consumed by the wall ── */

export interface Quoteish {
  symbol: string;
  retrieved_at?: string;
  name?: string;
  price?: string;
  change_percent?: string;
  percent_change?: string;
  chg_pct?: string;
  close?: string;
  change?: string;
  date?: string;
}

export interface FredRow {
  series_id: string;
  label: string;
  units: string;
  latest_value: string;
  latest_period: string;
  state: string;
}

export interface MarketsSlice {
  rows?: Quoteish[];
  status?: { last_update?: string; state?: string };
  research_summary?: {
    finnhub_quotes?: { state?: string; rows?: Quoteish[] };
    twelve_data_quotes?: { state?: string; rows?: Quoteish[] };
    twse_quotes?: { state?: string; rows?: Quoteish[] };
    fred_macro?: { state?: string; series?: FredRow[] };
  };
}

export interface CryptoSlice {
  account?: {
    quote_asset?: string;
    initial_cash?: string;
    cash?: string;
    equity?: string;
  };
  /** Cost basis only — no mark. Marks come from `market.rows`, or from
   *  /api/crypto/summary, which is a different payload than this one. */
  positions?: { symbol: string; quantity: string; avg_price: string; realized_pnl?: string }[];
  orders?: { order_id?: string; status?: string }[];
  history?: { created_at?: string; status?: string; side?: string; order_type?: string; symbol?: string }[];
  market?: { rows?: Quoteish[] };
}

export interface ActivityEvent {
  event_id?: string;
  created_at?: string;
  action_id?: string;
  route_id?: string;
  state?: string;
  summary?: string;
  artifact_path?: string;
}

export interface ActivitySlice {
  summary?: { event_count?: number; active_task_state?: string };
  events?: ActivityEvent[];
}

export interface NewsItem {
  item_id?: string;
  title?: string;
  source?: string;
  published_at?: string;
  age_minutes?: number;
  category?: string;
  url?: string;
  /** Positions in the active book this headline mentions, if any. */
  held_symbols?: string[];
  /** Names with a live judgment that this headline mentions. */
  watched_symbols?: string[];
  /** What the headline is worth to the reader: mine | tw | global | noise. */
  relevance?: string;
}

export interface NewsSlice {
  items?: NewsItem[];
  layout?: { watch_terms?: string[] };
  status?: { last_update?: string };
}

/** zh-native feeds need no digest to be readable. */
export function isZhNative(item: NewsItem): boolean {
  const id = item.item_id ?? "";
  return id.startsWith("cna_money-") || id.startsWith("cnyes_tw-") || /[一-鿿]/.test(item.title ?? "");
}

export interface DigestSlice {
  items?: Record<string, { title_zh?: string; summary_zh?: string }>;
  sections?: { category?: string; title_zh?: string; summary_zh?: string }[];
  updated_at?: string;
  origin?: string;
}

export interface WatchlistSlice {
  groups?: { crypto?: string[]; us?: string[]; tw?: string[]; fx?: string[] };
}

export interface BackupsSlice {
  summary?: { protected_file_count?: number; backup_file_count?: number; keep_backups?: number };
}

export interface SecretsStatusSlice {
  stored_provider_ids?: string[];
  eligible_provider_ids?: string[];
  providers?: unknown[];
}

export interface ShellRouteSlice {
  route_id: string;
  label: string;
  path: string;
}

export interface ShellContractSlice {
  routes?: ShellRouteSlice[];
}

export interface LocalStateSlice {
  settings?: { theme?: string; default_route?: string; data_refresh_seconds?: number };
  profile?: { display_name?: string; theme?: string };
  layout?: { active_route?: string };
}

/* ── formatting helpers ── */

/** Smart display formatter: strips provider trailing zeros (61876.00000000 → 61,876). */
export function fmt(value: unknown): string {
  const parsed = typeof value === "string" ? Number.parseFloat(value) : typeof value === "number" ? value : NaN;
  if (!Number.isFinite(parsed)) return String(value ?? "—");
  const abs = Math.abs(parsed);
  const digits = abs >= 1000 ? 2 : abs >= 1 ? 4 : 6;
  return parsed.toLocaleString("en-US", { maximumFractionDigits: digits });
}

export interface CandleRow {
  open?: string;
  high?: string;
  low?: string;
  close?: string;
  closed_at?: string;
}

export function num(value: unknown, digits = 2): string {
  const parsed = typeof value === "string" ? Number.parseFloat(value) : typeof value === "number" ? value : NaN;
  if (!Number.isFinite(parsed)) return "—";
  return parsed.toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

export function pct(value: unknown): { text: string; cls: string } {
  const parsed = typeof value === "string" ? Number.parseFloat(value) : typeof value === "number" ? value : NaN;
  if (!Number.isFinite(parsed)) return { text: "—", cls: "ft-dim" };
  const sign = parsed > 0 ? "+" : "";
  return { text: `${sign}${parsed.toFixed(2)}%`, cls: parsed > 0 ? "ft-up" : parsed < 0 ? "ft-down" : "ft-dim" };
}

export function quotePct(row: Quoteish): { text: string; cls: string } {
  return pct(row.change_percent ?? row.percent_change ?? row.chg_pct);
}

/** Whether a candle series has fallen behind the market it claims to draw.
 *
 *  The chart refreshed itself only when the cache was empty, so a series that
 *  existed was treated as a series that was current: 00982A drew a last bar of
 *  23.83 from three weeks earlier while the stock traded at 20.09, a 16% gap
 *  on the owner's own holding (2026-07-28).
 *
 *  Four days of slack — a weekend plus a holiday on either side of it — so a
 *  Monday morning does not accuse Friday's close of being stale.
 */
export function staleCandles(lastCloseAt?: string, now: Date = new Date()): boolean {
  if (!lastCloseAt) return false;
  const closed = new Date(`${lastCloseAt.slice(0, 10)}T00:00:00Z`);
  if (Number.isNaN(closed.getTime())) return false;
  const today = new Date(`${now.toISOString().slice(0, 10)}T00:00:00Z`);
  return (today.getTime() - closed.getTime()) / 86_400_000 > 4;
}

/** Headlines ordered for the wall's ten-row strip: his money first, junk last.
 *
 *  Freshness alone put none of the four stories touching his holdings in the
 *  top ten of a 120-item feed, while the receipt lottery made it purely by
 *  being minutes newer (2026-07-27 dogfood). Nothing is dropped — noise sinks
 *  and stays readable on the news page under its own count.
 *
 *  Exported so it can be tested: the bug lived in the ordering, not in the
 *  markup, and the ordering was buried inside the component.
 */
export function rankHeadlines<T extends { relevance?: string; age_minutes?: number }>(
  items: readonly T[]
): T[] {
  const rank = (item: T) => (item.relevance === "mine" ? 0 : item.relevance === "noise" ? 2 : 1);
  return [...items].sort(
    (a, b) => rank(a) - rank(b) || (a.age_minutes ?? 9e9) - (b.age_minutes ?? 9e9)
  );
}

/** "MM/DD" of the session a quote belongs to, or "" when the row won't say.
 *
 *  Fetch age answers "is the cache being refreshed"; it does not answer "is
 *  this price current", and on a Monday the two diverge by three days. Every
 *  free tier spells its session differently — TWSE a ROC date (1150724),
 *  Finnhub epoch seconds at the close, Twelve Data an ISO date — so read all
 *  three here rather than in each page. Epoch is read in UTC on purpose: local
 *  getters in UTC+8 rolled Friday's US close onto Saturday and stamped the
 *  rows with a day the market was shut.
 */
export function sessionStamp(row?: Quoteish): string {
  const raw = row as unknown as Record<string, unknown> | undefined;
  const roc = String(raw?.date ?? "");
  if (roc.length >= 7) return `${roc.slice(3, 5)}/${roc.slice(5, 7)}`;
  const day = String(raw?.latest_trading_day ?? "").trim();
  if (!day) return "";
  if (/^\d{4}-\d{2}-\d{2}/.test(day)) return `${day.slice(5, 7)}/${day.slice(8, 10)}`;
  if (!/^\d{9,}$/.test(day)) return "";
  const at = new Date(Number(day) * 1000);
  if (Number.isNaN(at.getTime())) return "";
  return `${String(at.getUTCMonth() + 1).padStart(2, "0")}/${String(at.getUTCDate()).padStart(2, "0")}`;
}

/** The session a whole quote group can honestly claim, and whether it is mixed.
 *
 *  A group is not one session. TWSE publishes its daily file per symbol, so
 *  on 2026-07-28 the same five rows carried two dates: 2330 and 2317 had the
 *  day's close, while 0050, 00982A and 2834 still held 07/27. Stamping the
 *  group from rows[0] certified three stale rows as today — 0050 had fallen
 *  4.24% and the wall showed +0.15% under a header saying it was today's
 *  close. Over-claiming freshness is worse than not claiming it, which is
 *  what the header did before it existed.
 *
 *  So: the oldest session present, never the newest. Nothing is certified
 *  fresher than it is, and `mixed` lets the caller say some rows are newer.
 */
export function sessionSpan(rows: readonly Quoteish[]): { stamp: string; mixed: boolean } {
  const stamps = rows.map((row) => sessionStamp(row)).filter(Boolean);
  if (stamps.length === 0) return { stamp: "", mixed: false };
  const distinct = [...new Set(stamps)].sort();
  // MM/DD compares correctly inside one year. Across a year boundary the
  // December date is the older one even though it sorts last, so pick it.
  const spansNewYear = distinct[0].startsWith("01") && distinct[distinct.length - 1].startsWith("12");
  return {
    stamp: spansNewYear ? distinct[distinct.length - 1] : distinct[0],
    mixed: distinct.length > 1
  };
}

/** "3分前 / 2小時前" — a quote wall must never pass off old numbers as current. */
export function ageLabel(iso?: string, lang: "zh" | "en" = "zh"): { text: string; staleMinutes: number } {
  if (!iso) return { text: "", staleMinutes: Number.POSITIVE_INFINITY };
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return { text: "", staleMinutes: Number.POSITIVE_INFINITY };
  const minutes = Math.max(0, Math.round((Date.now() - then) / 60_000));
  return { text: minutesToAge(minutes, lang), staleMinutes: minutes };
}

export function minutesToAge(minutes: number, lang: "zh" | "en" = "zh"): string {
  if (!Number.isFinite(minutes)) return "";
  if (minutes < 1) return lang === "zh" ? "剛剛" : "now";
  if (minutes < 60) return lang === "zh" ? `${minutes}分前` : `${minutes}m ago`;
  if (minutes < 60 * 24) {
    const hours = Math.round(minutes / 60);
    return lang === "zh" ? `${hours}小時前` : `${hours}h ago`;
  }
  const days = Math.round(minutes / (60 * 24));
  return lang === "zh" ? `${days}天前` : `${days}d ago`;
}

export function mmddhhmm(iso?: string): string {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "—";
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${pad(date.getMonth() + 1)}/${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

export function hhmm(iso?: string): string {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "—";
  return `${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`;
}

export function isToday(iso?: string): boolean {
  if (!iso) return false;
  const date = new Date(iso);
  const now = new Date();
  return date.getFullYear() === now.getFullYear()
    && date.getMonth() === now.getMonth()
    && date.getDate() === now.getDate();
}
