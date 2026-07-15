from pathlib import Path

from fastapi.testclient import TestClient

from otto.local_terminal import server
from otto.local_terminal.nasdaq_trader_data import (
    NASDAQ_TRADER_PROVIDER_ID,
    nasdaq_trader_symbol_search_payload,
    nasdaq_trader_symbol_directory_payload,
    normalize_nasdaq_trader_symbol_directory,
)
from otto.local_terminal.storage import LocalStateStore


def _raw_directory() -> dict[str, str]:
    return {
        "nasdaqlisted.txt": "\n".join(
            [
                "Symbol|Security Name|Market Category|Test Issue|Financial Status|Round Lot Size|ETF|NextShares",
                "AAPL|Apple Inc. - Common Stock|Q|N|N|100|N|N",
                "QQQ|Invesco QQQ Trust|G|N|N|100|Y|N",
                "ZTEST|Test Nasdaq Issue|Q|Y|N|100|N|N",
                "File Creation Time: 0526202617:03|||||||",
            ]
        ),
        "otherlisted.txt": "\n".join(
            [
                "ACT Symbol|Security Name|Exchange|CQS Symbol|ETF|Round Lot Size|Test Issue|NASDAQ Symbol",
                "IBM|International Business Machines Corporation|N|IBM|N|100|N|IBM",
                "SPY|SPDR S&P 500 ETF Trust|P|SPY|Y|100|N|SPY",
                "BAD|Test Other Issue|N|BAD|N|100|Y|BAD",
                "File Creation Time: 0526202617:04|||||||",
            ]
        ),
    }


def _fake_nasdaq_fetcher() -> dict[str, str]:
    return _raw_directory()


def test_nasdaq_trader_payload_uses_explicit_unavailable_state_without_fixture_runtime() -> None:
    payload = nasdaq_trader_symbol_directory_payload(
        {},
        refresh=False,
        fetcher=_fake_nasdaq_fetcher,
    )

    assert payload["status"]["state"] == "unavailable"
    assert payload["symbols"] == []
    assert payload["summary"]["provider_id"] == NASDAQ_TRADER_PROVIDER_ID
    assert payload["entry"]["auth_mode"] == "public-no-key"
    assert "offline_fixture" not in str(payload)


def test_nasdaq_trader_normalizes_symbol_directory_as_reference_data() -> None:
    payload = normalize_nasdaq_trader_symbol_directory(
        _raw_directory(),
        retrieved_at="2026-05-26T00:00:00Z",
    )

    assert payload["status"]["provider_id"] == NASDAQ_TRADER_PROVIDER_ID
    assert payload["status"]["state"] == "live"
    assert payload["summary"]["row_count"] == 4
    assert payload["summary"]["nasdaq_listed_count"] == 2
    assert payload["summary"]["other_listed_count"] == 2
    assert payload["summary"]["etf_count"] == 2
    assert payload["summary"]["test_issue_count"] == 2
    assert payload["summary"]["quote_semantics"] == "not_quote"
    assert payload["symbols"][0]["symbol"] == "AAPL"
    assert payload["symbols"][0]["quote_semantics"] == "not_quote"
    assert payload["symbols"][0]["live_action_enabled"] is False
    assert payload["symbols"][0]["orderable"] is False

    search = nasdaq_trader_symbol_search_payload(payload, query="SPY", limit=3)

    assert search["query"] == "SPY"
    assert search["row_count"] == 1
    assert search["total_matches"] == 1
    assert search["rows"][0]["symbol"] == "SPY"
    assert search["rows"][0]["quote_semantics"] == "not_quote"
    assert search["rows"][0]["orderable"] is False
    assert search["quote_semantics"] == "not_quote"


