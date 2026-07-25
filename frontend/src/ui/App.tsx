// M27 shell — 任務牆優先;15 個路由殼保留(path/testid/標題與 agent-contract 一致),
// 內容全面重建。輸入端在對話;這個介面只負責「看」。

import { useEffect, useMemo, useState } from "react";
import {
  type ActivitySlice,
  type BackupsSlice,
  type CryptoSlice,
  type LocalStateSlice,
  type MarketsSlice,
  type NewsSlice,
  type DigestSlice,
  type SecretsStatusSlice,
  type ShellContractSlice,
  type WatchlistSlice,
  type ShellRouteSlice,
  activateOnKey,
  getJson,
  hhmm,
  isToday,
  usePoll
} from "./api";
import { Wall } from "./wall";
import { BacktestPage, BacktestRunReader, NewsBriefReader, NewsPage } from "./readers";
import {
  AiRoutePage,
  AlgoPage,
  CryptoPage,
  ForumPage,
  MarketsPage,
  PaperPage,
  PortfolioPage,
  ProfilePage,
  SettingsPage
} from "./pages";
import { AI_OPERATOR_ROUTES, fallbackRoutes } from "../shellData";
import { LangProvider, useT } from "./i18n";

function testIdFor(route: ShellRouteSlice): string {
  return `workspace-${route.path.replace(/^\//, "")}`;
}

function buttonIdFor(route: ShellRouteSlice): string {
  return `route-button-${route.path.replace(/^\//, "")}`;
}

function RouteHeading({ routeId, label }: { routeId?: string; label: string }) {
  const { t } = useT();
  return (
    <div className="ft-page-head">
      <h1>{t(ROUTE_ZH[routeId ?? ""] ?? label)}</h1>
    </div>
  );
}

function PlaceholderPage({ route }: { route: ShellRouteSlice }) {
  const { t } = useT();
  return (
    <div className="ft-page" data-testid={testIdFor(route)}>
      <RouteHeading routeId={route.route_id} label={route.label} />
      <div className="ft-empty">
        {t("此頁由 AI 透過對話與 API 操作,不需要你手動點。")}
      </div>
    </div>
  );
}

const ROUTE_ZH: Record<string, string> = {
  dashboard: "任務牆", markets: "行情", crypto: "加密", paper: "紙上交易", portfolio: "帳本",
  news: "新聞", backtest: "回測", algo: "策略研究", nodes: "工作流", code: "筆記本",
  quant_lab: "量化實驗", quantlib: "計算器", forum: "研究筆記", settings: "系統",
  profile: "偏好", ai_chat: "AI 對話"
};

// Task-level, human-first: what a person can SAY. Curated by hand; the raw
// contract stays available in the fold-out below so nothing is hidden.
const SAYABLE: Array<{ group: string; items: string[] }> = [
  // The judgment ledger is the most useful thing here and this page — where a
  // person learns what to ask for — did not mention it at all, so there was no
  // way to discover it short of noticing the board on the wall. It goes first:
  // it is the reason the rest of the terminal is worth running.
  { group: "判斷(AI 給看法,到期用真實價格驗收)", items: [
    "你對我持股的看法是什麼?",
    "幫我看 2834 現在該怎麼辦",
    "掃一下有什麼標的值得研究",
    "你的判斷準嗎?給我命中率",
    "2834 的估值和有沒有重大訊息"
  ] },
  { group: "看行情", items: [
    "幫我盯 TSLA 和 2454",
    "拉 AAPL 的歷史 K 線",
    "現在 BTC 多少?",
    "刷新一下行情"
  ] },
  { group: "紙上交易(模擬,實盤鎖死)", items: [
    "用紙上帳戶買 0.001 BTC",
    "掛一張 60000 的限價買單",
    "撤掉那張掛單",
    "我現在賺賠多少?"
  ] },
  { group: "回測與策略", items: [
    "回測 BTC 15 分鐘均線交叉",
    "幫這個策略做 walk-forward 驗證",
    "建一個動能策略,掃描有沒有訊號",
    "比較最近幾次回測哪個好"
  ] },
  { group: "新聞", items: [
    "刷新新聞,補中文摘要",
    "出一份新聞簡報",
    "新聞幫我盯「Fed」和「台積電」"
  ] },
  { group: "帳本", items: [
    "建一本新帳本",
    "把剛才的回測做成帳本",
    "切回我的主帳本",
    "這本帳裡有什麼?"
  ] },
  { group: "系統與偏好", items: [
    "備份狀態現在如何?",
    "存這把 API key",
    "把刷新改成 30 秒",
    "介面改英文/亮色"
  ] },
  { group: "隨時可問", items: [
    "今天你做了什麼?",
    "下次 CPI 什麼時候?",
    "這檔為什麼跌?幫我查"
  ] }
];

