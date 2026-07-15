"""Public no-key fund and ETF registry provider adapters."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
import gzip
from datetime import UTC, datetime
from typing import Any


DOCS_CHECKED_AT = "2026-05-23"
SEC_ACCESS_DOCS_URL = "https://www.sec.gov/edgar/searchedgar/accessing-edgar-data.htm"
SEC_FUND_TICKERS_URL = "https://www.sec.gov/files/company_tickers_mf.json"
SEC_FUND_CACHE_PATH = "market_data/funds/sec/company_tickers_mf.json"
SEC_FUND_PROVIDER_ID = "sec_fund_ticker_registry_public"
SEC_FUND_TTL_SECONDS = 86400
SEC_USER_AGENT = "LocalTerminal/0.1 local research contact@example.invalid"
DEFAULT_FUND_SYMBOLS = ("QQQ", "VTI", "IVV", "BND", "BNDX", "KWEB")
MAX_FUND_ROWS = 18


class FundDataError(ValueError):
    """Raised when public fund provider data is invalid."""


def fund_data_payload(
    sec_fund_cache: dict[str, Any] | None = None,
    *,
    fetcher: Any | None = None,
    refresh: bool = False,
) -> dict[str, Any]:
    """Return normalized SEC fund ticker registry data with provenance and cache state."""

    fetcher = fetcher or fetch_sec_fund_tickers
    source_errors: list[str] = []
    sec_funds_payload = _coerce_sec_funds_payload(sec_fund_cache, state="stale")

    if refresh:
        try:
            sec_funds_payload = normalize_sec_fund_tickers(fetcher(), state="live")
        except (
            FundDataError,
            OSError,
            TimeoutError,
            urllib.error.URLError,
            json.JSONDecodeError,
        ) as exc:
            source_errors.append(str(exc) or exc.__class__.__name__)

    sec_funds = _sec_funds_section(sec_funds_payload)
    status = dict(sec_funds["status"])
    if source_errors and status["state"] == "unavailable":
        status["message"] = "SEC fund ticker registry refresh failed; no cache is available."
    elif source_errors:
        status["message"] = "SEC fund ticker registry refresh failed; using the last local cache."
    status["source_errors"] = source_errors
    return {
        "status": status,
        "sec_funds": sec_funds,
        "provider_entry": provider_entry_summary(),
        "cache": {"sec_funds": sec_funds_payload},
    }


def fetch_sec_fund_tickers(timeout: float = 8.0) -> dict[str, Any]:
    """Fetch the SEC fund ticker mapping JSON file."""

    request = urllib.request.Request(
        SEC_FUND_TICKERS_URL,
        headers={
            "User-Agent": SEC_USER_AGENT,
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = _read_json_response(response)
    if not isinstance(payload, dict):
        raise FundDataError("SEC fund ticker registry response must be an object")
    return payload


def normalize_sec_fund_tickers(
    raw: dict[str, Any],
    *,
    state: str = "live",
    retrieved_at: str | None = None,
    symbols: tuple[str, ...] = DEFAULT_FUND_SYMBOLS,
) -> dict[str, Any]:
    """Normalize SEC fund ticker arrays into route-friendly registry rows."""

    if "rows" in raw and "status" in raw and isinstance(raw.get("rows"), list):
        return _coerce_sec_funds_payload(raw, state=state)

    fields = raw.get("fields")
    data = raw.get("data")
    if not isinstance(fields, list) or not isinstance(data, list):
        raise FundDataError("SEC fund ticker registry payload must contain fields and data")

    field_names = [str(field) for field in fields]
    required = {"cik", "seriesId", "classId", "symbol"}
    if not required.issubset(set(field_names)):
        raise FundDataError("SEC fund ticker registry fields are missing required columns")

    indexes = {field: field_names.index(field) for field in required}
    wanted = {symbol.upper() for symbol in symbols}
    all_rows = [
        _row_from_sec_fund_record(record, indexes)
        for record in data
        if isinstance(record, list)
    ]
    all_rows = [row for row in all_rows if row is not None]
    matched = [row for row in all_rows if row["symbol"] in wanted]
    rows = sorted(matched or all_rows[:MAX_FUND_ROWS], key=lambda item: item["symbol"])
    if not rows:
        raise FundDataError("SEC fund ticker registry has no usable ticker rows")

    updated_at = retrieved_at or _utc_now()
    for row in rows:
        row.update(
            {
                "source": "sec_fund_ticker_registry",
                "provider_id": SEC_FUND_PROVIDER_ID,
                "retrieved_at": updated_at,
                "cache_path": SEC_FUND_CACHE_PATH,
                "docs_url": SEC_ACCESS_DOCS_URL,
                "reference_only": True,
            }
        )
    return {
        "status": _status(
            state=state,
            last_update=updated_at,
            message=(
                "SEC fund ticker registry normalized from public no-key JSON; "
                "this is fund/class reference data, not ETF quotes."
            ),
        ),
        "rows": rows,
        "summary": {
            "row_count": len(rows),
            "registry_total": len(all_rows),
            "matched_symbols": ",".join(row["symbol"] for row in rows),
            "quote_state": "disabled_until_provider_gate",
            "quote_provider": "optional_local_key_or_paid_etf_quote_provider",
            "source": "sec_fund_ticker_registry",
        },
    }


def provider_entry_summary() -> dict[str, Any]:
    return {
        "docs_checked_at": DOCS_CHECKED_AT,
        "providers": [
            {
                "provider_id": SEC_FUND_PROVIDER_ID,
                "official_docs": SEC_ACCESS_DOCS_URL,
                "auth_mode": "no-key",
                "rate_limit": "Use daily local cache and comply with SEC fair-access guidance.",
                "terms_risk": (
                    "SEC ticker mapping is public reference data; preserve source attribution "
                    "and do not present fund registry rows as executable ETF quotes."
                ),
                "cache_path": SEC_FUND_CACHE_PATH,
                "ttl_seconds": SEC_FUND_TTL_SECONDS,
                "schema": "company_tickers_mf fields/data -> fund ticker registry rows",
                "safety_class": "public_read_only_fund_reference",
            }
        ],
    }


def _row_from_sec_fund_record(
    record: list[Any],
    indexes: dict[str, int],
) -> dict[str, str] | None:
    try:
        symbol = str(record[indexes["symbol"]] or "").strip().upper()
        cik = str(record[indexes["cik"]] or "").strip()
        series_id = str(record[indexes["seriesId"]] or "").strip()
        class_id = str(record[indexes["classId"]] or "").strip()
    except IndexError:
        return None
    if not symbol or not cik or not series_id or not class_id:
        return None
    return {
        "symbol": symbol[:24],
        "cik": "".join(ch for ch in cik if ch.isdigit()).zfill(10)[-10:],
        "series_id": series_id[:24],
        "class_id": class_id[:24],
    }


def _coerce_sec_funds_payload(raw: dict[str, Any] | None, *, state: str) -> dict[str, Any]:
    if not isinstance(raw, dict) or not raw:
        return _empty_sec_funds_payload()
    if "rows" in raw and "status" in raw and isinstance(raw.get("rows"), list):
        payload = dict(raw)
        status = dict(payload.get("status") or {})
        status["state"] = _cache_state(status.get("state"), state)
        payload["status"] = status
        rows = [row for row in payload.get("rows", []) if isinstance(row, dict)]
        payload["rows"] = rows
        summary = payload.get("summary")
        if not isinstance(summary, dict):
            summary = _summary_from_rows(rows)
        payload["summary"] = summary
        return payload
    try:
        return normalize_sec_fund_tickers(raw, state=state)
    except FundDataError:
        return _empty_sec_funds_payload()


def _empty_sec_funds_payload() -> dict[str, Any]:
    return {
        "status": _status(
            state="unavailable",
            last_update="not refreshed",
            message="No SEC fund ticker registry cache is available yet.",
        ),
        "rows": [],
        "summary": {
            "row_count": 0,
            "registry_total": 0,
            "matched_symbols": "",
            "quote_state": "disabled_until_provider_gate",
            "quote_provider": "optional_local_key_or_paid_etf_quote_provider",
            "source": "sec_fund_ticker_registry",
        },
    }


def _sec_funds_section(payload: dict[str, Any]) -> dict[str, Any]:
    rows = [row for row in payload.get("rows", []) if isinstance(row, dict)]
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    return {
        "status": dict(payload.get("status") or {}),
        "rows": rows,
        "summary": {
            **_summary_from_rows(rows),
            **summary,
            "row_count": len(rows),
        },
    }


def _summary_from_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "row_count": len(rows),
        "registry_total": len(rows),
        "matched_symbols": ",".join(str(row.get("symbol") or "") for row in rows),
        "quote_state": "disabled_until_provider_gate",
        "quote_provider": "optional_local_key_or_paid_etf_quote_provider",
        "source": "sec_fund_ticker_registry",
    }


def _status(*, state: str, last_update: str, message: str) -> dict[str, str]:
    return {
        "source": "sec_fund_ticker_registry",
        "state": state,
        "last_update": last_update,
        "message": message,
        "provider_id": SEC_FUND_PROVIDER_ID,
        "cache_path": SEC_FUND_CACHE_PATH,
        "docs_url": SEC_ACCESS_DOCS_URL,
    }


def _read_json_response(response: Any) -> dict[str, Any]:
    body = response.read()
    encoding = str(response.headers.get("Content-Encoding") or "").lower()
    if "gzip" in encoding:
        body = gzip.decompress(body)
    payload = json.loads(body.decode("utf-8"))
    if not isinstance(payload, dict):
        raise FundDataError("SEC fund ticker registry response must be an object")
    return payload


def _cache_state(raw_state: Any, fallback: str) -> str:
    state = str(raw_state or "")
    if state in {"live", "stale", "partial", "unavailable"}:
        return fallback if state == "live" and fallback == "stale" else state
    return fallback


def _utc_now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
