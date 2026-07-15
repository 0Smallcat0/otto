"""Dashboard contracts and local route-state aggregation."""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


DASHBOARD_CATEGORIES: tuple[str, ...] = (
    "ALL",
    "TOOLS",
    "MARKETS",
    "RESEARCH",
    "GEOPOLITICS",
    "PORTFOLIO",
    "TRADING",
)

DASHBOARD_WIDGET_CATALOG: tuple[dict[str, str], ...] = (
    {"widget_id": "agent_errors", "label": "Agent Errors", "category": "TOOLS"},
    {"widget_id": "commodities", "label": "Commodities", "category": "MARKETS"},
    {"widget_id": "crypto_markets", "label": "Crypto Markets", "category": "MARKETS"},
    {"widget_id": "crypto_ticker", "label": "Crypto Ticker", "category": "MARKETS"},
    {"widget_id": "economic_calendar", "label": "Economic Calendar", "category": "RESEARCH"},
    {"widget_id": "forex_pairs", "label": "Forex Pairs", "category": "MARKETS"},
    {"widget_id": "geopolitics_events", "label": "Geopolitics Events", "category": "GEOPOLITICS"},
    {"widget_id": "holdings", "label": "Holdings", "category": "PORTFOLIO"},
    {"widget_id": "market_indices", "label": "Market Indices", "category": "MARKETS"},
    {"widget_id": "margin_usage", "label": "Margin Usage", "category": "TRADING"},
    {"widget_id": "maritime_vessels", "label": "Maritime Vessels", "category": "GEOPOLITICS"},
    {"widget_id": "news_feed", "label": "News Feed", "category": "RESEARCH"},
    {"widget_id": "news_category", "label": "News Category", "category": "RESEARCH"},
    {"widget_id": "notes", "label": "Notes", "category": "TOOLS"},
    {"widget_id": "open_positions", "label": "Open Positions", "category": "TRADING"},
    {"widget_id": "performance", "label": "Performance", "category": "PORTFOLIO"},
    {"widget_id": "polymarket", "label": "Prediction Markets", "category": "RESEARCH"},
    {"widget_id": "portfolio_summary", "label": "Portfolio Summary", "category": "PORTFOLIO"},
    {"widget_id": "quick_trade", "label": "Quick Trade", "category": "TRADING"},
    {"widget_id": "quote_strip", "label": "Quote Strip", "category": "MARKETS"},
    {"widget_id": "recent_files", "label": "Recent Files", "category": "TOOLS"},
    {"widget_id": "risk_metrics", "label": "Risk Metrics", "category": "PORTFOLIO"},
    {"widget_id": "stock_screener", "label": "Stock Screener", "category": "MARKETS"},
    {"widget_id": "sector_heatmap", "label": "Sector Heatmap", "category": "MARKETS"},
    {"widget_id": "market_sentiment", "label": "Market Sentiment", "category": "MARKETS"},
    {"widget_id": "sparklines", "label": "Sparklines", "category": "MARKETS"},
    {"widget_id": "stock_quote", "label": "Stock Quote", "category": "MARKETS"},
    {"widget_id": "today_pnl", "label": "Today P&L", "category": "PORTFOLIO"},
    {"widget_id": "top_movers", "label": "Top Movers", "category": "MARKETS"},
    {"widget_id": "trade_tape", "label": "Trade Tape", "category": "TRADING"},
    {"widget_id": "live_streams", "label": "Live Streams", "category": "RESEARCH"},
    {"widget_id": "watchlist", "label": "Watchlist", "category": "MARKETS"},
    {"widget_id": "web_scraper", "label": "Web Scraper", "category": "TOOLS"},
    {"widget_id": "working_orders", "label": "Working Orders", "category": "TRADING"},
)

