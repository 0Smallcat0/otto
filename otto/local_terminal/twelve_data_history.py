"""Daily-candle history via the user's Twelve Data key (M27-R4).

Gives US equities and FX the chart the crypto rows already have. Uses the
already-sealed local key (no new signup), writes one bounded cache file per
symbol, and never returns key material.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode

from otto.local_terminal.twelve_data import TWELVE_DATA_PROVIDER_ID

HISTORY_INTERVAL = "1day"
HISTORY_OUTPUTSIZE = 120
# Twelve Data's free tier allows eight requests a minute. TWSE listings ride a
# keyless endpoint and spend none of it, so they get their own bound.
MAX_HISTORY_SYMBOLS = 8
MAX_TWSE_HISTORY_SYMBOLS = 24


class TwelveDataHistoryError(ValueError):
    """Raised when a history refresh cannot be used safely."""


def fetch_twelve_data_time_series(
    *,
    symbol: str,
    api_key: str,
    timeout: float = 10.0,
) -> dict[str, Any]:
    params = urlencode(
        {
            "symbol": symbol,
            "interval": HISTORY_INTERVAL,
            "outputsize": HISTORY_OUTPUTSIZE,
            "apikey": api_key,
        }
    )
    request = urllib.request.Request(
        f"https://api.twelvedata.com/time_series?{params}",
        headers={"User-Agent": "LocalTerminal/0.1 clean-room local research"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise TwelveDataHistoryError("Twelve Data response must be a JSON object")
    return payload


def normalize_time_series(raw: dict[str, Any], *, symbol: str) -> dict[str, Any]:
    if str(raw.get("status") or "").lower() == "error":
        message = str(raw.get("message") or "provider error")
        if "credit" in message.lower() or "limit" in message.lower():
            raise TwelveDataHistoryError(f"rate_limited: {message[:120]}")
        raise TwelveDataHistoryError(message[:160])
    values = raw.get("values") if isinstance(raw.get("values"), list) else []
    candles: list[dict[str, str]] = []
    for row in reversed(values):  # provider returns newest-first
        if not isinstance(row, dict):
            continue
        candles.append(
            {
                "open": str(row.get("open") or ""),
                "high": str(row.get("high") or ""),
                "low": str(row.get("low") or ""),
                "close": str(row.get("close") or ""),
                "closed_at": str(row.get("datetime") or ""),
            }
        )
    if not candles:
        raise TwelveDataHistoryError("Twelve Data time series has no usable values")
    now = datetime.now(tz=UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
    return {
        "symbol": symbol,
        "interval": HISTORY_INTERVAL,
        "candles": candles[-HISTORY_OUTPUTSIZE:],
        "status": {
            "source": "twelve_data_time_series",
            "provider_id": TWELVE_DATA_PROVIDER_ID,
            "state": "live",
            "last_update": now,
        },
    }


def normalize_history_symbol(symbol: str) -> str:
    """`2834.TW` and `2834` are one cache file, and the refresh must agree.

    Holdings and research calls carry the exchange suffix; the watchlist and
    the cache filenames do not. Left unnormalised, a held name asked for by
    suffix is a different string from the one already cached, so it neither
    matches nor routes to TWSE.
    """
    text = str(symbol or "").strip().upper()
    for suffix in (".TW", ".TWO"):
        if text.endswith(suffix):
            return text[: -len(suffix)]
    return text


def is_twse_history_symbol(symbol: str) -> bool:
    """TW listings (4-6 digits, optional letter suffix like 00982A)."""
    body = normalize_history_symbol(symbol).replace("/", "")
    return len(body) >= 4 and body[:4].isdigit() and body.isalnum()


def select_history_symbols(
    watchlist: list[str] | tuple[str, ...],
    *,
    priority: list[str] | tuple[str, ...] = (),
    cap: int = MAX_HISTORY_SYMBOLS,
    twse_cap: int = MAX_TWSE_HISTORY_SYMBOLS,
) -> tuple[list[str], list[str]]:
    """Who survives the budget, and who is dropped by name.

    Two things were wrong with taking the first `cap` of the concatenated
    watchlist. The budget is Twelve Data's free tier — eight requests a minute
    (<https://support.twelvedata.com/en/articles/5615854-credits>) — and TW
    listings do not spend it: they ride TWSE's keyless endpoint. Charging them
    against a foreign rate limit dropped them for nothing.

    And the order that limit applied to was whatever order the watchlist
    happened to be concatenated in — US, then FX, then TW. Eleven symbols
    against a budget of eight meant the last three fell off every single time,
    and TW is last: the owner's two real holdings and the index his calls are
    benchmarked against went nine sessions without a refresh while TSLA was
    fetched daily, every result in the response reading `live` (2026-08-06).

    So the key budget binds only the symbols that spend it, what money is in
    goes first within each, and whatever is dropped comes back by name —
    a truncation nobody is told about reads exactly like a complete refresh.
    """
    ordered: list[str] = []
    for symbol in [*priority, *watchlist]:
        normalized = normalize_history_symbol(symbol)
        if normalized and normalized not in ordered:
            ordered.append(normalized)
    budget = {True: max(0, int(twse_cap)), False: max(0, int(cap))}
    selected: list[str] = []
    dropped: list[str] = []
    for symbol in ordered:
        metered = is_twse_history_symbol(symbol)
        if budget[metered] > 0:
            budget[metered] -= 1
            selected.append(symbol)
        else:
            dropped.append(symbol)
    return selected, dropped


def history_refresh_summary(
    results: dict[str, str], dropped: list[str] | tuple[str, ...] = ()
) -> dict[str, Any]:
    ok = [symbol for symbol, state in results.items() if state == "live"]
    skipped = list(dropped)
    return {
        "refreshed": ok,
        "results": results,
        "count": len(ok),
        "skipped": skipped,
        "skipped_reason": (
            f"over the refresh budget ({MAX_HISTORY_SYMBOLS} keyed symbols a "
            f"minute, {MAX_TWSE_HISTORY_SYMBOLS} keyless TWSE); holdings, open "
            "calls and benchmarks are taken first, so these are the watchlist "
            "tail. Ask for them by name to refresh them"
            if skipped
            else None
        ),
        "interval": HISTORY_INTERVAL,
        "provider_id": TWELVE_DATA_PROVIDER_ID,
        "safety": {
            "safety_class": "optional_key_market_data_no_broker_mutation",
            "external_calls": True,
            "mutates_local_state": True,
        },
    }
