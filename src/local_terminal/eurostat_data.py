"""Eurostat public no-key HICP macro context adapter."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any


EUROSTAT_PROVIDER_ID = "eurostat_hicp_public"
EUROSTAT_SOURCE = "eurostat_statistics_api"
EUROSTAT_DATASET = "prc_hicp_midx"
EUROSTAT_CACHE_PATH = "market_data/macro/eurostat/hicp_ea20_cp00_i15.json"
EUROSTAT_API_URL = (
    "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
    f"{EUROSTAT_DATASET}"
)
EUROSTAT_DOCS_URL = (
    "https://ec.europa.eu/eurostat/web/user-guides/data-browser/api-data-access/"
    "api-detailed-guidelines/api-statistics"
)
EUROSTAT_DATASET_URL = (
    "https://ec.europa.eu/eurostat/databrowser/view/prc_hicp_midx/default/table"
)
EUROSTAT_DOCS_CHECKED_AT = "2026-05-27"
EUROSTAT_TTL_SECONDS = 86400
EUROSTAT_NOTICE = (
    "Eurostat HICP rows are official macro/reference context only; they are not "
    "market quotes, orderable instruments, balances, or trading signals."
)


class EurostatDataError(ValueError):
    """Raised when Eurostat HICP rows cannot be normalized safely."""


def eurostat_hicp_payload(
    cache: dict[str, Any] | None,
    *,
    fetcher: Any | None = None,
    refresh: bool = False,
) -> dict[str, Any]:
    """Return bounded public Eurostat HICP macro rows without credentials."""

    fetcher = fetcher or fetch_eurostat_hicp
    if refresh:
        try:
            raw = fetcher()
            payload = normalize_eurostat_hicp(raw, state="live")
        except (
            EurostatDataError,
            OSError,
            TimeoutError,
            urllib.error.URLError,
            json.JSONDecodeError,
        ) as exc:
            return _coerce_eurostat_payload(
                cache,
                state="unavailable",
                message=f"Eurostat HICP refresh failed; using local cache if present. {exc.__class__.__name__}.",
            )
        return {**payload, "cache": {"eurostat": _cache_payload(payload)}}

    if cache:
        return _coerce_eurostat_payload(cache, state="stale_cache")
    return _empty_eurostat_payload(
        state="unavailable",
        message="No Eurostat HICP macro cache is available yet.",
    )


def fetch_eurostat_hicp(*, timeout: float = 8.0) -> dict[str, Any]:
    params = urllib.parse.urlencode(
        {
            "lang": "EN",
            "lastTimePeriod": "3",
            "geo": "EA20",
            "coicop": "CP00",
            "unit": "I15",
            "freq": "M",
        }
    )
    request = urllib.request.Request(
        f"{EUROSTAT_API_URL}?{params}",
        headers={"User-Agent": "LocalTerminal/0.1 clean-room local macro research"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise EurostatDataError("Eurostat response must be a JSON object")
    return payload


def _period_age_months(period: str) -> int | None:
    try:
        stamp = datetime.strptime(period, "%Y-%m")
    except ValueError:
        return None
    now = datetime.now(tz=UTC)
    return (now.year - stamp.year) * 12 + (now.month - stamp.month)


def normalize_eurostat_hicp(
    raw: dict[str, Any],
    *,
    state: str = "live",
    retrieved_at: str | None = None,
) -> dict[str, Any]:
    """Normalize Eurostat JSON-stat HICP rows into local macro series rows."""

    if "series" in raw and "status" in raw:
        return _coerce_eurostat_payload(raw, state=state)

    updated_at = retrieved_at or _utc_now()
    observations = _eurostat_observations(raw)
    if not observations:
        raise EurostatDataError("Eurostat response has no usable HICP observations")
    latest = observations[0]
    # status.state carries CACHE freshness for the whole provider pipeline
    # (stale = served from old cache), so data vintage gets its own axis: a
    # fresh fetch of a months-old print stays "live" but says so out loud.
    vintage_note = ""
    data_vintage = "current"
    age_months = _period_age_months(latest["period"])
    if age_months is not None and age_months > 3:
        data_vintage = "aged"
        vintage_note = f" Newest observation is {latest['period']} ({age_months} months old)."
    row = {
        "series_id": "prc_hicp_midx.EA20.CP00.I15",
        "label": "Euro area HICP all items",
        "dataset_name": "HICP - monthly data (index)",
        "source": EUROSTAT_SOURCE,
        "provider_id": EUROSTAT_PROVIDER_ID,
        "source_provider": "Eurostat",
        "dataset": EUROSTAT_DATASET,
        "retrieved_at": updated_at,
        "cache_path": EUROSTAT_CACHE_PATH,
        "docs_url": EUROSTAT_DOCS_URL,
        "latest_period": latest["period"],
        "latest_value": latest["value"],
        "observation_count": len(observations),
        "frequency": "monthly",
        "unit": "index 2015=100",
        "geo": "EA20",
        "coicop": "CP00",
        "indexed_at": updated_at,
        "notice": EUROSTAT_NOTICE,
        "summary_key": "euro_area_hicp",
    }
    return {
        "status": {
            **_status(
                state=state,
                last_update=updated_at,
                message="Eurostat HICP macro series normalized from public no-key API."
                + vintage_note,
            ),
            "data_vintage": data_vintage,
        },
        "series": [row],
        "observations": observations,
        "summary": {
            "provider_id": EUROSTAT_PROVIDER_ID,
            "source": EUROSTAT_SOURCE,
            "series_count": 1,
            "latest_period": latest["period"],
            "latest_value": latest["value"],
            "cache_path": EUROSTAT_CACHE_PATH,
            "quote_semantics": "not_quote",
            "notice": EUROSTAT_NOTICE,
        },
        "entry": eurostat_provider_entry_summary(),
        "cache": {"eurostat": None},
    }


def eurostat_provider_entry_summary() -> dict[str, Any]:
    return {
        "provider_id": EUROSTAT_PROVIDER_ID,
        "official_docs": [EUROSTAT_DOCS_URL, EUROSTAT_DATASET_URL],
        "docs_checked_at": EUROSTAT_DOCS_CHECKED_AT,
        "auth_mode": "no-key",
        "rate_limit": "Use daily local cache and bounded lastTimePeriod=3 HICP requests.",
        "terms_risk": (
            "Official Eurostat macro/reference data; preserve attribution and never "
            "represent HICP rows as executable quotes or trading signals."
        ),
        "cache_path": EUROSTAT_CACHE_PATH,
        "ttl_seconds": EUROSTAT_TTL_SECONDS,
        "schema": "JSON-stat value/time dimensions -> latest HICP macro context rows",
        "safety_class": "public_read_only_macro",
    }


def _coerce_eurostat_payload(
    raw: dict[str, Any] | None,
    *,
    state: str,
    message: str | None = None,
) -> dict[str, Any]:
    if not isinstance(raw, dict) or not raw:
        return _empty_eurostat_payload(state="unavailable", message=message)
    if "series" in raw and "status" in raw:
        payload = dict(raw)
        status = dict(payload.get("status") or {})
        status["state"] = _cache_state(status.get("state"), state)
        if message:
            status["message"] = message
        payload["status"] = status
        payload["cache"] = {"eurostat": None}
        return payload
    try:
        return normalize_eurostat_hicp(raw, state=state)
    except EurostatDataError:
        return _empty_eurostat_payload(state="unavailable", message=message)


def _empty_eurostat_payload(*, state: str, message: str) -> dict[str, Any]:
    return {
        "status": _status(state=state, last_update="", message=message),
        "series": [],
        "observations": [],
        "summary": {
            "provider_id": EUROSTAT_PROVIDER_ID,
            "source": EUROSTAT_SOURCE,
            "series_count": 0,
            "latest_period": "",
            "latest_value": "",
            "cache_path": EUROSTAT_CACHE_PATH,
            "quote_semantics": "not_quote",
            "notice": EUROSTAT_NOTICE,
        },
        "entry": eurostat_provider_entry_summary(),
        "cache": {"eurostat": None},
    }


def _eurostat_observations(raw: dict[str, Any]) -> list[dict[str, str]]:
    values = raw.get("value")
    if not isinstance(values, (dict, list)):
        raise EurostatDataError("Eurostat value map is missing")
    dimensions = raw.get("dimension") if isinstance(raw.get("dimension"), dict) else {}
    time_dimension = dimensions.get("time") if isinstance(dimensions.get("time"), dict) else {}
    category = time_dimension.get("category") if isinstance(time_dimension.get("category"), dict) else {}
    index_map = category.get("index") if isinstance(category.get("index"), dict) else {}
    periods = sorted(
        ((str(period), int(index)) for period, index in index_map.items()),
        key=lambda item: item[1],
        reverse=True,
    )
    observations: list[dict[str, str]] = []
    for period, index in periods[:3]:
        if isinstance(values, dict):
            value = values.get(str(index))
        elif 0 <= index < len(values):
            value = values[index]
        else:
            continue
        value_text = _number_text(value)
        if not value_text:
            continue
        observations.append(
            {
                "period": period,
                "value": value_text,
                "unit": "index 2015=100",
                "source": EUROSTAT_SOURCE,
                "provider_id": EUROSTAT_PROVIDER_ID,
            }
        )
    return observations


def _cache_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if key != "cache"}


def _status(*, state: str, last_update: str, message: str) -> dict[str, str | bool]:
    return {
        "source": EUROSTAT_SOURCE,
        "state": state,
        "last_update": last_update,
        "message": message,
        "provider_id": EUROSTAT_PROVIDER_ID,
        "cache_path": EUROSTAT_CACHE_PATH,
        "docs_url": EUROSTAT_DOCS_URL,
        "quote_semantics": "not_quote",
        "live_action_enabled": False,
        "orderable": False,
    }


def _cache_state(current: Any, fallback: str) -> str:
    state = str(current or "")
    return state if state in {"live", "partial", "stale", "stale_cache"} else fallback


def _number_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(Decimal(str(value)).quantize(Decimal("0.01")))
    except (InvalidOperation, ValueError):
        return ""


def _utc_now() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
