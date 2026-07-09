import json
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from src.local_terminal import server
from src.local_terminal.markets import default_markets_layout, markets_payload
from src.local_terminal.research_data import (
    normalize_sec_company_submissions_collection,
    normalize_sec_company_submissions,
    normalize_sec_company_tickers,
    normalize_sec_companyfacts,
    normalize_sec_xbrl_frame,
    research_data_payload,
)
from src.local_terminal.storage import LocalStateStore


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


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
                },
                "NetIncomeLoss": {
                    "units": {
                        "USD": [
                            {
                                "val": 94000000000,
                                "end": "2025-09-27",
                                "fy": 2025,
                                "fp": "FY",
                                "form": "10-K",
                                "filed": "2025-10-31",
                            }
                        ]
                    }
                },
            }
        },
    }


def _sec_tickers_raw() -> dict[str, object]:
    return {
        "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
        "1": {"cik_str": 789019, "ticker": "MSFT", "title": "MICROSOFT CORP"},
        "2": {"cik_str": 1045810, "ticker": "NVDA", "title": "NVIDIA CORP"},
        "3": {"cik_str": 1018724, "ticker": "AMZN", "title": "AMAZON COM INC"},
    }


def _sec_submissions_raw(
    *,
    symbol: str = "AAPL",
    cik: str = "320193",
    name: str = "Apple Inc.",
    latest_date: str = "2025-10-31",
    prior_date: str = "2025-08-01",
) -> dict[str, object]:
    compact_cik = str(int(cik))
    accession_prefix = compact_cik.zfill(10)
    return {
        "cik": compact_cik,
        "name": name,
        "tickers": [symbol],
        "filings": {
            "recent": {
                "accessionNumber": [
                    f"{accession_prefix}-25-000079",
                    f"{accession_prefix}-25-000073",
                ],
                "filingDate": [latest_date, prior_date],
                "reportDate": ["2025-09-27", "2025-06-28"],
                "acceptanceDateTime": ["20251031183000", "20250801170000"],
                "form": ["10-K", "10-Q"],
                "primaryDocument": [
                    f"{symbol.lower()}-20250927.htm",
                    f"{symbol.lower()}-20250628.htm",
                ],
                "primaryDocDescription": ["10-K", "10-Q"],
                "items": ["", ""],
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
        "description": "Total assets frame.",
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
            },
            {
                "cik": 789019,
                "entityName": "MICROSOFT CORP",
                "loc": "US-WA",
                "end": "2023-06-30",
                "val": 411976000000,
                "accn": "0000950170-23-035122",
                "fy": 2023,
                "fp": "FY",
                "form": "10-K",
                "filed": "2023-07-27",
                "frame": "CY2023Q4I",
            },
            {
                "cik": 1045810,
                "entityName": "NVIDIA CORP",
                "loc": "US-CA",
                "end": "2024-01-28",
                "val": 65728000000,
                "accn": "0001045810-24-000029",
                "fy": 2024,
                "fp": "FY",
                "form": "10-K",
                "filed": "2024-02-21",
                "frame": "CY2023Q4I",
            },
        ],
    }


def _fake_research() -> dict[str, object]:
    return {
        "sec": _sec_raw(),
        "sec_tickers": _sec_tickers_raw(),
        "sec_submissions": _sec_submissions_raw(),
        "sec_submissions_by_symbol": {
            "AAPL": _sec_submissions_raw(),
            "MSFT": _sec_submissions_raw(
                symbol="MSFT",
                cik="789019",
                name="MICROSOFT CORP",
                latest_date="2025-10-30",
            ),
            "NVDA": _sec_submissions_raw(
                symbol="NVDA",
                cik="1045810",
                name="NVIDIA CORP",
                latest_date="2025-10-29",
            ),
        },
        "sec_frames": _sec_frame_raw(),
        "dbnomics": {},
        "errors": [],
    }


def test_sec_company_tickers_normalize_no_key_registry() -> None:
    payload = normalize_sec_company_tickers(_sec_tickers_raw(), retrieved_at=_now())

    assert payload["status"]["provider_id"] == "sec_company_ticker_registry_public"
    assert payload["status"]["source"] == "sec_company_ticker_registry"
    assert payload["summary"]["row_count"] == 3
    assert payload["summary"]["registry_total"] == 4
    assert payload["summary"]["matched_symbols"] == "AAPL,MSFT,NVDA"
    assert payload["rows"][0]["symbol"] == "AAPL"
    assert payload["rows"][0]["reference_only"] is True
    assert "api_key" not in str(payload).lower()


