"""Yahoo Finance public quote snapshot adapter with no broker or order semantics.

Yahoo's public `v8/finance/chart` endpoint returns a delayed/reference quote in
its `meta` block without any credential. This adapter is a clean-room wrapper:
it fetches one symbol at a time, normalizes the `meta` into the same bounded,
non-orderable row shape the other public snapshot providers use, and never
touches broker, balance, margin, short, derivative, or live-trading semantics.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


YAHOO_PROVIDER_ID = "yahoo_finance_public_quote_snapshot"
YAHOO_SOURCE = "yahoo_finance_chart_quote"
YAHOO_WATCHLIST = ("AAPL", "MSFT", "NVDA", "SPY", "^GSPC", "^IXIC")
YAHOO_MAX_WATCHLIST = 8
YAHOO_QUOTE_URL = "https://query1.finance.yahoo.com/v8/finance/chart/"
YAHOO_DOCS_URL = "https://query1.finance.yahoo.com/v8/finance/chart/AAPL"
YAHOO_DOCS_CHECKED_AT = "2026-07-08"
YAHOO_TTL_SECONDS = 900
# Yahoo blocks the default Python-urllib agent; a plain browser agent is enough.
YAHOO_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
YAHOO_NOTICE = (
    "Yahoo Finance public chart snapshot rows are delayed/reference market data, "
    "are not orderable, and must not be used as broker, balance, margin, short, "
    "derivative, or live-trading execution data."
)


class YahooQuoteError(ValueError):
    """Raised when Yahoo public quote rows cannot be normalized safely."""


def yahoo_quote_snapshot_payload(
    caches: dict[str, dict[str, Any]] | None,
    *,
    fetcher: Any | None = None,
    refresh: bool = False,
    symbols: list[str] | str | None = None,
) -> dict[str, Any]:
    """Return bounded public Yahoo quote snapshots without credential material."""

    safe_symbols = yahoo_symbol_list(symbols)
    fetcher = fetcher or fetch_yahoo_quote_snapshot
    cache_map = caches if isinstance(caches, dict) else {}
    payloads: list[dict[str, Any]] = []
    writable_cache: dict[str, dict[str, Any]] = {}
    messages: list[str] = []

    for symbol in safe_symbols:
        cache = cache_map.get(symbol)
        if refresh:
            try:
                raw = fetcher(symbol=symbol)
                payload = normalize_yahoo_quote_snapshot(raw, symbol=symbol, state="live")
            except (YahooQuoteError, OSError, TimeoutError, URLError, HTTPError, ValueError) as exc:
                payload = _coerce_yahoo_payload(
                    cache,
                    state="stale_cache",
                    symbol=symbol,
                    message=f"Yahoo refresh failed; using local cache if present. {exc.__class__.__name__}.",
                )
                messages.append(str(payload["status"].get("message") or ""))
            payloads.append(payload)
            if _payload_has_rows(payload):
                writable_cache[symbol] = payload
            continue
        if cache:
            payloads.append(_coerce_yahoo_payload(cache, state="stale_cache", symbol=symbol))
        else:
            payloads.append(
                _empty_yahoo_payload(
                    state="unavailable",
                    symbol=symbol,
                    message="Run the Yahoo public snapshot refresh to populate this bounded cache.",
                )
            )

    rows = [row for payload in payloads for row in payload.get("quotes", []) if isinstance(row, dict)]
    states = [str(payload.get("status", {}).get("state") or "") for payload in payloads]
    status_state = _combined_state(states, rows)
    first_symbol = safe_symbols[0] if safe_symbols else YAHOO_WATCHLIST[0]
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
        "entry": yahoo_provider_entry_summary(symbol=first_symbol),
        "cache": {
            "yahoo": payloads[0] if rows else None,
            "yahoo_by_symbol": writable_cache,
        },
    }


def yahoo_symbol_list(raw_symbols: list[str] | str | None = None) -> list[str]:
    if raw_symbols is None:
        return list(YAHOO_WATCHLIST)
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
        if len(symbols) >= YAHOO_MAX_WATCHLIST:
            break
    return symbols or list(YAHOO_WATCHLIST)


def yahoo_lookup_symbols(raw_symbols: list[str] | str | None) -> list[str]:
    """Sanitized symbols for an explicit lookup — NO watchlist fallback.

    A lookup means "quote exactly what I asked for"; silently answering with
    the default watchlist when every requested symbol is invalid would be a
    lie. Returns an empty list in that case so callers can refuse.
    """
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
        if len(symbols) >= YAHOO_MAX_WATCHLIST:
            break
    return symbols


def fetch_yahoo_quote_snapshot(*, symbol: str, timeout: float = 6.0) -> dict[str, Any]:
    safe_symbol = _safe_symbol(symbol) or YAHOO_WATCHLIST[0]
    url = f"{YAHOO_QUOTE_URL}{quote(safe_symbol, safe='^=.-')}?range=1d&interval=1d"
    request = Request(url, headers={"User-Agent": YAHOO_USER_AGENT, "Accept": "application/json"})
    # One retry on a transient network blip: this quote is fetched live at
    # order-submit time, so a single dropped connection was refusing real
    # orders that succeeded on an identical retry (2026-07-24 loop drill —
    # the TW submit 400'd once, then filled). A genuine Yahoo error (bad
    # symbol, error block) still raises immediately below.
    last_error: OSError | None = None
    for attempt in (1, 2):
        try:
            with urlopen(request, timeout=timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
            break
        except (TimeoutError, URLError, OSError) as exc:
            last_error = exc
            if attempt == 2:
                raise
    else:  # pragma: no cover - loop always breaks or raises
        raise YahooQuoteError(f"Yahoo quote fetch failed for {safe_symbol}: {last_error}")
    chart = payload.get("chart") if isinstance(payload, dict) else None
    if not isinstance(chart, dict):
        raise YahooQuoteError("Yahoo chart response has no chart block")
    error = chart.get("error")
    if error:
        description = error.get("description") if isinstance(error, dict) else error
        raise YahooQuoteError(f"Yahoo chart error for {safe_symbol}: {description}")
    results = chart.get("result") if isinstance(chart.get("result"), list) else []
    meta = results[0].get("meta") if results and isinstance(results[0], dict) else None
    if not isinstance(meta, dict):
        raise YahooQuoteError(f"Yahoo chart result for {safe_symbol} has no meta block")
    return meta


def fetch_yahoo_daily_closes(
    *, symbol: str, start: str, end: str, timeout: float = 15.0
) -> dict[str, str]:
    """Published daily closes for `symbol`, keyed by session date (UTC).

    Same chart endpoint the live quote uses, asked for a date range instead of
    today. Only sessions the exchange actually printed appear — weekends and
    holidays are simply absent rather than carried forward, so a caller asking
    for a non-trading day has to decide for itself which session it means.

    A bar whose close is null is dropped: Yahoo emits one for the session in
    progress, and reading it as a real level would put a hole where a price is
    expected. `start`/`end` are ISO dates, end inclusive.
    """
    safe_symbol = _safe_symbol(symbol)
    if not safe_symbol:
        raise YahooQuoteError("Yahoo history needs a symbol")
    period1 = int(datetime.fromisoformat(f"{start}T00:00:00+00:00").timestamp())
    # End of the requested day, so the last session is inside the window.
    period2 = int(datetime.fromisoformat(f"{end}T00:00:00+00:00").timestamp()) + 86_400
    url = (
        f"{YAHOO_QUOTE_URL}{quote(safe_symbol, safe='^=.-')}"
        f"?period1={period1}&period2={period2}&interval=1d"
    )
    request = Request(url, headers={"User-Agent": YAHOO_USER_AGENT, "Accept": "application/json"})
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (TimeoutError, URLError, OSError) as exc:
        raise YahooQuoteError(f"Yahoo history fetch failed for {safe_symbol}: {exc}") from exc
    chart = payload.get("chart") if isinstance(payload, dict) else None
    if not isinstance(chart, dict):
        raise YahooQuoteError("Yahoo chart response has no chart block")
    if chart.get("error"):
        error = chart["error"]
        description = error.get("description") if isinstance(error, dict) else error
        raise YahooQuoteError(f"Yahoo chart error for {safe_symbol}: {description}")
    results = chart.get("result") if isinstance(chart.get("result"), list) else []
    result = results[0] if results and isinstance(results[0], dict) else {}
    stamps = result.get("timestamp") if isinstance(result.get("timestamp"), list) else []
    quotes = result.get("indicators", {}).get("quote") if isinstance(result, dict) else None
    closes = quotes[0].get("close") if isinstance(quotes, list) and quotes else []
    closes = closes if isinstance(closes, list) else []
    out: dict[str, str] = {}
    for stamp, close in zip(stamps, closes, strict=False):
        if close is None:
            continue
        day = datetime.fromtimestamp(int(stamp), tz=UTC).strftime("%Y-%m-%d")
        out[day] = _close_text(close)
    return out


def _close_text(close: Any) -> str:
    """A close as the exchange printed it, not as float64 stored it.

    Yahoo serialises 101.70 as 101.69999694824219. Carrying that into the
    ledger records eleven digits of precision the exchange never published —
    false precision reads as a measurement, which is the same defect as a stale
    quote wearing a live label. Four decimals keep every venue this touches
    (index points, TWD, BTC) and round the artefact away.

    Formatted with "f" and stripped by hand rather than Decimal.normalize(),
    which renders 1000 as 1E+3.
    """
    value = Decimal(str(close)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    return format(value, "f").rstrip("0").rstrip(".")


def normalize_yahoo_quote_snapshot(
    meta: dict[str, Any],
    *,
    symbol: str = YAHOO_WATCHLIST[0],
    state: str = "live",
) -> dict[str, Any]:
    safe_symbol = _safe_symbol(meta.get("symbol") or symbol) or _safe_symbol(symbol)
    if not safe_symbol:
        raise YahooQuoteError("Yahoo quote row is missing a usable symbol")
    price = _text(meta.get("regularMarketPrice"))
    if not price:
        raise YahooQuoteError(f"Yahoo quote for {safe_symbol} has no usable price value")
    previous_close = _text(meta.get("chartPreviousClose") or meta.get("previousClose"))
    change, change_percent = _change_fields(previous_close, price)
    retrieved_at = _utc_now()
    row = {
        "symbol": safe_symbol,
        "date": _epoch_to_date(meta.get("regularMarketTime")),
        "time": _epoch_to_time(meta.get("regularMarketTime")),
        "open": _text(meta.get("regularMarketOpen") or meta.get("chartPreviousClose")),
        "high": _text(meta.get("regularMarketDayHigh")),
        "low": _text(meta.get("regularMarketDayLow")),
        "close": price,
        "price": price,
        "previous_close": previous_close,
        "volume": _text(meta.get("regularMarketVolume")),
        "change": change,
        "change_percent": change_percent,
        "currency": _text(meta.get("currency")),
        "exchange": _text(meta.get("fullExchangeName") or meta.get("exchangeName")),
        "source": YAHOO_SOURCE,
        "provider_id": YAHOO_PROVIDER_ID,
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
            message="Yahoo public quote snapshot normalized; quote is not orderable.",
            symbol=safe_symbol,
        ),
        "quotes": [row],
        "summary": _summary_from_rows([row], symbols=[safe_symbol]),
        "entry": yahoo_provider_entry_summary(symbol=safe_symbol),
        "cache": {"yahoo": None},
    }


def yahoo_provider_entry_summary(symbol: str = YAHOO_WATCHLIST[0]) -> dict[str, Any]:
    safe_symbol = _safe_symbol(symbol) or YAHOO_WATCHLIST[0]
    return {
        "provider_id": YAHOO_PROVIDER_ID,
        "official_docs": [YAHOO_DOCS_URL],
        "docs_checked_at": YAHOO_DOCS_CHECKED_AT,
        "auth_mode": "public-no-key",
        "rate_limit": "Use bounded, explicit per-symbol chart snapshot requests only; no bulk crawler.",
        "terms_risk": (
            "Yahoo Finance chart is an unofficial public endpoint; rows are delayed/reference "
            "quotes for research context only and must never route orders or reads."
        ),
        "cache_path": _cache_path(safe_symbol),
        "ttl_seconds": YAHOO_TTL_SECONDS,
        "schema": "v8/finance/chart meta -> bounded delayed/reference quote snapshot rows",
        "fallback": "Show last local snapshot cache or explicit unavailable state; never use fixture quotes.",
        "safety_class": "public_read_only_market_data",
    }


def _coerce_yahoo_payload(
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
        status["message"] = message or "Showing last local Yahoo snapshot cache."
        payload["status"] = status
        summary = dict(payload.get("summary") if isinstance(payload.get("summary"), dict) else {})
        row_count = len(payload.get("quotes") if isinstance(payload.get("quotes"), list) else [])
        summary["row_count"] = row_count
        summary["live_count"] = 0
        summary["cached_count"] = row_count
        summary["stale_count"] = row_count if state == "stale_cache" else 0
        summary["unavailable_count"] = 0
        payload["summary"] = summary
        payload.setdefault("entry", yahoo_provider_entry_summary(symbol=symbol))
        payload["cache"] = {"yahoo": None}
        return payload
    return _empty_yahoo_payload(
        state="unavailable" if state == "stale_cache" else state,
        symbol=symbol,
        message=message or "No local Yahoo snapshot cache is available.",
    )


def _empty_yahoo_payload(*, state: str, symbol: str, message: str) -> dict[str, Any]:
    safe_symbol = _safe_symbol(symbol) or YAHOO_WATCHLIST[0]
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
            "source": YAHOO_SOURCE,
            "provider_id": YAHOO_PROVIDER_ID,
            "quote_semantics": "quote_not_orderable",
        },
        "entry": yahoo_provider_entry_summary(symbol=safe_symbol),
        "cache": {"yahoo": None},
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
        "symbol": str(first.get("symbol") or (symbols[0] if symbols else YAHOO_WATCHLIST[0])),
        "symbols": ",".join(symbols),
        "price": str(first.get("price") or ""),
        "change": str(first.get("change") or ""),
        "change_percent": str(first.get("change_percent") or ""),
        "latest_date": str(first.get("date") or ""),
        "latest_time": str(first.get("time") or ""),
        "row_count": len(rows),
        "requested_count": len(symbols),
        **state_counts,
        "source": YAHOO_SOURCE,
        "provider_id": YAHOO_PROVIDER_ID,
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
        return "Yahoo public quote snapshots refreshed; rows are not orderable."
    if state == "partial":
        return "Some Yahoo snapshots refreshed; unavailable rows remain explicit."
    if rows:
        return "Showing local Yahoo snapshot cache; refresh for current public rows."
    return messages[0] if messages else "No Yahoo snapshot cache is available yet."


def _latest_retrieved_at(rows: list[dict[str, Any]]) -> str:
    retrieved = [str(row.get("retrieved_at") or "") for row in rows if row.get("retrieved_at")]
    return max(retrieved) if retrieved else "not refreshed"


def _payload_has_rows(payload: dict[str, Any] | None) -> bool:
    return isinstance(payload, dict) and any(
        isinstance(row, dict) for row in payload.get("quotes", [])
    )


def _status(*, state: str, last_update: str, message: str, symbol: str) -> dict[str, Any]:
    safe_symbol = _safe_symbol(symbol) or YAHOO_WATCHLIST[0]
    return {
        "source": YAHOO_SOURCE,
        "provider_id": YAHOO_PROVIDER_ID,
        "state": state,
        "last_update": last_update,
        "message": message,
        "cache_path": _cache_path(safe_symbol),
        "docs_url": YAHOO_DOCS_URL,
        "symbol": safe_symbol,
        "auth_mode": "no-key",
        "quote_semantics": "quote_not_orderable",
        "live_action_enabled": False,
    }


def _safe_symbol(value: Any) -> str:
    raw = str(value or "").strip().upper().replace("/", "")
    return "".join(ch for ch in raw if ch.isalnum() or ch in {".", "^", "-", "="})[:24]


def _safe_path_part(symbol: str) -> str:
    return "".join(ch for ch in symbol.upper() if ch.isalnum())[:24] or "AAPL"


def _cache_path(symbol: str) -> str:
    return f"market_data/quotes/yahoo/{_safe_path_part(symbol)}.json"


def _text(value: Any) -> str:
    text = str(value if value is not None else "").strip()
    return "" if text.upper() in {"N/D", "NONE"} else text


def _change_fields(previous_close: str, price: str) -> tuple[str, str]:
    prev_decimal = _decimal(previous_close)
    price_decimal = _decimal(price)
    if prev_decimal is None or price_decimal is None:
        return "", ""
    change = price_decimal - prev_decimal
    if prev_decimal == 0:
        return _format_decimal(change), ""
    return _format_decimal(change), _format_decimal(change / prev_decimal * Decimal("100"))


def _decimal(value: Any) -> Decimal | None:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _format_decimal(value: Decimal | None) -> str:
    if value is None:
        return ""
    return str(value.quantize(Decimal("0.0001")).normalize())


def _epoch_to_date(value: Any) -> str:
    moment = _epoch_to_datetime(value)
    return moment.strftime("%Y-%m-%d") if moment else ""


def _epoch_to_time(value: Any) -> str:
    moment = _epoch_to_datetime(value)
    return moment.strftime("%H:%M:%S") if moment else ""


def _epoch_to_datetime(value: Any) -> datetime | None:
    try:
        return datetime.fromtimestamp(int(value), tz=UTC)
    except (TypeError, ValueError, OSError, OverflowError):
        return None


def _utc_now() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
