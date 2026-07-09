from pathlib import Path

from fastapi.testclient import TestClient

from src.local_terminal import server
from src.local_terminal.markets import default_markets_layout, markets_payload
from src.local_terminal.research_lineage import enrich_source_coverage_row
from src.local_terminal.storage import LocalStateStore


REQUIRED_MATRIX_FIELDS = {
    "asset_family",
    "runtime_role",
    "provider_id",
    "auth_mode",
    "state",
    "cache_path",
    "retrieved_at",
    "row_count",
    "freshness_ttl_seconds",
    "docs_url",
    "quote_semantics",
    "gated_reason",
    "safe_action_id",
    "next_safe_action",
    "markets_source_row_id",
    "markets_source_row_hash",
    "research_context_eligible",
    "backtest_data_eligible",
    "context_only",
    "live_action_enabled",
}


def _matrix_by_role(rows: list[dict[str, object]]) -> dict[tuple[str, str], dict[str, object]]:
    return {
        (str(row["asset_family"]), str(row["runtime_role"])): row
        for row in rows
    }


def test_markets_payload_source_coverage_matrix_shape_and_semantics() -> None:
    payload = markets_payload(default_markets_layout(), {}, refresh=False)
    matrix = payload["source_coverage_matrix"]
    by_role = _matrix_by_role(matrix)

    assert len(matrix) >= 15
    assert all(REQUIRED_MATRIX_FIELDS == set(row) for row in matrix)
    assert len({str(row["markets_source_row_id"]) for row in matrix}) == len(matrix)
    assert all(len(str(row["markets_source_row_hash"])) == 64 for row in matrix)
    assert all(row["research_context_eligible"] is True for row in matrix)
    assert all(row["backtest_data_eligible"] is False for row in matrix)
    assert all(row["live_action_enabled"] is False for row in matrix)
    assert {
        "Stocks",
        "ETF",
        "FX",
        "Commodities",
        "Indexes",
        "Regional",
        "Bonds/Rates",
    } <= {str(row["asset_family"]) for row in matrix}
    assert by_role[("Stocks", "quote_watchlist")]["auth_mode"] == "optional_local_key"
    assert by_role[("Stocks", "quote_watchlist")]["gated_reason"] == "local_secret_required"
    assert by_role[("Stocks", "quote_watchlist")]["quote_semantics"] == "quote_not_orderable"
    assert by_role[("Stocks", "quote_watchlist")]["context_only"] is False
    assert by_role[("Stocks", "fundamental_frames")]["provider_id"] == (
        "sec_xbrl_frames_public"
    )
    assert by_role[("Stocks", "fundamental_frames")]["auth_mode"] == "public_no_key"
    assert by_role[("Stocks", "fundamental_frames")]["quote_semantics"] == "not_quote"
    assert by_role[("Stocks", "fundamental_frames")]["context_only"] is True
    assert by_role[("Stocks", "symbol_directory")]["provider_id"] == (
        "nasdaq_trader_symbol_directory_public"
    )
    assert by_role[("Stocks", "symbol_directory")]["auth_mode"] == "public_no_key"
    assert by_role[("Stocks", "symbol_directory")]["quote_semantics"] == "not_quote"
    assert by_role[("Stocks", "symbol_directory")]["safe_action_id"] == (
        "markets_nasdaq_symbol_directory_refresh"
    )
    assert by_role[("Stocks", "symbol_directory")]["context_only"] is True
    assert by_role[("Stocks", "identifier_mapping")]["provider_id"] == (
        "openfigi_identifier_mapping_public"
    )
    assert by_role[("Stocks", "identifier_mapping")]["auth_mode"] == "public_no_key"
    assert by_role[("Stocks", "identifier_mapping")]["quote_semantics"] == "not_quote"
    assert by_role[("Stocks", "identifier_mapping")]["safe_action_id"] == (
        "markets_openfigi_mapping_refresh"
    )
    assert by_role[("Stocks", "identifier_mapping")]["context_only"] is True
    assert by_role[("ETF", "quote_watchlist")]["auth_mode"] == "optional_local_key"
    assert by_role[("ETF", "fund_registry")]["quote_semantics"] == "reference_only"
    assert by_role[("ETF", "fund_registry")]["context_only"] is True
    assert by_role[("FX", "eur_reference_rates")]["quote_semantics"] == "reference_only"
    assert by_role[("FX", "quote_watchlist")]["auth_mode"] == "optional_local_key"
    assert by_role[("FX", "quote_watchlist")]["gated_reason"] == "local_secret_required"
    assert by_role[("FX", "quote_watchlist")]["quote_semantics"] == "quote_not_orderable"
    assert by_role[("FX", "quote_watchlist")]["safe_action_id"] == (
        "markets_fx_quote_watchlist_refresh"
    )
    assert by_role[("Multi-Asset", "quote_watchlist_secondary")]["provider_id"] == (
        "twelve_data_quote_optional_key"
    )
    assert by_role[("Multi-Asset", "quote_watchlist_secondary")]["auth_mode"] == (
        "optional_local_key"
    )
    assert by_role[("Multi-Asset", "quote_watchlist_secondary")]["safe_action_id"] == (
        "markets_twelve_data_quote_watchlist_refresh"
    )
    assert by_role[("Multi-Asset", "quote_watchlist_secondary")]["quote_semantics"] == (
        "quote_not_orderable"
    )
    assert by_role[("Stocks", "equity_quote_watchlist_secondary")]["provider_id"] == (
        "finnhub_equity_quote_optional_key"
    )
    assert by_role[("Stocks", "equity_quote_watchlist_secondary")]["auth_mode"] == (
        "optional_local_key"
    )
    assert by_role[("Stocks", "equity_quote_watchlist_secondary")][
        "safe_action_id"
    ] == "markets_finnhub_quote_watchlist_refresh"
    assert by_role[("Stocks", "equity_quote_watchlist_secondary")][
        "quote_semantics"
    ] == "quote_not_orderable"
    assert by_role[("Stocks", "stock_quote_watchlist_tertiary")]["provider_id"] == (
        "fmp_stock_quote_optional_key"
    )
    assert by_role[("Stocks", "stock_quote_watchlist_tertiary")]["auth_mode"] == (
        "optional_local_key"
    )
    assert by_role[("Stocks", "stock_quote_watchlist_tertiary")][
        "safe_action_id"
    ] == "markets_fmp_quote_watchlist_refresh"
    assert by_role[("Stocks", "stock_quote_watchlist_tertiary")][
        "quote_semantics"
    ] == "quote_not_orderable"
    assert by_role[("Multi-Asset", "international_delayed_quote_snapshot")][
        "provider_id"
    ] == "moex_iss_delayed_quote_snapshot"
    assert by_role[("Multi-Asset", "international_delayed_quote_snapshot")][
        "auth_mode"
    ] == "public_no_key"
    assert by_role[("Multi-Asset", "international_delayed_quote_snapshot")][
        "quote_semantics"
    ] == "quote_not_orderable"
    assert by_role[("Multi-Asset", "international_delayed_quote_snapshot")][
        "safe_action_id"
    ] == "markets_moex_quote_snapshot_refresh"
    assert by_role[("Stocks", "twse_daily_quote_snapshot")]["provider_id"] == (
        "twse_openapi_daily_quote_snapshot"
    )
    assert by_role[("Stocks", "twse_daily_quote_snapshot")]["auth_mode"] == "public_no_key"
    assert by_role[("Stocks", "twse_daily_quote_snapshot")]["quote_semantics"] == (
        "quote_not_orderable"
    )
    assert by_role[("Stocks", "twse_daily_quote_snapshot")]["safe_action_id"] == (
        "markets_twse_quote_snapshot_refresh"
    )
    assert by_role[("FX", "usd_reference_rates")]["provider_id"] == (
        "federal_reserve_h10_ddp_public"
    )
    assert by_role[("FX", "usd_reference_rates")]["quote_semantics"] == "reference_only"
    assert by_role[("FX", "cad_reference_rates")]["provider_id"] == (
        "bank_of_canada_valet_fx_reference_public"
    )
    assert by_role[("FX", "cad_reference_rates")]["auth_mode"] == "public_no_key"
    assert by_role[("FX", "cad_reference_rates")]["quote_semantics"] == "reference_only"
    assert by_role[("FX", "cad_reference_rates")]["safe_action_id"] == (
        "markets_fx_refresh"
    )
    assert by_role[("Commodities", "monthly_reference_prices")]["quote_semantics"] == (
        "reference_only"
    )
    assert by_role[("Commodities", "positioning_context")]["provider_id"] == (
        "cftc_cot_legacy_public"
    )
    assert by_role[("Commodities", "positioning_context")]["auth_mode"] == "public_no_key"
    assert by_role[("Commodities", "positioning_context")]["quote_semantics"] == "not_quote"
    assert by_role[("Commodities", "positioning_context")]["safe_action_id"] == (
        "markets_cftc_cot_refresh"
    )
    assert by_role[("Indexes", "macro_context")]["quote_semantics"] == "not_quote"
    assert by_role[("Regional", "macro_context")]["quote_semantics"] == "not_quote"
    assert by_role[("Bonds/Rates", "yield_curve")]["safe_action_id"] == (
        "markets_rates_refresh"
    )
    assert by_role[("Bonds/Rates", "overnight_reference_rate")]["provider_id"] == (
        "nyfed_sofr_public"
    )
    assert by_role[("Bonds/Rates", "overnight_reference_rate")]["quote_semantics"] == (
        "reference_only"
    )
    assert "public_no_key" in {str(row["auth_mode"]) for row in matrix}
    assert "optional_local_key" in {str(row["auth_mode"]) for row in matrix}
    matrix_text = str(matrix).lower()
    assert "offline_fixture" not in matrix_text
    assert "mock" not in matrix_text
    assert "api_key" not in matrix_text
    assert "broker" not in matrix_text
    assert "real_order" not in matrix_text


