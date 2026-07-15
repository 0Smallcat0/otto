"""Public no-key macro and fundamentals provider adapters."""

from __future__ import annotations

import gzip
import json
import urllib.error
import urllib.request
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

from otto.local_terminal.bea_data import (
    BEA_PROVIDER_ID,
    bea_regional_payload,
    bea_provider_entry_summary,
)
from otto.local_terminal.bls_data import (
    bls_data_payload,
    bls_provider_entry_summary,
    fetch_bls_latest_series,
    normalize_bls_latest_series,
)
from otto.local_terminal.census_data import (
    CENSUS_PROVIDER_ID,
    census_acs_profile_payload,
    census_provider_entry_summary,
)
from otto.local_terminal.eurostat_data import (
    EUROSTAT_PROVIDER_ID,
    eurostat_hicp_payload,
    eurostat_provider_entry_summary,
    fetch_eurostat_hicp,
    normalize_eurostat_hicp,
)
from otto.local_terminal.fred_data import (
    FRED_PROVIDER_ID,
    fred_data_payload,
    fred_provider_entry_summary,
)


DOCS_CHECKED_AT = "2026-05-25"
SEC_DOCS_URL = "https://www.sec.gov/search-filings/edgar-application-programming-interfaces"
SEC_FAIR_ACCESS_URL = "https://www.sec.gov/about/developer-resources"
SEC_COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_COMPANY_SUBMISSIONS_URL_TEMPLATE = "https://data.sec.gov/submissions/CIK{cik}.json"
SEC_XBRL_FRAMES_URL_TEMPLATE = (
    "https://data.sec.gov/api/xbrl/frames/{taxonomy}/{tag}/{unit}/{period}.json"
)
DBNOMICS_DOCS_URL = "https://docs.db.nomics.world/"
SEC_DEFAULT_COMPANY = {
    "symbol": "AAPL",
    "cik": "0000320193",
    "label": "Apple Inc.",
}
SEC_DEFAULT_COMPANY_WATCHLIST: tuple[dict[str, str], ...] = (
    {"symbol": "AAPL", "cik": "0000320193", "label": "Apple Inc."},
    {"symbol": "MSFT", "cik": "0000789019", "label": "MICROSOFT CORP"},
    {"symbol": "NVDA", "cik": "0001045810", "label": "NVIDIA CORP"},
)
SEC_DEFAULT_COMPANY_SYMBOLS = tuple(company["symbol"] for company in SEC_DEFAULT_COMPANY_WATCHLIST)
SEC_DEFAULT_COMPANY_CIKS = {
    company["symbol"]: company["cik"] for company in SEC_DEFAULT_COMPANY_WATCHLIST
}
DBNOMICS_DEFAULT_SERIES = {
    "provider": "INSEE",
    "dataset": "IPC-2015",
    "series": "A.IPC.SO.00.00.INDICE.ENSEMBLE.FE.SO.BRUT.2015.FALSE",
    "label": "Annual CPI all items",
}
SEC_CACHE_PATH = "market_data/fundamentals/sec/0000320193/companyfacts.json"
SEC_COMPANY_TICKERS_CACHE_PATH = "market_data/fundamentals/sec/company_tickers.json"
SEC_COMPANY_SUBMISSIONS_CACHE_PATH = (
    "market_data/fundamentals/sec/0000320193/submissions.json"
)
SEC_COMPANY_SUBMISSIONS_CACHE_PATH_TEMPLATE = (
    "market_data/fundamentals/sec/{cik}/submissions.json"
)
SEC_XBRL_FRAMES_DEFAULT = {
    "taxonomy": "us-gaap",
    "tag": "Assets",
    "unit": "USD",
    "period": "CY2023Q4I",
}
SEC_XBRL_FRAMES_CACHE_PATH = (
    "market_data/fundamentals/sec/frames/us-gaap/Assets/USD/CY2023Q4I.json"
)
DBNOMICS_CACHE_PATH = (
    "market_data/macro/dbnomics/INSEE/IPC-2015/"
    "A.IPC.SO.00.00.INDICE.ENSEMBLE.FE.SO.BRUT.2015.FALSE.json"
)
SEC_USER_AGENT = "LocalTerminal/0.1 clean-room local research contact@example.invalid"
SEC_COMPANY_TICKERS_PROVIDER_ID = "sec_company_ticker_registry_public"
SEC_COMPANY_SUBMISSIONS_PROVIDER_ID = "sec_company_submissions_public"
SEC_XBRL_FRAMES_PROVIDER_ID = "sec_xbrl_frames_public"
SEC_COMPANY_TICKERS_TTL_SECONDS = 86400
SEC_COMPANY_SUBMISSIONS_TTL_SECONDS = 86400
SEC_XBRL_FRAMES_TTL_SECONDS = 86400
MAX_SEC_COMPANY_TICKER_ROWS = 18
MAX_SEC_SUBMISSION_ROWS = 12
MAX_SEC_XBRL_FRAME_ROWS = 12
OPTIONAL_KEY_SOURCES: tuple[dict[str, str], ...] = (
    {
        "provider_id": FRED_PROVIDER_ID,
        "label": "FRED economic data",
        "state": "key_required",
        "auth_mode": "optional-local-key",
        "message": "Store a local FRED key in Settings before refreshing this optional provider.",
    },
    {
        "provider_id": BEA_PROVIDER_ID,
        "label": "BEA Regional API",
        "state": "key_required",
        "auth_mode": "optional-local-key",
        "message": "Store a local BEA UserID in Settings before refreshing Regional macro context.",
    },
    {
        "provider_id": CENSUS_PROVIDER_ID,
        "label": "Census ACS 5-Year Profile API",
        "state": "key_required",
        "auth_mode": "optional-local-key",
        "message": "Store a local Census API key in Settings before refreshing Regional context.",
    },
    {
        "provider_id": "newsapi_optional_local_key",
        "label": "NewsAPI headlines",
        "state": "key_required",
        "auth_mode": "optional-local-key / paid-gated",
        "message": "Recorded as a provider option only; no key collection or article copying.",
    },
    {
        "provider_id": "gdelt_optional_local_key",
        "label": "GDELT structured events",
        "state": "key_required",
        "auth_mode": "optional-local-key",
        "message": "Disabled until local secret storage and source display rules exist.",
    },
)
MACRO_HEADLINE_PROVIDER_PRIORITY: tuple[str, ...] = (
    "dbnomics_public",
    FRED_PROVIDER_ID,
    "bls_public_macro",
    EUROSTAT_PROVIDER_ID,
    BEA_PROVIDER_ID,
    CENSUS_PROVIDER_ID,
)
MACRO_HEADLINE_RULE = (
    "primary_provider follows explicit priority dbnomics_public > "
    "fred_optional_local_key > bls_public_macro > eurostat_hicp_public > "
    "bea_regional_optional_key > census_api_optional_key; headline_series is "
    "the first available row for that provider."
)
SEC_FACT_CONCEPTS: tuple[tuple[str, str], ...] = (
    ("Assets", "Assets"),
    ("RevenueFromContractWithCustomerExcludingAssessedTax", "Revenue"),
    ("Revenues", "Revenue"),
    ("NetIncomeLoss", "Net income"),
    ("OperatingIncomeLoss", "Operating income"),
    ("CashAndCashEquivalentsAtCarryingValue", "Cash and equivalents"),
)


class ResearchDataError(ValueError):
    """Raised when public macro/fundamental provider data is invalid."""


def safe_sec_cik(cik: Any = SEC_DEFAULT_COMPANY["cik"]) -> str:
    return "".join(ch for ch in str(cik) if ch.isdigit()).zfill(10)[-10:]


def sec_company_submissions_cache_path(cik: Any = SEC_DEFAULT_COMPANY["cik"]) -> str:
    return SEC_COMPANY_SUBMISSIONS_CACHE_PATH_TEMPLATE.format(cik=safe_sec_cik(cik))


def sec_xbrl_frame_params(
    taxonomy: Any = SEC_XBRL_FRAMES_DEFAULT["taxonomy"],
    tag: Any = SEC_XBRL_FRAMES_DEFAULT["tag"],
    unit: Any = SEC_XBRL_FRAMES_DEFAULT["unit"],
    period: Any = SEC_XBRL_FRAMES_DEFAULT["period"],
) -> dict[str, str]:
    return {
        "taxonomy": _safe_sec_frame_part(taxonomy, SEC_XBRL_FRAMES_DEFAULT["taxonomy"]),
        "tag": _safe_sec_frame_part(tag, SEC_XBRL_FRAMES_DEFAULT["tag"]),
        "unit": _safe_sec_frame_part(unit, SEC_XBRL_FRAMES_DEFAULT["unit"]),
        "period": _safe_sec_frame_part(period, SEC_XBRL_FRAMES_DEFAULT["period"]),
    }


def sec_xbrl_frame_url(
    taxonomy: Any = SEC_XBRL_FRAMES_DEFAULT["taxonomy"],
    tag: Any = SEC_XBRL_FRAMES_DEFAULT["tag"],
    unit: Any = SEC_XBRL_FRAMES_DEFAULT["unit"],
    period: Any = SEC_XBRL_FRAMES_DEFAULT["period"],
) -> str:
    params = sec_xbrl_frame_params(taxonomy, tag, unit, period)
    return SEC_XBRL_FRAMES_URL_TEMPLATE.format(
        taxonomy=quote(params["taxonomy"], safe=""),
        tag=quote(params["tag"], safe=""),
        unit=quote(params["unit"], safe=""),
        period=quote(params["period"], safe=""),
    )


