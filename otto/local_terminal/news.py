"""Local news feed reader with public RSS, GDELT DOC metadata, and fallback."""

from __future__ import annotations

import copy
import email.utils
import hashlib
import html
import json
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4


NEWS_CATEGORIES = ("ALL", "MKT", "EARN", "ECO", "TECH", "NRG", "CRPT", "GEO")
NEWS_TIME_FILTERS = ("1H", "6H", "24H", "48H", "7D", "30D")
NEWS_SORTS = ("REL", "NEW")
NEWS_FEED_TYPES = ("WIRE", "CLST")
MAX_NEWS_ITEMS = 120
MAX_WATCH_TERMS = 12
PUBLIC_RSS_SOURCES = (
    {
        "source_id": "fed_press",
        "label": "Federal Reserve",
        "url": "https://www.federalreserve.gov/feeds/press_all.xml",
        "category": "ECO",
    },
    {
        "source_id": "sec_press",
        "label": "SEC",
        "url": "https://www.sec.gov/news/pressreleases.rss",
        "category": "MKT",
    },
    {
        "source_id": "coindesk",
        "label": "CoinDesk",
        "url": "https://www.coindesk.com/arc/outboundfeeds/rss/",
        "category": "CRPT",
    },
    {
        "source_id": "cna_money",
        "label": "中央社財經",
        "url": "https://feeds.feedburner.com/rsscna/finance",
        "category": "TWN",
    },
    {
        "source_id": "cnyes_tw",
        "label": "鉅亨台股",
        "url": "https://news.cnyes.com/rss/v1/news/category/tw_stock",
        "category": "TWN",
    },
)
GDELT_DOC_PROVIDER_ID = "gdelt_doc_public"
GDELT_DOC_DOCS_URL = "https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/"
GDELT_DOC_ENDPOINT = "https://api.gdeltproject.org/api/v2/doc/doc"
GDELT_DOC_QUERY = (
    '(markets OR stocks OR bonds OR energy OR oil OR crypto OR "central bank" OR inflation)'
)
GDELT_DOC_MAX_RECORDS = 40

# GDELT's DOC query matches loosely (an "energy" volcano piece, an "oil" war
# report), so the raw firehose drags in fashion, regional crime, and celebrity
# blogs in a dozen languages. The curated RSS feeds are already on-topic and
# bypass this gate; only GDELT items must earn their place by naming something
# financial. Kept deliberately broad — a missed keyword just drops one item.
_FINANCE_TERMS = (
    "stock", "share", "equit", "market", "bond", "yield", "fed", "rate",
    "inflation", "gdp", "earning", "revenue", "profit", "nasdaq", "dow ",
    "s&p", "index", "crypto", "bitcoin", "ethereum", "oil", "crude", "energy",
    "central bank", "dollar", "currency", "forex", "tariff", "ipo", "merger",
    "dividend", "treasury", "recession", "econom", "bank", "financ", "invest",
    "trader", "trading", "semiconductor", "chipmaker", "valuation", "buyback",
    "股", "債", "匯", "利率", "通膨", "通脹", "央行", "升息", "降息", "財報",
    "營收", "獲利", "台積", "半導體", "期貨", "美元", "經濟", "投資", "基金",
    "加密", "比特幣", "原油", "能源", "關稅", "上市", "財經", "外資", "台幣",
)


def _is_finance_relevant(item: dict[str, Any]) -> bool:
    """True when a headline names something financial (en or zh)."""
    haystack = f"{item.get('title') or ''} {item.get('summary') or ''}".lower()
    return any(term in haystack for term in _FINANCE_TERMS)


def _is_gdelt_item(item: dict[str, Any]) -> bool:
    """True for items sourced from the GDELT firehose (vs a curated RSS feed)."""
    return (
        item.get("provider_id") == GDELT_DOC_PROVIDER_ID
        or str(item.get("item_id") or "").startswith("gdelt-")
    )
NEWS_CACHE_PATH = "artifacts/news/news_cache.json"
NEWS_RESEARCH_BRIEF_ROOT = "artifacts/news/research_briefs"
NEWS_RESEARCH_BRIEF_FILES = ("brief.json", "source_health.json", "manifest.json", "brief.md")
NEWS_RESEARCH_BRIEF_ARTIFACT_KEYS = {
    "brief.json": "brief",
    "source_health.json": "source_health",
    "manifest.json": "manifest",
    "brief.md": "report",
}


class NewsError(ValueError):
    """Raised when local news layout or fetch contracts are invalid."""


def default_news_layout() -> dict[str, Any]:
    return {
        "layout_id": "news",
        "auto_refresh": True,
        "category": "ALL",
        "time_filter": "24H",
        "sort": "REL",
        "feed_type": "WIRE",
        "watch_terms": [],
        "watch_only": False,
    }


def normalize_news_layout(layout: dict[str, Any]) -> dict[str, Any]:
    default = default_news_layout()
    category = str(layout.get("category") or default["category"]).upper()
    time_filter = str(layout.get("time_filter") or default["time_filter"]).upper()
    sort = str(layout.get("sort") or default["sort"]).upper()
    feed_type = str(layout.get("feed_type") or default["feed_type"]).upper()
    return {
        **default,
        "auto_refresh": bool(layout.get("auto_refresh", default["auto_refresh"])),
        "category": category if category in NEWS_CATEGORIES else default["category"],
        "time_filter": time_filter if time_filter in NEWS_TIME_FILTERS else default["time_filter"],
        "sort": sort if sort in NEWS_SORTS else default["sort"],
        "feed_type": feed_type if feed_type in NEWS_FEED_TYPES else default["feed_type"],
        "watch_terms": _normalize_watch_terms(layout.get("watch_terms", [])),
        "watch_only": bool(layout.get("watch_only", default["watch_only"])),
        "layout_id": "news",
    }