def test_markets_quote_reference_coverage_summarizes_non_orderable_lanes() -> None:
    payload = markets_payload(default_markets_layout(), {}, refresh=False)
    coverage = payload["quote_reference_coverage"]
    summary = coverage["summary"]
    quote_lanes = coverage["quote_lanes"]
    reference_lanes = coverage["reference_lanes"]

    assert coverage["mode"] == "read_only_markets_quote_reference_coverage"
    assert summary["source_row_count"] == len(payload["source_coverage_matrix"])
    assert summary["quote_lane_count"] == len(quote_lanes)
    assert summary["quote_lane_count"] >= 6
    assert summary["public_quote_lane_count"] >= 2
    assert summary["optional_quote_lane_count"] >= 3
    assert summary["reference_lane_count"] == len(reference_lanes)
    assert summary["executable_quote_lane_count"] == 0
    assert summary["orderable_lane_count"] == 0
    assert summary["live_action_enabled_count"] == 0
    assert summary["coverage_status"] == "partial_non_orderable_quotes"
    assert coverage["snapshot_board"]["mode"] == "read_only_markets_quote_snapshot_board"
    assert coverage["snapshot_board"]["summary"]["snapshot_lane_count"] == len(
        quote_lanes
    )
    assert coverage["snapshot_board"]["summary"]["orderable_snapshot_count"] == 0
    assert coverage["snapshot_board"]["summary"]["executable_snapshot_count"] == 0
    assert coverage["snapshot_board"]["rows"]
    assert all(row["orderable"] is False for row in coverage["snapshot_board"]["rows"])
    assert all(row["executable"] is False for row in coverage["snapshot_board"]["rows"])
    assert all(
        row["preflight_endpoint"].startswith("/api/agent-actions/")
        for row in coverage["snapshot_board"]["rows"]
    )
    assert all(row["quote_semantics"] == "quote_not_orderable" for row in quote_lanes)
    assert all(row["quote_semantics"] == "reference_only" for row in reference_lanes)
    assert {
        "moex_iss_delayed_quote_snapshot",
        "twse_openapi_daily_quote_snapshot",
        "finnhub_equity_quote_optional_key",
        "fmp_stock_quote_optional_key",
    } <= {row["provider_id"] for row in quote_lanes}
    assert {
        "markets_moex_quote_snapshot_refresh",
        "markets_twse_quote_snapshot_refresh",
        "markets_finnhub_quote_watchlist_refresh",
        "markets_fmp_quote_watchlist_refresh",
    } <= {row["action_id"] for row in coverage["recommended_actions"]}
    assert coverage["safety"]["read_only"] is True
    assert coverage["safety"]["uses_existing_source_coverage_matrix"] is True
    assert coverage["safety"]["external_provider_calls"] is False
    assert coverage["safety"]["writes_local_artifacts"] is False
    assert coverage["safety"]["secret_values"] is False
    assert coverage["safety"]["orderable_quotes"] is False
    assert coverage["safety"]["live_orders"] is False


