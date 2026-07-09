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

from src.local_terminal.twelve_data import TWELVE_DATA_PROVIDER_ID

HISTORY_INTERVAL = "1day"
HISTORY_OUTPUTSIZE = 120
MAX_HISTORY_SYMBOLS = 8


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


def history_refresh_summary(results: dict[str, str]) -> dict[str, Any]:
    ok = [symbol for symbol, state in results.items() if state == "live"]
    return {
        "refreshed": ok,
        "results": results,
        "count": len(ok),
        "interval": HISTORY_INTERVAL,
        "provider_id": TWELVE_DATA_PROVIDER_ID,
        "safety": {
            "safety_class": "optional_key_market_data_no_broker_mutation",
            "external_calls": True,
            "mutates_local_state": True,
        },
    }