DASHBOARD_TEMPLATES: dict[str, list[str]] = {
    "Portfolio Manager": [
        "portfolio_summary",
        "holdings",
        "performance",
        "risk_metrics",
        "news_feed",
        "recent_files",
    ],
    "Hedge Fund": [
        "market_indices",
        "sector_heatmap",
        "market_sentiment",
        "risk_metrics",
        "open_positions",
        "news_feed",
    ],
    "Crypto Trader": [
        "crypto_markets",
        "crypto_ticker",
        "watchlist",
        "open_positions",
        "working_orders",
        "trade_tape",
    ],
    "Equity Trader": [
        "market_indices",
        "stock_screener",
        "stock_quote",
        "quote_strip",
        "working_orders",
        "trade_tape",
    ],
    "Macro Economist": [
        "economic_calendar",
        "forex_pairs",
        "commodities",
        "market_indices",
        "news_category",
        "notes",
    ],
    "Geopolitics Analyst": [
        "geopolitics_events",
        "maritime_vessels",
        "news_feed",
        "notes",
        "market_sentiment",
        "recent_files",
    ],
}

DEFAULT_DASHBOARD_WIDGETS: list[str] = [
    "portfolio_summary",
    "data_freshness",
    "open_positions",
    "working_orders",
    "market_pulse",
    "recent_files",
]

EXTRA_LOCAL_WIDGETS: tuple[dict[str, str], ...] = (
    {"widget_id": "data_freshness", "label": "Data Freshness", "category": "TOOLS"},
    {"widget_id": "market_pulse", "label": "Market Pulse", "category": "MARKETS"},
)

PUBLIC_DATA_PENDING_WIDGETS = {
    "commodities",
    "crypto_markets",
    "crypto_ticker",
    "economic_calendar",
    "forex_pairs",
    "geopolitics_events",
    "live_streams",
    "market_indices",
    "market_pulse",
    "market_sentiment",
    "maritime_vessels",
    "news_category",
    "news_feed",
    "polymarket",
    "quote_strip",
    "sector_heatmap",
    "sparklines",
    "stock_quote",
    "stock_screener",
    "top_movers",
}
PAPER_PENDING_WIDGETS = {"open_positions", "trade_tape", "working_orders"}
PORTFOLIO_PENDING_WIDGETS = {
    "holdings",
    "performance",
    "portfolio_summary",
    "risk_metrics",
    "today_pnl",
}
SAFETY_GATED_WIDGETS = {"margin_usage", "quick_trade", "web_scraper"}
LOCAL_STATUS_WIDGETS = {"agent_errors", "data_freshness", "notes", "recent_files", "watchlist"}


def default_dashboard_layout() -> dict[str, Any]:
    return {
        "layout_id": "dashboard-default",
        "template": "Local Default",
        "widgets": list(DEFAULT_DASHBOARD_WIDGETS),
        "alerts_read": False,
    }


def normalize_dashboard_layout(layout: dict[str, Any]) -> dict[str, Any]:
    template = layout.get("template")
    if not isinstance(template, str) or not template.strip():
        template = "Local Default"
    return {
        "layout_id": "dashboard-default",
        "template": template[:80],
        "widgets": _normalize_widgets(layout.get("widgets", DEFAULT_DASHBOARD_WIDGETS)),
        "alerts_read": layout.get("alerts_read") is True,
    }


