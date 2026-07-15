"""Stooq public quote snapshot adapter with no broker or order semantics."""

from __future__ import annotations

import csv
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from io import StringIO
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen


STOOQ_PROVIDER_ID = "stooq_public_quote_snapshot"
STOOQ_SOURCE = "stooq_current_quote_csv"
STOOQ_WATCHLIST = ("AAPL.US", "SPY.US", "^SPX", "EURUSD")
STOOQ_MAX_WATCHLIST = 6
STOOQ_QUOTE_URL = "https://stooq.com/q/l/"
STOOQ_DOCS_URL = "https://stooq.com/q/?s=^spx"
STOOQ_HISTORICAL_DOCS_URL = "https://stooq.com/db/h/"
STOOQ_DOCS_CHECKED_AT = "2026-05-26"
STOOQ_TTL_SECONDS = 900
STOOQ_NOTICE = (
    "Stooq public CSV snapshot rows are delayed/reference market data, are not "
    "orderable, and must not be used as broker, balance, margin, short, derivative, "
    "or live-trading execution data."
)


class StooqQuoteError(ValueError):
    """Raised when Stooq public quote rows cannot be normalized safely."""


def stooq_quote_snapshot_payload(
    caches: dict[str, dict[str, Any]] | None,
    *,
    fetcher: Any | None = None,
    refresh: bool = False,
    symbols: list[str] | str | None = None,
) -> dict[str, Any]:
    """Return bounded public Stooq quote snapshots without credential material."""

    safe_symbols = stooq_symbol_list(symbols)
    fetcher = fetcher or fetch_stooq_quote_snapshot
    cache_map = caches if isinstance(caches, dict) else {}
    payloads: list[dict[str, Any]] = []
    writable_cache: dict[str, dict[str, Any]] = {}
    messages: list[str] = []

    for symbol in safe_symbols:
        cache = cache_map.get(symbol)
        if refresh:
            try:
                raw = fetcher(symbol=symbol)
                payload = normalize_stooq_quote_snapshot(raw, symbol=symbol, state="live")
            except (StooqQuoteError, OSError, TimeoutError, URLError, HTTPError) as exc:
                payload = _coerce_stooq_payload(
                    cache,
                    state="stale_cache",
                    symbol=symbol,
                    message=f"Stooq refresh failed; using local cache if present. {exc.__class__.__name__}.",
                )
                messages.append(str(payload["status"].get("message") or ""))
            payloads.append(payload)
            if _payload_has_rows(payload):
                writable_cache[symbol] = payload
            continue
        if cache:
            payloads.append(_coerce_stooq_payload(cache, state="stale_cache", symbol=symbol))
        else:
            payloads.append(
                _empty_stooq_payload(
                    state="unavailable",
                    symbol=symbol,
                    message="Run the Stooq public snapshot refresh to populate this bounded cache.",
                )
            )

    rows = [row for payload in payloads for row in payload.get("quotes", []) if isinstance(row, dict)]
    states = [str(payload.get("status", {}).get("state") or "") for payload in payloads]
    status_state = _combined_state(states, rows)
    first_symbol = safe_symbols[0] if safe_symbols else STOOQ_WATCHLIST[0]
    status = _status(
        state=status_state,
        last_update=_latest_retrieved_at(rows),
        message=_combined_message(status_state, rows, messages),
        symbol=first_symbol,
    )
    summary = _summary_from_rows(rows, symbols=safe_symbols)
    row_state_pairs = [
        (str(payload.get("status", {}).get("state") or ""), payload)
        for payload in payloads
        if _payload_has_rows(payload)
    ]
    summary["live_count"] = sum(1 for state, _ in row_state_pairs if state == "live")
    summary["cached_count"] = sum(1 for state, _ in row_state_pairs if state != "live")
    summary["stale_count"] = sum(1 for state, _ in row_state_pairs if state == "stale_cache")
    summary["unavailable_count"] = max(len(safe_symbols) - len(rows), 0)
    return {
        "status": status,
        "quotes": rows,
        "summary": summary,
        "entry": stooq_provider_entry_summary(symbol=first_symbol),
        "cache": {
            "stooq": payloads[0] if rows else None,
            "stooq_by_symbol": writable_cache,
        },
    }


def stooq_symbol_list(raw_symbols: list[str] | str | None = None) -> list[str]:
    if raw_symbols is None:
        return list(STOOQ_WATCHLIST)
    raw_values: list[Any]
    if isinstance(raw_symbols, str):
        raw_values = [value.strip() for value in raw_symbols.replace(";", ",").split(",")]
    elif isinstance(raw_symbols, list):
        raw_values = raw_symbols
    else:
        raw_values = []
    symbols: list[str] = []
    for value in raw_values:
        symbol = _safe_symbol(value)
        if symbol and symbol not in symbols:
            symbols.append(symbol)
        if len(symbols) >= STOOQ_MAX_WATCHLIST:
            break
    return symbols or list(STOOQ_WATCHLIST)