def test_markets_source_coverage_matrix_row_identity_is_stable() -> None:
    first = markets_payload(default_markets_layout(), {}, refresh=False)[
        "source_coverage_matrix"
    ]
    second = markets_payload(default_markets_layout(), {}, refresh=False)[
        "source_coverage_matrix"
    ]

    assert [
        (row["markets_source_row_id"], row["markets_source_row_hash"])
        for row in first
    ] == [
        (row["markets_source_row_id"], row["markets_source_row_hash"])
        for row in second
    ]


def test_markets_source_coverage_matrix_row_hash_tracks_source_contract_fields() -> None:
    row = next(
        row
        for row in markets_payload(default_markets_layout(), {}, refresh=False)[
            "source_coverage_matrix"
        ]
        if row["asset_family"] == "FX" and row["runtime_role"] == "eur_reference_rates"
    )
    changed = {**row, "cache_path": "market_data/fx/ecb/changed_cache.json"}

    assert enrich_source_coverage_row(row)["markets_source_row_hash"] == row[
        "markets_source_row_hash"
    ]
    assert enrich_source_coverage_row(changed)["markets_source_row_id"] == row[
        "markets_source_row_id"
    ]
    assert enrich_source_coverage_row(changed)["markets_source_row_hash"] != row[
        "markets_source_row_hash"
    ]
    assert enrich_source_coverage_row(changed)["backtest_data_eligible"] is False
    assert enrich_source_coverage_row(changed)["live_action_enabled"] is False


