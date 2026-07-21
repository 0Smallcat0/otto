"""Nasdaq Trader public symbol-directory adapter."""

from __future__ import annotations

import csv
import ssl
from collections import Counter
from datetime import UTC, datetime
from io import StringIO
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


NASDAQ_TRADER_PROVIDER_ID = "nasdaq_trader_symbol_directory_public"
NASDAQ_TRADER_SOURCE = "nasdaq_trader_symbol_directory"
NASDAQ_TRADER_DOCS_URL = "https://www.nasdaqtrader.com/trader.aspx?id=symboldirdefs"
NASDAQ_TRADER_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"
NASDAQ_TRADER_OTHER_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt"
NASDAQ_TRADER_DOCS_CHECKED_AT = "2026-05-26"
NASDAQ_TRADER_CACHE_PATH = "market_data/reference/nasdaq_trader/symbol_directory.json"
NASDAQ_TRADER_TTL_SECONDS = 86400
NASDAQ_TRADER_MAX_ROWS = 20000
NASDAQ_TRADER_DEFAULT_SEARCH_QUERY = "AAPL"
NASDAQ_TRADER_DEFAULT_SEARCH_LIMIT = 12
NASDAQ_TRADER_MAX_SEARCH_LIMIT = 25
NASDAQ_TRADER_NOTICE = (
    "Nasdaq Trader symbol-directory rows are reference identifiers only, not quotes, "
    "balances, broker availability, or executable market data."
)


class NasdaqTraderDataError(ValueError):
    """Raised when Nasdaq Trader symbol-directory rows cannot be normalized."""


def nasdaq_trader_symbol_directory_payload(
    cache: dict[str, Any] | None,
    *,
    fetcher: Any | None = None,
    refresh: bool = False,
) -> dict[str, Any]:
    """Return public no-key Nasdaq Trader symbol-directory reference data."""

    fetcher = fetcher or fetch_nasdaq_trader_symbol_directory
    if refresh:
        try:
            payload = normalize_nasdaq_trader_symbol_directory(
                fetcher(),
                state="live",
            )
        except (
            NasdaqTraderDataError,
            OSError,
            TimeoutError,
            URLError,
            HTTPError,
            csv.Error,
        ) as exc:
            return _coerce_payload(
                cache,
                state="stale_cache",
                message=(
                    "Nasdaq Trader symbol-directory refresh failed; using local "
                    f"cache if present. {exc.__class__.__name__}."
                ),
            )
        return {**payload, "cache": {"nasdaq_trader": _cache_payload(payload)}}
    if cache:
        return _coerce_payload(cache, state="stale_cache")
    return _empty_payload(
        state="unavailable",
        message="No Nasdaq Trader symbol-directory cache is available yet.",
    )


def fetch_nasdaq_trader_symbol_directory(timeout: float = 8.0) -> dict[str, str]:
    """Fetch bounded official Nasdaq Trader symbol-directory text files."""

    return {
        "nasdaqlisted.txt": _fetch_text(NASDAQ_TRADER_LISTED_URL, timeout=timeout),
        "otherlisted.txt": _fetch_text(NASDAQ_TRADER_OTHER_URL, timeout=timeout),
    }


def normalize_nasdaq_trader_symbol_directory(
    raw: dict[str, Any],
    *,
    state: str = "live",
    retrieved_at: str | None = None,
) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise NasdaqTraderDataError("Nasdaq Trader payload must be a mapping of file names to text")
    retrieved_at = retrieved_at or _utc_now()
    listed_text = str(raw.get("nasdaqlisted.txt") or raw.get("nasdaq") or "")
    other_text = str(raw.get("otherlisted.txt") or raw.get("other") or "")
    listed_rows, listed_created_at, listed_test_count = _parse_listed_rows(
        listed_text,
        retrieved_at=retrieved_at,
    )
    other_rows, other_created_at, other_test_count = _parse_other_rows(
        other_text,
        retrieved_at=retrieved_at,
    )
    rows = [*listed_rows, *other_rows][:NASDAQ_TRADER_MAX_ROWS]
    if not rows:
        raise NasdaqTraderDataError("Nasdaq Trader symbol directory returned no usable rows")
    summary = _summary(
        rows,
        listed_created_at=listed_created_at,
        other_created_at=other_created_at,
        listed_test_count=listed_test_count,
        other_test_count=other_test_count,
    )
    return {
        "status": _status(
            state=state,
            last_update=retrieved_at,
            message="Nasdaq Trader public symbol directory normalized as reference data.",
        ),
        "symbols": rows,
        "summary": summary,
        "entry": nasdaq_trader_provider_entry_summary(),
        "cache": {"nasdaq_trader": None},
    }


