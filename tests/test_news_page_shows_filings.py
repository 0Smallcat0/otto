"""The owner's own companies' filings belong on the page the owner reads.

The filing store and the agent's news packet were wired together first, which
served the agent and nobody else. Measured on the running terminal: the news
page returned 103 headlines — CoinDesk, SEC, an ETF explainer — while the same
terminal held 720 TWSE filings and surfaced none of them. Nothing failed; the
data was one API away from the wrong screen.

Yahoo cannot resolve a Taiwan ticker at all, so for a TW holding the company's
own material disclosure is the only single-name news that exists.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from otto.local_terminal import server
from otto.local_terminal.storage import LocalStateStore
from otto.local_terminal.twse_announcements import (
    merge_announcements,
    normalize_twse_announcements,
)


def _row(code: str, name: str, subject: str) -> dict[str, str]:
    return {
        "出表日期": "1150805",
        "發言日期": "1150805",
        "發言時間": "160532",
        "公司代號": code,
        "公司名稱": name,
        "主旨 ": subject,
        "符合條款": "第11款",
        "事實發生日": "1150805",
        "說明": "detail",
    }


def _store_with(tmp_path, *, holding: str | None, filings: list[dict]) -> LocalStateStore:
    store = LocalStateStore(root=tmp_path)
    if filings:
        state, _ = merge_announcements(
            store.read_tw_announcement_state(), normalize_twse_announcements(filings)
        )
        store.write_tw_announcement_state(state)
    if holding:
        portfolio = store.read_portfolio_state()
        client = TestClient(server.create_app())
        del portfolio, client  # the import endpoint owns the shape; use it below
    return store


def _seed_holding(client: TestClient, symbol: str) -> None:
    response = client.post(
        "/api/portfolio/import",
        json={
            "mode": "create_new",
            "portfolio": {
                "name": "test-book",
                "positions": [{"symbol": symbol, "quantity": "1000", "avg_cost": "250"}],
            },
        },
    )
    assert response.status_code == 200, response.text


def test_a_holdings_filing_reaches_the_news_page(tmp_path, monkeypatch) -> None:
    _store_with(
        tmp_path,
        holding=None,
        filings=[_row("2317", "鴻海", "公告本公司董事會決議通過買回庫藏股")],
    )
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())
    _seed_holding(client, "2317")

    items = client.get("/api/news").json()["items"]
    filings = [i for i in items if i.get("is_company_filing")]

    assert len(filings) == 1
    assert filings[0]["relevance"] == "mine", "a filing on a holding is not general news"
    assert filings[0]["held_symbols"] == ["2317"]
    assert filings[0]["source"] == "TWSE 重大訊息"
    assert "庫藏股" in filings[0]["title"]


def test_a_filing_for_a_company_not_held_stays_off_the_page(tmp_path, monkeypatch) -> None:
    """Scoped to the owner's names, not the whole 700-filing store."""
    _store_with(
        tmp_path,
        holding=None,
        filings=[
            _row("2317", "鴻海", "公告買回庫藏股"),
            _row("3711", "日月光投控", "公告完成訂價"),
        ],
    )
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())
    _seed_holding(client, "2317")

    filings = [i for i in client.get("/api/news").json()["items"] if i.get("is_company_filing")]

    assert [f["held_symbols"] for f in filings] == [["2317"]]


def test_no_holdings_leaves_the_feed_untouched(tmp_path, monkeypatch) -> None:
    _store_with(tmp_path, holding=None, filings=[_row("2317", "鴻海", "公告買回庫藏股")])
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())

    items = client.get("/api/news").json()["items"]

    assert not [i for i in items if i.get("is_company_filing")]


def test_an_empty_filing_store_is_not_an_error(tmp_path, monkeypatch) -> None:
    """A holding that filed nothing on the sessions held is silence, not failure."""
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())
    _seed_holding(client, "2834")

    response = client.get("/api/news")

    assert response.status_code == 200
    assert not [i for i in response.json()["items"] if i.get("is_company_filing")]
