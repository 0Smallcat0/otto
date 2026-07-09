"""M27-R2 — the quote watchlist the AI edits on request ("watch X for me").

State is a protected file (rotating backups); us/tw/fx groups are free-form,
crypto stays inside SUPPORTED_SYMBOLS because paper trading and the exchange
pair maps are wired per symbol.
"""

from fastapi.testclient import TestClient

from src.local_terminal import server
from src.local_terminal.storage import LocalStateStore


def _client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    return TestClient(server.create_app())


def test_watchlist_defaults_cover_all_groups(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    body = client.get("/api/markets/watchlist").json()
    assert body["group_order"] == ["crypto", "us", "tw", "fx"]
    assert body["groups"]["us"] == ["AAPL", "MSFT", "NVDA", "SPY"]
    assert body["groups"]["crypto"] == ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    assert body["safety"]["external_calls"] is False


def test_watchlist_update_persists_and_leaves_a_backup(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    first = client.post("/api/markets/watchlist", json={"group": "us", "symbols": ["tsla", "aapl "]})
    assert first.status_code == 200
    assert first.json()["groups"]["us"] == ["TSLA", "AAPL"]

    second = client.post("/api/markets/watchlist", json={"group": "tw", "symbols": "2454, 2330"})
    assert second.status_code == 200
    assert second.json()["groups"]["tw"] == ["2454", "2330"]
    # first write is unchanged by the second
    assert second.json()["groups"]["us"] == ["TSLA", "AAPL"]

    assert client.get("/api/markets/watchlist").json()["groups"]["us"] == ["TSLA", "AAPL"]
    backup = server.STORE.watchlist_state_path.with_name("watchlist_state.json.bak1")
    assert backup.is_file()


def test_watchlist_rejects_bad_updates(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    assert client.post("/api/markets/watchlist", json={"group": "bonds", "symbols": ["X"]}).status_code == 400
    assert client.post("/api/markets/watchlist", json={"group": "us", "symbols": []}).status_code == 400
    # crypto outside the supported paper symbols yields no valid entries
    assert client.post(
        "/api/markets/watchlist", json={"group": "crypto", "symbols": ["DOGEUSDT"]}
    ).status_code == 400
    # fx entries must be pairs
    assert client.post("/api/markets/watchlist", json={"group": "fx", "symbols": ["EURUSD"]}).status_code == 400
    ok = client.post("/api/markets/watchlist", json={"group": "fx", "symbols": ["usd/jpy"]})
    assert ok.status_code == 200
    assert ok.json()["groups"]["fx"] == ["USD/JPY"]


def test_watchlist_actions_registered_in_contract(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    contract = client.get("/api/agent-contract").json()
    actions = {action["action_id"]: action for action in contract["actions"]}
    assert actions["markets_watchlist_index"]["method"] == "GET"
    assert actions["markets_watchlist_update"]["safety_class"] == "local_watchlist_state_only"