function SayableItem({ text }: { text: string }) {
  const { t } = useT();
  const [copied, setCopied] = useState(false);
  const copy = () => {
    try {
      void navigator.clipboard.writeText(text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1200);
    } catch {
      /* clipboard unavailable */
    }
  };
  return (
    <div onClick={copy} role="button" tabIndex={0} onKeyDown={activateOnKey(copy)}
      style={{ cursor: "pointer", padding: "5px 10px", margin: "4px 0",
      border: "1px solid var(--line)", background: "var(--bg)", fontSize: 13 }}>
      「{t(text)}」
      <span className="ft-faint" style={{ float: "right", fontSize: 11 }}>
        {copied ? t("已複製 ✓") : t("點擊複製")}
      </span>
    </div>
  );
}

function CapabilitiesDoc({ onBack }: { onBack: () => void }) {
  const { t } = useT();
  const [caps, setCaps] = useState<{ actions?: { action_id?: string; route_id?: string; label?: string }[] } | null>(null);
  const [showRaw, setShowRaw] = useState(false);
  useEffect(() => {
    void getJson<{ actions?: { action_id?: string; route_id?: string; label?: string }[] }>("/api/agent-contract").then(setCaps);
  }, []);
  const actions = caps?.actions ?? [];
  const byRoute = new Map<string, { label?: string }[]>();
  for (const action of actions) {
    const key = action.route_id ?? "other";
    if (!byRoute.has(key)) byRoute.set(key, []);
    byRoute.get(key)?.push(action);
  }
  return (
    <div className="ft-doc-wrap" data-testid="capabilities-doc">
      <a className="ft-link ft-mono" role="button" tabIndex={0} onClick={onBack} onKeyDown={activateOnKey(onBack)}>{t("← 回任務牆")}</a>
      <div className="ft-doc">
        <h1>{t("AI 能做什麼")}</h1>
        <div className="sub">{t("不用記指令——想做什麼,用你的話說。下面每一句都可以直接用(點一下就複製,貼到對話裡)。")}</div>
        {SAYABLE.map((section) => (
          <div key={section.group} style={{ marginBottom: 16 }}>
            <h3>{t(section.group)}</h3>
            {section.items.map((item) => <SayableItem key={item} text={item} />)}
          </div>
        ))}
        <div style={{ marginTop: 20, borderTop: "1px solid var(--line)", paddingTop: 10 }}>
          <a className="ft-link" style={{ fontSize: 12 }} role="button" tabIndex={0} aria-expanded={showRaw}
            onClick={() => setShowRaw(!showRaw)} onKeyDown={activateOnKey(() => setShowRaw(!showRaw))}>
            {showRaw ? "▾" : "▸"} {t("技術明細")}:{actions.length} {t("個底層動作(讀自 agent-contract,新功能自動出現)")}
          </a>
          {showRaw ? (
            Array.from(byRoute.entries()).map(([routeId, routeActions]) => (
              <div key={routeId} style={{ margin: "10px 0" }}>
                <div className="ft-cap">{t(ROUTE_ZH[routeId] ?? routeId)} · {routeActions.length}</div>
                <div className="ft-faint" style={{ fontSize: 11.5, lineHeight: 1.7 }}>
                  {routeActions.map((action) => action.label).filter(Boolean).join(" · ")}
                </div>
              </div>
            ))
          ) : null}
        </div>
      </div>
    </div>
  );
}

