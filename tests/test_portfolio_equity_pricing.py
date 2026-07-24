"""Imported-portfolio equity positions must price live, not freeze at import.

Regression for the owner's TW book showing a stale P&L: the portfolio pricer
only read the crypto/markets cache, so equity holdings stayed pinned to their
import-time snapshot price. _portfolio_equity_price_rows fetches live Yahoo
marks (numeric TW listing codes get a .TW suffix) and returns them as
market-cache rows keyed by the bare symbol.
"""

from __future__ import annotations

from otto.local_terminal import server


def _state():
    return {
        "active_portfolio_id": "pf1",
        "portfolios": {
            "pf1": {
                "currency": "TWD",
                "positions": [
                    {"symbol": "2834", "asset_class": "Equity"},
                    {"symbol": "00982A", "asset_class": "Equity"},
                    {"symbol": "AAPL", "asset_class": "Equity"},
                    {"symbol": "BTCUSDT", "asset_class": "Crypto"},
                ],
            }
        },
    }


def test_numeric_tw_codes_get_tw_suffix_us_ticker_kept_crypto_skipped(monkeypatch):
    seen: dict[str, list[str]] = {}

    def fake_snapshot(*, refresh, symbols):
        seen["symbols"] = list(symbols)
        prices = {"2834.TW": "18.0", "00982A.TW": "21.98", "AAPL": "331.67"}
        return {
            "quotes": [
                {"symbol": s, "price": prices[s], "change_percent": "1.0", "retrieved_at": "t"}
                for s in symbols
                if s in prices
            ]
        }

    monkeypatch.setattr(server, "_yahoo_quote_snapshot_payload_from_store", fake_snapshot)
    rows = server._portfolio_equity_price_rows(_state())

    # crypto skipped; TW numeric codes suffixed; US alpha ticker untouched
    assert "BTCUSDT" not in seen["symbols"]
    assert set(seen["symbols"]) == {"2834.TW", "00982A.TW", "AAPL"}

    by_symbol = {r["symbol"]: r for r in rows}
    # rows are keyed by the BARE portfolio symbol so the price book matches
    assert set(by_symbol) == {"2834", "00982A", "AAPL"}
    assert by_symbol["2834"]["price"] == "18.0"
    assert by_symbol["00982A"]["price"] == "21.98"
    assert by_symbol["2834"]["state"] == "live"
    assert by_symbol["2834"]["source"] == "yahoo_finance_public_quote_snapshot"


def test_missing_quote_leaves_symbol_out_not_faked(monkeypatch):
    def fake_snapshot(*, refresh, symbols):
        # 00982A.TW comes back unpriced (N/A) — must not produce a row
        return {
            "quotes": [
                {"symbol": "2834.TW", "price": "18.0", "change_percent": "0"},
                {"symbol": "00982A.TW", "price": "N/A"},
            ]
        }

    monkeypatch.setattr(server, "_yahoo_quote_snapshot_payload_from_store", fake_snapshot)
    rows = server._portfolio_equity_price_rows(_state())
    symbols = {r["symbol"] for r in rows}
    assert symbols == {"2834"}  # 00982A dropped, AAPL absent from fake → dropped


def test_no_active_portfolio_returns_empty(monkeypatch):
    called = False

    def fake_snapshot(*, refresh, symbols):
        nonlocal called
        called = True
        return {"quotes": []}

    monkeypatch.setattr(server, "_yahoo_quote_snapshot_payload_from_store", fake_snapshot)
    assert server._portfolio_equity_price_rows({"portfolios": {}}) == []
    assert called is False  # no positions → no network fetch