def test_markets_source_coverage_matrix_reuses_provider_cache_state() -> None:
    payload = markets_payload(
        default_markets_layout(),
        {},
        research_data={
            "sec_frames": {
                "status": {
                    "state": "live",
                    "provider_id": "sec_xbrl_frames_public",
                    "last_update": "2026-05-25T00:00:00Z",
                    "cache_path": (
                        "market_data/fundamentals/sec/frames/us-gaap/Assets/USD/"
                        "CY2023Q4I.json"
                    ),
                },
                "summary": {"row_count": 2, "tag": "Assets", "period": "CY2023Q4I"},
                "rows": [
                    {"cik": "0000320193", "entity_name": "Apple Inc.", "value": "1"},
                    {"cik": "0000789019", "entity_name": "MICROSOFT CORP", "value": "2"},
                ],
            },
            "macro": {
                "status": {
                    "state": "live",
                    "provider_id": "bls_public_macro",
                    "last_update": "2026-05-25T00:00:00Z",
                    "cache_path": "market_data/macro/bls/latest_series.json",
                    "docs_url": "https://www.bls.gov/developers/api_signature_v2.htm",
                },
                "summary": {"provider_count": 1},
                "series": [{"series_id": "CPIAUCSL", "latest_value": "320.0"}],
            },
        },
        rates_data={
            "treasury": {
                "status": {
                    "state": "live",
                    "provider_id": "us_treasury_yield_public",
                    "last_update": "2026-05-25T00:00:00Z",
                    "cache_path": "market_data/rates/treasury/daily_yield_curve.json",
                },
                "latest": {
                    "date": "2026-05-22",
                    "tenors": [
                        {"tenor": "2Y", "rate": "4.02", "unit": "percent"},
                        {"tenor": "10Y", "rate": "4.57", "unit": "percent"},
                    ],
                },
            },
            "sofr": {
                "status": {
                    "state": "live",
                    "provider_id": "nyfed_sofr_public",
                    "last_update": "2026-05-25T00:00:00Z",
                    "cache_path": "market_data/rates/nyfed/sofr.json",
                },
                "summary": {"row_count": 2, "latest_date": "2026-05-22", "rate": "3.52"},
                "rows": [{"date": "2026-05-21"}, {"date": "2026-05-22"}],
            }
        },
        fx_data={
            "ecb": {
                "status": {
                    "state": "live",
                    "provider_id": "ecb_fx_reference_public",
                    "last_update": "2026-05-25T00:00:00Z",
                    "cache_path": "market_data/fx/ecb/eurofxref_daily.json",
                },
                "summary": {"row_count": 2, "date": "2026-05-23"},
            },
            "h10": {
                "status": {
                    "state": "live",
                    "provider_id": "federal_reserve_h10_ddp_public",
                    "last_update": "2026-05-25T00:00:00Z",
                    "cache_path": (
                        "market_data/fx/federal_reserve/h10_reference_rates.json"
                    ),
                },
                "summary": {"row_count": 5, "date": "2026-05-23"},
            },
            "boc": {
                "status": {
                    "state": "live",
                    "provider_id": "bank_of_canada_valet_fx_reference_public",
                    "last_update": "2026-05-25T00:00:00Z",
                    "cache_path": (
                        "market_data/fx/bank_of_canada/valet_fx_reference_rates.json"
                    ),
                },
                "summary": {"row_count": 5, "date": "2026-05-23"},
            }
        },
        fx_quote_data={
            "status": {
                "state": "live",
                "provider_id": "alphavantage_global_quote_optional_key",
                "source": "alphavantage_currency_exchange_rate",
                "last_update": "2026-05-25T00:00:00Z",
                "cache_path": (
                    "market_data/fx/alphavantage/currency_exchange/EURUSD.json"
                ),
            },
            "summary": {
                "pair": "EUR/USD",
                "pairs": "EUR/USD,USD/JPY,GBP/USD",
                "row_count": 3,
                "requested_count": 3,
            },
            "quotes": [
                {"pair": "EUR/USD", "rate": "1.1"},
                {"pair": "USD/JPY", "rate": "150"},
                {"pair": "GBP/USD", "rate": "1.3"},
            ],
        },
        commodity_data={
            "world_bank": {
                "status": {
                    "state": "live",
                    "provider_id": "world_bank_commodity_monthly_public",
                    "last_update": "2026-05-25T00:00:00Z",
                    "cache_path": (
                        "market_data/commodities/world_bank/pink_sheet_monthly.json"
                    ),
                },
                "summary": {"row_count": 3, "period": "2026M04"},
            },
            "cftc": {
                "status": {
                    "state": "live",
                    "provider_id": "cftc_cot_legacy_public",
                    "last_update": "2026-05-25T00:00:00Z",
                    "cache_path": "market_data/commodities/cftc/cot_legacy_futures.json",
                },
                "summary": {"row_count": 4, "report_date": "2026-05-19"},
                "rows": [
                    {"contract": "Gold", "report_date": "2026-05-19"},
                    {"contract": "Wheat SRW", "report_date": "2026-05-19"},
                    {"contract": "WTI crude", "report_date": "2026-05-19"},
                    {"contract": "Copper", "report_date": "2026-05-19"},
                ],
            }
        },
    )
    by_role = _matrix_by_role(payload["source_coverage_matrix"])

    assert by_role[("Bonds/Rates", "yield_curve")]["row_count"] == 2
    assert by_role[("Bonds/Rates", "yield_curve")]["state"] == "live"
    assert by_role[("Bonds/Rates", "yield_curve")]["freshness_ttl_seconds"] == 86400
    assert by_role[("Bonds/Rates", "overnight_reference_rate")]["row_count"] == 2
    assert by_role[("Bonds/Rates", "overnight_reference_rate")]["state"] == "live"
    assert by_role[("Bonds/Rates", "overnight_reference_rate")]["cache_path"] == (
        "market_data/rates/nyfed/sofr.json"
    )
    assert by_role[("FX", "eur_reference_rates")]["row_count"] == 2
    assert by_role[("FX", "eur_reference_rates")]["cache_path"] == (
        "market_data/fx/ecb/eurofxref_daily.json"
    )
    assert by_role[("FX", "usd_reference_rates")]["row_count"] == 5
    assert by_role[("FX", "usd_reference_rates")]["cache_path"] == (
        "market_data/fx/federal_reserve/h10_reference_rates.json"
    )
    assert by_role[("FX", "cad_reference_rates")]["row_count"] == 5
    assert by_role[("FX", "cad_reference_rates")]["cache_path"] == (
        "market_data/fx/bank_of_canada/valet_fx_reference_rates.json"
    )
    assert by_role[("FX", "quote_watchlist")]["row_count"] == 3
    assert by_role[("FX", "quote_watchlist")]["state"] == "live"
    assert by_role[("FX", "quote_watchlist")]["quote_semantics"] == "quote_not_orderable"
    assert by_role[("Stocks", "fundamental_frames")]["row_count"] == 2
    assert by_role[("Stocks", "fundamental_frames")]["state"] == "live"
    assert by_role[("Commodities", "monthly_reference_prices")]["row_count"] == 3
    assert by_role[("Commodities", "monthly_reference_prices")][
        "freshness_ttl_seconds"
    ] == 604800
    assert by_role[("Commodities", "positioning_context")]["row_count"] == 4
    assert by_role[("Commodities", "positioning_context")]["cache_path"] == (
        "market_data/commodities/cftc/cot_legacy_futures.json"
    )
    assert by_role[("Indexes", "macro_context")]["provider_id"] == "bls_public_macro"
    assert by_role[("Indexes", "macro_context")]["safe_action_id"] == (
        "markets_macro_refresh"
    )
    assert by_role[("Regional", "macro_context")]["row_count"] == 1