def fetch_stooq_quote_snapshot(*, symbol: str, timeout: float = 5.0) -> dict[str, Any]:
    safe_symbol = _safe_symbol(symbol) or STOOQ_WATCHLIST[0]
    params = urlencode({"s": safe_symbol.lower(), "f": "sd2t2ohlcv", "h": "", "e": "csv"})
    with urlopen(f"{STOOQ_QUOTE_URL}?{params}", timeout=timeout) as response:
        text = response.read().decode("utf-8-sig")
    reader = csv.DictReader(StringIO(text))
    rows = [dict(row) for row in reader]
    if not rows:
        raise StooqQuoteError("Stooq CSV response did not contain quote rows")
    return rows[0]


def normalize_stooq_quote_snapshot(
    raw: dict[str, Any],
    *,
    symbol: str = STOOQ_WATCHLIST[0],
    state: str = "live",
) -> dict[str, Any]:
    safe_symbol = _safe_symbol(raw.get("Symbol") or raw.get("symbol") or symbol) or _safe_symbol(symbol)
    if not safe_symbol:
        raise StooqQuoteError("Stooq quote row is missing a usable symbol")
    date = _text(raw.get("Date") or raw.get("date"))
    time = _text(raw.get("Time") or raw.get("time"))
    close = _text(raw.get("Close") or raw.get("close"))
    if close.upper() == "N/D" or not close:
        raise StooqQuoteError(f"Stooq quote for {safe_symbol} has no usable close value")
    open_value = _text(raw.get("Open") or raw.get("open"))
    change, change_percent = _change_fields(open_value, close)
    retrieved_at = _utc_now()
    row = {
        "symbol": safe_symbol,
        "date": date,
        "time": time,
        "open": open_value,
        "high": _text(raw.get("High") or raw.get("high")),
        "low": _text(raw.get("Low") or raw.get("low")),
        "close": close,
        "price": close,
        "volume": _text(raw.get("Volume") or raw.get("volume")),
        "change": change,
        "change_percent": change_percent,
        "source": STOOQ_SOURCE,
        "provider_id": STOOQ_PROVIDER_ID,
        "retrieved_at": retrieved_at,
        "cache_path": _cache_path(safe_symbol),
        "quote_semantics": "quote_not_orderable",
        "context_only": False,
        "live_action_enabled": False,
        "orderable": False,
    }
    return {
        "status": _status(
            state=state,
            last_update=retrieved_at,
            message="Stooq public quote snapshot normalized; quote is not orderable.",
            symbol=safe_symbol,
        ),
        "quotes": [row],
        "summary": _summary_from_rows([row], symbols=[safe_symbol]),
        "entry": stooq_provider_entry_summary(symbol=safe_symbol),
        "cache": {"stooq": None},
    }


def stooq_provider_entry_summary(symbol: str = STOOQ_WATCHLIST[0]) -> dict[str, Any]:
    safe_symbol = _safe_symbol(symbol) or STOOQ_WATCHLIST[0]
    return {
        "provider_id": STOOQ_PROVIDER_ID,
        "official_docs": [STOOQ_DOCS_URL, STOOQ_HISTORICAL_DOCS_URL],
        "docs_checked_at": STOOQ_DOCS_CHECKED_AT,
        "auth_mode": "public-no-key",
        "rate_limit": "Use bounded, explicit per-symbol CSV snapshot requests only; no bulk crawler.",
        "terms_risk": (
            "Stooq quote pages attribute upstream data providers; historical CSV download now "
            "requires a CAPTCHA/API-link gate and is not implemented in this adapter."
        ),
        "cache_path": _cache_path(safe_symbol),
        "ttl_seconds": STOOQ_TTL_SECONDS,
        "schema": "/q/l CSV -> bounded delayed/reference quote snapshot rows",
        "fallback": "Show last local snapshot cache or explicit unavailable state; never use fixture quotes.",
        "safety_class": "public_read_only_market_data",
    }


def _coerce_stooq_payload(
    cache: dict[str, Any] | None,
    *,
    state: str,
    symbol: str,
    message: str | None = None,
) -> dict[str, Any]:
    if isinstance(cache, dict) and _payload_has_rows(cache):
        payload = dict(cache)
        status = dict(payload.get("status") if isinstance(payload.get("status"), dict) else {})
        status["state"] = state
        status["message"] = message or "Showing last local Stooq snapshot cache."
        payload["status"] = status
        summary = dict(payload.get("summary") if isinstance(payload.get("summary"), dict) else {})
        row_count = len(payload.get("quotes") if isinstance(payload.get("quotes"), list) else [])
        summary["row_count"] = row_count
        summary["live_count"] = 0
        summary["cached_count"] = row_count
        summary["stale_count"] = row_count if state == "stale_cache" else 0
        summary["unavailable_count"] = 0
        payload["summary"] = summary
        payload.setdefault("entry", stooq_provider_entry_summary(symbol=symbol))
        payload["cache"] = {"stooq": None}
        return payload
    return _empty_stooq_payload(
        state="unavailable" if state == "stale_cache" else state,
        symbol=symbol,
        message=message or "No local Stooq snapshot cache is available.",
    )


