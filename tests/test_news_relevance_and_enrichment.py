"""Rules that decide what the reader sees — pinned, because they rot silently.

Three helpers shipped on 2026-07-25 encoding judgment calls (what counts as
relevant, which name to show, which holdings to research) went out with no
tests of their own, verified only by looking at live data once.
"""

from __future__ import annotations

from otto.local_terminal import server
from otto.local_terminal.news_digest import build_live_sections
from otto.local_terminal.news_packet import news_relevance


def test_holdings_outrank_every_other_bucket() -> None:
    # a lottery headline that names a held symbol is still about his money
    item = {"title": "統一發票開獎", "source": "鉅亨台股", "held_symbols": ["2834.TW"]}
    assert news_relevance(item) == "mine"
    assert news_relevance({"title": "x", "source": "CoinDesk", "watched_symbols": ["BTC-USD"]}) == "mine"


def test_lottery_draws_are_noise_whatever_the_source() -> None:
    assert news_relevance({"title": "今彩539第115180期　頭獎1注中獎", "source": "中央社財經"}) == "noise"
    assert news_relevance({"title": "完整獎號一次看！統一發票千萬特別獎", "source": "鉅亨台股"}) == "noise"
    assert news_relevance({"title": "威力彩頭獎摃龜", "source": "中央社財經"}) == "noise"


def test_earnings_previews_survive_the_lottery_filter() -> None:
    """開獎 is how Chinese finance desks say "results are revealed".

    The bare verb was a noise pattern, so a real headline — 微軟、Meta、蘋果下周
    開獎 — was classified as a lottery draw and only escaped burial because it
    also matched a held symbol (2026-07-27 dogfood). A name he does not hold
    would have been dropped off the wall entirely.
    """
    assert news_relevance({"title": "AI巨頭財報前瞻一表看！微軟、Meta、蘋果下周開獎", "source": "鉅亨台股"}) == "tw"
    assert news_relevance({"title": "輝達財報開獎在即", "source": "經濟日報"}) == "tw"


def test_taiwanese_desks_are_their_own_bucket() -> None:
    assert news_relevance({"title": "台股開盤跌逾百點", "source": "鉅亨台股"}) == "tw"
    assert news_relevance({"title": "主計總處上修成長", "source": "中央社財經"}) == "tw"
    # crypto wire for a reader holding none: not noise, just not his market
    assert news_relevance({"title": "Bitcoin ETF flows", "source": "CoinDesk"}) == "global"
    # A row with no title renders as source + age and nothing to read. It used
    # to default to "global" on the principle of not hiding what we don't
    # understand; folding it under a count is the better reading of that same
    # principle, since the reader can still open the fold.
    assert news_relevance({}) == "noise"


def test_scraped_page_titles_are_not_treated_as_stories() -> None:
    """三則論壇落地頁曾是「國際與其他」整節的全部內容。

    GDELT returns metadata-only hits, and some are site furniture. Three
    东方财富 forum boards outranked 33 real stories purely by being freshest
    (2026-07-27 dogfood), so the section labelled 國際與其他 held no
    international news at all.
    """
    assert news_relevance({"title": "_ 狮头股份 ( 600539 ) 股吧 _ 东方财富网股吧", "source": "guba.eastmoney.com"}) == "noise"
    assert news_relevance({"title": "华天科技 ( 002185 ) 股吧", "source": "guba.eastmoney.com"}) == "noise"
    assert news_relevance({"title": "| Reuters", "source": "reuters.com"}) == "noise"
    assert news_relevance({"title": "", "source": "x"}) == "noise"


def test_real_stories_survive_the_page_title_filter() -> None:
    """Narrow on purpose — a hyphen inside a sentence is not a breadcrumb."""
    assert news_relevance({"title": "台股拉回緯創獨扛 6檔含緯ETF近一周含息報酬衝破4%", "source": "鉅亨台股"}) == "tw"
    assert news_relevance({"title": "Bitcoin settles near $65,000 as oil's march fails", "source": "CoinDesk"}) == "global"
    # A dash mid-title is ordinary punctuation; only a LEADING separator is evidence.
    assert news_relevance({"title": "Fed holds — markets shrug", "source": "CoinDesk"}) == "global"