def sec_xbrl_frame_cache_path(
    taxonomy: Any = SEC_XBRL_FRAMES_DEFAULT["taxonomy"],
    tag: Any = SEC_XBRL_FRAMES_DEFAULT["tag"],
    unit: Any = SEC_XBRL_FRAMES_DEFAULT["unit"],
    period: Any = SEC_XBRL_FRAMES_DEFAULT["period"],
) -> str:
    params = sec_xbrl_frame_params(taxonomy, tag, unit, period)
    return (
        "market_data/fundamentals/sec/frames/"
        f"{params['taxonomy']}/{params['tag']}/{params['unit']}/{params['period']}.json"
    )


def sec_company_submission_watchlist() -> tuple[dict[str, str], ...]:
    return tuple(dict(company) for company in SEC_DEFAULT_COMPANY_WATCHLIST)


def research_data_payload(
    sec_cache: dict[str, Any] | None = None,
    dbnomics_cache: dict[str, Any] | None = None,
    fred_cache: dict[str, Any] | None = None,
    bls_cache: dict[str, Any] | None = None,
    eurostat_cache: dict[str, Any] | None = None,
    bea_cache: dict[str, Any] | None = None,
    census_cache: dict[str, Any] | None = None,
    *,
    sec_ticker_cache: dict[str, Any] | None = None,
    sec_submissions_cache: dict[str, Any] | None = None,
    sec_frames_cache: dict[str, Any] | None = None,
    fetcher: Any | None = None,
    fred_payload: dict[str, Any] | None = None,
    fred_core_payload: dict[str, Any] | None = None,
    bls_payload: dict[str, Any] | None = None,
    eurostat_payload: dict[str, Any] | None = None,
    bea_payload: dict[str, Any] | None = None,
    census_payload: dict[str, Any] | None = None,
    refresh: bool = False,
) -> dict[str, Any]:
    """Return normalized no-key research data with provenance and gated options."""

    fetcher = fetcher or fetch_public_research_data
    source_errors: list[str] = []
    sec_payload = _coerce_sec_payload(sec_cache, state="stale")
    sec_tickers_payload = _coerce_sec_company_tickers_payload(sec_ticker_cache, state="stale")
    sec_submissions_payload = _coerce_sec_company_submissions_collection_payload(
        sec_submissions_cache,
        state="stale",
    )
    sec_frames_payload = _coerce_sec_xbrl_frames_payload(sec_frames_cache, state="stale")
    dbnomics_payload = _coerce_dbnomics_payload(dbnomics_cache, state="stale")
    fred_payload = (
        fred_payload
        if isinstance(fred_payload, dict)
        else fred_data_payload(fred_cache, None, refresh=False)
    )
    bls_payload = (
        bls_payload
        if isinstance(bls_payload, dict)
        else bls_data_payload(bls_cache, refresh=False)
    )
    eurostat_payload = (
        eurostat_payload
        if isinstance(eurostat_payload, dict)
        else eurostat_hicp_payload(eurostat_cache, refresh=False)
    )
    bea_payload = (
        bea_payload
        if isinstance(bea_payload, dict)
        else bea_regional_payload(bea_cache, None, refresh=False)
    )
    census_payload = (
        census_payload
        if isinstance(census_payload, dict)
        else census_acs_profile_payload(census_cache, None, refresh=False)
    )

    if refresh:
        try:
            fetched = fetcher()
        except (ResearchDataError, OSError, TimeoutError, urllib.error.URLError) as exc:
            source_errors.append(str(exc) or exc.__class__.__name__)
        else:
            if isinstance(fetched, dict):
                source_errors.extend(str(error) for error in fetched.get("errors", []) if str(error))
                fetched_sec = fetched.get("sec")
                fetched_sec_tickers = fetched.get("sec_tickers")
                fetched_sec_submissions = (
                    fetched.get("sec_submissions_by_symbol")
                    if isinstance(fetched.get("sec_submissions_by_symbol"), dict)
                    else fetched.get("sec_submissions")
                )
                fetched_sec_frames = fetched.get("sec_frames")
                fetched_dbnomics = fetched.get("dbnomics")
                fetched_bls = fetched.get("bls")
                fetched_eurostat = fetched.get("eurostat")
            else:
                fetched_sec = None
                fetched_sec_tickers = None
                fetched_sec_submissions = None
                fetched_sec_frames = None
                fetched_dbnomics = None
                fetched_bls = None
                fetched_eurostat = None
            if isinstance(fetched_sec, dict):
                try:
                    sec_payload = normalize_sec_companyfacts(fetched_sec, state="live")
                except ResearchDataError as exc:
                    source_errors.append(f"SEC: {exc}")
            if isinstance(fetched_sec_tickers, dict):
                try:
                    sec_tickers_payload = normalize_sec_company_tickers(
                        fetched_sec_tickers,
                        state="live",
                    )
                except ResearchDataError as exc:
                    source_errors.append(f"SEC tickers: {exc}")
            if isinstance(fetched_sec_submissions, dict):
                try:
                    sec_submissions_payload = normalize_sec_company_submissions_collection(
                        fetched_sec_submissions,
                        state="live",
                    )
                except ResearchDataError as exc:
                    source_errors.append(f"SEC submissions: {exc}")
            if isinstance(fetched_sec_frames, dict):
                try:
                    sec_frames_payload = normalize_sec_xbrl_frame(
                        fetched_sec_frames,
                        state="live",
                    )
                except ResearchDataError as exc:
                    source_errors.append(f"SEC frames: {exc}")
            if isinstance(fetched_dbnomics, dict):
                try:
                    dbnomics_payload = normalize_dbnomics_series(fetched_dbnomics, state="live")
                except ResearchDataError as exc:
                    source_errors.append(f"DBnomics: {exc}")
            if isinstance(fetched_bls, dict):
                try:
                    bls_payload = normalize_bls_latest_series(fetched_bls, state="live")
                except ValueError as exc:
                    source_errors.append(f"BLS: {exc}")
            if isinstance(fetched_eurostat, dict):
                try:
                    eurostat_payload = normalize_eurostat_hicp(fetched_eurostat, state="live")
                except ValueError as exc:
                    source_errors.append(f"Eurostat: {exc}")

    fundamentals = _fundamentals_section(sec_payload)
    equity_registry = _equity_registry_section(sec_tickers_payload)
    filings = _filings_section(sec_submissions_payload)
    sec_frames = _sec_xbrl_frames_section(sec_frames_payload)
    macro = _macro_section(
        dbnomics_payload,
        fred_payload,
        bls_payload,
        eurostat_payload,
        bea_payload,
        census_payload,
    )
    return {
        "status": _combined_status(
            fundamentals,
            equity_registry,
            filings,
            sec_frames,
            macro,
            source_errors,
        ),
        "fundamentals": fundamentals,
        "equity_registry": equity_registry,
        "filings": filings,
        "sec_frames": sec_frames,
        "macro": macro,
        "fred": _public_fred_payload(fred_payload),
        "fred_core": fred_core_payload if isinstance(fred_core_payload, dict) else {},
        "bls": _public_bls_payload(bls_payload),
        "eurostat": _public_eurostat_payload(eurostat_payload),
        "bea": _public_bea_payload(bea_payload),
        "census": _public_census_payload(census_payload),
        "optional_key_sources": _optional_key_sources(fred_payload, bea_payload, census_payload),
        "provider_entry": provider_entry_summary(),
        "cache": {
            "sec": sec_payload,
            "sec_tickers": sec_tickers_payload,
            "sec_submissions": sec_submissions_payload,
            "sec_frames": sec_frames_payload,
            "dbnomics": dbnomics_payload,
            "bls": _cacheable_bls_payload(bls_payload),
            "eurostat": _cacheable_eurostat_payload(eurostat_payload),
            "bea": _cacheable_bea_payload(bea_payload),
            "census": _cacheable_census_payload(census_payload),
        },
    }


def fetch_public_research_data() -> dict[str, Any]:
    """Fetch public no-key SEC reference/fundamental data plus macro series."""

    errors: list[str] = []
    sec_payload: dict[str, Any] = {}
    sec_tickers_payload: dict[str, Any] = {}
    sec_submissions_payload: dict[str, Any] = {}
    sec_submissions_by_symbol: dict[str, Any] = {}
    sec_frames_payload: dict[str, Any] = {}
    dbnomics_payload: dict[str, Any] = {}
    bls_payload: dict[str, Any] = {}
    eurostat_payload: dict[str, Any] = {}
    try:
        sec_payload = fetch_sec_companyfacts()
    except (OSError, urllib.error.URLError, json.JSONDecodeError, ResearchDataError) as exc:
        errors.append(f"SEC: {exc}")
    try:
        sec_tickers_payload = fetch_sec_company_tickers()
    except (OSError, urllib.error.URLError, json.JSONDecodeError, ResearchDataError) as exc:
        errors.append(f"SEC tickers: {exc}")
    for company in sec_company_submission_watchlist_candidates(sec_tickers_payload):
        symbol = company["symbol"]
        try:
            payload = fetch_sec_company_submissions(company["cik"])
        except (OSError, urllib.error.URLError, json.JSONDecodeError, ResearchDataError) as exc:
            errors.append(f"SEC submissions {symbol}: {exc}")
            continue
        sec_submissions_by_symbol[symbol] = payload
        if symbol == SEC_DEFAULT_COMPANY["symbol"]:
            sec_submissions_payload = payload
    try:
        sec_frames_payload = fetch_sec_xbrl_frame()
    except (OSError, urllib.error.URLError, json.JSONDecodeError, ResearchDataError) as exc:
        errors.append(f"SEC frames: {exc}")
    try:
        dbnomics_payload = fetch_dbnomics_series()
    except (OSError, urllib.error.URLError, json.JSONDecodeError, ResearchDataError) as exc:
        errors.append(f"DBnomics: {exc}")
    try:
        bls_payload = fetch_bls_latest_series()
    except (OSError, urllib.error.URLError, json.JSONDecodeError, ValueError) as exc:
        errors.append(f"BLS: {exc}")
    try:
        eurostat_payload = fetch_eurostat_hicp()
    except (OSError, urllib.error.URLError, json.JSONDecodeError, ValueError) as exc:
        errors.append(f"Eurostat: {exc}")
    if (
        not sec_payload
        and not sec_tickers_payload
        and not sec_submissions_by_symbol
        and not sec_frames_payload
        and not dbnomics_payload
        and not bls_payload
        and not eurostat_payload
        and errors
    ):
        raise ResearchDataError("Public research providers failed")
    return {
        "sec": sec_payload,
        "sec_tickers": sec_tickers_payload,
        "sec_submissions": sec_submissions_payload,
        "sec_submissions_by_symbol": sec_submissions_by_symbol,
        "sec_frames": sec_frames_payload,
        "dbnomics": dbnomics_payload,
        "bls": bls_payload,
        "eurostat": eurostat_payload,
        "errors": errors,
    }


