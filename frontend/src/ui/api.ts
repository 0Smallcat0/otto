// M27 API layer — thin typed slices over the local terminal's read endpoints.
// The AI operates the terminal through these same endpoints; this UI only reads.

import { useEffect, useRef, useState } from "react";

export async function getJson<T>(path: string): Promise<T | null> {
  try {
    const response = await fetch(path, { headers: { Accept: "application/json" } });
    if (!response.ok) return null;
    return (await response.json()) as T;
  } catch {
    return null;
  }
}

/** Poll an endpoint; refetch on an interval and on demand. */
export function usePoll<T>(path: string, intervalMs: number): { data: T | null; reload: () => void } {
  const [data, setData] = useState<T | null>(null);
  const [tick, setTick] = useState(0);
  const alive = useRef(true);
  useEffect(() => {
    alive.current = true;
    void getJson<T>(path).then((value) => {
      if (alive.current && value !== null) setData(value);
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
  return { data, reload: () => setTick((n) => n + 1) };
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
