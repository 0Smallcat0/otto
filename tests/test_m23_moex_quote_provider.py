from pathlib import Path

from fastapi.testclient import TestClient

from src.local_terminal import server
from src.local_terminal.moex_data import (
    MOEX_PROVIDER_ID,
    MOEX_WATCHLIST,
    moex_quote_snapshot_payload,
    moex_symbol_list,
    normalize_moex_quote_snapshot,
)
from src.local_terminal.storage import LocalStateStore


def _raw(symbol: str = "SBER") -> dict[str, object]:
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
                [symbol, None, None, None, None, 0, 0, "19:20:39", None, None, "SPEQ"],
                [symbol, 319.75, 322.5, 324.75, 317.67, 37169464, 11933949644, "22:30:03", 319.75, 319.76, "TQBR"],
            ],
        },
    }


def _fake_moex_fetcher(*, symbol: str) -> dict[str, object]:
    assert symbol in set(MOEX_WATCHLIST)
    return _raw(symbol=symbol)


def test_moex_payload_uses_explicit_unavailable_state_without_fixture_runtime() -> None:
    payload = moex_quote_snapshot_payload(
        {},
        refresh=False,
        fetcher=_fake_moex_fetcher,
    )

    assert payload["status"]["state"] == "unavailable"
    assert payload["quotes"] == []
    assert payload["summary"]["provider_id"] == MOEX_PROVIDER_ID
    assert payload["entry"]["auth_mode"] == "public-no-key"
    assert "offline_fixture" not in str(payload)


def test_moex_symbol_list_is_bounded_and_normalized() -> None:
    assert moex_symbol_list("sber, GAZP,MOEX,SBER, bad symbol!, USD/RUB") == [
        "SBER",
        "GAZP",
        "MOEX",
        "BADSYMBOL",
        "USDRUB",
    ]
    assert moex_symbol_list("") == list(MOEX_WATCHLIST)


def test_moex_normalizes_delayed_quote_snapshot_as_non_orderable() -> None:
    payload = normalize_moex_quote_snapshot(_raw())

    assert payload["status"]["provider_id"] == MOEX_PROVIDER_ID
    assert payload["status"]["state"] == "live"
    assert payload["summary"]["price"] == "319.75"
    assert payload["quotes"][0]["board_id"] == "TQBR"
    assert payload["quotes"][0]["quote_semantics"] == "quote_not_orderable"
    assert payload["quotes"][0]["live_action_enabled"] is False
    assert payload["quotes"][0]["orderable"] is False


def test_moex_refresh_endpoint_writes_public_cache_and_markets_contract(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = LocalStateStore(root=tmp_path)
    monkeypatch.setattr(server, "STORE", store)
    monkeypatch.setattr(server, "MOEX_FETCHER", _fake_moex_fetcher)
    client = TestClient(server.create_app())

    refreshed = client.post(
        "/api/moex/quote-snapshots/refresh",
        json={"symbols": "SBER,GAZP,MOEX"},
    )
    markets = client.post("/api/markets/moex/quotes/refresh")
    providers = client.get("/api/providers")
    local_state = client.get("/api/local-state")

    assert refreshed.status_code == 200
    assert refreshed.json()["status"]["state"] == "live"
    assert refreshed.json()["summary"]["symbols"] == "SBER,GAZP,MOEX"
    assert refreshed.json()["summary"]["row_count"] == 3
    assert "cache" not in refreshed.json()
    assert not (tmp_path / "settings" / "local_secrets.json").exists()
    assert (tmp_path / "market_data" / "quotes" / "moex" / "SBER.json").is_file()
    assert (tmp_path / "market_data" / "quotes" / "moex" / "GAZP.json").is_file()
    assert (tmp_path / "market_data" / "quotes" / "moex" / "MOEX.json").is_file()

    source_row = next(
        row
        for row in markets.json()["source_coverage_matrix"]
        if row["provider_id"] == MOEX_PROVIDER_ID
    )
    assert source_row["state"] == "live"
    assert source_row["auth_mode"] == "public_no_key"
    assert source_row["runtime_role"] == "international_delayed_quote_snapshot"
    assert source_row["quote_semantics"] == "quote_not_orderable"
    assert source_row["safe_action_id"] == "markets_moex_quote_snapshot_refresh"
    assert source_row["live_action_enabled"] is False
    assert markets.json()["research_summary"]["moex_quotes"]["row_count"] == 3
    assert any(
        provider["provider_id"] == MOEX_PROVIDER_ID
        and provider["health"]["state"] == "active"
        and provider["health"]["cache_id"] == "moex_quote_SBER"
        for provider in providers.json()["providers"]
    )
    assert local_state.json()["storage"]["moex_quote_cache"].endswith("SBER.json")


def test_moex_market_refresh_without_cache_is_explicitly_not_refreshed(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())

    response = client.get("/api/moex/quote-snapshots")
    markets = client.get("/api/markets")

    assert response.status_code == 200
    assert response.json()["status"]["state"] == "unavailable"
    assert response.json()["quotes"] == []
    source_row = next(
        row
        for row in markets.json()["source_coverage_matrix"]
        if row["provider_id"] == MOEX_PROVIDER_ID
    )
    assert source_row["gated_reason"] == "refresh_not_run"
    assert source_row["next_safe_action"] == (
        "Run markets_moex_quote_snapshot_refresh to populate the public no-key cache."
    )
    assert "offline_fixture" not in response.text
