"""A backtest must say whether its sample can carry the question it was asked.

The README tells a newcomer to say "backtest an SMA cross on BTCUSDT and tell me
if it's any good". Run on a fresh install, that returned −3.29%, a Sharpe of
−68.81 and a 0% win rate — from 79 fifteen-minute candles and 11 round trips,
about twenty hours of one market in one regime. Nothing in the response said the
sample could not support a verdict, and those figures read exactly like one.

Thresholds are external, not invented here: 30 round trips is the floor at which
sample means begin to behave, 100 the point where performance metrics are called
reliable, 200+ what institutional practice asks for across regimes.
  https://www.backtestbase.com/education/how-many-trades-for-backtest
"""

from __future__ import annotations

from otto.local_terminal.backtest import (
    SAMPLE_DEFENSIBLE_ROUND_TRIPS,
    SAMPLE_FLOOR_ROUND_TRIPS,
    SAMPLE_FRAGILE_METRICS,
    SAMPLE_RELIABLE_ROUND_TRIPS,
    _sample_sufficiency,
)


def _sample(round_trips: int, candles: int = 79):
    return _sample_sufficiency(
        round_trips=round_trips,
        candles=candles,
        timeframe="15m",
        first_opened_at="2026-08-05T02:45:00+00:00",
        last_closed_at="2026-08-05T22:29:59+00:00",
    )


def test_the_readme_first_backtest_is_not_reported_as_a_verdict() -> None:
    """The exact run a newcomer gets, in the numbers it produced."""
    sample = _sample(11)

    assert sample["verdict"] == "not_a_verdict"
    assert sample["round_trip_count"] == 11
    assert "below the floor" in sample["reads_as"]
    # The span has to be legible: twenty hours is the fact that matters, and a
    # candle count alone does not convey it.
    assert "2026-08-05T02:45:00+00:00" in sample["span"]
    assert "2026-08-05T22:29:59+00:00" in sample["span"]


def test_the_metrics_that_look_most_like_a_conclusion_are_named() -> None:
    """Sharpe is the number a reader trusts most and the one least able to bear it."""
    sample = _sample(11)

    assert "sharpe_ratio" in sample["fragile_metrics"]
    assert "win_rate_pct" in sample["fragile_metrics"]
    assert set(sample["fragile_metrics"]) == set(SAMPLE_FRAGILE_METRICS)
    assert "measures the annualisation" in sample["note"]


def test_each_band_is_named_at_its_boundary() -> None:
    assert _sample(SAMPLE_FLOOR_ROUND_TRIPS - 1)["verdict"] == "not_a_verdict"
    assert _sample(SAMPLE_FLOOR_ROUND_TRIPS)["verdict"] == "directional_only"
    assert _sample(SAMPLE_RELIABLE_ROUND_TRIPS - 1)["verdict"] == "directional_only"
    assert _sample(SAMPLE_RELIABLE_ROUND_TRIPS)["verdict"] == "reliable"
    assert _sample(SAMPLE_DEFENSIBLE_ROUND_TRIPS - 1)["verdict"] == "reliable"
    assert _sample(SAMPLE_DEFENSIBLE_ROUND_TRIPS)["verdict"] == "defensible"


def test_a_large_sample_is_still_told_to_check_its_regimes() -> None:
    """Trade count alone is not sufficiency; one trending year is still one regime."""
    sample = _sample(500)

    assert sample["verdict"] == "defensible"
    assert "regime" in sample["note"]


def test_a_run_that_never_traded_is_the_weakest_case_not_an_error() -> None:
    sample = _sample(0)

    assert sample["verdict"] == "not_a_verdict"
    assert sample["round_trip_count"] == 0


def test_the_thresholds_are_ordered() -> None:
    assert (
        SAMPLE_FLOOR_ROUND_TRIPS
        < SAMPLE_RELIABLE_ROUND_TRIPS
        < SAMPLE_DEFENSIBLE_ROUND_TRIPS
    )
