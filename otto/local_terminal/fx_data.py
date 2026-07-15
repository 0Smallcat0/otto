"""Public no-key foreign exchange reference-rate provider adapters."""

from __future__ import annotations

import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
import csv
import json
from io import StringIO
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any


DOCS_CHECKED_AT = "2026-05-26"
ECB_DOCS_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-xml.html"
ECB_DAILY_XML_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"
ECB_CACHE_PATH = "market_data/fx/ecb/eurofxref_daily.json"
ECB_PROVIDER_ID = "ecb_fx_reference_public"
ECB_TTL_SECONDS = 86400
FED_H10_DOCS_URL = "https://www.federalreserve.gov/datadownload/choose.aspx?rel=h10"
FED_H10_DAILY_RATES_CSV_URL = (
    "https://www.federalreserve.gov/datadownload/Output.aspx?"
    "rel=H10&series=60f32914ab61dfab590e0e470153e3ae&lastobs=10&from=&to=&"
    "filetype=csv&label=include&layout=seriescolumn&type=package"
)
FED_H10_CACHE_PATH = "market_data/fx/federal_reserve/h10_reference_rates.json"
FED_H10_PROVIDER_ID = "federal_reserve_h10_ddp_public"
FED_H10_TTL_SECONDS = 86400
BOC_DOCS_URL = "https://www.bankofcanada.ca/valet/docs"
BOC_EXCHANGE_RATES_URL = "https://www.bankofcanada.ca/rates/exchange/"
BOC_CACHE_PATH = "market_data/fx/bank_of_canada/valet_fx_reference_rates.json"
BOC_PROVIDER_ID = "bank_of_canada_valet_fx_reference_public"
BOC_TTL_SECONDS = 86400
BOC_SERIES = ("FXUSDCAD", "FXEURCAD", "FXGBPCAD", "FXJPYCAD", "FXCHFCAD")
BOC_OBSERVATIONS_URL = (
    "https://www.bankofcanada.ca/valet/observations/"
    f"{','.join(BOC_SERIES)}/json?recent=1"
)
SUMMARY_QUOTES = ("USD", "GBP", "JPY", "CHF", "CNY")
H10_SUMMARY_CURRENCIES = ("EUR", "GBP", "JPY", "CAD", "CNY")
BOC_SUMMARY_CURRENCIES = ("USD", "EUR", "GBP", "JPY", "CHF")


class FxDataError(ValueError):
    """Raised when public FX provider data is invalid."""


def fx_data_payload(
    ecb_cache: dict[str, Any] | None = None,
    *,
    h10_cache: dict[str, Any] | None = None,
    boc_cache: dict[str, Any] | None = None,
    fetcher: Any | None = None,
    h10_fetcher: Any | None = None,
    boc_fetcher: Any | None = None,
    refresh: bool = False,
) -> dict[str, Any]:
    """Return normalized public FX reference rates with provenance and cache state."""

    fetcher = fetcher or fetch_ecb_fx_reference_rates
    h10_fetcher = h10_fetcher or fetch_federal_reserve_h10_reference_rates
    boc_fetcher = boc_fetcher or fetch_bank_of_canada_valet_fx_reference_rates
    source_errors: list[str] = []
    ecb_payload = _coerce_ecb_payload(ecb_cache, state="stale")
    h10_payload = _coerce_h10_payload(h10_cache, state="stale")
    boc_payload = _coerce_boc_payload(boc_cache, state="stale")

    if refresh:
        try:
            ecb_payload = normalize_ecb_fx_reference_rates(fetcher(), state="live")
        except (
            FxDataError,
            OSError,
            TimeoutError,
            urllib.error.URLError,
            ET.ParseError,
        ) as exc:
            source_errors.append(str(exc) or exc.__class__.__name__)
        try:
            h10_payload = normalize_federal_reserve_h10_reference_rates(
                h10_fetcher(),
                state="live",
            )
        except (FxDataError, OSError, TimeoutError, urllib.error.URLError) as exc:
            source_errors.append(str(exc) or exc.__class__.__name__)
        try:
            boc_payload = normalize_bank_of_canada_valet_fx_reference_rates(
                boc_fetcher(),
                state="live",
            )
        except (
            FxDataError,
            OSError,
            TimeoutError,
            urllib.error.URLError,
            json.JSONDecodeError,
        ) as exc:
            source_errors.append(str(exc) or exc.__class__.__name__)

    ecb = _ecb_section(ecb_payload)
    h10 = _h10_section(h10_payload)
    boc = _boc_section(boc_payload)
    status = dict(ecb["status"])
    if source_errors and status["state"] == "unavailable":
        status["message"] = "FX reference-rate refresh failed; no usable local cache is available."
    elif source_errors:
        status["message"] = "One FX reference-rate refresh failed; using available local cache."
    status["source_errors"] = source_errors
    return {
        "status": status,
        "ecb": ecb,
        "h10": h10,
        "boc": boc,
        "provider_entry": provider_entry_summary(),
        "cache": {"ecb": ecb_payload, "h10": h10_payload, "boc": boc_payload},
    }


