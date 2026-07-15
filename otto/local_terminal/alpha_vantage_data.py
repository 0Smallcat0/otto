"""Alpha Vantage optional-key equity/ETF quote adapter with local-only credential gates."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode


ALPHA_VANTAGE_PROVIDER_ID = "alphavantage_global_quote_optional_key"
ALPHA_VANTAGE_SOURCE = "alphavantage_global_quote"
ALPHA_VANTAGE_DEFAULT_SYMBOL = "AAPL"
ALPHA_VANTAGE_DEFAULT_ETF_SYMBOL = "SPY"
ALPHA_VANTAGE_STOCK_WATCHLIST = ("AAPL", "MSFT", "NVDA")
ALPHA_VANTAGE_ETF_WATCHLIST = ("SPY", "QQQ", "IWM")
ALPHA_VANTAGE_FX_WATCHLIST = ("EUR/USD", "USD/JPY", "GBP/USD")
ALPHA_VANTAGE_MAX_WATCHLIST = 5
ALPHA_VANTAGE_DOCS_URL = "https://www.alphavantage.co/documentation/"
ALPHA_VANTAGE_TERMS_URL = "https://www.alphavantage.co/terms_of_service/"
ALPHA_VANTAGE_PREMIUM_URL = "https://www.alphavantage.co/premium/"
ALPHA_VANTAGE_DOCS_CHECKED_AT = "2026-05-25"
ALPHA_VANTAGE_CACHE_PATH = (
    f"market_data/equities/alphavantage/global_quote/{ALPHA_VANTAGE_DEFAULT_SYMBOL}.json"
)
ALPHA_VANTAGE_FX_SOURCE = "alphavantage_currency_exchange_rate"
ALPHA_VANTAGE_TTL_SECONDS = 86400
ALPHA_VANTAGE_NOTICE = (
    "User-owned Alpha Vantage API access; default Global Quote data is end-of-day unless "
    "the user has separate market-data entitlement."
)
ALPHA_VANTAGE_FX_NOTICE = (
    "User-owned Alpha Vantage FX access; currency exchange rows are not orderable and "
    "must not be used for live trading without a separate safety contract."
)


class AlphaVantageDataError(ValueError):
    """Raised when Alpha Vantage optional-key quote data cannot be used safely."""


class AlphaVantageRateLimitError(AlphaVantageDataError):
    """Raised when Alpha Vantage returns a rate-limit or entitlement message."""


def alpha_vantage_quote_payload(
    cache: dict[str, Any] | None,
    local_secret_status: dict[str, Any] | None,
    *,
    fetcher: Any | None = None,
    refresh: bool = False,
    credential: str = "",
    symbol: str = ALPHA_VANTAGE_DEFAULT_SYMBOL,
) -> dict[str, Any]:
    """Return optional-key Global Quote data without exposing the local credential."""

    fetcher = fetcher or fetch_alpha_vantage_global_quote
    safe_symbol = _safe_symbol(symbol)
    status = local_secret_status if isinstance(local_secret_status, dict) else {}
    stored_ids = status.get("stored_provider_ids") if isinstance(status.get("stored_provider_ids"), list) else []
    key_stored = ALPHA_VANTAGE_PROVIDER_ID in {str(provider_id) for provider_id in stored_ids}

    if refresh and not key_stored:
        return _coerce_alpha_vantage_payload(
            cache,
            state="key_required",
            symbol=safe_symbol,
            message="Store a local Alpha Vantage key in Settings before refreshing this quote.",
        )

    if refresh:
        if not credential:
            return _coerce_alpha_vantage_payload(
                cache,
                state="key_required",
                symbol=safe_symbol,
                message="The Alpha Vantage provider is configured, but the local key could not be opened.",
            )
        try:
            raw = fetcher(symbol=safe_symbol, credential=credential)
            payload = normalize_alpha_vantage_global_quote(raw, symbol=safe_symbol, state="live")
        except AlphaVantageRateLimitError as exc:
            return _coerce_alpha_vantage_payload(
                cache,
                state="rate_limited",
                symbol=safe_symbol,
                message=f"Alpha Vantage refresh is rate-limited; using local cache if present. {exc}",
            )
        except (
            AlphaVantageDataError,
            OSError,
            TimeoutError,
            urllib.error.URLError,
            json.JSONDecodeError,
        ) as exc:
            return _coerce_alpha_vantage_payload(
                cache,
                state="unavailable",
                symbol=safe_symbol,
                message=(
                    "Alpha Vantage refresh failed without exposing credential material: "
                    f"{exc.__class__.__name__}."
                ),
            )
        return {**payload, "cache": {"alpha_vantage": payload}}

    if cache:
        return _coerce_alpha_vantage_payload(cache, state="stale_cache", symbol=safe_symbol)
    if key_stored:
        return _empty_alpha_vantage_payload(
            state="unavailable",
            symbol=safe_symbol,
            message=(
                "A local Alpha Vantage key is stored; refresh this provider to populate "
                "this quote cache."
            ),
        )
    return _empty_alpha_vantage_payload(
        state="key_required",
        symbol=safe_symbol,
        message="Store a local Alpha Vantage key in Settings before using this optional provider.",
    )


def alpha_vantage_quote_watchlist_payload(
    caches: dict[str, dict[str, Any]] | None,
    local_secret_status: dict[str, Any] | None,
    *,
    fetcher: Any | None = None,
    refresh: bool = False,
    credential: str = "",
    symbols: list[str] | tuple[str, ...] | str | None = None,
    fallback_symbols: tuple[str, ...] = ALPHA_VANTAGE_STOCK_WATCHLIST,
) -> dict[str, Any]:
    """Return a bounded per-symbol Global Quote watchlist payload."""

    safe_symbols = alpha_vantage_symbol_list(symbols, fallback_symbols=fallback_symbols)
    cache_map = caches if isinstance(caches, dict) else {}
    payloads: list[dict[str, Any]] = []
    writable_cache: dict[str, dict[str, Any]] = {}
    for symbol in safe_symbols:
        payload = alpha_vantage_quote_payload(
            cache_map.get(symbol) or {},
            local_secret_status,
            fetcher=fetcher,
            refresh=refresh,
            credential=credential,
            symbol=symbol,
        )
        payloads.append(payload)
        cache = payload.get("cache")
        quote_cache = cache.get("alpha_vantage") if isinstance(cache, dict) else None
        if _cache_is_writable(quote_cache):
            writable_cache[symbol] = quote_cache
    return _combine_quote_payloads(payloads, safe_symbols, writable_cache)


def alpha_vantage_symbol_list(
    symbols: list[str] | tuple[str, ...] | str | None,
    *,
    fallback_symbols: tuple[str, ...] = ALPHA_VANTAGE_STOCK_WATCHLIST,
) -> list[str]:
    raw_symbols: list[Any]
    if isinstance(symbols, str):
        raw_symbols = symbols.replace(";", ",").split(",")
    elif isinstance(symbols, (list, tuple)):
        raw_symbols = list(symbols)
    else:
        raw_symbols = list(fallback_symbols)
    seen: set[str] = set()
    safe_symbols: list[str] = []
    for raw in raw_symbols:
        safe_symbol = _safe_symbol_candidate(raw)
        if not safe_symbol:
            continue
        if safe_symbol in seen:
            continue
        seen.add(safe_symbol)
        safe_symbols.append(safe_symbol)
        if len(safe_symbols) >= ALPHA_VANTAGE_MAX_WATCHLIST:
            break
    if safe_symbols:
        return safe_symbols
    return [_safe_symbol(symbol) for symbol in fallback_symbols[:ALPHA_VANTAGE_MAX_WATCHLIST]]


def alpha_vantage_fx_quote_watchlist_payload(
    caches: dict[str, dict[str, Any]] | None,
    local_secret_status: dict[str, Any] | None,
    *,
    fetcher: Any | None = None,
    refresh: bool = False,
    credential: str = "",
    pairs: list[str] | tuple[str, ...] | str | None = None,
) -> dict[str, Any]:
    """Return a bounded optional-key FX exchange-rate watchlist payload."""

    safe_pairs = alpha_vantage_fx_pair_list(pairs)
    cache_map = caches if isinstance(caches, dict) else {}
    payloads: list[dict[str, Any]] = []
    writable_cache: dict[str, dict[str, Any]] = {}
    for pair in safe_pairs:
        payload = alpha_vantage_fx_quote_payload(
            cache_map.get(_fx_pair_key(pair)) or cache_map.get(pair) or {},
            local_secret_status,
            fetcher=fetcher,
            refresh=refresh,
            credential=credential,
            pair=pair,
        )
        payloads.append(payload)
        cache = payload.get("cache")
        quote_cache = cache.get("alpha_vantage_fx") if isinstance(cache, dict) else None
        if _cache_is_writable_fx(quote_cache):
            writable_cache[_fx_pair_key(pair)] = quote_cache
    return _combine_fx_quote_payloads(payloads, safe_pairs, writable_cache)


def alpha_vantage_fx_quote_payload(
    cache: dict[str, Any] | None,
    local_secret_status: dict[str, Any] | None,
    *,
    fetcher: Any | None = None,
    refresh: bool = False,
    credential: str = "",
    pair: str = "EUR/USD",
) -> dict[str, Any]:
    """Return one Alpha Vantage CURRENCY_EXCHANGE_RATE row without exposing keys."""

    fetcher = fetcher or fetch_alpha_vantage_currency_exchange_rate
    safe_pair = _safe_fx_pair(pair)
    status = local_secret_status if isinstance(local_secret_status, dict) else {}
    stored_ids = status.get("stored_provider_ids") if isinstance(status.get("stored_provider_ids"), list) else []
    key_stored = ALPHA_VANTAGE_PROVIDER_ID in {str(provider_id) for provider_id in stored_ids}

    if refresh and not key_stored:
        return _coerce_alpha_vantage_fx_payload(
            cache,
            state="key_required",
            pair=safe_pair,
            message="Store a local Alpha Vantage key in Settings before refreshing FX quotes.",
        )
    if refresh:
        if not credential:
            return _coerce_alpha_vantage_fx_payload(
                cache,
                state="key_required",
                pair=safe_pair,
                message="The Alpha Vantage provider is configured, but the local key could not be opened.",
            )
        try:
            raw = fetcher(pair=safe_pair, credential=credential)
            payload = normalize_alpha_vantage_currency_exchange_rate(
                raw,
                pair=safe_pair,
                state="live",
            )
        except AlphaVantageRateLimitError as exc:
            return _coerce_alpha_vantage_fx_payload(
                cache,
                state="rate_limited",
                pair=safe_pair,
                message=f"Alpha Vantage FX refresh is rate-limited; using local cache if present. {exc}",
            )
        except (
            AlphaVantageDataError,
            OSError,
            TimeoutError,
            urllib.error.URLError,
            json.JSONDecodeError,
        ) as exc:
            return _coerce_alpha_vantage_fx_payload(
                cache,
                state="unavailable",
                pair=safe_pair,
                message=(
                    "Alpha Vantage FX refresh failed without exposing credential material: "
                    f"{exc.__class__.__name__}."
                ),
            )
        return {**payload, "cache": {"alpha_vantage_fx": payload}}
    if cache:
        return _coerce_alpha_vantage_fx_payload(cache, state="stale_cache", pair=safe_pair)
    if key_stored:
        return _empty_alpha_vantage_fx_payload(
            state="unavailable",
            pair=safe_pair,
            message="A local Alpha Vantage key is stored; refresh this provider to populate FX quotes.",
        )
    return _empty_alpha_vantage_fx_payload(
        state="key_required",
        pair=safe_pair,
        message="Store a local Alpha Vantage key in Settings before using optional FX quotes.",
    )


def alpha_vantage_fx_pair_list(
    pairs: list[str] | tuple[str, ...] | str | None,
) -> list[str]:
    raw_pairs: list[Any]
    if isinstance(pairs, str):
        raw_pairs = pairs.replace(";", ",").split(",")
    elif isinstance(pairs, (list, tuple)):
        raw_pairs = list(pairs)
    else:
        raw_pairs = list(ALPHA_VANTAGE_FX_WATCHLIST)
    seen: set[str] = set()
    safe_pairs: list[str] = []
    for raw in raw_pairs:
        pair = _safe_fx_pair_candidate(raw)
        if not pair or pair in seen:
            continue
        seen.add(pair)
        safe_pairs.append(pair)
        if len(safe_pairs) >= ALPHA_VANTAGE_MAX_WATCHLIST:
            break
    return safe_pairs or list(ALPHA_VANTAGE_FX_WATCHLIST)


def fetch_alpha_vantage_global_quote(
    *,
    symbol: str,
    credential: str,
    timeout: float = 8.0,
) -> dict[str, Any]:
    """Fetch an Alpha Vantage Global Quote payload with a user-owned local key."""

    params = urlencode(
        {
            "function": "GLOBAL_QUOTE",
            "symbol": _safe_symbol(symbol),
            "api" + "key": credential,
        }
    )
    request = urllib.request.Request(
        f"https://www.alphavantage.co/query?{params}",
        headers={"User-Agent": "LocalTerminal/0.1 clean-room local equity research"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            raise AlphaVantageRateLimitError("HTTP 429") from exc
        if exc.code in {400, 401, 403}:
            raise AlphaVantageDataError("Alpha Vantage request rejected; verify the local key and symbol") from exc
        raise AlphaVantageDataError(f"Alpha Vantage request failed with HTTP {exc.code}") from exc
    if not isinstance(payload, dict):
        raise AlphaVantageDataError("Alpha Vantage response must be a JSON object")
    return payload


def fetch_alpha_vantage_currency_exchange_rate(
    *,
    pair: str,
    credential: str,
    timeout: float = 8.0,
) -> dict[str, Any]:
    """Fetch an Alpha Vantage CURRENCY_EXCHANGE_RATE payload with a local key."""

    from_currency, to_currency = _split_fx_pair(pair)
    params = urlencode(
        {
            "function": "CURRENCY_EXCHANGE_RATE",
            "from_currency": from_currency,
            "to_currency": to_currency,
            "api" + "key": credential,
        }
    )
    request = urllib.request.Request(
        f"https://www.alphavantage.co/query?{params}",
        headers={"User-Agent": "LocalTerminal/0.1 clean-room local fx quotes"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            raise AlphaVantageRateLimitError("HTTP 429") from exc
        if exc.code in {400, 401, 403}:
            raise AlphaVantageDataError("Alpha Vantage FX request rejected; verify the local key and pair") from exc
        raise AlphaVantageDataError(f"Alpha Vantage FX request failed with HTTP {exc.code}") from exc
    if not isinstance(payload, dict):
        raise AlphaVantageDataError("Alpha Vantage FX response must be a JSON object")
    return payload


def normalize_alpha_vantage_global_quote(
    raw: dict[str, Any],
    *,
    symbol: str = ALPHA_VANTAGE_DEFAULT_SYMBOL,
    state: str = "live",
    retrieved_at: str | None = None,
) -> dict[str, Any]:
    """Normalize Global Quote into a local quote row."""

    if "quotes" in raw and "status" in raw:
        return _coerce_alpha_vantage_payload(raw, state=state, symbol=symbol)
    if raw.get("Note") or raw.get("Information"):
        message = str(raw.get("Note") or raw.get("Information") or "provider message")
        raise AlphaVantageRateLimitError(_safe_message(message))
    if raw.get("Error Message"):
        raise AlphaVantageDataError("Alpha Vantage returned an error for the requested symbol")
    quote = raw.get("Global Quote")
    if not isinstance(quote, dict):
        raise AlphaVantageDataError("Alpha Vantage response has no Global Quote object")

    updated_at = retrieved_at or _utc_now()
    safe_symbol = _safe_symbol(quote.get("01. symbol") or symbol)
    price = str(quote.get("05. price") or "")
    latest_day = str(quote.get("07. latest trading day") or "")
    if not safe_symbol or not price:
        raise AlphaVantageDataError("Alpha Vantage Global Quote has no usable price")

    row = {
        "symbol": safe_symbol,
        "price": price,
        "open": str(quote.get("02. open") or ""),
        "high": str(quote.get("03. high") or ""),
        "low": str(quote.get("04. low") or ""),
        "volume": str(quote.get("06. volume") or ""),
        "latest_trading_day": latest_day,
        "previous_close": str(quote.get("08. previous close") or ""),
        "change": str(quote.get("09. change") or ""),
        "change_percent": str(quote.get("10. change percent") or ""),
        "source": ALPHA_VANTAGE_SOURCE,
        "provider_id": ALPHA_VANTAGE_PROVIDER_ID,
        "retrieved_at": updated_at,
        "cache_path": _cache_path(safe_symbol),
        "docs_url": ALPHA_VANTAGE_DOCS_URL,
        "auth_mode": "optional-local-key",
        "safety_class": "optional_local_secret_data_provider",
    }
    return {
        "status": _status(
            state=state,
            last_update=updated_at,
            message="Alpha Vantage Global Quote normalized from user-owned local-key access.",
            cache_path=_cache_path(safe_symbol),
            symbol=safe_symbol,
        ),
        "quotes": [row],
        "summary": {
            "symbol": safe_symbol,
            "price": price,
            "change": row["change"],
            "change_percent": row["change_percent"],
            "latest_trading_day": latest_day,
            "row_count": 1,
            "source": ALPHA_VANTAGE_SOURCE,
            "provider_id": ALPHA_VANTAGE_PROVIDER_ID,
        },
        "entry": alpha_vantage_provider_entry_summary(symbol=safe_symbol),
        "cache": {"alpha_vantage": None},
    }


def normalize_alpha_vantage_currency_exchange_rate(
    raw: dict[str, Any],
    *,
    pair: str = "EUR/USD",
    state: str = "live",
    retrieved_at: str | None = None,
) -> dict[str, Any]:
    """Normalize CURRENCY_EXCHANGE_RATE into a non-orderable FX quote row."""

    if "quotes" in raw and "status" in raw:
        return _coerce_alpha_vantage_fx_payload(raw, state=state, pair=pair)
    if raw.get("Note") or raw.get("Information"):
        message = str(raw.get("Note") or raw.get("Information") or "provider message")
        raise AlphaVantageRateLimitError(_safe_message(message))
    if raw.get("Error Message"):
        raise AlphaVantageDataError("Alpha Vantage returned an error for the requested FX pair")
    quote = raw.get("Realtime Currency Exchange Rate")
    if not isinstance(quote, dict):
        raise AlphaVantageDataError("Alpha Vantage response has no FX exchange-rate object")

    updated_at = retrieved_at or _utc_now()
    from_currency = _safe_currency(quote.get("1. From_Currency Code"))
    to_currency = _safe_currency(quote.get("3. To_Currency Code"))
    safe_pair = _safe_fx_pair(f"{from_currency}/{to_currency}" if from_currency and to_currency else pair)
    rate = str(quote.get("5. Exchange Rate") or "")
    if not safe_pair or not rate:
        raise AlphaVantageDataError("Alpha Vantage FX response has no usable exchange rate")

    row = {
        "pair": safe_pair,
        "from_currency": _split_fx_pair(safe_pair)[0],
        "to_currency": _split_fx_pair(safe_pair)[1],
        "from_currency_name": str(quote.get("2. From_Currency Name") or ""),
        "to_currency_name": str(quote.get("4. To_Currency Name") or ""),
        "rate": rate,
        "last_refreshed": str(quote.get("6. Last Refreshed") or ""),
        "time_zone": str(quote.get("7. Time Zone") or ""),
        "bid": str(quote.get("8. Bid Price") or ""),
        "ask": str(quote.get("9. Ask Price") or ""),
        "source": ALPHA_VANTAGE_FX_SOURCE,
        "provider_id": ALPHA_VANTAGE_PROVIDER_ID,
        "retrieved_at": updated_at,
        "cache_path": _fx_cache_path(safe_pair),
        "docs_url": ALPHA_VANTAGE_DOCS_URL,
        "auth_mode": "optional-local-key",
        "quote_semantics": "quote_not_orderable",
        "live_action_enabled": False,
        "safety_class": "optional_local_secret_data_provider",
    }
    return {
        "status": _fx_status(
            state=state,
            last_update=updated_at,
            message=(
                "Alpha Vantage CURRENCY_EXCHANGE_RATE normalized from user-owned "
                "local-key access; quote is not orderable."
            ),
            pair=safe_pair,
        ),
        "quotes": [row],
        "summary": _fx_summary_from_quotes([row], pair=safe_pair),
        "entry": alpha_vantage_fx_provider_entry_summary(pair=safe_pair),
        "cache": {"alpha_vantage_fx": None},
    }


def alpha_vantage_provider_entry_summary(symbol: str = ALPHA_VANTAGE_DEFAULT_SYMBOL) -> dict[str, Any]:
    safe_symbol = _safe_symbol(symbol)
    return {
        "provider_id": ALPHA_VANTAGE_PROVIDER_ID,
        "official_docs": [
            ALPHA_VANTAGE_DOCS_URL,
            ALPHA_VANTAGE_PREMIUM_URL,
            ALPHA_VANTAGE_TERMS_URL,
        ],
        "docs_checked_at": ALPHA_VANTAGE_DOCS_CHECKED_AT,
        "auth_mode": "optional-local-key",
        "rate_limit": "Standard free usage is 25 requests/day; keep a daily local cache.",
        "terms_risk": (
            "User-owned credential, plan-specific entitlements, no bundled key, "
            "and no live trading or broker account use."
        ),
        "cache_path": _cache_path(safe_symbol),
        "ttl_seconds": ALPHA_VANTAGE_TTL_SECONDS,
        "schema": "Global Quote -> single equity or ETF quote row",
        "fallback": "Show last local quote cache or key-required state; never use fixture quotes as runtime data.",
        "safety_class": "optional_local_secret_data_provider",
    }


def alpha_vantage_fx_provider_entry_summary(pair: str = "EUR/USD") -> dict[str, Any]:
    safe_pair = _safe_fx_pair(pair)
    return {
        "provider_id": ALPHA_VANTAGE_PROVIDER_ID,
        "official_docs": [
            ALPHA_VANTAGE_DOCS_URL,
            ALPHA_VANTAGE_PREMIUM_URL,
            ALPHA_VANTAGE_TERMS_URL,
        ],
        "docs_checked_at": ALPHA_VANTAGE_DOCS_CHECKED_AT,
        "auth_mode": "optional-local-key",
        "rate_limit": "Standard free usage is 25 requests/day; keep bounded FX pairs and daily local caches.",
        "terms_risk": (
            "User-owned credential, plan-specific entitlements, no bundled key, "
            "and no live trading or broker account use."
        ),
        "cache_path": _fx_cache_path(safe_pair),
        "ttl_seconds": ALPHA_VANTAGE_TTL_SECONDS,
        "schema": "CURRENCY_EXCHANGE_RATE -> bounded non-orderable FX quote rows",
        "fallback": "Show last local FX quote cache or key-required state; never use fixture FX quotes.",
        "safety_class": "optional_local_secret_data_provider",
    }


def _coerce_alpha_vantage_payload(
    raw: dict[str, Any] | None,
    *,
    state: str,
    symbol: str = ALPHA_VANTAGE_DEFAULT_SYMBOL,
    message: str = "",
) -> dict[str, Any]:
    safe_symbol = _safe_symbol(symbol)
    if isinstance(raw, dict) and "quotes" in raw and "status" in raw:
        payload = dict(raw)
        status = dict(payload.get("status") or {})
        quotes = payload.get("quotes") if isinstance(payload.get("quotes"), list) else []
        if quotes and state == "key_required":
            status["state"] = "stale_cache"
            status["message"] = (
                message or "Showing last local Alpha Vantage cache; store a local key to refresh."
            )
        elif quotes and state == "unavailable":
            status["state"] = "stale_cache"
            status["message"] = message or "Showing last local Alpha Vantage cache after refresh failure."
        elif state in {"rate_limited", "stale_cache"} and quotes:
            status["state"] = state
            status["message"] = message or status.get("message") or "Showing local Alpha Vantage cache."
        else:
            status["state"] = state or status.get("state") or "unavailable"
            if message:
                status["message"] = message
        payload["status"] = status
        payload.setdefault("summary", _summary_from_quotes(quotes, symbol=safe_symbol))
        payload.setdefault("entry", alpha_vantage_provider_entry_summary(symbol=safe_symbol))
        cache_payload = {key: value for key, value in payload.items() if key != "cache"}
        payload["cache"] = {"alpha_vantage": cache_payload if quotes else None}
        return payload
    return _empty_alpha_vantage_payload(state=state, symbol=safe_symbol, message=message)


def _empty_alpha_vantage_payload(*, state: str, symbol: str, message: str) -> dict[str, Any]:
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
            "price": "",
            "change": "",
            "change_percent": "",
            "latest_trading_day": "",
            "row_count": 0,
            "source": ALPHA_VANTAGE_SOURCE,
            "provider_id": ALPHA_VANTAGE_PROVIDER_ID,
        },
        "entry": alpha_vantage_provider_entry_summary(symbol=safe_symbol),
        "cache": {"alpha_vantage": None},
    }


def _coerce_alpha_vantage_fx_payload(
    raw: dict[str, Any] | None,
    *,
    state: str,
    pair: str = "EUR/USD",
    message: str = "",
) -> dict[str, Any]:
    safe_pair = _safe_fx_pair(pair)
    if isinstance(raw, dict) and "quotes" in raw and "status" in raw:
        payload = dict(raw)
        status = dict(payload.get("status") or {})
        quotes = payload.get("quotes") if isinstance(payload.get("quotes"), list) else []
        if quotes and state == "key_required":
            status["state"] = "stale_cache"
            status["message"] = message or "Showing last local Alpha Vantage FX cache; store a local key to refresh."
        elif quotes and state == "unavailable":
            status["state"] = "stale_cache"
            status["message"] = message or "Showing last local Alpha Vantage FX cache after refresh failure."
        elif state in {"rate_limited", "stale_cache"} and quotes:
            status["state"] = state
            status["message"] = message or status.get("message") or "Showing local Alpha Vantage FX cache."
        else:
            status["state"] = state or status.get("state") or "unavailable"
            if message:
                status["message"] = message
        payload["status"] = status
        payload.setdefault("summary", _fx_summary_from_quotes(quotes, pair=safe_pair))
        payload.setdefault("entry", alpha_vantage_fx_provider_entry_summary(pair=safe_pair))
        cache_payload = {key: value for key, value in payload.items() if key != "cache"}
        payload["cache"] = {"alpha_vantage_fx": cache_payload if quotes else None}
        return payload
    return _empty_alpha_vantage_fx_payload(state=state, pair=safe_pair, message=message)


def _empty_alpha_vantage_fx_payload(*, state: str, pair: str, message: str) -> dict[str, Any]:
    safe_pair = _safe_fx_pair(pair)
    return {
        "status": _fx_status(
            state=state,
            last_update="not refreshed",
            message=message,
            pair=safe_pair,
        ),
        "quotes": [],
        "summary": {
            "pair": safe_pair,
            "pairs": safe_pair,
            "rate": "",
            "bid": "",
            "ask": "",
            "last_refreshed": "",
            "row_count": 0,
            "requested_count": 1,
            "source": ALPHA_VANTAGE_FX_SOURCE,
            "provider_id": ALPHA_VANTAGE_PROVIDER_ID,
        },
        "entry": alpha_vantage_fx_provider_entry_summary(pair=safe_pair),
        "cache": {"alpha_vantage_fx": None},
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
        "source": ALPHA_VANTAGE_SOURCE,
        "state": state,
        "last_update": last_update,
        "message": message,
        "provider_id": ALPHA_VANTAGE_PROVIDER_ID,
        "cache_path": cache_path,
        "docs_url": ALPHA_VANTAGE_DOCS_URL,
        "terms_url": ALPHA_VANTAGE_TERMS_URL,
        "premium_url": ALPHA_VANTAGE_PREMIUM_URL,
        "auth_mode": "optional-local-key",
        "safety_class": "optional_local_secret_data_provider",
        "symbol": symbol,
        "notice": ALPHA_VANTAGE_NOTICE,
    }


def _fx_status(
    *,
    state: str,
    last_update: str,
    message: str,
    pair: str,
) -> dict[str, Any]:
    safe_pair = _safe_fx_pair(pair)
    return {
        "source": ALPHA_VANTAGE_FX_SOURCE,
        "state": state,
        "last_update": last_update,
        "message": message,
        "provider_id": ALPHA_VANTAGE_PROVIDER_ID,
        "cache_path": _fx_cache_path(safe_pair),
        "docs_url": ALPHA_VANTAGE_DOCS_URL,
        "terms_url": ALPHA_VANTAGE_TERMS_URL,
        "premium_url": ALPHA_VANTAGE_PREMIUM_URL,
        "auth_mode": "optional-local-key",
        "safety_class": "optional_local_secret_data_provider",
        "pair": safe_pair,
        "quote_semantics": "quote_not_orderable",
        "live_action_enabled": False,
        "notice": ALPHA_VANTAGE_FX_NOTICE,
    }


def _summary_from_quotes(
    quotes: list[Any],
    *,
    symbol: str = ALPHA_VANTAGE_DEFAULT_SYMBOL,
) -> dict[str, Any]:
    safe_symbol = _safe_symbol(symbol)
    quote = quotes[0] if quotes and isinstance(quotes[0], dict) else {}
    return {
        "symbol": str(quote.get("symbol") or safe_symbol),
        "price": str(quote.get("price") or ""),
        "change": str(quote.get("change") or ""),
        "change_percent": str(quote.get("change_percent") or ""),
        "latest_trading_day": str(quote.get("latest_trading_day") or ""),
        "row_count": len([item for item in quotes if isinstance(item, dict)]),
        "source": ALPHA_VANTAGE_SOURCE,
        "provider_id": ALPHA_VANTAGE_PROVIDER_ID,
    }


def _fx_summary_from_quotes(
    quotes: list[Any],
    *,
    pair: str = "EUR/USD",
) -> dict[str, Any]:
    safe_pair = _safe_fx_pair(pair)
    quote = quotes[0] if quotes and isinstance(quotes[0], dict) else {}
    return {
        "pair": str(quote.get("pair") or safe_pair),
        "pairs": str(quote.get("pair") or safe_pair),
        "rate": str(quote.get("rate") or ""),
        "bid": str(quote.get("bid") or ""),
        "ask": str(quote.get("ask") or ""),
        "last_refreshed": str(quote.get("last_refreshed") or ""),
        "row_count": len([item for item in quotes if isinstance(item, dict)]),
        "requested_count": 1,
        "source": ALPHA_VANTAGE_FX_SOURCE,
        "provider_id": ALPHA_VANTAGE_PROVIDER_ID,
    }


def _combine_quote_payloads(
    payloads: list[dict[str, Any]],
    symbols: list[str],
    writable_cache: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    quotes: list[dict[str, Any]] = []
    states: list[str] = []
    messages: list[str] = []
    retrieved_at = "not refreshed"
    cache_paths: list[str] = []
    for payload in payloads:
        status = payload.get("status") if isinstance(payload.get("status"), dict) else {}
        state = str(status.get("state") or "unavailable")
        states.append(state)
        message = str(status.get("message") or "")
        if message:
            messages.append(message)
        last_update = str(status.get("last_update") or "")
        if last_update and last_update not in {"not refreshed", "unknown"}:
            retrieved_at = last_update
        cache_path = str(status.get("cache_path") or "")
        if cache_path:
            cache_paths.append(cache_path)
        rows = payload.get("quotes") if isinstance(payload.get("quotes"), list) else []
        quotes.extend(row for row in rows if isinstance(row, dict))

    state = _combined_quote_state(states, quotes)
    first_quote = quotes[0] if quotes else {}
    first_symbol = str(first_quote.get("symbol") or (symbols[0] if symbols else ALPHA_VANTAGE_DEFAULT_SYMBOL))
    summary = _summary_from_quotes(quotes, symbol=first_symbol)
    summary.update(
        {
            "symbol": first_symbol,
            "symbols": ",".join(symbols),
            "requested_count": len(symbols),
            "row_count": len(quotes),
            "cached_count": len(writable_cache) if writable_cache else len(quotes),
            "live_count": states.count("live"),
            "stale_count": states.count("stale_cache"),
            "key_required_count": states.count("key_required"),
            "rate_limited_count": states.count("rate_limited"),
            "unavailable_count": states.count("unavailable"),
        }
    )
    status = _status(
        state=state,
        last_update=retrieved_at,
        message=_combined_quote_message(state, summary, messages),
        cache_path=cache_paths[0] if cache_paths else _cache_path(first_symbol),
        symbol=first_symbol,
    )
    status["symbols"] = list(symbols)
    status["cache_paths"] = cache_paths
    return {
        "status": status,
        "quotes": quotes,
        "summary": summary,
        "entry": {
            **alpha_vantage_provider_entry_summary(symbol=first_symbol),
            "schema": "Global Quote -> bounded equity/ETF quote watchlist rows",
            "watchlist_symbols": list(symbols),
            "max_watchlist": ALPHA_VANTAGE_MAX_WATCHLIST,
        },
        "cache": {"alpha_vantage_by_symbol": writable_cache},
    }


def _combine_fx_quote_payloads(
    payloads: list[dict[str, Any]],
    pairs: list[str],
    writable_cache: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    quotes: list[dict[str, Any]] = []
    states: list[str] = []
    messages: list[str] = []
    retrieved_at = "not refreshed"
    cache_paths: list[str] = []
    for payload in payloads:
        status = payload.get("status") if isinstance(payload.get("status"), dict) else {}
        state = str(status.get("state") or "unavailable")
        states.append(state)
        message = str(status.get("message") or "")
        if message:
            messages.append(message)
        last_update = str(status.get("last_update") or "")
        if last_update and last_update not in {"not refreshed", "unknown"}:
            retrieved_at = last_update
        cache_path = str(status.get("cache_path") or "")
        if cache_path:
            cache_paths.append(cache_path)
        rows = payload.get("quotes") if isinstance(payload.get("quotes"), list) else []
        quotes.extend(row for row in rows if isinstance(row, dict))

    state = _combined_quote_state(states, quotes)
    first_quote = quotes[0] if quotes else {}
    first_pair = str(first_quote.get("pair") or (pairs[0] if pairs else "EUR/USD"))
    summary = _fx_summary_from_quotes(quotes, pair=first_pair)
    summary.update(
        {
            "pair": first_pair,
            "pairs": ",".join(pairs),
            "requested_count": len(pairs),
            "row_count": len(quotes),
            "cached_count": len(writable_cache) if writable_cache else len(quotes),
            "live_count": states.count("live"),
            "stale_count": states.count("stale_cache"),
            "key_required_count": states.count("key_required"),
            "rate_limited_count": states.count("rate_limited"),
            "unavailable_count": states.count("unavailable"),
        }
    )
    status = _fx_status(
        state=state,
        last_update=retrieved_at,
        message=_combined_fx_quote_message(state, summary, messages),
        pair=first_pair,
    )
    status["pairs"] = list(pairs)
    status["cache_paths"] = cache_paths
    return {
        "status": status,
        "quotes": quotes,
        "summary": summary,
        "entry": {
            **alpha_vantage_fx_provider_entry_summary(pair=first_pair),
            "watchlist_pairs": list(pairs),
            "max_watchlist": ALPHA_VANTAGE_MAX_WATCHLIST,
        },
        "cache": {"alpha_vantage_fx_by_pair": writable_cache},
    }


def _combined_quote_state(states: list[str], quotes: list[dict[str, Any]]) -> str:
    if "live" in states:
        return "live"
    if "stale_cache" in states and quotes:
        return "stale_cache"
    if "rate_limited" in states:
        return "rate_limited"
    if states and all(state == "key_required" for state in states):
        return "key_required"
    if quotes:
        return "stale_cache"
    return states[0] if states else "unavailable"


def _combined_quote_message(
    state: str,
    summary: dict[str, Any],
    messages: list[str],
) -> str:
    row_count = int(summary.get("row_count") or 0)
    requested = int(summary.get("requested_count") or 0)
    symbols = str(summary.get("symbols") or "")
    if state == "live":
        return f"Alpha Vantage watchlist refreshed for {row_count}/{requested} symbols: {symbols}."
    if state == "stale_cache":
        return f"Showing local Alpha Vantage watchlist cache for {row_count}/{requested} symbols: {symbols}."
    if state == "key_required":
        return "Store a local Alpha Vantage key in Settings before refreshing this quote watchlist."
    if state == "rate_limited":
        return "Alpha Vantage watchlist refresh is rate-limited; keep local cache and retry later."
    return messages[0] if messages else "Alpha Vantage watchlist is unavailable."


def _combined_fx_quote_message(
    state: str,
    summary: dict[str, Any],
    messages: list[str],
) -> str:
    row_count = int(summary.get("row_count") or 0)
    requested = int(summary.get("requested_count") or 0)
    pairs = str(summary.get("pairs") or "")
    if state == "live":
        return f"Alpha Vantage FX watchlist refreshed for {row_count}/{requested} pairs: {pairs}."
    if state == "stale_cache":
        return f"Showing local Alpha Vantage FX cache for {row_count}/{requested} pairs: {pairs}."
    if state == "key_required":
        return "Store a local Alpha Vantage key in Settings before refreshing this FX watchlist."
    if state == "rate_limited":
        return "Alpha Vantage FX watchlist refresh is rate-limited; keep local cache and retry later."
    return messages[0] if messages else "Alpha Vantage FX watchlist is unavailable."


def _cache_is_writable(value: Any) -> bool:
    return isinstance(value, dict) and isinstance(value.get("quotes"), list)


def _cache_is_writable_fx(value: Any) -> bool:
    return isinstance(value, dict) and isinstance(value.get("quotes"), list)


def _safe_symbol(raw: Any) -> str:
    value = _safe_symbol_candidate(raw)
    return value or ALPHA_VANTAGE_DEFAULT_SYMBOL


def _safe_symbol_candidate(raw: Any) -> str:
    value = "".join(ch for ch in str(raw or "").upper() if ch.isalnum() or ch in {".", "-", "^"})
    return value[:24]


def _safe_fx_pair(raw: Any) -> str:
    return _safe_fx_pair_candidate(raw) or "EUR/USD"


def _safe_fx_pair_candidate(raw: Any) -> str:
    value = str(raw or "").upper().strip().replace("-", "/")
    if "/" not in value:
        compact = "".join(ch for ch in value if ch.isalpha())
        if len(compact) == 6:
            value = f"{compact[:3]}/{compact[3:]}"
    left, _, right = value.partition("/")
    from_currency = _safe_currency(left)
    to_currency = _safe_currency(right)
    if not from_currency or not to_currency or from_currency == to_currency:
        return ""
    return f"{from_currency}/{to_currency}"


def _safe_currency(raw: Any) -> str:
    value = "".join(ch for ch in str(raw or "").upper() if ch.isalpha())
    return value[:8] if 2 <= len(value) <= 8 else ""


def _split_fx_pair(pair: str) -> tuple[str, str]:
    safe_pair = _safe_fx_pair(pair)
    left, _, right = safe_pair.partition("/")
    return left, right


def _cache_path(symbol: str) -> str:
    return f"market_data/equities/alphavantage/global_quote/{_safe_symbol(symbol)}.json"


def _fx_pair_key(pair: str) -> str:
    from_currency, to_currency = _split_fx_pair(pair)
    return f"{from_currency}{to_currency}"


def _fx_cache_path(pair: str) -> str:
    return f"market_data/fx/alphavantage/currency_exchange/{_fx_pair_key(pair)}.json"


def _safe_message(raw: str) -> str:
    return raw.replace("\n", " ").replace("\r", " ")[:240]


def _utc_now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
