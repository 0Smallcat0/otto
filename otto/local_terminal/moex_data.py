"""MOEX ISS delayed quote snapshot adapter with no order semantics."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


MOEX_PROVIDER_ID = "moex_iss_delayed_quote_snapshot"
MOEX_SOURCE = "moex_iss_marketdata_delayed"
MOEX_WATCHLIST = ("SBER", "GAZP", "MOEX")
MOEX_MAX_WATCHLIST = 6
MOEX_BOARD = "TQBR"
MOEX_QUOTE_URL_TEMPLATE = (
    "https://iss.moex.com/iss/engines/stock/markets/shares/securities/{symbol}.json"
)
MOEX_DOCS_URL = "https://www.moex.com/a2920"
MOEX_DEVELOPER_MANUAL_URL = "https://www.moex.com/files/4be999zbzp80bx2bgmwayrtyx0"
MOEX_DOCS_CHECKED_AT = "2026-05-26"
MOEX_TTL_SECONDS = 900
MOEX_NOTICE = (
    "MOEX ISS rows are delayed public market-data snapshots for local research only; "
    "they are not orderable and must not be used as broker, balance, margin, short, "
    "derivative, or live-trading execution data."
)


class MoexQuoteError(ValueError):
    """Raised when MOEX ISS quote rows cannot be normalized safely."""


def moex_quote_snapshot_payload(
    caches: dict[str, dict[str, Any]] | None,
    *,
    fetcher: Any | None = None,
    refresh: bool = False,
    symbols: list[str] | str | None = None,
) -> dict[str, Any]:
    """Return bounded public MOEX ISS delayed quote snapshots."""

    safe_symbols = moex_symbol_list(symbols)
    fetcher = fetcher or fetch_moex_quote_snapshot
    cache_map = caches if isinstance(caches, dict) else {}
    payloads: list[dict[str, Any]] = []
    writable_cache: dict[str, dict[str, Any]] = {}
    messages: list[str] = []

    for symbol in safe_symbols:
        cache = cache_map.get(symbol)
        if refresh:
            try:
                raw = fetcher(symbol=symbol)
                payload = normalize_moex_quote_snapshot(raw, symbol=symbol, state="live")
            except (MoexQuoteError, OSError, TimeoutError, URLError, HTTPError, json.JSONDecodeError) as exc:
                payload = _coerce_moex_payload(
                    cache,
                    state="stale_cache",
                    symbol=symbol,
                    message=f"MOEX ISS refresh failed; using local cache if present. {exc.__class__.__name__}.",
                )
                messages.append(str(payload["status"].get("message") or ""))
            payloads.append(payload)
            if _payload_has_rows(payload):
                writable_cache[symbol] = payload
            continue
        if cache:
            payloads.append(_coerce_moex_payload(cache, state="stale_cache", symbol=symbol))
        else:
            payloads.append(
                _empty_moex_payload(
                    state="unavailable",
                    symbol=symbol,
                    message="Run the MOEX ISS delayed quote refresh to populate this bounded cache.",
                )
            )

    rows = [row for payload in payloads for row in payload.get("quotes", []) if isinstance(row, dict)]
    states = [str(payload.get("status", {}).get("state") or "") for payload in payloads]
    status_state = _combined_state(states, rows)
    first_symbol = safe_symbols[0] if safe_symbols else MOEX_WATCHLIST[0]
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
        "entry": moex_provider_entry_summary(symbol=first_symbol),
        "cache": {
            "moex": payloads[0] if rows else None,
            "moex_by_symbol": writable_cache,
        },
    }


def moex_symbol_list(raw_symbols: list[str] | str | None = None) -> list[str]:
    if raw_symbols is None:
        return list(MOEX_WATCHLIST)
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
        if len(symbols) >= MOEX_MAX_WATCHLIST:
            break
    return symbols or list(MOEX_WATCHLIST)


def fetch_moex_quote_snapshot(*, symbol: str, timeout: float = 5.0) -> dict[str, Any]:
    safe_symbol = _safe_symbol(symbol) or MOEX_WATCHLIST[0]
    params = urlencode(
        {
            "iss.meta": "off",
            "iss.only": "securities,marketdata",
            "securities.columns": "SECID,SHORTNAME,BOARDID",
            "marketdata.columns": (
                "SECID,LAST,OPEN,HIGH,LOW,VOLTODAY,VALTODAY,UPDATETIME,BID,OFFER,BOARDID"
            ),
        }
    )
    url = f"{MOEX_QUOTE_URL_TEMPLATE.format(symbol=safe_symbol)}?{params}"
    request = Request(url, headers={"User-Agent": "LocalFinancialTerminal/1.0"})
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def normalize_moex_quote_snapshot(
    raw: dict[str, Any],
    *,
    symbol: str = MOEX_WATCHLIST[0],
    state: str = "live",
) -> dict[str, Any]:
    safe_symbol = _safe_symbol(symbol) or MOEX_WATCHLIST[0]
    securities = _table_rows(raw.get("securities"))
    marketdata = _table_rows(raw.get("marketdata"))
    security = _choose_row(securities, board=MOEX_BOARD) or {}
    quote = _choose_quote_row(marketdata, symbol=safe_symbol)
    if not quote:
        raise MoexQuoteError(f"MOEX ISS response for {safe_symbol} did not contain a quote row")
    last = _text(quote.get("LAST"))
    if not last:
        raise MoexQuoteError(f"MOEX ISS quote for {safe_symbol} has no usable LAST value")
    open_value = _text(quote.get("OPEN"))
    change, change_percent = _change_fields(open_value, last)
    board_id = _text(quote.get("BOARDID")) or _text(security.get("BOARDID")) or MOEX_BOARD
    retrieved_at = _utc_now()
    row = {
        "symbol": safe_symbol,
        "name": _text(security.get("SHORTNAME")) or safe_symbol,
        "board_id": board_id,
        "price": last,
        "open": open_value,
        "high": _text(quote.get("HIGH")),
        "low": _text(quote.get("LOW")),
        "volume": _text(quote.get("VOLTODAY")),
        "value": _text(quote.get("VALTODAY")),
        "bid": _text(quote.get("BID")),
        "ask": _text(quote.get("OFFER")),
        "update_time": _text(quote.get("UPDATETIME")),
        "change": change,
        "change_percent": change_percent,
        "currency": "RUB",
        "source": MOEX_SOURCE,
        "provider_id": MOEX_PROVIDER_ID,
        "retrieved_at": retrieved_at,
        "cache_path": _cache_path(safe_symbol),
        "quote_semantics": "quote_not_orderable",
        "delay": "15_minute_delayed_without_auth",
        "context_only": False,
        "live_action_enabled": False,
        "orderable": False,
    }
    return {
        "status": _status(
            state=state,
            last_update=retrieved_at,
            message="MOEX ISS delayed quote snapshot normalized; quote is not orderable.",
            symbol=safe_symbol,
        ),
        "quotes": [row],
        "summary": _summary_from_rows([row], symbols=[safe_symbol]),
        "entry": moex_provider_entry_summary(symbol=safe_symbol),
        "cache": {"moex": None},
    }


def moex_provider_entry_summary(symbol: str = MOEX_WATCHLIST[0]) -> dict[str, Any]:
    safe_symbol = _safe_symbol(symbol) or MOEX_WATCHLIST[0]
    return {
        "provider_id": MOEX_PROVIDER_ID,
        "official_docs": [MOEX_DOCS_URL, MOEX_DEVELOPER_MANUAL_URL],
        "docs_checked_at": MOEX_DOCS_CHECKED_AT,
        "auth_mode": "public-no-key",
        "rate_limit": "Use bounded explicit securities requests; no orderbook or authenticated ISS calls.",
        "terms_risk": (
            "MOEX ISS documentation says unauthenticated market data is delayed; "
            "do not request subscriber-only orderbooks or authenticated real-time data."
        ),
        "cache_path": _cache_path(safe_symbol),
        "ttl_seconds": MOEX_TTL_SECONDS,
        "schema": "/iss/engines/stock/markets/shares/securities/{symbol}.json -> securities + marketdata",
        "fallback": "Show last local delayed snapshot cache or explicit unavailable state; never use fixture quotes.",
        "safety_class": "public_read_only_market_data",
    }


def _table_rows(table: Any) -> list[dict[str, Any]]:
    if not isinstance(table, dict):
        return []
    columns = table.get("columns")
    data = table.get("data")
    if not isinstance(columns, list) or not isinstance(data, list):
        return []
    rows: list[dict[str, Any]] = []
    for values in data:
        if not isinstance(values, list):
            continue
        rows.append({str(column): values[index] if index < len(values) else "" for index, column in enumerate(columns)})
    return rows


def _choose_row(rows: list[dict[str, Any]], *, board: str) -> dict[str, Any] | None:
    for row in rows:
        if _text(row.get("BOARDID")).upper() == board:
            return row
    return rows[0] if rows else None


def _choose_quote_row(rows: list[dict[str, Any]], *, symbol: str) -> dict[str, Any] | None:
    matching = [row for row in rows if _text(row.get("SECID")).upper() == symbol]
    for row in matching:
        if _text(row.get("BOARDID")).upper() == MOEX_BOARD and _text(row.get("LAST")):
            return row
    for row in matching:
        if _text(row.get("LAST")):
            return row
    return _choose_row(matching, board=MOEX_BOARD)


def _coerce_moex_payload(
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
        status["message"] = message or "Showing last local MOEX ISS delayed snapshot cache."
        payload["status"] = status
        summary = dict(payload.get("summary") if isinstance(payload.get("summary"), dict) else {})
        row_count = len(payload.get("quotes") if isinstance(payload.get("quotes"), list) else [])
        summary["row_count"] = row_count
        summary["live_count"] = 0
        summary["cached_count"] = row_count
        summary["stale_count"] = row_count if state == "stale_cache" else 0
        summary["unavailable_count"] = 0
        payload["summary"] = summary
        payload.setdefault("entry", moex_provider_entry_summary(symbol=symbol))
        payload["cache"] = {"moex": None}
        return payload
    return _empty_moex_payload(
        state="unavailable" if state == "stale_cache" else state,
        symbol=symbol,
        message=message or "No local MOEX ISS delayed snapshot cache is available.",
    )


def _empty_moex_payload(*, state: str, symbol: str, message: str) -> dict[str, Any]:
    safe_symbol = _safe_symbol(symbol) or MOEX_WATCHLIST[0]
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
            "latest_time": "",
            "row_count": 0,
            "requested_count": 1,
            "live_count": 0,
            "cached_count": 0,
            "stale_count": 0,
            "unavailable_count": 1,
            "source": MOEX_SOURCE,
            "provider_id": MOEX_PROVIDER_ID,
            "quote_semantics": "quote_not_orderable",
        },
        "entry": moex_provider_entry_summary(symbol=safe_symbol),
        "cache": {"moex": None},
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
        "symbol": str(first.get("symbol") or (symbols[0] if symbols else MOEX_WATCHLIST[0])),
        "symbols": ",".join(symbols),
        "price": str(first.get("price") or ""),
        "change": str(first.get("change") or ""),
        "change_percent": str(first.get("change_percent") or ""),
        "latest_time": str(first.get("update_time") or ""),
        "row_count": len(rows),
        "requested_count": len(symbols),
        **state_counts,
        "source": MOEX_SOURCE,
        "provider_id": MOEX_PROVIDER_ID,
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
        return "MOEX ISS delayed quote snapshots refreshed; rows are not orderable."
    if state == "partial":
        return "Some MOEX ISS snapshots refreshed; unavailable rows remain explicit."
    if rows:
        return "Showing local MOEX ISS delayed snapshot cache; refresh for current public rows."
    return messages[0] if messages else "No MOEX ISS delayed snapshot cache is available yet."


def _latest_retrieved_at(rows: list[dict[str, Any]]) -> str:
    retrieved = [str(row.get("retrieved_at") or "") for row in rows if row.get("retrieved_at")]
    return max(retrieved) if retrieved else "not refreshed"


def _payload_has_rows(payload: dict[str, Any] | None) -> bool:
    return isinstance(payload, dict) and any(
        isinstance(row, dict) for row in payload.get("quotes", [])
    )


def _status(*, state: str, last_update: str, message: str, symbol: str) -> dict[str, Any]:
    safe_symbol = _safe_symbol(symbol) or MOEX_WATCHLIST[0]
    return {
        "source": MOEX_SOURCE,
        "provider_id": MOEX_PROVIDER_ID,
        "state": state,
        "last_update": last_update,
        "message": message,
        "cache_path": _cache_path(safe_symbol),
        "docs_url": MOEX_DOCS_URL,
        "developer_manual_url": MOEX_DEVELOPER_MANUAL_URL,
        "symbol": safe_symbol,
        "auth_mode": "no-key",
        "quote_semantics": "quote_not_orderable",
        "live_action_enabled": False,
    }


def _safe_symbol(value: Any) -> str:
    raw = str(value or "").strip().upper().replace("/", "")
    return "".join(ch for ch in raw if ch.isalnum() or ch in {".", "^", "-"})[:24]


def _safe_path_part(symbol: str) -> str:
    return "".join(ch for ch in symbol.upper() if ch.isalnum())[:24] or "SBER"


def _cache_path(symbol: str) -> str:
    return f"market_data/quotes/moex/{_safe_path_part(symbol)}.json"


def _text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.upper() in {"N/D", "NONE", "NULL"} else text


def _change_fields(open_value: str, last: str) -> tuple[str, str]:
    open_decimal = _decimal(open_value)
    last_decimal = _decimal(last)
    if open_decimal is None or last_decimal is None:
        return "", ""
    change = last_decimal - open_decimal
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
