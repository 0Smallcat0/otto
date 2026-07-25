"""Rules that decide what the reader sees — pinned, because they rot silently.

Three helpers shipped on 2026-07-25 encoding judgment calls (what counts as
relevant, which name to show, which holdings to research) went out with no
tests of their own, verified only by looking at live data once.
"""

from __future__ import annotations

from otto.local_terminal import server
from otto.local_terminal.news_packet import news_relevance


def test_holdings_outrank_every_other_bucket() -> None:
    # a lottery headline that names a held symbol is still about his money
    item = {"title": "統一發票開獎", "source": "鉅亨台股", "held_symbols": ["2834.TW"]}
    assert news_relevance(item) == "mine"
    assert news_relevance({"title": "x", "source": "CoinDesk", "watched_symbols": ["BTC-USD"]}) == "mine"


def test_lottery_draws_are_noise_whatever_the_source() -> None:
    assert news_relevance({"title": "今彩539第115180期　頭獎1注中獎", "source": "中央社財經"}) == "noise"
    assert news_relevance({"title": "完整獎號一次看！統一發票千萬特別獎", "source": "鉅亨台股"}) == "noise"


def test_taiwanese_desks_are_their_own_bucket() -> None:
    assert news_relevance({"title": "台股開盤跌逾百點", "source": "鉅亨台股"}) == "tw"
    assert news_relevance({"title": "主計總處上修成長", "source": "中央社財經"}) == "tw"
    # crypto wire for a reader holding none: not noise, just not his market
    assert news_relevance({"title": "Bitcoin ETF flows", "source": "CoinDesk"}) == "global"
    assert news_relevance({}) == "global"


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
