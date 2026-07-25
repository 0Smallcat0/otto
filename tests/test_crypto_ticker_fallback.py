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


# ---- P3: the status must name the provider that actually served ----

from otto.local_terminal.markets import (
    default_markets_layout,
    markets_payload,
)


def _binance_shaped(symbol: str, price: str) -> dict:
    return {
        "symbol": symbol,
        "lastPrice": price,
        "priceChange": "1.0",
        "priceChangePercent": "1.0",
        "highPrice": "2",
        "lowPrice": "1",
        "volume": "10",
        "bidPrice": price,
        "askPrice": price,
        "openPrice": price,
    }


def test_chain_stamps_binance_provenance_on_primary_success() -> None:
    rows = fetch_public_crypto_tickers(
        ["BTCUSDT"],
        primary=lambda symbols, timeout: [_binance_shaped("BTCUSDT", "64000")],
        fallback=lambda symbols, timeout: [],
    )
    assert rows[0]["_source"] == "binance_public"
    assert rows[0]["_provider_id"] == "binance_spot_public"


def test_chain_stamps_kraken_provenance_on_fallback() -> None:
    def broken(symbols, timeout):
        raise OSError("binance blocked")

    rows = fetch_public_crypto_tickers(
        ["BTCUSDT"],
        primary=broken,
        fallback=lambda symbols, timeout: [_binance_shaped("BTCUSDT", "63900")],
    )
    assert rows[0]["_source"] == "kraken_public"
    assert rows[0]["_provider_id"] == "kraken_public_market_data"


def test_markets_status_names_the_fallback_provider_not_binance() -> None:
    def kraken_chain(symbols, timeout=6.0):
        def broken(_symbols, timeout):
            raise OSError("binance blocked")

        return fetch_public_crypto_tickers(
            symbols,
            primary=broken,
            fallback=lambda _symbols, timeout: [
                _binance_shaped(symbol, "63900") for symbol in symbols
            ],
        )

    payload = markets_payload(
        default_markets_layout(), {}, fetcher=kraken_chain, refresh=True
    )
    status = payload["status"]
    assert status["source"] == "kraken_public"
    assert status["provider_id"] == "kraken_public_market_data"
    assert status["fallback_used"] is True
    assert "Kraken" in status["message"]
    # the per-row labels follow the status, so no row claims Binance either
    served = [row for row in payload["rows"] if row.get("price")]
    assert served and all(row["source"] == "kraken_public" for row in served)


def test_markets_status_keeps_binance_labels_when_binance_serves() -> None:
    payload = markets_payload(
        default_markets_layout(),
        {},
        fetcher=lambda symbols, timeout=6.0: fetch_public_crypto_tickers(
            symbols,
            primary=lambda _s, timeout: [_binance_shaped(s, "64000") for s in symbols],
            fallback=lambda _s, timeout: [],
        ),
        refresh=True,
    )
    assert payload["status"]["source"] == "binance_public"
    assert payload["status"]["fallback_used"] is False


def test_unstamped_fetcher_still_defaults_to_binance_labels() -> None:
    # legacy/injected fetchers that return bare rows must not break the pipeline
    payload = markets_payload(
        default_markets_layout(),
        {},
        fetcher=lambda symbols: [_binance_shaped(s, "64000") for s in symbols],
        refresh=True,
    )
    assert payload["status"]["source"] == "binance_public"
    assert payload["status"]["state"] == "live"