function Clock() {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 1000);
    return () => window.clearInterval(timer);
  }, []);
  const pad = (value: number) => String(value).padStart(2, "0");
  return (
    <div className="ft-clock">
      {now.getFullYear()}-{pad(now.getMonth() + 1)}-{pad(now.getDate())} {pad(now.getHours())}:{pad(now.getMinutes())}:{pad(now.getSeconds())}
    </div>
  );
}

export function App() {
  return (
    <LangProvider>
      <Shell />
    </LangProvider>
  );
}

function Shell() {
  const { t, lang, setLang } = useT();
  const [routes, setRoutes] = useState<ShellRouteSlice[]>(fallbackRoutes);
  const [activeRoute, setActiveRoute] = useState("dashboard");
  const [refreshSeconds, setRefreshSeconds] = useState(60);
  const [theme, setTheme] = useState(() => {
    try {
      const saved = window.localStorage.getItem("ft-theme");
      return saved === "light" || saved === "dark" ? saved : "dark";
    } catch {
      return "dark";
    }
  });
  const [artifactPath, setArtifactPath] = useState<string | null>(null);
  const [showCaps, setShowCaps] = useState(false);

  useEffect(() => {
    void (async () => {
      const [contract, state] = await Promise.all([
        getJson<ShellContractSlice>("/api/shell-contract"),
        getJson<LocalStateSlice>("/api/local-state")
      ]);
      if (contract?.routes?.length) setRoutes(contract.routes);
      const seconds = state?.settings?.data_refresh_seconds;
      if (typeof seconds === "number" && seconds >= 5) setRefreshSeconds(seconds);
      // localStorage (the top-strip toggle) wins over the stored preference.
      try {
        if (!window.localStorage.getItem("ft-theme")) {
          const preferred = state?.settings?.theme;
          if (preferred === "light" || preferred === "dark") setTheme(preferred);
        }
      } catch {
        /* private mode */
      }
      const hash = window.location.hash.replace("#/", "");
      const fallback = state?.layout?.active_route || state?.settings?.default_route || "dashboard";
      setActiveRoute(hash || fallback);
      // Auto-load public data once per browser session (kept from the old shell:
      // cached data shows instantly; this refresh job updates it in the background).
      try {
        if (sessionStorage.getItem("local-terminal.autoloaded") !== "1") {
          sessionStorage.setItem("local-terminal.autoloaded", "1");
          void fetch("/api/providers/refresh-public/jobs", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
        }
      } catch {
        /* private mode: skip */
      }
    })();
  }, []);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try {
      window.localStorage.setItem("ft-theme", theme);
    } catch {
      /* private mode */
    }
  }, [theme]);

  useEffect(() => {
    const onHashChange = () => {
      const routeId = window.location.hash.replace("#/", "");
      if (routeId) setActiveRoute(routeId);
    };
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  const pollMs = Math.max(refreshSeconds, 15) * 1000;
  const markets = usePoll<MarketsSlice>("/api/markets", pollMs);

  // Ambient freshness: if the public crypto cache is older than 5 minutes,
  // quietly refresh it (no-key Binance only; throttled so several open tabs
  // do not stampede the provider).
  useEffect(() => {
    const lastUpdate = markets.data?.status?.last_update;
    if (!lastUpdate) return;
    const ageMinutes = (Date.now() - new Date(lastUpdate).getTime()) / 60_000;
    if (!(ageMinutes > 5)) return;
    try {
      const stamp = Number(window.localStorage.getItem("ft-crypto-refresh") || 0);
      if (Date.now() - stamp < 5 * 60_000) return;
      window.localStorage.setItem("ft-crypto-refresh", String(Date.now()));
    } catch {
      /* private mode: still refresh, just unthrottled across tabs */
    }
    void fetch("/api/markets/refresh", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}"
    });
  }, [markets.data?.status?.last_update]);

  const crypto = usePoll<CryptoSlice>("/api/crypto", pollMs);
  const news = usePoll<NewsSlice>("/api/news", pollMs);

  // Same ambient freshness for news: older than 30 minutes → quiet refresh
  // (throttled across tabs; the fetch takes ~15s server-side and the next
  // poll picks it up).
  useEffect(() => {
    const lastUpdate = news.data?.status?.last_update;
    if (!lastUpdate) return;
    const ageMinutes = (Date.now() - new Date(lastUpdate).getTime()) / 60_000;
    if (!(ageMinutes > 30)) return;
    try {
      const stamp = Number(window.localStorage.getItem("ft-news-refresh") || 0);
      if (Date.now() - stamp < 30 * 60_000) return;
      window.localStorage.setItem("ft-news-refresh", String(Date.now()));
    } catch {
      /* private mode */
    }
    void fetch("/api/news/refresh", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}"
    });
  }, [news.data?.status?.last_update]);

  // Ambient freshness for the keyed quote groups (US via Finnhub, FX via Twelve
  // Data, TW via TWSE). /api/markets/refresh only freshens the no-key crypto
  // cache, so these would otherwise sit a full day stale. Slower cadence than
  // crypto and a shared throttle keep the free-tier keys well under their caps.
  useEffect(() => {
    const research = markets.data?.research_summary;
    const retrieved =
      research?.finnhub_quotes?.rows?.[0]?.retrieved_at ??
      research?.twelve_data_quotes?.rows?.[0]?.retrieved_at ??
      research?.twse_quotes?.rows?.[0]?.retrieved_at;
    if (!retrieved) return;
    const ageMinutes = (Date.now() - new Date(retrieved).getTime()) / 60_000;
    if (!(ageMinutes > 20)) return;
    try {
      const stamp = Number(window.localStorage.getItem("ft-quotes-refresh") || 0);
      if (Date.now() - stamp < 20 * 60_000) return;
      window.localStorage.setItem("ft-quotes-refresh", String(Date.now()));
    } catch {
      /* private mode: still refresh, just unthrottled across tabs */
    }
    const opts = { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" };
    void fetch("/api/markets/finnhub/quotes/refresh", opts);
    void fetch("/api/markets/twelve-data/quotes/refresh", opts);
    void fetch("/api/markets/twse/quotes/refresh", opts);
  }, [markets.data?.research_summary]);

  // The daily HISTORY cache is what the real-book banner, book detail, and the
  // TW quote overlay actually price off — a stale history means stale money
  // numbers even with fresh intraday quotes. It only turns over once a session,
  // so refresh hard (30 min) while the newest close we hold is from a prior day,
  // and idle (6 h) otherwise, to pull each new close instead of only labelling
  // the old one as stale.
  useEffect(() => {
    const roc = markets.data?.research_summary?.twse_quotes?.rows?.[0]?.date;
    let behind = false;
    if (typeof roc === "string" && roc.length >= 7) {
      const iso = `${Number(roc.slice(0, -4)) + 1911}-${roc.slice(-4, -2)}-${roc.slice(-2)}`;
      behind = /^\d{4}-\d{2}-\d{2}$/.test(iso) && iso < new Date().toISOString().slice(0, 10);
    }
    try {
      const stamp = Number(window.localStorage.getItem("ft-history-refresh") || 0);
      if (Date.now() - stamp < (behind ? 30 * 60_000 : 6 * 60 * 60_000)) return;
      window.localStorage.setItem("ft-history-refresh", String(Date.now()));
    } catch {
      /* private mode */
    }
    void fetch("/api/markets/history/refresh", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}"
    });
  }, [markets.data?.research_summary]);
  const activity = usePoll<ActivitySlice>("/api/agent-activity", Math.min(pollMs, 20_000));
  const portfolio = usePoll<{
    active_portfolio_id?: string;
    portfolio?: { name?: string; currency?: string };
    positions?: Record<string, string>[];
  }>("/api/portfolio", 60_000);
  const backups = usePoll<BackupsSlice>("/api/local-state/backups", 60_000);
  const watchlist = usePoll<WatchlistSlice>("/api/markets/watchlist", 60_000);
  const digest = usePoll<DigestSlice>("/api/news/digest", 60_000);
  const secrets = usePoll<SecretsStatusSlice>("/api/local-secrets/status", 120_000);

  const routesById = useMemo(
    () => Object.fromEntries(routes.map((route) => [route.route_id, route])),
    [routes]
  );
  const humanRoutes = routes.filter((route) => !AI_OPERATOR_ROUTES.has(route.route_id));
  const active = routesById[activeRoute] ?? routes[0] ?? fallbackRoutes[0];

  const storedKeys = secrets.data?.stored_provider_ids?.length;
  const eligibleKeys = secrets.data?.eligible_provider_ids?.length;
  const backupSummary = backups.data?.summary;

  const warnToday = (activity.data?.events ?? []).find(
    (event) => isToday(event.created_at) && ["failed", "blocked", "skipped"].includes(event.state ?? "")
  );

  const navigate = (routeId: string) => {
    window.location.hash = `#/${routeId}`;
    setActiveRoute(routeId);
    // The capabilities page and the artifact reader render *instead of* the
    // workspace, so with either open the sidebar highlighted the new route and
    // then showed the old view — clicking 回測 did nothing until you first
    // found "← 回任務牆". Navigation now always lands where it says.
    setShowCaps(false);
    setArtifactPath(null);
  };

  return (
    <div className="ft-shell">
      <nav className="ft-side" data-testid="shell-sidebar">
        <div className="ft-cap">OTTO</div>
        {humanRoutes.map((route) => {
          // Native title="" lagged, could not be styled, and never showed on
          // keyboard focus. Only worth a tip when it adds the canonical name.
          const visible = t(ROUTE_ZH[route.route_id] ?? route.label);
          return (
            <button
              key={route.route_id}
              type="button"
              className={route.route_id === active?.route_id ? "on" : ""}
              data-testid={buttonIdFor(route)}
              onClick={() => navigate(route.route_id)}
              data-tip={visible === route.label ? undefined : route.label}
            >
              {visible}
            </button>
          );
        })}
        <div className="ft-cap" style={{ marginTop: 14 }}>{t("操作")}</div>
        <div className="ft-note">{t("全部指令走對話。這裡只負責看。")}</div>
        <button type="button" className="on" style={{ borderLeftColor: "transparent" }}
          data-testid="capabilities-button" onClick={() => setShowCaps(true)}>
          {t("AI 能做什麼 →")}
        </button>
      </nav>

      <div className="ft-main">
        <header className="ft-top" data-testid="shell-topstrip">
          <div className="ft-brand"><em>OTTO</em></div>
          <span className="ft-st">{t("實盤")} <b className="ft-down">{t("關")}</b> · {t("外部執行")} <b className="ft-down">{t("關")}</b></span>
          <span className="ft-st">{t("備份")} <b>{backupSummary ? `${backupSummary.protected_file_count ?? 0}${t("檔")}·${backupSummary.backup_file_count ?? 0}${t("份")}` : "—"}</b></span>
          <span className="ft-st">KEYS <b>{typeof storedKeys === "number" ? `${storedKeys}${eligibleKeys ? `/${eligibleKeys}` : ""}` : "—"}</b></span>
          <span className="ft-st">
            <button
              type="button"
              onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
              style={{ background: "none", border: 0, color: "inherit", font: "inherit", cursor: "pointer" }}
              data-testid="theme-toggle"
            >
              {t("主題")} <b>{theme === "dark" ? t("暗") : t("亮")}</b>
            </button>
          </span>
          <span className="ft-st">
            <button
              type="button"
              onClick={() => setLang(lang === "zh" ? "en" : "zh")}
              style={{ background: "none", border: 0, color: "inherit", font: "inherit", cursor: "pointer" }}
              data-testid="lang-toggle"
            >
              {t("語言")} <b>{lang === "zh" ? "中" : "EN"}</b>
            </button>
          </span>
          <Clock />
        </header>

        <div className="ft-alerts" data-testid="shell-alerts">
          {warnToday
            ? <>⚠ {hhmm(warnToday.created_at)} {warnToday.summary || warnToday.action_id}</>
            : <span className="ft-faint">{t("無警示")}</span>}
        </div>

        {showCaps ? (
          <CapabilitiesDoc onBack={() => setShowCaps(false)} />
        ) : artifactPath ? (() => {
          const runMatch = artifactPath.match(/backtests[\\/](bt-[a-z0-9-]+)/);
          if (runMatch) return <BacktestRunReader runId={runMatch[1]} onBack={() => setArtifactPath(null)} />;
          const briefMatch = artifactPath.match(/research_briefs[\\/](news-brief-[a-z0-9-]+)/);
          if (briefMatch) return <NewsBriefReader briefId={briefMatch[1]} onBack={() => setArtifactPath(null)} />;
          return (
            <div className="ft-doc-wrap" data-testid="artifact-reader">
              <a className="ft-link ft-mono" role="button" tabIndex={0}
                onClick={() => setArtifactPath(null)} onKeyDown={activateOnKey(() => setArtifactPath(null))}>{t("← 回任務牆")}</a>
              <div className="ft-doc">
                <h1>{t("產出位置")}</h1>
                <div className="sub">{artifactPath}</div>
                <div className="ft-empty">{t("這類產出尚無專屬讀者——在對話請 AI 讀給你。")}</div>
              </div>
            </div>
          );
        })() : active?.route_id === "backtest" ? (
          <BacktestPage heading={<RouteHeading routeId={active.route_id} label={active.label} />} />
        ) : active?.route_id === "news" ? (
          <NewsPage heading={<RouteHeading routeId={active.route_id} label={active.label} />} items={news.data?.items ?? []} digest={digest.data} />
        ) : active?.route_id === "markets" ? (
          <MarketsPage heading={<RouteHeading routeId={active.route_id} label={active.label} />} markets={markets.data} />
        ) : active?.route_id === "crypto" ? (
          <CryptoPage heading={<RouteHeading routeId={active.route_id} label={active.label} />} crypto={crypto.data} />
        ) : active?.route_id === "paper" ? (
          <PaperPage heading={<RouteHeading routeId={active.route_id} label={active.label} />} crypto={crypto.data} />
        ) : active?.route_id === "portfolio" ? (
          <PortfolioPage heading={<RouteHeading routeId={active.route_id} label={active.label} />} />
        ) : active?.route_id === "algo" ? (
          <AlgoPage heading={<RouteHeading routeId={active.route_id} label={active.label} />} onOpenArtifact={setArtifactPath} />
        ) : active?.route_id === "settings" ? (
          <SettingsPage heading={<RouteHeading routeId={active.route_id} label={active.label} />} />
        ) : active?.route_id === "profile" ? (
          <ProfilePage heading={<RouteHeading routeId={active.route_id} label={active.label} />} />
        ) : active?.route_id === "forum" ? (
          <ForumPage heading={<RouteHeading routeId={active.route_id} label={active.label} />} />
        ) : active && AI_OPERATOR_ROUTES.has(active.route_id) ? (
          <AiRoutePage
            heading={<RouteHeading routeId={active.route_id} label={active.label} />}
            routeId={active.route_id}
            testId={`workspace-${active.path.replace(/^\//, "")}`}
            activity={activity.data}
          />
        ) : active?.route_id === "dashboard" ? (
          <Wall
            markets={markets.data}
            crypto={crypto.data}
            activity={activity.data}
            news={news.data}
            watchlist={watchlist.data}
            digest={digest.data}
            book={portfolio.data}
            onOpenArtifact={setArtifactPath}
            heading={<RouteHeading routeId={active.route_id} label={active.label} />}
            settled={{ markets: markets.settled, activity: activity.settled, news: news.settled }}
          />
        ) : active ? (
          <PlaceholderPage route={active} />
        ) : null}
      </div>
    </div>
  );
}
