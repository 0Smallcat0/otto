"""M27-R4 — daily history candles via the sealed Twelve Data key."""

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from otto.local_terminal import server
from otto.local_terminal.storage import LocalStateStore
from otto.local_terminal.twelve_data import TWELVE_DATA_PROVIDER_ID


def _fake_series(*, symbol: str, api_key: str, timeout: float = 10.0):
    assert api_key == "synthetic-key"
    return {
        "status": "ok",
        "values": [
            {"datetime": f"2026-07-{7 - i:02d}", "open": f"{100 + i}", "high": f"{101 + i}",
             "low": f"{99 + i}", "close": f"{100.5 + i}"}
            for i in range(5)
        ],
    }


def _client(tmp_path, monkeypatch, *, with_key: bool) -> TestClient:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    if with_key:
        monkeypatch.setattr(
            server,
            "_twelve_data_secret_status_from_store",
            lambda: {"stored_provider_ids": [TWELVE_DATA_PROVIDER_ID]},
        )
        monkeypatch.setattr(server, "read_local_data_provider_secret", lambda *_, **__: "synthetic-key")
        monkeypatch.setattr(server, "fetch_twelve_data_time_series", _fake_series)
    return TestClient(server.create_app())


def test_history_refresh_fills_caches_and_candles_endpoint_serves_them(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch, with_key=True)
    refreshed = client.post("/api/markets/history/refresh", json={"symbols": ["TSLA", "EUR/USD"]})
    assert refreshed.status_code == 200, refreshed.text
    body = refreshed.json()
    assert body["results"] == {"TSLA": "live", "EUR/USD": "live"}
    assert body["count"] == 2

    candles = client.get("/api/markets/candles/TSLA").json()
    assert candles["source"] == "history_cache"
    assert candles["timeframe"] == "1d"
    assert len(candles["candles"]) == 5
    # oldest-first after normalization
    assert candles["candles"][0]["closed_at"] < candles["candles"][-1]["closed_at"]

    fx = client.get("/api/markets/candles/EURUSD").json()
    assert fx["source"] == "history_cache"


def _fake_stock_day(*, stock_no: str, yyyymmdd: str, timeout: float = 10.0):
    year = int(yyyymmdd[:4]) - 1911
    month = yyyymmdd[4:6]
    return {
        "stat": "OK",
        "data": [
            [f"{year}/{month}/{day:02d}", "1,000", "2,000", "100.5", "102.0", "99.5", "101.0", "+0.5", "500"]
            for day in (1, 2, 3)
        ],
    }


def test_history_refresh_defaults_to_us_fx_and_tw_watchlists(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch, with_key=True)
    monkeypatch.setattr(server, "TWSE_HISTORY_FETCHER", _fake_stock_day)
    body = client.post("/api/markets/history/refresh", json={}).json()
    assert set(body["results"]) == {"AAPL", "MSFT", "NVDA", "SPY", "EUR/USD", "2330", "2317", "0050"}
    assert body["results"]["2330"] == "live"


def test_tw_history_needs_no_key_and_feeds_the_candles_endpoint(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch, with_key=False)
    monkeypatch.setattr(server, "TWSE_HISTORY_FETCHER", _fake_stock_day)
    body = client.post("/api/markets/history/refresh", json={"symbols": ["2330"]}).json()
    assert body["results"] == {"2330": "live"}

    candles = client.get("/api/markets/candles/2330").json()
    assert candles["source"] == "history_cache"
    assert candles["timeframe"] == "1d"
    assert len(candles["candles"]) == 9  # 3 rows × 3 stitched months
    assert candles["candles"][0]["closed_at"] < candles["candles"][-1]["closed_at"]


def test_suffixed_tw_codes_route_to_twse(tmp_path, monkeypatch) -> None:
    """Active ETFs like 00982A carry a letter suffix and still belong to TWSE."""
    client = _client(tmp_path, monkeypatch, with_key=False)
    monkeypatch.setattr(server, "TWSE_HISTORY_FETCHER", _fake_stock_day)
    body = client.post("/api/markets/history/refresh", json={"symbols": ["00982A"]}).json()
    assert body["results"] == {"00982A": "live"}
    assert client.get("/api/markets/candles/00982A").json()["source"] == "history_cache"


def test_tw_quote_rows_prefer_freshest_history_close(tmp_path, monkeypatch) -> None:
    """The quote file can lag a session behind history; money numbers must not."""
    store = LocalStateStore(root=tmp_path)
    monkeypatch.setattr(server, "STORE", store)
    store.write_history_cache("00982A", {
        "symbol": "00982A",
        "candles": [
            {"open": "25", "high": "26", "low": "24", "close": "25.28", "closed_at": "2026-07-06"},
            {"open": "25", "high": "25.5", "low": "24", "close": "24.09", "closed_at": "2026-07-07"},
        ],
    })
    rows = [{"symbol": "00982A", "price": "25.28", "close": "25.28", "date": "1150706"}]
    server._apply_history_close_overlay(rows)
    assert rows[0]["price"] == "24.09"
    assert rows[0]["date"] == "1150707"
    assert rows[0]["change_percent"] == "-4.71"
    assert rows[0]["price_basis"] == "history_close_overlay"

    # never regress to an OLDER close
    stale = [{"symbol": "00982A", "price": "23.00", "close": "23.00", "date": "1150708"}]
    server._apply_history_close_overlay(stale)
    assert stale[0]["price"] == "23.00"


