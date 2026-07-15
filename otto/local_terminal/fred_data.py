"""FRED optional-key macro data adapter with local-only credential gates."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode


FRED_PROVIDER_ID = "fred_optional_local_key"
FRED_SOURCE = "fred_api"
FRED_DEFAULT_SERIES_ID = "DGS10"
FRED_DEFAULT_LABEL = "10-Year Treasury Constant Maturity Rate"
FRED_SERIES_OBSERVATIONS_DOC = "https://fred.stlouisfed.org/docs/api/fred/series_observations.html"
FRED_API_KEY_DOC = "https://fred.stlouisfed.org/docs/api/api_key.html"
FRED_TERMS_DOC = "https://fred.stlouisfed.org/docs/api/terms_of_use.html"
FRED_DOCS_CHECKED_AT = "2026-05-23"
FRED_CACHE_PATH = f"market_data/macro/fred/{FRED_DEFAULT_SERIES_ID}.json"
FRED_TTL_SECONDS = 86400
FRED_NOTICE = (
    "Uses the FRED API; not endorsed or certified by the Federal Reserve Bank of St. Louis."
)


class FredDataError(ValueError):
    """Raised when FRED optional-key macro data cannot be used safely."""


class FredRateLimitError(FredDataError):
    """Raised when FRED returns a throttling or rate-limit response."""


def fred_data_payload(
    cache: dict[str, Any] | None,
    local_secret_status: dict[str, Any] | None,
    *,
    fetcher: Any | None = None,
    refresh: bool = False,
    credential: str = "",
    series_id: str = FRED_DEFAULT_SERIES_ID,
    limit: int = 12,
) -> dict[str, Any]:
    """Return FRED macro data without exposing the local API key."""

    fetcher = fetcher or fetch_fred_series_observations
    status = local_secret_status if isinstance(local_secret_status, dict) else {}
    stored_ids = status.get("stored_provider_ids") if isinstance(status.get("stored_provider_ids"), list) else []
    key_stored = FRED_PROVIDER_ID in {str(provider_id) for provider_id in stored_ids}

    if refresh and not key_stored:
        return _coerce_fred_payload(
            cache,
            state="key_required",
            message="Store a local FRED API key in Settings before refreshing this provider.",
        )

    if refresh:
        if not credential:
            return _coerce_fred_payload(
                cache,
                state="key_required",
                message="The FRED provider is configured, but the local key could not be opened.",
            )
        try:
            raw = fetcher(**{"series_id": series_id, "api_" + "key": credential, "limit": limit})
            payload = normalize_fred_series_observations(raw, series_id=series_id, state="live")
        except FredRateLimitError as exc:
            return _coerce_fred_payload(
                cache,
                state="rate_limited",
                message=f"FRED refresh is rate-limited; using local cache if present. {exc}",
            )
        except (
            FredDataError,
            OSError,
            TimeoutError,
            urllib.error.URLError,
            json.JSONDecodeError,
        ) as exc:
            return _coerce_fred_payload(
                cache,
                state="unavailable",
                message=f"FRED refresh failed without exposing key material: {exc.__class__.__name__}.",
            )
        return {**payload, "cache": {"fred": payload}}

    if cache:
        return _coerce_fred_payload(cache, state="stale_cache")
    if key_stored:
        return _empty_fred_payload(
            state="unavailable",
            message="A local FRED key is stored; refresh this provider to populate macro cache.",
        )
    return _empty_fred_payload(
        state="key_required",
        message="Store a local FRED API key in Settings before using this optional provider.",
    )


def fetch_fred_series_observations(
    *,
    series_id: str,
    api_key: str,
    limit: int = 12,
    timeout: float = 8.0,
) -> dict[str, Any]:
    """Fetch a FRED series observations payload with a user-owned key."""

    params = urlencode(
        {
            "series_id": _safe_series_id(series_id),
            "api_key": api_key,
            "file_type": "json",
            "sort_order": "desc",
            "limit": max(1, min(int(limit), 1000)),
        }
    )
    request = urllib.request.Request(
        f"https://api.stlouisfed.org/fred/series/observations?{params}",
        headers={"User-Agent": "LocalTerminal/0.1 clean-room local macro research"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            raise FredRateLimitError("HTTP 429") from exc
        if exc.code in {400, 401, 403}:
            raise FredDataError("FRED request rejected; verify the local key and series") from exc
        raise FredDataError(f"FRED request failed with HTTP {exc.code}") from exc
    if not isinstance(payload, dict):
        raise FredDataError("FRED response must be a JSON object")
    return payload


def normalize_fred_series_observations(
    raw: dict[str, Any],
    *,
    series_id: str = FRED_DEFAULT_SERIES_ID,
    state: str = "live",
    retrieved_at: str | None = None,
) -> dict[str, Any]:
    """Normalize FRED observations into local macro series rows."""

    if "series" in raw and "status" in raw:
        return _coerce_fred_payload(raw, state=state)
    observations = raw.get("observations") if isinstance(raw.get("observations"), list) else []
    rows: list[dict[str, str]] = []
    for row in observations:
        if not isinstance(row, dict):
            continue
        value = str(row.get("value") or "")
        if value in {"", "."}:
            continue
        rows.append(
            {
                "date": str(row.get("date") or ""),
                "value": value,
                "realtime_start": str(row.get("realtime_start") or ""),
                "realtime_end": str(row.get("realtime_end") or ""),
            }
        )
    if not rows:
        raise FredDataError("FRED observations response has no usable values")

    updated_at = retrieved_at or _utc_now()
    safe_series_id = _safe_series_id(series_id)
    latest = rows[0]
    cache_path = f"market_data/macro/fred/{safe_series_id}.json"
    return {
        "status": _status(
            state=state,
            last_update=updated_at,
            message="FRED observations normalized from user-owned local-key API access.",
            cache_path=cache_path,
        ),
        "series": [
            {
                "series_id": safe_series_id,
                "label": FRED_DEFAULT_LABEL if safe_series_id == FRED_DEFAULT_SERIES_ID else safe_series_id,
                "dataset_name": "FRED economic data",
                "source": FRED_SOURCE,
                "provider_id": FRED_PROVIDER_ID,
                "source_provider": "FRED API",
                "dataset": "series/observations",
                "retrieved_at": updated_at,
                "cache_path": cache_path,
                "docs_url": FRED_SERIES_OBSERVATIONS_DOC,
                "latest_period": latest["date"],
                "latest_value": latest["value"],
                "observation_count": len(rows),
                "frequency": str(raw.get("frequency") or ""),
                "indexed_at": updated_at,
                "notice": FRED_NOTICE,
            }
        ],
        "observations": rows,
        "summary": {
            "series_id": safe_series_id,
            "latest_period": latest["date"],
            "latest_value": latest["value"],
            "observation_count": len(rows),
            "source": FRED_SOURCE,
            "provider_id": FRED_PROVIDER_ID,
        },
        "entry": fred_provider_entry_summary(),
        "cache": {"fred": None},
    }


def fred_provider_entry_summary() -> dict[str, Any]:
    return {
        "provider_id": FRED_PROVIDER_ID,
        "official_docs": [FRED_SERIES_OBSERVATIONS_DOC, FRED_TERMS_DOC],
        "docs_checked_at": FRED_DOCS_CHECKED_AT,
        "auth_mode": "optional-local-key",
        "rate_limit": "FRED terms allow limits and throttling; keep a daily local cache.",
        "terms_risk": (
            "User-owned credential, required source notice, no provider logo/trademark use, "
            "and no endorsement implication."
        ),
        "cache_path": FRED_CACHE_PATH,
        "ttl_seconds": FRED_TTL_SECONDS,
        "schema": "series observations -> latest macro observation and recent rows",
        "fallback": "Show last local cache or key-required state; never use fixture values as runtime data.",
        "safety_class": "optional_local_secret_data_provider",
    }


def _coerce_fred_payload(
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
            status["message"] = (
                message or "Showing last local FRED cache; store a local key to refresh."
            )
        elif series and state == "unavailable":
            status["state"] = "stale_cache"
            status["message"] = message or "Showing last local FRED cache after refresh failure."
        elif state in {"rate_limited", "stale_cache"} and series:
            status["state"] = state
            status["message"] = message or status.get("message") or "Showing local FRED cache."
        else:
            status["state"] = state or status.get("state") or "unavailable"
            if message:
                status["message"] = message
        payload["status"] = status
        payload["cache"] = {"fred": payload if series else None}
        payload.setdefault("summary", _summary_from_series(series))
        payload.setdefault("entry", fred_provider_entry_summary())
        return payload
    if isinstance(raw, dict) and raw:
        try:
            payload = normalize_fred_series_observations(raw, state=state)
            if message:
                payload["status"]["message"] = message
            return payload
        except FredDataError:
            pass
    return _empty_fred_payload(state=state, message=message)


def _empty_fred_payload(*, state: str, message: str) -> dict[str, Any]:
    return {
        "status": _status(
            state=state,
            last_update="not refreshed",
            message=message,
            cache_path=FRED_CACHE_PATH,
        ),
        "series": [],
        "observations": [],
        "summary": {
            "series_id": FRED_DEFAULT_SERIES_ID,
            "latest_period": "",
            "latest_value": "",
            "observation_count": 0,
            "source": FRED_SOURCE,
            "provider_id": FRED_PROVIDER_ID,
        },
        "entry": fred_provider_entry_summary(),
        "cache": {"fred": None},
    }


def _status(*, state: str, last_update: str, message: str, cache_path: str) -> dict[str, str]:
    return {
        "source": FRED_SOURCE,
        "state": state,
        "last_update": last_update,
        "message": message,
        "provider_id": FRED_PROVIDER_ID,
        "cache_path": cache_path,
        "docs_url": FRED_SERIES_OBSERVATIONS_DOC,
        "auth_mode": "optional-local-key",
        "safety_class": "optional_local_secret_data_provider",
        "notice": FRED_NOTICE,
    }


def _summary_from_series(series: list[Any]) -> dict[str, Any]:
    first = series[0] if series and isinstance(series[0], dict) else {}
    return {
        "series_id": str(first.get("series_id") or FRED_DEFAULT_SERIES_ID),
        "latest_period": str(first.get("latest_period") or ""),
        "latest_value": str(first.get("latest_value") or ""),
        "observation_count": int(first.get("observation_count") or 0),
        "source": FRED_SOURCE,
        "provider_id": FRED_PROVIDER_ID,
    }


def _safe_series_id(series_id: str) -> str:
    return "".join(ch for ch in str(series_id).upper() if ch.isalnum() or ch in {"_", "-"})[:64] or FRED_DEFAULT_SERIES_ID


def _utc_now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
