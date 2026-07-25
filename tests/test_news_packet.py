"""P2 from the 2026-07-17 dogfood: the judgment step needs one readable read.

The information half of the loop was starved — the digest auto-expires and
assembling anything readable cost three heavyweight calls. The packet is the
news counterpart of `paper_account_summary`: bounded, freshness-labeled,
tagged against held symbols, and explicit that the tagging is keyword-based
so an unmatched item is never reported as irrelevant.
"""

import json

from fastapi.testclient import TestClient

from otto.local_terminal import server
from otto.local_terminal.news_packet import (
    PACKET_MAX_ITEMS,
    news_packet_payload,
    symbol_terms,
)
from otto.local_terminal.storage import LocalStateStore


def _news(items: list[dict], state: str = "live") -> dict:
    return {
        "items": items,
        "status": {
            "state": state,
            "last_update": "2026-07-19T09:00:00Z",
            "failed_source_count": 0,
            "source_errors": [],
        },
    }


def _item(item_id: str, title: str, age: int, summary: str = "", tags=()) -> dict:
    return {
        "item_id": item_id,
        "title": title,
        "source": "Test Wire",
        "category": "MARKETS",
        "age_minutes": age,
        "published_at": "2026-07-19T08:00:00Z",
        "url": f"https://example.test/{item_id}",
        "summary": summary,
        "tags": list(tags),
        "alert": False,
    }


def test_symbol_terms_strip_quote_and_market_suffixes() -> None:
    assert symbol_terms("BTCUSDT") == ["btc", "bitcoin"]
    assert symbol_terms("2330.TW")[0] == "2330"
    assert "tsmc" in symbol_terms("2330.TW")
    assert symbol_terms("AAPL") == ["aapl", "apple"]
    assert symbol_terms("") == []
    # an unknown ticker still matches on itself rather than guessing a name
    assert symbol_terms("ZZZZ") == ["zzzz"]


def test_matched_items_sort_first_then_freshest() -> None:
    news = _news(
        [
            _item("old-unrelated", "Shipping lanes reopen", 10),
            _item("fresh-unrelated", "Bond auction demand steady", 2),
            _item("matched-old", "Bitcoin ETF flows turn positive", 400),
            _item("matched-fresh", "Apple supplier guidance raised", 30),
        ]
    )
    packet = news_packet_payload(news, {}, symbols=["BTCUSDT", "AAPL"], limit=4)

    order = [item["item_id"] for item in packet["items"]]
    assert order[:2] == ["matched-fresh", "matched-old"]  # matched first, fresher first
    assert order[2] == "fresh-unrelated"
    assert packet["summary"]["matched_count"] == 2
    assert packet["items"][0]["matched_symbols"] == ["AAPL"]
    assert packet["summary"]["newest_age_minutes"] == 2


def test_packet_is_bounded_and_small() -> None:
    # pathological feed: 40 items with runaway titles and summaries
    news = _news([_item(f"i{n}", f"Headline number {n}" * 20, n, "x" * 900) for n in range(40)])
    packet = news_packet_payload(news, {}, symbols=[], limit=50)  # over the cap
    assert len(packet["items"]) == PACKET_MAX_ITEMS
    assert packet["summary"]["available_count"] == 40  # the count is not hidden
    assert all(len(item["title"]) <= 160 for item in packet["items"])
    assert all(len(item["summary"]) <= 240 for item in packet["items"])
    assert len(json.dumps(packet)) < 9000  # hard ceiling even against garbage

    # realistic wire: what the loop actually pays per iteration
    realistic = _news(
        [
            _item(
                f"r{n}",
                "Fed holds rates steady as inflation cools further",
                n * 7,
                "Policymakers kept the benchmark unchanged and signalled patience.",
                ("MACRO",),
            )
            for n in range(12)
        ]
    )
    typical = news_packet_payload(realistic, {}, symbols=["AAPL"], limit=8)
    assert len(json.dumps(typical)) < 4500  # vs 74k+ for the raw news route


def test_matching_is_declared_keyword_based() -> None:
    packet = news_packet_payload(_news([]), {}, symbols=["BTCUSDT"])
    assert packet["matching"]["mode"] == "keyword"
    assert "not evidence" in packet["matching"]["note"]
    assert packet["matching"]["terms_by_symbol"]["BTCUSDT"] == ["btc", "bitcoin"]