def test_sec_company_submissions_normalize_recent_filings() -> None:
    payload = normalize_sec_company_submissions(_sec_submissions_raw(), retrieved_at=_now())

    assert payload["status"]["provider_id"] == "sec_company_submissions_public"
    assert payload["status"]["source"] == "sec_company_submissions"
    assert payload["summary"]["row_count"] == 2
    assert payload["summary"]["latest_form"] == "10-K"
    assert payload["rows"][0]["symbol"] == "AAPL"
    assert payload["rows"][0]["form"] == "10-K"
    assert payload["rows"][0]["reference_only"] is True
    assert payload["rows"][0]["filing_url"].startswith(
        "https://www.sec.gov/Archives/edgar/data/320193/"
    )
    assert "api_key" not in str(payload).lower()


def test_sec_xbrl_frame_normalize_bounded_reference_rows() -> None:
    payload = normalize_sec_xbrl_frame(_sec_frame_raw(), retrieved_at=_now())

    assert payload["status"]["provider_id"] == "sec_xbrl_frames_public"
    assert payload["status"]["source"] == "sec_xbrl_frames"
    assert payload["summary"]["tag"] == "Assets"
    assert payload["summary"]["period"] == "CY2023Q4I"
    assert payload["summary"]["row_count"] == 3
    assert payload["summary"]["entity_count"] == 3
    assert payload["summary"]["quote_semantics"] == "not_quote"
    assert payload["rows"][0]["symbol"] == "AAPL"
    assert payload["rows"][1]["symbol"] == "MSFT"
    assert payload["rows"][0]["reference_only"] is True
    assert payload["rows"][0]["cache_path"].endswith(
        "market_data/fundamentals/sec/frames/us-gaap/Assets/USD/CY2023Q4I.json"
    )
    assert "api_key" not in str(payload).lower()
    assert "real_order" not in str(payload).lower()


def test_sec_company_submissions_collection_normalizes_watchlist() -> None:
    payload = normalize_sec_company_submissions_collection(
        {
            "by_symbol": {
                "AAPL": _sec_submissions_raw(),
                "MSFT": _sec_submissions_raw(
                    symbol="MSFT",
                    cik="789019",
                    name="MICROSOFT CORP",
                    latest_date="2025-10-30",
                ),
                "NVDA": _sec_submissions_raw(
                    symbol="NVDA",
                    cik="1045810",
                    name="NVIDIA CORP",
                    latest_date="2025-10-29",
                ),
            }
        },
        retrieved_at=_now(),
    )

    assert payload["status"]["provider_id"] == "sec_company_submissions_public"
    assert payload["summary"]["row_count"] == 6
    assert payload["summary"]["company_count"] == 3
    assert payload["summary"]["filing_symbols"] == "AAPL,MSFT,NVDA"
    assert payload["summary"]["latest_symbol"] == "AAPL"
    assert len(payload["company_summaries"]) == 3
    assert payload["rows"][0]["symbol"] == "AAPL"
    assert {row["symbol"] for row in payload["rows"]} == {"AAPL", "MSFT", "NVDA"}
    assert "0000789019/submissions.json" in payload["summary"]["cache_paths"]
    assert "api_key" not in str(payload).lower()


