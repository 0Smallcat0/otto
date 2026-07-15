"""Public no-key rates provider adapters."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any


DOCS_CHECKED_AT = "2026-05-26"
TREASURY_DOCS_URL = "https://home.treasury.gov/treasury-daily-interest-rate-xml-feed"
TREASURY_XML_URL = (
    "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml"
    "?data=daily_treasury_yield_curve&field_tdr_date_value={year}"
)
TREASURY_CACHE_PATH = "market_data/rates/treasury/daily_yield_curve.json"
TREASURY_PROVIDER_ID = "us_treasury_yield_public"
TREASURY_TTL_SECONDS = 86400
NYFED_SOFR_DOCS_URL = "https://www.newyorkfed.org/markets/reference-rates/sofr"
NYFED_MARKETS_API_DOCS_URL = "https://markets.newyorkfed.org/static/docs/markets-api.html"
NYFED_SOFR_JSON_URL = "https://markets.newyorkfed.org/api/rates/secured/sofr/last/10.json"
NYFED_SOFR_CACHE_PATH = "market_data/rates/nyfed/sofr.json"
NYFED_SOFR_PROVIDER_ID = "nyfed_sofr_public"
NYFED_SOFR_TTL_SECONDS = 86400
TREASURY_TENORS: tuple[tuple[str, str], ...] = (
    ("1M", "BC_1MONTH"),
    ("1.5M", "BC_1_5MONTH"),
    ("2M", "BC_2MONTH"),
    ("3M", "BC_3MONTH"),
    ("4M", "BC_4MONTH"),
    ("6M", "BC_6MONTH"),
    ("1Y", "BC_1YEAR"),
    ("2Y", "BC_2YEAR"),
    ("3Y", "BC_3YEAR"),
    ("5Y", "BC_5YEAR"),
    ("7Y", "BC_7YEAR"),
    ("10Y", "BC_10YEAR"),
    ("20Y", "BC_20YEAR"),
    ("30Y", "BC_30YEAR"),
)
ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}
DATA_NS = "{http://schemas.microsoft.com/ado/2007/08/dataservices}"


class RatesDataError(ValueError):
    """Raised when public rates provider data is invalid."""


def rates_data_payload(
    treasury_cache: dict[str, Any] | None = None,
    sofr_cache: dict[str, Any] | None = None,
    *,
    fetcher: Any | None = None,
    sofr_fetcher: Any | None = None,
    refresh: bool = False,
) -> dict[str, Any]:
    """Return normalized public rates data with provenance and local cache state."""

    fetcher = fetcher or fetch_treasury_yield_curve
    sofr_fetcher = sofr_fetcher or fetch_nyfed_sofr
    source_errors: list[str] = []
    treasury_payload = _coerce_treasury_payload(treasury_cache, state="stale")
    sofr_payload = _coerce_sofr_payload(sofr_cache, state="stale")

    if refresh:
        try:
            treasury_payload = normalize_treasury_yield_curve(fetcher(), state="live")
        except (
            RatesDataError,
            OSError,
            TimeoutError,
            urllib.error.URLError,
            ET.ParseError,
        ) as exc:
            source_errors.append(f"Treasury: {str(exc) or exc.__class__.__name__}")
        try:
            sofr_payload = normalize_nyfed_sofr(sofr_fetcher(), state="live")
        except (
            RatesDataError,
            OSError,
            TimeoutError,
            urllib.error.URLError,
            json.JSONDecodeError,
        ) as exc:
            source_errors.append(f"NY Fed SOFR: {str(exc) or exc.__class__.__name__}")

    treasury = _treasury_section(treasury_payload)
    sofr = _sofr_section(sofr_payload)
    status = dict(treasury["status"])
    if status["state"] == "unavailable" and sofr["status"].get("state") in {"live", "stale"}:
        status = dict(sofr["status"])
        status["message"] = "NY Fed SOFR reference cache is available; Treasury curve is unavailable."
    elif source_errors and status["state"] == "unavailable":
        status["message"] = "Rates refresh failed; no usable local rates cache is available."
    elif source_errors:
        status["message"] = "One or more rates refreshes failed; using available local rates cache."
    status["source_errors"] = source_errors
    return {
        "status": status,
        "treasury": treasury,
        "sofr": sofr,
        "provider_entry": provider_entry_summary(),
        "cache": {"treasury": treasury_payload, "sofr": sofr_payload},
    }


def fetch_treasury_yield_curve(year: int | None = None, timeout: float = 8.0) -> str:
    """Fetch the U.S. Treasury daily yield curve XML feed."""

    current_year = datetime.now(tz=UTC).year
    safe_year = year if isinstance(year, int) and 1990 <= year <= current_year + 1 else current_year
    request = urllib.request.Request(
        TREASURY_XML_URL.format(year=safe_year),
        headers={"User-Agent": "LocalTerminal/0.1 clean-room local rates"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8")


def fetch_nyfed_sofr(timeout: float = 8.0) -> dict[str, Any]:
    """Fetch the latest New York Fed SOFR reference-rate JSON rows."""

    request = urllib.request.Request(
        NYFED_SOFR_JSON_URL,
        headers={
            "Accept": "application/json",
            "User-Agent": "LocalTerminal/0.1 clean-room local rates",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def normalize_treasury_yield_curve(
    raw: str | bytes | dict[str, Any],
    *,
    state: str = "live",
    retrieved_at: str | None = None,
) -> dict[str, Any]:
    """Normalize Treasury XML feed data into a compact local rates schema."""

    if isinstance(raw, dict) and "rows" in raw and "status" in raw:
        return _coerce_treasury_payload(raw, state=state)
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    if not isinstance(raw, str) or not raw.strip():
        raise RatesDataError("Treasury yield curve payload is empty")

    root = ET.fromstring(raw)
    rows: list[dict[str, Any]] = []
    for entry in root.findall("atom:entry", ATOM_NS):
        properties = entry.find(".//{http://schemas.microsoft.com/ado/2007/08/dataservices/metadata}properties")
        if properties is None:
            continue
        row = _row_from_properties(properties)
        if row is not None:
            rows.append(row)

    if not rows:
        raise RatesDataError("Treasury yield curve payload has no rate rows")
    rows = sorted(rows, key=lambda item: str(item["date"]))
    updated_at = retrieved_at or _utc_now()
    for row in rows:
        row.update(
            {
                "source": "us_treasury_public",
                "provider_id": TREASURY_PROVIDER_ID,
                "retrieved_at": updated_at,
                "cache_path": TREASURY_CACHE_PATH,
                "docs_url": TREASURY_DOCS_URL,
            }
        )
    latest = rows[-1]
    return {
        "status": _status(
            state=state,
            last_update=updated_at,
            message="U.S. Treasury daily yield curve normalized from public no-key XML feed.",
        ),
        "rows": rows,
        "latest": latest,
    }


def normalize_nyfed_sofr(
    raw: str | bytes | dict[str, Any],
    *,
    state: str = "live",
    retrieved_at: str | None = None,
) -> dict[str, Any]:
    """Normalize NY Fed SOFR JSON into reference-rate rows."""

    if isinstance(raw, dict) and "rows" in raw and "status" in raw:
        return _coerce_sofr_payload(raw, state=state)
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    if isinstance(raw, str):
        if not raw.strip():
            raise RatesDataError("NY Fed SOFR payload is empty")
        raw = json.loads(raw)
    if not isinstance(raw, dict):
        raise RatesDataError("NY Fed SOFR payload is not a JSON object")
    ref_rates = raw.get("refRates")
    if not isinstance(ref_rates, list):
        raise RatesDataError("NY Fed SOFR payload has no refRates rows")

    updated_at = retrieved_at or _utc_now()
    rows: list[dict[str, Any]] = []
    for item in ref_rates:
        if not isinstance(item, dict):
            continue
        if str(item.get("type") or "").upper() not in {"", "SOFR"}:
            continue
        date = str(item.get("effectiveDate") or "")
        rate = _format_decimal(_to_decimal(item.get("percentRate")))
        if not date or not rate:
            continue
        rows.append(
            {
                "date": date,
                "rate": rate,
                "unit": "percent",
                "volume_in_billions": _format_whole_number(item.get("volumeInBillions")),
                "percentile_1": _format_decimal(_to_decimal(item.get("percentPercentile1"))),
                "percentile_25": _format_decimal(_to_decimal(item.get("percentPercentile25"))),
                "percentile_75": _format_decimal(_to_decimal(item.get("percentPercentile75"))),
                "percentile_99": _format_decimal(_to_decimal(item.get("percentPercentile99"))),
                "revision_indicator": str(item.get("revisionIndicator") or ""),
                "source": "nyfed_sofr_public",
                "provider_id": NYFED_SOFR_PROVIDER_ID,
                "retrieved_at": updated_at,
                "cache_path": NYFED_SOFR_CACHE_PATH,
                "docs_url": NYFED_SOFR_DOCS_URL,
            }
        )
    if not rows:
        raise RatesDataError("NY Fed SOFR payload has no usable SOFR rows")
    rows = sorted(rows, key=lambda item: str(item["date"]))
    latest = rows[-1]
    return {
        "status": _sofr_status(
            state=state,
            last_update=updated_at,
            message="NY Fed SOFR normalized from public no-key reference-rate API.",
        ),
        "rows": rows,
        "latest": latest,
    }


def provider_entry_summary() -> dict[str, Any]:
    return {
        "docs_checked_at": DOCS_CHECKED_AT,
        "providers": [
            {
                "provider_id": TREASURY_PROVIDER_ID,
                "official_docs": TREASURY_DOCS_URL,
                "auth_mode": "no-key",
                "rate_limit": "Use daily local cache; Treasury XML feed is a public read-only data source.",
                "terms_risk": "Public government rate data; preserve source attribution and retrieval date.",
                "cache_path": TREASURY_CACHE_PATH,
                "ttl_seconds": TREASURY_TTL_SECONDS,
                "schema": "Atom XML feed -> daily tenor curve rows",
                "safety_class": "public_read_only_rates",
            },
            {
                "provider_id": NYFED_SOFR_PROVIDER_ID,
                "official_docs": NYFED_SOFR_DOCS_URL,
                "api_docs": NYFED_MARKETS_API_DOCS_URL,
                "auth_mode": "no-key",
                "rate_limit": "Use daily local cache; New York Fed Markets API is public read-only reference data.",
                "terms_risk": "Reference rate data only; preserve New York Fed attribution and retrieval date.",
                "cache_path": NYFED_SOFR_CACHE_PATH,
                "ttl_seconds": NYFED_SOFR_TTL_SECONDS,
                "schema": "JSON refRates rows -> daily SOFR reference-rate rows",
                "safety_class": "public_read_only_rates",
            }
        ],
    }


def _coerce_treasury_payload(raw: dict[str, Any] | None, *, state: str) -> dict[str, Any]:
    if not isinstance(raw, dict) or not raw:
        return _empty_treasury_payload()
    if "rows" in raw and "status" in raw and isinstance(raw.get("rows"), list):
        payload = dict(raw)
        status = dict(payload.get("status") or {})
        status["state"] = _cache_state(status.get("state"), state)
        payload["status"] = status
        rows = [row for row in payload.get("rows", []) if isinstance(row, dict)]
        payload["rows"] = rows
        latest = payload.get("latest")
        payload["latest"] = latest if isinstance(latest, dict) else (rows[-1] if rows else {})
        return payload
    try:
        return normalize_treasury_yield_curve(raw, state=state)
    except (RatesDataError, ET.ParseError):
        return _empty_treasury_payload()


def _coerce_sofr_payload(raw: dict[str, Any] | None, *, state: str) -> dict[str, Any]:
    if not isinstance(raw, dict) or not raw:
        return _empty_sofr_payload()
    if "rows" in raw and "status" in raw and isinstance(raw.get("rows"), list):
        payload = dict(raw)
        status = dict(payload.get("status") or {})
        status["state"] = _cache_state(status.get("state"), state)
        payload["status"] = status
        rows = [row for row in payload.get("rows", []) if isinstance(row, dict)]
        payload["rows"] = rows
        latest = payload.get("latest")
        payload["latest"] = latest if isinstance(latest, dict) else (rows[-1] if rows else {})
        return payload
    try:
        return normalize_nyfed_sofr(raw, state=state)
    except (RatesDataError, json.JSONDecodeError):
        return _empty_sofr_payload()


def _empty_treasury_payload() -> dict[str, Any]:
    return {
        "status": _status(
            state="unavailable",
            last_update="not refreshed",
            message="No Treasury yield curve cache is available yet.",
        ),
        "rows": [],
        "latest": {},
    }


def _empty_sofr_payload() -> dict[str, Any]:
    return {
        "status": _sofr_status(
            state="unavailable",
            last_update="not refreshed",
            message="No NY Fed SOFR cache is available yet.",
        ),
        "rows": [],
        "latest": {},
    }


def _treasury_section(payload: dict[str, Any]) -> dict[str, Any]:
    rows = [row for row in payload.get("rows", []) if isinstance(row, dict)]
    latest = payload.get("latest") if isinstance(payload.get("latest"), dict) else {}
    tenors = latest.get("tenors") if isinstance(latest.get("tenors"), list) else []
    two_year = _tenor_rate(tenors, "2Y")
    ten_year = _tenor_rate(tenors, "10Y")
    thirty_year = _tenor_rate(tenors, "30Y")
    slope = _format_decimal(
        _to_decimal(ten_year) - _to_decimal(two_year)
        if _to_decimal(ten_year) is not None and _to_decimal(two_year) is not None
        else None
    )
    return {
        "status": dict(payload.get("status") or {}),
        "rows": rows,
        "latest": latest,
        "summary": {
            "row_count": len(rows),
            "latest_date": str(latest.get("date") or ""),
            "tenor_count": len(tenors),
            "two_year": two_year,
            "ten_year": ten_year,
            "thirty_year": thirty_year,
            "slope_10y_2y": slope,
            "source": "us_treasury_public",
        },
    }


def _sofr_section(payload: dict[str, Any]) -> dict[str, Any]:
    rows = [row for row in payload.get("rows", []) if isinstance(row, dict)]
    latest = payload.get("latest") if isinstance(payload.get("latest"), dict) else {}
    return {
        "status": dict(payload.get("status") or {}),
        "rows": rows,
        "latest": latest,
        "summary": {
            "row_count": len(rows),
            "latest_date": str(latest.get("date") or ""),
            "rate": str(latest.get("rate") or ""),
            "volume_in_billions": str(latest.get("volume_in_billions") or ""),
            "percentile_25": str(latest.get("percentile_25") or ""),
            "percentile_75": str(latest.get("percentile_75") or ""),
            "source": "nyfed_sofr_public",
            "quote_semantics": "reference_only",
        },
    }


def _row_from_properties(properties: ET.Element) -> dict[str, Any] | None:
    date_text = _child_text(properties, "NEW_DATE")
    date = _date_from_datetime(date_text)
    if not date:
        return None
    tenors = []
    for tenor, field in TREASURY_TENORS:
        rate = _format_decimal(_to_decimal(_child_text(properties, field)))
        if rate == "":
            continue
        tenors.append({"tenor": tenor, "field": field, "rate": rate, "unit": "percent"})
    if not tenors:
        return None
    return {
        "date": date,
        "tenors": tenors,
        "tenor_count": len(tenors),
    }


def _child_text(properties: ET.Element, local_name: str) -> str:
    node = properties.find(f"{DATA_NS}{local_name}")
    return str(node.text or "").strip() if node is not None else ""


def _date_from_datetime(raw: str) -> str:
    if not raw:
        return ""
    return raw.split("T", 1)[0]


def _status(*, state: str, last_update: str, message: str) -> dict[str, str]:
    return {
        "source": "us_treasury_public",
        "state": state,
        "last_update": last_update,
        "message": message,
        "provider_id": TREASURY_PROVIDER_ID,
        "cache_path": TREASURY_CACHE_PATH,
        "docs_url": TREASURY_DOCS_URL,
    }


def _sofr_status(*, state: str, last_update: str, message: str) -> dict[str, str]:
    return {
        "source": "nyfed_sofr_public",
        "state": state,
        "last_update": last_update,
        "message": message,
        "provider_id": NYFED_SOFR_PROVIDER_ID,
        "cache_path": NYFED_SOFR_CACHE_PATH,
        "docs_url": NYFED_SOFR_DOCS_URL,
    }


def _tenor_rate(tenors: list[Any], tenor: str) -> str:
    for row in tenors:
        if isinstance(row, dict) and row.get("tenor") == tenor:
            return str(row.get("rate") or "")
    return ""


def _to_decimal(raw: Any) -> Decimal | None:
    try:
        return Decimal(str(raw))
    except (InvalidOperation, ValueError):
        return None


def _format_decimal(value: Decimal | None) -> str:
    if value is None:
        return ""
    return f"{value.quantize(Decimal('0.01'))}"


def _format_whole_number(value: Any) -> str:
    decimal = _to_decimal(value)
    if decimal is None:
        return ""
    return f"{decimal.quantize(Decimal('1'))}"


def _cache_state(current: Any, requested: str) -> str:
    if requested == "stale" and str(current or "") in {"live", "partial"}:
        return "stale"
    return str(current or requested)


def _utc_now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
