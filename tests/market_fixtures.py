"""Shared market-data fixtures for tests.

`fake_binance_tickers` was copy-pasted byte-identical into seven test files
(2026-07-22 debt sweep); one canonical copy keeps the Binance ticker row
shape — the contract every markets_payload fetcher must satisfy — pinned in
one place. Import it as `from market_fixtures import fake_binance_tickers`
(the tests directory sits on sys.path under pytest's default import mode).
"""


def fake_binance_tickers(symbols: list[str]) -> list[dict[str, str]]:
    return [
        {
            "symbol": symbol,
            "lastPrice": "100.00",
            "priceChange": "1.00",
            "priceChangePercent": "1.00",
            "highPrice": "110.00",
            "lowPrice": "90.00",
            "volume": "12345",
            "bidPrice": "99.50",
            "askPrice": "100.50",
            "openPrice": "99.00",
        }
        for symbol in symbols
    ]