def test_markets_payload_exposes_stock_fundamentals_view() -> None:
    sec = normalize_sec_companyfacts(_sec_raw(), retrieved_at=_now())
    sec_tickers = normalize_sec_company_tickers(_sec_tickers_raw(), retrieved_at=_now())
    sec_frames = normalize_sec_xbrl_frame(_sec_frame_raw(), retrieved_at=_now())
    sec_submissions = normalize_sec_company_submissions_collection(
        {
            "by_symbol": {
                "AAPL": _sec_submissions_raw(),
                "MSFT": _sec_submissions_raw(
                    symbol="MSFT",
                    cik="789019",
                    name="MICROSOFT CORP",
                    latest_date="2025-10-30",
                ),
                "NVDA": _sec_submissions_raw(
                    symbol="NVDA",
                    cik="1045810",
                    name="NVIDIA CORP",
                    latest_date="2025-10-29",
                ),
            }
        },
        retrieved_at=_now(),
    )
    payload = markets_payload(
        default_markets_layout(),
        {},
        research_data=research_data_payload(
            sec,
            {},
            sec_ticker_cache=sec_tickers,
            sec_submissions_cache=sec_submissions,
            sec_frames_cache=sec_frames,
        ),
    )

    assert payload["stocks"]["status"]["provider_id"] == "sec_edgar_public"
    assert payload["stocks"]["status"]["source"] == "sec_edgar_public"
    assert payload["stocks"]["registry_status"]["provider_id"] == "sec_company_ticker_registry_public"
    assert payload["stocks"]["summary"]["registry_row_count"] == 3
    assert payload["stocks"]["summary"]["registry_total"] == 4
    assert payload["stocks"]["summary"]["registry_matched_symbols"] == "AAPL,MSFT,NVDA"
    assert payload["stocks"]["filings_status"]["provider_id"] == "sec_company_submissions_public"
    assert payload["stocks"]["summary"]["filing_count"] == 6
    assert payload["stocks"]["summary"]["filing_company_count"] == 3
    assert payload["stocks"]["summary"]["filing_symbols"] == "AAPL,MSFT,NVDA"
    assert payload["stocks"]["summary"]["latest_filing_form"] == "10-K"
    assert payload["stocks"]["summary"]["company_count"] == 1
    assert payload["stocks"]["summary"]["fact_count"] == 2
    assert payload["stocks"]["summary"]["frame_count"] == 3
    assert payload["stocks"]["summary"]["frame_entity_count"] == 3
    assert payload["stocks"]["summary"]["frame_quote_semantics"] == "not_quote"
    assert payload["stocks"]["summary"]["quote_state"] == "key_required"
    assert payload["stocks"]["summary"]["quote_provider"] == "alphavantage_global_quote_optional_key"
    assert payload["stocks"]["summary"]["status_lane_count"] == 6
    assert payload["stocks"]["summary"]["available_lane_count"] == 4
    assert payload["stocks"]["summary"]["gated_lane_count"] == 1
    assert payload["stocks"]["summary"]["available_lanes"] == "registry,filings,fundamentals,frames"
    assert [lane["lane_id"] for lane in payload["stocks"]["status_lanes"]] == [
        "quotes",
        "symbol_directory",
        "registry",
        "filings",
        "fundamentals",
        "frames",
    ]
    assert payload["stocks"]["status_lanes"][0]["gated"] is True
    assert payload["stocks"]["status_lanes"][3]["available"] is True
    assert "AAPL,MSFT,NVDA" in payload["stocks"]["status_lanes"][3]["summary"]
    assert payload["stocks"]["companies"][0]["symbol"] == "AAPL"
    assert payload["stocks"]["registry"][1]["symbol"] == "MSFT"
    assert payload["stocks"]["filings"][0]["accession_number"] == "0000320193-25-000079"
    assert {row["symbol"] for row in payload["stocks"]["filings"]} == {"AAPL", "MSFT", "NVDA"}
    assert payload["stocks"]["companies"][0]["facts"][0]["label"] == "Assets"
    assert payload["research_summary"]["equity_registry"]["rows"][2]["symbol"] == "NVDA"
    assert payload["research_summary"]["filings"]["company_count"] == 3
    assert any(row["form"] == "10-Q" for row in payload["research_summary"]["filings"]["rows"])
    assert payload["research_summary"]["fundamentals"]["companies"][0]["facts"][1]["label"] == "Net income"
    assert payload["research_summary"]["sec_frames"]["rows"][1]["symbol"] == "MSFT"
    assert payload["research_summary"]["sec_frames"]["quote_semantics"] == "not_quote"
    assert any(
        gateway["tab_id"] == "stocks" and gateway["state"] == "stock_lanes_available"
        for gateway in payload["asset_gateways"]
    )
    assert "api_key" not in str(payload).lower()