def news_payload(
    layout: dict[str, Any],
    cache: dict[str, Any] | None = None,
    *,
    fetcher: Any | None = None,
    refresh: bool = False,
) -> dict[str, Any]:
    normalized_layout = normalize_news_layout(layout)
    cache_payload = copy.deepcopy(cache or {})
    fetcher = fetcher or fetch_public_news
    status = {
        "source": "offline_fixture",
        "state": "offline",
        "last_update": str(cache_payload.get("fetched_at") or "not started"),
        "message": "Using local fallback news items.",
        "source_errors": [],
        "source_count": 0,
        "failed_source_count": 0,
    }
    provider_states = _offline_provider_states()
    items: list[dict[str, Any]] = []

    if refresh:
        try:
            fetch_result = fetcher()
        except NewsError as exc:
            fetched = []
            status["message"] = str(exc)
            source_errors = [str(exc)]
            source_count = 0
            failed_source_count = 0
        else:
            if isinstance(fetch_result, dict):
                raw_fetched = fetch_result.get("items", [])
                source_errors = [
                    str(error) for error in fetch_result.get("errors", []) if str(error)
                ]
                source_count = int(fetch_result.get("source_count", 0) or 0)
                failed_source_count = int(fetch_result.get("failed_source_count", len(source_errors)) or 0)
                provider_states = _normalize_provider_states(fetch_result.get("providers"))
            else:
                raw_fetched = fetch_result
                source_errors = []
                source_count = 0
                failed_source_count = 0
                provider_states = _default_provider_states("live", len(raw_fetched) if isinstance(raw_fetched, list) else 0)
            fetched = _normalize_items(raw_fetched)
        if fetched:
            merged = list(fetched)
            if source_errors:
                # A source failed this round — carry its last-known-good items
                # forward instead of silently dropping them from the wire.
                fresh_keys = {str(item.get("url") or item.get("title") or "") for item in fetched}
                cached_items = cache_payload.get("items")
                if isinstance(cached_items, list) and cached_items:
                    try:
                        for cached_item in _normalize_items(cached_items):
                            cached_key = str(cached_item.get("url") or cached_item.get("title") or "")
                            if cached_key and cached_key not in fresh_keys:
                                merged.append(cached_item)
                    except NewsError:
                        pass
            merged.sort(key=lambda item: str(item.get("published_at") or ""), reverse=True)
            items = merged[:MAX_NEWS_ITEMS]
            cache_payload = {
                "fetched_at": _utc_now(),
                "items": items,
                "providers": provider_states or _default_provider_states("live", len(items)),
            }
            provider_states = cache_payload["providers"]
            state = "partial" if source_errors else "live"
            status = {
                "source": "public_news_multi_source",
                "state": state,
                "last_update": cache_payload["fetched_at"],
                "message": (
                    "Public news sources partially refreshed."
                    if source_errors
                    else "Public RSS and GDELT DOC sources refreshed."
                ),
                "source_errors": source_errors,
                "source_count": source_count,
                "failed_source_count": failed_source_count,
            }

    if not items:
        cached_items = cache_payload.get("items")
        if isinstance(cached_items, list) and cached_items:
            try:
                items = _normalize_items(cached_items)[:MAX_NEWS_ITEMS]
            except NewsError:
                items = []
            if items:
                provider_states = _normalize_provider_states(cache_payload.get("providers"))
                status = {
                    "source": "local_cache",
                    "state": "stale",
                    "last_update": str(cache_payload.get("fetched_at") or "unknown"),
                    "message": "Using stale local news cache.",
                    "source_errors": [],
                    "source_count": 0,
                    "failed_source_count": 0,
                }
        else:
            items = offline_news_items()
    if not items:
        items = offline_news_items()
    if not provider_states:
        provider_states = _offline_provider_states()

    # Curation gate (R7): the curated RSS feeds are on-topic by construction, but
    # the GDELT firehose drags in fashion, regional crime, and war coverage in a
    # dozen languages. Require GDELT-origin items to actually name something
    # financial — applied here (not just at fetch) so stale junk already sitting
    # in the cache is purged on every read, not only on the next refresh.
    items = [item for item in items if not _is_gdelt_item(item) or _is_finance_relevant(item)]
    visible = _apply_filters(items, normalized_layout)
    if normalized_layout["feed_type"] == "CLST":
        visible = _clustered_wire(visible)
    clusters = _clusters(visible)
    intel = _news_intel(visible, clusters, provider_states)
    return {
        "layout": normalized_layout,
        "status": status,
        "categories": list(NEWS_CATEGORIES),
        "time_filters": list(NEWS_TIME_FILTERS),
        "sorts": list(NEWS_SORTS),
        "feed_types": list(NEWS_FEED_TYPES),
        "items": visible,
        "clusters": clusters,
        "summary": {
            # total = every item on the cached wire; visible = after the
            # layout filters below; the difference is spelled out so nobody
            # has to guess where the missing articles went.
            "total": len(items),
            "visible": len(visible),
            "hidden_by_filters": max(0, len(items) - len(visible)),
            "alerts": sum(1 for item in visible if item["alert"]),
            "watched": sum(1 for item in visible if item["watched"]),
            "sources": intel["source_count"],
            "sentiment": intel["sentiment"],
        },
        "intel": intel,
        "topic_entity_map": _news_topic_entity_map(
            normalized_layout,
            visible,
            clusters,
            provider_states,
        ),
        "cache": cache_payload,
        "safety": {
            "public_read_only": True,
            "private_api_required": False,
            "cloud_account_required": False,
            "subscription_required": False,
            "ai_summary_enabled": False,
            "full_article_copy_enabled": False,
            "article_body_storage_enabled": False,
            "gdelt_doc_no_key": True,
        },
    }


def news_topic_entity_map_payload(payload: dict[str, Any]) -> dict[str, Any]:
    layout = normalize_news_layout(
        payload.get("layout") if isinstance(payload.get("layout"), dict) else {}
    )
    items = [item for item in payload.get("items", []) if isinstance(item, dict)]
    clusters = [row for row in payload.get("clusters", []) if isinstance(row, dict)]
    intel = payload.get("intel") if isinstance(payload.get("intel"), dict) else {}
    provider_states = _normalize_provider_states(intel.get("provider_states"))
    return _news_topic_entity_map(layout, items, clusters, provider_states)


def write_news_research_brief(payload: dict[str, Any], artifact_root: Path) -> dict[str, Any]:
    """Write a metadata-only local News research brief for AI Agent inspection."""

    brief_id = f"news-brief-{datetime.now(tz=UTC).strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:8]}"
    created_at = _utc_now()
    brief_dir = artifact_root / NEWS_RESEARCH_BRIEF_ROOT / brief_id
    resolved = brief_dir.resolve()
    if not resolved.is_relative_to(artifact_root.resolve()):
        raise NewsError("Refusing to write News research brief outside repository")
    items = payload.get("items") if isinstance(payload.get("items"), list) else []
    provider_states = (
        payload.get("intel", {}).get("provider_states")
        if isinstance(payload.get("intel"), dict)
        else []
    )
    provider_states = _normalize_provider_states(provider_states)
    source_health = _news_source_health(artifact_root, brief_id, provider_states, created_at)
    brief_items = _brief_items(items)
    topics = _topic_rows(brief_items)
    artifacts = {
        "brief": f"{NEWS_RESEARCH_BRIEF_ROOT}/{brief_id}/brief.json",
        "source_health": f"{NEWS_RESEARCH_BRIEF_ROOT}/{brief_id}/source_health.json",
        "manifest": f"{NEWS_RESEARCH_BRIEF_ROOT}/{brief_id}/manifest.json",
        "report": f"{NEWS_RESEARCH_BRIEF_ROOT}/{brief_id}/brief.md",
    }
    brief = {
        "contract": "news_research_brief_v1",
        "brief_id": brief_id,
        "created_at": created_at,
        "status": payload.get("status", {}),
        "layout": payload.get("layout", {}),
        "summary": payload.get("summary", {}),
        "intel": payload.get("intel", {}),
        "topics": topics,
        "items": brief_items,
        "research_context": _brief_research_context(payload.get("research")),
        "source_health": source_health["summary"],
        "safety": _news_brief_safety(),
    }
    manifest = {
        "brief_id": brief_id,
        "artifact_contract": "news_research_brief_artifacts_v1",
        "created_at": created_at,
        "item_count": len(brief_items),
        "topic_count": len(topics),
        "provider_count": len(provider_states),
        "brief_hash": _hash_json(brief),
        "source_health": source_health["summary"],
        "artifact_files": artifacts,
        "safety": _news_brief_safety(),
    }
    brief_dir.mkdir(parents=True, exist_ok=True)
    _write_json(brief_dir / "brief.json", brief)
    _write_json(brief_dir / "source_health.json", source_health)
    _write_json(brief_dir / "manifest.json", manifest)
    _write_news_brief_markdown(brief_dir / "brief.md", brief, manifest)
    return {
        "status": "generated",
        "brief_id": brief_id,
        "created_at": created_at,
        "artifact_dir": f"{NEWS_RESEARCH_BRIEF_ROOT}/{brief_id}",
        "artifacts": artifacts,
        "summary": {
            "item_count": len(brief_items),
            "topic_count": len(topics),
            "provider_count": len(provider_states),
            "missing_source_artifact_count": source_health["summary"]["missing_cache_count"],
            "unsafe_source_artifact_count": source_health["summary"]["unsafe_cache_count"],
        },
        "safety": _news_brief_safety(),
    }


