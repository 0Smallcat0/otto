"""M27 S3 — read-only detail endpoints that serve finished artifacts to readers.

The mission wall links a person from an activity event to the finished
document. These endpoints read local artifact directories only: no refresh,
no mutation, strict id validation (no path traversal).
"""

from fastapi.testclient import TestClient

from src.local_terminal import server
from src.local_terminal.markets import default_markets_layout, markets_payload
from src.local_terminal.storage import LocalStateStore


def _fake_tickers(symbols: list[str]) -> list[dict[str, str]]:
    return [
        {
            "symbol": symbol,
            "lastPrice": "100.00",
            "priceChange": "1.00",
            "priceChangePercent": "1.00",
            "highPrice": "110.00",
            "lowPrice": "90.00",
            "volume": "12345",
            "bidPrice": "99.50",
            "askPrice": "100.50",
            "openPrice": "99.00",
        }
        for symbol in symbols
    ]


def _client(tmp_path, monkeypatch) -> TestClient:
    store = LocalStateStore(root=tmp_path)
    monkeypatch.setattr(server, "STORE", store)
    live = markets_payload(default_markets_layout(), {}, fetcher=_fake_tickers, refresh=True)
    store.write_market_cache(live["cache"])
    return TestClient(server.create_app())


def test_backtest_run_detail_serves_finished_run(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    run = client.post("/api/backtest/run", json={})
    assert run.status_code == 200, run.text
    run_id = run.json()["run_id"]

    detail = client.get(f"/api/backtest/runs/{run_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["run_id"] == run_id
    assert body["summary"].get("symbol") == "BTCUSDT"
    assert isinstance(body["trades"], list)
    assert isinstance(body["equity_curve"], list)
    assert body["equity_curve"], "returns_curve.csv should parse into rows"
    assert "report_md" in body
    assert body["safety"]["mutates_local_state"] is False


def test_backtest_run_detail_rejects_unknown_and_hostile_ids(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    assert client.get("/api/backtest/runs/bt-00000000000000-deadbeef").status_code == 404
    assert client.get("/api/backtest/runs/..%2f..%2fsettings").status_code == 404
    assert client.get("/api/backtest/runs/bt-..-escape").status_code == 404


def test_news_brief_detail_serves_finished_brief(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    generated = client.post("/api/news/research-brief", json={})
    assert generated.status_code == 200, generated.text
    payload = generated.json()
    brief_meta = payload.get("research_brief") if isinstance(payload.get("research_brief"), dict) else payload
    brief_id = brief_meta.get("brief_id")
    assert brief_id, "research brief should report its brief_id"

    detail = client.get(f"/api/news/briefs/{brief_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["brief_id"] == brief_id
    assert isinstance(body["brief"], dict)
    assert "topics" in body["brief"]
    assert "brief_md" in body


def test_news_brief_detail_rejects_unknown_ids(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    assert client.get("/api/news/briefs/news-brief-00000000000000-dead").status_code == 404
    assert client.get("/api/news/briefs/not-a-brief").status_code == 404
