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
        _row("x", "", 1_780_000_000, related=["AAPL"]),
        _row("y", "A" * 400, 1_780_000_000, related=["AAPL"]),
    ]
    items = normalize_yahoo_news_items("AAPL", rows, now=_NOW)
    assert len(items) == 1  # empty-title row dropped
    assert len(items[0]["title"]) == 200  # capped
    assert items[0]["tags"] == ["AAPL"]


def test_normalize_bad_timestamp_is_missing_not_zero() -> None:
    rows = [_row("z", "Headline", "not-a-number", related=["NVDA"])]
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
                _row("g1", "Alphabet specific", epoch, related=["GOOGL"]),
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


def test_unrelated_filler_is_dropped_not_stamped_with_the_symbol() -> None:
    """2026-07-25 live drill: Yahoo cannot resolve TW listings and answered a
    query for 00982A.TW with Toll Brothers / Revolution Medicines / Visa. Those
    were being tagged as that holding's news — fabricated attribution. Only
    stories Yahoo itself relates to the symbol may be kept."""
    epoch = int(_NOW.timestamp()) - 600
    rows = [
        _row("f1", "How Toll Brothers' Communities Could Shift", epoch, related=["TOL"]),
        _row("f2", "Visa Completed China's First B2B Agentic Payment", epoch, related=["V", "2598.HK"]),
        _row("f3", "Novilla Marks 15 Years of Comfort", epoch, related=None),
    ]
    assert normalize_yahoo_news_items("00982A.TW", rows, now=_NOW) == []


def test_bare_root_counts_as_related_for_suffixed_symbols() -> None:
    epoch = int(_NOW.timestamp()) - 600
    rows = [_row("t1", "臺企銀法說會展望", epoch, related=["2834"])]
    items = normalize_yahoo_news_items("2834.TW", rows, now=_NOW)
    assert len(items) == 1  # related "2834" ties to requested "2834.TW"
    assert items[0]["tags"][0] == "2834.TW"
