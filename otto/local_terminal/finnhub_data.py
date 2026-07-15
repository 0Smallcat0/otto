"""Finnhub optional-key equity quote adapter with local-only credential gates."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode


FINNHUB_PROVIDER_ID = "finnhub_equity_quote_optional_key"
FINNHUB_SOURCE = "finnhub_quote"
FINNHUB_WATCHLIST = ("AAPL", "MSFT", "NVDA", "SPY")
FINNHUB_MAX_WATCHLIST = 5
FINNHUB_DOCS_URL = "https://finnhub.io/docs/api/quote"
FINNHUB_RATE_LIMIT_DOCS_URL = "https://finnhub.io/docs/api/rate-limit"
FINNHUB_DOCS_CHECKED_AT = "2026-05-26"
FINNHUB_TTL_SECONDS = 86400
FINNHUB_NOTICE = (
    "User-owned Finnhub API access; quote rows are non-orderable and must not "
    "be used for live trading without a separate safety contract."
)


class FinnhubError(ValueError):
    """Raised when Finnhub optional-key quote data cannot be used safely."""


class FinnhubRateLimitError(FinnhubError):
    """Raised when Finnhub returns a rate-limit response."""


def finnhub_quote_watchlist_payload(
    caches: dict[str, dict[str, Any]] | None,
    local_secret_status: dict[str, Any] | None,
    *,
    fetcher: Any | None = None,
    refresh: bool = False,
    credential: str = "",
    symbols: list[str] | tuple[str, ...] | str | None = None,
) -> dict[str, Any]:
    """Return a bounded per-symbol Finnhub quote watchlist without secrets."""

    safe_symbols = finnhub_symbol_list(symbols)
    cache_map = caches if isinstance(caches, dict) else {}
    payloads: list[dict[str, Any]] = []
    writable_cache: dict[str, dict[str, Any]] = {}
    for symbol in safe_symbols:
        payload = finnhub_quote_payload(
            cache_map.get(_symbol_key(symbol)) or cache_map.get(symbol) or {},
            local_secret_status,
            fetcher=fetcher,
            refresh=refresh,
            credential=credential,
            symbol=symbol,
        )
        payloads.append(payload)
        cache = payload.get("cache")
        quote_cache = cache.get("finnhub") if isinstance(cache, dict) else None
        if _cache_is_writable(quote_cache):
            writable_cache[_symbol_key(symbol)] = quote_cache
    return _combine_quote_payloads(payloads, safe_symbols, writable_cache)


def finnhub_quote_payload(
    cache: dict[str, Any] | None,
    local_secret_status: dict[str, Any] | None,
    *,
    fetcher: Any | None = None,
    refresh: bool = False,
    credential: str = "",
    symbol: str = FINNHUB_WATCHLIST[0],
) -> dict[str, Any]:
    """Return one Finnhub quote row without exposing the local credential."""

    fetcher = fetcher or fetch_finnhub_quote
    safe_symbol = _safe_symbol(symbol)
    status = local_secret_status if isinstance(local_secret_status, dict) else {}
    stored_ids = status.get("stored_provider_ids") if isinstance(status.get("stored_provider_ids"), list) else []
    key_stored = FINNHUB_PROVIDER_ID in {str(provider_id) for provider_id in stored_ids}

    if refresh and not key_stored:
        return _coerce_finnhub_payload(
            cache,
            state="key_required",
            symbol=safe_symbol,
            message="Store a local Finnhub key in Settings before refreshing equity quotes.",
        )
    if refresh:
        if not credential:
            return _coerce_finnhub_payload(
                cache,
                state="key_required",
                symbol=safe_symbol,
                message="Finnhub is configured, but the local key could not be opened.",
            )
        try:
            raw = fetcher(symbol=safe_symbol, credential=credential)
            payload = normalize_finnhub_quote(raw, symbol=safe_symbol, state="live")
        except FinnhubRateLimitError as exc:
            return _coerce_finnhub_payload(
                cache,
                state="rate_limited",
                symbol=safe_symbol,
                message=f"Finnhub refresh is rate-limited; using local cache if present. {exc}",
            )
        except (
            FinnhubError,
            OSError,
            TimeoutError,
            urllib.error.URLError,
            json.JSONDecodeError,
        ) as exc:
            return _coerce_finnhub_payload(
                cache,
                state="unavailable",
                symbol=safe_symbol,
                message=(
                    "Finnhub refresh failed without exposing credential material: "
                    f"{exc.__class__.__name__}."
                ),
            )
        return {**payload, "cache": {"finnhub": payload}}

    if cache:
        return _coerce_finnhub_payload(cache, state="stale_cache", symbol=safe_symbol)
    if key_stored:
        return _empty_finnhub_payload(
            state="unavailable",
            symbol=safe_symbol,
            message="A local Finnhub key is stored; refresh this provider to populate quotes.",
        )
    return _empty_finnhub_payload(
        state="key_required",
        symbol=safe_symbol,
        message="Store a local Finnhub key in Settings before using this optional provider.",
    )


def finnhub_symbol_list(
    symbols: list[str] | tuple[str, ...] | str | None,
) -> list[str]:
    raw_symbols: list[Any]
    if isinstance(symbols, str):
        raw_symbols = symbols.replace(";", ",").split(",")
    elif isinstance(symbols, (list, tuple)):
        raw_symbols = list(symbols)
    else:
        raw_symbols = list(FINNHUB_WATCHLIST)
    seen: set[str] = set()
    safe_symbols: list[str] = []
    for raw in raw_symbols:
        safe_symbol = _safe_symbol_candidate(raw)
        if not safe_symbol or safe_symbol in seen:
            continue
        seen.add(safe_symbol)
        safe_symbols.append(safe_symbol)
        if len(safe_symbols) >= FINNHUB_MAX_WATCHLIST:
            break
    return safe_symbols or list(FINNHUB_WATCHLIST)


def fetch_finnhub_quote(
    *,
    symbol: str,
    credential: str,
    timeout: float = 8.0,
) -> dict[str, Any]:
    """Fetch a Finnhub /quote payload with a user-owned local key."""

    params = urlencode({"symbol": _safe_symbol(symbol), "token": credential})
    request = urllib.request.Request(
        f"https://finnhub.io/api/v1/quote?{params}",
        headers={"User-Agent": "LocalTerminal/0.1 clean-room equity quotes"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            raise FinnhubRateLimitError("HTTP 429") from exc
        if exc.code in {400, 401, 403}:
            raise FinnhubError("Finnhub request rejected; verify the local key and symbol") from exc
        raise FinnhubError(f"Finnhub request failed with HTTP {exc.code}") from exc
    if not isinstance(payload, dict):
        raise FinnhubError("Finnhub response must be a JSON object")
    return payload


def normalize_finnhub_quote(
    raw: dict[str, Any],
    *,
    symbol: str = FINNHUB_WATCHLIST[0],
    state: str = "live",
    retrieved_at: str | None = None,
) -> dict[str, Any]:
    """Normalize Finnhub /quote into a non-orderable local quote row."""

    if "quotes" in raw and "status" in raw:
        return _coerce_finnhub_payload(raw, state=state, symbol=symbol)
    if raw.get("error"):
        message = _safe_message(str(raw.get("error") or "provider error"))
        if "limit" in message.lower() or "rate" in message.lower():
            raise FinnhubRateLimitError(message)
        raise FinnhubError(message or "Finnhub returned an error")

    updated_at = retrieved_at or _utc_now()
    safe_symbol = _safe_symbol(symbol)
    price = _safe_value(raw.get("c"))
    previous_close = _safe_value(raw.get("pc"))
    if not safe_symbol or (not price and not previous_close):
        raise FinnhubError("Finnhub quote has no usable price")

    row = {
        "symbol": safe_symbol,
        "price": price or previous_close,
        "open": _safe_value(raw.get("o")),
        "high": _safe_value(raw.get("h")),
        "low": _safe_value(raw.get("l")),
        "previous_close": previous_close,
        "change": _safe_value(raw.get("d")),
        "change_percent": _safe_value(raw.get("dp")),
        "timestamp": _safe_value(raw.get("t")),
        "latest_trading_day": _safe_value(raw.get("t")),
        "source": FINNHUB_SOURCE,
        "provider_id": FINNHUB_PROVIDER_ID,
        "retrieved_at": updated_at,
        "cache_path": _cache_path(safe_symbol),
        "docs_url": FINNHUB_DOCS_URL,
        "auth_mode": "optional-local-key",
        "quote_semantics": "quote_not_orderable",
        "live_action_enabled": False,
        "safety_class": "optional_local_secret_data_provider",
    }
    return {
        "status": _status(
            state=state,
            last_update=updated_at,
            message="Finnhub /quote normalized from user-owned local-key access; quote is not orderable.",
            cache_path=_cache_path(safe_symbol),
            symbol=safe_symbol,
        ),
        "quotes": [row],
        "summary": _summary_from_quotes([row], symbol=safe_symbol),
        "entry": finnhub_provider_entry_summary(symbol=safe_symbol),
        "cache": {"finnhub": None},
    }


def finnhub_provider_entry_summary(symbol: str = FINNHUB_WATCHLIST[0]) -> dict[str, Any]:
    safe_symbol = _safe_symbol(symbol)
    return {
        "provider_id": FINNHUB_PROVIDER_ID,
        "official_docs": [FINNHUB_DOCS_URL, FINNHUB_RATE_LIMIT_DOCS_URL],
        "docs_checked_at": FINNHUB_DOCS_CHECKED_AT,
        "auth_mode": "optional-local-key",
        "rate_limit": "Finnhub /quote requires a user token; keep bounded symbols and daily local caches.",
        "terms_risk": (
            "User-owned credential, plan-specific entitlements, no bundled key, "
            "and no live trading or broker account use."
        ),
        "cache_path": _cache_path(safe_symbol),
        "ttl_seconds": FINNHUB_TTL_SECONDS,
        "schema": "/quote -> bounded equity/ETF non-orderable quote rows",
        "fallback": "Show last local quote cache or key-required state; never use fixture quotes.",
        "safety_class": "optional_local_secret_data_provider",
    }


def _combine_quote_payloads(
    payloads: list[dict[str, Any]],
    symbols: list[str],
    writable_cache: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    states: list[str] = []
    messages: list[str] = []
    for payload in payloads:
        status = payload.get("status") if isinstance(payload.get("status"), dict) else {}
        states.append(str(status.get("state") or "unavailable"))
        if status.get("message"):
            messages.append(str(status.get("message")))
        rows.extend(payload.get("quotes") if isinstance(payload.get("quotes"), list) else [])
    state = _combined_state(states, bool(rows))
    first_symbol = symbols[0] if symbols else FINNHUB_WATCHLIST[0]
    summary = _summary_from_quotes(rows, symbol=first_symbol)
    summary.update(
        {
            "symbols": ",".join(symbols),
            "requested_count": len(symbols),
            "cached_count": len(rows),
            "live_count": states.count("live"),
            "stale_count": states.count("stale_cache"),
            "key_required_count": states.count("key_required"),
        }
    )
    status = _status(
        state=state,
        last_update=str(rows[0].get("retrieved_at") or "not refreshed") if rows else "not refreshed",
        message=messages[0] if messages else FINNHUB_NOTICE,
        cache_path=str(rows[0].get("cache_path") or _cache_path(first_symbol)) if rows else _cache_path(first_symbol),
        symbol=first_symbol,
    )
    status["symbols"] = symbols
    return {
        "status": status,
        "quotes": rows,
        "summary": summary,
        "entry": finnhub_provider_entry_summary(symbol=first_symbol),
        "cache": {
            "finnhub": {
                "status": status,
                "quotes": rows,
                "summary": summary,
                "entry": finnhub_provider_entry_summary(symbol=first_symbol),
            }
            if rows
            else None,
            "finnhub_by_symbol": writable_cache,
        },
    }


def _coerce_finnhub_payload(
    raw: dict[str, Any] | None,
    *,
    state: str,
    symbol: str = FINNHUB_WATCHLIST[0],
    message: str = "",
) -> dict[str, Any]:
    safe_symbol = _safe_symbol(symbol)
    if isinstance(raw, dict) and "quotes" in raw and "status" in raw:
        payload = dict(raw)
        status = dict(payload.get("status") or {})
        quotes = payload.get("quotes") if isinstance(payload.get("quotes"), list) else []
        if quotes and state in {"key_required", "unavailable"}:
            status["state"] = "stale_cache"
            status["message"] = message or "Showing last local Finnhub cache."
        elif state in {"rate_limited", "stale_cache"} and quotes:
            status["state"] = state
            status["message"] = message or status.get("message") or "Showing local Finnhub cache."
        else:
            status["state"] = state or status.get("state") or "unavailable"
            if message:
                status["message"] = message
        payload["status"] = status
        payload.setdefault("summary", _summary_from_quotes(quotes, symbol=safe_symbol))
        payload.setdefault("entry", finnhub_provider_entry_summary(symbol=safe_symbol))
        cache_payload = {key: value for key, value in payload.items() if key != "cache"}
        payload["cache"] = {"finnhub": cache_payload if quotes else None}
        return payload
    return _empty_finnhub_payload(state=state, symbol=safe_symbol, message=message)


def _empty_finnhub_payload(*, state: str, symbol: str, message: str) -> dict[str, Any]:
    safe_symbol = _safe_symbol(symbol)
    return {
        "status": _status(
            state=state,
            last_update="not refreshed",
            message=message,
            cache_path=_cache_path(safe_symbol),
            symbol=safe_symbol,
        ),
        "quotes": [],
        "summary": {
            "symbol": safe_symbol,
            "symbols": safe_symbol,
            "price": "",
            "change": "",
            "change_percent": "",
            "latest_trading_day": "",
            "row_count": 0,
            "requested_count": 1,
            "cached_count": 0,
            "live_count": 0,
            "stale_count": 0,
            "key_required_count": 1 if state == "key_required" else 0,
            "source": FINNHUB_SOURCE,
            "provider_id": FINNHUB_PROVIDER_ID,
        },
        "entry": finnhub_provider_entry_summary(symbol=safe_symbol),
        "cache": {"finnhub": None},
    }


def _summary_from_quotes(rows: list[dict[str, Any]], *, symbol: str) -> dict[str, Any]:
    first = rows[0] if rows else {}
    symbols = ",".join(str(row.get("symbol") or "") for row in rows if row.get("symbol"))
    return {
        "symbol": str(first.get("symbol") or symbol),
        "symbols": symbols or symbol,
        "price": str(first.get("price") or ""),
        "change": str(first.get("change") or ""),
        "change_percent": str(first.get("change_percent") or ""),
        "latest_trading_day": str(first.get("latest_trading_day") or ""),
        "row_count": len(rows),
        "source": FINNHUB_SOURCE,
        "provider_id": FINNHUB_PROVIDER_ID,
    }


def _status(
    *,
    state: str,
    last_update: str,
    message: str,
    cache_path: str,
    symbol: str,
) -> dict[str, Any]:
    return {
        "source": FINNHUB_SOURCE,
        "provider_id": FINNHUB_PROVIDER_ID,
        "state": state,
        "last_update": last_update,
        "cache_path": cache_path,
        "docs_url": FINNHUB_DOCS_URL,
        "auth_mode": "optional-local-key",
        "message": message,
        "symbol": _safe_symbol(symbol),
        "quote_semantics": "quote_not_orderable",
        "live_action_enabled": False,
    }


def _combined_state(states: list[str], has_rows: bool) -> str:
    if "live" in states:
        return "live"
    if "stale_cache" in states or has_rows:
        return "stale_cache"
    if "rate_limited" in states:
        return "rate_limited"
    if states and all(state == "key_required" for state in states):
        return "key_required"
    return states[0] if states else "unavailable"


def _cache_is_writable(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    status = payload.get("status")
    status = status if isinstance(status, dict) else {}
    return str(status.get("state") or "") in {"live", "partial", "stale_cache", "stale"}


def _safe_symbol(value: Any) -> str:
    return _safe_symbol_candidate(value) or FINNHUB_WATCHLIST[0]


def _safe_symbol_candidate(value: Any) -> str:
    raw = str(value or "").strip().upper()
    if not raw:
        return ""
    allowed = []
    for char in raw[:20]:
        if char.isalnum() or char in {".", "-", "_"}:
            allowed.append(char)
    symbol = "".join(allowed).strip(".-_")
    if len(symbol) < 1:
        return ""
    return symbol


def _symbol_key(symbol: str) -> str:
    return _safe_path_part(symbol)


def _safe_path_part(value: str) -> str:
    raw = str(value or "").upper()
    safe = "".join(char for char in raw if char.isalnum() or char in {"_", "-"})
    return safe[:32] or "AAPL"


def _cache_path(symbol: str) -> str:
    return f"market_data/quotes/finnhub/{_safe_path_part(symbol)}.json"


def _safe_message(value: str) -> str:
    return " ".join(str(value or "").split())[:240]


def _safe_value(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _utc_now() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