def test_tw_quote_rows_take_the_yahoo_close_when_it_is_the_freshest(tmp_path, monkeypatch) -> None:
    """The candles are not the only local cache that can be ahead of TWSE.

    TWSE publishes STOCK_DAY_ALL per symbol, so one group carries two sessions
    at once. On 2026-07-28 the owner's two holdings were among the laggards
    while 2330 had the day's close, and the candle cache was three weeks old —
    so only the Yahoo snapshot, rewritten every time the judgment board marks
    a position, held the current number. 0050 read +0.15% on a session it lost
    4.24%.
    """
    store = LocalStateStore(root=tmp_path)
    monkeypatch.setattr(server, "STORE", store)
    store.write_history_cache("0050", {
        "symbol": "0050",
        "candles": [{"open": "106", "high": "107", "low": "105", "close": "106.20", "closed_at": "2026-07-07"}],
    })
    store.write_yahoo_quote_cache({
        "status": {"symbol": "0050.TW"},
        "quotes": [{"symbol": "0050.TW", "date": "2026-07-28", "close": "97.15", "price": "97.15"}],
    })
    rows = [{
        "symbol": "0050", "price": "101.45", "close": "101.45", "date": "1150727",
        "open": "101.30", "high": "101.60", "low": "100.05", "volume": "109612623",
        "change_percent": "0.15",
    }]

    server._apply_history_close_overlay(rows)

    assert rows[0]["price"] == "97.15"
    assert rows[0]["date"] == "1150728"
    assert rows[0]["change_percent"] == "-4.24"
    # Attribution follows the number, or the row credits TWSE for a Yahoo close.
    assert rows[0]["price_basis"] == "yahoo_quote_overlay"
    # The rest of the row described the superseded session. Left in place it
    # produced an impossible bar — a low of 100.05 under a close of 97.15.
    assert rows[0]["low"] == ""
    assert rows[0]["high"] == ""
    assert rows[0]["open"] == ""
    assert rows[0]["volume"] == ""


def test_tw_quote_rows_keep_the_candle_close_when_it_is_the_newer_one(tmp_path, monkeypatch) -> None:
    """Whichever cache is ahead wins — the fix must not just always pick Yahoo."""
    store = LocalStateStore(root=tmp_path)
    monkeypatch.setattr(server, "STORE", store)
    store.write_history_cache("2330", {
        "symbol": "2330",
        "candles": [{"open": "2300", "high": "2310", "low": "2270", "close": "2280", "closed_at": "2026-07-28"}],
    })
    store.write_yahoo_quote_cache({
        "status": {"symbol": "2330.TW"},
        "quotes": [{"symbol": "2330.TW", "date": "2026-07-24", "close": "2355", "price": "2355"}],
    })
    rows = [{
        "symbol": "2330", "price": "2350", "close": "2350", "date": "1150724",
        "open": "2360", "high": "2380", "low": "2340",
    }]

    server._apply_history_close_overlay(rows)

    assert rows[0]["price"] == "2280"
    assert rows[0]["price_basis"] == "history_close_overlay"
    # A candle is a whole bar, so the new session's own high and low come with
    # it — blanking them here would discard figures we can actually vouch for.
    assert rows[0]["high"] == "2310"
    assert rows[0]["low"] == "2270"
    assert rows[0]["open"] == "2300"


def test_tw_quote_rows_ignore_a_yahoo_cache_older_than_the_row(tmp_path, monkeypatch) -> None:
    """Fail closed: a stale snapshot must never drag a current row backwards."""
    store = LocalStateStore(root=tmp_path)
    monkeypatch.setattr(server, "STORE", store)
    store.write_yahoo_quote_cache({
        "status": {"symbol": "2834.TW"},
        "quotes": [{"symbol": "2834.TW", "date": "2026-07-20", "close": "17.00", "price": "17.00"}],
    })
    rows = [{"symbol": "2834", "price": "18.10", "close": "18.10", "date": "1150728", "low": "17.95"}]

    server._apply_history_close_overlay(rows)

    assert rows[0]["price"] == "18.10"
    assert rows[0]["low"] == "17.95"
    assert "price_basis" not in rows[0]