def news_research_brief_index(
    artifact_root: Path,
    *,
    max_briefs: int = 5,
) -> dict[str, Any]:
    """Return metadata-only local News brief inventory without reading contents."""

    root = artifact_root.resolve()
    brief_root = (artifact_root / NEWS_RESEARCH_BRIEF_ROOT).resolve()
    if not brief_root.is_relative_to(root):
        raise NewsError("Refusing to inspect News research briefs outside repository")
    limit = _bounded_brief_index_limit(max_briefs)
    brief_dirs = []
    if brief_root.exists():
        brief_dirs = [
            path
            for path in brief_root.iterdir()
            if path.is_dir() and path.name.startswith("news-brief-")
        ]
    brief_dirs = sorted(brief_dirs, key=lambda path: path.stat().st_mtime, reverse=True)[:limit]
    rows = [_news_brief_index_row(root, brief_dir) for brief_dir in brief_dirs]
    missing_artifact_count = sum(_int(row.get("missing_artifact_count")) for row in rows)
    recovery_queue = _news_brief_index_recovery_queue(rows)
    return {
        "mode": "metadata_only_news_research_brief_index",
        "contract": "news_research_brief_index_v1",
        "generated_at": _utc_now(),
        "root": NEWS_RESEARCH_BRIEF_ROOT,
        "summary": {
            "brief_count": len(rows),
            "complete_brief_count": sum(1 for row in rows if bool(row.get("complete"))),
            "incomplete_brief_count": sum(1 for row in rows if not bool(row.get("complete"))),
            "missing_artifact_count": missing_artifact_count,
            "newest_brief_id": str(rows[0]["brief_id"]) if rows else "",
            "recovery_queue_count": len(recovery_queue),
        },
        "briefs": rows,
        "recovery_queue": recovery_queue,
        "safety": {
            "metadata_only": True,
            "file_content_read": False,
            "article_body_read": False,
            "full_article_copy_enabled": False,
            "ai_summary_enabled": False,
            "cloud_account_required": False,
            "subscription_required": False,
            "destructive_actions_enabled": False,
            "live_trading": False,
            "secret_values_returned": False,
        },
    }


def fetch_public_news() -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    errors = []
    provider_states = []
    for source in PUBLIC_RSS_SOURCES:
        try:
            request = urllib.request.Request(
                source["url"],
                headers={"User-Agent": "LocalTerminal/0.1 clean-room local app"},
            )
            with urllib.request.urlopen(request, timeout=8) as response:
                body = response.read()
            parsed = _parse_rss(body, source)
            items.extend(parsed)
            provider_states.append(
                _provider_state(
                    provider_id=str(source["source_id"]),
                    label=str(source["label"]),
                    state="live",
                    item_count=len(parsed),
                    docs_url=str(source["url"]),
                    message="Public RSS feed refreshed.",
                )
            )
        except (OSError, ET.ParseError, urllib.error.URLError) as exc:
            errors.append(f"{source['label']}: {_clean_error(exc)}")
            provider_states.append(
                _provider_state(
                    provider_id=str(source["source_id"]),
                    label=str(source["label"]),
                    state="unavailable",
                    item_count=0,
                    docs_url=str(source["url"]),
                    message="Public RSS feed unavailable.",
                    failed=True,
                )
            )
    try:
        gdelt_items = fetch_gdelt_doc_articles()
    except (NewsError, OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        errors.append(f"GDELT DOC: {_clean_error(exc)}")
        provider_states.append(
            _provider_state(
                provider_id=GDELT_DOC_PROVIDER_ID,
                label="GDELT DOC 2.0",
                state="unavailable",
                item_count=0,
                docs_url=GDELT_DOC_DOCS_URL,
                message="GDELT DOC metadata refresh unavailable.",
                failed=True,
            )
        )
    else:
        gdelt_items = [item for item in gdelt_items if _is_finance_relevant(item)]
        items.extend(gdelt_items)
        provider_states.append(
            _provider_state(
                provider_id=GDELT_DOC_PROVIDER_ID,
                label="GDELT DOC 2.0",
                state="live",
                item_count=len(gdelt_items),
                docs_url=GDELT_DOC_DOCS_URL,
                message="GDELT DOC ArticleList metadata refreshed.",
            )
        )
    if not items and errors:
        raise NewsError("Public news refresh failed")
    return {
        "items": items,
        "errors": errors,
        "source_count": len(PUBLIC_RSS_SOURCES) + 1,
        "failed_source_count": len(errors),
        "providers": provider_states,
    }


def fetch_gdelt_doc_articles(
    *,
    query: str = GDELT_DOC_QUERY,
    max_records: int = GDELT_DOC_MAX_RECORDS,
    opener: Any | None = None,
) -> list[dict[str, Any]]:
    params = {
        "query": query,
        "mode": "artlist",
        "format": "json",
        "maxrecords": str(max(1, min(max_records, 75))),
        "sort": "datedesc",
    }
    url = f"{GDELT_DOC_ENDPOINT}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "LocalTerminal/0.1 clean-room local app"},
    )
    open_url = opener or urllib.request.urlopen
    body: bytes | None = None
    last_error: Exception | None = None
    # GDELT serves a complete JSON payload alongside its 429 rate-limit code —
    # discarding it turned a throttle into a fake outage (2026-07-22 owner
    # fix-it round). A transient SSL/handshake timeout gets one quick retry.
    for attempt in (1, 2):
        try:
            # 20s, not the default 8: when GDELT throttles it also stalls the
            # TLS handshake, and curl-level probes confirm the payload arrives
            # after the 8s mark — a tight timeout misreads slow as down.
            with open_url(request, timeout=20) as response:
                body = response.read()
            break
        except urllib.error.HTTPError as exc:
            candidate = exc.read()
            try:
                probe = json.loads(candidate.decode("utf-8-sig"))
            except (ValueError, UnicodeDecodeError):
                probe = None
            if isinstance(probe, dict) and isinstance(probe.get("articles"), list):
                body = candidate
                break
            raise NewsError(
                f"GDELT DOC rate limited or unavailable (HTTP {exc.code}); "
                "retry after the per-IP throttle window"
            ) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
            if attempt == 2:
                raise
    if body is None:  # pragma: no cover - loop always breaks or raises
        raise NewsError(f"GDELT DOC fetch failed: {last_error}")
    payload = json.loads(body.decode("utf-8-sig"))
    articles = payload.get("articles") if isinstance(payload, dict) else None
    if not isinstance(articles, list):
        raise NewsError("GDELT DOC response did not include article metadata")
    return [
        item
        for item in (_parse_gdelt_article(article) for article in articles)
        if item is not None
    ]


