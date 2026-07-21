import json
from pathlib import Path

from fastapi.testclient import TestClient

from otto.local_terminal import server
from otto.local_terminal.dashboard import DASHBOARD_WIDGET_CATALOG, dashboard_payload
from otto.local_terminal.storage import LocalStateStore


def test_dashboard_payload_exposes_catalog_templates_and_local_status() -> None:
    payload = dashboard_payload(
        {
            "widgets": ["portfolio_summary", "data_freshness"],
            "template": "Local Default",
            "alerts_read": False,
        }
    )

    assert payload["summary"]["cash"] == "0.00"
    assert payload["freshness"]["market_data"] == "public_provider_unavailable / unavailable"
    assert payload["freshness"]["crypto_detail"] == "public_detail_unavailable / unavailable"
    assert len(payload["panels"]) >= 6
    assert len(payload["catalog"]) == len(DASHBOARD_WIDGET_CATALOG)
    assert len(payload["templates"]) == 6
    assert payload["widgets"] == ["portfolio_summary", "data_freshness"]
    assert payload["active_widgets"][1]["label"] == "Data Freshness"
    assert payload["active_widgets"][1]["capability"] == "local-status"
    margin_widget = next(
        widget for widget in payload["catalog"] if widget["widget_id"] == "margin_usage"
    )
    assert margin_widget["capability"] == "safety-gated"


def test_dashboard_payload_aggregates_provider_cache_and_paper_state() -> None:
    payload = dashboard_payload(
        {"widgets": ["crypto_markets", "open_positions"], "template": "Local Default"},
        {
            "status": {
                "source": "binance_public",
                "state": "live",
                "last_update": "2026-05-23T00:00:00Z",
            },
            "rows": [
                {"symbol": "BTCUSDT", "chg_pct": "2.5"},
                {"symbol": "ETHUSDT", "chg_pct": "-1.0"},
            ],
        },
        {
            "account": {
                "cash": "99500.00",
                "equity": "100250.00",
                "initial_cash": "100000.00",
                "updated_at": "2026-05-23T00:01:00Z",
            },
            "positions": {"BTCUSDT": {"symbol": "BTCUSDT"}},
            "orders": [{"status": "WORKING"}, {"status": "FILLED"}],
            "fills": [{"fill_id": "fill-1"}],
        },
        {
            "status": {
                "source": "binance_public",
                "state": "live",
                "last_update": "2026-05-23T00:00:30Z",
                "symbol": "BTCUSDT",
                "timeframe": "15m",
            },
            "trades": [{"trade_id": "t1"}],
            "candles": [
                {
                    "open": "100.00",
                    "high": "110.00",
                    "low": "99.00",
                    "close": "105.00",
                    "closed": True,
                }
            ],
        },
    )

    assert payload["summary"]["cash"] == "99500.00"
    assert payload["summary"]["open_pnl"] == "250.00"
    assert payload["summary"]["positions"] == 1
    assert payload["summary"]["open_orders"] == 1
    assert payload["freshness"]["market_data"] == "binance_public / live"
    assert payload["freshness"]["crypto_detail"] == "binance_public / live"
    assert payload["market_pulse"]["breadth"] == "1 up / 1 down / 2 tracked"
    assert payload["market_pulse"]["top_movers"][0] == "BTCUSDT 2.5%"
    assert {panel["panel_id"] for panel in payload["panels"]} >= {
        "provider_freshness",
        "market_pulse",
        "paper_ledger",
        "portfolio",
        "news",
        "backtests",
    }