def test_book_position_prices_overlay_uses_freshest_close(tmp_path, monkeypatch) -> None:
    """With no live quote, the book falls back to the freshest close we hold.

    A live mark now outranks this path (the daily-close cache was quoting
    00982A at 23.83 against a market at 21.98), so the fallback is asserted
    with the live source explicitly empty — which also keeps this test off the
    network.
    """
    store = LocalStateStore(root=tmp_path)
    monkeypatch.setattr(server, "STORE", store)
    monkeypatch.setattr(server, "_live_equity_marks", lambda symbols: {})
    recent = (datetime.now(tz=UTC).date() - timedelta(days=1)).isoformat()
    store.write_history_cache("00982A", {
        "symbol": "00982A",
        "candles": [{"close": "24.09", "closed_at": recent}],
    })
    book = {"positions": [
        {"symbol": "00982A", "quantity": "1000", "avg_cost": "15.15", "last_price": "15.15"},
        {"symbol": "NOHIST", "quantity": "5", "avg_cost": "10", "last_price": "10"},
    ]}
    server._overlay_book_position_prices(book)
    assert book["positions"][0]["last_price"] == "24.09"
    assert book["positions"][0]["market_value"] == "24090.00"
    assert book["positions"][0]["price_basis"] == "history_close_overlay"
    assert book["positions"][0]["price_date"] == recent
    # a symbol with no live/history price is tagged as cost-basis, not left to
    # masquerade as a real quote.
    assert book["positions"][1]["last_price"] == "10"
    assert book["positions"][1]["price_basis"] == "cost_basis"


def test_book_overlay_flags_a_genuinely_stale_close(tmp_path, monkeypatch) -> None:
    """A weeks-old close is served but flagged, not passed off as current."""
    store = LocalStateStore(root=tmp_path)
    monkeypatch.setattr(server, "STORE", store)
    monkeypatch.setattr(server, "_live_equity_marks", lambda symbols: {})  # keep it off the network
    store.write_history_cache("STALE", {
        "symbol": "STALE",
        "candles": [{"close": "50", "closed_at": "2020-01-02"}],
    })
    book = {"positions": [{"symbol": "STALE", "quantity": "10", "avg_cost": "40", "last_price": "40"}]}
    server._overlay_book_position_prices(book)
    assert book["positions"][0]["last_price"] == "50"
    assert book["positions"][0]["price_basis"] == "stale_history_close"


def test_quote_overlay_fails_closed_on_unparseable_row_date(tmp_path, monkeypatch) -> None:
    """An unreadable row date means we can't prove freshness — don't overwrite."""
    store = LocalStateStore(root=tmp_path)
    monkeypatch.setattr(server, "STORE", store)
    store.write_history_cache("2330", {
        "symbol": "2330",
        "candles": [{"close": "999", "closed_at": "2026-07-07"}],
    })
    rows = [{"symbol": "2330", "price": "500", "close": "500", "date": "??"}]
    server._apply_history_close_overlay(rows)
    assert rows[0]["price"] == "500"
    assert "price_basis" not in rows[0]


def test_history_without_key_marks_only_key_symbols(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch, with_key=False)
    monkeypatch.setattr(server, "TWSE_HISTORY_FETCHER", _fake_stock_day)
    body = client.post("/api/markets/history/refresh", json={"symbols": ["TSLA", "2330"]})
    assert body.status_code == 200
    assert body.json()["results"] == {"TSLA": "key_required", "2330": "live"}


def test_live_mark_outranks_the_daily_close_cache(tmp_path, monkeypatch) -> None:
    """The defect this ordering fixes: the book page quoted a stale close.

    00982A showed 23.83 from the daily-close cache while the market said 21.98,
    inflating the position's P&L by more than twelve points on the one page
    named after the owner's own money.
    """
    store = LocalStateStore(root=tmp_path)
    monkeypatch.setattr(server, "STORE", store)
    recent = (datetime.now(tz=UTC).date() - timedelta(days=1)).isoformat()
    store.write_history_cache("00982A", {
        "symbol": "00982A",
        "candles": [{"close": "23.83", "closed_at": recent}],
    })
    monkeypatch.setattr(
        server,
        "_live_equity_marks",
        lambda symbols: {"00982A": {"price": "21.98", "change_pct": "-2.2", "retrieved_at": "now"}},
    )
    book = {"positions": [{"symbol": "00982A", "quantity": "1000", "avg_cost": "15.15"}]}
    server._overlay_book_position_prices(book)
    position = book["positions"][0]
    assert position["last_price"] == "21.98"  # the market, not the cache
    assert position["price_basis"] == "live_quote"
    assert position["market_value"] == "21980.00"


def test_crypto_positions_are_not_sent_to_the_equity_quote_path(tmp_path, monkeypatch) -> None:
    store = LocalStateStore(root=tmp_path)
    monkeypatch.setattr(server, "STORE", store)
    seen: dict[str, list[str]] = {}

    def fake_marks(symbols):
        seen["symbols"] = list(symbols)
        return {}

    monkeypatch.setattr(server, "_live_equity_marks", fake_marks)
    book = {"positions": [
        {"symbol": "2834", "quantity": "1", "avg_cost": "10", "asset_class": "Equity"},
        {"symbol": "BTCUSDT", "quantity": "1", "avg_cost": "10", "asset_class": "Crypto"},
    ]}
    server._overlay_book_position_prices(book)
    assert seen["symbols"] == ["2834"]
