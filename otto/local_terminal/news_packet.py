"""One-call information packet for the agent decision loop.

The 2026-07-17 dogfood found the judgment step starved: the digest had
auto-expired, and assembling anything readable cost three heavyweight calls
whose responses the agent could not afford to read. This builds the
information half of the loop the same way `paper_account_summary` built the
position half — bounded, freshness-labeled, and honest about its limits:

- headlines are capped and trimmed to the fields a decision needs;
- every item carries its age, so "no news" and "stale news" never look alike;
- when the caller names its holdings, items are tagged with the symbols they
  mention, and the packet says plainly that the match is keyword-based over
  title/summary/tags — an unmatched item is not evidence of irrelevance.
"""

from __future__ import annotations

import re
from typing import Any

PACKET_MAX_ITEMS = 12
PACKET_TITLE_CHARS = 160
PACKET_SUMMARY_CHARS = 240
MATCH_MODE_NOTE = (
    "keyword match over title/summary/tags using each ticker plus its official "
    "security name from local reference caches (Nasdaq Trader directory, TWSE "
    "daily quotes); ASCII terms must sit on alphanumeric boundaries so a numeric "
    "Taiwan ticker like 2834 no longer matches any text that merely contains "
    "those digits; an item without a matched symbol is not evidence that it "
    "is irrelevant"
)

# Corporate-suffix noise stripped from official security names before they are
# used as search terms ("Apple Inc. - Common Stock" should match "Apple").
_NAME_SUFFIX_NOISE = (
    "inc.", "inc", "corp.", "corp", "corporation", "ltd.", "ltd", "plc",
    "co.", "co", "company", "holdings", "holding", "group", "trust", "etf",
    "fund", "sa", "n.v.", "nv", "ag",
)
_NAME_MIN_CHARS = 3

# Aliases only where the ticker alone would miss obvious coverage. Kept small
# on purpose: a long guessed table would produce confident wrong matches.
SYMBOL_ALIASES: dict[str, tuple[str, ...]] = {
    "BTC": ("bitcoin",),
    "ETH": ("ethereum", "ether"),
    "SOL": ("solana",),
    "2330": ("tsmc", "taiwan semiconductor", "台積電"),
    "AAPL": ("apple",),
    "MSFT": ("microsoft",),
    "NVDA": ("nvidia",),
    "TSLA": ("tesla",),
    "GOOGL": ("google", "alphabet"),
    "AMZN": ("amazon",),
    "META": ("meta platforms", "facebook"),
    "SPY": ("s&p 500", "sp500"),
}

_QUOTE_SUFFIXES = ("USDT", "USDC", "USD", "TWD")


def _terms_from_name(name: str) -> list[str]:
    """Usable search terms from an official security name.

    Keeps the full lowered name plus a cleaned head form with corporate
    suffixes stripped, so "Apple Inc. - Common Stock" also matches "Apple"
    and a Chinese name like 台積電 passes through unchanged.
    """
    cleaned = str(name or "").strip().lower()
    if not cleaned:
        return []
    head = cleaned.split(" - ")[0].strip()
    words = [word for word in head.replace(",", " ").split() if word]
    while words and words[-1] in _NAME_SUFFIX_NOISE:
        words.pop()
    short = " ".join(words).strip()
    terms = []
    for candidate in (short, head):
        has_cjk = any("一" <= ch <= "鿿" for ch in candidate)
        if candidate and (len(candidate) >= _NAME_MIN_CHARS or has_cjk):
            terms.append(candidate)
    return terms


def symbol_terms(symbol: str, extra_names: tuple[str, ...] | list[str] = ()) -> list[str]:
    """Search terms for one holding: root, curated aliases, official names."""
    raw = str(symbol or "").strip().upper()
    if not raw:
        return []
    root = raw.split(".")[0]
    for suffix in _QUOTE_SUFFIXES:
        if root.endswith(suffix) and len(root) > len(suffix):
            root = root[: -len(suffix)]
            break
    terms = [root.lower()]
    terms.extend(alias.lower() for alias in SYMBOL_ALIASES.get(root, ()))
    for name in extra_names:
        terms.extend(_terms_from_name(name))
    return list(dict.fromkeys(term for term in terms if term))


