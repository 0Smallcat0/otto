import os
from pathlib import Path

from fastapi.testclient import TestClient

from otto.local_terminal import server
from otto.local_terminal.storage import LocalStateStore, _relative


def test_local_state_store_writes_repo_local_json(tmp_path: Path) -> None:
    store = LocalStateStore(root=tmp_path)

    settings = store.write_settings(
        {
            "theme": "dark",
            "default_route": "markets",
            "compact_mode": True,
            "data_refresh_seconds": 30,
        }
    )
    profile = store.write_profile(
        {
            "display_name": "Research Desk",
            "theme": "dark",
            "default_route": "profile",
            "billing_enabled": True,
        }
    )
    layout = store.write_layout(
        {
            "active_route": "crypto",
            "sidebar_collapsed": True,
            "focus_mode": True,
            "panel_order": ["primary", "side"],
        }
    )

    assert settings["default_route"] == "markets"
    assert profile["display_name"] == "Research Desk"
    assert profile["billing_enabled"] is False
    assert layout["active_route"] == "crypto"

    state = store.read_state()
    assert state["storage"] == {
        "settings": "settings/local_settings.json",
        "profile": "settings/local_profile.json",
        "layout": "workspace_layouts/default.json",
        "dashboard": "workspace_layouts/dashboard.json",
        "markets": "workspace_layouts/markets.json",
        "news": "workspace_layouts/news.json",
        "market_cache": "market_data/crypto_latest.json",
        "crypto_detail_cache": "market_data/crypto/BTCUSDT/15m.json",
        "news_cache": "artifacts/news/news_cache.json",
        "sec_fundamentals_cache": "market_data/fundamentals/sec/0000320193/companyfacts.json",
        "sec_company_tickers_cache": "market_data/fundamentals/sec/company_tickers.json",
        "sec_company_submissions_cache": (
            "market_data/fundamentals/sec/0000320193/submissions.json"
        ),
        "sec_company_submissions_watchlist_caches": [
            "market_data/fundamentals/sec/0000320193/submissions.json",
            "market_data/fundamentals/sec/0000789019/submissions.json",
            "market_data/fundamentals/sec/0001045810/submissions.json",
        ],
        "sec_xbrl_frames_cache": (
            "market_data/fundamentals/sec/frames/us-gaap/Assets/USD/CY2023Q4I.json"
        ),
        "dbnomics_macro_cache": (
            "market_data/macro/dbnomics/INSEE/IPC-2015/"
            "A.IPC.SO.00.00.INDICE.ENSEMBLE.FE.SO.BRUT.2015.FALSE.json"
        ),
        "fred_macro_cache": "market_data/macro/fred/DGS10.json",
        "bls_macro_cache": "market_data/macro/bls/latest_series.json",
        "eurostat_hicp_cache": "market_data/macro/eurostat/hicp_ea20_cp00_i15.json",
        "nasdaq_trader_symbol_directory_cache": (
            "market_data/reference/nasdaq_trader/symbol_directory.json"
        ),
        "openfigi_mapping_cache": "market_data/reference/openfigi/mapping.json",
        "bea_regional_cache": "market_data/regional/bea/SAGDP9N_LINE1_STATE.json",
        "census_acs_profile_cache": (
            "market_data/regional/census/acs5_profile_state_2023.json"
        ),
        "alpha_vantage_equity_quote_cache": (
            "market_data/equities/alphavantage/global_quote/AAPL.json"
        ),
        "alpha_vantage_etf_quote_cache": (
            "market_data/equities/alphavantage/global_quote/SPY.json"
        ),
        "alpha_vantage_fx_quote_cache": (
            "market_data/fx/alphavantage/currency_exchange/EURUSD.json"
        ),
        "twelve_data_quote_cache": "market_data/quotes/twelve_data/AAPL.json",
        "finnhub_quote_cache": "market_data/quotes/finnhub/AAPL.json",
        "fmp_quote_cache": "market_data/quotes/fmp/AAPL.json",
        "stooq_quote_cache": "market_data/quotes/stooq/AAPLUS.json",
        "yahoo_quote_cache": "market_data/quotes/yahoo/AAPL.json",
        "moex_quote_cache": "market_data/quotes/moex/SBER.json",
        "twse_quote_cache": "market_data/quotes/twse/2330.json",
        "treasury_rates_cache": "market_data/rates/treasury/daily_yield_curve.json",
        "nyfed_sofr_cache": "market_data/rates/nyfed/sofr.json",
        "ecb_fx_cache": "market_data/fx/ecb/eurofxref_daily.json",
        "federal_reserve_h10_fx_cache": (
            "market_data/fx/federal_reserve/h10_reference_rates.json"
        ),
        "bank_of_canada_fx_cache": (
            "market_data/fx/bank_of_canada/valet_fx_reference_rates.json"
        ),
        "world_bank_commodity_cache": (
            "market_data/commodities/world_bank/pink_sheet_monthly.json"
        ),
        "cftc_cot_cache": "market_data/commodities/cftc/cot_legacy_futures.json",
        "eia_energy_cache": "market_data/commodities/eia/energy_series.json",
        "sec_fund_tickers_cache": "market_data/funds/sec/company_tickers_mf.json",
        "paper_state": "artifacts/paper/paper_state.json",
        "paper_history": "artifacts/paper/paper_history.json",
        "research_ledger": "artifacts/research/research_ledger.json",
        "portfolio_state": "artifacts/portfolio/portfolio_state.json",
        "chat_state": "artifacts/chat/chat_state.json",
        "algo_state": "artifacts/algo/algo_state.json",
        "algo_scan_artifacts": "artifacts/algo/scans",
        "nodes_state": "artifacts/workflows/nodes_state.json",
        "code_state": "artifacts/code_workspace/code_state.json",
        "quant_lab_state": "artifacts/quant_lab/quant_lab_state.json",
        "quantlib_state": "artifacts/quantlib/quantlib_state.json",
        "forum_state": "artifacts/forum/forum_state.json",
        "diagnostics_artifacts": "artifacts/diagnostics",
    }
    assert (tmp_path / "settings" / "local_settings.json").is_file()
    assert (tmp_path / "settings" / "local_profile.json").is_file()
    assert (tmp_path / "workspace_layouts" / "default.json").is_file()


