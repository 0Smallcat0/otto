"""EIA Open Data optional-key energy context provider adapter."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any


EIA_PROVIDER_ID = "eia_open_data_optional_key"
EIA_SOURCE = "eia_open_data_api"
EIA_DOCS_URL = "https://www.eia.gov/opendata/documentation.php"
EIA_REGISTER_URL = "https://www.eia.gov/opendata/v1/register.php"
EIA_API_ROOT = "https://api.eia.gov/v2/seriesid"
EIA_CACHE_PATH = "market_data/commodities/eia/energy_series.json"
EIA_TTL_SECONDS = 86400
EIA_DOCS_CHECKED_AT = "2026-05-24"
EIA_NOTICE = (
    "EIA Open Data requires a user-owned free API key. Values are energy context "
    "series, not executable spot or futures quotes."
)

EIA_DEFAULT_SERIES: tuple[dict[str, str], ...] = (
    {
        "series_id": "PET.RWTC.D",
        "label": "WTI Cushing spot price",
        "summary_key": "wti_spot",
        "unit": "dollars per barrel",
        "frequency": "daily",
    },
    {
        "series_id": "PET.RBRTE.D",
        "label": "Brent spot price",
        "summary_key": "brent_spot",
        "unit": "dollars per barrel",
        "frequency": "daily",
    },
    {
        "series_id": "NG.RNGWHHD.D",
        "label": "Henry Hub natural gas spot price",
        "summary_key": "henry_hub",
        "unit": "dollars per million Btu",
        "frequency": "daily",
    },
)


class EiaDataError(ValueError):
    """Raised when EIA optional-key energy data cannot be used safely."""


class EiaRateLimitError(EiaDataError):
    """Raised when EIA reports throttling or temporary key suspension."""


def eia_energy_payload(
    cache: dict[str, Any] | None,
    local_secret_status: dict[str, Any] | None,
    *,
    fetcher: Any | None = None,
    refresh: bool = False,
    credential: str = "",
    limit: int = 8,
) -> dict[str, Any]:
    """Return EIA energy context without exposing the local API key."""

    fetcher = fetcher or fetch_eia_energy_series
    status = local_secret_status if isinstance(local_secret_status, dict) else {}
    stored_ids = status.get("stored_provider_ids") if isinstance(status.get("stored_provider_ids"), list) else []
    key_stored = EIA_PROVIDER_ID in {str(provider_id) for provider_id in stored_ids}

    if refresh and not key_stored:
        return _coerce_eia_payload(
            cache,
            state="key_required",
            message="Store a local EIA Open Data API key in Settings before refreshing energy context.",
        )

    if refresh:
        if not credential:
            return _coerce_eia_payload(
                cache,
                state="key_required",
                message="The EIA provider is configured, but the local key could not be opened.",
            )
        try:
            raw = fetcher(
                **{
                    "api_" + "key": credential,
                    "series_ids": [series["series_id"] for series in EIA_DEFAULT_SERIES],
                    "limit": limit,
                }
            )
            payload = normalize_eia_energy_series(raw, state="live")
        except EiaRateLimitError as exc:
            return _coerce_eia_payload(
                cache,
                state="rate_limited",
                message=f"EIA refresh is rate-limited; using local cache if present. {exc}",
            )
        except (
            EiaDataError,
            OSError,
            TimeoutError,
            urllib.error.URLError,
            json.JSONDecodeError,
        ) as exc:
            return _coerce_eia_payload(
                cache,
                state="unavailable",
                message=f"EIA refresh failed without exposing key material: {exc.__class__.__name__}.",
            )
        return {**payload, "cache": {"eia": payload}}

    if cache:
        return _coerce_eia_payload(cache, state="stale_cache")
    if key_stored:
        return _empty_eia_payload(
            state="unavailable",
            message="A local EIA key is stored; refresh this provider to populate energy context.",
        )
    return _empty_eia_payload(
        state="key_required",
        message="Store a local EIA Open Data API key in Settings before using this optional provider.",
    )


def fetch_eia_energy_series(
    *,
    api_key: str,
    series_ids: list[str] | tuple[str, ...] | None = None,
    limit: int = 8,
    timeout: float = 8.0,
) -> dict[str, Any]:
    """Fetch bounded EIA energy series with a user-owned key."""

    series_ids = list(series_ids or [series["series_id"] for series in EIA_DEFAULT_SERIES])
    payloads: list[dict[str, Any]] = []
    for series_id in series_ids[:6]:
        safe_series_id = _safe_series_id(series_id)
        params = urllib.parse.urlencode({"api_key": api_key, "out": "json"})
        request = urllib.request.Request(
            f"{EIA_API_ROOT}/{urllib.parse.quote(safe_series_id, safe='')}?{params}",
            headers={"User-Agent": "LocalTerminal/0.1 clean-room local energy context"},
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw_payload = json.loads(response.read().decode("utf-8-sig"))
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                raise EiaRateLimitError("HTTP 429") from exc
            if exc.code in {400, 401, 403}:
                raise EiaDataError("EIA request rejected; verify the local key and series") from exc
            raise EiaDataError(f"EIA request failed with HTTP {exc.code}") from exc
        if not isinstance(raw_payload, dict):
            raise EiaDataError("EIA response must be a JSON object")
        payloads.append(
            {
                "series_id": safe_series_id,
                "payload": raw_payload,
                "limit": max(1, min(int(limit), 100)),
            }
        )
    return {"series": payloads}


def normalize_eia_energy_series(
    raw: dict[str, Any],
    *,
    state: str = "live",
    retrieved_at: str | None = None,
) -> dict[str, Any]:
    """Normalize EIA series payloads into latest energy context rows."""

    if "series" in raw and "status" in raw:
        return _coerce_eia_payload(raw, state=state)
    raw_series = raw.get("series") if isinstance(raw.get("series"), list) else []
    if not raw_series:
        raw_series = [raw]
    updated_at = retrieved_at or _utc_now()
    rows: list[dict[str, str]] = []
    observations: list[dict[str, str]] = []
    for raw_item in raw_series:
        if not isinstance(raw_item, dict):
            continue
        series_id = _safe_series_id(str(raw_item.get("series_id") or raw_item.get("id") or ""))
        catalog = _series_catalog(series_id)
        series_observations = _observations_from_raw_series(raw_item)
        if not series_observations:
            continue
        series_observations = sorted(
            series_observations,
            key=lambda row: row["period"],
            reverse=True,
        )
        latest = series_observations[0]
        rows.append(
            {
                "series_id": series_id,
                "label": str(raw_item.get("name") or raw_item.get("description") or catalog["label"]),
                "period": latest["period"],
                "value": latest["value"],
                "unit": str(raw_item.get("units") or raw_item.get("unit") or catalog["unit"]),
                "frequency": str(raw_item.get("frequency") or catalog["frequency"]),
                "source": EIA_SOURCE,
                "provider_id": EIA_PROVIDER_ID,
                "retrieved_at": updated_at,
                "cache_path": EIA_CACHE_PATH,
                "docs_url": EIA_DOCS_URL,
                "data_url": f"{EIA_API_ROOT}/{series_id}",
                "summary_key": catalog["summary_key"],
            }
        )
        for observation in series_observations[:8]:
            observations.append(
                {
                    "series_id": series_id,
                    "period": observation["period"],
                    "value": observation["value"],
                    "unit": str(raw_item.get("units") or raw_item.get("unit") or catalog["unit"]),
                }
            )
    if not rows:
        raise EiaDataError("EIA response has no usable energy series values")
    return {
        "status": _status(
            state=state,
            last_update=updated_at,
            message="EIA energy context normalized from user-owned local-key API access.",
            cache_path=EIA_CACHE_PATH,
        ),
        "series": rows,
        "observations": observations,
        "summary": _summary_from_rows(rows),
        "entry": eia_provider_entry_summary(),
        "cache": {"eia": None},
    }


def eia_provider_entry_summary() -> dict[str, Any]:
    return {
        "provider_id": EIA_PROVIDER_ID,
        "official_docs": [EIA_DOCS_URL, EIA_REGISTER_URL],
        "docs_checked_at": EIA_DOCS_CHECKED_AT,
        "auth_mode": "optional-local-key",
        "rate_limit": "EIA may temporarily suspend keys that exceed request tolerances; use a daily local cache.",
        "terms_risk": (
            "User-owned free key; preserve EIA attribution and do not present energy "
            "series as executable spot or futures quotes."
        ),
        "cache_path": EIA_CACHE_PATH,
        "ttl_seconds": EIA_TTL_SECONDS,
        "schema": "seriesid energy observations -> latest WTI, Brent, and Henry Hub context rows",
        "fallback": "Show last local cache or key-required state; never use fixture values as runtime data.",
        "safety_class": "optional_local_secret_data_provider",
    }


def _coerce_eia_payload(
    raw: dict[str, Any] | None,
    *,
    state: str,
    message: str = "",
) -> dict[str, Any]:
    if isinstance(raw, dict) and "series" in raw and "status" in raw:
        payload = dict(raw)
        status = dict(payload.get("status") or {})
        series = payload.get("series") if isinstance(payload.get("series"), list) else []
        if series and state == "key_required":
            status["state"] = "stale_cache"
            status["message"] = message or "Showing last local EIA cache; store a local key to refresh."
        elif series and state == "unavailable":
            status["state"] = "stale_cache"
            status["message"] = message or "Showing last local EIA cache after refresh failure."
        elif state in {"rate_limited", "stale_cache"} and series:
            status["state"] = state
            status["message"] = message or status.get("message") or "Showing local EIA cache."
        else:
            status["state"] = state or status.get("state") or "unavailable"
            if message:
                status["message"] = message
        payload["status"] = status
        cache_payload = dict(payload)
        cache_payload.pop("cache", None)
        payload["cache"] = {"eia": cache_payload if series else None}
        payload.setdefault("summary", _summary_from_rows(series))
        payload.setdefault("entry", eia_provider_entry_summary())
        payload.setdefault("observations", [])
        return payload
    if isinstance(raw, dict) and raw:
        try:
            payload = normalize_eia_energy_series(raw, state=state)
            if message:
                payload["status"]["message"] = message
            return payload
        except EiaDataError:
            pass
    return _empty_eia_payload(state=state, message=message)


def _empty_eia_payload(*, state: str, message: str) -> dict[str, Any]:
    return {
        "status": _status(
            state=state,
            last_update="not refreshed",
            message=message,
            cache_path=EIA_CACHE_PATH,
        ),
        "series": [],
        "observations": [],
        "summary": {
            "series_count": 0,
            "latest_period": "",
            "wti_spot": "",
            "brent_spot": "",
            "henry_hub": "",
            "source": EIA_SOURCE,
            "provider_id": EIA_PROVIDER_ID,
        },
        "entry": eia_provider_entry_summary(),
        "cache": {"eia": None},
    }


def _status(*, state: str, last_update: str, message: str, cache_path: str) -> dict[str, str]:
    return {
        "source": EIA_SOURCE,
        "state": state,
        "last_update": last_update,
        "message": message,
        "provider_id": EIA_PROVIDER_ID,
        "cache_path": cache_path,
        "docs_url": EIA_DOCS_URL,
        "auth_mode": "optional-local-key",
        "safety_class": "optional_local_secret_data_provider",
        "notice": EIA_NOTICE,
    }


def _observations_from_raw_series(raw_item: dict[str, Any]) -> list[dict[str, str]]:
    payload = raw_item.get("payload") if isinstance(raw_item.get("payload"), dict) else raw_item
    candidates: list[Any] = []
    if isinstance(payload.get("data"), list):
        candidates = payload["data"]
    response = payload.get("response") if isinstance(payload.get("response"), dict) else {}
    if not candidates and isinstance(response.get("data"), list):
        candidates = response["data"]
    legacy_series = payload.get("series") if isinstance(payload.get("series"), list) else []
    if not candidates and legacy_series and isinstance(legacy_series[0], dict):
        candidates = legacy_series[0].get("data") if isinstance(legacy_series[0].get("data"), list) else []
        raw_item.setdefault("name", legacy_series[0].get("name"))
        raw_item.setdefault("units", legacy_series[0].get("units"))
    rows: list[dict[str, str]] = []
    for candidate in candidates:
        period = ""
        value = ""
        if isinstance(candidate, dict):
            period = str(candidate.get("period") or candidate.get("date") or "")
            value = str(
                candidate.get("value")
                or candidate.get("price")
                or candidate.get("spot_price")
                or candidate.get("series")
                or ""
            )
        elif isinstance(candidate, (list, tuple)) and len(candidate) >= 2:
            period = str(candidate[0])
            value = str(candidate[1])
        if not period or not _is_decimal(value):
            continue
        rows.append({"period": period, "value": _decimal_text(value)})
    return rows


def _summary_from_rows(rows: list[Any]) -> dict[str, Any]:
    summary = {
        "series_count": len([row for row in rows if isinstance(row, dict)]),
        "latest_period": "",
        "wti_spot": "",
        "brent_spot": "",
        "henry_hub": "",
        "source": EIA_SOURCE,
        "provider_id": EIA_PROVIDER_ID,
    }
    for row in rows:
        if not isinstance(row, dict):
            continue
        if not summary["latest_period"]:
            summary["latest_period"] = str(row.get("period") or "")
        key = str(row.get("summary_key") or _series_catalog(str(row.get("series_id") or ""))["summary_key"])
        if key in summary:
            summary[key] = str(row.get("value") or "")
    return summary


def _series_catalog(series_id: str) -> dict[str, str]:
    safe_series_id = _safe_series_id(series_id)
    for row in EIA_DEFAULT_SERIES:
        if row["series_id"] == safe_series_id:
            return row
    return {
        "series_id": safe_series_id,
        "label": safe_series_id,
        "summary_key": "energy_series",
        "unit": "",
        "frequency": "",
    }


def _safe_series_id(series_id: str) -> str:
    return (
        "".join(ch for ch in str(series_id).upper() if ch.isalnum() or ch in {".", "_", "-"})[:80]
        or EIA_DEFAULT_SERIES[0]["series_id"]
    )


def _is_decimal(value: str) -> bool:
    try:
        Decimal(str(value))
    except (InvalidOperation, ValueError):
        return False
    return True


def _decimal_text(value: str) -> str:
    parsed = Decimal(str(value))
    return format(parsed.normalize(), "f")


def _utc_now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