def test_markets_stocks_refresh_writes_sec_cache_and_keeps_quotes_gated(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    monkeypatch.setattr(server, "RESEARCH_FETCHER", _fake_research)
    client = TestClient(server.create_app())

    refreshed = client.post("/api/markets/stocks/refresh")
    providers = client.get("/api/providers")
    local_state = client.get("/api/local-state")

    assert refreshed.status_code == 200
    body = refreshed.json()
    assert body["stocks"]["status"]["state"] == "live"
    assert body["stocks"]["registry_status"]["state"] == "live"
    assert body["stocks"]["filings_status"]["state"] == "live"
    assert body["stocks"]["summary"]["registry_row_count"] == 3
    assert body["stocks"]["summary"]["filing_count"] == 6
    assert body["stocks"]["summary"]["filing_company_count"] == 3
    assert body["stocks"]["summary"]["filing_symbols"] == "AAPL,MSFT,NVDA"
    assert body["stocks"]["summary"]["company_count"] == 1
    assert body["stocks"]["summary"]["fact_count"] == 2
    assert body["stocks"]["summary"]["frame_count"] == 3
    assert body["stocks"]["frames_status"]["provider_id"] == "sec_xbrl_frames_public"
    assert body["stocks"]["summary"]["quote_state"] == "key_required"
    assert body["stocks"]["summary"]["available_lane_count"] == 4
    assert body["stocks"]["summary"]["status_lane_count"] == 6
    assert body["stocks"]["status_lanes"][0]["lane_id"] == "quotes"
    assert body["stocks"]["status_lanes"][0]["gated"] is True
    assert body["stocks"]["status_lanes"][1]["lane_id"] == "symbol_directory"
    stock_gateway = next(
        gateway for gateway in body["asset_gateways"] if gateway["tab_id"] == "stocks"
    )
    assert stock_gateway["state"] == "stock_lanes_available"
    assert stock_gateway["provider_id"] == "stock_status_lanes"
    assert (tmp_path / "market_data" / "fundamentals" / "sec" / "0000320193" / "companyfacts.json").is_file()
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
    msft_cache_path = (
        tmp_path / "market_data" / "fundamentals" / "sec" / "0000789019" / "submissions.json"
    )
    nvda_cache_path = (
        tmp_path / "market_data" / "fundamentals" / "sec" / "0001045810" / "submissions.json"
    )
    assert msft_cache_path.is_file()
    assert nvda_cache_path.is_file()
    msft_cache = json.loads(msft_cache_path.read_text(encoding="utf-8"))
    nvda_cache = json.loads(nvda_cache_path.read_text(encoding="utf-8"))
    assert msft_cache["summary"]["symbol"] == "MSFT"
    assert msft_cache["summary"]["latest_filing_date"] == "2025-10-30"
    assert msft_cache["summary"]["cache_paths"].endswith("0000789019/submissions.json")
    assert nvda_cache["summary"]["symbol"] == "NVDA"
    assert nvda_cache["summary"]["latest_filing_date"] == "2025-10-29"
    assert any(
        provider["provider_id"] == "sec_edgar_public"
        and provider["health"]["state"] == "active"
        for provider in providers.json()["providers"]
    )
    assert any(
        provider["provider_id"] == "sec_xbrl_frames_public"
        and provider["health"]["state"] == "active"
        for provider in providers.json()["providers"]
    )
    assert any(
        provider["provider_id"] == "sec_company_ticker_registry_public"
        and provider["health"]["state"] == "active"
        for provider in providers.json()["providers"]
    )
    assert any(
        provider["provider_id"] == "sec_company_submissions_public"
        and provider["health"]["state"] == "active"
        for provider in providers.json()["providers"]
    )
    assert local_state.json()["storage"]["sec_fundamentals_cache"].endswith("companyfacts.json")
    assert local_state.json()["storage"]["sec_xbrl_frames_cache"].endswith("CY2023Q4I.json")
    assert local_state.json()["storage"]["sec_company_tickers_cache"].endswith("company_tickers.json")
    assert local_state.json()["storage"]["sec_company_submissions_cache"].endswith("submissions.json")
    assert len(local_state.json()["storage"]["sec_company_submissions_watchlist_caches"]) == 3
    assert "api_key" not in refreshed.text.lower()
    assert "real_order" not in refreshed.text.lower()