def test_section_roll_up_never_leads_a_category_with_noise() -> None:
    """The dashboard shows one headline per category — so a noise lead *is* the category.

    The news page folded the receipt lottery away while the 市場 section on the
    task wall led with it, because the roll-up ran on the untagged feed and had
    no shared noise predicate (2026-07-27 dogfood).
    """
    items = [
        {"title": "今彩539第115180期　頭獎1注中獎", "category": "MKT", "age_minutes": 1},
        {"title": "統一發票千萬特別獎開獎", "category": "MKT", "age_minutes": 2},
        {"title": "台股量縮價穩，外資轉買超", "category": "MKT", "age_minutes": 90},
        {"title": "威力彩頭獎摃龜", "category": "GEO", "age_minutes": 3},
    ]
    sections = {s["category"]: s for s in build_live_sections(items)}

    assert sections["市場"]["title_zh"] == "台股量縮價穩，外資轉買超"
    assert sections["市場"]["summary_zh"] == ""  # the two lottery draws are gone, not demoted
    assert "地緣" not in sections  # a category that is only noise earns no section


def test_us_quote_rows_take_names_from_the_local_directory(monkeypatch) -> None:
    class FakeStore:
        def read_nasdaq_trader_symbol_directory_cache(self):
            return {"symbols": [
                {"symbol": "AAPL", "name": "Apple Inc. - Common Stock"},
                {"symbol": "SPY", "name": "State Street SPDR S&P 500 ETF Trust"},
            ]}

    monkeypatch.setattr(server, "STORE", FakeStore())
    payload = {"research_summary": {"finnhub_quotes": {"rows": [
        {"symbol": "AAPL"},
        {"symbol": "SPY", "name": "已有名稱"},
        {"symbol": "UNKNOWN"},
    ]}}}
    server._fill_equity_quote_names(payload)
    rows = {row["symbol"]: row.get("name") for row in payload["research_summary"]["finnhub_quotes"]["rows"]}
    assert rows["AAPL"] == "Apple Inc."  # share class trimmed, not three columns wide
    assert rows["SPY"] == "已有名稱"  # an existing name is never overwritten
    assert rows["UNKNOWN"] is None  # absent from the directory stays absent


def test_a_scoring_run_that_settled_nothing_says_so(tmp_path, monkeypatch) -> None:
    """The score response handed back the ledger's lifetime total as its own.

    The endpoint set "scored_count": len(scored) and then spread the ledger
    payload over it, which owns the same key and means "calls in scored status,
    ever". The two agreed while the ledger held nothing, so the shadowing was
    invisible until a run settled nothing on a ledger with two closed calls and
    reported 2 — an operator reading it tells the owner a call closed that the
    market never touched (2026-07-29).
    """
    from fastapi.testclient import TestClient

    from otto.local_terminal.storage import LocalStateStore

    store = LocalStateStore(root=tmp_path)
    # one call already closed, one open and nowhere near its invalidation
    store.write_research_ledger_state(
        {
            "calls": [
                {
                    "call_id": "call-old",
                    "as_of": "2026-07-01T00:00:00+00:00",
                    "symbol": "2330.TW",
                    "market": "tw_equity",
                    "stance": "hold",
                    "conviction": "medium",
                    "thesis": "已結算",
                    "ref_price": "2355.0",
                    "matures_at": "2026-07-02T00:00:00+00:00",
                    "horizon_days": 1,
                    "status": "scored",
                    "outcome": "invalidated",
                }
            ]
        }
    )
    monkeypatch.setattr(server, "STORE", store)
    client = TestClient(server.create_app())
    assert client.post(
        "/api/research/call",
        json={
            "symbol": "AAPL",
            "stance": "hold",
            "thesis": "相對強勢仍成立,離失效價還很遠。",
            "ref_price": "340.0",
            "invalidation": "200",
            "horizon_days": 90,
        },
    ).status_code == 200

    body = client.post("/api/research/score", json={"refresh": False}).json()
    assert body["scored"] == []  # nothing matured, nothing breached
    assert body["newly_scored_count"] == 0  # what this run actually closed
    assert body["scored_count"] == 1  # the ledger's lifetime total, unchanged