def test_nasdaq_trader_refresh_endpoint_writes_reference_cache_and_markets_contract(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = LocalStateStore(root=tmp_path)
    monkeypatch.setattr(server, "STORE", store)
    monkeypatch.setattr(server, "NASDAQ_TRADER_FETCHER", _fake_nasdaq_fetcher)
    client = TestClient(server.create_app())

    refreshed = client.post("/api/nasdaq-trader/symbol-directory/refresh")
    search = client.get("/api/markets/nasdaq-trader/symbols/search?query=IBM&limit=5")
    markets = client.post("/api/markets/nasdaq-trader/symbols/refresh")
    providers = client.get("/api/providers")
    local_state = client.get("/api/local-state")

    assert refreshed.status_code == 200
    assert refreshed.json()["status"]["state"] == "live"
    assert refreshed.json()["summary"]["row_count"] == 4
    assert refreshed.json()["symbols"][1]["is_etf"] is True
    assert "cache" not in refreshed.json()
    assert search.status_code == 200
    assert search.json()["query"] == "IBM"
    assert search.json()["row_count"] == 1
    assert search.json()["rows"][0]["symbol"] == "IBM"
    assert search.json()["rows"][0]["listing_exchange"] == "NYSE"
    assert search.json()["orderable"] is False
    assert not (tmp_path / "settings" / "local_secrets.json").exists()
    assert (
        tmp_path
        / "market_data"
        / "reference"
        / "nasdaq_trader"
        / "symbol_directory.json"
    ).is_file()

    source_row = next(
        row
        for row in markets.json()["source_coverage_matrix"]
        if row["provider_id"] == NASDAQ_TRADER_PROVIDER_ID
    )
    assert source_row["state"] == "live"
    assert source_row["auth_mode"] == "public_no_key"
    assert source_row["runtime_role"] == "symbol_directory"
    assert source_row["quote_semantics"] == "not_quote"
    assert source_row["safe_action_id"] == "markets_nasdaq_symbol_directory_refresh"
    assert source_row["context_only"] is True
    assert source_row["live_action_enabled"] is False
    assert markets.json()["research_summary"]["nasdaq_symbols"]["row_count"] == 4
    assert markets.json()["research_summary"]["nasdaq_symbols"]["search"]["rows"][0][
        "symbol"
    ] == "AAPL"
    assert markets.json()["stocks"]["symbol_directory_status"]["provider_id"] == (
        NASDAQ_TRADER_PROVIDER_ID
    )
    assert markets.json()["stocks"]["summary"]["symbol_directory_row_count"] == 4
    assert markets.json()["stocks"]["summary"]["symbol_directory_quote_semantics"] == "not_quote"
    assert markets.json()["stocks"]["symbol_search"]["query"] == "AAPL"
    assert markets.json()["stocks"]["symbols"][0]["live_action_enabled"] is False
    assert any(
        provider["provider_id"] == NASDAQ_TRADER_PROVIDER_ID
        and provider["health"]["state"] == "active"
        and provider["health"]["cache_id"] == "nasdaq_trader_symbol_directory"
        for provider in providers.json()["providers"]
    )
    assert local_state.json()["storage"]["nasdaq_trader_symbol_directory_cache"].endswith(
        "market_data/reference/nasdaq_trader/symbol_directory.json"
    )


def test_nasdaq_trader_market_refresh_without_cache_is_explicitly_not_refreshed(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())

    response = client.get("/api/nasdaq-trader/symbol-directory")
    search = client.get("/api/markets/nasdaq-trader/symbols/search?query=AAPL")
    markets = client.get("/api/markets")

    assert response.status_code == 200
    assert response.json()["status"]["state"] == "unavailable"
    assert response.json()["symbols"] == []
    assert search.json()["status"]["state"] == "unavailable"
    assert search.json()["row_count"] == 0
    assert search.json()["orderable"] is False
    source_row = next(
        row
        for row in markets.json()["source_coverage_matrix"]
        if row["provider_id"] == NASDAQ_TRADER_PROVIDER_ID
    )
    assert source_row["gated_reason"] == "refresh_not_run"
    assert source_row["next_safe_action"] == (
        "Run markets_nasdaq_symbol_directory_refresh to populate the public no-key cache."
    )
    assert "offline_fixture" not in response.text