def test_markets_source_coverage_matrix_marks_fred_macro_context_optional_key() -> None:
    payload = markets_payload(
        default_markets_layout(),
        {},
        research_data={
            "macro": {
                "status": {
                    "state": "key_required",
                    "provider_id": "fred_optional_local_key",
                    "last_update": "not refreshed",
                    "cache_path": "market_data/macro/fred/DGS10.json",
                    "docs_url": "https://fred.stlouisfed.org/docs/api/fred/",
                },
                "summary": {
                    "series_count": 0,
                    "primary_provider": "fred_optional_local_key",
                },
                "series": [],
            },
        },
    )
    by_role = _matrix_by_role(payload["source_coverage_matrix"])

    assert by_role[("Indexes", "macro_context")]["provider_id"] == (
        "fred_optional_local_key"
    )
    assert by_role[("Indexes", "macro_context")]["auth_mode"] == "optional_local_key"
    assert by_role[("Indexes", "macro_context")]["gated_reason"] == (
        "local_secret_required"
    )
    assert by_role[("Indexes", "macro_context")]["safe_action_id"] == (
        "markets_fred_refresh"
    )
    assert by_role[("Regional", "macro_context")]["auth_mode"] == "optional_local_key"


def test_markets_source_coverage_matrix_marks_bea_regional_context_optional_key() -> None:
    payload = markets_payload(
        default_markets_layout(),
        {},
        research_data={
            "macro": {
                "status": {
                    "state": "key_required",
                    "provider_id": "bea_regional_optional_key",
                    "last_update": "not refreshed",
                    "cache_path": "market_data/regional/bea/SAGDP9N_LINE1_STATE.json",
                    "docs_url": "https://apps.bea.gov/api/_pdf/bea_web_service_api_user_guide.pdf",
                },
                "summary": {
                    "series_count": 0,
                    "primary_provider": "bea_regional_optional_key",
                },
                "series": [],
            },
        },
    )
    by_role = _matrix_by_role(payload["source_coverage_matrix"])

    assert by_role[("Indexes", "macro_context")]["provider_id"] == (
        "bea_regional_optional_key"
    )
    assert by_role[("Indexes", "macro_context")]["auth_mode"] == "optional_local_key"
    assert by_role[("Indexes", "macro_context")]["gated_reason"] == (
        "local_secret_required"
    )
    assert by_role[("Indexes", "macro_context")]["safe_action_id"] == (
        "markets_bea_refresh"
    )
    assert by_role[("Regional", "macro_context")]["auth_mode"] == "optional_local_key"