def offline_news_items() -> list[dict[str, Any]]:
    now = datetime.now(tz=UTC)
    seeds = [
        ("MKT", "Public markets digest flags softer breadth before the open", "SPY,QQQ", "Local Wire"),
        ("EARN", "Earnings calendar highlights large-cap software reports", "MSFT,NVDA", "Local Wire"),
        ("ECO", "Central-bank schedule keeps rates and inflation in focus", "USD,RATES", "Local Wire"),
        ("TECH", "AI infrastructure spending remains the dominant technology theme", "AI,CHIPS", "Local Wire"),
        ("NRG", "Energy desks track crude supply headlines and refinery margins", "OIL,NRG", "Local Wire"),
        ("CRPT", "Crypto market watch keeps BTC and ETH liquidity in view", "BTC,ETH", "Local Wire"),
        ("GEO", "Geopolitical risk monitor watches shipping and sanctions events", "GEO,SHIPPING", "Local Wire"),
    ]
    items = []
    for index, (category, title, tags, source) in enumerate(seeds):
        published = now - timedelta(hours=index * 3)
        items.append(
            _normalize_item(
                {
                    "item_id": f"offline-{category.lower()}",
                    "title": title,
                    "source": source,
                    "category": category,
                    "published_at": published.isoformat().replace("+00:00", "Z"),
                    "url": "",
                    "summary": "Local fallback item used when public RSS is unavailable.",
                    "tags": tags.split(","),
                }
            )
        )
    return items


def _normalize_items(raw_items: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_items, list):
        raise NewsError("News items must be a list")
    return [_normalize_item(item) for item in raw_items if isinstance(item, dict)]


def _stable_item_hash(identity: str, length: int = 10) -> str:
    """Deterministic item id from the article's canonical identity (its URL).

    Ids used to be uuid4-per-fetch, so the SAME article changed id on every
    refresh — anything keyed by item_id (the operator's zh digest) silently
    fell off. Hashing the link keeps ids stable across refreshes.
    """
    return hashlib.sha1(identity.encode("utf-8", "replace")).hexdigest()[:length]


def _parse_rss(body: bytes, source: dict[str, str]) -> list[dict[str, Any]]:
    root = ET.fromstring(body)
    parsed_items = []
    for node in root.findall(".//item")[:40]:
        title = _node_text(node, "title")
        if not title:
            continue
        published = _parse_date(_node_text(node, "pubDate") or _node_text(node, "updated"))
        summary = html.unescape(_node_text(node, "description"))[:280]
        link = _node_text(node, "link")
        parsed_items.append(
            {
                "item_id": f"{source['source_id']}-{_stable_item_hash(link or title)}",
                "title": html.unescape(title),
                "source": source["label"],
                "category": _infer_category(title, summary, source["category"]),
                "published_at": published,
                "url": link,
                "summary": _clean_summary(summary),
                "tags": _tags_from_text(f"{title} {summary}"),
            }
        )
    return parsed_items


