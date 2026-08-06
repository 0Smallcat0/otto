"""OpenFIGI public identifier-mapping adapter."""

from __future__ import annotations

import json
import ssl
from collections import Counter
from datetime import UTC, datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


OPENFIGI_PROVIDER_ID = "openfigi_identifier_mapping_public"
OPENFIGI_SOURCE = "openfigi_v3_mapping"
OPENFIGI_MAPPING_URL = "https://api.openfigi.com/v3/mapping"
OPENFIGI_DOCS_URL = "https://www.openfigi.com/api/documentation"
OPENFIGI_DOCS_CHECKED_AT = "2026-05-27"
OPENFIGI_CACHE_PATH = "market_data/reference/openfigi/mapping.json"
OPENFIGI_TTL_SECONDS = 86400
OPENFIGI_WATCHLIST = ("AAPL", "MSFT", "SPY")
OPENFIGI_MAX_SYMBOLS = 5
OPENFIGI_NOTICE = (
    "OpenFIGI mapping rows are identifier metadata only, not quotes, balances, "
    "broker availability, or executable market data."
)


class OpenFigiDataError(ValueError):
    """Raised when OpenFIGI mapping rows cannot be normalized."""


def openfigi_mapping_payload(
    cache: dict[str, Any] | None,
    *,
    fetcher: Any | None = None,
    refresh: bool = False,
    symbols: list[str] | str | None = None,
) -> dict[str, Any]:
    """Return bounded public OpenFIGI identifier-mapping reference data."""

    safe_symbols = openfigi_symbol_list(symbols)
    fetcher = fetcher or fetch_openfigi_mapping
    if refresh:
        try:
            jobs = openfigi_mapping_jobs(safe_symbols)
            payload = normalize_openfigi_mapping(
                fetcher(jobs),
                requested_symbols=safe_symbols,
                state="live",
            )
        except (
            OpenFigiDataError,
            OSError,
            TimeoutError,
            URLError,
            HTTPError,
            json.JSONDecodeError,
        ) as exc:
            return _coerce_payload(
                cache,
                state="stale_cache",
                symbols=safe_symbols,
                message=(
                    "OpenFIGI mapping refresh failed; using local cache if present. "
                    f"{exc.__class__.__name__}."
                ),
            )
        return {**payload, "cache": {"openfigi": _cache_payload(payload)}}
    if cache:
        return _coerce_payload(cache, state="stale_cache")
    return _empty_payload(
        state="unavailable",
        symbols=safe_symbols,
        message="No OpenFIGI mapping cache is available yet.",
    )


def fetch_openfigi_mapping(
    jobs: list[dict[str, Any]],
    timeout: float = 8.0,
) -> list[dict[str, Any]]:
    """Fetch bounded OpenFIGI v3 mapping jobs without an API key."""

    if not jobs:
        raise OpenFigiDataError("OpenFIGI mapping requires at least one job")
    data = json.dumps(jobs, separators=(",", ":")).encode("utf-8")
    request = Request(
        OPENFIGI_MAPPING_URL,
        data=data,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "LocalFinancialTerminal/1.0",
        },
        method="POST",
    )
    with urlopen(request, timeout=timeout, context=_ssl_context()) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, list):
        raise OpenFigiDataError("OpenFIGI mapping response must be a list")
    return payload