def test_recording_a_judgment_writes_itself_onto_the_activity_feed(tmp_path, monkeypatch) -> None:
    """The wall said 閒置 while the ledger held nine calls.

    The activity journal is written by hand, so judgments recorded on 07-24/25
    never reached it and the dashboard's newest entry stayed 07-10 — the wall
    telling the owner the AI had done nothing (2026-07-27 dogfood).
    """
    from fastapi.testclient import TestClient

    from otto.local_terminal.agent_activity import agent_activity_payload
    from otto.local_terminal.storage import LocalStateStore

    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())

    response = client.post(
        "/api/research/call",
        json={
            "symbol": "2330.TW",
            "stance": "hold",
            "thesis": "先進製程訂單能見度到年底，估值未過熱，維持觀望不加碼。",
            "ref_price": "2355.0",
            "invalidation": "2200",
            "conviction": "medium",
            "horizon_days": 30,
        },
    )
    assert response.status_code == 200, response.text

    events = agent_activity_payload(tmp_path)["events"]
    assert len(events) == 1
    assert events[0]["action_id"] == "research_call_record"
    assert events[0]["state"] == "succeeded"
    assert "2330.TW" in events[0]["summary"]
    assert "hold" in events[0]["summary"]


def test_owner_holdings_become_research_universe_entries() -> None:
    state = {
        "active_portfolio_id": "pf1",
        "portfolios": {"pf1": {"positions": [
            {"symbol": "2834", "name": "臺企銀", "asset_class": "Equity"},
            {"symbol": "AAPL", "asset_class": "Equity"},
            {"symbol": "BTCUSDT", "asset_class": "Crypto"},
        ]}},
    }
    universe = server._owner_holdings_universe(state)
    assert universe["2834.TW"] == ("tw_equity", "臺企銀")  # numeric code gets .TW
    assert universe["AAPL"] == ("us_equity", "AAPL")
    assert "BTCUSDT" not in universe  # the paper crypto book covers those
    assert server._owner_holdings_universe({}) == {}


def test_a_recorded_call_is_named_by_the_reference_cache(tmp_path, monkeypatch) -> None:
    """The judgment board showed a bare 00982A.TW while two other panels named it.

    record_call falls back to the curated DEFAULT_UNIVERSE, which by design
    carries liquid well-known names only — so the symbols that lose their label
    are exactly the owner's own holdings, the rows that matter most. The TWSE
    quote cache already held 主動群益台灣強棒 and the news matcher already read
    it, so the blank row was a drop, not missing data (2026-07-29 dogfood).
    """
    from fastapi.testclient import TestClient

    from otto.local_terminal.storage import LocalStateStore

    store = LocalStateStore(root=tmp_path)
    store.write_twse_quote_cache(
        {
            "status": {"symbol": "00982A"},
            "quotes": [{"symbol": "00982A", "name": "主動群益台灣強棒"}],
        }
    )
    monkeypatch.setattr(server, "STORE", store)
    client = TestClient(server.create_app())

    def record(**overrides):
        body = {
            "symbol": "00982A.TW",
            "market": "tw_equity",
            "stance": "hold",
            "thesis": "改判：這不是全面 risk-off，是半導體單一產業重新定價。",
            "ref_price": "18.87",
            "conviction": "low",
            "horizon_days": 31,
        }
        body.update(overrides)
        response = client.post("/api/research/call", json=body)
        assert response.status_code == 200, response.text
        return response.json()["call"]

    # the gap this closes: nobody typed a name, and it is not a curated name
    assert record()["name"] == "主動群益台灣強棒"
    # an explicit name always wins — the cache fills blanks, it does not relabel
    assert record(name="我自己取的")["name"] == "我自己取的"
    # curated labels are not quietly rewritten into the exchange's Chinese name
    assert record(symbol="2330.TW", ref_price="2200")["name"] == "TSMC"
    # nothing anywhere still records the call; it just stays unnamed
    assert record(symbol="9999.TW", ref_price="10")["name"] is None
