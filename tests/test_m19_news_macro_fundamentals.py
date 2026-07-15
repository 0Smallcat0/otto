from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from otto.local_terminal import server
from otto.local_terminal.research_data import (
    normalize_dbnomics_series,
    normalize_sec_company_submissions,
    normalize_sec_company_tickers,
    normalize_sec_companyfacts,
    research_data_payload,
)
from otto.local_terminal.storage import LocalStateStore


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


def _fake_research() -> dict[str, object]:
    return {
        "sec": _sec_raw(),
        "sec_tickers": _sec_tickers_raw(),
        "sec_submissions": _sec_submissions_raw(),
        "dbnomics": _dbnomics_raw(),
        "errors": [],
    }


def _fake_news() -> dict[str, object]:
    return {
        "items": [
            {
                "item_id": "m19-news",
                "title": "Market desk tracks CPI and company filings",
                "source": "Public Wire",
                "category": "ECO",
                "published_at": _now(),
                "url": "https://example.test/m19",
                "summary": "Source-attributed headline metadata only.",
                "tags": ["CPI", "SEC"],
            }
        ],
        "errors": [],
        "source_count": 1,
        "failed_source_count": 0,
    }


def test_research_data_normalizes_sec_and_dbnomics_without_keys() -> None:
    sec = normalize_sec_companyfacts(_sec_raw(), retrieved_at=_now())
    sec_tickers = normalize_sec_company_tickers(_sec_tickers_raw(), retrieved_at=_now())
    sec_submissions = normalize_sec_company_submissions(_sec_submissions_raw(), retrieved_at=_now())
    dbnomics = normalize_dbnomics_series(_dbnomics_raw(), retrieved_at=_now())
    payload = research_data_payload(
        sec,
        dbnomics,
        sec_ticker_cache=sec_tickers,
        sec_submissions_cache=sec_submissions,
    )

    assert sec["status"]["provider_id"] == "sec_edgar_public"
    assert sec["companies"][0]["facts"][0]["label"] == "Assets"
    assert dbnomics["status"]["provider_id"] == "dbnomics_public"
    assert dbnomics["series"][0]["latest_value"] == "119.34"
    assert payload["status"]["state"] == "stale"
    assert payload["equity_registry"]["summary"]["row_count"] == 3
    assert payload["filings"]["summary"]["row_count"] == 1
    assert payload["fundamentals"]["summary"]["fact_count"] == 2
    assert payload["macro"]["summary"]["series_count"] == 1
    assert "api_key=" not in str(payload).lower()


def test_news_refresh_writes_research_caches_and_exposes_provider_state(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    monkeypatch.setattr(server, "NEWS_FETCHER", _fake_news)
    monkeypatch.setattr(server, "RESEARCH_FETCHER", _fake_research)
    client = TestClient(server.create_app())

    refreshed = client.post("/api/news/refresh")
    providers = client.get("/api/providers")
    local_state = client.get("/api/local-state")

    assert refreshed.status_code == 200
    body = refreshed.json()
    assert body["status"]["state"] == "live"
    assert body["research"]["fundamentals"]["summary"]["company_count"] == 1
    assert body["research"]["filings"]["summary"]["row_count"] == 1
    assert body["research"]["macro"]["summary"]["latest_value"] == "119.34"
    assert body["research"]["optional_key_sources"][0]["state"] == "key_required"
    assert "cache" not in body
    assert "api_key=" not in refreshed.text.lower()
    assert (tmp_path / "market_data" / "fundamentals" / "sec" / "0000320193" / "companyfacts.json").is_file()
    assert (tmp_path / "market_data" / "fundamentals" / "sec" / "company_tickers.json").is_file()
    assert (tmp_path / "market_data" / "fundamentals" / "sec" / "0000320193" / "submissions.json").is_file()
    assert (
        tmp_path
        / "market_data"
        / "macro"
        / "dbnomics"
        / "INSEE"
        / "IPC-2015"
        / "A.IPC.SO.00.00.INDICE.ENSEMBLE.FE.SO.BRUT.2015.FALSE.json"
    ).is_file()
    assert any(
        provider["provider_id"] == "sec_edgar_public"
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
    assert any(
        provider["provider_id"] == "dbnomics_public"
        and provider["health"]["state"] == "active"
        for provider in providers.json()["providers"]
    )
    assert local_state.json()["storage"]["sec_fundamentals_cache"].endswith("companyfacts.json")
    assert local_state.json()["storage"]["sec_company_tickers_cache"].endswith("company_tickers.json")
    assert local_state.json()["storage"]["sec_company_submissions_cache"].endswith("submissions.json")
    assert local_state.json()["storage"]["dbnomics_macro_cache"].endswith(".json")


def test_dashboard_and_markets_consume_research_summaries(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = LocalStateStore(root=tmp_path)
    store.write_sec_fundamentals_cache(normalize_sec_companyfacts(_sec_raw(), retrieved_at=_now()))
    store.write_sec_company_tickers_cache(
        normalize_sec_company_tickers(_sec_tickers_raw(), retrieved_at=_now())
    )
    store.write_sec_company_submissions_cache(
        normalize_sec_company_submissions(_sec_submissions_raw(), retrieved_at=_now())
    )
    store.write_dbnomics_macro_cache(normalize_dbnomics_series(_dbnomics_raw(), retrieved_at=_now()))
    monkeypatch.setattr(server, "STORE", store)
    client = TestClient(server.create_app())

    dashboard = client.get("/api/dashboard")
    markets = client.get("/api/markets")

    assert dashboard.status_code == 200
    research_panel = next(
        panel for panel in dashboard.json()["panels"] if panel["panel_id"] == "macro_fundamentals"
    )
    assert research_panel["state"] == "stale"
    assert research_panel["metrics"][0]["value"] == "1"
    assert "research_data" in dashboard.json()["freshness"]
    assert markets.status_code == 200
    assert markets.json()["research_summary"]["fundamentals"]["company_count"] == 1
    assert markets.json()["research_summary"]["equity_registry"]["row_count"] == 3
    assert markets.json()["research_summary"]["filings"]["row_count"] == 1
    assert markets.json()["research_summary"]["macro"]["latest"] == "119.34"
    assert any(
        gateway["tab_id"] == "stocks" and gateway["state"] == "stock_lanes_available"
        for gateway in markets.json()["asset_gateways"]
    )