def normalize_openfigi_mapping(
    raw: list[Any],
    *,
    requested_symbols: list[str] | None = None,
    state: str = "live",
    retrieved_at: str | None = None,
) -> dict[str, Any]:
    if not isinstance(raw, list):
        raise OpenFigiDataError("OpenFIGI mapping payload must be a list")
    retrieved_at = retrieved_at or _utc_now()
    safe_symbols = openfigi_symbol_list(requested_symbols or list(OPENFIGI_WATCHLIST))
    rows: list[dict[str, Any]] = []
    unmatched = 0
    warning_counts: Counter[str] = Counter()
    for index, result in enumerate(raw[: len(safe_symbols)]):
        if not isinstance(result, dict):
            unmatched += 1
            warning_counts["invalid_result"] += 1
            continue
        request_symbol = safe_symbols[index] if index < len(safe_symbols) else ""
        data_rows = result.get("data") if isinstance(result.get("data"), list) else []
        if not data_rows:
            unmatched += 1
            warning = str(result.get("warning") or result.get("error") or "no_data")
            warning_counts[warning[:64]] += 1
            continue
        for data_row in data_rows[:3]:
            if isinstance(data_row, dict):
                row = _mapping_row(
                    data_row,
                    request_symbol=request_symbol,
                    retrieved_at=retrieved_at,
                )
                if row["figi"] or row["ticker"]:
                    rows.append(row)
    if not rows:
        raise OpenFigiDataError("OpenFIGI mapping returned no usable rows")
    return {
        "status": _status(
            state=state,
            last_update=retrieved_at,
            message="OpenFIGI public mapping normalized as reference identifier data.",
            symbol=safe_symbols[0],
        ),
        "mappings": rows,
        "summary": _summary(
            rows,
            requested_symbols=safe_symbols,
            unmatched_count=unmatched,
            warning_counts=warning_counts,
        ),
        "entry": openfigi_provider_entry_summary(),
        "cache": {"openfigi": None},
    }


def openfigi_provider_entry_summary() -> dict[str, Any]:
    return {
        "provider_id": OPENFIGI_PROVIDER_ID,
        # OPENFIGI_MAPPING_URL is the POST endpoint this module calls; opened
        # in a browser it answers 405, so it is not documentation.
        "official_docs": [OPENFIGI_DOCS_URL],
        "docs_checked_at": OPENFIGI_DOCS_CHECKED_AT,
        "auth_mode": "public-no-key",
        "rate_limit": (
            "Use bounded v3 mapping batches and daily local cache; unauthenticated "
            "requests have the lower OpenFIGI public rate limit."
        ),
        "terms_risk": (
            "OpenFIGI returns identifier/reference metadata. Preserve attribution and "
            "do not represent mapping rows as quotes or tradable inventory."
        ),
        "cache_path": OPENFIGI_CACHE_PATH,
        "ttl_seconds": OPENFIGI_TTL_SECONDS,
        "schema": "OpenFIGI v3 mapping jobs using TICKER idType and US exchCode",
        "fallback": "Show last local OpenFIGI mapping cache or explicit unavailable state.",
        "safety_class": "public_read_only_reference_data",
    }


def openfigi_symbol_list(symbols: list[str] | str | None = None) -> list[str]:
    raw_symbols: list[Any]
    if symbols is None:
        raw_symbols = list(OPENFIGI_WATCHLIST)
    elif isinstance(symbols, str):
        raw_symbols = [part.strip() for part in symbols.split(",")]
    elif isinstance(symbols, list):
        raw_symbols = symbols
    else:
        raw_symbols = list(OPENFIGI_WATCHLIST)
    safe: list[str] = []
    for symbol in raw_symbols:
        value = _safe_symbol(symbol)
        if value and value not in safe:
            safe.append(value)
        if len(safe) >= OPENFIGI_MAX_SYMBOLS:
            break
    return safe or list(OPENFIGI_WATCHLIST)


def openfigi_mapping_jobs(symbols: list[str] | str | None = None) -> list[dict[str, Any]]:
    return [
        {
            "idType": "TICKER",
            "idValue": symbol,
            "exchCode": "US",
        }
        for symbol in openfigi_symbol_list(symbols)
    ]


def _mapping_row(
    row: dict[str, Any],
    *,
    request_symbol: str,
    retrieved_at: str,
) -> dict[str, Any]:
    return {
        "request_symbol": request_symbol,
        "ticker": _text(row.get("ticker") or row.get("securityDescription")),
        "name": _text(row.get("name")),
        "figi": _text(row.get("figi")),
        "composite_figi": _text(row.get("compositeFIGI")),
        "share_class_figi": _text(row.get("shareClassFIGI")),
        "exchange_code": _text(row.get("exchCode")),
        "market_sector": _text(row.get("marketSector")),
        "security_type": _text(row.get("securityType")),
        "security_type2": _text(row.get("securityType2")),
        "security_description": _text(row.get("securityDescription")),
        "source": OPENFIGI_SOURCE,
        "provider_id": OPENFIGI_PROVIDER_ID,
        "retrieved_at": retrieved_at,
        "cache_path": OPENFIGI_CACHE_PATH,
        "docs_url": OPENFIGI_DOCS_URL,
        "quote_semantics": "not_quote",
        "live_action_enabled": False,
        "orderable": False,
        "context_only": True,
    }