def term_matches(term: str, haystack: str) -> bool:
    """Whether one search term occurs in the (lowered) haystack.

    Plain substring matching made numeric Taiwan tickers useless: "2834" hit
    any text containing those digits — article ids, prices, longer numbers —
    so a TW holding matched a run of unrelated US stories (2026-07-25 live
    drill). ASCII terms therefore need alphanumeric boundaries on both sides;
    CJK names have no such boundaries and keep substring semantics.
    """
    if not term:
        return False
    if term.isascii():
        return re.search(rf"(?<![0-9a-z]){re.escape(term)}(?![0-9a-z])", haystack) is not None
    return term in haystack


def news_packet_payload(
    news: dict[str, Any],
    digest: dict[str, Any] | None = None,
    *,
    symbols: list[str] | None = None,
    limit: int = 8,
    symbol_names: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    """Bounded headlines + digest + freshness, tagged against held symbols."""
    bounded_limit = max(1, min(int(limit or 8), PACKET_MAX_ITEMS))
    held = [str(symbol).strip().upper() for symbol in (symbols or []) if str(symbol).strip()]
    names = symbol_names or {}
    terms_by_symbol = {
        symbol: symbol_terms(symbol, tuple(names.get(symbol, ()))) for symbol in held
    }

    raw_items = news.get("items") if isinstance(news.get("items"), list) else []
    digest_items = {}
    if isinstance(digest, dict) and isinstance(digest.get("items"), dict):
        digest_items = digest["items"]

    scored: list[tuple[int, int, dict[str, Any]]] = []
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        haystack = " ".join(
            [
                str(raw.get("title", "")),
                str(raw.get("summary", "")),
                " ".join(str(tag) for tag in raw.get("tags", []) if tag),
            ]
        ).lower()
        matched = [
            symbol
            for symbol, terms in terms_by_symbol.items()
            if any(term_matches(term, haystack) for term in terms)
        ]
        item_id = str(raw.get("item_id", ""))
        digest_entry = digest_items.get(item_id) if isinstance(digest_items, dict) else None
        age_minutes = _int(raw.get("age_minutes"))
        item = {
            "item_id": item_id,
            "title": str(raw.get("title", ""))[:PACKET_TITLE_CHARS],
            "source": str(raw.get("source", "")),
            "category": str(raw.get("category", "")),
            "age_minutes": age_minutes,
            "published_at": str(raw.get("published_at", "")),
            "url": str(raw.get("url", "")),
            "summary": str(raw.get("summary", ""))[:PACKET_SUMMARY_CHARS],
            "matched_symbols": matched,
            "alert": bool(raw.get("alert")),
        }
        if isinstance(digest_entry, dict):
            item["digest_title"] = str(digest_entry.get("title_zh", ""))[:PACKET_TITLE_CHARS]
            item["digest_summary"] = str(digest_entry.get("summary_zh", ""))[:PACKET_SUMMARY_CHARS]
        # matched items first, then freshest
        scored.append((0 if matched else 1, age_minutes if age_minutes >= 0 else 10**6, item))

    scored.sort(key=lambda row: (row[0], row[1]))
    items = [row[2] for row in scored[:bounded_limit]]
    matched_total = sum(1 for row in scored if row[0] == 0)
    ages = [row[1] for row in scored if row[1] < 10**6]

    status = news.get("status") if isinstance(news.get("status"), dict) else {}
    source_errors = status.get("source_errors") if isinstance(status, dict) else []
    digest_payload = digest if isinstance(digest, dict) else {}
    return {
        "mode": "read_only_information_packet",
        "requested_symbols": held,
        "items": items,
        "summary": {
            "item_count": len(items),
            "available_count": len(scored),
            "matched_count": matched_total,
            "newest_age_minutes": min(ages) if ages else None,
            "oldest_age_minutes": max(ages) if ages else None,
            "digest_entry_count": len(digest_items) if isinstance(digest_items, dict) else 0,
        },
        "freshness": {
            "feed_state": str(status.get("state") or "unknown"),
            "last_update": str(status.get("last_update") or "not started"),
            "failed_source_count": _int(status.get("failed_source_count")),
            "source_errors": [str(error) for error in (source_errors or [])][:3],
            "refresh_action": "news_refresh",
        },
        "matching": {
            "mode": "keyword",
            "note": MATCH_MODE_NOTE,
            "terms_by_symbol": terms_by_symbol,
        },
        "digest": {
            "updated_at": str(digest_payload.get("updated_at") or "not started"),
            "write_action": "news_digest_write",
            "note": "digest text is operator-authored; empty means nobody has written one",
        },
        "safety": {
            "read_only": True,
            "external_calls": False,
            "mutates_local_state": False,
        },
    }


def _int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return -1


# ── relevance buckets ────────────────────────────────────────────────────────
# Sources that write for a Taiwanese investor, in a language he reads.
TW_NATIVE_SOURCES = ("鉅亨", "中央社", "經濟日報", "工商時報", "自由財經", "MoneyDJ")
# Finance-shaped headlines with no investment content. Every pattern names a
# specific game or draw, because the generic verbs do not belong to lotteries:
# 開獎 is idiomatic for an earnings reveal ("微軟、Meta、蘋果下周開獎" is a real
# 2026-07-27 headline) and 中獎 turns up in metaphor. Bare verbs were burying
# legitimate previews; only the game names discriminate.
NEWS_NOISE_PATTERNS = (
    "統一發票",
    "發票號碼",
    "樂透",
    "威力彩",
    "今彩",
    "雙贏彩",
    "星彩",
    "樂合彩",
    "運動彩券",
)


def is_news_noise(title: Any) -> bool:
    """Whether a headline is finance-shaped with no investment content.

    Split out of `news_relevance` because the relevance bucket is only reachable
    once an item has been tagged against holdings, and the roll-up that picks
    one lead headline per category runs on the raw feed. Without a predicate
    both paths can share, the 市場 section led with the national receipt lottery
    while the news page — filtering the same feed correctly — folded it away
    (2026-07-27 dogfood).
    """
    text = str(title or "")
    return any(pattern in text for pattern in NEWS_NOISE_PATTERNS)


# Scraped page titles arrive as site breadcrumbs, not sentences. A leading
# separator means the segment before it was empty — the crawler captured a
# <title> like "_ 狮头股份 ( 600539 ) 股吧 _ 东方财富网股吧", which is a forum
# board's landing page, not a story about anything.
_TITLE_SEPARATORS = ("_", "|", "-", "–", "—", "»", "·")
# Board/forum section markers: the page is a place to post, not an article.
_FORUM_MARKERS = ("股吧", "论坛", "論壇", "贴吧", "message board")


def is_not_a_headline(item: dict[str, Any]) -> bool:
    """Whether a feed row is a page rather than a story.

    GDELT returns metadata-only hits, and some of them are site furniture:
    three 东方财富 forum landing pages were the entire 國際與其他 section on
    2026-07-27, outranking 33 real stories purely by being freshest. They are
    finance-shaped with nothing to read, which is what the noise bucket is
    for — the reader can still open the fold and see them.

    Deliberately narrow. A leading separator is mechanical evidence the title
    was scraped furniture; a forum marker names the page type outright. Neither
    guesses at whether a real story is interesting.
    """
    title = str(item.get("title") or "").strip()
    if not title:
        return True
    if title[0] in _TITLE_SEPARATORS:
        return True
    lowered = title.lower()
    return any(marker in lowered for marker in _FORUM_MARKERS)


def news_relevance(item: dict[str, Any]) -> str:
    """Bucket one headline by what it is worth to the reader.

    The feed ran 99 items where 29 were crypto for someone whose book holds
    none, next to a foreign bank licence revocation and the national receipt
    lottery. Nothing is deleted — the bucket lets a page lead with what touches
    the reader's money and fold the rest away with a count, so "irrelevant"
    stays a claim that can be checked.

    "mine" wins over everything: a lottery headline that somehow names a held
    symbol is still about his money.
    """
    if item.get("held_symbols") or item.get("watched_symbols"):
        return "mine"
    if is_not_a_headline(item):
        return "noise"
    if is_news_noise(item.get("title", "")):
        return "noise"
    source = str(item.get("source", ""))
    if any(native in source for native in TW_NATIVE_SOURCES):
        return "tw"
    return "global"