def test_markets_source_coverage_matrix_marks_census_regional_context_optional_key() -> None:
    payload = markets_payload(
        default_markets_layout(),
        {},
        research_data={
            "macro": {
                "status": {
                    "state": "key_required",
                    "provider_id": "census_api_optional_key",
                    "last_update": "not refreshed",
                    "cache_path": "market_data/regional/census/acs5_profile_state_2023.json",
                    "docs_url": "https://api.census.gov/data/2023/acs/acs5/profile.html",
                },
                "summary": {
                    "series_count": 0,
                    "primary_provider": "census_api_optional_key",
                },
                "series": [],
            },
        },
    )
    by_role = _matrix_by_role(payload["source_coverage_matrix"])

    assert by_role[("Indexes", "macro_context")]["provider_id"] == (
        "census_api_optional_key"
    )
    assert by_role[("Indexes", "macro_context")]["auth_mode"] == "optional_local_key"
    assert by_role[("Indexes", "macro_context")]["gated_reason"] == (
        "local_secret_required"
    )
    assert by_role[("Indexes", "macro_context")]["safe_action_id"] == (
        "markets_census_refresh"
    )
    assert by_role[("Regional", "macro_context")]["auth_mode"] == "optional_local_key"


def test_markets_api_exposes_source_coverage_matrix_without_secret_store(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())

    response = client.get("/api/markets")

    assert response.status_code == 200
    payload = response.json()
    assert payload["source_coverage_matrix"]
    assert all(REQUIRED_MATRIX_FIELDS == set(row) for row in payload["source_coverage_matrix"])
    assert not (tmp_path / "settings" / "local_secrets.json").exists()
    response_text = response.text.lower()
    assert "offline_fixture" not in response_text
    assert "api_key" not in response_text
    assert "real_order" not in response_text


