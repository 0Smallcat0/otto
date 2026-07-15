"""TWSE OpenAPI daily quote snapshot adapter with no order semantics."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


TWSE_PROVIDER_ID = "twse_openapi_daily_quote_snapshot"
TWSE_SOURCE = "twse_stock_day_all_openapi"
TWSE_WATCHLIST = ("2330", "2317", "0050")
TWSE_MAX_WATCHLIST = 6
TWSE_QUOTE_URL = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
TWSE_DOCS_URL = "https://openapi.twse.com.tw/"
TWSE_SWAGGER_URL = "https://openapi.twse.com.tw/v1/swagger.json"
TWSE_DOCS_CHECKED_AT = "2026-05-27"
TWSE_TTL_SECONDS = 86400
TWSE_NOTICE = (
    "TWSE OpenAPI STOCK_DAY_ALL rows are daily public quote snapshots for local "
    "research only; they are not orderable and must not be used as broker, "
    "balance, margin, short, derivative, or live-trading execution data."
)


class TwseQuoteError(ValueError):
    """Raised when TWSE OpenAPI quote rows cannot be normalized safely."""


def twse_quote_snapshot_payload(
    caches: dict[str, dict[str, Any]] | None,
    *,
    fetcher: Any | None = None,
    refresh: bool = False,
    symbols: list[str] | str | None = None,
) -> dict[str, Any]:
    """Return bounded public TWSE OpenAPI daily quote snapshots."""

    safe_symbols = twse_symbol_list(symbols)
    fetcher = fetcher or fetch_twse_quote_snapshot
    cache_map = caches if isinstance(caches, dict) else {}
    payloads: list[dict[str, Any]] = []
    writable_cache: dict[str, dict[str, Any]] = {}
    messages: list[str] = []

    if refresh:
        try:
            raw = fetcher()
            payload = normalize_twse_quote_snapshot(raw, symbols=safe_symbols, state="live")
        except (TwseQuoteError, OSError, TimeoutError, URLError, HTTPError, json.JSONDecodeError) as exc:
            payloads = [
                _coerce_twse_payload(
                    cache_map.get(symbol),
                    state="stale_cache",
                    symbol=symbol,
                    message=(
                        "TWSE OpenAPI refresh failed; using local cache if present. "
                        f"{exc.__class__.__name__}."
                    ),
                )
                for symbol in safe_symbols
            ]
            messages.extend(str(payload["status"].get("message") or "") for payload in payloads)
        else:
            payloads.append(payload)
            cache = payload.get("cache")
            by_symbol = cache.get("twse_by_symbol") if isinstance(cache, dict) else {}
            if isinstance(by_symbol, dict):
                writable_cache.update(
                    {
                        str(symbol): quote_cache
                        for symbol, quote_cache in by_symbol.items()
                        if isinstance(quote_cache, dict)
                    }
                )
    else:
        for symbol in safe_symbols:
            cache = cache_map.get(symbol)
            if cache:
                payloads.append(_coerce_twse_payload(cache, state="stale_cache", symbol=symbol))
            else:
                payloads.append(
                    _empty_twse_payload(
                        state="unavailable",
                        symbol=symbol,
                        message="Run the TWSE OpenAPI daily quote refresh to populate this bounded cache.",
                    )
                )

    rows = [row for payload in payloads for row in payload.get("quotes", []) if isinstance(row, dict)]
    states = [str(payload.get("status", {}).get("state") or "") for payload in payloads]
    status_state = _combined_state(states, rows)
    first_symbol = safe_symbols[0] if safe_symbols else TWSE_WATCHLIST[0]
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
        "entry": twse_provider_entry_summary(symbol=first_symbol),
        "cache": {
            "twse": payloads[0] if rows else None,
            "twse_by_symbol": writable_cache,
        },
    }


def twse_symbol_list(raw_symbols: list[str] | str | None = None) -> list[str]:
    if raw_symbols is None:
        return list(TWSE_WATCHLIST)
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
        if len(symbols) >= TWSE_MAX_WATCHLIST:
            break
    return symbols or list(TWSE_WATCHLIST)


def fetch_twse_quote_snapshot(*, timeout: float = 5.0) -> list[dict[str, Any]]:
    request = Request(TWSE_QUOTE_URL, headers={"User-Agent": "LocalFinancialTerminal/1.0"})
    with urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, list):
        raise TwseQuoteError("TWSE OpenAPI response was not a JSON row list")
    return [row for row in payload if isinstance(row, dict)]


def normalize_twse_quote_snapshot(
    raw: list[dict[str, Any]] | dict[str, Any],
    *,
    symbols: list[str] | str | None = None,
    state: str = "live",
) -> dict[str, Any]:
    safe_symbols = twse_symbol_list(symbols)
    source_rows = _raw_rows(raw)
    rows_by_code = {_text(row.get("Code")).upper(): row for row in source_rows}
    retrieved_at = _utc_now()
    rows: list[dict[str, Any]] = []
    by_symbol: dict[str, dict[str, Any]] = {}
    for symbol in safe_symbols:
        raw_row = rows_by_code.get(symbol)
        if not raw_row:
            continue
        row = _normalize_row(raw_row, symbol=symbol, retrieved_at=retrieved_at)
        rows.append(row)
        by_symbol[symbol] = _single_symbol_payload(row, state=state)
    if not rows:
        raise TwseQuoteError("TWSE OpenAPI response did not contain requested quote rows")
    first_symbol = rows[0]["symbol"]
    return {
        "status": _status(
            state=state,
            last_update=retrieved_at,
            message="TWSE OpenAPI daily quote snapshot normalized; quote is not orderable.",
            symbol=first_symbol,
        ),
        "quotes": rows,
        "summary": _summary_from_rows(rows, symbols=safe_symbols),
        "entry": twse_provider_entry_summary(symbol=first_symbol),
        "cache": {"twse": None, "twse_by_symbol": by_symbol},
    }


def twse_provider_entry_summary(symbol: str = TWSE_WATCHLIST[0]) -> dict[str, Any]:
    safe_symbol = _safe_symbol(symbol) or TWSE_WATCHLIST[0]
    return {
        "provider_id": TWSE_PROVIDER_ID,
        "official_docs": [TWSE_DOCS_URL, TWSE_SWAGGER_URL],
        "docs_checked_at": TWSE_DOCS_CHECKED_AT,
        "auth_mode": "public-no-key",
        "rate_limit": "Use bounded STOCK_DAY_ALL refreshes; no private, broker, or realtime feeds.",
        "terms_risk": (
            "TWSE OpenAPI publishes listed-stock daily trading rows; keep them as delayed "
            "public snapshots and do not imply order routing, balances, or tradeability."
        ),
        "cache_path": _cache_path(safe_symbol),
        "ttl_seconds": TWSE_TTL_SECONDS,
        "schema": "STOCK_DAY_ALL -> Date/Code/Name/TradeVolume/TradeValue/OHLC/Change/Transaction",
        "fallback": "Show last local daily snapshot cache or explicit unavailable state; never use fixture quotes.",
        "safety_class": "public_read_only_market_data",
    }


def _raw_rows(raw: list[dict[str, Any]] | dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(raw, list):
        return [row for row in raw if isinstance(row, dict)]
    if isinstance(raw, dict):
        data = raw.get("data")
        if isinstance(data, list):
            return [row for row in data if isinstance(row, dict)]
    raise TwseQuoteError("TWSE OpenAPI response did not contain a row list")


def _normalize_row(raw: dict[str, Any], *, symbol: str, retrieved_at: str) -> dict[str, Any]:
    price = _number_text(raw.get("ClosingPrice"))
    if not price:
        raise TwseQuoteError(f"TWSE quote for {symbol} has no usable ClosingPrice value")
    open_value = _number_text(raw.get("OpeningPrice"))
    change = _number_text(raw.get("Change"))
    return {
        "symbol": symbol,
        "name": _text(raw.get("Name")) or symbol,
        "date": _text(raw.get("Date")),
        "price": price,
        "open": open_value,
        "high": _number_text(raw.get("HighestPrice")),
        "low": _number_text(raw.get("LowestPrice")),
        "close": price,
        "volume": _number_text(raw.get("TradeVolume")),
        "value": _number_text(raw.get("TradeValue")),
        "transaction_count": _number_text(raw.get("Transaction")),
        "change": change,
        "change_percent": _change_percent(open_value, price),
        "currency": "TWD",
        "source": TWSE_SOURCE,
        "provider_id": TWSE_PROVIDER_ID,
        "retrieved_at": retrieved_at,
        "cache_path": _cache_path(symbol),
        "quote_semantics": "quote_not_orderable",
        "delay": "official_daily_snapshot",
        "context_only": False,
        "live_action_enabled": False,
        "orderable": False,
    }


def _single_symbol_payload(row: dict[str, Any], *, state: str) -> dict[str, Any]:
    symbol = str(row.get("symbol") or TWSE_WATCHLIST[0])
    rows = [row]
    return {
        "status": _status(
            state=state,
            last_update=str(row.get("retrieved_at") or ""),
            message="TWSE OpenAPI daily quote snapshot normalized; quote is not orderable.",
            symbol=symbol,
        ),
        "quotes": rows,
        "summary": _summary_from_rows(rows, symbols=[symbol]),
        "entry": twse_provider_entry_summary(symbol=symbol),
        "cache": {"twse": None},
    }


def _coerce_twse_payload(
    payload: dict[str, Any] | None,
    *,
    state: str,
    symbol: str,
    message: str | None = None,
) -> dict[str, Any]:
    if isinstance(payload, dict) and _payload_has_rows(payload):
        rows = [row for row in payload.get("quotes", []) if isinstance(row, dict)]
        status = _status(
            state=state,
            last_update=_latest_retrieved_at(rows),
            message=message or "Using local TWSE OpenAPI daily quote snapshot cache.",
            symbol=symbol,
        )
        return {
            "status": status,
            "quotes": rows,
            "summary": _summary_from_rows(rows, symbols=[symbol]),
            "entry": twse_provider_entry_summary(symbol=symbol),
            "cache": {"twse": None},
        }
    return _empty_twse_payload(state="unavailable", symbol=symbol, message=message)


def _empty_twse_payload(*, state: str, symbol: str, message: str | None = None) -> dict[str, Any]:
    status = _status(
        state=state,
        last_update="",
        message=message or "TWSE OpenAPI daily quote snapshot cache is unavailable.",
        symbol=symbol,
    )
    return {
        "status": status,
        "quotes": [],
        "summary": _summary_from_rows([], symbols=[symbol]),
        "entry": twse_provider_entry_summary(symbol=symbol),
        "cache": {"twse": None},
    }


def _status(
    *,
    state: str,
    last_update: str,
    message: str,
    symbol: str,
) -> dict[str, str | bool]:
    return {
        "source": TWSE_SOURCE,
        "state": state,
        "last_update": last_update,
        "message": message,
        "provider_id": TWSE_PROVIDER_ID,
        "symbol": symbol,
        "cache_path": _cache_path(symbol),
        "docs_url": TWSE_DOCS_URL,
        "swagger_url": TWSE_SWAGGER_URL,
        "quote_semantics": "quote_not_orderable",
        "live_action_enabled": False,
        "orderable": False,
    }


def _summary_from_rows(rows: list[dict[str, Any]], *, symbols: list[str]) -> dict[str, Any]:
    first = rows[0] if rows else {}
    return {
        "provider_id": TWSE_PROVIDER_ID,
        "source": TWSE_SOURCE,
        "symbol": str(first.get("symbol") or (symbols[0] if symbols else TWSE_WATCHLIST[0])),
        "symbols": ",".join(symbols or list(TWSE_WATCHLIST)),
        "price": str(first.get("price") or ""),
        "change": str(first.get("change") or ""),
        "change_percent": str(first.get("change_percent") or ""),
        "latest_date": str(first.get("date") or ""),
        "currency": "TWD",
        "row_count": len(rows),
        "requested_count": len(symbols),
        "quote_semantics": "quote_not_orderable",
        "notice": TWSE_NOTICE,
    }


def _combined_state(states: list[str], rows: list[dict[str, Any]]) -> str:
    if any(state == "live" for state in states) and rows:
        return "live"
    if rows:
        return "stale_cache"
    return "unavailable"


def _combined_message(state: str, rows: list[dict[str, Any]], messages: list[str]) -> str:
    if state == "live":
        return "TWSE OpenAPI daily quote snapshots refreshed; rows are not orderable."
    if rows:
        return "Using local TWSE OpenAPI daily quote snapshot cache; rows are not orderable."
    return next((message for message in messages if message), "Run TWSE refresh to populate public no-key quote snapshots.")


def _payload_has_rows(payload: dict[str, Any] | None) -> bool:
    return isinstance(payload, dict) and any(isinstance(row, dict) for row in payload.get("quotes", []))


def _latest_retrieved_at(rows: list[dict[str, Any]]) -> str:
    values = [str(row.get("retrieved_at") or "") for row in rows if isinstance(row, dict)]
    return max(values) if values else ""


def _change_percent(open_value: str, close_value: str) -> str:
    try:
        open_decimal = Decimal(open_value)
        close_decimal = Decimal(close_value)
        if open_decimal == 0:
            return ""
        percent = ((close_decimal - open_decimal) / open_decimal * Decimal("100")).quantize(
            Decimal("0.01")
        )
    except (InvalidOperation, ValueError):
        return ""
    return str(percent)


def _number_text(value: Any) -> str:
    text = _text(value).replace(",", "")
    return "" if text in {"", "--", "-"} else text


def _text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _safe_symbol(value: Any) -> str:
    text = "".join(ch for ch in str(value).upper() if ch.isalnum())
    return text[:12]


def _cache_path(symbol: str) -> str:
    safe_symbol = _safe_symbol(symbol) or TWSE_WATCHLIST[0]
    return f"market_data/quotes/twse/{safe_symbol}.json"


def _utc_now() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