def nasdaq_trader_provider_entry_summary() -> dict[str, Any]:
    return {
        "provider_id": NASDAQ_TRADER_PROVIDER_ID,
        "official_docs": [
            NASDAQ_TRADER_DOCS_URL,
            NASDAQ_TRADER_LISTED_URL,
            NASDAQ_TRADER_OTHER_URL,
        ],
        "docs_checked_at": NASDAQ_TRADER_DOCS_CHECKED_AT,
        "auth_mode": "public-no-key",
        "rate_limit": "Use daily local cache and the two official downloadable text files only.",
        "terms_risk": (
            "Symbol-directory data is reference metadata. Preserve Nasdaq Trader "
            "attribution and do not represent rows as quotes or tradable inventory."
        ),
        "cache_path": NASDAQ_TRADER_CACHE_PATH,
        "ttl_seconds": NASDAQ_TRADER_TTL_SECONDS,
        "schema": "nasdaqlisted.txt + otherlisted.txt pipe-delimited symbol directory rows",
        "fallback": "Show last local symbol-directory cache or explicit unavailable state.",
        "safety_class": "public_read_only_reference_data",
    }


def nasdaq_trader_symbol_search_payload(
    cache: dict[str, Any] | None,
    *,
    query: str = NASDAQ_TRADER_DEFAULT_SEARCH_QUERY,
    limit: int = NASDAQ_TRADER_DEFAULT_SEARCH_LIMIT,
) -> dict[str, Any]:
    """Search local Nasdaq Trader symbol-directory reference rows."""

    payload = (
        _coerce_payload(cache, state="stale_cache")
        if isinstance(cache, dict) and cache.get("symbols")
        else _empty_payload(
            state="unavailable",
            message="No local Nasdaq Trader symbol-directory cache is available to search.",
        )
    )
    normalized_query = _search_query(query)
    normalized_limit = _search_limit(limit)
    rows = payload.get("symbols") if isinstance(payload.get("symbols"), list) else []
    matches, total_matches = _search_rows(rows, normalized_query, limit=normalized_limit)
    status = dict(payload.get("status") if isinstance(payload.get("status"), dict) else {})
    if matches:
        status["message"] = (
            f"Found {total_matches} Nasdaq Trader symbol-directory reference rows for "
            f"{normalized_query}."
        )
    elif rows:
        status["message"] = (
            f"No Nasdaq Trader symbol-directory reference rows matched {normalized_query}."
        )
    return {
        "status": status,
        "query": normalized_query,
        "limit": normalized_limit,
        "row_count": len(matches),
        "total_matches": total_matches,
        "rows": matches,
        "source": NASDAQ_TRADER_SOURCE,
        "provider_id": NASDAQ_TRADER_PROVIDER_ID,
        "cache_path": NASDAQ_TRADER_CACHE_PATH,
        "docs_url": NASDAQ_TRADER_DOCS_URL,
        "quote_semantics": "not_quote",
        "live_action_enabled": False,
        "orderable": False,
        "notice": NASDAQ_TRADER_NOTICE,
    }


def _parse_listed_rows(
    text: str,
    *,
    retrieved_at: str,
) -> tuple[list[dict[str, Any]], str, int]:
    rows: list[dict[str, Any]] = []
    file_created_at = _file_creation_time(text)
    test_count = 0
    for row in _pipe_rows(text):
        test_issue = _text(row.get("Test Issue"))
        if test_issue == "Y":
            test_count += 1
            continue
        symbol = _safe_symbol(row.get("Symbol"))
        name = _text(row.get("Security Name"))
        if not symbol or not name:
            continue
        rows.append(
            _row(
                symbol=symbol,
                name=name,
                listing_exchange="NASDAQ",
                market_category=_text(row.get("Market Category")),
                source_file="nasdaqlisted.txt",
                retrieved_at=retrieved_at,
                is_etf=_yes(row.get("ETF")),
                round_lot_size=_text(row.get("Round Lot Size") or row.get("Round Lot")),
                financial_status=_text(row.get("Financial Status")),
                cqs_symbol="",
                nasdaq_symbol=symbol,
            )
        )
    return rows, file_created_at, test_count


def _parse_other_rows(
    text: str,
    *,
    retrieved_at: str,
) -> tuple[list[dict[str, Any]], str, int]:
    rows: list[dict[str, Any]] = []
    file_created_at = _file_creation_time(text)
    test_count = 0
    for row in _pipe_rows(text):
        test_issue = _text(row.get("Test Issue"))
        if test_issue == "Y":
            test_count += 1
            continue
        symbol = _safe_symbol(row.get("ACT Symbol") or row.get("NASDAQ Symbol"))
        name = _text(row.get("Security Name"))
        if not symbol or not name:
            continue
        rows.append(
            _row(
                symbol=symbol,
                name=name,
                listing_exchange=_exchange_name(row.get("Exchange")),
                market_category=_text(row.get("Exchange")),
                source_file="otherlisted.txt",
                retrieved_at=retrieved_at,
                is_etf=_yes(row.get("ETF")),
                round_lot_size=_text(row.get("Round Lot Size")),
                financial_status="",
                cqs_symbol=_safe_symbol(row.get("CQS Symbol")),
                nasdaq_symbol=_safe_symbol(row.get("NASDAQ Symbol")),
            )
        )
    return rows, file_created_at, test_count