def sec_company_submission_watchlist_candidates(
    sec_tickers_payload: dict[str, Any] | None = None,
) -> tuple[dict[str, str], ...]:
    """Return the bounded stock submissions watchlist with CIKs from the SEC registry when present."""

    registry = _sec_registry_symbol_ciks(sec_tickers_payload)
    candidates: list[dict[str, str]] = []
    for company in SEC_DEFAULT_COMPANY_WATCHLIST:
        symbol = company["symbol"]
        candidates.append(
            {
                "symbol": symbol,
                "cik": registry.get(symbol, company["cik"]),
                "label": company["label"],
            }
        )
    return tuple(candidates)


def _sec_registry_symbol_ciks(raw: dict[str, Any] | None) -> dict[str, str]:
    if not isinstance(raw, dict):
        return {}
    records: list[dict[str, Any]] = []
    if isinstance(raw.get("rows"), list):
        records = [row for row in raw.get("rows", []) if isinstance(row, dict)]
    else:
        records = [row for row in raw.values() if isinstance(row, dict)]
    mapping: dict[str, str] = {}
    for record in records:
        symbol = str(record.get("symbol") or record.get("ticker") or "").strip().upper()
        raw_cik = record.get("cik") if record.get("cik") is not None else record.get("cik_str")
        if not any(ch.isdigit() for ch in str(raw_cik)):
            continue
        cik = safe_sec_cik(raw_cik)
        if symbol and cik:
            mapping[symbol] = cik
    return mapping


def fetch_sec_companyfacts(cik: str = SEC_DEFAULT_COMPANY["cik"], timeout: float = 8.0) -> dict[str, Any]:
    safe_cik = safe_sec_cik(cik)
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{safe_cik}.json"
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": SEC_USER_AGENT,
            "Accept-Encoding": "gzip, deflate",
            "Host": "data.sec.gov",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = _read_json_response(response)
    if not isinstance(payload, dict):
        raise ResearchDataError("SEC company facts response must be an object")
    return payload


