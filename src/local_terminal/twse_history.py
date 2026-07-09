"""Daily-candle history for Taiwan listings via TWSE STOCK_DAY (M27-R5).

Official exchange endpoint, no key, one month per call; we stitch the last
three months so every TW symbol gets the same chart crypto and US rows have.
ROC dates (115/07/07) and comma-grouped numbers are normalized here.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from typing import Any

TWSE_STOCK_DAY_URL = "https://www.twse.com.tw/exchangeReport/STOCK_DAY"
HISTORY_MONTHS = 3
MAX_TW_CANDLES = 120
_FETCH_PAUSE_SECONDS = 0.35  # be polite; TWSE rate-bans rapid callers


class TwseHistoryError(ValueError):
    """Raised when TWSE history cannot be used safely."""


def fetch_twse_stock_day(
    *,
    stock_no: str,
    yyyymmdd: str,
    timeout: float = 10.0,
) -> dict[str, Any]:
    request = urllib.request.Request(
        f"{TWSE_STOCK_DAY_URL}?response=json&date={yyyymmdd}&stockNo={stock_no}",
        headers={"User-Agent": "LocalTerminal/0.1 clean-room local research"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise TwseHistoryError("TWSE response must be a JSON object")
    return payload


def build_twse_history(
    symbol: str,
    *,
    fetcher: Any | None = None,
    months: int = HISTORY_MONTHS,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Stitch the last `months` STOCK_DAY pages into one candle series."""

    fetcher = fetcher or fetch_twse_stock_day
    stock_no = "".join(ch for ch in str(symbol).upper() if ch.isalnum())[:8]
    # Taiwan codes are 4-6 digits with an optional letter suffix (00982A is
    # an active ETF; leveraged pairs end in L/R).
    if not (stock_no[:4].isdigit() and all(ch.isdigit() or ch.isalpha() for ch in stock_no)):
        raise TwseHistoryError("TWSE history needs a Taiwan stock number")
    moment = now or datetime.now(tz=UTC)
    candles: list[dict[str, str]] = []
    year, month = moment.year, moment.month
    stamps: list[str] = []
    for _ in range(max(1, months)):
        stamps.append(f"{year:04d}{month:02d}01")
        month -= 1
        if month == 0:
            year, month = year - 1, 12
    for index, stamp in enumerate(reversed(stamps)):  # oldest month first
        if index:
            time.sleep(_FETCH_PAUSE_SECONDS)
        raw = fetcher(stock_no=stock_no, yyyymmdd=stamp)
        candles.extend(_parse_stock_day_rows(raw))
    if not candles:
        raise TwseHistoryError("TWSE STOCK_DAY returned no usable rows")
    candles.sort(key=lambda row: row["closed_at"])
    stamp_now = moment.isoformat(timespec="seconds").replace("+00:00", "Z")
    return {
        "symbol": stock_no,
        "interval": "1day",
        "candles": candles[-MAX_TW_CANDLES:],
        "status": {
            "source": "twse_stock_day",
            "provider_id": "twse_public_stock_day",
            "state": "live",
            "last_update": stamp_now,
        },
    }


def _parse_stock_day_rows(raw: dict[str, Any]) -> list[dict[str, str]]:
    if str(raw.get("stat") or "").upper() not in {"OK"}:
        return []
    rows = raw.get("data") if isinstance(raw.get("data"), list) else []
    candles: list[dict[str, str]] = []
    for row in rows:
        if not isinstance(row, list) or len(row) < 7:
            continue
        closed_at = _roc_to_iso(str(row[0]))
        candle = {
            "open": _clean_number(row[3]),
            "high": _clean_number(row[4]),
            "low": _clean_number(row[5]),
            "close": _clean_number(row[6]),
            "closed_at": closed_at,
        }
        if not closed_at or "" in (candle["open"], candle["high"], candle["low"], candle["close"]):
            continue
        candles.append(candle)
    return candles


def _roc_to_iso(value: str) -> str:
    parts = value.strip().split("/")
    if len(parts) != 3:
        return ""
    try:
        year = int(parts[0]) + 1911
        return f"{year:04d}-{int(parts[1]):02d}-{int(parts[2]):02d}"
    except ValueError:
        return ""


def _clean_number(value: Any) -> str:
    text = str(value or "").replace(",", "").strip()
    if not text or text in {"--", "X"}:
        return ""
    try:
        float(text)
    except ValueError:
        return ""
    return text
