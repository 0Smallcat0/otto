"""BLS public no-key macro/labor data adapter."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any


BLS_PROVIDER_ID = "bls_public_macro"
BLS_SOURCE = "bls_public_api"
BLS_API_ROOT = "https://api.bls.gov/publicAPI/v2/timeseries/data"
BLS_DOCS_URL = "https://www.bls.gov/developers/api_signature_v2.htm"
BLS_GETTING_STARTED_URL = "https://www.bls.gov/developers/home.htm"
BLS_UNIX_SAMPLE_URL = "https://www.bls.gov/developers/api_unix_v2.htm"
BLS_DOCS_CHECKED_AT = "2026-05-24"
BLS_CACHE_PATH = "market_data/macro/bls/latest_series.json"
BLS_TTL_SECONDS = 86400
BLS_NOTICE = (
    "BLS public API series are official macro/labor context data, not executable "
    "market quotes or trading signals."
)

BLS_DEFAULT_SERIES: tuple[dict[str, str], ...] = (
    {
        "series_id": "LNS14000000",
        "label": "Civilian unemployment rate",
        "dataset_name": "Labor Force Statistics from the Current Population Survey",
        "source_provider": "BLS CPS",
        "summary_key": "unemployment_rate",
        "unit": "percent",
        "frequency": "monthly",
    },
    {
        "series_id": "CES0000000001",
        "label": "All employees, total nonfarm",
        "dataset_name": "Current Employment Statistics",
        "source_provider": "BLS CES",
        "summary_key": "nonfarm_payrolls",
        "unit": "thousands of persons",
        "frequency": "monthly",
    },
    {
        "series_id": "CUSR0000SA0",
        "label": "CPI-U all items, seasonally adjusted",
        "dataset_name": "Consumer Price Index",
        "source_provider": "BLS CPI",
        "summary_key": "cpi_u",
        "unit": "index 1982-84=100",
        "frequency": "monthly",
    },
)


class BlsDataError(ValueError):
    """Raised when BLS public macro data is invalid or unavailable."""


class BlsRateLimitError(BlsDataError):
    """Raised when BLS reports throttling or request rejection."""


def bls_data_payload(
    cache: dict[str, Any] | None,
    *,
    fetcher: Any | None = None,
    refresh: bool = False,
) -> dict[str, Any]:
    """Return BLS latest macro/labor series without credentials or fixtures."""

    fetcher = fetcher or fetch_bls_latest_series
    if refresh:
        try:
            raw = fetcher(series_ids=[series["series_id"] for series in BLS_DEFAULT_SERIES])
            payload = normalize_bls_latest_series(raw, state="live")
        except BlsRateLimitError as exc:
            return _coerce_bls_payload(
                cache,
                state="rate_limited",
                message=f"BLS refresh is rate-limited; using local cache if present. {exc}",
            )
        except (
            BlsDataError,
            OSError,
            TimeoutError,
            urllib.error.URLError,
            json.JSONDecodeError,
        ) as exc:
            return _coerce_bls_payload(
                cache,
                state="unavailable",
                message=f"BLS public macro refresh failed: {exc.__class__.__name__}.",
            )
        return {**payload, "cache": {"bls": _cache_payload(payload)}}

    if cache:
        return _coerce_bls_payload(cache, state="stale_cache")
    return _empty_bls_payload(
        state="unavailable",
        message="No BLS public macro cache is available yet.",
    )


def fetch_bls_latest_series(
    *,
    series_ids: list[str] | tuple[str, ...] | None = None,
    timeout: float = 8.0,
) -> dict[str, Any]:
    """Fetch latest BLS observations for a bounded no-key series list."""

    payloads: list[dict[str, Any]] = []
    for series_id in list(series_ids or [series["series_id"] for series in BLS_DEFAULT_SERIES])[:6]:
        safe_series_id = _safe_series_id(series_id)
        params = urllib.parse.urlencode({"latest": "true"})
        request = urllib.request.Request(
            f"{BLS_API_ROOT}/{urllib.parse.quote(safe_series_id, safe='')}?{params}",
            headers={"User-Agent": "LocalTerminal/0.1 clean-room local macro research"},
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw_payload = json.loads(response.read().decode("utf-8-sig"))
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                raise BlsRateLimitError("HTTP 429") from exc
            if exc.code in {400, 403}:
                raise BlsDataError("BLS request rejected; verify the public series id") from exc
            raise BlsDataError(f"BLS request failed with HTTP {exc.code}") from exc
        if not isinstance(raw_payload, dict):
            raise BlsDataError("BLS response must be a JSON object")
        payloads.append({"series_id": safe_series_id, "payload": raw_payload})
    return {"series": payloads}


def normalize_bls_latest_series(
    raw: dict[str, Any],
    *,
    state: str = "live",
    retrieved_at: str | None = None,
) -> dict[str, Any]:
    """Normalize latest BLS observations into local macro series rows."""

    if "series" in raw and "status" in raw:
        return _coerce_bls_payload(raw, state=state)

    updated_at = retrieved_at or _utc_now()
    rows: list[dict[str, str]] = []
    observations: list[dict[str, str]] = []
    for item in _raw_series_items(raw):
        series_id = _safe_series_id(str(item.get("series_id") or item.get("seriesID") or ""))
        catalog = _series_catalog(series_id)
        data_rows = item.get("data") if isinstance(item.get("data"), list) else []
        if not data_rows:
            payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
            data_rows = _data_rows_from_bls_response(payload)
            series_id = _safe_series_id(str(item.get("series_id") or series_id))
            catalog = _series_catalog(series_id)
        usable_rows = _usable_observations(data_rows)
        if not usable_rows:
            continue
        latest = usable_rows[0]
        rows.append(
            {
                "series_id": series_id,
                "label": catalog["label"],
                "dataset_name": catalog["dataset_name"],
                "source": BLS_SOURCE,
                "provider_id": BLS_PROVIDER_ID,
                "source_provider": catalog["source_provider"],
                "dataset": "timeseries/latest",
                "retrieved_at": updated_at,
                "cache_path": BLS_CACHE_PATH,
                "docs_url": BLS_DOCS_URL,
                "latest_period": latest["period_label"],
                "latest_value": latest["value"],
                "observation_count": len(usable_rows),
                "frequency": catalog["frequency"],
                "unit": catalog["unit"],
                "indexed_at": updated_at,
                "notice": BLS_NOTICE,
                "summary_key": catalog["summary_key"],
            }
        )
        for observation in usable_rows[:3]:
            observations.append(
                {
                    "series_id": series_id,
                    "period": observation["period_label"],
                    "value": observation["value"],
                    "unit": catalog["unit"],
                }
            )
    if not rows:
        raise BlsDataError("BLS response has no usable latest series values")
    return {
        "status": _status(
            state=state,
            last_update=updated_at,
            message="BLS latest macro/labor series normalized from public no-key API.",
            cache_path=BLS_CACHE_PATH,
        ),
        "series": rows,
        "observations": observations,
        "summary": _summary_from_rows(rows),
        "entry": bls_provider_entry_summary(),
        "cache": {"bls": None},
    }


def bls_provider_entry_summary() -> dict[str, Any]:
    return {
        "provider_id": BLS_PROVIDER_ID,
        "official_docs": [BLS_DOCS_URL, BLS_GETTING_STARTED_URL, BLS_UNIX_SAMPLE_URL],
        "docs_checked_at": BLS_DOCS_CHECKED_AT,
        "auth_mode": "no-key",
        "rate_limit": "Use a daily local cache and bounded latest-series requests for public BLS API data.",
        "terms_risk": "Public government macro/labor data; preserve BLS source attribution.",
        "cache_path": BLS_CACHE_PATH,
        "ttl_seconds": BLS_TTL_SECONDS,
        "schema": "latest timeseries observations -> macro/labor context rows",
        "fallback": "Show last local cache or unavailable state; never use fixture values as runtime data.",
        "safety_class": "public_read_only_macro",
    }


def _coerce_bls_payload(
    raw: dict[str, Any] | None,
    *,
    state: str,
    message: str = "",
) -> dict[str, Any]:
    if isinstance(raw, dict) and "series" in raw and "status" in raw:
        payload = dict(raw)
        status = dict(payload.get("status") or {})
        series = payload.get("series") if isinstance(payload.get("series"), list) else []
        if series and state == "unavailable":
            status["state"] = "stale_cache"
            status["message"] = message or "Showing last local BLS cache after refresh failure."
        elif state in {"rate_limited", "stale_cache"} and series:
            status["state"] = state
            status["message"] = message or status.get("message") or "Showing local BLS cache."
        else:
            status["state"] = state or status.get("state") or "unavailable"
            if message:
                status["message"] = message
        payload["status"] = status
        cache_payload = _cache_payload(payload)
        payload["cache"] = {"bls": cache_payload if series else None}
        payload.setdefault("summary", _summary_from_rows(series))
        payload.setdefault("entry", bls_provider_entry_summary())
        payload.setdefault("observations", [])
        return payload
    if isinstance(raw, dict) and raw:
        try:
            payload = normalize_bls_latest_series(raw, state=state)
            if message:
                payload["status"]["message"] = message
            return payload
        except BlsDataError:
            pass
    return _empty_bls_payload(state=state, message=message)


def _empty_bls_payload(*, state: str, message: str) -> dict[str, Any]:
    return {
        "status": _status(
            state=state,
            last_update="not refreshed",
            message=message,
            cache_path=BLS_CACHE_PATH,
        ),
        "series": [],
        "observations": [],
        "summary": {
            "series_count": 0,
            "latest_period": "",
            "unemployment_rate": "",
            "nonfarm_payrolls": "",
            "cpi_u": "",
            "source": BLS_SOURCE,
            "provider_id": BLS_PROVIDER_ID,
        },
        "entry": bls_provider_entry_summary(),
        "cache": {"bls": None},
    }


def _status(*, state: str, last_update: str, message: str, cache_path: str) -> dict[str, str]:
    return {
        "source": BLS_SOURCE,
        "state": state,
        "last_update": last_update,
        "message": message,
        "provider_id": BLS_PROVIDER_ID,
        "cache_path": cache_path,
        "docs_url": BLS_DOCS_URL,
        "auth_mode": "no-key",
        "safety_class": "public_read_only_macro",
        "notice": BLS_NOTICE,
    }


def _raw_series_items(raw: dict[str, Any]) -> list[dict[str, Any]]:
    series = raw.get("series") if isinstance(raw.get("series"), list) else []
    if series:
        return [item for item in series if isinstance(item, dict)]
    results = raw.get("Results")
    if isinstance(results, dict):
        result_series = results.get("series")
        if isinstance(result_series, list):
            return [item for item in result_series if isinstance(item, dict)]
    if isinstance(results, list):
        items: list[dict[str, Any]] = []
        for result in results:
            if not isinstance(result, dict):
                continue
            result_series = result.get("series")
            if isinstance(result_series, list):
                items.extend(item for item in result_series if isinstance(item, dict))
        return items
    return []


def _data_rows_from_bls_response(raw: dict[str, Any]) -> list[Any]:
    results = raw.get("Results")
    if isinstance(results, dict):
        series = results.get("series")
        if isinstance(series, list) and series and isinstance(series[0], dict):
            return series[0].get("data") if isinstance(series[0].get("data"), list) else []
    if isinstance(results, list):
        for result in results:
            if not isinstance(result, dict):
                continue
            series = result.get("series")
            if isinstance(series, list) and series and isinstance(series[0], dict):
                return series[0].get("data") if isinstance(series[0].get("data"), list) else []
    return []


def _usable_observations(rows: list[Any]) -> list[dict[str, str]]:
    observations: list[dict[str, str]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        value = _decimal_text(row.get("value"))
        if not value:
            continue
        year = str(row.get("year") or "")
        period = str(row.get("periodName") or row.get("period") or "")
        period_label = f"{period} {year}".strip() if year else period
        observations.append(
            {
                "period_label": period_label,
                "value": value,
            }
        )
    return observations


def _summary_from_rows(rows: list[Any]) -> dict[str, Any]:
    summary = {
        "series_count": len([row for row in rows if isinstance(row, dict)]),
        "latest_period": "",
        "unemployment_rate": "",
        "nonfarm_payrolls": "",
        "cpi_u": "",
        "source": BLS_SOURCE,
        "provider_id": BLS_PROVIDER_ID,
    }
    for row in rows:
        if not isinstance(row, dict):
            continue
        if not summary["latest_period"]:
            summary["latest_period"] = str(row.get("latest_period") or "")
        key = str(row.get("summary_key") or _series_catalog(str(row.get("series_id") or ""))["summary_key"])
        if key in summary:
            summary[key] = str(row.get("latest_value") or "")
    return summary


def _series_catalog(series_id: str) -> dict[str, str]:
    safe_series_id = _safe_series_id(series_id)
    for row in BLS_DEFAULT_SERIES:
        if row["series_id"] == safe_series_id:
            return row
    return {
        "series_id": safe_series_id,
        "label": safe_series_id,
        "dataset_name": "BLS public timeseries",
        "source_provider": "BLS",
        "summary_key": "bls_series",
        "unit": "",
        "frequency": "",
    }


def _safe_series_id(series_id: str) -> str:
    return (
        "".join(ch for ch in str(series_id).upper() if ch.isalnum() or ch in {"_", "-", "#"})[:80]
        or BLS_DEFAULT_SERIES[0]["series_id"]
    )


def _decimal_text(raw: Any) -> str:
    try:
        value = Decimal(str(raw))
    except (InvalidOperation, ValueError):
        return ""
    return format(value.normalize(), "f")


def _cache_payload(payload: dict[str, Any]) -> dict[str, Any]:
    cache_payload = dict(payload)
    cache_payload.pop("cache", None)
    return cache_payload


def _utc_now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
