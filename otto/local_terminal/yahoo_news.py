"""Yahoo Finance public per-symbol news adapter — no key, no order semantics.

The 2026-07-24 decision drill hit a real wall: the news packet (GDELT + a
Taiwan feed) surfaces broad-market and TW headlines but almost no US
single-name catalyst, so a -7% move in GOOGL came back with zero Alphabet
news and the call had to be abstained. Flagging that as a "limitation" was the
same not-solving-the-problem reflex the owner keeps correcting.

This is the fix. Yahoo's public `v1/finance/search` endpoint returns a `news`
array per query with no credential — the same host the quote adapter already
uses. This module fetches a symbol's headlines and normalizes them into the
exact item shape the news packet already consumes, so US single-name catalysts
show up alongside the existing sources and the packet's keyword matcher tags
them to the holding.

Same honesty conventions as the quote adapter: one retry on a transient blip,
a genuine error raised (never faked), every item carries its age so "no news"
and "stale news" never look alike, and a per-symbol fetch failure degrades that
symbol only — it never fabricates a headline or breaks the whole packet.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

YAHOO_NEWS_PROVIDER_ID = "yahoo_finance_public_symbol_news"
YAHOO_NEWS_SOURCE = "yahoo_finance_search_news"
YAHOO_NEWS_URL = "https://query1.finance.yahoo.com/v1/finance/search"
# Yahoo blocks the default urllib agent; a plain browser agent is enough.
YAHOO_NEWS_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
YAHOO_NEWS_PER_SYMBOL = 6
YAHOO_NEWS_MAX_SYMBOLS = 8
YAHOO_NEWS_TITLE_CHARS = 200


class YahooNewsError(ValueError):
    """Raised when Yahoo public news cannot be fetched or parsed safely."""


def _safe_symbol(value: Any) -> str:
    raw = str(value or "").strip().upper().replace("/", "")
    return "".join(ch for ch in raw if ch.isalnum() or ch in {".", "^", "-", "="})[:24]


def fetch_yahoo_symbol_news(
    *, symbol: str, count: int = YAHOO_NEWS_PER_SYMBOL, timeout: float = 8.0
) -> list[dict[str, Any]]:
    """Return Yahoo's public `news` array for one symbol (no credential)."""
    safe_symbol = _safe_symbol(symbol)
    if not safe_symbol:
        raise YahooNewsError("Yahoo news request is missing a usable symbol")
    query = urlencode(
        {
            "q": safe_symbol,
            "newsCount": max(1, min(int(count or YAHOO_NEWS_PER_SYMBOL), 20)),
            "quotesCount": 0,
            "enableFuzzyQuery": "false",
        }
    )
    url = f"{YAHOO_NEWS_URL}?{query}"
    request = Request(
        url,
        headers={"User-Agent": YAHOO_NEWS_USER_AGENT, "Accept": "application/json"},
    )
    # One retry on a transient blip, mirroring the quote adapter: a single
    # dropped connection should not read as "this symbol has no news".
    last_error: OSError | None = None
    for attempt in (1, 2):
        try:
            with urlopen(request, timeout=timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
            break
        except (TimeoutError, URLError, HTTPError, OSError) as exc:
            last_error = exc
            if attempt == 2:
                raise YahooNewsError(
                    f"Yahoo news fetch failed for {safe_symbol}: {exc.__class__.__name__}"
                ) from exc
    else:  # pragma: no cover - loop always breaks or raises
        raise YahooNewsError(f"Yahoo news fetch failed for {safe_symbol}: {last_error}")
    if not isinstance(payload, dict):
        raise YahooNewsError(f"Yahoo news response for {safe_symbol} is not an object")
    news = payload.get("news")
    return [item for item in news if isinstance(item, dict)] if isinstance(news, list) else []


def _age_minutes(publish_epoch: Any, *, now: datetime) -> int:
    try:
        published = datetime.fromtimestamp(int(publish_epoch), tz=UTC)
    except (TypeError, ValueError, OSError, OverflowError):
        return -1
    return max(int((now - published).total_seconds() // 60), 0)


def _published_iso(publish_epoch: Any) -> str:
    try:
        published = datetime.fromtimestamp(int(publish_epoch), tz=UTC)
    except (TypeError, ValueError, OSError, OverflowError):
        return ""
    return published.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _relates_to(symbol: str, related: list[str]) -> bool:
    """Whether Yahoo itself ties this story to the requested symbol.

    Yahoo's search silently returns unrelated filler for symbols it cannot
    resolve — a query for the TW listing 00982A.TW came back with Toll
    Brothers, Revolution Medicines and Visa (2026-07-25 live drill). Stamping
    the requested symbol on those made the packet claim they were that
    holding's news, which is fabricated attribution. An item counts only when
    Yahoo's own relatedTickers name the symbol (bare root accepted, so
    "2834.TW" matches a related "2834").
    """
    root = symbol.split(".")[0]
    return any(ticker == symbol or ticker.split(".")[0] == root for ticker in related)


def normalize_yahoo_news_items(
    symbol: str,
    news: list[dict[str, Any]],
    *,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Normalize Yahoo `news` rows into the packet's raw-item shape.

    Only stories Yahoo itself relates to the symbol are kept, so the packet
    never claims an unrelated headline as a holding's news. Items are tagged
    with the symbol (and Yahoo's relatedTickers) so the packet's keyword
    matcher attributes them even when the headline names the company rather
    than the ticker. A symbol Yahoo cannot resolve simply yields nothing —
    honest silence beats invented context.
    """
    safe_symbol = _safe_symbol(symbol)
    now = now or datetime.now(tz=UTC)
    items: list[dict[str, Any]] = []
    for row in news:
        if not isinstance(row, dict):
            continue
        title = str(row.get("title") or "").strip()
        if not title:
            continue
        uuid = str(row.get("uuid") or "").strip()
        raw_related = row.get("relatedTickers")
        related = [
            str(ticker).strip().upper()
            for ticker in (raw_related if isinstance(raw_related, list) else [])
            if str(ticker).strip()
        ]
        if not _relates_to(safe_symbol, related):
            continue
        tags = list(dict.fromkeys([safe_symbol, *related]))
        publish_epoch = row.get("providerPublishTime")
        items.append(
            {
                "item_id": f"yahoo-{uuid}" if uuid else f"yahoo-{safe_symbol}-{len(items)}",
                "title": title[:YAHOO_NEWS_TITLE_CHARS],
                "source": str(row.get("publisher") or "Yahoo Finance"),
                "category": "STK",
                "age_minutes": _age_minutes(publish_epoch, now=now),
                "published_at": _published_iso(publish_epoch),
                "url": str(row.get("link") or ""),
                "summary": "",
                "tags": tags,
                "provider_id": YAHOO_NEWS_PROVIDER_ID,
                "alert": False,
            }
        )
    return items


def collect_yahoo_news(
    symbols: list[str] | None,
    *,
    fetcher: Any | None = None,
    per_symbol: int = YAHOO_NEWS_PER_SYMBOL,
    now: datetime | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Fetch + normalize per-symbol Yahoo news for several holdings.

    Returns (items, errors). A per-symbol failure is recorded in `errors` and
    that symbol contributes no items; it never raises or fabricates. Items are
    de-duplicated by item_id across symbols (Yahoo often returns the same
    macro headline for several tickers).
    """
    fetch = fetcher or fetch_yahoo_symbol_news
    now = now or datetime.now(tz=UTC)
    seen: set[str] = set()
    items: list[dict[str, Any]] = []
    errors: list[str] = []
    unique_symbols: list[str] = []
    for symbol in symbols or []:
        safe = _safe_symbol(symbol)
        if safe and safe not in unique_symbols:
            unique_symbols.append(safe)
        if len(unique_symbols) >= YAHOO_NEWS_MAX_SYMBOLS:
            break
    for symbol in unique_symbols:
        try:
            raw = fetch(symbol=symbol, count=per_symbol)
        except (YahooNewsError, OSError, ValueError) as exc:
            errors.append(f"{symbol}: {exc.__class__.__name__}")
            continue
        for item in normalize_yahoo_news_items(symbol, raw, now=now):
            item_id = str(item.get("item_id"))
            if item_id in seen:
                continue
            seen.add(item_id)
            items.append(item)
    return items, errors