def _row(
    *,
    symbol: str,
    name: str,
    listing_exchange: str,
    market_category: str,
    source_file: str,
    retrieved_at: str,
    is_etf: bool,
    round_lot_size: str,
    financial_status: str,
    cqs_symbol: str,
    nasdaq_symbol: str,
) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "name": name,
        "listing_exchange": listing_exchange,
        "market_category": market_category,
        "is_etf": is_etf,
        "round_lot_size": round_lot_size,
        "financial_status": financial_status,
        "cqs_symbol": cqs_symbol,
        "nasdaq_symbol": nasdaq_symbol,
        "source_file": source_file,
        "source": NASDAQ_TRADER_SOURCE,
        "provider_id": NASDAQ_TRADER_PROVIDER_ID,
        "retrieved_at": retrieved_at,
        "cache_path": NASDAQ_TRADER_CACHE_PATH,
        "quote_semantics": "not_quote",
        "live_action_enabled": False,
        "orderable": False,
    }


def _summary(
    rows: list[dict[str, Any]],
    *,
    listed_created_at: str,
    other_created_at: str,
    listed_test_count: int,
    other_test_count: int,
) -> dict[str, Any]:
    source_counts = Counter(str(row.get("source_file") or "") for row in rows)
    exchange_counts = Counter(str(row.get("listing_exchange") or "") for row in rows)
    return {
        "row_count": len(rows),
        "nasdaq_listed_count": source_counts.get("nasdaqlisted.txt", 0),
        "other_listed_count": source_counts.get("otherlisted.txt", 0),
        "etf_count": sum(1 for row in rows if row.get("is_etf") is True),
        "test_issue_count": listed_test_count + other_test_count,
        "exchange_counts": dict(sorted(exchange_counts.items())),
        "file_creation_times": {
            "nasdaqlisted.txt": listed_created_at,
            "otherlisted.txt": other_created_at,
        },
        "source": NASDAQ_TRADER_SOURCE,
        "provider_id": NASDAQ_TRADER_PROVIDER_ID,
        "cache_path": NASDAQ_TRADER_CACHE_PATH,
        "docs_url": NASDAQ_TRADER_DOCS_URL,
        "quote_semantics": "not_quote",
        "notice": NASDAQ_TRADER_NOTICE,
    }


def _coerce_payload(
    cache: dict[str, Any] | None,
    *,
    state: str,
    message: str | None = None,
) -> dict[str, Any]:
    if isinstance(cache, dict) and isinstance(cache.get("symbols"), list):
        payload = dict(cache)
        status = dict(payload.get("status") if isinstance(payload.get("status"), dict) else {})
        status["state"] = state
        status["message"] = message or "Showing last local Nasdaq Trader symbol-directory cache."
        payload["status"] = status
        payload.setdefault("entry", nasdaq_trader_provider_entry_summary())
        payload["cache"] = {"nasdaq_trader": _cache_payload(payload)}
        return payload
    return _empty_payload(
        state="unavailable" if state == "stale_cache" else state,
        message=message or "No local Nasdaq Trader symbol-directory cache is available.",
    )


def _empty_payload(*, state: str, message: str) -> dict[str, Any]:
    return {
        "status": _status(
            state=state,
            last_update="not refreshed",
            message=message,
        ),
        "symbols": [],
        "summary": {
            "row_count": 0,
            "nasdaq_listed_count": 0,
            "other_listed_count": 0,
            "etf_count": 0,
            "test_issue_count": 0,
            "exchange_counts": {},
            "file_creation_times": {},
            "source": NASDAQ_TRADER_SOURCE,
            "provider_id": NASDAQ_TRADER_PROVIDER_ID,
            "cache_path": NASDAQ_TRADER_CACHE_PATH,
            "docs_url": NASDAQ_TRADER_DOCS_URL,
            "quote_semantics": "not_quote",
            "notice": NASDAQ_TRADER_NOTICE,
        },
        "entry": nasdaq_trader_provider_entry_summary(),
        "cache": {"nasdaq_trader": None},
    }


def _cache_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if key != "cache"}


def _status(*, state: str, last_update: str, message: str) -> dict[str, Any]:
    return {
        "source": NASDAQ_TRADER_SOURCE,
        "provider_id": NASDAQ_TRADER_PROVIDER_ID,
        "state": state,
        "last_update": last_update,
        "message": message,
        "cache_path": NASDAQ_TRADER_CACHE_PATH,
        "docs_url": NASDAQ_TRADER_DOCS_URL,
        "auth_mode": "no-key",
        "quote_semantics": "not_quote",
        "live_action_enabled": False,
    }