def test_stale_feed_and_empty_digest_are_visible_not_silent() -> None:
    news = _news([_item("a", "Anything", 5000)], state="stale_cache")
    news["status"]["failed_source_count"] = 2
    news["status"]["source_errors"] = ["rss timeout", "gdelt 503"]
    packet = news_packet_payload(news, {"items": {}, "updated_at": "not started"})

    assert packet["freshness"]["feed_state"] == "stale_cache"
    assert packet["freshness"]["failed_source_count"] == 2
    assert packet["freshness"]["source_errors"] == ["rss timeout", "gdelt 503"]
    assert packet["summary"]["newest_age_minutes"] == 5000
    assert packet["digest"]["updated_at"] == "not started"
    assert packet["summary"]["digest_entry_count"] == 0


def test_digest_text_rides_along_when_written() -> None:
    news = _news([_item("item-1", "Fed holds rates", 12)])
    digest = {
        "items": {"item-1": {"title_zh": "聯準會按兵不動", "summary_zh": "維持利率不變"}},
        "updated_at": "2026-07-19T09:00:00Z",
    }
    packet = news_packet_payload(news, digest)
    assert packet["items"][0]["digest_title"] == "聯準會按兵不動"
    assert packet["summary"]["digest_entry_count"] == 1


def test_endpoint_and_contract(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())

    response = client.post("/api/news/packet", json={"symbols": ["BTCUSDT"], "limit": 3})
    assert response.status_code == 200
    body = response.json()
    assert body["requested_symbols"] == ["BTCUSDT"]
    assert len(body["items"]) <= 3
    assert body["safety"]["mutates_local_state"] is False

    over_cap = client.post("/api/news/packet", json={"limit": PACKET_MAX_ITEMS + 1})
    assert over_cap.status_code == 422
    extra = client.post("/api/news/packet", json={"symbols": [], "sentiment": True})
    assert extra.status_code == 422

    contract = client.get("/api/agent-contract").json()
    actions = {action["action_id"]: action for action in contract["actions"]}
    entry = actions["news_information_packet"]
    assert entry["endpoint"] == "/api/news/packet"
    assert entry["local_mutation"] is False
    news_route = next(r for r in contract["routes"] if r["route_id"] == "news")
    assert news_route["recommended_actions"][0] == "news_information_packet"


# ---- official-name matching (2026-07-22): caches beat a hand alias table ----


def test_symbol_terms_include_cleaned_official_names() -> None:
    terms = symbol_terms("AVGO", ("Broadcom Inc. - Common Stock",))
    assert "avgo" in terms
    assert "broadcom" in terms  # suffix noise stripped
    tw = symbol_terms("2317.TW", ("鴻海",))
    assert "鴻海" in tw  # CJK names pass through even under 3 latin chars


def test_packet_matches_via_official_name_not_just_ticker() -> None:
    news = _news(
        [
            _item("n1", "Broadcom raises AI networking guidance", 10),
            _item("n2", "鴻海進軍AI伺服器市場", 20),
        ]
    )
    payload = news_packet_payload(
        news,
        symbols=["AVGO", "2317.TW"],
        symbol_names={
            "AVGO": ["Broadcom Inc. - Common Stock"],
            "2317.TW": ["鴻海"],
        },
    )
    matched = {item["item_id"]: item.get("matched_symbols", []) for item in payload["items"]}
    assert matched["n1"] == ["AVGO"]
    assert matched["n2"] == ["2317.TW"]
    assert "official security name" in payload["matching"]["note"]


def test_numeric_tw_ticker_needs_boundaries_not_bare_substring() -> None:
    """2026-07-25 live drill: the owner's TW holdings matched unrelated US
    stories because "2834" was substring-matched into ids/prices/longer
    numbers. ASCII terms now need alphanumeric boundaries on both sides."""
    news = _news(
        [
            _item("hit", "臺企銀 2834 法說會釋出展望", 10),
            _item("longer", "Fund NAV rose to 12834 on the day", 12),
            _item("glued", "Ticker 28345 hits limit up", 14),
            _item("price", "Revenue of $2,834 million reported", 16),
        ]
    )
    payload = news_packet_payload(news, symbols=["2834.TW"], limit=8)
    matched = {item["item_id"]: item.get("matched_symbols", []) for item in payload["items"]}
    assert matched["hit"] == ["2834.TW"]  # real mention still matches
    assert matched["longer"] == []  # 12834 is not 2834
    assert matched["glued"] == []  # 28345 is not 2834
    assert matched["price"] == []  # 2,834 has a separator, not the bare code
    assert payload["summary"]["matched_count"] == 1


def test_ascii_ticker_does_not_match_inside_a_longer_word() -> None:
    news = _news(
        [
            _item("real", "Apple lifts AAPL guidance", 5),
            _item("glued", "AAPLX fund launches", 6),
        ]
    )
    payload = news_packet_payload(news, symbols=["AAPL"], limit=8)
    matched = {item["item_id"]: item.get("matched_symbols", []) for item in payload["items"]}
    assert matched["real"] == ["AAPL"]
    assert matched["glued"] == []