def dashboard_payload(
    layout: dict[str, Any],
    market_cache: dict[str, Any] | None = None,
    paper_state: dict[str, Any] | None = None,
    crypto_detail_cache: dict[str, Any] | None = None,
    portfolio_state: dict[str, Any] | None = None,
    news_cache: dict[str, Any] | None = None,
    provider_state: dict[str, Any] | None = None,
    artifact_root: Path | None = None,
    research_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    layout = normalize_dashboard_layout(layout)
    summary = _summary_from_paper_state(paper_state)
    freshness = _freshness_from_cache(
        market_cache,
        paper_state,
        crypto_detail_cache,
        news_cache,
        research_data,
    )
    market_pulse = _market_pulse_from_cache(market_cache, crypto_detail_cache)
    panels = [
        _provider_panel(provider_state),
        _market_panel(market_cache, crypto_detail_cache, market_pulse),
        _paper_panel(paper_state),
        _portfolio_panel(portfolio_state),
        _news_panel(news_cache),
        _research_panel(research_data),
        _backtest_panel(artifact_root),
        _macro_setup_panel(provider_state),
    ]
    return {
        "summary": summary,
        "freshness": freshness,
        "market_pulse": market_pulse,
        "panels": panels,
        "alerts": [] if layout.get("alerts_read") else _alerts_from_panels(panels),
        "widgets": layout["widgets"],
        "active_widgets": [_widget_metadata(widget_id) for widget_id in layout["widgets"]],
        "catalog": [_with_capability(widget) for widget in DASHBOARD_WIDGET_CATALOG],
        "categories": list(DASHBOARD_CATEGORIES),
        "templates": [
            {"name": name, "widgets": widgets_for_template}
            for name, widgets_for_template in DASHBOARD_TEMPLATES.items()
        ],
        "template": layout.get("template", "Local Default"),
    }


def apply_dashboard_template(template_name: str) -> dict[str, Any]:
    widgets = DASHBOARD_TEMPLATES.get(template_name, DEFAULT_DASHBOARD_WIDGETS)
    return normalize_dashboard_layout(
        {
            "layout_id": "dashboard-default",
            "template": template_name if template_name in DASHBOARD_TEMPLATES else "Local Default",
            "widgets": widgets,
            "alerts_read": False,
        }
    )


def _normalize_widgets(raw_widgets: Any) -> list[str]:
    valid_ids = {
        item["widget_id"] for item in DASHBOARD_WIDGET_CATALOG + EXTRA_LOCAL_WIDGETS
    }
    widgets: list[str] = []
    if isinstance(raw_widgets, list):
        for widget_id in raw_widgets:
            if isinstance(widget_id, str) and widget_id in valid_ids and widget_id not in widgets:
                widgets.append(widget_id)
    return widgets or list(DEFAULT_DASHBOARD_WIDGETS)


def _widget_metadata(widget_id: str) -> dict[str, str]:
    widgets = {item["widget_id"]: item for item in DASHBOARD_WIDGET_CATALOG + EXTRA_LOCAL_WIDGETS}
    widget = widgets.get(
        widget_id,
        {"widget_id": widget_id, "label": widget_id, "category": "LOCAL"},
    )
    return _with_capability(widget)


def _with_capability(widget: dict[str, str]) -> dict[str, str]:
    widget_id = widget["widget_id"]
    if widget_id in SAFETY_GATED_WIDGETS:
        capability = "safety-gated"
    elif widget_id in PAPER_PENDING_WIDGETS:
        capability = "paper-ledger"
    elif widget_id in PUBLIC_DATA_PENDING_WIDGETS:
        capability = "provider-scoped"
    elif widget_id in PORTFOLIO_PENDING_WIDGETS:
        capability = "local-portfolio"
    elif widget_id in LOCAL_STATUS_WIDGETS:
        capability = "local-status"
    else:
        capability = "local-pending"
    return {**widget, "capability": capability}


def _summary_from_paper_state(paper_state: dict[str, Any] | None) -> dict[str, str | int]:
    if not isinstance(paper_state, dict):
        return {
            "cash": "0.00",
            "equity": "0.00",
            "open_pnl": "0.00",
            "positions": 0,
            "open_orders": 0,
            "fills_today": 0,
            "active_signals": 0,
        }
    account = paper_state.get("account") if isinstance(paper_state.get("account"), dict) else {}
    positions = paper_state.get("positions") if isinstance(paper_state.get("positions"), dict) else {}
    orders = paper_state.get("orders") if isinstance(paper_state.get("orders"), list) else []
    fills = paper_state.get("fills") if isinstance(paper_state.get("fills"), list) else []
    cash = str(account.get("cash") or "0.00")
    equity = str(account.get("equity") or cash)
    open_pnl = _money(_decimal(equity) - _decimal(str(account.get("initial_cash") or cash)))
    return {
        "cash": cash,
        "equity": equity,
        "open_pnl": open_pnl,
        "positions": len(positions),
        "open_orders": sum(1 for order in orders if isinstance(order, dict) and order.get("status") == "WORKING"),
        "fills_today": len(fills),
        "active_signals": 0,
    }


def _freshness_from_cache(
    market_cache: dict[str, Any] | None,
    paper_state: dict[str, Any] | None,
    crypto_detail_cache: dict[str, Any] | None,
    news_cache: dict[str, Any] | None,
    research_data: dict[str, Any] | None,
) -> dict[str, str]:
    status = market_cache.get("status") if isinstance(market_cache, dict) else {}
    status = status if isinstance(status, dict) else {}
    market_source = str(status.get("source") or "public_provider_unavailable")
    market_state = str(status.get("state") or "unavailable")
    detail_status = (
        crypto_detail_cache.get("status") if isinstance(crypto_detail_cache, dict) else {}
    )
    detail_status = detail_status if isinstance(detail_status, dict) else {}
    detail_source = str(detail_status.get("source") or "public_detail_unavailable")
    detail_state = str(detail_status.get("state") or "unavailable")
    news_update = (
        str(news_cache.get("fetched_at"))
        if isinstance(news_cache, dict) and news_cache.get("fetched_at")
        else "not refreshed"
    )
    research_status = research_data.get("status") if isinstance(research_data, dict) else {}
    research_status = research_status if isinstance(research_status, dict) else {}
    research_source = str(research_status.get("source") or "public_research_providers")
    research_state = str(research_status.get("state") or "unavailable")
    last_update = str(
        status.get("last_update")
        or detail_status.get("last_update")
        or research_status.get("last_update")
        or "not refreshed"
    )
    account = paper_state.get("account") if isinstance(paper_state, dict) and isinstance(paper_state.get("account"), dict) else {}
    paper_update = str(account.get("updated_at") or "not started")
    return {
        "market_data": f"{market_source} / {market_state}",
        "crypto_detail": f"{detail_source} / {detail_state}",
        "paper_ledger": f"local_paper / {paper_update}",
        "news_cache": f"public_rss / {news_update}",
        "research_data": f"{research_source} / {research_state}",
        "last_update": last_update,
    }


def _market_pulse_from_cache(
    market_cache: dict[str, Any] | None,
    crypto_detail_cache: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rows = market_cache.get("rows") if isinstance(market_cache, dict) else []
    rows = rows if isinstance(rows, list) else []
    rows = [row for row in rows if isinstance(row, dict)]
    if not rows:
        detail_pulse = _market_pulse_from_detail(crypto_detail_cache)
        if detail_pulse is not None:
            return detail_pulse
        return {
            "breadth": "Awaiting public provider refresh",
            "top_movers": [],
            "volatility": "Awaiting cache",
        }
    sorted_rows = sorted(rows, key=lambda row: abs(_decimal(str(row.get("chg_pct") or "0"))), reverse=True)
    changes = [_decimal(str(row.get("chg_pct") or "0")) for row in rows]
    up_count = sum(1 for change in changes if change > 0)
    down_count = sum(1 for change in changes if change < 0)
    top_movers = [
        f"{row.get('symbol', '')} {row.get('chg_pct', '0')}%"
        for row in sorted_rows[:3]
        if row.get("symbol")
    ]
    return {
        "breadth": f"{up_count} up / {down_count} down / {len(rows)} tracked",
        "top_movers": top_movers,
        "volatility": f"{_money(max(changes) - min(changes))}% range" if changes else "Unavailable",
    }


def _market_pulse_from_detail(crypto_detail_cache: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(crypto_detail_cache, dict):
        return None
    status = crypto_detail_cache.get("status")
    candles = crypto_detail_cache.get("candles")
    if not isinstance(status, dict) or not isinstance(candles, list) or not candles:
        return None
    clean_candles = [candle for candle in candles if isinstance(candle, dict)]
    if not clean_candles:
        return None
    latest = clean_candles[-1]
    symbol = str(status.get("symbol") or "BTCUSDT")
    open_price = _decimal(str(latest.get("open") or "0"))
    close_price = _decimal(str(latest.get("close") or "0"))
    highs = [_decimal(str(candle.get("high") or "0")) for candle in clean_candles[-24:]]
    lows = [_decimal(str(candle.get("low") or "0")) for candle in clean_candles[-24:]]
    change_pct = Decimal("0")
    if open_price > 0:
        change_pct = ((close_price / open_price) - Decimal("1")) * Decimal("100")
    volatility = max(highs or [Decimal("0")]) - min(lows or [Decimal("0")])
    return {
        "breadth": f"{symbol} candle flow / {len(clean_candles)} closed candles",
        "top_movers": [f"{symbol} {_money(change_pct)}%"],
        "volatility": f"{_money(volatility)} 24-candle range",
    }


def _provider_panel(provider_state: dict[str, Any] | None) -> dict[str, Any]:
    summary = provider_state.get("summary") if isinstance(provider_state, dict) else {}
    summary = summary if isinstance(summary, dict) else {}
    freshness = provider_state.get("freshness_strip") if isinstance(provider_state, dict) else []
    freshness = [item for item in freshness if isinstance(item, dict)] if isinstance(freshness, list) else []
    active = _int(summary.get("active"))
    stale = _int(summary.get("stale_cache"))
    gated = _int(summary.get("key_required")) + _int(summary.get("plan_required")) + _int(summary.get("disabled_by_safety"))
    rows = [
        {
            "label": str(item.get("label") or item.get("provider_id") or "Provider"),
            "value": str(item.get("state") or "unavailable"),
            "detail": _short_detail(str(item.get("message") or item.get("cache_path") or "")),
        }
        for item in freshness[:5]
    ]
    return _panel(
        "provider_freshness",
        "Provider Freshness",
        "active" if active else "setup_required",
        "provider_registry",
        str(provider_state.get("generated_at") if isinstance(provider_state, dict) else ""),
        [
            {"label": "Active", "value": active},
            {"label": "Stale", "value": stale},
            {"label": "Gated", "value": gated},
        ],
        rows,
        "Provider registry exposes source, TTL, auth, and safety state.",
    )


def _market_panel(
    market_cache: dict[str, Any] | None,
    crypto_detail_cache: dict[str, Any] | None,
    market_pulse: dict[str, Any],
) -> dict[str, Any]:
    status = market_cache.get("status") if isinstance(market_cache, dict) else {}
    status = status if isinstance(status, dict) else {}
    detail_status = (
        crypto_detail_cache.get("status") if isinstance(crypto_detail_cache, dict) else {}
    )
    detail_status = detail_status if isinstance(detail_status, dict) else {}
    rows = market_cache.get("rows") if isinstance(market_cache, dict) else []
    rows = [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []
    detail_trades = crypto_detail_cache.get("trades") if isinstance(crypto_detail_cache, dict) else []
    detail_trades = detail_trades if isinstance(detail_trades, list) else []
    top_movers = market_pulse.get("top_movers") if isinstance(market_pulse.get("top_movers"), list) else []
    source = str(status.get("source") or detail_status.get("source") or "public_provider_unavailable")
    state = str(status.get("state") or detail_status.get("state") or "unavailable")
    return _panel(
        "market_pulse",
        "Market Pulse",
        state,
        source,
        str(status.get("last_update") or detail_status.get("last_update") or ""),
        [
            {"label": "Tracked", "value": len(rows) or _detail_candle_count(crypto_detail_cache)},
            {"label": "Trades", "value": len(detail_trades)},
            {"label": "Volatility", "value": str(market_pulse.get("volatility") or "Awaiting cache")},
        ],
        [
            {"label": "Breadth", "value": str(market_pulse.get("breadth") or "")},
            {"label": "Top movers", "value": ", ".join(str(item) for item in top_movers) or "Awaiting movers"},
        ],
        "Reads market ticker cache first, then public crypto detail candles.",
    )


def _paper_panel(paper_state: dict[str, Any] | None) -> dict[str, Any]:
    summary = _summary_from_paper_state(paper_state)
    account = paper_state.get("account") if isinstance(paper_state, dict) and isinstance(paper_state.get("account"), dict) else {}
    orders = paper_state.get("orders") if isinstance(paper_state, dict) and isinstance(paper_state.get("orders"), list) else []
    fills = paper_state.get("fills") if isinstance(paper_state, dict) and isinstance(paper_state.get("fills"), list) else []
    rows = []
    for order in orders[-2:]:
        if isinstance(order, dict):
            rows.append(
                {
                    "label": str(order.get("symbol") or "paper_order"),
                    "value": str(order.get("status") or "recorded"),
                    "detail": str(order.get("created_at") or order.get("reason") or ""),
                }
            )
    if not rows:
        rows.append({"label": "Order flow", "value": "Paper-only", "detail": "Crypto ticket writes local ledger"})
    return _panel(
        "paper_ledger",
        "Paper Ledger",
        str(account.get("mode") or "paper"),
        "local_paper",
        str(account.get("updated_at") or "not started"),
        [
            {"label": "Cash", "value": summary["cash"]},
            {"label": "Equity", "value": summary["equity"]},
            {"label": "Fills", "value": len(fills)},
        ],
        rows,
        "Live trading remains unreachable; ledger state is local paper only.",
    )


def _portfolio_panel(portfolio_state: dict[str, Any] | None) -> dict[str, Any]:
    state = portfolio_state if isinstance(portfolio_state, dict) else {}
    portfolios = state.get("portfolios")
    portfolios = portfolios if isinstance(portfolios, dict) else {}
    active_id = state.get("active_portfolio_id")
    active = portfolios.get(active_id) if active_id in portfolios else None
    active = active if isinstance(active, dict) else None
    positions = active.get("positions") if isinstance(active, dict) else []
    positions = [position for position in positions if isinstance(position, dict)] if isinstance(positions, list) else []
    transactions = active.get("transactions") if isinstance(active, dict) else []
    transactions = transactions if isinstance(transactions, list) else []
    value = sum(
        (
            _decimal(str(position.get("quantity") or "0"))
            * _decimal(str(position.get("last_price") or "0"))
            for position in positions
        ),
        Decimal("0"),
    )
    rows = [
        {
            "label": str(position.get("symbol") or "holding"),
            "value": _money(
                _decimal(str(position.get("quantity") or "0"))
                * _decimal(str(position.get("last_price") or "0"))
            ),
            "detail": str(position.get("sector") or position.get("asset_class") or ""),
        }
        for position in positions[:3]
    ]
    if not rows:
        rows.append(
            {
                "label": "First use",
                "value": "Create, import, demo, paper link, or backtest link",
                "detail": "Portfolio state stays local.",
            }
        )
    return _panel(
        "portfolio",
        "Portfolio",
        "first_use" if active is None else str(active.get("source") or "local"),
        str(active.get("source") if active else "local_portfolio"),
        str(active.get("updated_at") or state.get("updated_at") or "not started") if active else "not started",
        [
            {"label": "Value", "value": _money(value)},
            {"label": "Positions", "value": len(positions)},
            {"label": "Transactions", "value": len(transactions)},
        ],
        rows,
        "Portfolio aggregates local imports, demo state, paper ledger links, or backtest artifacts.",
    )


def _news_panel(news_cache: dict[str, Any] | None) -> dict[str, Any]:
    cache = news_cache if isinstance(news_cache, dict) else {}
    items = cache.get("items")
    items = [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []
    source_counts: dict[str, int] = {}
    for item in items:
        source = str(item.get("source") or "Public source")
        source_counts[source] = source_counts.get(source, 0) + 1
    rows = [
        {"label": source, "value": count, "detail": "cached headlines"}
        for source, count in sorted(source_counts.items(), key=lambda item: item[1], reverse=True)[:3]
    ]
    if not rows:
        rows.append(
            {
                "label": "Public RSS",
                "value": "Refresh News route",
                "detail": "Cache will populate from configured public feeds.",
            }
        )
    return _panel(
        "news",
        "News",
        "cache_ready" if items else "cache_missing",
        "public_rss",
        str(cache.get("fetched_at") or "not refreshed"),
        [
            {"label": "Items", "value": len(items)},
            {"label": "Sources", "value": len(source_counts)},
            {"label": "Alerts", "value": sum(1 for item in items if item.get("alert") is True)},
        ],
        rows,
        "Dashboard uses cached headline metadata only; no full article copying.",
    )


def _research_panel(research_data: dict[str, Any] | None) -> dict[str, Any]:
    data = research_data if isinstance(research_data, dict) else {}
    status = data.get("status") if isinstance(data.get("status"), dict) else {}
    fundamentals = data.get("fundamentals") if isinstance(data.get("fundamentals"), dict) else {}
    macro = data.get("macro") if isinstance(data.get("macro"), dict) else {}
    companies = fundamentals.get("companies") if isinstance(fundamentals.get("companies"), list) else []
    series = macro.get("series") if isinstance(macro.get("series"), list) else []
    fact_count = sum(
        len(company.get("facts", []))
        for company in companies
        if isinstance(company, dict)
    )
    rows = []
    for company in companies[:2]:
        if not isinstance(company, dict):
            continue
        facts = company.get("facts") if isinstance(company.get("facts"), list) else []
        latest_fact = facts[0] if facts and isinstance(facts[0], dict) else {}
        rows.append(
            {
                "label": str(company.get("symbol") or company.get("cik") or "SEC company"),
                "value": str(latest_fact.get("label") or "company facts"),
                "detail": str(company.get("cache_path") or "SEC cache"),
            }
        )
    for row in series[:2]:
        if not isinstance(row, dict):
            continue
        rows.append(
            {
                "label": str(row.get("source_provider") or "DBnomics"),
                "value": str(row.get("latest_value") or "macro series"),
                "detail": f"{row.get('latest_period', '')} {row.get('series_id', '')}".strip(),
            }
        )
    if not rows:
        rows.append(
            {
                "label": "Public research",
                "value": "Refresh News",
                "detail": "SEC company facts and DBnomics macro cache populate from no-key providers.",
            }
        )
    return _panel(
        "macro_fundamentals",
        "Macro & Fundamentals",
        str(status.get("state") or "unavailable"),
        str(status.get("source") or "public_research_providers"),
        str(status.get("last_update") or "not refreshed"),
        [
            {"label": "Companies", "value": len(companies)},
            {"label": "Facts", "value": fact_count},
            {"label": "Macro series", "value": len(series)},
        ],
        rows,
        "No-key SEC and DBnomics summaries feed Dashboard and Markets without secrets.",
    )


def _backtest_panel(artifact_root: Path | None) -> dict[str, Any]:
    runs = _backtest_runs(artifact_root)
    latest = runs[0] if runs else {}
    summary = latest.get("summary") if isinstance(latest.get("summary"), dict) else {}
    manifest = latest.get("manifest") if isinstance(latest.get("manifest"), dict) else {}
    artifact_dir = str(latest.get("artifact_dir") or "")
    rows = []
    if latest:
        rows.append(
            {
                "label": str(manifest.get("run_id") or Path(artifact_dir).name),
                "value": f"{summary.get('return_pct', '0.00')}%",
                "detail": str(manifest.get("provider") or summary.get("strategy") or ""),
            }
        )
    else:
        rows.append(
            {
                "label": "Backtest artifacts",
                "value": "No local runs yet",
                "detail": "Run Backtest to create config, summary, trades, report, and manifest.",
            }
        )
    return _panel(
        "backtests",
        "Backtests",
        "artifact_ready" if latest else "no_runs",
        "local_artifacts",
        str(manifest.get("created_at") or ""),
        [
            {"label": "Runs", "value": len(runs)},
            {"label": "Trades", "value": _int(summary.get("trade_count"))},
            {"label": "Provider", "value": str(manifest.get("provider") or "pending")},
        ],
        rows,
        artifact_dir or "Backtest artifacts stay under artifacts/backtests.",
    )


def _macro_setup_panel(provider_state: dict[str, Any] | None) -> dict[str, Any]:
    providers = provider_state.get("providers") if isinstance(provider_state, dict) else []
    providers = [item for item in providers if isinstance(item, dict)] if isinstance(providers, list) else []
    macro = [
        provider
        for provider in providers
        if any(term in provider.get("coverage", []) for term in ("macro", "fundamentals"))
    ]
    rows = [
        {
            "label": str(provider.get("label") or provider.get("provider_id")),
            "value": str(provider.get("health", {}).get("state") or provider.get("capability_state") or "planned"),
            "detail": str(provider.get("auth_mode") or ""),
        }
        for provider in macro[:4]
    ]
    if not rows:
        rows.append(
            {
                "label": "Macro/fundamentals",
                "value": "Provider registry pending",
                "detail": "No-key adapters should land before optional-key providers.",
            }
        )
    no_key = sum(1 for provider in macro if str(provider.get("auth_mode")) == "no-key")
    key_gated = sum(1 for provider in macro if "key" in str(provider.get("auth_mode")))
    return _panel(
        "macro_setup",
        "Macro Setup",
        "planned",
        "provider_registry",
        str(provider_state.get("generated_at") if isinstance(provider_state, dict) else ""),
        [
            {"label": "No-key", "value": no_key},
            {"label": "Key-gated", "value": key_gated},
            {"label": "Planned", "value": len(macro)},
        ],
        rows,
        "Optional-key providers stay disabled until local secret storage is reviewed.",
    )


def _panel(
    panel_id: str,
    title: str,
    state: str,
    source: str,
    updated_at: str,
    metrics: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    detail: str,
) -> dict[str, Any]:
    return {
        "panel_id": panel_id,
        "title": title,
        "state": state,
        "source": source,
        "updated_at": updated_at or "not refreshed",
        "detail": detail,
        "metrics": [
            {"label": str(metric.get("label") or ""), "value": str(metric.get("value") or "0")}
            for metric in metrics
        ],
        "rows": [
            {
                "label": str(row.get("label") or ""),
                "value": str(row.get("value") or ""),
                "detail": str(row.get("detail") or ""),
            }
            for row in rows
        ],
    }


def _alerts_from_panels(panels: list[dict[str, Any]]) -> list[str]:
    alert_states = {"stale_cache", "rate_limited", "partial"}
    alerts = []
    for panel in panels:
        state = str(panel.get("state") or "")
        if state in alert_states:
            alerts.append(f"{panel['title']}: {state}")
    return alerts


def _backtest_runs(artifact_root: Path | None) -> list[dict[str, Any]]:
    if artifact_root is None:
        return []
    root = artifact_root / "artifacts" / "backtests"
    if not root.exists():
        return []
    runs = []
    for run_dir in root.iterdir():
        if not run_dir.is_dir():
            continue
        manifest = _read_json(run_dir / "manifest.json")
        summary = _read_json(run_dir / "summary.json")
        created_at = str(manifest.get("created_at") or "")
        runs.append(
            {
                "artifact_dir": run_dir.relative_to(artifact_root).as_posix(),
                "manifest": manifest,
                "summary": summary,
                "created_at": created_at,
                "mtime": run_dir.stat().st_mtime,
            }
        )
    return sorted(runs, key=lambda run: (str(run["created_at"]), float(run["mtime"])), reverse=True)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _detail_candle_count(crypto_detail_cache: dict[str, Any] | None) -> int:
    candles = crypto_detail_cache.get("candles") if isinstance(crypto_detail_cache, dict) else []
    return len(candles) if isinstance(candles, list) else 0


def _int(raw: Any) -> int:
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 0


def _short_detail(raw: str) -> str:
    return raw[:140]


def _decimal(raw: str) -> Decimal:
    try:
        return Decimal(raw)
    except (InvalidOperation, ValueError):
        return Decimal("0")


def _money(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01")))
