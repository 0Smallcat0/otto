"""P0 from the 2026-07-17 dogfood: paper fills must not lie about price.

A MARKET order filled at a 7-day-old cached quote stamped `quote_state:
"live"` — the state the cache had when captured, silently carried forward.
Two rules now hold:

1. A quote snapshot older than QUOTE_FRESHNESS_TTL_SECONDS is never labeled
   `live`; it demotes to `stale_cache`.
2. A MARKET paper order on a stale (or unstampable) quote is refused with a
   clear "refresh first" error instead of filling at a phantom price.

Resting LIMIT orders are still accepted — they do not fill at submit time.
"""

from datetime import UTC, datetime, timedelta

import pytest

from otto.local_terminal.crypto import (
    QUOTE_FRESHNESS_TTL_SECONDS,
    PaperOrderError,
    place_paper_order,
)
from otto.local_terminal.crypto import default_paper_state


def _market_cache(retrieved_at: str) -> dict:
    return {
        "rows": [
            {
                "symbol": "BTCUSDT",
                "price": "64000.00000000",
                "chg": "100.0",
                "chg_pct": "0.15",
                "bid": "63999.9",
                "ask": "64000.1",
                "name": "Bitcoin / Tether",
                "source": "binance_public",
                "state": "live",
                "provider_id": "binance_spot_public",
                "retrieved_at": retrieved_at,
                "cache_path": "market_data/crypto_latest.json",
            }
        ],
        "status": {
            "source": "binance_public",
            "state": "live",
            "last_update": retrieved_at,
            "provider_id": "binance_spot_public",
            "cache_path": "market_data/crypto_latest.json",
        },
    }


def _stamp(age_seconds: float) -> str:
    return (
        datetime.now(tz=UTC) - timedelta(seconds=age_seconds)
    ).isoformat(timespec="seconds")


_ORDER = {"symbol": "BTCUSDT", "side": "BUY", "order_type": "MARKET", "quantity": "0.001"}


def test_market_order_fills_on_a_fresh_quote() -> None:
    state, order = place_paper_order(
        default_paper_state(), dict(_ORDER), _market_cache(_stamp(30))
    )
    assert order["status"] == "FILLED"
    assert order["quote_state"] == "live"


def test_market_order_is_refused_on_a_stale_quote() -> None:
    stale = _stamp(QUOTE_FRESHNESS_TTL_SECONDS + 60)
    with pytest.raises(PaperOrderError, match="stale quote|Refresh public"):
        place_paper_order(default_paper_state(), dict(_ORDER), _market_cache(stale))


def test_market_order_is_refused_when_quote_age_is_unknown() -> None:
    with pytest.raises(PaperOrderError, match="unknown"):
        place_paper_order(
            default_paper_state(), dict(_ORDER), _market_cache("not refreshed")
        )


def test_resting_limit_order_is_still_accepted_on_a_stale_quote() -> None:
    stale = _stamp(QUOTE_FRESHNESS_TTL_SECONDS + 60)
    request = {
        "symbol": "BTCUSDT",
        "side": "BUY",
        "order_type": "LIMIT",
        "quantity": "0.001",
        "limit_price": "1000.00",
    }
    state, order = place_paper_order(default_paper_state(), request, _market_cache(stale))
    assert order["status"] == "WORKING"
    # and the carried-forward state stops claiming to be live
    assert order["quote_state"] == "stale_cache"


def test_stale_quote_state_is_demoted_everywhere_it_is_recorded() -> None:
    stale = _stamp(QUOTE_FRESHNESS_TTL_SECONDS + 3600)
    request = {
        "symbol": "BTCUSDT",
        "side": "BUY",
        "order_type": "LIMIT",
        "quantity": "0.001",
        "limit_price": "1000.00",
    }
    state, order = place_paper_order(default_paper_state(), request, _market_cache(stale))
    ledger_row = state["ledger"][-1]
    assert ledger_row["quote_state"] == "stale_cache"
    assert order["quote_retrieved_at"] == stale