def test_dashboard_payload_builds_route_state_panels_from_local_sources(tmp_path: Path) -> None:
    run_dir = tmp_path / "artifacts" / "backtests" / "bt-route-state"
    run_dir.mkdir(parents=True)
    (run_dir / "manifest.json").write_text(
        json.dumps(
            {
                "run_id": "bt-route-state",
                "provider": "public_crypto_closed_candle_cache",
                "created_at": "2026-05-23T01:00:00Z",
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "summary.json").write_text(
        json.dumps({"return_pct": "4.25", "trade_count": 3}),
        encoding="utf-8",
    )
    payload = dashboard_payload(
        {"widgets": ["portfolio_summary", "data_freshness"], "template": "Local Default"},
        market_cache={
            "status": {
                "source": "binance_public",
                "state": "live",
                "last_update": "2026-05-23T00:00:00Z",
            },
            "rows": [{"symbol": "BTCUSDT", "chg_pct": "1.5"}],
        },
        paper_state={
            "account": {
                "mode": "paper",
                "cash": "100000.00",
                "equity": "100500.00",
                "updated_at": "2026-05-23T00:05:00Z",
            },
            "positions": {},
            "orders": [],
            "fills": [],
        },
        crypto_detail_cache={
            "status": {
                "source": "binance_public",
                "state": "live",
                "last_update": "2026-05-23T00:00:30Z",
                "symbol": "BTCUSDT",
                "timeframe": "15m",
            },
            "trades": [{"trade_id": "t1"}],
            "candles": [{"open": "100", "high": "110", "low": "95", "close": "108"}],
        },
        portfolio_state={
            "active_portfolio_id": "portfolio-local",
            "updated_at": "2026-05-23T00:06:00Z",
            "portfolios": {
                "portfolio-local": {
                    "source": "manual",
                    "updated_at": "2026-05-23T00:06:00Z",
                    "positions": [
                        {
                            "symbol": "BTCUSDT",
                            "quantity": "0.5",
                            "last_price": "68000",
                            "sector": "Crypto",
                        }
                    ],
                    "transactions": [{"transaction_id": "tx-1"}],
                }
            },
        },
        news_cache={
            "fetched_at": "2026-05-23T00:07:00Z",
            "items": [
                {"source": "Federal Reserve", "alert": False},
                {"source": "Federal Reserve", "alert": True},
            ],
        },
        provider_state={
            "generated_at": "2026-05-23T00:08:00Z",
            "summary": {
                "active": 2,
                "stale_cache": 1,
                "key_required": 1,
                "plan_required": 0,
                "disabled_by_safety": 1,
            },
            "freshness_strip": [
                {
                    "label": "Binance Spot public market data",
                    "state": "active",
                    "message": "Provider cache is within TTL.",
                }
            ],
            "providers": [
                {
                    "label": "DBnomics public macro data",
                    "coverage": ["macro"],
                    "auth_mode": "no-key",
                    "health": {"state": "unavailable"},
                },
                {
                    "label": "FRED economic data",
                    "coverage": ["macro"],
                    "auth_mode": "optional-local-key",
                    "health": {"state": "key_required"},
                },
            ],
        },
        artifact_root=tmp_path,
    )

    panels = {panel["panel_id"]: panel for panel in payload["panels"]}

    assert panels["provider_freshness"]["metrics"][0]["value"] == "2"
    assert panels["market_pulse"]["metrics"][1]["value"] == "1"
    assert panels["portfolio"]["metrics"][0]["value"] == "34000.00"
    assert panels["news"]["metrics"][0]["value"] == "2"
    assert panels["backtests"]["rows"][0]["label"] == "bt-route-state"
    assert panels["macro_setup"]["metrics"][0]["value"] == "1"
    assert "Not connected" not in json.dumps(payload)


def test_dashboard_api_saves_layout_and_applies_template(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())

    initial = client.get("/api/dashboard")
    saved = client.post(
        "/api/dashboard/layout",
        json={
            "widgets": ["crypto_markets", "not-a-widget", "watchlist", "crypto_markets"],
            "template": "Manual",
            "alerts_read": False,
        },
    )
    layout_path = tmp_path / "workspace_layouts" / "dashboard.json"

    assert initial.status_code == 200
    assert saved.status_code == 200
    assert saved.json()["widgets"] == ["crypto_markets", "watchlist"]
    assert layout_path.is_file()
    saved_layout = json.loads(layout_path.read_text(encoding="utf-8"))
    assert saved_layout["widgets"] == ["crypto_markets", "watchlist"]

    refused = client.post("/api/dashboard/reset", json={"template": "Crypto Trader"})
    assert refused.status_code == 400
    assert "confirm" in refused.json()["detail"]

    reset = client.post(
        "/api/dashboard/reset", json={"template": "Crypto Trader", "confirm": True}
    )

    assert reset.status_code == 200
    assert reset.json()["template"] == "Crypto Trader"
    assert "working_orders" in reset.json()["widgets"]
    reset_layout = json.loads(layout_path.read_text(encoding="utf-8"))
    assert reset_layout["widgets"] == [
        "crypto_markets",
        "crypto_ticker",
        "watchlist",
        "open_positions",
        "working_orders",
        "trade_tape",
    ]