def _empty_stooq_payload(*, state: str, symbol: str, message: str) -> dict[str, Any]:
    safe_symbol = _safe_symbol(symbol) or STOOQ_WATCHLIST[0]
    return {
        "status": _status(
            state=state,
            last_update="not refreshed",
            message=message,
            symbol=safe_symbol,
        ),
        "quotes": [],
        "summary": {
            "symbol": safe_symbol,
            "symbols": safe_symbol,
            "price": "",
            "change": "",
            "change_percent": "",
            "latest_date": "",
            "latest_time": "",
            "row_count": 0,
            "requested_count": 1,
            "live_count": 0,
            "cached_count": 0,
            "stale_count": 0,
            "unavailable_count": 1,
            "source": STOOQ_SOURCE,
            "provider_id": STOOQ_PROVIDER_ID,
            "quote_semantics": "quote_not_orderable",
        },
        "entry": stooq_provider_entry_summary(symbol=safe_symbol),
        "cache": {"stooq": None},
    }


def _summary_from_rows(rows: list[dict[str, Any]], *, symbols: list[str]) -> dict[str, Any]:
    first = rows[0] if rows else {}
    state_counts = {
        "live_count": sum(1 for row in rows if str(row.get("retrieved_at") or "")),
        "cached_count": 0,
        "stale_count": 0,
        "unavailable_count": max(len(symbols) - len(rows), 0),
    }
    return {
        "symbol": str(first.get("symbol") or (symbols[0] if symbols else STOOQ_WATCHLIST[0])),
        "symbols": ",".join(symbols),
        "price": str(first.get("price") or ""),
        "change": str(first.get("change") or ""),
        "change_percent": str(first.get("change_percent") or ""),
        "latest_date": str(first.get("date") or ""),
        "latest_time": str(first.get("time") or ""),
        "row_count": len(rows),
        "requested_count": len(symbols),
        **state_counts,
        "source": STOOQ_SOURCE,
        "provider_id": STOOQ_PROVIDER_ID,
        "quote_semantics": "quote_not_orderable",
    }


def _combined_state(states: list[str], rows: list[dict[str, Any]]) -> str:
    if rows and all(state == "live" for state in states):
        return "live"
    if rows and any(state == "live" for state in states):
        return "partial"
    if rows:
        return "stale_cache"
    return "unavailable"


def _combined_message(state: str, rows: list[dict[str, Any]], messages: list[str]) -> str:
    if state == "live":
        return "Stooq public quote snapshots refreshed; rows are not orderable."
    if state == "partial":
        return "Some Stooq snapshots refreshed; unavailable rows remain explicit."
    if rows:
        return "Showing local Stooq snapshot cache; refresh for current public rows."
    return messages[0] if messages else "No Stooq snapshot cache is available yet."


def _latest_retrieved_at(rows: list[dict[str, Any]]) -> str:
    retrieved = [str(row.get("retrieved_at") or "") for row in rows if row.get("retrieved_at")]
    return max(retrieved) if retrieved else "not refreshed"


def _payload_has_rows(payload: dict[str, Any] | None) -> bool:
    return isinstance(payload, dict) and any(
        isinstance(row, dict) for row in payload.get("quotes", [])
    )


def _status(*, state: str, last_update: str, message: str, symbol: str) -> dict[str, Any]:
    safe_symbol = _safe_symbol(symbol) or STOOQ_WATCHLIST[0]
    return {
        "source": STOOQ_SOURCE,
        "provider_id": STOOQ_PROVIDER_ID,
        "state": state,
        "last_update": last_update,
        "message": message,
        "cache_path": _cache_path(safe_symbol),
        "docs_url": STOOQ_DOCS_URL,
        "historical_docs_url": STOOQ_HISTORICAL_DOCS_URL,
        "symbol": safe_symbol,
        "auth_mode": "no-key",
        "quote_semantics": "quote_not_orderable",
        "live_action_enabled": False,
    }


def _safe_symbol(value: Any) -> str:
    raw = str(value or "").strip().upper().replace("/", "")
    return "".join(ch for ch in raw if ch.isalnum() or ch in {".", "^"})[:24]


def _safe_path_part(symbol: str) -> str:
    return "".join(ch for ch in symbol.upper() if ch.isalnum())[:24] or "AAPLUS"


def _cache_path(symbol: str) -> str:
    return f"market_data/quotes/stooq/{_safe_path_part(symbol)}.json"


def _text(value: Any) -> str:
    text = str(value or "").strip()
    return "" if text.upper() == "N/D" else text


def _change_fields(open_value: str, close: str) -> tuple[str, str]:
    open_decimal = _decimal(open_value)
    close_decimal = _decimal(close)
    if open_decimal is None or close_decimal is None:
        return "", ""
    change = close_decimal - open_decimal
    if open_decimal == 0:
        return _format_decimal(change), ""
    return _format_decimal(change), _format_decimal(change / open_decimal * Decimal("100"))


def _decimal(value: Any) -> Decimal | None:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _format_decimal(value: Decimal | None) -> str:
    if value is None:
        return ""
    return str(value.quantize(Decimal("0.0001")).normalize())


def _utc_now() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