def _summary(
    rows: list[dict[str, Any]],
    *,
    requested_symbols: list[str],
    unmatched_count: int,
    warning_counts: Counter[str],
) -> dict[str, Any]:
    sector_counts = Counter(str(row.get("market_sector") or "") for row in rows)
    return {
        "row_count": len(rows),
        "requested_count": len(requested_symbols),
        "requested_symbols": ",".join(requested_symbols),
        "matched_symbol_count": len({str(row.get("request_symbol") or "") for row in rows}),
        "unmatched_count": unmatched_count,
        "warning_counts": dict(sorted(warning_counts.items())),
        "sector_counts": dict(sorted(sector_counts.items())),
        "source": OPENFIGI_SOURCE,
        "provider_id": OPENFIGI_PROVIDER_ID,
        "cache_path": OPENFIGI_CACHE_PATH,
        "docs_url": OPENFIGI_DOCS_URL,
        "quote_semantics": "not_quote",
        "notice": OPENFIGI_NOTICE,
    }


def _coerce_payload(
    cache: dict[str, Any] | None,
    *,
    state: str,
    symbols: list[str] | None = None,
    message: str | None = None,
) -> dict[str, Any]:
    if isinstance(cache, dict) and isinstance(cache.get("mappings"), list):
        payload = dict(cache)
        status = dict(payload.get("status") if isinstance(payload.get("status"), dict) else {})
        status["state"] = state
        status["message"] = message or "Showing last local OpenFIGI mapping cache."
        payload["status"] = status
        payload.setdefault("entry", openfigi_provider_entry_summary())
        payload["cache"] = {"openfigi": _cache_payload(payload)}
        return payload
    return _empty_payload(
        state="unavailable" if state == "stale_cache" else state,
        symbols=symbols or list(OPENFIGI_WATCHLIST),
        message=message or "No local OpenFIGI mapping cache is available.",
    )


def _empty_payload(
    *,
    state: str,
    symbols: list[str],
    message: str,
) -> dict[str, Any]:
    return {
        "status": _status(
            state=state,
            last_update="not refreshed",
            message=message,
            symbol=symbols[0] if symbols else OPENFIGI_WATCHLIST[0],
        ),
        "mappings": [],
        "summary": {
            "row_count": 0,
            "requested_count": len(symbols),
            "requested_symbols": ",".join(symbols),
            "matched_symbol_count": 0,
            "unmatched_count": 0,
            "warning_counts": {},
            "sector_counts": {},
            "source": OPENFIGI_SOURCE,
            "provider_id": OPENFIGI_PROVIDER_ID,
            "cache_path": OPENFIGI_CACHE_PATH,
            "docs_url": OPENFIGI_DOCS_URL,
            "quote_semantics": "not_quote",
            "notice": OPENFIGI_NOTICE,
        },
        "entry": openfigi_provider_entry_summary(),
        "cache": {"openfigi": None},
    }


def _cache_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if key != "cache"}


def _status(
    *,
    state: str,
    last_update: str,
    message: str,
    symbol: str,
) -> dict[str, Any]:
    return {
        "source": OPENFIGI_SOURCE,
        "provider_id": OPENFIGI_PROVIDER_ID,
        "state": state,
        "last_update": last_update,
        "message": message,
        "symbol": symbol,
        "cache_path": OPENFIGI_CACHE_PATH,
        "docs_url": OPENFIGI_DOCS_URL,
        "auth_mode": "no-key",
        "quote_semantics": "not_quote",
        "live_action_enabled": False,
    }


def _safe_symbol(value: Any) -> str:
    raw = str(value or "").strip().upper()
    return "".join(ch for ch in raw if ch.isalnum() or ch in {".", "-"})[:16]


def _text(value: Any) -> str:
    return str(value or "").strip()


def _ssl_context() -> ssl.SSLContext:
    try:
        import certifi
    except ImportError:
        return ssl.create_default_context()
    return ssl.create_default_context(cafile=certifi.where())


def _utc_now() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
