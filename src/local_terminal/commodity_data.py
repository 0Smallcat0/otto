"""Public no-key commodity reference-price provider adapters."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from io import BytesIO
from typing import Any


DOCS_CHECKED_AT = "2026-05-23"
WORLD_BANK_COMMODITY_MARKETS_URL = "https://www.worldbank.org/en/research/commodity-markets"
WORLD_BANK_MONTHLY_XLSX_URL = (
    "https://thedocs.worldbank.org/en/doc/74e8be41ceb20fa0da750cda2f6b9e4e-0050012026/"
    "related/CMO-Historical-Data-Monthly.xlsx"
)
WORLD_BANK_CACHE_PATH = "market_data/commodities/world_bank/pink_sheet_monthly.json"
WORLD_BANK_PROVIDER_ID = "world_bank_commodity_monthly_public"
WORLD_BANK_TTL_SECONDS = 604800
CFTC_COT_DOCS_URL = "https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm"
CFTC_COT_API_DOCS_URL = "https://dev.socrata.com/foundry/publicreporting.cftc.gov/6dca-aqww"
CFTC_COT_API_URL = "https://publicreporting.cftc.gov/resource/6dca-aqww.json"
CFTC_COT_CACHE_PATH = "market_data/commodities/cftc/cot_legacy_futures.json"
CFTC_COT_PROVIDER_ID = "cftc_cot_legacy_public"
CFTC_COT_TTL_SECONDS = 604800
CFTC_COT_CONTRACTS = (
    "GOLD - COMMODITY EXCHANGE INC.",
    "WHEAT-SRW - CHICAGO BOARD OF TRADE",
    "CRUDE OIL, LIGHT SWEET-WTI - ICE FUTURES EUROPE",
    "COPPER- #1 - COMMODITY EXCHANGE INC.",
)
CFTC_COT_LABELS = {
    "GOLD - COMMODITY EXCHANGE INC.": "Gold",
    "WHEAT-SRW - CHICAGO BOARD OF TRADE": "Wheat SRW",
    "CRUDE OIL, LIGHT SWEET-WTI - ICE FUTURES EUROPE": "WTI crude",
    "COPPER- #1 - COMMODITY EXCHANGE INC.": "Copper",
}
SUMMARY_CODES = ("CRUDE_WTI", "CRUDE_BRENT", "NGAS_US", "GOLD", "COPPER", "WHEAT_US_SRW")
SHEET_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
REL_NS = {"rel": "http://schemas.openxmlformats.org/package/2006/relationships"}
REL_ID = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
PERIOD_RE = re.compile(r"^\d{4}M\d{2}$")


class CommodityDataError(ValueError):
    """Raised when public commodity provider data is invalid."""


def commodity_data_payload(
    commodity_cache: dict[str, Any] | None = None,
    *,
    cftc_cache: dict[str, Any] | None = None,
    fetcher: Any | None = None,
    cftc_fetcher: Any | None = None,
    refresh: bool = False,
) -> dict[str, Any]:
    """Return normalized World Bank commodity prices with provenance and cache state."""

    fetcher = fetcher or fetch_world_bank_commodity_prices
    cftc_fetcher = cftc_fetcher or fetch_cftc_cot_legacy_futures
    source_errors: list[str] = []
    world_bank_payload = _coerce_world_bank_payload(commodity_cache, state="stale")
    cftc_payload = _coerce_cftc_cot_payload(cftc_cache, state="stale")

    if refresh:
        try:
            world_bank_payload = normalize_world_bank_commodity_prices(fetcher(), state="live")
        except (
            CommodityDataError,
            OSError,
            TimeoutError,
            urllib.error.URLError,
            zipfile.BadZipFile,
            ET.ParseError,
        ) as exc:
            source_errors.append(str(exc) or exc.__class__.__name__)
        try:
            cftc_payload = normalize_cftc_cot_legacy_futures(cftc_fetcher(), state="live")
        except (
            CommodityDataError,
            OSError,
            TimeoutError,
            urllib.error.URLError,
            json.JSONDecodeError,
        ) as exc:
            source_errors.append(str(exc) or exc.__class__.__name__)

    world_bank = _world_bank_section(world_bank_payload)
    cftc = _cftc_cot_section(cftc_payload)
    status = dict(world_bank["status"])
    if source_errors and status["state"] == "unavailable":
        status["message"] = (
            "Commodity provider refresh failed; no usable local cache is available."
        )
    elif source_errors:
        status["message"] = (
            "Commodity provider refresh had source errors; using available local cache."
        )
    status["source_errors"] = source_errors
    return {
        "status": status,
        "world_bank": world_bank,
        "cftc": cftc,
        "provider_entry": provider_entry_summary(),
        "cache": {"world_bank": world_bank_payload, "cftc": cftc_payload},
    }


def fetch_world_bank_commodity_prices(timeout: float = 12.0) -> bytes:
    """Fetch the World Bank Pink Sheet monthly commodity XLSX file."""

    request = urllib.request.Request(
        WORLD_BANK_MONTHLY_XLSX_URL,
        headers={"User-Agent": "LocalTerminal/0.1 clean-room local commodities"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def fetch_cftc_cot_legacy_futures(timeout: float = 12.0) -> bytes:
    """Fetch bounded public CFTC Legacy futures-only COT rows from the PRE API."""

    where_values = ",".join(f"'{contract}'" for contract in CFTC_COT_CONTRACTS)
    query = urllib.parse.urlencode(
        {
            "$select": (
                "market_and_exchange_names,report_date_as_yyyy_mm_dd,open_interest_all,"
                "noncomm_positions_long_all,noncomm_positions_short_all,"
                "comm_positions_long_all,comm_positions_short_all"
            ),
            "$where": f"market_and_exchange_names in({where_values})",
            "$order": "report_date_as_yyyy_mm_dd DESC",
            "$limit": "40",
        }
    )
    request = urllib.request.Request(
        f"{CFTC_COT_API_URL}?{query}",
        headers={"User-Agent": "LocalTerminal/0.1 clean-room local CFTC COT"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def normalize_world_bank_commodity_prices(
    raw: bytes | dict[str, Any],
    *,
    state: str = "live",
    retrieved_at: str | None = None,
) -> dict[str, Any]:
    """Normalize World Bank Pink Sheet XLSX data into latest monthly rows."""

    if isinstance(raw, dict) and "rows" in raw and "status" in raw:
        return _coerce_world_bank_payload(raw, state=state)
    if not isinstance(raw, bytes) or not raw:
        raise CommodityDataError("World Bank commodity payload is empty")

    workbook_rows = _xlsx_sheet_rows(raw, "Monthly Prices")
    if not workbook_rows:
        raise CommodityDataError("World Bank commodity workbook has no Monthly Prices rows")

    rows_by_number = {row_number: cells for row_number, cells in workbook_rows}
    names = rows_by_number.get(5, {})
    units = rows_by_number.get(6, {})
    codes = rows_by_number.get(7, {})
    if not codes:
        raise CommodityDataError("World Bank commodity workbook has no code row")

    latest_period, latest_cells = _latest_period_cells(workbook_rows)
    updated_at = retrieved_at or _utc_now()
    data_rows: list[dict[str, Any]] = []
    for column, raw_code in sorted(codes.items()):
        code = str(raw_code or "").strip()
        if not code:
            continue
        value = _rate_text(latest_cells.get(column))
        if not value:
            continue
        data_rows.append(
            {
                "code": code,
                "name": str(names.get(column) or code).strip(),
                "unit": str(units.get(column) or "").strip(),
                "value": value,
                "period": latest_period,
                "source": "world_bank_pink_sheet",
                "provider_id": WORLD_BANK_PROVIDER_ID,
                "retrieved_at": updated_at,
                "cache_path": WORLD_BANK_CACHE_PATH,
                "docs_url": WORLD_BANK_COMMODITY_MARKETS_URL,
                "data_url": WORLD_BANK_MONTHLY_XLSX_URL,
                "monthly_reference": True,
            }
        )

    if not data_rows:
        raise CommodityDataError("World Bank commodity workbook has no latest commodity rows")

    return {
        "status": _status(
            state=state,
            last_update=updated_at,
            message=(
                "World Bank Pink Sheet monthly commodity prices normalized from public "
                "no-key XLSX; values are monthly reference data, not executable quotes."
            ),
        ),
        "rows": data_rows,
        "latest": {
            "period": latest_period,
            "updated_on": str(rows_by_number.get(4, {}).get(1) or ""),
            "rows": data_rows,
        },
    }


def normalize_cftc_cot_legacy_futures(
    raw: bytes | list[dict[str, Any]] | dict[str, Any],
    *,
    state: str = "live",
    retrieved_at: str | None = None,
) -> dict[str, Any]:
    """Normalize public CFTC Legacy futures-only COT rows into positioning context."""

    if isinstance(raw, dict) and "rows" in raw and "status" in raw:
        return _coerce_cftc_cot_payload(raw, state=state)
    if isinstance(raw, bytes):
        parsed = json.loads(raw.decode("utf-8"))
    else:
        parsed = raw
    if not isinstance(parsed, list):
        raise CommodityDataError("CFTC COT payload is not a row list")

    updated_at = retrieved_at or _utc_now()
    latest_by_contract: dict[str, dict[str, Any]] = {}
    for item in parsed:
        if not isinstance(item, dict):
            continue
        contract = str(item.get("market_and_exchange_names") or "").strip()
        if contract not in CFTC_COT_CONTRACTS or contract in latest_by_contract:
            continue
        report_date = _date_text(item.get("report_date_as_yyyy_mm_dd"))
        if not report_date:
            continue
        long_value = _int_text(item.get("noncomm_positions_long_all"))
        short_value = _int_text(item.get("noncomm_positions_short_all"))
        comm_long = _int_text(item.get("comm_positions_long_all"))
        comm_short = _int_text(item.get("comm_positions_short_all"))
        latest_by_contract[contract] = {
            "contract": CFTC_COT_LABELS.get(contract, contract),
            "market_and_exchange_names": contract,
            "report_date": report_date,
            "open_interest": _int_text(item.get("open_interest_all")),
            "noncommercial_long": long_value,
            "noncommercial_short": short_value,
            "noncommercial_net": _net_text(long_value, short_value),
            "commercial_long": comm_long,
            "commercial_short": comm_short,
            "commercial_net": _net_text(comm_long, comm_short),
            "source": "cftc_cot_legacy_futures_only",
            "provider_id": CFTC_COT_PROVIDER_ID,
            "retrieved_at": updated_at,
            "cache_path": CFTC_COT_CACHE_PATH,
            "docs_url": CFTC_COT_DOCS_URL,
            "api_docs_url": CFTC_COT_API_DOCS_URL,
            "report_type": "legacy_futures_only",
            "positioning_context": True,
        }

    rows = [latest_by_contract[contract] for contract in CFTC_COT_CONTRACTS if contract in latest_by_contract]
    if not rows:
        raise CommodityDataError("CFTC COT payload has no configured commodity rows")
    return {
        "status": _cftc_status(
            state=state,
            last_update=updated_at,
            message=(
                "CFTC Legacy futures-only Commitments of Traders rows normalized from "
                "the public reporting API; values are positioning context, not "
                "executable commodity quotes."
            ),
        ),
        "rows": rows,
        "summary": _cftc_summary(rows),
    }


def provider_entry_summary() -> dict[str, Any]:
    return {
        "docs_checked_at": DOCS_CHECKED_AT,
        "providers": [
            {
                "provider_id": WORLD_BANK_PROVIDER_ID,
                "official_docs": WORLD_BANK_COMMODITY_MARKETS_URL,
                "download_url": WORLD_BANK_MONTHLY_XLSX_URL,
                "auth_mode": "no-key",
                "rate_limit": "Use weekly local cache; Pink Sheet XLSX is a public monthly data file.",
                "terms_risk": (
                    "World Bank commodity data is public reference data; preserve attribution "
                    "and do not present monthly values as executable spot or futures quotes."
                ),
                "cache_path": WORLD_BANK_CACHE_PATH,
                "ttl_seconds": WORLD_BANK_TTL_SECONDS,
                "schema": "Pink Sheet XLSX Monthly Prices -> latest monthly commodity rows",
                "safety_class": "public_read_only_commodity_reference",
            },
            {
                "provider_id": CFTC_COT_PROVIDER_ID,
                "official_docs": CFTC_COT_DOCS_URL,
                "api_docs": CFTC_COT_API_DOCS_URL,
                "auth_mode": "no-key",
                "rate_limit": "Use weekly local cache; CFTC PRE API is public and should be queried in bounded form.",
                "terms_risk": (
                    "CFTC COT rows are public positioning context; preserve attribution "
                    "and do not present them as executable spot or futures quotes."
                ),
                "cache_path": CFTC_COT_CACHE_PATH,
                "ttl_seconds": CFTC_COT_TTL_SECONDS,
                "schema": "CFTC Legacy Futures Only rows -> bounded commodity positioning context",
                "safety_class": "public_read_only_commodity_positioning",
            }
        ],
    }


def _coerce_world_bank_payload(raw: dict[str, Any] | None, *, state: str) -> dict[str, Any]:
    if not isinstance(raw, dict) or not raw:
        return _empty_world_bank_payload()
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
    return _empty_world_bank_payload()


def _empty_world_bank_payload() -> dict[str, Any]:
    return {
        "status": _status(
            state="unavailable",
            last_update="not refreshed",
            message="No World Bank commodity cache is available yet.",
        ),
        "rows": [],
        "latest": {},
    }


def _coerce_cftc_cot_payload(raw: dict[str, Any] | None, *, state: str) -> dict[str, Any]:
    if not isinstance(raw, dict) or not raw:
        return _empty_cftc_cot_payload()
    if "rows" in raw and "status" in raw and isinstance(raw.get("rows"), list):
        payload = dict(raw)
        status = dict(payload.get("status") or {})
        status["state"] = _cache_state(status.get("state"), state)
        payload["status"] = status
        rows = [row for row in payload.get("rows", []) if isinstance(row, dict)]
        payload["rows"] = rows
        summary = payload.get("summary")
        payload["summary"] = summary if isinstance(summary, dict) else _cftc_summary(rows)
        return payload
    return _empty_cftc_cot_payload()


def _empty_cftc_cot_payload() -> dict[str, Any]:
    return {
        "status": _cftc_status(
            state="unavailable",
            last_update="not refreshed",
            message="No CFTC COT commodity positioning cache is available yet.",
        ),
        "rows": [],
        "summary": _cftc_summary([]),
    }


def _world_bank_section(payload: dict[str, Any]) -> dict[str, Any]:
    rows = [row for row in payload.get("rows", []) if isinstance(row, dict)]
    latest = payload.get("latest") if isinstance(payload.get("latest"), dict) else {}
    summary = {
        "row_count": len(rows),
        "period": str(latest.get("period") or _first_row_value(rows, "period")),
        "updated_on": str(latest.get("updated_on") or ""),
        "source": "world_bank_pink_sheet",
    }
    for code in SUMMARY_CODES:
        summary[code.lower()] = _code_value(rows, code)
    return {
        "status": dict(payload.get("status") or {}),
        "rows": rows,
        "latest": latest,
        "summary": summary,
    }


def _cftc_cot_section(payload: dict[str, Any]) -> dict[str, Any]:
    rows = [row for row in payload.get("rows", []) if isinstance(row, dict)]
    summary = payload.get("summary")
    return {
        "status": dict(payload.get("status") or {}),
        "rows": rows,
        "summary": summary if isinstance(summary, dict) else _cftc_summary(rows),
    }


def _xlsx_sheet_rows(raw: bytes, sheet_name: str) -> list[tuple[int, dict[int, str]]]:
    with zipfile.ZipFile(BytesIO(raw)) as workbook:
        shared_strings = _shared_strings(workbook)
        sheet_path = _sheet_path(workbook, sheet_name)
        root = ET.fromstring(workbook.read(sheet_path))
    rows: list[tuple[int, dict[int, str]]] = []
    for row in root.findall("m:sheetData/m:row", SHEET_NS):
        row_number = int(row.attrib.get("r") or len(rows) + 1)
        cells: dict[int, str] = {}
        for cell in row.findall("m:c", SHEET_NS):
            column = _column_index(str(cell.attrib.get("r") or ""))
            if column:
                cells[column] = _cell_text(cell, shared_strings)
        rows.append((row_number, cells))
    return rows


def _sheet_path(workbook: zipfile.ZipFile, sheet_name: str) -> str:
    workbook_xml = ET.fromstring(workbook.read("xl/workbook.xml"))
    rels = ET.fromstring(workbook.read("xl/_rels/workbook.xml.rels"))
    relmap = {
        str(rel.attrib.get("Id") or ""): str(rel.attrib.get("Target") or "")
        for rel in rels.findall("rel:Relationship", REL_NS)
    }
    for sheet in workbook_xml.findall("m:sheets/m:sheet", SHEET_NS):
        if str(sheet.attrib.get("name") or "") != sheet_name:
            continue
        target = relmap.get(str(sheet.attrib.get(REL_ID) or ""))
        if not target:
            break
        return target[1:] if target.startswith("/") else f"xl/{target}"
    raise CommodityDataError(f"World Bank commodity workbook is missing {sheet_name}")


def _shared_strings(workbook: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in workbook.namelist():
        return []
    root = ET.fromstring(workbook.read("xl/sharedStrings.xml"))
    strings = []
    for item in root.findall("m:si", SHEET_NS):
        strings.append("".join(node.text or "" for node in item.findall(".//m:t", SHEET_NS)))
    return strings


def _cell_text(cell: ET.Element, shared_strings: list[str]) -> str:
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        return "".join(node.text or "" for node in cell.findall(".//m:t", SHEET_NS)).strip()
    value = cell.find("m:v", SHEET_NS)
    text = str(value.text or "").strip() if value is not None else ""
    if cell_type == "s" and text:
        index = int(text)
        return shared_strings[index] if 0 <= index < len(shared_strings) else ""
    return text


def _latest_period_cells(workbook_rows: list[tuple[int, dict[int, str]]]) -> tuple[str, dict[int, str]]:
    for _, cells in reversed(workbook_rows):
        period = str(cells.get(1) or "").strip()
        if PERIOD_RE.match(period) and any(_rate_text(value) for key, value in cells.items() if key != 1):
            return period, cells
    raise CommodityDataError("World Bank commodity workbook has no latest monthly period")


def _latest_from_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {}
    return {
        "period": str(rows[0].get("period") or ""),
        "updated_on": "",
        "rows": rows,
    }


def _first_row_value(rows: list[dict[str, Any]], key: str) -> str:
    for row in rows:
        value = row.get(key)
        if value:
            return str(value)
    return ""


# Canonical Pink Sheet series names; cached rows often carry unit strings or
# artifacts in "code", so the name is the reliable key.
SUMMARY_SERIES_NAMES = {
    "CRUDE_WTI": "crude oil, wti",
    "CRUDE_BRENT": "crude oil, brent",
    "NGAS_US": "natural gas, us",
    "GOLD": "gold",
    "COPPER": "copper",
    "WHEAT_US_SRW": "wheat, us srw",
}


def _normalized_series_name(raw_name: Any) -> str:
    return str(raw_name or "").strip().rstrip("*").strip().lower()


def _code_value(rows: list[dict[str, Any]], code: str) -> str:
    wanted_name = SUMMARY_SERIES_NAMES.get(code, "")
    for row in rows:
        if str(row.get("code") or "").upper() == code:
            return str(row.get("value") or "")
        if wanted_name and _normalized_series_name(row.get("name")) == wanted_name:
            return str(row.get("value") or "")
    return ""


def _cftc_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    latest_dates = [str(row.get("report_date") or "") for row in rows if row.get("report_date")]
    summary = {
        "row_count": len(rows),
        "report_date": max(latest_dates) if latest_dates else "",
        "contracts": ",".join(str(row.get("contract") or "") for row in rows if row.get("contract")),
        "source": "cftc_cot_legacy_futures_only",
    }
    for row in rows:
        label = str(row.get("contract") or "").lower().replace(" ", "_")
        if label in {"gold", "wheat_srw", "wti_crude", "copper"}:
            summary[f"{label}_noncommercial_net"] = str(row.get("noncommercial_net") or "")
    return summary


def _date_text(raw: Any) -> str:
    text = str(raw or "").strip()
    if "T" in text:
        return text.split("T", 1)[0]
    return text


def _int_text(raw: Any) -> str:
    text = str(raw or "").strip().replace(",", "")
    if not text:
        return ""
    try:
        return str(int(Decimal(text)))
    except (InvalidOperation, ValueError):
        return ""


def _net_text(long_value: str, short_value: str) -> str:
    if not long_value or not short_value:
        return ""
    return str(int(long_value) - int(short_value))


def _rate_text(raw: Any) -> str:
    text = str(raw or "").strip()
    if text in {"", "..."}:
        return ""
    try:
        value = Decimal(text)
    except (InvalidOperation, ValueError):
        return ""
    return _format_reference_value(value)


def _format_reference_value(value: Decimal) -> str:
    step = Decimal("0.01") if abs(value) >= Decimal("1000") else Decimal("0.0001")
    return f"{value.quantize(step).normalize():f}"


def _status(*, state: str, last_update: str, message: str) -> dict[str, str]:
    return {
        "source": "world_bank_pink_sheet",
        "state": state,
        "last_update": last_update,
        "message": message,
        "provider_id": WORLD_BANK_PROVIDER_ID,
        "cache_path": WORLD_BANK_CACHE_PATH,
        "docs_url": WORLD_BANK_COMMODITY_MARKETS_URL,
    }


def _cftc_status(*, state: str, last_update: str, message: str) -> dict[str, str]:
    return {
        "source": "cftc_cot_legacy_futures_only",
        "state": state,
        "last_update": last_update,
        "message": message,
        "provider_id": CFTC_COT_PROVIDER_ID,
        "cache_path": CFTC_COT_CACHE_PATH,
        "docs_url": CFTC_COT_DOCS_URL,
    }


def _cache_state(current: Any, requested: str) -> str:
    if requested == "stale" and str(current or "") in {"live", "partial"}:
        return "stale"
    return str(current or requested)


def _column_index(reference: str) -> int:
    letters = "".join(ch for ch in reference if ch.isalpha()).upper()
    index = 0
    for letter in letters:
        index = index * 26 + ord(letter) - 64
    return index


def _utc_now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