def _pipe_rows(text: str) -> list[dict[str, str]]:
    if not text.strip():
        return []
    reader = csv.DictReader(StringIO(text), delimiter="|")
    rows: list[dict[str, str]] = []
    for row in reader:
        first_value = next(iter(row.values()), "") if isinstance(row, dict) else ""
        if str(first_value or "").startswith("File Creation Time"):
            continue
        rows.append({str(key): str(value or "") for key, value in row.items() if key})
    return rows


def _file_creation_time(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("File Creation Time"):
            return line.split("|", 1)[0].replace("File Creation Time:", "").strip()
    return ""


def _fetch_text(url: str, *, timeout: float) -> str:
    request = Request(url, headers={"User-Agent": "LocalFinancialTerminal/1.0"})
    with urlopen(request, timeout=timeout, context=_ssl_context()) as response:
        return response.read().decode("utf-8-sig")


def _ssl_context() -> ssl.SSLContext:
    try:
        import certifi
    except ImportError:
        return ssl.create_default_context()
    return ssl.create_default_context(cafile=certifi.where())


def _exchange_name(value: Any) -> str:
    code = _text(value)
    return {
        "A": "NYSE MKT",
        "N": "NYSE",
        "P": "NYSE ARCA",
        "Z": "BATS",
        "V": "IEX",
    }.get(code, code)


def _safe_symbol(value: Any) -> str:
    raw = str(value or "").strip().upper()
    return "".join(ch for ch in raw if ch.isalnum() or ch in {".", "-", "^"})[:24]


def _search_query(value: Any) -> str:
    raw = str(value or "").strip().upper()[:64]
    query = "".join(ch for ch in raw if ch.isalnum() or ch in {".", "-", "^", " ", "&"})
    return " ".join(query.split()) or NASDAQ_TRADER_DEFAULT_SEARCH_QUERY


def _search_limit(value: Any) -> int:
    try:
        limit = int(value)
    except (TypeError, ValueError):
        return NASDAQ_TRADER_DEFAULT_SEARCH_LIMIT
    return max(1, min(limit, NASDAQ_TRADER_MAX_SEARCH_LIMIT))


def _search_rows(
    rows: list[Any],
    query: str,
    *,
    limit: int,
) -> tuple[list[dict[str, Any]], int]:
    query_lower = query.lower()
    scored: list[tuple[int, str, dict[str, Any]]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        symbol = str(row.get("symbol") or "").upper()
        name = str(row.get("name") or "")
        cqs_symbol = str(row.get("cqs_symbol") or "").upper()
        nasdaq_symbol = str(row.get("nasdaq_symbol") or "").upper()
        haystack = " ".join([symbol, cqs_symbol, nasdaq_symbol, name]).lower()
        if query_lower not in haystack:
            continue
        score = 40
        reason = "name_contains"
        if symbol == query:
            score = 0
            reason = "symbol_exact"
        elif query in (cqs_symbol, nasdaq_symbol):
            score = 1
            reason = "alternate_symbol_exact"
        elif symbol.startswith(query):
            score = 2
            reason = "symbol_prefix"
        elif query_lower in symbol.lower():
            score = 3
            reason = "symbol_contains"
        scored.append((score, symbol, _search_row(row, match_reason=reason)))
    scored.sort(key=lambda item: (item[0], item[1]))
    matches = [row for _, _, row in scored[:limit]]
    return matches, len(scored)


def _search_row(row: dict[str, Any], *, match_reason: str) -> dict[str, Any]:
    return {
        "symbol": str(row.get("symbol") or ""),
        "name": str(row.get("name") or ""),
        "listing_exchange": str(row.get("listing_exchange") or ""),
        "market_category": str(row.get("market_category") or ""),
        "is_etf": bool(row.get("is_etf", False)),
        "cqs_symbol": str(row.get("cqs_symbol") or ""),
        "nasdaq_symbol": str(row.get("nasdaq_symbol") or ""),
        "source_file": str(row.get("source_file") or ""),
        "source": str(row.get("source") or NASDAQ_TRADER_SOURCE),
        "provider_id": str(row.get("provider_id") or NASDAQ_TRADER_PROVIDER_ID),
        "retrieved_at": str(row.get("retrieved_at") or ""),
        "cache_path": str(row.get("cache_path") or NASDAQ_TRADER_CACHE_PATH),
        "quote_semantics": str(row.get("quote_semantics") or "not_quote"),
        "live_action_enabled": False,
        "orderable": False,
        "match_reason": match_reason,
    }


def _yes(value: Any) -> bool:
    return _text(value).upper() == "Y"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _utc_now() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