def fetch_sec_company_tickers(timeout: float = 8.0) -> dict[str, Any]:
    request = urllib.request.Request(
        SEC_COMPANY_TICKERS_URL,
        headers={
            "User-Agent": SEC_USER_AGENT,
            "Accept-Encoding": "gzip, deflate",
            "Host": "www.sec.gov",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = _read_json_response(response)
    if not isinstance(payload, dict):
        raise ResearchDataError("SEC company ticker registry response must be an object")
    return payload


def fetch_sec_company_submissions(
    cik: str = SEC_DEFAULT_COMPANY["cik"],
    timeout: float = 8.0,
) -> dict[str, Any]:
    safe_cik = safe_sec_cik(cik)
    request = urllib.request.Request(
        SEC_COMPANY_SUBMISSIONS_URL_TEMPLATE.format(cik=safe_cik),
        headers={
            "User-Agent": SEC_USER_AGENT,
            "Accept-Encoding": "gzip, deflate",
            "Host": "data.sec.gov",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = _read_json_response(response)
    if not isinstance(payload, dict):
        raise ResearchDataError("SEC company submissions response must be an object")
    return payload


def fetch_sec_xbrl_frame(
    taxonomy: str = SEC_XBRL_FRAMES_DEFAULT["taxonomy"],
    tag: str = SEC_XBRL_FRAMES_DEFAULT["tag"],
    unit: str = SEC_XBRL_FRAMES_DEFAULT["unit"],
    period: str = SEC_XBRL_FRAMES_DEFAULT["period"],
    timeout: float = 8.0,
) -> dict[str, Any]:
    request = urllib.request.Request(
        sec_xbrl_frame_url(taxonomy, tag, unit, period),
        headers={
            "User-Agent": SEC_USER_AGENT,
            "Accept-Encoding": "gzip, deflate",
            "Host": "data.sec.gov",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = _read_json_response(response)
    if not isinstance(payload, dict):
        raise ResearchDataError("SEC XBRL frames response must be an object")
    return payload


def fetch_dbnomics_series(
    provider: str = DBNOMICS_DEFAULT_SERIES["provider"],
    dataset: str = DBNOMICS_DEFAULT_SERIES["dataset"],
    series: str = DBNOMICS_DEFAULT_SERIES["series"],
    timeout: float = 8.0,
) -> dict[str, Any]:
    url = (
        "https://api.db.nomics.world/v22/series/"
        f"{quote(provider, safe='')}/{quote(dataset, safe='')}/{quote(series, safe='')}"
        "?observations=1"
    )
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "LocalTerminal/0.1 clean-room local research"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = _read_json_response(response)
    if not isinstance(payload, dict):
        raise ResearchDataError("DBnomics series response must be an object")
    return payload


def normalize_sec_companyfacts(
    raw: dict[str, Any],
    *,
    state: str = "live",
    retrieved_at: str | None = None,
) -> dict[str, Any]:
    if "companies" in raw and "status" in raw:
        return _coerce_sec_payload(raw, state=state)
    entity_name = str(raw.get("entityName") or SEC_DEFAULT_COMPANY["label"])
    cik = str(raw.get("cik") or SEC_DEFAULT_COMPANY["cik"]).zfill(10)[-10:]
    facts = _extract_sec_facts(raw)
    if not facts:
        raise ResearchDataError("SEC company facts payload has no supported US-GAAP facts")
    updated_at = retrieved_at or _utc_now()
    return {
        "status": _status(
            source="sec_edgar_public",
            state=state,
            last_update=updated_at,
            message="SEC company facts normalized from public no-key API.",
            provider_id="sec_edgar_public",
            cache_path=SEC_CACHE_PATH,
            docs_url=SEC_DOCS_URL,
        ),
        "companies": [
            {
                "symbol": SEC_DEFAULT_COMPANY["symbol"],
                "cik": cik,
                "entity_name": entity_name,
                "source": "sec_edgar_public",
                "provider_id": "sec_edgar_public",
                "retrieved_at": updated_at,
                "cache_path": SEC_CACHE_PATH,
                "docs_url": SEC_DOCS_URL,
                "facts": facts,
            }
        ],
    }


def normalize_sec_company_tickers(
    raw: dict[str, Any],
    *,
    state: str = "live",
    retrieved_at: str | None = None,
    symbols: tuple[str, ...] = SEC_DEFAULT_COMPANY_SYMBOLS,
) -> dict[str, Any]:
    if "rows" in raw and "status" in raw and isinstance(raw.get("rows"), list):
        return _coerce_sec_company_tickers_payload(raw, state=state)

    all_rows = [
        _row_from_sec_company_ticker_record(record)
        for record in raw.values()
        if isinstance(record, dict)
    ]
    all_rows = [row for row in all_rows if row is not None]
    if not all_rows:
        raise ResearchDataError("SEC company ticker registry has no usable company rows")

    rows_by_symbol = {row["symbol"]: row for row in all_rows}
    wanted_rows = [
        rows_by_symbol[symbol.upper()]
        for symbol in symbols
        if symbol.upper() in rows_by_symbol
    ]
    rows = wanted_rows or sorted(all_rows, key=lambda row: row["symbol"])[:MAX_SEC_COMPANY_TICKER_ROWS]
    updated_at = retrieved_at or _utc_now()
    for row in rows:
        row.update(
            {
                "source": "sec_company_ticker_registry",
                "provider_id": SEC_COMPANY_TICKERS_PROVIDER_ID,
                "retrieved_at": updated_at,
                "cache_path": SEC_COMPANY_TICKERS_CACHE_PATH,
                "docs_url": SEC_COMPANY_TICKERS_URL,
                "reference_only": True,
            }
        )
    return {
        "status": _status(
            source="sec_company_ticker_registry",
            state=state,
            last_update=updated_at,
            message=(
                "SEC public company ticker registry normalized from no-key JSON; "
                "this is issuer reference data, not stock quotes."
            ),
            provider_id=SEC_COMPANY_TICKERS_PROVIDER_ID,
            cache_path=SEC_COMPANY_TICKERS_CACHE_PATH,
            docs_url=SEC_COMPANY_TICKERS_URL,
        ),
        "rows": rows,
        "summary": {
            "row_count": len(rows),
            "registry_total": len(all_rows),
            "matched_symbols": ",".join(row["symbol"] for row in rows),
            "quote_state": "disabled_until_optional_quote_provider",
            "quote_provider": "alphavantage_global_quote_optional_key",
            "source": "sec_company_ticker_registry",
        },
    }


def normalize_sec_company_submissions(
    raw: dict[str, Any],
    *,
    state: str = "live",
    retrieved_at: str | None = None,
) -> dict[str, Any]:
    if "rows" in raw and "status" in raw and isinstance(raw.get("rows"), list):
        return _coerce_sec_company_submissions_payload(raw, state=state)

    recent = raw.get("filings", {}).get("recent") if isinstance(raw.get("filings"), dict) else {}
    if not isinstance(recent, dict):
        raise ResearchDataError("SEC submissions payload has no recent filings object")

    accession_numbers = _submission_column(recent, "accessionNumber")
    if not accession_numbers:
        raise ResearchDataError("SEC submissions payload has no recent accession numbers")

    updated_at = retrieved_at or _utc_now()
    cik = safe_sec_cik(raw.get("cik") or SEC_DEFAULT_COMPANY["cik"])
    entity_name = str(raw.get("name") or SEC_DEFAULT_COMPANY["label"])
    tickers = raw.get("tickers") if isinstance(raw.get("tickers"), list) else []
    symbol = str(tickers[0] if tickers else SEC_DEFAULT_COMPANY["symbol"]).upper()
    cache_path = sec_company_submissions_cache_path(cik)
    rows = [
        row
        for row in (
            _sec_submission_row_from_recent(
                recent,
                index,
                symbol=symbol,
                cik=cik,
                entity_name=entity_name,
                retrieved_at=updated_at,
                cache_path=cache_path,
            )
            for index in range(min(len(accession_numbers), MAX_SEC_SUBMISSION_ROWS))
        )
        if row is not None
    ]
    if not rows:
        raise ResearchDataError("SEC submissions payload has no usable recent filing rows")

    latest = rows[0]
    return {
        "status": _status(
            source="sec_company_submissions",
            state=state,
            last_update=updated_at,
            message=(
                "SEC company submissions normalized from public no-key API; "
                "filings are issuer reference metadata, not executable quotes."
            ),
            provider_id=SEC_COMPANY_SUBMISSIONS_PROVIDER_ID,
            cache_path=cache_path,
            docs_url=SEC_DOCS_URL,
        ),
        "rows": rows,
        "summary": {
            "row_count": len(rows),
            "latest_filing_date": str(latest.get("filing_date") or ""),
            "latest_form": str(latest.get("form") or ""),
            "symbol": symbol,
            "cik": cik,
            "source": "sec_company_submissions",
        },
    }


def normalize_sec_company_submissions_collection(
    raw: dict[str, Any],
    *,
    state: str = "live",
    retrieved_at: str | None = None,
) -> dict[str, Any]:
    if "rows" in raw and "status" in raw and isinstance(raw.get("rows"), list):
        return _coerce_sec_company_submissions_payload(raw, state=state)
    if "filings" in raw or "cik" in raw:
        return normalize_sec_company_submissions(raw, state=state, retrieved_at=retrieved_at)

    if isinstance(raw.get("by_symbol"), dict):
        raw_by_symbol = raw["by_symbol"]
    elif isinstance(raw.get("by_cik"), dict):
        raw_by_symbol = raw["by_cik"]
    else:
        raw_by_symbol = raw

    if not isinstance(raw_by_symbol, dict):
        return _empty_sec_company_submissions_payload()

    rows: list[dict[str, Any]] = []
    company_summaries: list[dict[str, Any]] = []
    source_errors: list[str] = []
    for key, payload in _ordered_submission_payloads(raw_by_symbol):
        if not isinstance(payload, dict) or not payload:
            continue
        try:
            normalized = normalize_sec_company_submissions(
                payload,
                state=state,
                retrieved_at=retrieved_at,
            )
        except ResearchDataError as exc:
            source_errors.append(f"{key}: {exc}")
            continue
        normalized_rows = [row for row in normalized.get("rows", []) if isinstance(row, dict)]
        if not normalized_rows:
            continue
        rows.extend(normalized_rows)
        summary = normalized.get("summary") if isinstance(normalized.get("summary"), dict) else {}
        status = normalized.get("status") if isinstance(normalized.get("status"), dict) else {}
        company_summaries.append(
            {
                "symbol": str(summary.get("symbol") or key).upper(),
                "cik": safe_sec_cik(summary.get("cik") or normalized_rows[0].get("cik")),
                "entity_name": str(normalized_rows[0].get("entity_name") or ""),
                "row_count": len(normalized_rows),
                "latest_filing_date": str(summary.get("latest_filing_date") or ""),
                "latest_form": str(summary.get("latest_form") or ""),
                "cache_path": str(status.get("cache_path") or ""),
                "state": str(status.get("state") or state),
            }
        )

    if not rows:
        payload = _empty_sec_company_submissions_payload()
        if source_errors:
            payload["status"] = {
                **payload["status"],
                "message": "SEC company submissions watchlist had no usable filing rows.",
                "source_errors": source_errors[:5],
            }
        return payload

    rows = sorted(
        rows,
        key=lambda row: (
            str(row.get("filing_date") or ""),
            str(row.get("acceptance_datetime") or ""),
            str(row.get("symbol") or ""),
        ),
        reverse=True,
    )
    latest = rows[0]
    cache_paths = [summary["cache_path"] for summary in company_summaries if summary["cache_path"]]
    symbols = [summary["symbol"] for summary in company_summaries if summary["symbol"]]
    updated_at = retrieved_at or _latest_submission_timestamp(rows)
    return {
        "status": _status(
            source="sec_company_submissions",
            state=state,
            last_update=updated_at,
            message=(
                "SEC company submissions watchlist normalized from public no-key API; "
                "filings are issuer reference metadata, not executable quotes."
            ),
            provider_id=SEC_COMPANY_SUBMISSIONS_PROVIDER_ID,
            cache_path=cache_paths[0] if cache_paths else SEC_COMPANY_SUBMISSIONS_CACHE_PATH,
            docs_url=SEC_DOCS_URL,
        ),
        "rows": rows,
        "company_summaries": company_summaries,
        "summary": {
            **_filings_summary_from_rows(rows),
            "row_count": len(rows),
            "company_count": len(company_summaries),
            "symbol_count": len(set(symbols)),
            "symbols": ",".join(symbols),
            "filing_symbols": ",".join(symbols),
            "latest_symbol": str(latest.get("symbol") or ""),
            "cache_paths": ",".join(cache_paths),
            "source_error_count": len(source_errors),
            "source": "sec_company_submissions",
        },
        "source_errors": source_errors[:5],
    }


def normalize_sec_xbrl_frame(
    raw: dict[str, Any],
    *,
    state: str = "live",
    retrieved_at: str | None = None,
) -> dict[str, Any]:
    if "rows" in raw and "status" in raw and isinstance(raw.get("rows"), list):
        return _coerce_sec_xbrl_frames_payload(raw, state=state)

    data = raw.get("data")
    if not isinstance(data, list):
        raise ResearchDataError("SEC XBRL frame payload has no data rows")

    updated_at = retrieved_at or _utc_now()
    taxonomy = _safe_sec_frame_part(raw.get("taxonomy"), SEC_XBRL_FRAMES_DEFAULT["taxonomy"])
    tag = _safe_sec_frame_part(raw.get("tag"), SEC_XBRL_FRAMES_DEFAULT["tag"])
    unit = _safe_sec_frame_part(raw.get("uom"), SEC_XBRL_FRAMES_DEFAULT["unit"])
    period = _safe_sec_frame_part(raw.get("ccp"), SEC_XBRL_FRAMES_DEFAULT["period"])
    cache_path = sec_xbrl_frame_cache_path(taxonomy, tag, unit, period)
    all_rows = [
        row
        for row in (
            _sec_xbrl_frame_row(
                record,
                taxonomy=taxonomy,
                tag=tag,
                unit=unit,
                period=period,
                retrieved_at=updated_at,
                cache_path=cache_path,
            )
            for record in data
            if isinstance(record, dict)
        )
        if row is not None
    ]
    if not all_rows:
        raise ResearchDataError("SEC XBRL frame payload has no usable company rows")
    rows = _bounded_sec_xbrl_frame_rows(all_rows)
    return {
        "status": _status(
            source="sec_xbrl_frames",
            state=state,
            last_update=updated_at,
            message=(
                "SEC XBRL frame normalized from public no-key API; "
                "cross-company fundamentals are reference context, not quotes."
            ),
            provider_id=SEC_XBRL_FRAMES_PROVIDER_ID,
            cache_path=cache_path,
            docs_url=SEC_DOCS_URL,
        ),
        "rows": rows,
        "summary": {
            "row_count": len(rows),
            "source_row_count": len(all_rows),
            "entity_count": len({row["cik"] for row in rows}),
            "taxonomy": taxonomy,
            "tag": tag,
            "unit": unit,
            "period": period,
            "label": str(raw.get("label") or tag),
            "description": str(raw.get("description") or "")[:240],
            "source": "sec_xbrl_frames",
            "quote_semantics": "not_quote",
        },
    }


def normalize_dbnomics_series(
    raw: dict[str, Any],
    *,
    state: str = "live",
    retrieved_at: str | None = None,
) -> dict[str, Any]:
    if "series" in raw and "status" in raw and isinstance(raw.get("series"), list):
        return _coerce_dbnomics_payload(raw, state=state)
    docs = raw.get("series", {}).get("docs") if isinstance(raw.get("series"), dict) else None
    docs = docs if isinstance(docs, list) else []
    if not docs or not isinstance(docs[0], dict):
        raise ResearchDataError("DBnomics response has no series docs")
    doc = docs[0]
    periods = doc.get("period")
    values = doc.get("value")
    periods = periods if isinstance(periods, list) else []
    values = values if isinstance(values, list) else []
    latest_period = ""
    latest_value = ""
    observation_count = 0
    for period, value in zip(periods, values, strict=False):
        if value in (None, "", "NA"):
            continue
        observation_count += 1
        latest_period = str(period)
        latest_value = str(value)
    if not latest_period:
        raise ResearchDataError("DBnomics series has no numeric observations")
    updated_at = retrieved_at or _utc_now()
    provider = str(doc.get("provider_code") or DBNOMICS_DEFAULT_SERIES["provider"])
    dataset = str(doc.get("dataset_code") or DBNOMICS_DEFAULT_SERIES["dataset"])
    series_code = str(doc.get("series_code") or DBNOMICS_DEFAULT_SERIES["series"])
    return {
        "status": _status(
            source="dbnomics_public",
            state=state,
            last_update=updated_at,
            message="DBnomics macro series normalized from public no-key API.",
            provider_id="dbnomics_public",
            cache_path=DBNOMICS_CACHE_PATH,
            docs_url=DBNOMICS_DOCS_URL,
        ),
        "series": [
            {
                "series_id": f"{provider}/{dataset}/{series_code}",
                "label": str(doc.get("series_name") or DBNOMICS_DEFAULT_SERIES["label"]),
                "dataset_name": str(doc.get("dataset_name") or dataset),
                "source": "dbnomics_public",
                "provider_id": "dbnomics_public",
                "source_provider": provider,
                "dataset": dataset,
                "retrieved_at": updated_at,
                "cache_path": DBNOMICS_CACHE_PATH,
                "docs_url": DBNOMICS_DOCS_URL,
                "latest_period": latest_period,
                "latest_value": latest_value,
                "observation_count": observation_count,
                "frequency": str(doc.get("@frequency") or ""),
                "indexed_at": str(doc.get("indexed_at") or ""),
            }
        ],
    }


def provider_entry_summary() -> dict[str, Any]:
    return {
        "docs_checked_at": DOCS_CHECKED_AT,
        "providers": [
            {
                "provider_id": "sec_edgar_public",
                "official_docs": SEC_DOCS_URL,
                "auth_mode": "no-key",
                "rate_limit": "SEC fair access guidance: no more than 10 requests per second.",
                "terms_risk": "Public SEC data; use respectful User-Agent and source attribution.",
                "cache_path": SEC_CACHE_PATH,
                "ttl_seconds": 86400,
                "schema": "companyfacts -> company fact rows",
                "safety_class": "public_read_only_fundamentals",
            },
            {
                "provider_id": SEC_COMPANY_TICKERS_PROVIDER_ID,
                "official_docs": SEC_COMPANY_TICKERS_URL,
                "auth_mode": "no-key",
                "rate_limit": "Use daily local cache and comply with SEC fair-access guidance.",
                "terms_risk": (
                    "Public SEC company ticker mapping; preserve source attribution and "
                    "do not present registry rows as executable stock quotes."
                ),
                "cache_path": SEC_COMPANY_TICKERS_CACHE_PATH,
                "ttl_seconds": SEC_COMPANY_TICKERS_TTL_SECONDS,
                "schema": "company_tickers.json objects -> company ticker registry rows",
                "safety_class": "public_read_only_company_reference",
            },
            {
                "provider_id": SEC_COMPANY_SUBMISSIONS_PROVIDER_ID,
                "official_docs": SEC_DOCS_URL,
                "auth_mode": "no-key",
                "rate_limit": "Use daily local cache and comply with SEC fair-access guidance.",
                "terms_risk": (
                    "Public SEC filing metadata; preserve source attribution and "
                    "do not represent recent filings as quotes, advice, or executable signals."
                ),
                "cache_path": SEC_COMPANY_SUBMISSIONS_CACHE_PATH,
                "ttl_seconds": SEC_COMPANY_SUBMISSIONS_TTL_SECONDS,
                "schema": "submissions filings.recent column arrays -> recent filing rows",
                "safety_class": "public_read_only_company_filings",
            },
            {
                "provider_id": SEC_XBRL_FRAMES_PROVIDER_ID,
                "official_docs": SEC_DOCS_URL,
                "auth_mode": "no-key",
                "rate_limit": "Use daily local cache and comply with SEC fair-access guidance.",
                "terms_risk": (
                    "Public SEC XBRL frame data; preserve source attribution and "
                    "never present cross-company fundamentals as executable quotes."
                ),
                "cache_path": SEC_XBRL_FRAMES_CACHE_PATH,
                "ttl_seconds": SEC_XBRL_FRAMES_TTL_SECONDS,
                "schema": "frames taxonomy/tag/unit/period data rows -> bounded fundamental rows",
                "safety_class": "public_read_only_fundamental_frames",
            },
            {
                "provider_id": "dbnomics_public",
                "official_docs": DBNOMICS_DOCS_URL,
                "auth_mode": "no-key",
                "rate_limit": "Use daily local cache; verify provider-specific limits before broad fetches.",
                "terms_risk": "DBnomics preserves original source terms; show source provider/dataset.",
                "cache_path": DBNOMICS_CACHE_PATH,
                "ttl_seconds": 86400,
                "schema": "series docs -> latest macro observation",
                "safety_class": "public_read_only_macro",
            },
            bls_provider_entry_summary(),
            eurostat_provider_entry_summary(),
            fred_provider_entry_summary(),
            bea_provider_entry_summary(),
            census_provider_entry_summary(),
        ],
    }


def _coerce_sec_payload(raw: dict[str, Any] | None, *, state: str) -> dict[str, Any]:
    if not isinstance(raw, dict) or not raw:
        return _empty_sec_payload()
    if "companies" in raw and "status" in raw:
        payload = dict(raw)
        status = dict(payload.get("status") or {})
        status["state"] = _cache_state(status.get("state"), state)
        payload["status"] = status
        return payload
    try:
        return normalize_sec_companyfacts(raw, state=state)
    except ResearchDataError:
        return _empty_sec_payload()


def _coerce_sec_company_tickers_payload(
    raw: dict[str, Any] | None,
    *,
    state: str,
) -> dict[str, Any]:
    if not isinstance(raw, dict) or not raw:
        return _empty_sec_company_tickers_payload()
    if "rows" in raw and "status" in raw and isinstance(raw.get("rows"), list):
        payload = dict(raw)
        status = dict(payload.get("status") or {})
        status["state"] = _cache_state(status.get("state"), state)
        payload["status"] = status
        rows = [row for row in payload.get("rows", []) if isinstance(row, dict)]
        payload["rows"] = rows
        summary = payload.get("summary")
        if not isinstance(summary, dict):
            summary = _equity_registry_summary_from_rows(rows)
        payload["summary"] = summary
        return payload
    try:
        return normalize_sec_company_tickers(raw, state=state)
    except ResearchDataError:
        return _empty_sec_company_tickers_payload()


def _coerce_sec_company_submissions_payload(
    raw: dict[str, Any] | None,
    *,
    state: str,
) -> dict[str, Any]:
    if not isinstance(raw, dict) or not raw:
        return _empty_sec_company_submissions_payload()
    if "rows" in raw and "status" in raw and isinstance(raw.get("rows"), list):
        payload = dict(raw)
        status = dict(payload.get("status") or {})
        status["state"] = _cache_state(status.get("state"), state)
        payload["status"] = status
        rows = [row for row in payload.get("rows", []) if isinstance(row, dict)]
        payload["rows"] = rows
        summary = payload.get("summary")
        if not isinstance(summary, dict):
            summary = _filings_summary_from_rows(rows)
        payload["summary"] = {**_filings_summary_from_rows(rows), **summary}
        return payload
    try:
        return normalize_sec_company_submissions(raw, state=state)
    except ResearchDataError:
        return _empty_sec_company_submissions_payload()


def _coerce_sec_company_submissions_collection_payload(
    raw: dict[str, Any] | None,
    *,
    state: str,
) -> dict[str, Any]:
    if not isinstance(raw, dict) or not raw:
        return _empty_sec_company_submissions_payload()
    if "rows" in raw and "status" in raw and isinstance(raw.get("rows"), list):
        return _coerce_sec_company_submissions_payload(raw, state=state)
    if "filings" in raw or "cik" in raw:
        return _coerce_sec_company_submissions_payload(raw, state=state)
    if isinstance(raw.get("by_symbol"), dict) or isinstance(raw.get("by_cik"), dict):
        return normalize_sec_company_submissions_collection(raw, state=state)
    if any(isinstance(value, dict) for value in raw.values()):
        return normalize_sec_company_submissions_collection(raw, state=state)
    return _coerce_sec_company_submissions_payload(raw, state=state)


def _coerce_sec_xbrl_frames_payload(raw: dict[str, Any] | None, *, state: str) -> dict[str, Any]:
    if not isinstance(raw, dict) or not raw:
        return _empty_sec_xbrl_frames_payload()
    if "rows" in raw and "status" in raw and isinstance(raw.get("rows"), list):
        payload = dict(raw)
        status = dict(payload.get("status") or {})
        status["state"] = _cache_state(status.get("state"), state)
        payload["status"] = status
        rows = [row for row in payload.get("rows", []) if isinstance(row, dict)]
        payload["rows"] = rows[:MAX_SEC_XBRL_FRAME_ROWS]
        summary = payload.get("summary")
        if not isinstance(summary, dict):
            summary = _sec_xbrl_frames_summary_from_rows(rows)
        payload["summary"] = {
            **_sec_xbrl_frames_summary_from_rows(payload["rows"]),
            **summary,
            "row_count": len(payload["rows"]),
        }
        return payload
    try:
        return normalize_sec_xbrl_frame(raw, state=state)
    except ResearchDataError:
        return _empty_sec_xbrl_frames_payload()


def _coerce_dbnomics_payload(raw: dict[str, Any] | None, *, state: str) -> dict[str, Any]:
    if not isinstance(raw, dict) or not raw:
        return _empty_dbnomics_payload()
    if "series" in raw and "status" in raw and isinstance(raw.get("series"), list):
        payload = dict(raw)
        status = dict(payload.get("status") or {})
        status["state"] = _cache_state(status.get("state"), state)
        payload["status"] = status
        return payload
    try:
        return normalize_dbnomics_series(raw, state=state)
    except ResearchDataError:
        return _empty_dbnomics_payload()


def _empty_sec_payload() -> dict[str, Any]:
    return {
        "status": _status(
            source="sec_edgar_public",
            state="unavailable",
            last_update="not refreshed",
            message="No SEC company facts cache is available yet.",
            provider_id="sec_edgar_public",
            cache_path=SEC_CACHE_PATH,
            docs_url=SEC_DOCS_URL,
        ),
        "companies": [],
    }


def _empty_sec_company_tickers_payload() -> dict[str, Any]:
    return {
        "status": _status(
            source="sec_company_ticker_registry",
            state="unavailable",
            last_update="not refreshed",
            message="No SEC company ticker registry cache is available yet.",
            provider_id=SEC_COMPANY_TICKERS_PROVIDER_ID,
            cache_path=SEC_COMPANY_TICKERS_CACHE_PATH,
            docs_url=SEC_COMPANY_TICKERS_URL,
        ),
        "rows": [],
        "summary": {
            "row_count": 0,
            "registry_total": 0,
            "matched_symbols": "",
            "quote_state": "disabled_until_optional_quote_provider",
            "quote_provider": "alphavantage_global_quote_optional_key",
            "source": "sec_company_ticker_registry",
        },
    }


def _empty_sec_company_submissions_payload() -> dict[str, Any]:
    return {
        "status": _status(
            source="sec_company_submissions",
            state="unavailable",
            last_update="not refreshed",
            message="No SEC company submissions cache is available yet.",
            provider_id=SEC_COMPANY_SUBMISSIONS_PROVIDER_ID,
            cache_path=SEC_COMPANY_SUBMISSIONS_CACHE_PATH,
            docs_url=SEC_DOCS_URL,
        ),
        "rows": [],
        "summary": {
            "row_count": 0,
            "latest_filing_date": "",
            "latest_form": "",
            "symbol": SEC_DEFAULT_COMPANY["symbol"],
            "cik": SEC_DEFAULT_COMPANY["cik"],
            "company_count": 0,
            "symbol_count": 0,
            "symbols": "",
            "filing_symbols": "",
            "latest_symbol": "",
            "cache_paths": "",
            "source_error_count": 0,
            "source": "sec_company_submissions",
        },
    }


def _empty_sec_xbrl_frames_payload() -> dict[str, Any]:
    return {
        "status": _status(
            source="sec_xbrl_frames",
            state="unavailable",
            last_update="not refreshed",
            message="No SEC XBRL frame cache is available yet.",
            provider_id=SEC_XBRL_FRAMES_PROVIDER_ID,
            cache_path=SEC_XBRL_FRAMES_CACHE_PATH,
            docs_url=SEC_DOCS_URL,
        ),
        "rows": [],
        "summary": {
            "row_count": 0,
            "source_row_count": 0,
            "entity_count": 0,
            "taxonomy": SEC_XBRL_FRAMES_DEFAULT["taxonomy"],
            "tag": SEC_XBRL_FRAMES_DEFAULT["tag"],
            "unit": SEC_XBRL_FRAMES_DEFAULT["unit"],
            "period": SEC_XBRL_FRAMES_DEFAULT["period"],
            "label": SEC_XBRL_FRAMES_DEFAULT["tag"],
            "description": "",
            "source": "sec_xbrl_frames",
            "quote_semantics": "not_quote",
        },
    }


def _empty_dbnomics_payload() -> dict[str, Any]:
    return {
        "status": _status(
            source="dbnomics_public",
            state="unavailable",
            last_update="not refreshed",
            message="No DBnomics macro cache is available yet.",
            provider_id="dbnomics_public",
            cache_path=DBNOMICS_CACHE_PATH,
            docs_url=DBNOMICS_DOCS_URL,
        ),
        "series": [],
    }


def _fundamentals_section(sec_payload: dict[str, Any]) -> dict[str, Any]:
    companies = [company for company in sec_payload.get("companies", []) if isinstance(company, dict)]
    fact_count = sum(len(company.get("facts", [])) for company in companies)
    return {
        "status": dict(sec_payload.get("status") or {}),
        "companies": companies,
        "summary": {
            "company_count": len(companies),
            "fact_count": fact_count,
            "source": "sec_edgar_public",
        },
    }


def _equity_registry_section(sec_tickers_payload: dict[str, Any]) -> dict[str, Any]:
    rows = [row for row in sec_tickers_payload.get("rows", []) if isinstance(row, dict)]
    summary = (
        sec_tickers_payload.get("summary")
        if isinstance(sec_tickers_payload.get("summary"), dict)
        else {}
    )
    return {
        "status": dict(sec_tickers_payload.get("status") or {}),
        "rows": rows,
        "summary": {
            **_equity_registry_summary_from_rows(rows),
            **summary,
            "row_count": len(rows),
        },
    }


def _filings_section(sec_submissions_payload: dict[str, Any]) -> dict[str, Any]:
    rows = [row for row in sec_submissions_payload.get("rows", []) if isinstance(row, dict)]
    summary = (
        sec_submissions_payload.get("summary")
        if isinstance(sec_submissions_payload.get("summary"), dict)
        else {}
    )
    return {
        "status": dict(sec_submissions_payload.get("status") or {}),
        "rows": rows,
        "summary": {
            **_filings_summary_from_rows(rows),
            **summary,
            "row_count": len(rows),
        },
    }


def _sec_xbrl_frames_section(sec_frames_payload: dict[str, Any]) -> dict[str, Any]:
    rows = [row for row in sec_frames_payload.get("rows", []) if isinstance(row, dict)]
    summary = (
        sec_frames_payload.get("summary")
        if isinstance(sec_frames_payload.get("summary"), dict)
        else {}
    )
    return {
        "status": dict(sec_frames_payload.get("status") or {}),
        "rows": rows,
        "summary": {
            **_sec_xbrl_frames_summary_from_rows(rows),
            **summary,
            "row_count": len(rows),
        },
    }


def _macro_section(
    dbnomics_payload: dict[str, Any],
    fred_payload: dict[str, Any],
    bls_payload: dict[str, Any],
    eurostat_payload: dict[str, Any],
    bea_payload: dict[str, Any],
    census_payload: dict[str, Any],
) -> dict[str, Any]:
    series = [row for row in dbnomics_payload.get("series", []) if isinstance(row, dict)]
    fred_series = [row for row in fred_payload.get("series", []) if isinstance(row, dict)]
    bls_series = [row for row in bls_payload.get("series", []) if isinstance(row, dict)]
    eurostat_series = [
        row for row in eurostat_payload.get("series", []) if isinstance(row, dict)
    ]
    bea_series = [row for row in bea_payload.get("series", []) if isinstance(row, dict)]
    census_series = [row for row in census_payload.get("series", []) if isinstance(row, dict)]
    all_series = [
        *series,
        *fred_series,
        *bls_series,
        *eurostat_series,
        *bea_series,
        *census_series,
    ]
    headline = _macro_headline_series(all_series)
    provider_summaries = _macro_provider_summaries(
        [
            _macro_provider_candidate(dbnomics_payload),
            _macro_provider_candidate(fred_payload),
            _macro_provider_candidate(bls_payload),
            _macro_provider_candidate(eurostat_payload),
            _macro_provider_candidate(bea_payload),
            _macro_provider_candidate(census_payload),
        ],
        headline,
    )
    status = _macro_status(
        dbnomics_payload,
        fred_payload,
        bls_payload,
        eurostat_payload,
        bea_payload,
        census_payload,
    )
    return {
        "status": status,
        "series": all_series,
        "headline_series": headline,
        "provider_summaries": provider_summaries,
        "summary": {
            "series_count": len(all_series),
            "provider_count": len(
                [row for row in provider_summaries if int(row.get("series_count") or 0) > 0]
            ),
            "latest_period": str(headline.get("latest_period") or ""),
            "latest_value": str(headline.get("latest_value") or ""),
            "primary_provider": str(headline.get("provider_id") or ""),
            "headline_series_id": str(headline.get("series_id") or ""),
            "headline_label": str(headline.get("label") or ""),
            "headline_rule": MACRO_HEADLINE_RULE,
            "source": str(status.get("source") or "macro_provider_mix"),
        },
    }


def _macro_status(
    dbnomics_payload: dict[str, Any],
    fred_payload: dict[str, Any],
    bls_payload: dict[str, Any],
    eurostat_payload: dict[str, Any],
    bea_payload: dict[str, Any],
    census_payload: dict[str, Any],
) -> dict[str, Any]:
    candidates = [
        _macro_provider_candidate(dbnomics_payload),
        _macro_provider_candidate(fred_payload),
        _macro_provider_candidate(bls_payload),
        _macro_provider_candidate(eurostat_payload),
        _macro_provider_candidate(bea_payload),
        _macro_provider_candidate(census_payload),
    ]
    active = [candidate for candidate in candidates if candidate["series"]]
    if not active:
        return dict(dbnomics_payload.get("status") or {})
    if len(active) == 1:
        return dict(active[0]["status"])
    state = active[0]["state"]
    latest = ""
    for candidate in active:
        state = _best_state(state, candidate["state"])
        latest = _latest_timestamp(latest, candidate["last_update"])
    cache_paths = [
        path
        for path in (candidate["cache_path"] for candidate in active)
        if path
    ]
    docs_urls = [candidate["docs_url"] for candidate in active if candidate["docs_url"]]
    provider_ids = [candidate["provider_id"] for candidate in active if candidate["provider_id"]]
    return {
        "source": "macro_provider_mix",
        "state": state,
        "last_update": latest or "not refreshed",
        "message": "Multiple macro providers are available with source attribution.",
        "provider_id": "/".join(provider_ids),
        "cache_path": ",".join(cache_paths),
        "docs_url": ",".join(docs_urls),
    }


def _public_fred_payload(fred_payload: dict[str, Any]) -> dict[str, Any]:
    public = dict(fred_payload)
    public.pop("cache", None)
    return public


def _public_bls_payload(bls_payload: dict[str, Any]) -> dict[str, Any]:
    public = dict(bls_payload)
    public.pop("cache", None)
    return public


def _public_eurostat_payload(eurostat_payload: dict[str, Any]) -> dict[str, Any]:
    public = dict(eurostat_payload)
    public.pop("cache", None)
    return public


def _public_bea_payload(bea_payload: dict[str, Any]) -> dict[str, Any]:
    public = dict(bea_payload)
    public.pop("cache", None)
    return public


def _public_census_payload(census_payload: dict[str, Any]) -> dict[str, Any]:
    public = dict(census_payload)
    public.pop("cache", None)
    return public


def _cacheable_bls_payload(bls_payload: dict[str, Any]) -> dict[str, Any]:
    cache = bls_payload.get("cache") if isinstance(bls_payload, dict) else {}
    if isinstance(cache, dict) and isinstance(cache.get("bls"), dict):
        return cache["bls"]
    return bls_payload


def _cacheable_eurostat_payload(eurostat_payload: dict[str, Any]) -> dict[str, Any]:
    cache = eurostat_payload.get("cache") if isinstance(eurostat_payload, dict) else {}
    if isinstance(cache, dict) and isinstance(cache.get("eurostat"), dict):
        return cache["eurostat"]
    return eurostat_payload


def _cacheable_bea_payload(bea_payload: dict[str, Any]) -> dict[str, Any]:
    cache = bea_payload.get("cache") if isinstance(bea_payload, dict) else {}
    if isinstance(cache, dict) and isinstance(cache.get("bea"), dict):
        return cache["bea"]
    return bea_payload


def _cacheable_census_payload(census_payload: dict[str, Any]) -> dict[str, Any]:
    cache = census_payload.get("cache") if isinstance(census_payload, dict) else {}
    if isinstance(cache, dict) and isinstance(cache.get("census"), dict):
        return cache["census"]
    return census_payload


def _macro_headline_series(series: list[dict[str, Any]]) -> dict[str, Any]:
    for provider_id in MACRO_HEADLINE_PROVIDER_PRIORITY:
        for row in series:
            if row.get("provider_id") == provider_id:
                return dict(row)
    for row in series:
        return dict(row)
    return {}


def _macro_provider_summaries(
    candidates: list[dict[str, Any]],
    headline: dict[str, Any],
) -> list[dict[str, Any]]:
    selected_provider = str(headline.get("provider_id") or "")
    summaries: list[dict[str, Any]] = []
    for candidate in candidates:
        series = candidate["series"]
        first = series[0] if series and isinstance(series[0], dict) else {}
        provider_id = candidate["provider_id"]
        summaries.append(
            {
                "provider_id": provider_id,
                "state": candidate["state"],
                "series_count": len(series),
                "latest_period": str(first.get("latest_period") or ""),
                "latest_value": str(first.get("latest_value") or ""),
                "cache_path": candidate["cache_path"],
                "docs_url": candidate["docs_url"],
                "selected_for_headline": bool(provider_id and provider_id == selected_provider),
            }
        )
    return summaries


def _macro_provider_candidate(payload: dict[str, Any]) -> dict[str, Any]:
    status = dict(payload.get("status") or {})
    series = payload.get("series") if isinstance(payload.get("series"), list) else []
    return {
        "status": status,
        "series": series,
        "state": str(status.get("state") or "unavailable"),
        "last_update": str(status.get("last_update") or ""),
        "cache_path": str(status.get("cache_path") or ""),
        "docs_url": str(status.get("docs_url") or ""),
        "provider_id": str(status.get("provider_id") or ""),
    }


def _submission_column(recent: dict[str, Any], key: str) -> list[Any]:
    values = recent.get(key)
    return values if isinstance(values, list) else []


def _submission_value(recent: dict[str, Any], key: str, index: int) -> str:
    values = _submission_column(recent, key)
    if index >= len(values):
        return ""
    value = values[index]
    return "" if value is None else str(value)


def _sec_submission_row_from_recent(
    recent: dict[str, Any],
    index: int,
    *,
    symbol: str,
    cik: str,
    entity_name: str,
    retrieved_at: str,
    cache_path: str,
) -> dict[str, Any] | None:
    accession_number = _submission_value(recent, "accessionNumber", index).strip()
    form = _submission_value(recent, "form", index).strip()
    filing_date = _submission_value(recent, "filingDate", index).strip()
    primary_document = _submission_value(recent, "primaryDocument", index).strip()
    if not accession_number or not form or not filing_date:
        return None
    return {
        "symbol": symbol[:24],
        "cik": cik,
        "entity_name": entity_name[:160],
        "accession_number": accession_number[:48],
        "filing_date": filing_date[:24],
        "report_date": _submission_value(recent, "reportDate", index)[:24],
        "acceptance_datetime": _submission_value(recent, "acceptanceDateTime", index)[:40],
        "form": form[:32],
        "primary_document": primary_document[:160],
        "description": _submission_value(recent, "primaryDocDescription", index)[:180],
        "items": _submission_value(recent, "items", index)[:120],
        "source": "sec_company_submissions",
        "provider_id": SEC_COMPANY_SUBMISSIONS_PROVIDER_ID,
        "retrieved_at": retrieved_at,
        "cache_path": cache_path,
        "docs_url": SEC_DOCS_URL,
        "filing_url": _sec_filing_url(cik, accession_number, primary_document),
        "reference_only": True,
    }


def _ordered_submission_payloads(raw_by_symbol: dict[str, Any]) -> list[tuple[str, Any]]:
    preferred = {symbol: index for index, symbol in enumerate(SEC_DEFAULT_COMPANY_SYMBOLS)}

    def sort_key(item: tuple[str, Any]) -> tuple[int, str]:
        key = str(item[0]).upper()
        payload = item[1] if isinstance(item[1], dict) else {}
        tickers = payload.get("tickers") if isinstance(payload.get("tickers"), list) else []
        symbol = str(tickers[0] if tickers else key).upper()
        return (preferred.get(symbol, len(preferred)), symbol)

    return sorted(raw_by_symbol.items(), key=sort_key)


def _latest_submission_timestamp(rows: list[dict[str, Any]]) -> str:
    for row in rows:
        value = str(row.get("retrieved_at") or "")
        if value:
            return value
    return _utc_now()


def _sec_filing_url(cik: str, accession_number: str, primary_document: str) -> str:
    safe_cik = str(int(cik)) if cik.isdigit() else ""
    accession_path = "".join(ch for ch in accession_number if ch.isalnum())
    if not safe_cik or not accession_path or not primary_document:
        return ""
    return (
        "https://www.sec.gov/Archives/edgar/data/"
        f"{safe_cik}/{accession_path}/{primary_document}"
    )


def _row_from_sec_company_ticker_record(record: dict[str, Any]) -> dict[str, str] | None:
    symbol = str(record.get("ticker") or "").strip().upper()
    entity_name = str(record.get("title") or "").strip()
    raw_cik = str(record.get("cik_str") or "").strip()
    cik = "".join(ch for ch in raw_cik if ch.isdigit()).zfill(10)[-10:]
    if not symbol or not entity_name or not cik:
        return None
    return {
        "symbol": symbol[:24],
        "cik": cik,
        "entity_name": entity_name[:160],
    }


def _equity_registry_summary_from_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "row_count": len(rows),
        "registry_total": len(rows),
        "matched_symbols": ",".join(str(row.get("symbol") or "") for row in rows),
        "quote_state": "disabled_until_optional_quote_provider",
        "quote_provider": "alphavantage_global_quote_optional_key",
        "source": "sec_company_ticker_registry",
    }


def _filings_summary_from_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    latest = rows[0] if rows else {}
    symbols = []
    for row in rows:
        symbol = str(row.get("symbol") or "").upper()
        if symbol and symbol not in symbols:
            symbols.append(symbol)
    cache_paths = []
    for row in rows:
        cache_path = str(row.get("cache_path") or "")
        if cache_path and cache_path not in cache_paths:
            cache_paths.append(cache_path)
    return {
        "row_count": len(rows),
        "latest_filing_date": str(latest.get("filing_date") or ""),
        "latest_form": str(latest.get("form") or ""),
        "symbol": str(latest.get("symbol") or SEC_DEFAULT_COMPANY["symbol"]),
        "cik": str(latest.get("cik") or SEC_DEFAULT_COMPANY["cik"]),
        "company_count": len(symbols),
        "symbol_count": len(symbols),
        "symbols": ",".join(symbols),
        "filing_symbols": ",".join(symbols),
        "latest_symbol": str(latest.get("symbol") or ""),
        "cache_paths": ",".join(cache_paths),
        "source": "sec_company_submissions",
    }


def _sec_xbrl_frames_summary_from_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    first = rows[0] if rows else {}
    return {
        "row_count": len(rows),
        "source_row_count": len(rows),
        "entity_count": len({str(row.get("cik") or "") for row in rows if row.get("cik")}),
        "taxonomy": str(first.get("taxonomy") or SEC_XBRL_FRAMES_DEFAULT["taxonomy"]),
        "tag": str(first.get("tag") or SEC_XBRL_FRAMES_DEFAULT["tag"]),
        "unit": str(first.get("unit") or SEC_XBRL_FRAMES_DEFAULT["unit"]),
        "period": str(first.get("period") or SEC_XBRL_FRAMES_DEFAULT["period"]),
        "label": str(first.get("label") or SEC_XBRL_FRAMES_DEFAULT["tag"]),
        "description": "",
        "source": "sec_xbrl_frames",
        "quote_semantics": "not_quote",
    }


def _optional_key_sources(
    fred_payload: dict[str, Any],
    bea_payload: dict[str, Any],
    census_payload: dict[str, Any],
) -> list[dict[str, str]]:
    sources = [dict(source) for source in OPTIONAL_KEY_SOURCES]
    fred_status = fred_payload.get("status") if isinstance(fred_payload.get("status"), dict) else {}
    bea_status = bea_payload.get("status") if isinstance(bea_payload.get("status"), dict) else {}
    census_status = (
        census_payload.get("status") if isinstance(census_payload.get("status"), dict) else {}
    )
    for source in sources:
        if source["provider_id"] == FRED_PROVIDER_ID:
            source["state"] = str(fred_status.get("state") or source["state"])
            source["message"] = str(fred_status.get("message") or source["message"])
            source["cache_path"] = str(fred_status.get("cache_path") or "")
        if source["provider_id"] == BEA_PROVIDER_ID:
            source["state"] = str(bea_status.get("state") or source["state"])
            source["message"] = str(bea_status.get("message") or source["message"])
            source["cache_path"] = str(bea_status.get("cache_path") or "")
        if source["provider_id"] == CENSUS_PROVIDER_ID:
            source["state"] = str(census_status.get("state") or source["state"])
            source["message"] = str(census_status.get("message") or source["message"])
            source["cache_path"] = str(census_status.get("cache_path") or "")
    return sources


def _combined_status(
    fundamentals: dict[str, Any],
    equity_registry: dict[str, Any],
    filings: dict[str, Any],
    sec_frames: dict[str, Any],
    macro: dict[str, Any],
    source_errors: list[str],
) -> dict[str, Any]:
    states = {
        str(fundamentals.get("status", {}).get("state") or "unavailable"),
        str(equity_registry.get("status", {}).get("state") or "unavailable"),
        str(filings.get("status", {}).get("state") or "unavailable"),
        str(sec_frames.get("status", {}).get("state") or "unavailable"),
        str(macro.get("status", {}).get("state") or "unavailable"),
    }
    if "live" in states and len(states - {"live"}) == 0:
        state = "live"
    elif "live" in states:
        state = "partial"
    elif states & {"stale", "stale_cache"}:
        state = "stale"
    else:
        state = "unavailable"
    latest = _latest_timestamp(
        str(fundamentals.get("status", {}).get("last_update") or ""),
        str(equity_registry.get("status", {}).get("last_update") or ""),
        str(filings.get("status", {}).get("last_update") or ""),
        str(sec_frames.get("status", {}).get("last_update") or ""),
        str(macro.get("status", {}).get("last_update") or ""),
    )
    return {
        "source": "public_research_providers",
        "state": state,
        "last_update": latest or "not refreshed",
        "message": (
            "SEC fundamentals, SEC frames, SEC company registry, SEC filings, "
            "and macro summaries are available."
        )
        if state in {"live", "partial", "stale"}
        else "Refresh News to populate public no-key research providers.",
        "source_errors": source_errors,
        "source_count": 8,
        "failed_source_count": len(source_errors),
    }


def _best_state(*states: str) -> str:
    if all(state == "live" for state in states):
        return "live"
    if any(state == "live" for state in states):
        return "partial"
    if any(state in {"stale", "stale_cache"} for state in states):
        return "stale"
    if any(state == "rate_limited" for state in states):
        return "rate_limited"
    if any(state == "key_required" for state in states):
        return "key_required"
    return "unavailable"


def _extract_sec_facts(raw: dict[str, Any]) -> list[dict[str, str]]:
    facts = raw.get("facts")
    us_gaap = facts.get("us-gaap") if isinstance(facts, dict) else {}
    us_gaap = us_gaap if isinstance(us_gaap, dict) else {}
    rows: list[dict[str, str]] = []
    labels_seen: set[str] = set()
    for concept, label in SEC_FACT_CONCEPTS:
        if label in labels_seen:
            continue
        concept_payload = us_gaap.get(concept)
        if not isinstance(concept_payload, dict):
            continue
        latest = _latest_sec_unit_fact(concept_payload.get("units"))
        if latest is None:
            continue
        labels_seen.add(label)
        rows.append(
            {
                "concept": concept,
                "label": label,
                "unit": latest["unit"],
                "value": str(latest["value"]),
                "end": str(latest.get("end") or ""),
                "fy": str(latest.get("fy") or ""),
                "fp": str(latest.get("fp") or ""),
                "form": str(latest.get("form") or ""),
                "filed": str(latest.get("filed") or ""),
            }
        )
    return rows


def _latest_sec_unit_fact(units: Any) -> dict[str, Any] | None:
    if not isinstance(units, dict):
        return None
    candidates: list[dict[str, Any]] = []
    for unit, rows in units.items():
        if unit != "USD" or not isinstance(rows, list):
            continue
        for row in rows:
            if isinstance(row, dict) and row.get("val") is not None:
                candidates.append({**row, "unit": str(unit), "value": row.get("val")})
    if not candidates:
        return None
    return sorted(
        candidates,
        key=lambda row: (str(row.get("filed") or ""), str(row.get("end") or "")),
    )[-1]


def _sec_xbrl_frame_row(
    raw: dict[str, Any],
    *,
    taxonomy: str,
    tag: str,
    unit: str,
    period: str,
    retrieved_at: str,
    cache_path: str,
) -> dict[str, Any] | None:
    if raw.get("val") is None:
        return None
    cik = safe_sec_cik(raw.get("cik"))
    if cik == "0000000000":
        return None
    return {
        "symbol": _sec_symbol_for_cik(cik),
        "cik": cik,
        "entity_name": str(raw.get("entityName") or raw.get("entity_name") or ""),
        "taxonomy": taxonomy,
        "tag": tag,
        "label": tag,
        "unit": unit,
        "period": period,
        "value": str(raw.get("val")),
        "end": str(raw.get("end") or ""),
        "fy": str(raw.get("fy") or ""),
        "fp": str(raw.get("fp") or ""),
        "form": str(raw.get("form") or ""),
        "filed": str(raw.get("filed") or ""),
        "frame": str(raw.get("frame") or period),
        "accession_number": str(raw.get("accn") or ""),
        "location": str(raw.get("loc") or ""),
        "source": "sec_xbrl_frames",
        "provider_id": SEC_XBRL_FRAMES_PROVIDER_ID,
        "retrieved_at": retrieved_at,
        "cache_path": cache_path,
        "docs_url": SEC_DOCS_URL,
        "reference_only": True,
    }


def _bounded_sec_xbrl_frame_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    preferred_ciks = {safe_sec_cik(cik) for cik in SEC_DEFAULT_COMPANY_CIKS.values()}
    preferred = [row for row in rows if safe_sec_cik(row.get("cik")) in preferred_ciks]
    remainder = [row for row in rows if safe_sec_cik(row.get("cik")) not in preferred_ciks]
    return [*preferred, *remainder][:MAX_SEC_XBRL_FRAME_ROWS]


def _safe_sec_frame_part(value: Any, fallback: str) -> str:
    text = "".join(
        ch for ch in str(value or "").strip() if ch.isalnum() or ch in {"-", "_"}
    )
    return text[:80] or fallback


def _sec_symbol_for_cik(cik: Any) -> str:
    safe_cik = safe_sec_cik(cik)
    for symbol, known_cik in SEC_DEFAULT_COMPANY_CIKS.items():
        if safe_sec_cik(known_cik) == safe_cik:
            return symbol
    return ""


def _status(
    *,
    source: str,
    state: str,
    last_update: str,
    message: str,
    provider_id: str,
    cache_path: str,
    docs_url: str,
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


def _read_json_response(response: Any) -> Any:
    body = response.read()
    encoding = str(response.headers.get("Content-Encoding") or "").lower()
    if "gzip" in encoding or body.startswith(b"\x1f\x8b"):
        body = gzip.decompress(body)
    return json.loads(body.decode("utf-8"))


def _cache_state(current: Any, requested: str) -> str:
    if requested == "stale" and str(current or "") in {"live", "partial"}:
        return "stale"
    return str(current or requested)


def _latest_timestamp(*values: str) -> str:
    parsed: list[datetime] = []
    for value in values:
        if not value or value in {"not refreshed", "unknown"}:
            continue
        try:
            timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            continue
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=UTC)
        parsed.append(timestamp.astimezone(UTC))
    if not parsed:
        return ""
    return max(parsed).isoformat(timespec="seconds").replace("+00:00", "Z")


def _utc_now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
