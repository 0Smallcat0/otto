"""BEA optional-key regional macro context adapter."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import urlencode


BEA_PROVIDER_ID = "bea_regional_optional_key"
BEA_SOURCE = "bea_regional_api"
BEA_API_ROOT = "https://apps.bea.gov/api/data"
BEA_DOCS_URL = "https://apps.bea.gov/api/_pdf/bea_web_service_api_user_guide.pdf"
BEA_SIGNUP_URL = "https://apps.bea.gov/API/signup/"
BEA_DOCS_CHECKED_AT = "2026-05-25"
BEA_TTL_SECONDS = 86400
BEA_DEFAULT_TABLE = "SAGDP9N"
BEA_DEFAULT_LINE_CODE = "1"
BEA_DEFAULT_GEO_FIPS = "STATE"
BEA_DEFAULT_YEAR = "ALL"
BEA_CACHE_PATH = "market_data/regional/bea/SAGDP9N_LINE1_STATE.json"
BEA_NOTICE = (
    "BEA Regional data is official macro context, not executable quotes, "
    "balances, or trade instructions."
)
BEA_MAX_ROWS = 8


class BeaDataError(ValueError):
    """Raised when BEA optional-key regional data cannot be used safely."""


class BeaRateLimitError(BeaDataError):
    """Raised when BEA returns a throttling or quota response."""


def bea_regional_payload(
    cache: dict[str, Any] | None,
    local_secret_status: dict[str, Any] | None,
    *,
    fetcher: Any | None = None,
    refresh: bool = False,
    credential: str = "",
) -> dict[str, Any]:
    """Return BEA Regional context without exposing the local UserID."""

    fetcher = fetcher or fetch_bea_regional_data
    status = local_secret_status if isinstance(local_secret_status, dict) else {}
    stored_ids = status.get("stored_provider_ids") if isinstance(status.get("stored_provider_ids"), list) else []
    key_stored = BEA_PROVIDER_ID in {str(provider_id) for provider_id in stored_ids}

    if refresh and not key_stored:
        return _coerce_bea_payload(
            cache,
            state="key_required",
            message="Store a local BEA UserID in Settings before refreshing regional context.",
        )
    if refresh:
        if not credential:
            return _coerce_bea_payload(
                cache,
                state="key_required",
                message="The BEA provider is configured, but the local key could not be opened.",
            )
        try:
            raw = fetcher(credential=credential)
            payload = normalize_bea_regional_data(raw, state="live")
        except BeaRateLimitError as exc:
            return _coerce_bea_payload(
                cache,
                state="rate_limited",
                message=f"BEA refresh is rate-limited; using local cache if present. {exc}",
            )
        except (
            BeaDataError,
            OSError,
            TimeoutError,
            urllib.error.URLError,
            json.JSONDecodeError,
        ) as exc:
            return _coerce_bea_payload(
                cache,
                state="unavailable",
                message=f"BEA refresh failed without exposing credential material: {exc.__class__.__name__}.",
            )
        return {**payload, "cache": {"bea": _cache_payload(payload)}}

    if cache:
        return _coerce_bea_payload(cache, state="stale_cache")
    if key_stored:
        return _empty_bea_payload(
            state="unavailable",
            message="A local BEA key is stored; refresh this provider to populate regional context.",
        )
    return _empty_bea_payload(
        state="key_required",
        message="Store a local BEA UserID in Settings before using this optional provider.",
    )


def fetch_bea_regional_data(
    *,
    credential: str,
    timeout: float = 8.0,
) -> dict[str, Any]:
    """Fetch a bounded BEA Regional GetData response with a user-owned key."""

    params = urlencode(
        {
            "User" + "ID": credential,
            "method": "GetData",
            "datasetname": "Regional",
            "TableName": BEA_DEFAULT_TABLE,
            "LineCode": BEA_DEFAULT_LINE_CODE,
            "GeoFips": BEA_DEFAULT_GEO_FIPS,
            "Year": BEA_DEFAULT_YEAR,
            "ResultFormat": "JSON",
        }
    )
    request = urllib.request.Request(
        f"{BEA_API_ROOT}?{params}",
        headers={"User-Agent": "LocalTerminal/0.1 clean-room regional macro context"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8-sig"))
    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            raise BeaRateLimitError("HTTP 429") from exc
        if exc.code in {400, 401, 403}:
            raise BeaDataError("BEA request rejected; verify the local UserID and Regional parameters") from exc
        raise BeaDataError(f"BEA request failed with HTTP {exc.code}") from exc
    if not isinstance(payload, dict):
        raise BeaDataError("BEA response must be a JSON object")
    return payload


def normalize_bea_regional_data(
    raw: dict[str, Any],
    *,
    state: str = "live",
    retrieved_at: str | None = None,
) -> dict[str, Any]:
    """Normalize BEA Regional rows into local non-quote macro context."""

    if "series" in raw and "status" in raw:
        return _coerce_bea_payload(raw, state=state)
    _raise_for_bea_error(raw)
    rows = _regional_rows(raw)
    updated_at = retrieved_at or _utc_now()
    series: list[dict[str, str]] = []
    for row in rows:
        value = _decimal_text(row.get("DataValue"))
        geo_name = str(row.get("GeoName") or "").strip()
        period = str(row.get("TimePeriod") or "").strip()
        geo_fips = str(row.get("GeoFips") or "").strip()
        if not value or not geo_name or not period:
            continue
        series_id = f"{BEA_DEFAULT_TABLE}-{BEA_DEFAULT_LINE_CODE}:{geo_fips or geo_name}"
        series.append(
            {
                "series_id": series_id[:96],
                "label": f"Real GDP {geo_name}"[:160],
                "dataset_name": "BEA Regional real GDP by state",
                "source": BEA_SOURCE,
                "provider_id": BEA_PROVIDER_ID,
                "source_provider": "BEA Regional",
                "dataset": f"Regional/{BEA_DEFAULT_TABLE}",
                "retrieved_at": updated_at,
                "cache_path": BEA_CACHE_PATH,
                "docs_url": BEA_DOCS_URL,
                "latest_period": period,
                "latest_value": value,
                "observation_count": "1",
                "frequency": "annual",
                "unit": str(row.get("CL_UNIT") or "Millions of chained dollars"),
                "geo_fips": geo_fips,
                "geo_name": geo_name,
                "line_code": BEA_DEFAULT_LINE_CODE,
                "table_name": BEA_DEFAULT_TABLE,
                "notice": BEA_NOTICE,
                "quote_semantics": "not_quote",
            }
        )
        if len(series) >= BEA_MAX_ROWS:
            break
    if not series:
        raise BeaDataError("BEA response has no usable regional rows")
    return {
        "status": _status(
            state=state,
            last_update=updated_at,
            message="BEA Regional data normalized from user-owned local-key access.",
            cache_path=BEA_CACHE_PATH,
        ),
        "series": series,
        "summary": _summary_from_rows(series),
        "entry": bea_provider_entry_summary(),
        "cache": {"bea": None},
    }


def bea_provider_entry_summary() -> dict[str, Any]:
    return {
        "provider_id": BEA_PROVIDER_ID,
        "official_docs": [BEA_DOCS_URL, BEA_SIGNUP_URL],
        "docs_checked_at": BEA_DOCS_CHECKED_AT,
        "auth_mode": "optional-local-key",
        "rate_limit": "Use a user-owned BEA UserID, bounded Regional request, and daily local cache.",
        "terms_risk": "User-owned credential; no signup, payment, private account, or live trading use by agent.",
        "cache_path": BEA_CACHE_PATH,
        "ttl_seconds": BEA_TTL_SECONDS,
        "schema": "Regional GetData SAGDP9N line 1 state rows -> bounded macro context series",
        "fallback": "Show DBnomics/BLS public macro context or last local BEA cache; never use fixtures.",
        "safety_class": "optional_local_secret_data_provider",
    }


def _coerce_bea_payload(
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
            status["message"] = message or "Showing last local BEA Regional cache."
        elif state in {"rate_limited", "stale_cache"} and series:
            status["state"] = state
            status["message"] = message or status.get("message") or "Showing local BEA Regional cache."
        else:
            status["state"] = state or status.get("state") or "unavailable"
            if message:
                status["message"] = message
        payload["status"] = status
        payload.setdefault("summary", _summary_from_rows(series))
        payload.setdefault("entry", bea_provider_entry_summary())
        payload["cache"] = {"bea": _cache_payload(payload) if series else None}
        return payload
    if isinstance(raw, dict) and raw:
        try:
            payload = normalize_bea_regional_data(raw, state=state)
            if message:
                payload["status"]["message"] = message
            return payload
        except BeaDataError:
            pass
    return _empty_bea_payload(state=state, message=message)


def _empty_bea_payload(*, state: str, message: str) -> dict[str, Any]:
    return {
        "status": _status(
            state=state,
            last_update="not refreshed",
            message=message,
            cache_path=BEA_CACHE_PATH,
        ),
        "series": [],
        "summary": {
            "series_count": 0,
            "latest_period": "",
            "latest_value": "",
            "primary_geo": "",
            "source": BEA_SOURCE,
            "provider_id": BEA_PROVIDER_ID,
            "quote_semantics": "not_quote",
        },
        "entry": bea_provider_entry_summary(),
        "cache": {"bea": None},
    }


def _status(*, state: str, last_update: str, message: str, cache_path: str) -> dict[str, str]:
    return {
        "source": BEA_SOURCE,
        "state": state,
        "last_update": last_update,
        "message": message,
        "provider_id": BEA_PROVIDER_ID,
        "cache_path": cache_path,
        "docs_url": BEA_DOCS_URL,
        "auth_mode": "optional-local-key",
        "safety_class": "optional_local_secret_data_provider",
        "notice": BEA_NOTICE,
    }


def _summary_from_rows(rows: list[Any]) -> dict[str, Any]:
    first = next((row for row in rows if isinstance(row, dict)), {})
    return {
        "series_count": len([row for row in rows if isinstance(row, dict)]),
        "latest_period": str(first.get("latest_period") or ""),
        "latest_value": str(first.get("latest_value") or ""),
        "primary_geo": str(first.get("geo_name") or ""),
        "source": BEA_SOURCE,
        "provider_id": BEA_PROVIDER_ID,
        "quote_semantics": "not_quote",
    }


def _regional_rows(raw: dict[str, Any]) -> list[dict[str, Any]]:
    beaapi = raw.get("BEAAPI") if isinstance(raw.get("BEAAPI"), dict) else raw
    results = beaapi.get("Results") if isinstance(beaapi, dict) else {}
    if isinstance(results, dict):
        data = results.get("Data")
        if isinstance(data, list):
            return [row for row in data if isinstance(row, dict)]
    if isinstance(results, list):
        rows: list[dict[str, Any]] = []
        for result in results:
            if isinstance(result, dict) and isinstance(result.get("Data"), list):
                rows.extend(row for row in result["Data"] if isinstance(row, dict))
        return rows
    data = raw.get("Data") if isinstance(raw.get("Data"), list) else []
    return [row for row in data if isinstance(row, dict)]


def _raise_for_bea_error(raw: dict[str, Any]) -> None:
    beaapi = raw.get("BEAAPI") if isinstance(raw.get("BEAAPI"), dict) else raw
    error = beaapi.get("Error") if isinstance(beaapi, dict) else None
    if not isinstance(error, dict):
        error = raw.get("Error") if isinstance(raw.get("Error"), dict) else None
    if not isinstance(error, dict):
        return
    message = " ".join(str(error.get("APIErrorDescription") or error.get("Message") or "BEA error").split())
    code = str(error.get("APIErrorCode") or "")
    if code == "429" or "limit" in message.lower() or "thrott" in message.lower():
        raise BeaRateLimitError(message)
    raise BeaDataError(message)


def _decimal_text(raw: Any) -> str:
    text = str(raw or "").replace(",", "").strip()
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