def fetch_ecb_fx_reference_rates(timeout: float = 8.0) -> str:
    """Fetch the ECB latest euro foreign exchange reference-rate XML feed."""

    request = urllib.request.Request(
        ECB_DAILY_XML_URL,
        headers={"User-Agent": "LocalTerminal/0.1 clean-room local fx"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8")


def fetch_federal_reserve_h10_reference_rates(timeout: float = 8.0) -> str:
    """Fetch the Federal Reserve H.10 daily rates preformatted CSV package."""

    request = urllib.request.Request(
        FED_H10_DAILY_RATES_CSV_URL,
        headers={"User-Agent": "LocalTerminal/0.1 clean-room local fx"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8-sig")


def fetch_bank_of_canada_valet_fx_reference_rates(timeout: float = 8.0) -> str:
    """Fetch latest bounded Bank of Canada Valet FX reference-rate observations."""

    request = urllib.request.Request(
        BOC_OBSERVATIONS_URL,
        headers={"User-Agent": "LocalTerminal/0.1 clean-room local fx"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8")


def normalize_ecb_fx_reference_rates(
    raw: str | bytes | dict[str, Any],
    *,
    state: str = "live",
    retrieved_at: str | None = None,
) -> dict[str, Any]:
    """Normalize ECB eurofxref XML into EUR-base reference-rate rows."""

    if isinstance(raw, dict) and "rows" in raw and "status" in raw:
        return _coerce_ecb_payload(raw, state=state)
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    if not isinstance(raw, str) or not raw.strip():
        raise FxDataError("ECB FX reference-rate payload is empty")

    root = ET.fromstring(raw)
    time_cube = _latest_time_cube(root)
    if time_cube is None:
        raise FxDataError("ECB FX reference-rate payload has no dated rate cube")

    date = str(time_cube.attrib.get("time") or "").strip()
    if not date:
        raise FxDataError("ECB FX reference-rate payload has no observation date")

    updated_at = retrieved_at or _utc_now()
    rows: list[dict[str, Any]] = []
    for rate_cube in time_cube:
        currency = str(rate_cube.attrib.get("currency") or "").strip().upper()
        rate = _rate_text(rate_cube.attrib.get("rate"))
        if not currency or not rate:
            continue
        rows.append(
            {
                "pair": f"EUR/{currency}",
                "base": "EUR",
                "quote": currency,
                "rate": rate,
                "date": date,
                "source": "ecb_fx_reference",
                "provider_id": ECB_PROVIDER_ID,
                "retrieved_at": updated_at,
                "cache_path": ECB_CACHE_PATH,
                "docs_url": ECB_DOCS_URL,
                "reference_only": True,
            }
        )

    if not rows:
        raise FxDataError("ECB FX reference-rate payload has no currency rows")

    rows = sorted(rows, key=lambda item: str(item["quote"]))
    return {
        "status": _status(
            state=state,
            last_update=updated_at,
            message=(
                "ECB euro foreign exchange reference rates normalized from public "
                "no-key XML feed; rates are reference-only, not executable spot quotes."
            ),
        ),
        "rows": rows,
        "latest": {"date": date, "base": "EUR", "rows": rows},
    }


def normalize_federal_reserve_h10_reference_rates(
    raw: str | bytes | dict[str, Any],
    *,
    state: str = "live",
    retrieved_at: str | None = None,
) -> dict[str, Any]:
    """Normalize Federal Reserve H.10 DDP CSV into USD reference-rate rows."""

    if isinstance(raw, dict) and "rows" in raw and "status" in raw:
        return _coerce_h10_payload(raw, state=state)
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8-sig")
    if not isinstance(raw, str) or not raw.strip():
        raise FxDataError("Federal Reserve H.10 reference-rate payload is empty")

    parsed = [row for row in csv.reader(StringIO(raw)) if row]
    try:
        descriptions = parsed[0]
        currencies = next(row for row in parsed if row[0].strip() == "Currency:")
        identifiers = next(row for row in parsed if row[0].strip() == "Unique Identifier:")
        data_start = next(
            index + 1
            for index, row in enumerate(parsed)
            if row and row[0].strip() == "Time Period"
        )
    except StopIteration as exc:
        raise FxDataError("Federal Reserve H.10 CSV is missing required header rows") from exc

    latest = _latest_h10_observation(parsed[data_start:])
    date = str(latest[0]).strip()
    updated_at = retrieved_at or _utc_now()
    rows: list[dict[str, Any]] = []
    for index, raw_currency in enumerate(currencies[1:], start=1):
        currency = str(raw_currency or "").strip().upper()
        rate = _rate_text(latest[index] if index < len(latest) else "")
        if not currency or not rate:
            continue
        identifier = str(identifiers[index] if index < len(identifiers) else "")
        rate_basis = "usd_per_currency" if "$US" in identifier else "currency_per_usd"
        pair = f"{currency}/USD" if rate_basis == "usd_per_currency" else f"USD/{currency}"
        rows.append(
            {
                "pair": pair,
                "currency": currency,
                "label": str(descriptions[index] if index < len(descriptions) else currency),
                "rate": rate,
                "date": date,
                "rate_basis": rate_basis,
                "source": "federal_reserve_h10",
                "provider_id": FED_H10_PROVIDER_ID,
                "retrieved_at": updated_at,
                "cache_path": FED_H10_CACHE_PATH,
                "docs_url": FED_H10_DOCS_URL,
                "reference_only": True,
            }
        )

    if not rows:
        raise FxDataError("Federal Reserve H.10 reference-rate payload has no currency rows")

    rows = sorted(rows, key=lambda item: str(item["currency"]))
    return {
        "status": _status(
            state=state,
            last_update=updated_at,
            message=(
                "Federal Reserve H.10 daily rates normalized from public no-key "
                "DDP CSV package; rates are reference-only, not executable FX quotes."
            ),
            source="federal_reserve_h10",
            provider_id=FED_H10_PROVIDER_ID,
            cache_path=FED_H10_CACHE_PATH,
            docs_url=FED_H10_DOCS_URL,
        ),
        "rows": rows,
        "latest": {"date": date, "base": "USD reference", "rows": rows},
    }


def normalize_bank_of_canada_valet_fx_reference_rates(
    raw: str | bytes | dict[str, Any],
    *,
    state: str = "live",
    retrieved_at: str | None = None,
) -> dict[str, Any]:
    """Normalize Bank of Canada Valet JSON into CAD reference-rate rows."""

    if isinstance(raw, dict) and "rows" in raw and "status" in raw:
        return _coerce_boc_payload(raw, state=state)
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    if isinstance(raw, str):
        raw = json.loads(raw)
    if not isinstance(raw, dict):
        raise FxDataError("Bank of Canada Valet payload must be JSON object")

    observations = raw.get("observations")
    if not isinstance(observations, list) or not observations:
        raise FxDataError("Bank of Canada Valet payload has no observations")
    latest = next(
        (item for item in reversed(observations) if isinstance(item, dict) and item.get("d")),
        {},
    )
    date = str(latest.get("d") or "").strip()
    if not date:
        raise FxDataError("Bank of Canada Valet payload has no observation date")

    updated_at = retrieved_at or _utc_now()
    rows: list[dict[str, Any]] = []
    for series in BOC_SERIES:
        observation = latest.get(series)
        value = observation.get("v") if isinstance(observation, dict) else ""
        rate = _rate_text(value)
        if not rate:
            continue
        currency = series[2:5].upper()
        rows.append(
            {
                "pair": f"{currency}/CAD",
                "base": currency,
                "quote": "CAD",
                "currency": currency,
                "series": series,
                "rate": rate,
                "date": date,
                "rate_basis": "cad_per_currency",
                "source": "bank_of_canada_valet",
                "provider_id": BOC_PROVIDER_ID,
                "retrieved_at": updated_at,
                "cache_path": BOC_CACHE_PATH,
                "docs_url": BOC_DOCS_URL,
                "reference_only": True,
            }
        )

    if not rows:
        raise FxDataError("Bank of Canada Valet payload has no configured FX rows")

    rows = sorted(rows, key=lambda item: str(item["currency"]))
    return {
        "status": _status(
            state=state,
            last_update=updated_at,
            message=(
                "Bank of Canada Valet daily FX observations normalized from public "
                "no-key JSON; rates are indicative reference data, not executable quotes."
            ),
            source="bank_of_canada_valet",
            provider_id=BOC_PROVIDER_ID,
            cache_path=BOC_CACHE_PATH,
            docs_url=BOC_DOCS_URL,
        ),
        "rows": rows,
        "latest": {"date": date, "base": "CAD reference", "rows": rows},
    }


def provider_entry_summary() -> dict[str, Any]:
    return {
        "docs_checked_at": DOCS_CHECKED_AT,
        "providers": [
            {
                "provider_id": ECB_PROVIDER_ID,
                "official_docs": ECB_DOCS_URL,
                "auth_mode": "no-key",
                "rate_limit": "Use daily local cache; ECB latest XML feed is a public read-only source.",
                "terms_risk": (
                    "ECB publishes reference rates for information purposes; preserve attribution "
                    "and do not present them as executable trading quotes."
                ),
                "cache_path": ECB_CACHE_PATH,
                "ttl_seconds": ECB_TTL_SECONDS,
                "schema": "ECB eurofxref XML -> EUR-base reference-rate rows",
                "safety_class": "public_read_only_fx_reference",
            },
            {
                "provider_id": FED_H10_PROVIDER_ID,
                "official_docs": FED_H10_DOCS_URL,
                "auth_mode": "no-key",
                "rate_limit": (
                    "Use daily local cache; Federal Reserve H.10 DDP CSV package is "
                    "a public read-only source."
                ),
                "terms_risk": (
                    "Federal Reserve H.10 rates are public reference data; preserve "
                    "attribution and do not present them as executable trading quotes."
                ),
                "cache_path": FED_H10_CACHE_PATH,
                "ttl_seconds": FED_H10_TTL_SECONDS,
                "schema": "Federal Reserve H.10 DDP CSV -> USD reference-rate rows",
                "safety_class": "public_read_only_fx_reference",
            },
            {
                "provider_id": BOC_PROVIDER_ID,
                "official_docs": BOC_DOCS_URL,
                "auth_mode": "no-key",
                "rate_limit": (
                    "Use daily local cache; Bank of Canada Valet observations are "
                    "public read-only reference data."
                ),
                "terms_risk": (
                    "Bank of Canada exchange rates are indicative reference data; "
                    "preserve attribution and do not present them as executable "
                    "trading quotes."
                ),
                "cache_path": BOC_CACHE_PATH,
                "ttl_seconds": BOC_TTL_SECONDS,
                "schema": "Bank of Canada Valet JSON -> CAD reference-rate rows",
                "safety_class": "public_read_only_fx_reference",
            },
        ],
    }


def _coerce_ecb_payload(raw: dict[str, Any] | None, *, state: str) -> dict[str, Any]:
    if not isinstance(raw, dict) or not raw:
        return _empty_ecb_payload()
    if "rows" in raw and "status" in raw and isinstance(raw.get("rows"), list):
        payload = dict(raw)
        status = dict(payload.get("status") or {})
        status["state"] = _cache_state(status.get("state"), state)
        payload["status"] = status
        rows = [row for row in payload.get("rows", []) if isinstance(row, dict)]
        payload["rows"] = rows
        latest = payload.get("latest")
        payload["latest"] = latest if isinstance(latest, dict) else _latest_from_rows(rows)
        return payload
    try:
        return normalize_ecb_fx_reference_rates(raw, state=state)
    except (FxDataError, ET.ParseError):
        return _empty_ecb_payload()


def _empty_ecb_payload() -> dict[str, Any]:
    return {
        "status": _status(
            state="unavailable",
            last_update="not refreshed",
            message="No ECB FX reference-rate cache is available yet.",
        ),
        "rows": [],
        "latest": {},
    }


def _coerce_h10_payload(raw: dict[str, Any] | None, *, state: str) -> dict[str, Any]:
    if not isinstance(raw, dict) or not raw:
        return _empty_h10_payload()
    if "rows" in raw and "status" in raw and isinstance(raw.get("rows"), list):
        payload = dict(raw)
        status = dict(payload.get("status") or {})
        status["state"] = _cache_state(status.get("state"), state)
        payload["status"] = status
        rows = [row for row in payload.get("rows", []) if isinstance(row, dict)]
        payload["rows"] = rows
        latest = payload.get("latest")
        payload["latest"] = latest if isinstance(latest, dict) else _latest_from_rows(rows)
        return payload
    try:
        return normalize_federal_reserve_h10_reference_rates(raw, state=state)
    except FxDataError:
        return _empty_h10_payload()


def _empty_h10_payload() -> dict[str, Any]:
    return {
        "status": _status(
            state="unavailable",
            last_update="not refreshed",
            message="No Federal Reserve H.10 FX reference-rate cache is available yet.",
            source="federal_reserve_h10",
            provider_id=FED_H10_PROVIDER_ID,
            cache_path=FED_H10_CACHE_PATH,
            docs_url=FED_H10_DOCS_URL,
        ),
        "rows": [],
        "latest": {},
    }


def _coerce_boc_payload(raw: dict[str, Any] | None, *, state: str) -> dict[str, Any]:
    if not isinstance(raw, dict) or not raw:
        return _empty_boc_payload()
    if "rows" in raw and "status" in raw and isinstance(raw.get("rows"), list):
        payload = dict(raw)
        status = dict(payload.get("status") or {})
        status["state"] = _cache_state(status.get("state"), state)
        payload["status"] = status
        rows = [row for row in payload.get("rows", []) if isinstance(row, dict)]
        payload["rows"] = rows
        latest = payload.get("latest")
        payload["latest"] = latest if isinstance(latest, dict) else _boc_latest_from_rows(rows)
        return payload
    try:
        return normalize_bank_of_canada_valet_fx_reference_rates(raw, state=state)
    except (FxDataError, json.JSONDecodeError):
        return _empty_boc_payload()


def _empty_boc_payload() -> dict[str, Any]:
    return {
        "status": _status(
            state="unavailable",
            last_update="not refreshed",
            message="No Bank of Canada Valet FX reference-rate cache is available yet.",
            source="bank_of_canada_valet",
            provider_id=BOC_PROVIDER_ID,
            cache_path=BOC_CACHE_PATH,
            docs_url=BOC_DOCS_URL,
        ),
        "rows": [],
        "latest": {},
    }


def _ecb_section(payload: dict[str, Any]) -> dict[str, Any]:
    rows = [row for row in payload.get("rows", []) if isinstance(row, dict)]
    latest = payload.get("latest") if isinstance(payload.get("latest"), dict) else {}
    summary = {
        "row_count": len(rows),
        "date": str(latest.get("date") or _first_row_value(rows, "date")),
        "base": str(latest.get("base") or "EUR"),
        "source": "ecb_fx_reference",
    }
    for quote in SUMMARY_QUOTES:
        summary[quote.lower()] = _quote_rate(rows, quote)
    return {
        "status": dict(payload.get("status") or {}),
        "rows": rows,
        "latest": latest,
        "summary": summary,
    }


def _h10_section(payload: dict[str, Any]) -> dict[str, Any]:
    rows = [row for row in payload.get("rows", []) if isinstance(row, dict)]
    latest = payload.get("latest") if isinstance(payload.get("latest"), dict) else {}
    summary = {
        "row_count": len(rows),
        "date": str(latest.get("date") or _first_row_value(rows, "date")),
        "base": str(latest.get("base") or "USD reference"),
        "source": "federal_reserve_h10",
    }
    for currency in H10_SUMMARY_CURRENCIES:
        summary[currency.lower()] = _h10_currency_rate(rows, currency)
    return {
        "status": dict(payload.get("status") or {}),
        "rows": rows,
        "latest": latest,
        "summary": summary,
    }


def _boc_section(payload: dict[str, Any]) -> dict[str, Any]:
    rows = [row for row in payload.get("rows", []) if isinstance(row, dict)]
    latest = payload.get("latest") if isinstance(payload.get("latest"), dict) else {}
    summary = {
        "row_count": len(rows),
        "date": str(latest.get("date") or _first_row_value(rows, "date")),
        "base": str(latest.get("base") or "CAD reference"),
        "source": "bank_of_canada_valet",
        "quote_semantics": "reference_only",
    }
    for currency in BOC_SUMMARY_CURRENCIES:
        summary[currency.lower()] = _boc_currency_rate(rows, currency)
    return {
        "status": dict(payload.get("status") or {}),
        "rows": rows,
        "latest": latest,
        "summary": summary,
    }


def _latest_h10_observation(rows: list[list[str]]) -> list[str]:
    for row in reversed(rows):
        if row and str(row[0]).strip() and any(str(value).strip() for value in row[1:]):
            return row
    raise FxDataError("Federal Reserve H.10 CSV has no observation rows")


def _latest_time_cube(root: ET.Element) -> ET.Element | None:
    cubes = [
        element
        for element in root.iter()
        if str(element.tag).endswith("Cube") and "time" in element.attrib
    ]
    if not cubes:
        return None
    return cubes[-1]


def _latest_from_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {}
    return {
        "date": str(rows[0].get("date") or ""),
        "base": "EUR",
        "rows": rows,
    }


def _boc_latest_from_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {}
    return {
        "date": str(rows[0].get("date") or ""),
        "base": "CAD reference",
        "rows": rows,
    }


def _first_row_value(rows: list[dict[str, Any]], key: str) -> str:
    for row in rows:
        value = row.get(key)
        if value:
            return str(value)
    return ""


def _quote_rate(rows: list[dict[str, Any]], quote: str) -> str:
    for row in rows:
        if str(row.get("quote") or "").upper() == quote:
            return str(row.get("rate") or "")
    return ""


def _h10_currency_rate(rows: list[dict[str, Any]], currency: str) -> str:
    for row in rows:
        if str(row.get("currency") or "").upper() == currency:
            return str(row.get("rate") or "")
    return ""


def _boc_currency_rate(rows: list[dict[str, Any]], currency: str) -> str:
    for row in rows:
        if str(row.get("currency") or "").upper() == currency:
            return str(row.get("rate") or "")
    return ""


def _rate_text(raw: Any) -> str:
    try:
        Decimal(str(raw))
    except (InvalidOperation, ValueError):
        return ""
    return str(raw).strip()


def _status(
    *,
    state: str,
    last_update: str,
    message: str,
    source: str = "ecb_fx_reference",
    provider_id: str = ECB_PROVIDER_ID,
    cache_path: str = ECB_CACHE_PATH,
    docs_url: str = ECB_DOCS_URL,
) -> dict[str, str]:
    return {
        "source": source,
        "state": state,
        "last_update": last_update,
        "message": message,
        "provider_id": provider_id,
        "cache_path": cache_path,
        "docs_url": docs_url,
    }


def _cache_state(current: Any, requested: str) -> str:
    if requested == "stale" and str(current or "") in {"live", "partial"}:
        return "stale"
    return str(current or requested)


def _utc_now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
