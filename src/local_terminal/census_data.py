"""Census optional-key ACS regional context adapter."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import urlencode


CENSUS_PROVIDER_ID = "census_api_optional_key"
CENSUS_SOURCE = "census_acs5_profile_api"
CENSUS_VINTAGE = "2023"
CENSUS_DATASET = "acs/acs5/profile"
CENSUS_API_ROOT = f"https://api.census.gov/data/{CENSUS_VINTAGE}/{CENSUS_DATASET}"
CENSUS_DOCS_URL = "https://www.census.gov/data/developers/guidance/api-user-guide.API_Key.html"
CENSUS_DATASET_DOCS_URL = f"{CENSUS_API_ROOT}.html"
CENSUS_VARIABLES_DOCS_URL = f"{CENSUS_API_ROOT}/variables.html"
CENSUS_DOCS_CHECKED_AT = "2026-05-25"
CENSUS_TTL_SECONDS = 86400
CENSUS_CACHE_PATH = "market_data/regional/census/acs5_profile_state_2023.json"
CENSUS_MAX_SERIES = 12
CENSUS_NOTICE = (
    "Census ACS profile data is official regional context, not executable "
    "quotes, balances, or trade instructions."
)
CENSUS_VARIABLES: tuple[tuple[str, str, str], ...] = (
    ("DP05_0001E", "ACS total population", "people"),
    ("DP03_0062E", "ACS median household income", "dollars"),
    ("DP03_0009PE", "ACS unemployment rate", "percent"),
    ("DP03_0128PE", "ACS poverty rate", "percent"),
)


class CensusDataError(ValueError):
    """Raised when Census optional-key regional data cannot be used safely."""


class CensusRateLimitError(CensusDataError):
    """Raised when Census returns a throttling or quota response."""


def census_acs_profile_payload(
    cache: dict[str, Any] | None,
    local_secret_status: dict[str, Any] | None,
    *,
    fetcher: Any | None = None,
    refresh: bool = False,
    credential: str = "",
) -> dict[str, Any]:
    """Return Census ACS regional context without exposing the local key."""

    fetcher = fetcher or fetch_census_acs_profile_data
    status = local_secret_status if isinstance(local_secret_status, dict) else {}
    stored_ids = status.get("stored_provider_ids") if isinstance(status.get("stored_provider_ids"), list) else []
    key_stored = CENSUS_PROVIDER_ID in {str(provider_id) for provider_id in stored_ids}

    if refresh and not key_stored:
        return _coerce_census_payload(
            cache,
            state="key_required",
            message="Store a local Census API key in Settings before refreshing regional context.",
        )
    if refresh:
        if not credential:
            return _coerce_census_payload(
                cache,
                state="key_required",
                message="The Census provider is configured, but the local key could not be opened.",
            )
        try:
            raw = fetcher(credential=credential)
            payload = normalize_census_acs_profile_data(raw, state="live")
        except CensusRateLimitError as exc:
            return _coerce_census_payload(
                cache,
                state="rate_limited",
                message=f"Census refresh is rate-limited; using local cache if present. {exc}",
            )
        except (
            CensusDataError,
            OSError,
            TimeoutError,
            urllib.error.URLError,
            json.JSONDecodeError,
        ) as exc:
            return _coerce_census_payload(
                cache,
                state="unavailable",
                message=f"Census refresh failed without exposing credential material: {exc.__class__.__name__}.",
            )
        return {**payload, "cache": {"census": _cache_payload(payload)}}

    if cache:
        return _coerce_census_payload(cache, state="stale_cache")
    if key_stored:
        return _empty_census_payload(
            state="unavailable",
            message="A local Census key is stored; refresh this provider to populate regional context.",
        )
    return _empty_census_payload(
        state="key_required",
        message="Store a local Census API key in Settings before using this optional provider.",
    )


def fetch_census_acs_profile_data(
    *,
    credential: str,
    timeout: float = 8.0,
) -> list[Any]:
    """Fetch a bounded Census ACS profile state-level response with a user-owned key."""

    params = urlencode(
        {
            "get": ",".join(["NAME", *(variable for variable, _, _ in CENSUS_VARIABLES)]),
            "for": "state:*",
            "key": credential,
        }
    )
    request = urllib.request.Request(
        f"{CENSUS_API_ROOT}?{params}",
        headers={"User-Agent": "LocalTerminal/0.1 clean-room regional ACS context"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8-sig"))
    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            raise CensusRateLimitError("HTTP 429") from exc
        if exc.code in {400, 401, 403}:
            raise CensusDataError(
                "Census request rejected; verify the local key and ACS profile parameters"
            ) from exc
        raise CensusDataError(f"Census request failed with HTTP {exc.code}") from exc
    if not isinstance(payload, list):
        raise CensusDataError("Census response must be a JSON array")
    return payload


def normalize_census_acs_profile_data(
    raw: Any,
    *,
    state: str = "live",
    retrieved_at: str | None = None,
) -> dict[str, Any]:
    """Normalize Census ACS profile rows into local non-quote regional context."""

    if isinstance(raw, dict) and "series" in raw and "status" in raw:
        return _coerce_census_payload(raw, state=state)
    rows = _census_rows(raw)
    updated_at = retrieved_at or _utc_now()
    series: list[dict[str, str]] = []
    metric_map = {variable: (label, unit) for variable, label, unit in CENSUS_VARIABLES}
    for row in rows:
        geo_name = str(row.get("NAME") or "").strip()
        state_code = str(row.get("state") or "").strip()
        if not geo_name or not state_code:
            continue
        for variable, (label, unit) in metric_map.items():
            value = _number_text(row.get(variable))
            if not value:
                continue
            series.append(
                {
                    "series_id": f"ACS5_PROFILE_{CENSUS_VINTAGE}:{state_code}:{variable}",
                    "label": f"{label} {geo_name}"[:160],
                    "dataset_name": f"Census ACS {CENSUS_VINTAGE} 5-year Data Profile",
                    "source": CENSUS_SOURCE,
                    "provider_id": CENSUS_PROVIDER_ID,
                    "source_provider": "U.S. Census Bureau ACS",
                    "dataset": f"{CENSUS_VINTAGE}/{CENSUS_DATASET}",
                    "retrieved_at": updated_at,
                    "cache_path": CENSUS_CACHE_PATH,
                    "docs_url": CENSUS_DATASET_DOCS_URL,
                    "latest_period": f"{CENSUS_VINTAGE} ACS 5-year",
                    "latest_value": value,
                    "observation_count": "1",
                    "frequency": "5-year ACS",
                    "unit": unit,
                    "geo_fips": state_code,
                    "geo_name": geo_name,
                    "variable": variable,
                    "notice": CENSUS_NOTICE,
                    "quote_semantics": "not_quote",
                }
            )
            if len(series) >= CENSUS_MAX_SERIES:
                break
        if len(series) >= CENSUS_MAX_SERIES:
            break
    if not series:
        raise CensusDataError("Census response has no usable ACS profile rows")
    return {
        "status": _status(
            state=state,
            last_update=updated_at,
            message="Census ACS profile data normalized from user-owned local-key access.",
            cache_path=CENSUS_CACHE_PATH,
        ),
        "series": series,
        "summary": _summary_from_rows(series),
        "entry": census_provider_entry_summary(),
        "cache": {"census": None},
    }


def census_provider_entry_summary() -> dict[str, Any]:
    return {
        "provider_id": CENSUS_PROVIDER_ID,
        "official_docs": [CENSUS_DOCS_URL, CENSUS_DATASET_DOCS_URL, CENSUS_VARIABLES_DOCS_URL],
        "docs_checked_at": CENSUS_DOCS_CHECKED_AT,
        "auth_mode": "optional-local-key",
        "rate_limit": "Use a user-owned Census API key, bounded ACS profile request, and daily local cache.",
        "terms_risk": "User-owned key; no signup, payment, private account, or live trading use by agent.",
        "cache_path": CENSUS_CACHE_PATH,
        "ttl_seconds": CENSUS_TTL_SECONDS,
        "schema": "ACS 5-year profile state rows -> bounded regional context series",
        "fallback": "Show DBnomics/BLS/BEA public or cached macro context; never use fixtures.",
        "safety_class": "optional_local_secret_data_provider",
    }


def _coerce_census_payload(
    raw: dict[str, Any] | None,
    *,
    state: str,
    message: str = "",
) -> dict[str, Any]:
    if isinstance(raw, dict) and "series" in raw and "status" in raw:
        payload = dict(raw)
        status = dict(payload.get("status") or {})
        series = payload.get("series") if isinstance(payload.get("series"), list) else []
        if series and state in {"key_required", "unavailable"}:
            status["state"] = "stale_cache"
            status["message"] = message or "Showing last local Census ACS cache."
        elif state in {"rate_limited", "stale_cache"} and series:
            status["state"] = state
            status["message"] = message or status.get("message") or "Showing local Census ACS cache."
        else:
            status["state"] = state or status.get("state") or "unavailable"
            if message:
                status["message"] = message
        payload["status"] = status
        payload.setdefault("summary", _summary_from_rows(series))
        payload.setdefault("entry", census_provider_entry_summary())
        payload["cache"] = {"census": _cache_payload(payload) if series else None}
        return payload
    return _empty_census_payload(state=state, message=message)


def _empty_census_payload(*, state: str, message: str) -> dict[str, Any]:
    return {
        "status": _status(
            state=state,
            last_update="not refreshed",
            message=message,
            cache_path=CENSUS_CACHE_PATH,
        ),
        "series": [],
        "summary": {
            "series_count": 0,
            "state_count": 0,
            "latest_period": "",
            "latest_value": "",
            "primary_geo": "",
            "source": CENSUS_SOURCE,
            "provider_id": CENSUS_PROVIDER_ID,
            "quote_semantics": "not_quote",
        },
        "entry": census_provider_entry_summary(),
        "cache": {"census": None},
    }


def _status(*, state: str, last_update: str, message: str, cache_path: str) -> dict[str, str]:
    return {
        "source": CENSUS_SOURCE,
        "state": state,
        "last_update": last_update,
        "message": message,
        "provider_id": CENSUS_PROVIDER_ID,
        "cache_path": cache_path,
        "docs_url": CENSUS_DATASET_DOCS_URL,
        "auth_mode": "optional-local-key",
        "safety_class": "optional_local_secret_data_provider",
        "notice": CENSUS_NOTICE,
    }


def _summary_from_rows(rows: list[Any]) -> dict[str, Any]:
    valid = [row for row in rows if isinstance(row, dict)]
    first = valid[0] if valid else {}
    return {
        "series_count": len(valid),
        "state_count": len({str(row.get("geo_fips") or "") for row in valid if row.get("geo_fips")}),
        "latest_period": str(first.get("latest_period") or ""),
        "latest_value": str(first.get("latest_value") or ""),
        "primary_geo": str(first.get("geo_name") or ""),
        "source": CENSUS_SOURCE,
        "provider_id": CENSUS_PROVIDER_ID,
        "quote_semantics": "not_quote",
    }


def _census_rows(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list) or not raw:
        raise CensusDataError("Census response is empty")
    header = raw[0]
    if not isinstance(header, list) or not all(isinstance(item, str) for item in header):
        raise CensusDataError("Census response header is invalid")
    rows: list[dict[str, Any]] = []
    for item in raw[1:]:
        if isinstance(item, list) and len(item) == len(header):
            rows.append(dict(zip(header, item, strict=True)))
    return rows


def _number_text(raw: Any) -> str:
    text = str(raw or "").replace(",", "").strip()
    if text in {"", "-888888888", "-999999999", "null", "None"}:
        return ""
    try:
        value = Decimal(text)
    except (InvalidOperation, ValueError):
        return ""
    return format(value.normalize(), "f")


def _cache_payload(payload: dict[str, Any]) -> dict[str, Any]:
    cache_payload = dict(payload)
    cache_payload.pop("cache", None)
    return cache_payload


def _utc_now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
