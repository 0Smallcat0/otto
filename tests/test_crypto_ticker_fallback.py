"""P0 #2 from the 2026-07-17 dogfood: the ticker must follow the fallback chain.

When Binance is unreachable the detail path already falls back to Kraken,
but the ticker snapshot silently stayed a week old — and once the paper
freshness gate landed, that stale ticker blocked all paper trading. The
ticker now rides the same chain: Binance first, Kraken second, with Kraken
rows normalized to the Binance ticker shape the markets pipeline expects.
"""

import pytest

from otto.local_terminal.crypto_data import (
    fetch_kraken_tickers,
    fetch_public_crypto_tickers,
)

_KRAKEN_TICKER = {
    "error": [],
    "result": {
        "XBTUSDT": {
            "a": ["64010.1", "1", "1.000"],
            "b": ["64009.9", "1", "1.000"],
            "c": ["64010.0", "0.001"],
            "v": ["120.5", "980.25"],
            "h": ["64500.0", "64800.0"],
            "l": ["63000.0", "62800.0"],
            "o": "63500.0",
        }
    },
}


def test_kraken_rows_are_binance_shaped() -> None:
    rows = fetch_kraken_tickers(
        ["BTCUSDT"], reader=lambda url, timeout: _KRAKEN_TICKER
    )
    assert len(rows) == 1
    row = rows[0]
    assert row["symbol"] == "BTCUSDT"
    assert row["lastPrice"] == "64010.0"
    assert row["openPrice"] == "63500.0"
    assert row["highPrice"] == "64800.0"  # index 1 = last 24h
    assert row["volume"] == "980.25"
    assert row["bidPrice"] == "64009.9"
    assert float(row["priceChange"]) == pytest.approx(510.0)
    assert float(row["priceChangePercent"]) == pytest.approx(0.803, abs=0.001)


def test_kraken_with_no_mappable_symbols_raises() -> None:
    with pytest.raises(ValueError, match="no rows"):
        fetch_kraken_tickers(["DOGEUSDT"], reader=lambda url, timeout: _KRAKEN_TICKER)


def test_chain_prefers_primary() -> None:
    rows = fetch_public_crypto_tickers(
        ["BTCUSDT"],
        primary=lambda symbols, timeout: [{"symbol": "BTCUSDT", "lastPrice": "1"}],
        fallback=lambda symbols, timeout: (_ for _ in ()).throw(AssertionError("fallback used")),
    )
    assert rows[0]["lastPrice"] == "1"


def test_chain_falls_back_when_primary_is_unreachable() -> None:
    def broken(symbols, timeout):
        raise OSError("binance blocked")

    rows = fetch_public_crypto_tickers(
        ["BTCUSDT"],
        primary=broken,
        fallback=lambda symbols, timeout: [{"symbol": "BTCUSDT", "lastPrice": "2"}],
    )
    assert rows[0]["lastPrice"] == "2"


def test_chain_raises_when_both_fail() -> None:
    def broken(symbols, timeout):
        raise OSError("down")

    def also_broken(symbols, timeout):
        raise ValueError("down too")

    with pytest.raises(ValueError):
        fetch_public_crypto_tickers(["BTCUSDT"], primary=broken, fallback=also_broken)
