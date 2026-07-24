"""Yahoo public per-symbol news adapter — normalization and resilient collection."""

from __future__ import annotations

from datetime import UTC, datetime

from otto.local_terminal.yahoo_news import (
    YahooNewsError,
    collect_yahoo_news,
    normalize_yahoo_news_items,
)

_NOW = datetime(2026, 7, 24, 6, 0, 0, tzinfo=UTC)


def _row(uuid, title, epoch, publisher="Yahoo Finance Video", related=None):
    return {
        "uuid": uuid,
        "title": title,
        "publisher": publisher,
        "link": f"https://finance.yahoo.com/news/{uuid}.html",
        "providerPublishTime": epoch,
        "relatedTickers": related or [],
    }


def test_normalize_shapes_items_and_tags_source_symbol() -> None:
    epoch = int((_NOW.timestamp())) - 3600  # 60 minutes ago
    rows = [_row("abc", "The Discount On GOOGL Stock Looks Overdone", epoch, related=["GOOGL", "META"])]
    items = normalize_yahoo_news_items("GOOGL", rows, now=_NOW)
    assert len(items) == 1
    it = items[0]
    assert it["item_id"] == "yahoo-abc"
    assert it["title"].startswith("The Discount On GOOGL")
    assert it["source"] == "Yahoo Finance Video"
    assert it["age_minutes"] == 60
    assert it["published_at"].endswith("Z")
    assert it["url"].endswith("abc.html")
    # source symbol first, relatedTickers folded in, deduped
    assert it["tags"] == ["GOOGL", "META"]
    assert it["category"] == "STK"


def test_normalize_skips_untitled_and_caps_title() -> None:
    rows = [
        _row("x", "", 1_780_000_000),
        _row("y", "A" * 400, 1_780_000_000),
    ]
    items = normalize_yahoo_news_items("AAPL", rows, now=_NOW)
    assert len(items) == 1  # empty-title row dropped
    assert len(items[0]["title"]) == 200  # capped
    assert items[0]["tags"] == ["AAPL"]


def test_normalize_bad_timestamp_is_missing_not_zero() -> None:
    rows = [_row("z", "Headline", "not-a-number")]
    items = normalize_yahoo_news_items("NVDA", rows, now=_NOW)
    assert items[0]["age_minutes"] == -1
    assert items[0]["published_at"] == ""


def test_collect_merges_dedupes_and_isolates_failures() -> None:
    epoch = int(_NOW.timestamp()) - 120

    def fake_fetch(*, symbol, count):
        if symbol == "BOOM":
            raise YahooNewsError("Yahoo news fetch failed for BOOM: URLError")
        if symbol == "GOOGL":
            return [
                _row("shared", "Big Tech sell-off", epoch, related=["GOOGL", "AMZN"]),
                _row("g1", "Alphabet specific", epoch),
            ]
        if symbol == "AMZN":
            # 'shared' is the same macro headline Yahoo returns for AMZN too
            return [_row("shared", "Big Tech sell-off", epoch, related=["GOOGL", "AMZN"])]
        return []

    items, errors = collect_yahoo_news(["GOOGL", "AMZN", "BOOM"], fetcher=fake_fetch, now=_NOW)
    ids = [i["item_id"] for i in items]
    assert ids == ["yahoo-shared", "yahoo-g1"]  # deduped across GOOGL/AMZN
    assert errors == ["BOOM: YahooNewsError"]  # failure isolated, others survive


def test_collect_never_raises_when_all_fail() -> None:
    def boom(*, symbol, count):
        raise OSError("network down")

    items, errors = collect_yahoo_news(["AAPL", "MSFT"], fetcher=boom, now=_NOW)
    assert items == []
    assert len(errors) == 2


def test_collect_handles_empty_and_bad_symbols() -> None:
    items, errors = collect_yahoo_news([], fetcher=lambda **_: [], now=_NOW)
    assert items == [] and errors == []
