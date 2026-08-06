"""The refresh ran daily and the owner's own holdings never moved.

`markets_history_refresh` took the first `MAX_HISTORY_SYMBOLS` of the watchlist
concatenated as US + FX + TW. Eleven symbols against a budget of eight meant
the last three fell off every single time, and TW is last. On 2026-08-06 the
caches told the whole story: AAPL, MSFT, NVDA, SPY, TSLA, EUR/USD, 2330 and
2317 stamped that morning; 0050, 00982A and 2834 still stamped 2026-07-28 —
nine sessions stale, the owner's two real positions and the index his TW calls
are graded against. Every result in the response read `live`, and the three
that were never attempted appeared nowhere in it.

The budget is Twelve Data's free tier, eight requests a minute
(https://support.twelvedata.com/en/articles/5615854-credits). TW listings ride
TWSE's keyless endpoint and spend none of it.
"""

from __future__ import annotations

from otto.local_terminal.twelve_data_history import (
    MAX_HISTORY_SYMBOLS,
    history_refresh_summary,
    is_twse_history_symbol,
    normalize_history_symbol,
    select_history_symbols,
)

# The watchlist exactly as the endpoint concatenated it that morning.
REAL_WATCHLIST = [
    "AAPL", "MSFT", "NVDA", "SPY", "TSLA",
    "EUR/USD",
    "2330", "2317", "0050", "00982A", "2834",
]


def test_the_holdings_that_kept_falling_off_no_longer_do() -> None:
    selected, dropped = select_history_symbols(
        REAL_WATCHLIST, priority=["00982A", "2834", "0050.TW", "SPY"]
    )

    assert dropped == []
    for held in ("2834", "00982A", "0050"):
        assert held in selected, f"{held} is a real position or its benchmark"
    # And it is not merely present — money goes before the watch list.
    assert selected[:3] == ["00982A", "2834", "0050"]


def test_a_keyless_exchange_does_not_spend_the_key_budget() -> None:
    """Ten US names exhaust the tier; the five TW ones are not charged for it."""
    watch = [f"US{index}" for index in range(10)] + ["2330", "2317", "0050", "00982A", "2834"]
    selected, dropped = select_history_symbols(watch)

    assert len([s for s in selected if is_twse_history_symbol(s)]) == 5
    assert len([s for s in selected if not is_twse_history_symbol(s)]) == MAX_HISTORY_SYMBOLS
    assert dropped == ["US8", "US9"]


def test_what_is_dropped_comes_back_by_name() -> None:
    _, dropped = select_history_symbols([f"US{index}" for index in range(12)])
    summary = history_refresh_summary({"US0": "live"}, dropped)

    assert summary["skipped"] == ["US8", "US9", "US10", "US11"]
    assert "budget" in summary["skipped_reason"]
    assert "by name" in summary["skipped_reason"]


def test_a_complete_refresh_says_nothing_was_skipped() -> None:
    summary = history_refresh_summary({"AAPL": "live"}, [])

    assert summary["skipped"] == []
    assert summary["skipped_reason"] is None, (
        "a reason on a refresh that dropped nothing is noise that trains the "
        "reader to ignore the field"
    )


def test_a_suffixed_holding_is_the_same_cache_file_as_the_bare_code() -> None:
    """Calls carry 2834.TW, the watchlist carries 2834, the cache is one file."""
    assert normalize_history_symbol("2834.TW") == "2834"
    assert normalize_history_symbol("6488.TWO") == "6488"
    assert normalize_history_symbol(" aapl ") == "AAPL"

    selected, _ = select_history_symbols(["2834"], priority=["2834.TW"])
    assert selected == ["2834"], "one symbol, not two entries and two fetches"


def test_a_suffixed_symbol_still_routes_to_the_keyless_endpoint() -> None:
    """Unnormalised, `2834.TW` fails isalnum() and would be billed to the key."""
    assert is_twse_history_symbol("2834.TW") is True
    assert is_twse_history_symbol("00982A") is True
    assert is_twse_history_symbol("AAPL") is False
    assert is_twse_history_symbol("EUR/USD") is False