def test_relative_normalizes_windows_extended_prefix(tmp_path: Path) -> None:
    if os.name != "nt":
        return
    path = Path(f"\\\\?\\{tmp_path}\\artifacts\\algo\\algo_state.json")

    assert _relative(path, tmp_path) == "artifacts/algo/algo_state.json"


def test_local_state_store_falls_back_from_invalid_json(tmp_path: Path) -> None:
    store = LocalStateStore(root=tmp_path)
    store.settings_path.parent.mkdir(parents=True)
    store.settings_path.write_text("{not-json", encoding="utf-8")

    settings = store.read_settings()

    assert settings["default_route"] == "dashboard"


def test_local_state_store_retries_transient_windows_replace_lock(
    tmp_path: Path, monkeypatch
) -> None:
    store = LocalStateStore(root=tmp_path)
    original_replace = Path.replace
    calls = {"count": 0}

    def flaky_replace(self: Path, target: Path) -> Path:
        if str(target).endswith("news_cache.json") and calls["count"] == 0:
            calls["count"] += 1
            raise PermissionError("temporary file lock")
        return original_replace(self, target)

    monkeypatch.setattr(Path, "replace", flaky_replace)

    store.write_news_cache({"items": []})

    assert calls["count"] == 1
    assert store.news_cache_path.is_file()


def test_local_state_store_removes_temp_file_after_replace_lock_exhaustion(
    tmp_path: Path, monkeypatch
) -> None:
    store = LocalStateStore(root=tmp_path)
    original_replace = Path.replace

    def locked_replace(self: Path, target: Path) -> Path:
        if str(target).endswith("news_cache.json"):
            raise PermissionError("persistent file lock")
        return original_replace(self, target)

    monkeypatch.setattr(Path, "replace", locked_replace)

    try:
        store.write_news_cache({"items": []})
    except PermissionError:
        pass
    else:
        raise AssertionError("persistent replace lock should propagate")

    assert not list(store.news_cache_path.parent.glob("news_cache.json.*.tmp"))


def test_local_state_store_sanitizes_tampered_profile_on_read(tmp_path: Path) -> None:
    store = LocalStateStore(root=tmp_path)
    store.profile_path.parent.mkdir(parents=True)
    store.profile_path.write_text(
        '{"billing_enabled": true, "private_api_required": true}',
        encoding="utf-8",
    )

    profile = store.read_profile()

    assert profile["billing_enabled"] is False
    assert profile["private_api_required"] is False


def test_local_state_api_saves_settings_profile_and_layout(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())

    settings_response = client.post(
        "/api/settings",
        json={
            "theme": "dark",
            "default_route": "unknown",
            "compact_mode": True,
            "data_refresh_seconds": 45,
        },
    )
    profile_response = client.post(
        "/api/profile",
        json={
            "display_name": "Research Desk",
            "theme": "dark",
            "default_route": "markets",
        },
    )
    layout_response = client.post(
        "/api/layouts/default",
        json={
            "active_route": "profile",
            "sidebar_collapsed": True,
            "focus_mode": True,
            "panel_order": ["primary"],
        },
    )

    assert settings_response.status_code == 200
    assert settings_response.json()["default_route"] == "dashboard"
    assert profile_response.status_code == 200
    assert profile_response.json()["private_api_required"] is False
    assert layout_response.status_code == 200
    assert layout_response.json()["active_route"] == "profile"