def test_markets_quote_reference_coverage_api_is_read_only_and_secret_free(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())

    response = client.get("/api/markets/quote-reference-coverage")

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "read_only_markets_quote_reference_coverage"
    assert payload["summary"]["quote_lane_count"] >= 6
    assert payload["summary"]["executable_quote_lane_count"] == 0
    assert payload["summary"]["orderable_lane_count"] == 0
    assert payload["safety"]["external_provider_calls"] is False
    assert payload["safety"]["writes_local_artifacts"] is False
    assert not (tmp_path / "settings" / "local_secrets.json").exists()
    response_text = response.text.lower()
    assert "offline_fixture" not in response_text
    assert "api_key" not in response_text
    assert "real_order" not in response_text


def test_markets_quote_snapshot_board_api_is_read_only_and_secret_free(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())

    response = client.get("/api/markets/quote-snapshot-board")

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "read_only_markets_quote_snapshot_board"
    assert payload["summary"]["snapshot_lane_count"] >= 6
    assert payload["summary"]["non_orderable_snapshot_count"] == payload["summary"][
        "snapshot_lane_count"
    ]
    assert payload["summary"]["orderable_snapshot_count"] == 0
    assert payload["summary"]["executable_snapshot_count"] == 0
    assert payload["rows"]
    assert payload["rows"][0]["preflight_endpoint"].startswith("/api/agent-actions/")
    assert all(row["orderable"] is False for row in payload["rows"])
    assert all(row["live_action_enabled"] is False for row in payload["rows"])
    assert payload["safety"]["read_only"] is True
    assert payload["safety"]["external_provider_calls"] is False
    assert payload["safety"]["writes_local_artifacts"] is False
    assert payload["safety"]["secret_values"] is False
    assert not (tmp_path / "settings" / "local_secrets.json").exists()
    response_text = response.text.lower()
    assert "offline_fixture" not in response_text
    assert "api_key" not in response_text
    assert "real_order" not in response_text
