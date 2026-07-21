from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path
import time
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi.testclient import TestClient

from otto.local_terminal import server
from otto.local_terminal import provider_refresh as provider_refresh_service
from otto.local_terminal.provider_refresh import (
    PublicProviderRefreshCallbacks,
    complete_public_provider_refresh_job,
    create_public_provider_refresh_job,
    provider_refresh_result,
    provider_refresh_summary,
)
from otto.local_terminal.providers import ENTRY_REQUIRED_FIELDS, ERROR_STATES, providers_payload
from otto.local_terminal.storage import LocalStateStore
from market_fixtures import fake_binance_tickers as _fake_tickers


def _live_market_cache() -> dict[str, object]:
    now = datetime.now(tz=UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
    return {
        "status": {
            "source": "binance_public",
            "state": "live",
            "last_update": now,
            "message": "Public read-only Binance data refreshed.",
        },
        "rows": [
            {
                "symbol": "BTCUSDT",
                "price": "100.00",
                "chg": "1.00",
                "chg_pct": "1.00",
                "high": "110.00",
                "low": "90.00",
                "vol": "12345",
                "bid": "99.50",
                "ask": "100.50",
                "open": "99.00",
                "name": "Bitcoin / Tether",
            }
        ],
    }


def _fake_stooq_quote(*, symbol: str = "AAPL.US") -> dict[str, str]:
    return {
        "Symbol": symbol,
        "Date": "2026-05-22",
        "Time": "22:00:19",
        "Open": "306.12",
        "High": "311.40",
        "Low": "305.84",
        "Close": "308.82",
        "Volume": "43670223",
    }


def _fake_moex_quote(*, symbol: str = "SBER") -> dict[str, object]:
    return {
        "securities": {
            "columns": ["SECID", "SHORTNAME", "BOARDID"],
            "data": [[symbol, f"{symbol} issuer", "TQBR"]],
        },
        "marketdata": {
            "columns": [
                "SECID",
                "LAST",
                "OPEN",
                "HIGH",
                "LOW",
                "VOLTODAY",
                "VALTODAY",
                "UPDATETIME",
                "BID",
                "OFFER",
                "BOARDID",
            ],
            "data": [
                [symbol, 319.75, 322.5, 324.75, 317.67, 37169464, 11933949644, "22:30:03", 319.75, 319.76, "TQBR"],
            ],
        },
    }


def _fake_twse_quote() -> list[dict[str, str]]:
    return [
        {
            "Date": "20260526",
            "Code": "2330",
            "Name": "TSMC",
            "TradeVolume": "25713389",
            "TradeValue": "22181949200",
            "OpeningPrice": "860.00",
            "HighestPrice": "870.00",
            "LowestPrice": "855.00",
            "ClosingPrice": "865.00",
            "Change": "+5.00",
            "Transaction": "33112",
        },
        {
            "Date": "20260526",
            "Code": "2317",
            "Name": "Hon Hai",
            "TradeVolume": "51230000",
            "TradeValue": "8742000000",
            "OpeningPrice": "169.50",
            "HighestPrice": "172.00",
            "LowestPrice": "168.00",
            "ClosingPrice": "171.00",
            "Change": "+1.50",
            "Transaction": "22100",
        },
        {
            "Date": "20260526",
            "Code": "0050",
            "Name": "Yuanta Taiwan 50",
            "TradeVolume": "9820000",
            "TradeValue": "1852300000",
            "OpeningPrice": "188.20",
            "HighestPrice": "189.10",
            "LowestPrice": "187.80",
            "ClosingPrice": "188.90",
            "Change": "+0.70",
            "Transaction": "8700",
        },
    ]


def _fake_nasdaq_trader_directory() -> dict[str, str]:
    return {
        "nasdaqlisted.txt": "\n".join(
            [
                "Symbol|Security Name|Market Category|Test Issue|Financial Status|Round Lot Size|ETF|NextShares",
                "AAPL|Apple Inc. - Common Stock|Q|N|N|100|N|N",
                "QQQ|Invesco QQQ Trust|G|N|N|100|Y|N",
                "File Creation Time: 0526202617:03|||||||",
            ]
        ),
        "otherlisted.txt": "\n".join(
            [
                "ACT Symbol|Security Name|Exchange|CQS Symbol|ETF|Round Lot Size|Test Issue|NASDAQ Symbol",
                "IBM|International Business Machines Corporation|N|IBM|N|100|N|IBM",
                "SPY|SPDR S&P 500 ETF Trust|P|SPY|Y|100|N|SPY",
                "File Creation Time: 0526202617:04|||||||",
            ]
        ),
    }


def _fake_openfigi_mapping(jobs: list[dict[str, object]]) -> list[dict[str, object]]:
    assert jobs
    return [
        {
            "data": [
                {
                    "figi": "BBG000B9XRY4",
                    "name": "APPLE INC",
                    "ticker": "AAPL",
                    "exchCode": "US",
                    "compositeFIGI": "BBG000B9XRY4",
                    "shareClassFIGI": "BBG001S5N8V8",
                    "securityType": "Common Stock",
                    "marketSector": "Equity",
                    "securityType2": "Common Stock",
                    "securityDescription": "AAPL",
                }
            ]
        }
        for _ in jobs
    ]


def _fake_crypto_detail(*, symbol: str = "BTCUSDT", interval: str = "15m") -> dict[str, object]:
    now = datetime.now(tz=UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
    return {
        "status": {
            "source": "binance_public",
            "state": "live",
            "last_update": now,
            "message": "Public read-only Binance depth, trades, and closed candles refreshed.",
            "symbol": symbol,
            "timeframe": interval,
            "provider_id": "binance_spot_public",
        },
        "provider": {
            "provider_id": "binance_spot_public",
            "label": "Binance Spot public market data",
            "source": "binance_public",
            "state": "live",
            "auth_mode": "no-key",
            "cache_path": f"market_data/crypto/{symbol}/{interval}.json",
        },
        "depth": {
            "bids": [{"price": "99.50", "quantity": "1.5"}],
            "asks": [{"price": "100.50", "quantity": "1.2"}],
        },
        "trades": [{"price": "100.00", "quantity": "0.1", "side": "BUY", "traded_at": now}],
        "candles": [
            {
                "opened_at": "2026-05-23T00:00:00+00:00",
                "closed_at": "2026-05-23T00:15:00+00:00",
                "open": "100.00",
                "high": "101.00",
                "low": "99.00",
                "close": "100.50",
                "volume": "10.0",
                "interval": interval,
                "closed": True,
            }
        ],
    }


def _fake_kraken_detail(*, symbol: str = "BTCUSDT", interval: str = "15m") -> dict[str, object]:
    payload = _fake_crypto_detail(symbol=symbol, interval=interval)
    payload["status"] = {
        **payload["status"],
        "source": "kraken_public",
        "provider_id": "kraken_public_market_data",
    }
    payload["provider"] = {
        **payload["provider"],
        "provider_id": "kraken_public_market_data",
        "label": "Kraken public market data",
        "source": "kraken_public",
    }
    return payload


def _failing_provider(*args: object, **kwargs: object) -> object:
    raise OSError("provider unavailable in test")


def _sec_raw() -> dict[str, object]:
    return {
        "cik": 320193,
        "entityName": "Apple Inc.",
        "facts": {
            "us-gaap": {
                "Assets": {
                    "units": {
                        "USD": [
                            {
                                "val": 350000000000,
                                "end": "2025-09-27",
                                "fy": 2025,
                                "fp": "FY",
                                "form": "10-K",
                                "filed": "2025-10-31",
                            }
                        ]
                    }
                }
            }
        },
    }


def _sec_tickers_raw() -> dict[str, object]:
    return {
        "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
        "1": {"cik_str": 789019, "ticker": "MSFT", "title": "MICROSOFT CORP"},
        "2": {"cik_str": 1045810, "ticker": "NVDA", "title": "NVIDIA CORP"},
    }


def _sec_submissions_raw() -> dict[str, object]:
    return {
        "cik": "320193",
        "name": "Apple Inc.",
        "tickers": ["AAPL"],
        "filings": {
            "recent": {
                "accessionNumber": ["0000320193-25-000079"],
                "filingDate": ["2025-10-31"],
                "reportDate": ["2025-09-27"],
                "acceptanceDateTime": ["20251031183000"],
                "form": ["10-K"],
                "primaryDocument": ["aapl-20250927.htm"],
                "primaryDocDescription": ["10-K"],
                "items": [""],
            }
        },
    }


def _sec_frame_raw() -> dict[str, object]:
    return {
        "taxonomy": "us-gaap",
        "tag": "Assets",
        "ccp": "CY2023Q4I",
        "uom": "USD",
        "label": "Assets",
        "data": [
            {
                "cik": 320193,
                "entityName": "Apple Inc.",
                "loc": "US-CA",
                "end": "2023-09-30",
                "val": 352583000000,
                "accn": "0000320193-23-000106",
                "fy": 2023,
                "fp": "FY",
                "form": "10-K",
                "filed": "2023-11-03",
                "frame": "CY2023Q4I",
            }
        ],
    }


def _dbnomics_raw() -> dict[str, object]:
    return {
        "series": {
            "docs": [
                {
                    "provider_code": "INSEE",
                    "dataset_code": "IPC-2015",
                    "series_code": "A.IPC.SO.00.00.INDICE.ENSEMBLE.FE.SO.BRUT.2015.FALSE",
                    "series_name": "Annual CPI all items",
                    "dataset_name": "Consumer price index",
                    "period": ["2024", "2025"],
                    "value": [117.2, 119.34],
                    "@frequency": "annual",
                    "indexed_at": "2026-01-15T00:00:00Z",
                }
            ]
        }
    }


def _bls_raw() -> dict[str, object]:
    return {
        "series": [
            {
                "series_id": "LNS14000000",
                "data": [
                    {
                        "year": "2026",
                        "period": "M04",
                        "periodName": "April",
                        "latest": "true",
                        "value": "4.2",
                    }
                ],
            }
        ]
    }


def _eurostat_raw() -> dict[str, object]:
    return {
        "version": "2.0",
        "label": "HICP - monthly data (index) (1996-2025)",
        "source": "ESTAT",
        "updated": "2026-02-06T23:00:00+0100",
        "value": {"0": 129.72, "1": 129.34, "2": 129.57},
        "dimension": {
            "time": {
                "category": {
                    "index": {
                        "2025-10": 0,
                        "2025-11": 1,
                        "2025-12": 2,
                    }
                }
            }
        },
    }


def _fake_research() -> dict[str, object]:
    return {
        "sec": _sec_raw(),
        "sec_tickers": _sec_tickers_raw(),
        "sec_submissions": _sec_submissions_raw(),
        "sec_frames": _sec_frame_raw(),
        "dbnomics": _dbnomics_raw(),
        "bls": _bls_raw(),
        "eurostat": _eurostat_raw(),
        "errors": [],
    }


def _fake_research_bls_only() -> dict[str, object]:
    return {
        "sec": _sec_raw(),
        "sec_tickers": _sec_tickers_raw(),
        "sec_submissions": _sec_submissions_raw(),
        "sec_frames": _sec_frame_raw(),
        "dbnomics": {},
        "bls": _bls_raw(),
        "errors": ["DBnomics: unavailable"],
    }


def _fake_news() -> dict[str, object]:
    now = datetime.now(tz=UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
    return {
        "items": [
            {
                "item_id": "provider-refresh-news",
                "title": "Market desk tracks CPI and company filings",
                "source": "Public Wire",
                "category": "ECO",
                "published_at": now,
                "url": "https://example.test/provider-refresh",
                "summary": "Source-attributed headline metadata only.",
                "tags": ["CPI", "SEC"],
            }
        ],
        "errors": [],
        "source_count": 2,
        "failed_source_count": 0,
        "providers": [
            {
                "provider_id": "public_rss_news",
                "label": "Public RSS",
                "state": "live",
                "source_count": 1,
                "item_count": 1,
                "failed": False,
                "docs_url": "https://example.test/rss",
                "message": "Public RSS refreshed.",
            },
            {
                "provider_id": "gdelt_doc_public",
                "label": "GDELT DOC 2.0",
                "state": "live",
                "source_count": 1,
                "item_count": 1,
                "failed": False,
                "docs_url": "https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/",
                "message": "GDELT DOC metadata refreshed.",
            },
        ],
    }


def _treasury_xml() -> str:
    return """<?xml version="1.0" encoding="utf-8" standalone="yes" ?>
<feed xmlns:d="http://schemas.microsoft.com/ado/2007/08/dataservices"
  xmlns:m="http://schemas.microsoft.com/ado/2007/08/dataservices/metadata"
  xmlns="http://www.w3.org/2005/Atom">
<entry><content type="application/xml"><m:properties>
<d:NEW_DATE m:type="Edm.DateTime">2026-05-22T00:00:00</d:NEW_DATE>
<d:BC_1MONTH m:type="Edm.Double">3.92</d:BC_1MONTH>
<d:BC_2YEAR m:type="Edm.Double">4.02</d:BC_2YEAR>
<d:BC_10YEAR m:type="Edm.Double">4.57</d:BC_10YEAR>
<d:BC_30YEAR m:type="Edm.Double">5.08</d:BC_30YEAR>
</m:properties></content></entry>
</feed>
"""


def _sofr_json() -> dict[str, object]:
    return {
        "refRates": [
            {
                "effectiveDate": "2026-05-22",
                "type": "SOFR",
                "percentRate": 3.52,
                "percentPercentile25": 3.51,
                "percentPercentile75": 3.56,
                "volumeInBillions": 3081,
                "revisionIndicator": "",
            }
        ]
    }


def _ecb_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8"?>
<gesmes:Envelope
  xmlns:gesmes="http://www.gesmes.org/xml/2002-08-01"
  xmlns="http://www.ecb.int/vocabulary/2002-08-01/eurofxref">
  <Cube><Cube time="2026-05-22">
    <Cube currency="USD" rate="1.1595"/>
    <Cube currency="JPY" rate="184.53"/>
    <Cube currency="GBP" rate="0.86418"/>
  </Cube></Cube>
</gesmes:Envelope>
"""


def _h10_csv() -> str:
    return "\n".join(
        [
            (
                '"Series Description","Euro-Area Euro","United Kingdom Pound",'
                '"Canadian Dollar","Chinese Yuan","Japanese Yen"'
            ),
            '"Unit:","Currency","Currency","Currency","Currency","Currency"',
            '"Multiplier:","1","1","1","1","1"',
            '"Currency:","EUR","GBP","CAD","CNY","JPY"',
            (
                '"Unique Identifier:","H10/H10/RXI$US_N.B.EU",'
                '"H10/H10/RXI$US_N.B.UK","H10/H10/RXI_N.B.CA",'
                '"H10/H10/RXI_N.B.CH","H10/H10/RXI_N.B.JA"'
            ),
            (
                '"Time Period","RXI$US_N.B.EU","RXI$US_N.B.UK","RXI_N.B.CA",'
                '"RXI_N.B.CH","RXI_N.B.JA"'
            ),
            "2026-05-15,1.1627,1.3332,1.3750,6.8092,158.6900",
        ]
    )


def _boc_json() -> dict[str, object]:
    return {
        "observations": [
            {
                "d": "2026-05-25",
                "FXUSDCAD": {"v": "1.3804"},
                "FXEURCAD": {"v": "1.6072"},
                "FXGBPCAD": {"v": "1.8639"},
                "FXJPYCAD": {"v": "0.008690"},
                "FXCHFCAD": {"v": "1.7246"},
            }
        ]
    }


def _world_bank_xlsx() -> bytes:
    def cell(ref: str, value: str) -> str:
        return f'<c r="{ref}" t="inlineStr"><is><t>{value}</t></is></c>'

    def row(number: int, values: dict[str, str]) -> str:
        return f'<row r="{number}">{"".join(cell(ref, value) for ref, value in values.items())}</row>'

    sheet = f"""<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData>
    {row(1, {"A1": "World Bank Commodity Price Data (The Pink Sheet)"})}
    {row(4, {"A4": "Updated on May 04, 2026"})}
    {row(5, {"B5": "Crude oil, WTI", "C5": "Gold"})}
    {row(6, {"B6": "($/bbl)", "C6": "($/troy oz)"})}
    {row(7, {"B7": "CRUDE_WTI", "C7": "GOLD"})}
    {row(8, {"A8": "2026M04", "B8": "98.63", "C8": "4721.42"})}
  </sheetData>
</worksheet>
"""
    workbook = """<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
  xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets><sheet name="Monthly Prices" sheetId="1" r:id="rId1"/></sheets>
</workbook>
"""
    rels = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1"
    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"
    Target="worksheets/sheet1.xml"/>
</Relationships>
"""
    payload = BytesIO()
    with ZipFile(payload, "w", ZIP_DEFLATED) as workbook_zip:
        workbook_zip.writestr("xl/workbook.xml", workbook)
        workbook_zip.writestr("xl/_rels/workbook.xml.rels", rels)
        workbook_zip.writestr("xl/worksheets/sheet1.xml", sheet)
    return payload.getvalue()


def _cftc_cot_raw() -> bytes:
    return b"""[
      {
        "market_and_exchange_names": "GOLD - COMMODITY EXCHANGE INC.",
        "report_date_as_yyyy_mm_dd": "2026-05-19T00:00:00.000",
        "open_interest_all": "379325",
        "noncomm_positions_long_all": "211018",
        "noncomm_positions_short_all": "51185",
        "comm_positions_long_all": "69520",
        "comm_positions_short_all": "261149"
      }
    ]"""


def _sec_funds_raw() -> dict[str, object]:
    return {
        "fields": ["cik", "seriesId", "classId", "symbol"],
        "data": [
            [36405, "S000002848", "C000007808", "VTI"],
            [794105, "S000002564", "C000046844", "BND"],
            [1067839, "S000101292", "C000271435", "QQQ"],
        ],
    }


def test_provider_registry_exposes_entry_gate_and_error_states(tmp_path: Path) -> None:
    payload = providers_payload(LocalStateStore(root=tmp_path))

    assert set(payload["entry_template"]["required_fields"]) == set(ENTRY_REQUIRED_FIELDS)
    assert set(payload["entry_template"]["required_error_states"]) == set(ERROR_STATES)
    assert set(payload["error_state_catalog"]) == set(ERROR_STATES)
    assert payload["safety"] == {
        "private_api_keys_persisted": False,
        "live_execution_reachable": False,
        "paid_provider_enabled": False,
        "installed_source_used": False,
    }
    for provider in payload["providers"]:
        for field in ENTRY_REQUIRED_FIELDS:
            assert field in provider
        assert provider["health"]["state"] in {*ERROR_STATES, "active"}
        assert "secret" not in str(provider["health"]).lower()


def test_provider_cache_marks_binance_cache_as_primary_runtime(tmp_path: Path) -> None:
    store = LocalStateStore(root=tmp_path)
    store.write_market_cache(_live_market_cache())

    payload = providers_payload(store)
    binance = next(
        provider for provider in payload["providers"] if provider["provider_id"] == "binance_spot_public"
    )
    cache = next(cache for cache in payload["caches"] if cache["cache_id"] == "market_crypto_latest")

    assert binance["health"]["state"] == "active"
    assert binance["health"]["runtime_source"] == "binance_public"
    assert binance["health"]["runtime_source"] != "offline_fixture"
    assert cache["state"] == "active"
    assert cache["path"] == "market_data/crypto_latest.json"
    assert payload["summary"]["active"] >= 1


def test_provider_cache_reports_stale_cache_with_source(tmp_path: Path) -> None:
    store = LocalStateStore(root=tmp_path)
    stale = _live_market_cache()
    stale["status"]["last_update"] = (
        datetime.now(tz=UTC) - timedelta(hours=2)
    ).isoformat(timespec="seconds").replace("+00:00", "Z")
    store.write_market_cache(stale)

    payload = providers_payload(store)
    binance = next(
        provider for provider in payload["providers"] if provider["provider_id"] == "binance_spot_public"
    )

    assert binance["health"]["state"] == "stale_cache"
    assert binance["health"]["runtime_source"] == "binance_public"
    assert binance["health"]["age_seconds"] >= 3600
    assert payload["summary"]["stale_cache"] == 1


def test_provider_registry_assigns_crypto_detail_cache_to_fallback_provider(
    tmp_path: Path,
) -> None:
    store = LocalStateStore(root=tmp_path)
    now = datetime.now(tz=UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
    store.write_crypto_detail_cache(
        {
            "status": {
                "source": "kraken_public",
                "state": "live",
                "last_update": now,
                "message": "Public Kraken detail refreshed.",
                "symbol": "BTCUSDT",
                "timeframe": "15m",
                "provider_id": "kraken_public_market_data",
            },
            "provider": {
                "provider_id": "kraken_public_market_data",
                "label": "Kraken public market data",
                "source": "kraken_public",
                "state": "live",
            },
            "depth": {"bids": [], "asks": []},
            "trades": [],
            "candles": [{"open": "100", "high": "101", "low": "99", "close": "100"}],
        }
    )

    payload = providers_payload(store)
    kraken = next(
        provider
        for provider in payload["providers"]
        if provider["provider_id"] == "kraken_public_market_data"
    )
    detail_cache = next(cache for cache in payload["caches"] if cache["cache_id"] == "crypto_public_detail")

    assert detail_cache["provider_id"] == "kraken_public_market_data"
    assert kraken["health"]["state"] == "active"
    assert kraken["health"]["runtime_source"] == "kraken_public"


def test_provider_api_endpoints_return_registry_and_cache(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())

    registry = client.get("/api/providers")
    cache = client.get("/api/providers/cache")

    assert registry.status_code == 200
    assert cache.status_code == 200
    assert registry.json()["summary"]["provider_count"] >= 6
    assert {item["state"] for item in registry.json()["freshness_strip"]} >= {
        "unavailable",
        "key_required",
        "plan_required",
        "disabled_by_safety",
    }
    assert cache.json()["caches"][0]["cache_id"] == "market_crypto_latest"
    assert any(item["cache_id"] == "crypto_public_detail" for item in cache.json()["caches"])
    assert "kraken_public_market_data" in registry.text
    assert "coinbase_public_market_data" in registry.text
    assert "eia_open_data_optional_key" in registry.text
    assert "fx_quote_alphavantage_EURUSD" in registry.text
    assert "market_data/fx/alphavantage/currency_exchange/EURUSD.json" in registry.text
    assert "twelve_data_quote_optional_key" in registry.text
    assert "twelve_data_quote_AAPL" in registry.text
    assert "market_data/quotes/twelve_data/AAPL.json" in registry.text
    assert "finnhub_equity_quote_optional_key" in registry.text
    assert "finnhub_quote_AAPL" in registry.text
    assert "market_data/quotes/finnhub/AAPL.json" in registry.text
    assert "fmp_stock_quote_optional_key" in registry.text
    assert "fmp_quote_AAPL" in registry.text
    assert "market_data/quotes/fmp/AAPL.json" in registry.text
    assert "stooq_public_quote_snapshot" in registry.text
    assert "stooq_quote_AAPLUS" in registry.text
    assert "market_data/quotes/stooq/AAPLUS.json" in registry.text
    assert "moex_iss_delayed_quote_snapshot" in registry.text
    assert "moex_quote_SBER" in registry.text
    assert "market_data/quotes/moex/SBER.json" in registry.text
    assert "twse_openapi_daily_quote_snapshot" in registry.text
    assert "twse_quote_2330" in registry.text
    assert "market_data/quotes/twse/2330.json" in registry.text
    assert "eurostat_hicp_public" in registry.text
    assert "macro_eurostat_hicp" in registry.text
    assert "market_data/macro/eurostat/hicp_ea20_cp00_i15.json" in registry.text
    assert "nasdaq_trader_symbol_directory_public" in registry.text
    assert "nasdaq_trader_symbol_directory" in registry.text
    assert "market_data/reference/nasdaq_trader/symbol_directory.json" in registry.text
    assert "openfigi_identifier_mapping_public" in registry.text
    assert "openfigi_identifier_mapping" in registry.text
    assert "market_data/reference/openfigi/mapping.json" in registry.text
    assert "bea_regional_optional_key" in registry.text
    assert "regional_bea_SAGDP9N_LINE1_STATE" in registry.text
    assert "market_data/regional/bea/SAGDP9N_LINE1_STATE.json" in registry.text
    assert "census_api_optional_key" in registry.text
    assert "regional_census_ACS5_PROFILE_STATE_2023" in registry.text
    assert "market_data/regional/census/acs5_profile_state_2023.json" in registry.text
    assert "api_key=" not in registry.text.lower()
    assert "private_broker_live_execution" in registry.text


def test_provider_refresh_result_separates_written_cache_from_available_cache() -> None:
    live = provider_refresh_result(
        "provider_live",
        "Live provider",
        {
            "source": "provider_live",
            "state": "live",
            "last_update": "2026-05-25T00:00:00Z",
            "message": "Fresh provider payload returned.",
        },
        cache_written=True,
        cache_path="market_data/provider_live.json",
    )
    stale = provider_refresh_result(
        "provider_stale",
        "Stale provider",
        {
            "source": "provider_stale",
            "state": "stale_cache",
            "last_update": "2026-05-24T00:00:00Z",
            "message": "Provider unavailable; stale cache is still usable.",
        },
        cache_written=True,
        cache_path="market_data/provider_stale.json",
    )
    unavailable = provider_refresh_result(
        "provider_unavailable",
        "Unavailable provider",
        {
            "source": "provider_unavailable",
            "state": "unavailable",
            "message": "Provider returned no runtime cache.",
        },
        cache_written=False,
        cache_path="market_data/provider_unavailable.json",
    )

    assert live["cache_written"] is True
    assert live["cache_written_this_run"] is True
    assert live["cache_available"] is True
    assert live["cache_reused"] is False
    assert live["cache_write_status"] == "written_this_run"
    assert stale["cache_written"] is False
    assert stale["cache_written_this_run"] is False
    assert stale["cache_available"] is True
    assert stale["cache_reused"] is True
    assert stale["cache_write_status"] == "available_from_cache"
    assert unavailable["cache_available"] is False
    assert unavailable["cache_write_status"] == "not_available"

    summary = provider_refresh_summary([live, stale, unavailable])
    assert summary["cache_written"] == 1
    assert summary["cache_written_this_run"] == 1
    assert summary["cache_available"] == 2
    assert summary["cache_reused"] == 1
    assert summary["stale_or_cached"] == 1
    assert summary["unavailable"] == 1


def test_public_provider_refresh_endpoint_populates_no_key_caches_and_artifacts(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = LocalStateStore(root=tmp_path)
    monkeypatch.setattr(server, "STORE", store)
    monkeypatch.setattr(server, "MARKET_FETCHER", _fake_tickers)
    monkeypatch.setattr(server, "CRYPTO_DETAIL_FETCHER", _fake_crypto_detail)
    monkeypatch.setattr(server, "NEWS_FETCHER", _fake_news)
    monkeypatch.setattr(server, "RESEARCH_FETCHER", _fake_research)
    monkeypatch.setattr(server, "RATES_FETCHER", _treasury_xml)
    monkeypatch.setattr(server, "SOFR_FETCHER", _sofr_json)
    monkeypatch.setattr(server, "FX_FETCHER", _ecb_xml)
    monkeypatch.setattr(server, "FED_H10_FETCHER", _h10_csv)
    monkeypatch.setattr(server, "BOC_FX_FETCHER", _boc_json)
    monkeypatch.setattr(server, "COMMODITY_FETCHER", _world_bank_xlsx)
    monkeypatch.setattr(server, "CFTC_COT_FETCHER", _cftc_cot_raw)
    monkeypatch.setattr(server, "FUND_FETCHER", _sec_funds_raw)
    monkeypatch.setattr(server, "STOOQ_FETCHER", _fake_stooq_quote)
    monkeypatch.setattr(server, "MOEX_FETCHER", _fake_moex_quote)
    monkeypatch.setattr(server, "TWSE_FETCHER", _fake_twse_quote)
    monkeypatch.setattr(server, "NASDAQ_TRADER_FETCHER", _fake_nasdaq_trader_directory)
    monkeypatch.setattr(server, "OPENFIGI_FETCHER", _fake_openfigi_mapping)
    client = TestClient(server.create_app())

    response = client.post("/api/providers/refresh-public")

    payload = response.json()
    result_ids = {item["provider_id"] for item in payload["last_refresh"]["results"]}
    assert response.status_code == 200
    assert payload["last_refresh"]["output_mode"] == "public_no_key_provider_refresh"
    assert payload["last_refresh"]["summary"]["result_count"] == 24
    assert payload["last_refresh"]["summary"]["provider_count"] == 23
    assert payload["last_refresh"]["summary"]["refreshed"] >= 16
    assert payload["last_refresh"]["summary"]["cache_written"] >= 16
    assert payload["last_refresh"]["summary"]["cache_written_this_run"] >= 16
    assert payload["last_refresh"]["summary"]["cache_available"] >= 16
    assert payload["last_refresh"]["summary"]["cache_reused"] == 0
    assert payload["summary"]["active"] >= 10
    assert result_ids >= {
        "binance_spot_public",
        "public_rss_news",
        "gdelt_doc_public",
        "sec_edgar_public",
        "sec_xbrl_frames_public",
        "sec_company_ticker_registry_public",
        "sec_company_submissions_public",
        "dbnomics_public",
        "bls_public_macro",
        "eurostat_hicp_public",
        "us_treasury_yield_public",
        "nyfed_sofr_public",
        "ecb_fx_reference_public",
        "federal_reserve_h10_ddp_public",
        "bank_of_canada_valet_fx_reference_public",
        "stooq_public_quote_snapshot",
        "moex_iss_delayed_quote_snapshot",
        "twse_openapi_daily_quote_snapshot",
        "nasdaq_trader_symbol_directory_public",
        "openfigi_identifier_mapping_public",
        "world_bank_commodity_monthly_public",
        "cftc_cot_legacy_public",
        "sec_fund_ticker_registry_public",
    }
    artifact_dir = tmp_path / payload["last_refresh"]["artifact_dir"]
    assert (tmp_path / "market_data" / "crypto_latest.json").is_file()
    assert (tmp_path / "market_data" / "crypto" / "BTCUSDT" / "15m.json").is_file()
    assert (
        tmp_path
        / "market_data"
        / "reference"
        / "nasdaq_trader"
        / "symbol_directory.json"
    ).is_file()
    assert (tmp_path / "market_data" / "reference" / "openfigi" / "mapping.json").is_file()
    assert (tmp_path / "market_data" / "quotes" / "moex" / "SBER.json").is_file()
    assert (tmp_path / "market_data" / "quotes" / "twse" / "2330.json").is_file()
    assert (tmp_path / "artifacts" / "news" / "news_cache.json").is_file()
    assert (
        tmp_path
        / "market_data"
        / "fundamentals"
        / "sec"
        / "frames"
        / "us-gaap"
        / "Assets"
        / "USD"
        / "CY2023Q4I.json"
    ).is_file()
    assert (tmp_path / "market_data" / "fundamentals" / "sec" / "company_tickers.json").is_file()
    assert (tmp_path / "market_data" / "fundamentals" / "sec" / "0000320193" / "submissions.json").is_file()
    assert (
        tmp_path / "market_data" / "fx" / "federal_reserve" / "h10_reference_rates.json"
    ).is_file()
    assert (
        tmp_path / "market_data" / "fx" / "bank_of_canada" / "valet_fx_reference_rates.json"
    ).is_file()
    assert (
        tmp_path / "market_data" / "macro" / "eurostat" / "hicp_ea20_cp00_i15.json"
    ).is_file()
    assert (
        tmp_path / "market_data" / "commodities" / "cftc" / "cot_legacy_futures.json"
    ).is_file()
    assert (artifact_dir / "manifest.json").is_file()
    assert (artifact_dir / "results.json").is_file()
    assert (artifact_dir / "providers_after.json").is_file()
    assert (artifact_dir / "job_status.json").is_file()
    assert (artifact_dir / "report.md").is_file()
    results = payload["last_refresh"]["results"]
    assert all("cache_available" in item for item in results)
    assert all("cache_written_this_run" in item for item in results)
    assert all("cache_write_status" in item for item in results)
    assert {item["cache_write_status"] for item in results} <= {
        "written_this_run",
        "available_from_cache",
        "not_available",
    }
    assert payload["last_refresh"]["safety"]["public_no_key_only"] is True
    assert payload["last_refresh"]["safety"]["optional_key_providers_refreshed"] is False
    assert payload["last_refresh"]["safety"]["private_api_key_flow"] is False
    assert payload["last_refresh"]["safety"]["real_order_path"] is False
    assert payload["last_refresh"]["safety"]["installed_source_read"] is False
    assert not (tmp_path / "settings" / "local_secrets.json").exists()
    assert "api_key=" not in response.text.lower()
    assert "sk-" not in response.text.lower()
    assert "123456" not in response.text


def test_public_provider_refresh_job_tracks_status_artifacts_and_provider_payload(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = LocalStateStore(root=tmp_path)
    monkeypatch.setattr(server, "STORE", store)
    monkeypatch.setattr(server, "MARKET_FETCHER", _fake_tickers)
    monkeypatch.setattr(server, "CRYPTO_DETAIL_FETCHER", _fake_crypto_detail)
    monkeypatch.setattr(server, "NEWS_FETCHER", _fake_news)
    monkeypatch.setattr(server, "RESEARCH_FETCHER", _fake_research)
    monkeypatch.setattr(server, "RATES_FETCHER", _treasury_xml)
    monkeypatch.setattr(server, "SOFR_FETCHER", _sofr_json)
    monkeypatch.setattr(server, "FX_FETCHER", _ecb_xml)
    monkeypatch.setattr(server, "FED_H10_FETCHER", _h10_csv)
    monkeypatch.setattr(server, "BOC_FX_FETCHER", _boc_json)
    monkeypatch.setattr(server, "COMMODITY_FETCHER", _world_bank_xlsx)
    monkeypatch.setattr(server, "CFTC_COT_FETCHER", _cftc_cot_raw)
    monkeypatch.setattr(server, "FUND_FETCHER", _sec_funds_raw)
    monkeypatch.setattr(server, "STOOQ_FETCHER", _fake_stooq_quote)
    monkeypatch.setattr(server, "MOEX_FETCHER", _fake_moex_quote)
    monkeypatch.setattr(server, "TWSE_FETCHER", _fake_twse_quote)
    monkeypatch.setattr(server, "NASDAQ_TRADER_FETCHER", _fake_nasdaq_trader_directory)
    monkeypatch.setattr(server, "OPENFIGI_FETCHER", _fake_openfigi_mapping)
    client = TestClient(server.create_app())

    started = client.post("/api/providers/refresh-public/jobs")

    assert started.status_code == 200
    queued = started.json()
    assert queued["run_id"].startswith("provider-refresh-")
    assert queued["status"] in {"queued", "running", "completed"}
    assert queued["mode"] == "manual_public_no_key_provider_refresh"
    assert queued["safety"]["public_no_key_only"] is True
    assert queued["safety"]["secret_reads_enabled"] is False
    assert queued["safety"]["real_order_path"] is False

    status_payload = {}
    for _ in range(20):
        status = client.get(f"/api/providers/refresh-public/jobs/{queued['run_id']}")
        assert status.status_code == 200
        status_payload = status.json()
        if status_payload["status"] == "completed":
            break
        time.sleep(0.05)

    assert status_payload["status"] == "completed"
    assert status_payload["summary"]["result_count"] == 24
    assert status_payload["summary"]["provider_count"] == 23
    assert status_payload["summary"]["cache_written"] >= 16
    assert status_payload["summary"]["cache_written_this_run"] >= 16
    assert status_payload["summary"]["cache_available"] >= 16
    assert status_payload["summary"]["cache_reused"] == 0
    assert any(
        item["provider_id"] == "gdelt_doc_public"
        for item in status_payload["last_refresh"]["results"]
    )
    assert status_payload["last_refresh"]["run_id"] == queued["run_id"]
    assert status_payload["provider_payload"]["last_refresh"]["run_id"] == queued["run_id"]
    artifact_dir = tmp_path / status_payload["artifact_dir"]
    assert (artifact_dir / "job_status.json").is_file()
    assert (artifact_dir / "manifest.json").is_file()
    assert (artifact_dir / "providers_after.json").is_file()
    assert not (tmp_path / "settings" / "local_secrets.json").exists()
    assert "api_key=" not in status.text.lower()
    assert "sk-" not in status.text.lower()

    providers = client.get("/api/providers")
    assert providers.status_code == 200
    assert providers.json()["last_refresh"]["run_id"] == queued["run_id"]

    missing = client.get("/api/providers/refresh-public/jobs/not-a-provider-refresh-job")
    assert missing.status_code == 404


def test_public_provider_refresh_job_failure_writes_failed_status_without_secrets(
    tmp_path: Path,
) -> None:
    store = LocalStateStore(root=tmp_path)
    callbacks = PublicProviderRefreshCallbacks(
        market_payload=lambda: (_ for _ in ()).throw(RuntimeError("network token=sample")),
        crypto_detail_payload=lambda: {},
        news_payload=lambda: {},
        research_payload=lambda: {},
        rates_payload=lambda: {},
        fx_payload=lambda: {},
        commodity_payload=lambda: {},
        fund_payload=lambda: {},
        stooq_quote_payload=lambda: {},
        moex_quote_payload=lambda: {},
        twse_quote_payload=lambda: {},
        nasdaq_symbol_payload=lambda: {},
        openfigi_mapping_payload=lambda: {},
        provider_state_payload=lambda: providers_payload(store),
    )
    job = create_public_provider_refresh_job(store, run_id="provider-refresh-000000000000")

    result = complete_public_provider_refresh_job(store, callbacks, job["run_id"])

    assert result["status"] == "failed"
    assert result["summary"]["unavailable"] == 1
    assert result["safety"]["public_no_key_only"] is True
    assert result["safety"]["secret_writes_enabled"] is False
    assert "sample" not in result["error"]["message"]
    artifact_dir = tmp_path / result["artifact_dir"]
    assert (artifact_dir / "job_status.json").is_file()
    assert (artifact_dir / "error.log").is_file()
    assert not (tmp_path / "settings" / "local_secrets.json").exists()


def test_public_provider_refresh_job_rejects_overlapping_refreshes(
    tmp_path: Path,
) -> None:
    store = LocalStateStore(root=tmp_path)
    callbacks = PublicProviderRefreshCallbacks(
        market_payload=_fake_tickers,
        crypto_detail_payload=_fake_crypto_detail,
        news_payload=_fake_news,
        research_payload=_fake_research,
        rates_payload=_treasury_xml,
        fx_payload=_ecb_xml,
        commodity_payload=_world_bank_xlsx,
        fund_payload=_sec_funds_raw,
        stooq_quote_payload=lambda: {},
        moex_quote_payload=lambda: {},
        twse_quote_payload=lambda: {},
        nasdaq_symbol_payload=lambda: {},
        openfigi_mapping_payload=lambda: {},
        provider_state_payload=lambda: providers_payload(store),
    )
    job = create_public_provider_refresh_job(store, run_id="provider-refresh-111111111111")
    acquired = provider_refresh_service._REFRESH_JOB_LOCK.acquire(blocking=False)
    assert acquired is True
    try:
        result = complete_public_provider_refresh_job(store, callbacks, job["run_id"])
    finally:
        provider_refresh_service._REFRESH_JOB_LOCK.release()

    assert result["status"] == "failed"
    assert "already running" in result["message"]
    artifact_dir = tmp_path / result["artifact_dir"]
    assert (artifact_dir / "job_status.json").is_file()
    assert (artifact_dir / "error.log").is_file()
    assert not (tmp_path / "settings" / "local_secrets.json").exists()


def test_public_provider_refresh_does_not_count_detail_fallback_as_ticker_success(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = LocalStateStore(root=tmp_path)
    monkeypatch.setattr(server, "STORE", store)
    monkeypatch.setattr(server, "MARKET_FETCHER", _failing_provider)
    monkeypatch.setattr(server, "CRYPTO_DETAIL_FETCHER", _fake_kraken_detail)
    monkeypatch.setattr(server, "NEWS_FETCHER", _failing_provider)
    monkeypatch.setattr(server, "RESEARCH_FETCHER", _failing_provider)
    monkeypatch.setattr(server, "RATES_FETCHER", _failing_provider)
    monkeypatch.setattr(server, "SOFR_FETCHER", _failing_provider)
    monkeypatch.setattr(server, "FX_FETCHER", _failing_provider)
    monkeypatch.setattr(server, "FED_H10_FETCHER", _failing_provider)
    monkeypatch.setattr(server, "BOC_FX_FETCHER", _failing_provider)
    monkeypatch.setattr(server, "COMMODITY_FETCHER", _failing_provider)
    monkeypatch.setattr(server, "FUND_FETCHER", _failing_provider)
    monkeypatch.setattr(server, "STOOQ_FETCHER", _failing_provider)
    monkeypatch.setattr(server, "NASDAQ_TRADER_FETCHER", _failing_provider)
    monkeypatch.setattr(server, "OPENFIGI_FETCHER", _failing_provider)
    client = TestClient(server.create_app())

    response = client.post("/api/providers/refresh-public")

    payload = response.json()
    results = {item["provider_id"]: item for item in payload["last_refresh"]["results"]}
    providers = {item["provider_id"]: item for item in payload["providers"]}
    assert response.status_code == 200
    assert results["binance_spot_public"]["state"] == "unavailable"
    assert results["binance_spot_public"]["usable_runtime"] is False
    assert results["kraken_public_market_data"]["state"] == "live"
    assert providers["binance_spot_public"]["health"]["state"] == "unavailable"
    # kraken's cache TTL is 30s and refresh-public refreshes every provider
    # before the health block is computed, so on a slow machine the label can
    # honestly read stale_cache seconds after a live fill; both prove the
    # detail refresh produced a cache — "unavailable" is the failure signal
    assert providers["kraken_public_market_data"]["health"]["state"] in {
        "active",
        "stale_cache",
    }
    assert payload["last_refresh"]["summary"]["unavailable"] >= 1
    assert payload["last_refresh"]["summary"]["refreshed"] >= 1
    assert not (tmp_path / "market_data" / "crypto_latest.json").exists()
    assert (tmp_path / "market_data" / "crypto" / "BTCUSDT" / "15m.json").is_file()
    error_log = tmp_path / payload["last_refresh"]["artifacts"]["error_log"]
    assert error_log.read_text(encoding="utf-8")
    assert "binance_spot_public unavailable" in error_log.read_text(encoding="utf-8")


def test_public_provider_refresh_keeps_dbnomics_result_provider_specific_when_bls_succeeds(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = LocalStateStore(root=tmp_path)
    monkeypatch.setattr(server, "STORE", store)
    monkeypatch.setattr(server, "MARKET_FETCHER", _fake_tickers)
    monkeypatch.setattr(server, "CRYPTO_DETAIL_FETCHER", _fake_crypto_detail)
    monkeypatch.setattr(server, "NEWS_FETCHER", _fake_news)
    monkeypatch.setattr(server, "RESEARCH_FETCHER", _fake_research_bls_only)
    monkeypatch.setattr(server, "RATES_FETCHER", _treasury_xml)
    monkeypatch.setattr(server, "SOFR_FETCHER", _sofr_json)
    monkeypatch.setattr(server, "FX_FETCHER", _ecb_xml)
    monkeypatch.setattr(server, "FED_H10_FETCHER", _h10_csv)
    monkeypatch.setattr(server, "BOC_FX_FETCHER", _boc_json)
    monkeypatch.setattr(server, "COMMODITY_FETCHER", _world_bank_xlsx)
    monkeypatch.setattr(server, "FUND_FETCHER", _sec_funds_raw)
    monkeypatch.setattr(server, "STOOQ_FETCHER", _fake_stooq_quote)
    monkeypatch.setattr(server, "NASDAQ_TRADER_FETCHER", _fake_nasdaq_trader_directory)
    monkeypatch.setattr(server, "OPENFIGI_FETCHER", _fake_openfigi_mapping)
    client = TestClient(server.create_app())

    response = client.post("/api/providers/refresh-public")

    payload = response.json()
    results = {item["provider_id"]: item for item in payload["last_refresh"]["results"]}
    assert response.status_code == 200
    assert results["dbnomics_public"]["state"] == "unavailable"
    assert results["dbnomics_public"]["cache_written"] is False
    assert results["dbnomics_public"]["cache_available"] is False
    assert results["dbnomics_public"]["cache_write_status"] == "not_available"
    assert results["dbnomics_public"]["usable_runtime"] is False
    assert results["bls_public_macro"]["state"] == "live"
    assert results["bls_public_macro"]["cache_written"] is True
    assert results["bls_public_macro"]["cache_written_this_run"] is True
    assert results["bls_public_macro"]["cache_available"] is True
    assert results["bls_public_macro"]["cache_write_status"] == "written_this_run"
    assert results["bls_public_macro"]["usable_runtime"] is True
    assert payload["last_refresh"]["summary"]["unavailable"] >= 1
    assert (tmp_path / "market_data" / "macro" / "bls" / "latest_series.json").is_file()
    assert not (
        tmp_path
        / "market_data"
        / "macro"
        / "dbnomics"
        / "INSEE"
        / "IPC-2015"
        / "A.IPC.SO.00.00.INDICE.ENSEMBLE.FE.SO.BRUT.2015.FALSE.json"
    ).exists()