def _parse_gdelt_article(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    title = str(raw.get("title") or "").strip()
    url = str(raw.get("url") or "").strip()
    if not title or not url:
        return None
    domain = str(raw.get("domain") or "").strip()
    source_country = str(raw.get("sourcecountry") or raw.get("sourceCountry") or "").strip()
    language = str(raw.get("language") or "").strip()
    published_at = _parse_gdelt_date(str(raw.get("seendate") or raw.get("seenDate") or ""))
    source = domain or "GDELT DOC"
    return {
        "item_id": f"gdelt-{_stable_item_hash(url, 12)}",
        "title": html.unescape(title),
        "source": source,
        "category": _infer_category(title, "", "MKT"),
        "published_at": published_at,
        "url": url,
        "summary": "GDELT DOC metadata-only article hit; no full article body is stored.",
        "tags": _tags_from_text(f"{title} {domain} {source_country}"),
        "provider_id": GDELT_DOC_PROVIDER_ID,
        "domain": domain,
        "source_country": source_country,
        "language": language,
    }


def _normalize_item(raw: dict[str, Any]) -> dict[str, Any]:
    title = str(raw.get("title") or "").strip()
    if not title:
        raise NewsError("News item title is required")
    category = str(raw.get("category") or "MKT").upper()
    if category not in NEWS_CATEGORIES or category == "ALL":
        category = "MKT"
    published_at = _parse_date(str(raw.get("published_at") or ""))
    tags = _normalize_watch_terms(raw.get("tags", []))
    return {
        "item_id": str(raw.get("item_id") or f"news-{uuid4().hex[:12]}"),
        "title": title[:240],
        "source": str(raw.get("source") or "Public RSS")[:80],
        "category": category,
        "published_at": published_at,
        "age_minutes": _age_minutes(published_at),
        "url": str(raw.get("url") or "")[:500],
        "summary": str(raw.get("summary") or "")[:360],
        "tags": tags,
        "alert": _is_alert(title),
        "watched": False,
        "relevance": _relevance(title, tags),
        "provider_id": str(raw.get("provider_id") or "public_rss_news")[:80],
        "domain": str(raw.get("domain") or "")[:120],
        "source_country": str(raw.get("source_country") or "")[:80],
        "language": str(raw.get("language") or "")[:40],
    }


def _apply_filters(items: list[dict[str, Any]], layout: dict[str, Any]) -> list[dict[str, Any]]:
    window = _time_window(layout["time_filter"])
    watch_terms = layout["watch_terms"]
    visible = []
    for item in items:
        candidate = dict(item)
        candidate["watched"] = _matches_watch(candidate, watch_terms)
        if layout["category"] != "ALL" and candidate["category"] != layout["category"]:
            continue
        if _published_datetime(candidate["published_at"]) < window:
            continue
        if layout["watch_only"] and not candidate["watched"]:
            continue
        visible.append(candidate)
    key = (
        (lambda item: _published_datetime(item["published_at"]))
        if layout["sort"] == "NEW"
        else (lambda item: (int(item["watched"]), int(item["alert"]), item["relevance"]))
    )
    return sorted(visible, key=key, reverse=True)[:MAX_NEWS_ITEMS]


def _clustered_wire(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    clusters: dict[str, dict[str, Any]] = {}
    for item in items:
        key = _cluster_key(item)
        if key not in clusters:
            clusters[key] = {**item, "cluster_size": 1}
        else:
            clusters[key]["cluster_size"] += 1
    return sorted(
        clusters.values(),
        key=lambda item: (item["cluster_size"], item["relevance"], _published_datetime(item["published_at"])),
        reverse=True,
    )


def _clusters(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for item in items:
        counts[item["category"]] = counts.get(item["category"], 0) + 1
    return [
        {"category": category, "count": count}
        for category, count in sorted(counts.items(), key=lambda item: item[1], reverse=True)
    ]


def _node_text(node: ET.Element, name: str) -> str:
    child = node.find(name)
    return child.text.strip() if child is not None and child.text else ""


_UNKNOWN_PUBLISHED = datetime(1970, 1, 1, tzinfo=UTC)


def _parse_date(raw: str) -> str:
    # An unparseable date must NOT become "now" — that would float a garbled or
    # weeks-old item to the top of every recency view. Return "" (unknown) and
    # let the sort/age helpers treat it as very old instead of very fresh.
    if not raw:
        return ""
    try:
        parsed = email.utils.parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return ""
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _published_datetime(raw: str) -> datetime:
    if not raw:
        return _UNKNOWN_PUBLISHED
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return _UNKNOWN_PUBLISHED


def _age_minutes(published_at: str) -> int:
    age = datetime.now(tz=UTC) - _published_datetime(published_at)
    return max(0, int(age.total_seconds() // 60))


def _time_window(filter_id: str) -> datetime:
    hours = {
        "1H": 1,
        "6H": 6,
        "24H": 24,
        "48H": 48,
        "7D": 24 * 7,
        "30D": 24 * 30,
    }[filter_id]
    return datetime.now(tz=UTC) - timedelta(hours=hours)


def _infer_category(title: str, summary: str, default: str) -> str:
    text = f"{title} {summary}".lower()
    if any(term in text for term in ("bitcoin", "crypto", "ether", "token", "blockchain")):
        return "CRPT"
    if any(term in text for term in ("energy", "oil", "gas", "refinery", "crude")):
        return "NRG"
    if any(term in text for term in ("earnings", "revenue", "profit", "eps")):
        return "EARN"
    if any(term in text for term in ("rate", "inflation", "fed", "central bank", "treasury")):
        return "ECO"
    if any(term in text for term in ("chip", "software", "ai", "technology", "semiconductor")):
        return "TECH"
    if any(term in text for term in ("sanction", "election", "war", "shipping", "border")):
        return "GEO"
    return default


def _tags_from_text(text: str) -> list[str]:
    symbols = []
    for token in text.replace("$", " ").replace(",", " ").split():
        cleaned = "".join(ch for ch in token.upper() if ch.isalnum())
        if 2 <= len(cleaned) <= 8 and cleaned in {
            "BTC",
            "ETH",
            "USD",
            "SPY",
            "QQQ",
            "AI",
            "OIL",
            "FED",
            "SEC",
            "LNG",
            "GAS",
            "ECB",
            "BOE",
            "VIX",
            "NVDA",
        }:
            symbols.append(cleaned)
    return list(dict.fromkeys(symbols))[:6]


def _normalize_watch_terms(raw_terms: Any) -> list[str]:
    if isinstance(raw_terms, str):
        raw_terms = raw_terms.split(",")
    if not isinstance(raw_terms, list):
        return []
    terms = []
    for raw in raw_terms:
        term = "".join(ch for ch in str(raw).upper().strip() if ch.isalnum() or ch in {"-", "."})
        if term:
            terms.append(term[:24])
    return list(dict.fromkeys(terms))[:MAX_WATCH_TERMS]


def _matches_watch(item: dict[str, Any], watch_terms: list[str]) -> bool:
    if not watch_terms:
        return False
    text = f"{item['title']} {' '.join(item['tags'])}".upper()
    return any(term in text for term in watch_terms)


def _clean_summary(raw: str) -> str:
    text = " ".join(html.unescape(raw).replace("\n", " ").split())
    while "<" in text and ">" in text:
        start = text.find("<")
        end = text.find(">", start)
        if end == -1:
            break
        text = text[:start] + text[end + 1 :]
    return text[:280]


def _is_alert(title: str) -> bool:
    return any(term in title.lower() for term in ("breaking", "alert", "urgent", "warns", "risk"))


def _relevance(title: str, tags: list[str]) -> int:
    return min(100, len(tags) * 12 + (20 if _is_alert(title) else 0) + min(len(title), 120) // 6)


def _cluster_key(item: dict[str, Any]) -> str:
    tags = item.get("tags") if isinstance(item.get("tags"), list) else []
    if tags:
        return f"{item['category']}:{tags[0]}"
    title = str(item.get("title") or "").lower()
    for keyword in (
        "oil",
        "energy",
        "gas",
        "ai",
        "nvidia",
        "fed",
        "rate",
        "inflation",
        "bitcoin",
        "crypto",
        "war",
        "shipping",
        "earnings",
    ):
        if keyword in title:
            return f"{item['category']}:{keyword}"
    source = str(item.get("source") or "source").lower()
    return f"{item['category']}:{source}"


def _news_intel(
    visible: list[dict[str, Any]],
    clusters: list[dict[str, Any]],
    provider_states: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "feed_count": sum(int(provider.get("source_count", 1)) for provider in provider_states),
        "article_count": len(visible),
        "cluster_count": len(clusters),
        "source_count": len({str(item.get("source") or "") for item in visible if item.get("source")}),
        "sentiment": _sentiment_score(visible),
        "watch_count": sum(1 for item in visible if item.get("watched")),
        "provider_states": provider_states,
        "contract": {
            "mode": "metadata_only_news_intel",
            "full_article_body": False,
            "links_only": True,
            "no_key_public_sources": True,
        },
    }


def _news_topic_entity_map(
    layout: dict[str, Any],
    items: list[dict[str, Any]],
    clusters: list[dict[str, Any]],
    provider_states: list[dict[str, Any]],
) -> dict[str, Any]:
    entities = _news_entity_rows(items, layout.get("watch_terms", []))
    topics = _news_topic_rows(items, clusters)
    edges = _news_topic_entity_edges(items)
    return {
        "mode": "metadata_only_news_topic_entity_map",
        "contract": "news_topic_entity_map_v1",
        "generated_at": _utc_now(),
        "layout_scope": {
            "category": str(layout.get("category") or "ALL"),
            "time_filter": str(layout.get("time_filter") or "24H"),
            "feed_type": str(layout.get("feed_type") or "WIRE"),
            "watch_only": bool(layout.get("watch_only")),
        },
        "summary": {
            "item_count": len(items),
            "topic_count": len(topics),
            "entity_count": len(entities),
            "edge_count": len(edges),
            "watched_entity_count": sum(1 for row in entities if row["watched_item_count"]),
            "alert_entity_count": sum(1 for row in entities if row["alert_count"]),
            "provider_count": len(provider_states),
            "source_count": len({str(item.get("source") or "") for item in items if item.get("source")}),
        },
        "topics": topics,
        "entities": entities,
        "edges": edges,
        "provider_states": provider_states,
        "recommended_actions": [
            {
                "action_id": "news_refresh",
                "ready": not items,
                "safe": True,
                "reason": "Refresh public News metadata if the map has no visible items.",
            },
            {
                "action_id": "news_research_brief",
                "ready": bool(items),
                "safe": True,
                "reason": "Write a metadata-only local brief after reviewing topic/entity coverage.",
            },
        ],
        "safety": {
            "metadata_only": True,
            "payload_derived_only": True,
            "provider_refresh_performed": False,
            "writes_local_artifacts": False,
            "file_content_read": False,
            "article_body_read": False,
            "article_body_storage_enabled": False,
            "full_article_copy_enabled": False,
            "ai_summary_enabled": False,
            "secret_values_returned": False,
            "destructive_actions_enabled": False,
            "live_trading": False,
        },
    }


def _news_entity_rows(items: list[dict[str, Any]], watch_terms: Any) -> list[dict[str, Any]]:
    normalized_watch = set(_normalize_watch_terms(watch_terms))
    rows: dict[str, dict[str, Any]] = {}
    for item in items:
        tags = item.get("tags") if isinstance(item.get("tags"), list) else []
        for tag in tags:
            label = _entity_label(tag)
            if not label:
                continue
            entity_id = f"tag:{label.lower()}"
            row = rows.setdefault(
                entity_id,
                {
                    "entity_id": entity_id,
                    "label": label,
                    "kind": "watch_term" if label in normalized_watch else "tag",
                    "item_count": 0,
                    "watched_item_count": 0,
                    "alert_count": 0,
                    "topic_count": 0,
                    "categories": set(),
                    "sources": set(),
                    "latest_published_at": "",
                    "sample_item_ids": [],
                },
            )
            row["item_count"] += 1
            row["watched_item_count"] += 1 if item.get("watched") else 0
            row["alert_count"] += 1 if item.get("alert") else 0
            row["categories"].add(str(item.get("category") or "MKT"))
            source = str(item.get("source") or "")
            if source:
                row["sources"].add(source)
            published_at = str(item.get("published_at") or "")
            row["latest_published_at"] = max(row["latest_published_at"], published_at)
            item_id = str(item.get("item_id") or "")
            if item_id and item_id not in row["sample_item_ids"] and len(row["sample_item_ids"]) < 5:
                row["sample_item_ids"].append(item_id)
    cleaned = []
    for row in rows.values():
        categories = sorted(row.pop("categories"))
        sources = sorted(row.pop("sources"))
        row["categories"] = categories[:6]
        row["sources"] = sources[:6]
        row["topic_count"] = len(categories)
        cleaned.append(row)
    return sorted(cleaned, key=lambda row: (-int(row["item_count"]), str(row["label"])))[:24]


def _news_topic_rows(
    items: list[dict[str, Any]],
    clusters: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    cluster_counts: dict[str, int] = {}
    for cluster in clusters:
        category = str(cluster.get("category") or "MKT")
        cluster_counts[category] = cluster_counts.get(category, 0) + int(cluster.get("count") or 0)
    for item in items:
        category = str(item.get("category") or "MKT")
        topic_id = f"topic:{category.lower()}"
        row = rows.setdefault(
            topic_id,
            {
                "topic_id": topic_id,
                "label": category,
                "item_count": 0,
                "cluster_item_count": cluster_counts.get(category, 0),
                "watched_item_count": 0,
                "alert_count": 0,
                "source_count": 0,
                "sources": set(),
                "top_entities": {},
                "latest_published_at": "",
                "sample_item_ids": [],
            },
        )
        row["item_count"] += 1
        row["watched_item_count"] += 1 if item.get("watched") else 0
        row["alert_count"] += 1 if item.get("alert") else 0
        source = str(item.get("source") or "")
        if source:
            row["sources"].add(source)
        tags = item.get("tags") if isinstance(item.get("tags"), list) else []
        for tag in tags:
            label = _entity_label(tag)
            if label:
                row["top_entities"][label] = row["top_entities"].get(label, 0) + 1
        published_at = str(item.get("published_at") or "")
        row["latest_published_at"] = max(row["latest_published_at"], published_at)
        item_id = str(item.get("item_id") or "")
        if item_id and item_id not in row["sample_item_ids"] and len(row["sample_item_ids"]) < 5:
            row["sample_item_ids"].append(item_id)
    cleaned = []
    for row in rows.values():
        sources = sorted(row.pop("sources"))
        entity_counts = row.pop("top_entities")
        row["sources"] = sources[:6]
        row["source_count"] = len(sources)
        row["top_entities"] = [
            {"label": label, "item_count": count}
            for label, count in sorted(entity_counts.items(), key=lambda item: (-item[1], item[0]))[:6]
        ]
        cleaned.append(row)
    return sorted(cleaned, key=lambda row: (-int(row["item_count"]), str(row["label"])))


def _news_topic_entity_edges(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    edges: dict[tuple[str, str], int] = {}
    for item in items:
        category = str(item.get("category") or "MKT")
        topic_id = f"topic:{category.lower()}"
        tags = item.get("tags") if isinstance(item.get("tags"), list) else []
        for tag in tags:
            label = _entity_label(tag)
            if not label:
                continue
            entity_id = f"tag:{label.lower()}"
            key = (topic_id, entity_id)
            edges[key] = edges.get(key, 0) + 1
    rows = [
        {"topic_id": topic_id, "entity_id": entity_id, "item_count": count}
        for (topic_id, entity_id), count in edges.items()
    ]
    return sorted(rows, key=lambda row: (-row["item_count"], row["topic_id"], row["entity_id"]))[:48]


def _entity_label(raw: Any) -> str:
    return "".join(ch for ch in str(raw).upper().strip() if ch.isalnum() or ch in {"-", "."})[:24]


def _sentiment_score(items: list[dict[str, Any]]) -> str:
    if not items:
        return "+0.00"
    positive = ("rise", "gain", "growth", "higher", "surge", "improves", "progress")
    negative = ("risk", "falls", "loss", "war", "crisis", "toxic", "warn", "weakens")
    score = 0
    for item in items:
        text = str(item.get("title") or "").lower()
        score += sum(1 for word in positive if word in text)
        score -= sum(1 for word in negative if word in text)
    normalized = max(-1.0, min(1.0, score / max(1, len(items))))
    return f"{normalized:+.2f}"


def _provider_state(
    *,
    provider_id: str,
    label: str,
    state: str,
    item_count: int,
    docs_url: str,
    message: str,
    failed: bool = False,
) -> dict[str, Any]:
    return {
        "provider_id": provider_id,
        "label": label,
        "state": state,
        "source_count": 1,
        "item_count": max(0, int(item_count)),
        "failed": failed,
        "docs_url": docs_url,
        "cache_path": NEWS_CACHE_PATH,
        "message": message,
    }


def _normalize_provider_states(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    states = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        states.append(
            {
                "provider_id": str(row.get("provider_id") or "public_news_source")[:80],
                "label": str(row.get("label") or row.get("provider_id") or "Public news source")[:120],
                "state": str(row.get("state") or "unavailable")[:40],
                "source_count": _int(row.get("source_count"), default=1),
                "item_count": _int(row.get("item_count"), default=0),
                "failed": bool(row.get("failed", False)),
                "docs_url": str(row.get("docs_url") or "")[:500],
                "cache_path": str(row.get("cache_path") or NEWS_CACHE_PATH)[:240],
                "message": str(row.get("message") or "")[:240],
            }
        )
    return states


def _default_provider_states(state: str, item_count: int) -> list[dict[str, Any]]:
    return [
        _provider_state(
            provider_id="public_news_multi_source",
            label="Public news sources",
            state=state,
            item_count=item_count,
            docs_url=GDELT_DOC_DOCS_URL,
            message="Fetcher returned normalized public news items.",
        )
    ]


def _offline_provider_states() -> list[dict[str, Any]]:
    return [
        _provider_state(
            provider_id="public_rss_news",
            label="Public RSS news feeds",
            state="unavailable",
            item_count=0,
            docs_url="configured public RSS URLs",
            message="No live public RSS cache is available.",
        ),
        _provider_state(
            provider_id=GDELT_DOC_PROVIDER_ID,
            label="GDELT DOC 2.0",
            state="unavailable",
            item_count=0,
            docs_url=GDELT_DOC_DOCS_URL,
            message="No live GDELT DOC ArticleList cache is available.",
        ),
        _provider_state(
            provider_id="offline_news_fixture",
            label="Offline local fallback",
            state="offline",
            item_count=0,
            docs_url="",
            message="Local fallback is visible only when public sources and cache are unavailable.",
        )
    ]


def _brief_items(items: list[Any]) -> list[dict[str, Any]]:
    brief_items = []
    for raw in items[:40]:
        if not isinstance(raw, dict):
            continue
        brief_items.append(
            {
                "item_id": str(raw.get("item_id") or "")[:120],
                "title": str(raw.get("title") or "")[:240],
                "source": str(raw.get("source") or "")[:80],
                "category": str(raw.get("category") or "")[:20],
                "published_at": str(raw.get("published_at") or "")[:80],
                "url": str(raw.get("url") or "")[:500],
                "summary": str(raw.get("summary") or "")[:360],
                "tags": _normalize_watch_terms(raw.get("tags", [])),
                "provider_id": str(raw.get("provider_id") or "public_rss_news")[:80],
                "domain": str(raw.get("domain") or "")[:120],
                "source_country": str(raw.get("source_country") or "")[:80],
                "language": str(raw.get("language") or "")[:40],
                "watched": bool(raw.get("watched", False)),
                "alert": bool(raw.get("alert", False)),
                "relevance": _int(raw.get("relevance"), default=0),
            }
        )
    return brief_items


def _topic_rows(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    topics: dict[str, dict[str, Any]] = {}
    for item in items:
        item_topics = item.get("tags") if isinstance(item.get("tags"), list) else []
        if not item_topics:
            item_topics = [str(item.get("category") or "MKT")]
        for topic in item_topics[:4]:
            key = str(topic or "").upper()[:24]
            if not key:
                continue
            row = topics.setdefault(
                key,
                {
                    "topic": key,
                    "count": 0,
                    "categories": set(),
                    "sources": set(),
                    "provider_ids": set(),
                },
            )
            row["count"] += 1
            row["categories"].add(str(item.get("category") or ""))
            row["sources"].add(str(item.get("source") or ""))
            row["provider_ids"].add(str(item.get("provider_id") or ""))
    rows = []
    for row in sorted(topics.values(), key=lambda value: value["count"], reverse=True)[:12]:
        rows.append(
            {
                "topic": row["topic"],
                "count": row["count"],
                "categories": sorted(value for value in row["categories"] if value)[:6],
                "sources": sorted(value for value in row["sources"] if value)[:6],
                "provider_ids": sorted(value for value in row["provider_ids"] if value)[:6],
            }
        )
    return rows


def _brief_research_context(raw_research: Any) -> dict[str, Any]:
    research = raw_research if isinstance(raw_research, dict) else {}
    macro = research.get("macro") if isinstance(research.get("macro"), dict) else {}
    fundamentals = (
        research.get("fundamentals") if isinstance(research.get("fundamentals"), dict) else {}
    )
    fred = research.get("fred") if isinstance(research.get("fred"), dict) else {}
    bls = research.get("bls") if isinstance(research.get("bls"), dict) else {}
    return {
        "status": research.get("status", {}),
        "macro_summary": macro.get("summary", {}),
        "fundamentals_summary": fundamentals.get("summary", {}),
        "fred_summary": fred.get("summary", {}),
        "bls_summary": bls.get("summary", {}),
        "provider_entry": research.get("provider_entry", {}),
    }


def _news_source_health(
    artifact_root: Path,
    brief_id: str,
    provider_states: list[dict[str, Any]],
    created_at: str,
) -> dict[str, Any]:
    rows = []
    missing_count = 0
    unsafe_count = 0
    root = artifact_root.resolve()
    for provider in provider_states:
        cache_path = _safe_news_cache_path(provider.get("cache_path"))
        if not cache_path:
            unsafe_count += 1
            rows.append(
                {
                    "provider_id": provider["provider_id"],
                    "cache_path": "unsafe_news_cache_path",
                    "status": "unsafe_ignored",
                    "exists": False,
                    "sha256": "",
                    "recovery_hint": "Refresh News or inspect provider state; no mutation performed.",
                }
            )
            continue
        candidate = (artifact_root / cache_path).resolve()
        exists = candidate.is_relative_to(root) and candidate.is_file()
        if not exists:
            missing_count += 1
        rows.append(
            {
                "provider_id": provider["provider_id"],
                "cache_path": cache_path,
                "status": "available" if exists else "missing",
                "exists": exists,
                "sha256": _sha256_file(candidate) if exists else "",
                "recovery_hint": (
                    "available"
                    if exists
                    else "Refresh News to regenerate the metadata-only cache."
                ),
            }
        )
    status = "complete" if rows and not missing_count and not unsafe_count else "recovery_queue"
    if not rows:
        status = "no_provider_state"
    return {
        "contract": "news_source_health_v1",
        "brief_id": brief_id,
        "created_at": created_at,
        "status": status,
        "summary": {
            "provider_count": len(rows),
            "available_cache_count": sum(1 for row in rows if row["exists"]),
            "missing_cache_count": missing_count,
            "unsafe_cache_count": unsafe_count,
        },
        "rows": rows,
        "recovery_queue": [
            {
                "provider_id": row["provider_id"],
                "cache_path": row["cache_path"],
                "recommended_action": "news_refresh",
                "destructive_action_required": False,
            }
            for row in rows
            if row["status"] != "available"
        ],
        "safety": {
            "read_only": True,
            "destructive_actions_enabled": False,
            "full_article_copy_enabled": False,
            "secret_values_returned": False,
        },
    }


def _safe_news_cache_path(raw_path: Any) -> str:
    path = str(raw_path or "").strip().replace("\\", "/")[:240]
    if not path.startswith("artifacts/news/"):
        return ""
    if ".." in Path(path).parts:
        return ""
    lowered = path.lower()
    if any(term in lowered for term in ("api_key", "password", "private_key", "secret", "token")):
        return ""
    return path


def _news_brief_index_row(root: Path, brief_dir: Path) -> dict[str, Any]:
    resolved = brief_dir.resolve()
    if not resolved.is_relative_to(root):
        raise NewsError("Refusing to inspect News research brief outside repository")
    artifacts = {
        NEWS_RESEARCH_BRIEF_ARTIFACT_KEYS[name]: f"{NEWS_RESEARCH_BRIEF_ROOT}/{brief_dir.name}/{name}"
        for name in NEWS_RESEARCH_BRIEF_FILES
    }
    file_rows = []
    total_bytes = 0
    latest_timestamp = 0.0
    for filename in NEWS_RESEARCH_BRIEF_FILES:
        path = brief_dir / filename
        exists = path.is_file()
        stat = path.stat() if exists else None
        size = stat.st_size if stat else 0
        updated_at = stat.st_mtime if stat else 0.0
        total_bytes += size
        latest_timestamp = max(latest_timestamp, updated_at)
        file_rows.append(
            {
                "name": filename,
                "path": f"{NEWS_RESEARCH_BRIEF_ROOT}/{brief_dir.name}/{filename}",
                "exists": exists,
                "bytes": size,
            }
        )
    missing = [row for row in file_rows if not row["exists"]]
    return {
        "brief_id": brief_dir.name,
        "artifact_dir": f"{NEWS_RESEARCH_BRIEF_ROOT}/{brief_dir.name}",
        "artifacts": artifacts,
        "artifact_count": len(file_rows) - len(missing),
        "missing_artifact_count": len(missing),
        "total_bytes": total_bytes,
        "latest_updated_at": _timestamp_text(latest_timestamp),
        "complete": not missing,
        "files": file_rows,
    }


def _news_brief_index_recovery_queue(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not rows:
        return [
            {
                "queue_id": "news_research_brief_index:none",
                "brief_id": "",
                "artifact_path": NEWS_RESEARCH_BRIEF_ROOT,
                "recommended_action": "news_research_brief",
                "endpoint": "/api/news/research-brief",
                "reason": "No local News research brief artifacts found.",
                "destructive_action_required": False,
                "writes_local_artifacts": True,
            }
        ]
    queue = []
    for row in rows:
        for file_row in row["files"]:
            if bool(file_row.get("exists")):
                continue
            queue.append(
                {
                    "queue_id": f"news_research_brief_index:{row['brief_id']}:{file_row['name']}",
                    "brief_id": row["brief_id"],
                    "artifact_path": file_row["path"],
                    "recommended_action": "news_research_brief",
                    "endpoint": "/api/news/research-brief",
                    "reason": f"Missing News research brief artifact {file_row['name']}.",
                    "destructive_action_required": False,
                    "writes_local_artifacts": True,
                }
            )
    return queue


def _bounded_brief_index_limit(raw_value: Any) -> int:
    value = _int(raw_value, default=5)
    if value < 1:
        return 1
    if value > 20:
        return 20
    return value


def _timestamp_text(timestamp: float) -> str:
    if timestamp <= 0:
        return ""
    return datetime.fromtimestamp(timestamp, tz=UTC).isoformat(timespec="seconds").replace(
        "+00:00",
        "Z",
    )


def _news_brief_safety() -> dict[str, bool]:
    return {
        "metadata_only": True,
        "public_read_only": True,
        "full_article_copy_enabled": False,
        "article_body_storage_enabled": False,
        "ai_summary_enabled": False,
        "cloud_account_required": False,
        "subscription_required": False,
        "destructive_actions_enabled": False,
        "live_trading": False,
    }


def _write_news_brief_markdown(path: Path, brief: dict[str, Any], manifest: dict[str, Any]) -> None:
    lines = [
        f"# News Research Brief {brief['brief_id']}",
        "",
        f"- Created: {brief['created_at']}",
        f"- Status: {brief.get('status', {}).get('state', 'unknown')}",
        f"- Items: {manifest['item_count']}",
        f"- Topics: {manifest['topic_count']}",
        "- Safety: metadata only, links only, no full article copy, no AI summary",
        "",
        "## Topics",
    ]
    lines.extend(f"- {row['topic']}: {row['count']}" for row in brief["topics"])
    lines.append("")
    lines.append("## Top Items")
    lines.extend(
        f"- [{item['category']}] {item['title']} ({item['source']})"
        for item in brief["items"][:12]
    )
    lines.append("")
    lines.append("## Artifacts")
    lines.extend(f"- {name}: {artifact}" for name, artifact in manifest["artifact_files"].items())
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _hash_json(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError:
        return ""
    return digest.hexdigest()


def _parse_gdelt_date(raw: str) -> str:
    digits = "".join(ch for ch in raw if ch.isdigit())
    try:
        if len(digits) >= 14:
            parsed = datetime.strptime(digits[:14], "%Y%m%d%H%M%S").replace(tzinfo=UTC)
            return parsed.isoformat(timespec="seconds").replace("+00:00", "Z")
        if len(digits) >= 8:
            parsed = datetime.strptime(digits[:8], "%Y%m%d").replace(tzinfo=UTC)
            return parsed.isoformat(timespec="seconds").replace("+00:00", "Z")
    except ValueError:
        pass
    return _parse_date(raw)


def _clean_error(exc: BaseException) -> str:
    return " ".join(str(exc).replace("\n", " ").split())[:180]


def _int(value: Any, *, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _utc_now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
