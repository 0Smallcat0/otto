from pathlib import Path

from fastapi.testclient import TestClient

from otto.local_terminal import server
from otto.local_terminal.agent_contract import agent_operability_payload
from otto.local_terminal.provider_acquisition import provider_acquisition_gate_payload
from otto.local_terminal.storage import LocalStateStore


def _candidate_by_id(payload: dict[str, object]) -> dict[str, dict[str, object]]:
    candidates = payload["candidates"]
    assert isinstance(candidates, list)
    return {
        str(candidate["candidate_id"]): candidate
        for candidate in candidates
        if isinstance(candidate, dict)
    }


def test_provider_acquisition_gate_ranks_public_no_key_before_optional_keys() -> None:
    payload = provider_acquisition_gate_payload()
    candidates = _candidate_by_id(payload)

    assert payload["mode"] == "read_only_provider_acquisition_gate"
    assert payload["version"] == "m22-provider-acquisition-gate-v1"
    assert payload["docs_checked_at"] == "2026-06-01"
    assert payload["summary"]["next_candidate_id"] == ""
    assert payload["summary"]["approved_next_count"] == 0
    assert payload["summary"]["implemented_count"] == 16
    assert payload["summary"]["blocked_count"] == 5
    assert payload["summary"]["resume_state"] == "backlog_exhausted_needs_research"
    assert payload["summary"]["requires_official_research"] is True
    assert payload["summary"]["implementation_allowed"] is False
    assert payload["summary"]["public_no_key_count"] >= 5
    assert payload["resume_contract"]["implementation_allowed"] is False
    assert payload["resume_contract"]["requires_official_docs_refresh"] is True
    assert payload["resume_contract"]["implemented_or_blocked_count"] == (
        payload["summary"]["candidate_count"]
    )
    assert payload["resume_contract"]["next_safe_step"] == (
        "Run a new provider-entry research gate before implementation."
    )
    assert "official docs" in payload["resume_contract"]["anti_stall_rule"]
    closure = payload["quote_breadth_closure"]
    assert closure["mode"] == "non_live_quote_breadth_closure_v1"
    assert closure["status"] == "closed_until_new_official_provider_gate"
    assert closure["implementation_allowed"] is False
    assert closure["next_safe_action"] == (
        "Run a new official-doc provider-entry research gate before adapter work."
    )
    assert closure["non_live_scope"] == {
        "orderable_quotes": False,
        "executable_quotes": False,
        "broker_routing": False,
        "real_balances": False,
        "live_orders": False,
    }
    assert closure["provider_backlog"]["resume_state"] == (
        "backlog_exhausted_needs_research"
    )
    assert closure["provider_backlog"]["candidate_count"] == 21
    assert closure["provider_backlog"]["implemented_or_blocked_count"] == 21
    assert closure["provider_backlog"]["approved_next_count"] == 0
    assert closure["provider_backlog"]["blocked_count"] == 5
    assert closure["provider_backlog"]["blocked_market_data_gate_count"] == 5
    assert closure["provider_backlog"]["implemented_quote_lane_count"] >= 6
    assert set(closure["blocked_gate_ids"]) == {
        "cboe_delayed_quotes_gate",
        "iex_tops_market_data_gate",
        "nasdaq_data_link_dataset_gate",
        "jpx_jquants_market_data_gate",
        "yahoo_finance_market_data_gate",
    }
    assert "stooq_public_quote_snapshot" in closure["implemented_quote_candidate_ids"]
    assert "fmp_stock_quote_optional_key" in closure["implemented_quote_candidate_ids"]
    assert "orderable quote parity is outside" in closure["agent_rule"]
    assert "live_order" in closure["stop_gates"]
    assert payload["rules"]["public_no_key_first"] is True
    assert payload["rules"]["no_unused_key_hoarding"] is True

    sec_frames = candidates["sec_xbrl_frames_public"]
    assert sec_frames["status"] == "implemented_bounded_public_no_key"
    assert sec_frames["auth_mode"] == "public_no_key"
    assert sec_frames["quote_semantics"] == "not_quote"
    assert "sec.gov" in " ".join(sec_frames["official_docs"])

    fed_h10 = candidates["federal_reserve_h10_ddp_public"]
    assert fed_h10["status"] == "implemented_public_no_key_reference"
    assert fed_h10["auth_mode"] == "public_no_key"
    assert fed_h10["quote_semantics"] == "reference_only"

    eurostat = candidates["eurostat_hicp_public"]
    assert eurostat["status"] == "implemented_public_no_key_reference"
    assert eurostat["auth_mode"] == "public_no_key"
    assert eurostat["quote_semantics"] == "not_quote"
    assert eurostat["cache_policy"]["path"] == (
        "market_data/macro/eurostat/hicp_ea20_cp00_i15.json"
    )
    assert "Eurostat" in eurostat["implementation_gate"]

    boc = candidates["bank_of_canada_valet_fx_reference_public"]
    assert boc["status"] == "implemented_public_no_key_reference"
    assert boc["auth_mode"] == "public_no_key"
    assert boc["quote_semantics"] == "reference_only"
    assert boc["cache_policy"]["path"] == (
        "market_data/fx/bank_of_canada/valet_fx_reference_rates.json"
    )
    assert "Valet" in boc["implementation_gate"]

    nyfed_sofr = candidates["nyfed_sofr_public"]
    assert nyfed_sofr["status"] == "implemented_public_no_key_reference"
    assert nyfed_sofr["auth_mode"] == "public_no_key"
    assert nyfed_sofr["quote_semantics"] == "reference_only"
    assert nyfed_sofr["cache_policy"]["path"] == "market_data/rates/nyfed/sofr.json"

    cftc = candidates["cftc_cot_legacy_public"]
    assert cftc["status"] == "implemented_public_no_key_context"
    assert cftc["auth_mode"] == "public_no_key"
    assert cftc["quote_semantics"] == "not_quote"
    assert cftc["cache_policy"]["path"] == (
        "market_data/commodities/cftc/cot_legacy_futures.json"
    )
    assert "CFTC" in cftc["implementation_gate"]

    twelve_data = candidates["twelve_data_quote_optional_key"]
    assert twelve_data["status"] == "implemented_bounded_optional_key"
    assert twelve_data["auth_mode"] == "optional_local_key"
    assert twelve_data["quote_semantics"] == "quote_not_orderable"
    assert "twelvedata.com" in " ".join(twelve_data["official_docs"])

    finnhub = candidates["finnhub_equity_quote_optional_key"]
    assert finnhub["status"] == "implemented_bounded_optional_key"
    assert finnhub["auth_mode"] == "optional_local_key"
    assert finnhub["quote_semantics"] == "quote_not_orderable"
    assert finnhub["cache_policy"]["path"] == "market_data/quotes/finnhub/{symbol}.json"
    assert "finnhub.io" in " ".join(finnhub["official_docs"])
    assert "local secret gate" in finnhub["implementation_gate"]

    fmp = candidates["fmp_stock_quote_optional_key"]
    assert fmp["status"] == "implemented_bounded_optional_key"
    assert fmp["auth_mode"] == "optional_local_key"
    assert fmp["quote_semantics"] == "quote_not_orderable"
    assert fmp["cache_policy"]["path"] == "market_data/quotes/fmp/{symbol}.json"
    assert "financialmodelingprep.com" in " ".join(fmp["official_docs"])
    assert "local secret gate" in fmp["implementation_gate"]

    stooq = candidates["stooq_public_quote_snapshot"]
    assert stooq["status"] == "implemented_bounded_public_no_key_snapshot"
    assert stooq["auth_mode"] == "public_no_key"
    assert stooq["quote_semantics"] == "quote_not_orderable"
    assert stooq["cache_policy"]["path"] == "market_data/quotes/stooq/{symbol}.json"
    assert "CAPTCHA" in stooq["implementation_gate"]
    moex = candidates["moex_iss_delayed_quote_snapshot"]
    assert moex["status"] == "implemented_bounded_public_no_key_snapshot"
    assert moex["auth_mode"] == "public_no_key"
    assert moex["quote_semantics"] == "quote_not_orderable"
    assert moex["cache_policy"]["path"] == "market_data/quotes/moex/{symbol}.json"
    assert "authenticated real-time data" in moex["implementation_gate"]
    twse = candidates["twse_openapi_daily_quote_snapshot"]
    assert twse["status"] == "implemented_bounded_public_no_key_snapshot"
    assert twse["auth_mode"] == "public_no_key"
    assert twse["quote_semantics"] == "quote_not_orderable"
    assert twse["cache_policy"]["path"] == "market_data/quotes/twse/{symbol}.json"
    assert "STOCK_DAY_ALL" in twse["implementation_gate"]
    cboe = candidates["cboe_delayed_quotes_gate"]
    assert cboe["status"] == "blocked_official_terms"
    assert cboe["auth_mode"] == "public_no_key"
    assert cboe["quote_semantics"] == "quote_blocked_by_terms"
    assert cboe["cache_policy"]["path"] == ""
    assert "cboe.com" in " ".join(cboe["official_docs"])
    assert "not approved as an automated local quote adapter" in cboe[
        "implementation_gate"
    ]
    assert "blocked provider-entry record" in cboe["next_safe_action"]
    iex = candidates["iex_tops_market_data_gate"]
    assert iex["status"] == "blocked_official_terms"
    assert iex["auth_mode"] == "subscriber_agreement_required"
    assert iex["quote_semantics"] == "quote_blocked_by_terms"
    assert iex["cache_policy"]["path"] == ""
    assert "iexexchange.io" in " ".join(iex["official_docs"])
    assert "market-data agreements" in iex["implementation_gate"]
    assert "legacy IEX Cloud/no-key API assumptions" in iex["implementation_gate"]
    assert "blocked provider-entry record" in iex["next_safe_action"]
    nasdaq_data_link = candidates["nasdaq_data_link_dataset_gate"]
    assert nasdaq_data_link["status"] == "blocked_dataset_specific_gate"
    assert nasdaq_data_link["auth_mode"] == (
        "account_or_dataset_subscription_required"
    )
    assert nasdaq_data_link["quote_semantics"] == "dataset_specific_not_approved"
    assert nasdaq_data_link["cache_policy"]["path"] == ""
    assert "docs.data.nasdaq.com" in " ".join(nasdaq_data_link["official_docs"])
    assert "concrete free dataset product page" in nasdaq_data_link[
        "implementation_gate"
    ]
    assert "blocked provider-entry record" in nasdaq_data_link["next_safe_action"]
    jpx_jquants = candidates["jpx_jquants_market_data_gate"]
    assert jpx_jquants["status"] == "blocked_account_plan_gate"
    assert jpx_jquants["auth_mode"] == "api_key_or_plan_required"
    assert jpx_jquants["quote_semantics"] == "quote_blocked_by_account_plan"
    assert jpx_jquants["cache_policy"]["path"] == ""
    assert "jpx-jquants.com" in " ".join(jpx_jquants["official_docs"])
    assert "CSV bulk downloader" in jpx_jquants["implementation_gate"]
    assert "blocked provider-entry record" in jpx_jquants["next_safe_action"]
    yahoo_finance = candidates["yahoo_finance_market_data_gate"]
    assert yahoo_finance["status"] == "blocked_terms_credentials_gate"
    assert yahoo_finance["auth_mode"] == "application_id_or_api_credentials_required"
    assert yahoo_finance["quote_semantics"] == "quote_blocked_by_terms_credentials"
    assert yahoo_finance["cache_policy"]["path"] == ""
    assert "legal.yahoo.com" in " ".join(yahoo_finance["official_docs"])
    assert "query endpoint crawler" in yahoo_finance["implementation_gate"]
    assert "blocked provider-entry record" in yahoo_finance["next_safe_action"]
    nasdaq = candidates["nasdaq_trader_symbol_directory_public"]
    assert nasdaq["status"] == "implemented_public_no_key_reference"
    assert nasdaq["auth_mode"] == "public_no_key"
    assert nasdaq["quote_semantics"] == "not_quote"
    assert nasdaq["cache_policy"]["path"] == (
        "market_data/reference/nasdaq_trader/symbol_directory.json"
    )
    assert "downloadable text files" in nasdaq["implementation_gate"]
    openfigi = candidates["openfigi_identifier_mapping_public"]
    assert openfigi["status"] == "implemented_public_no_key_reference"
    assert openfigi["auth_mode"] == "public_no_key"
    assert openfigi["quote_semantics"] == "not_quote"
    assert openfigi["cache_policy"]["path"] == (
        "market_data/reference/openfigi/mapping.json"
    )
    assert "OpenFIGI v3 mapping jobs" in openfigi["implementation_gate"]

    bea = candidates["bea_regional_optional_key"]
    census = candidates["census_api_optional_key"]
    assert bea["status"] == "implemented_bounded_optional_key"
    assert census["status"] == "implemented_bounded_optional_key"
    assert "local secret gate" in bea["implementation_gate"]
    assert "UserID" in bea["implementation_gate"]
    assert bea["cache_policy"]["path"] == "market_data/regional/bea/SAGDP9N_LINE1_STATE.json"
    assert census["cache_policy"]["path"] == (
        "market_data/regional/census/acs5_profile_state_2023.json"
    )
    assert "local secret gate" in census["implementation_gate"]
    assert "key values" in census["implementation_gate"]


def test_provider_acquisition_gate_api_is_read_only_without_secret_store(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())

    response = client.get("/api/provider-acquisition-gate")

    assert response.status_code == 200
    payload = response.json()
    assert payload["safety"] == {
        "read_only": True,
        "external_network_fetch": False,
        "provider_signup": False,
        "secret_values_returned": False,
        "paid_provider_enabled": False,
        "live_trading": False,
        "installed_source_read": False,
    }
    assert not (tmp_path / "settings" / "local_secrets.json").exists()
    response_text = response.text.lower()
    assert "api_key=" not in response_text
    assert "protected_value" not in response_text
    assert "password" not in response_text
    assert "private_key" not in response_text


def test_agent_contract_exposes_provider_acquisition_gate(tmp_path: Path) -> None:
    payload = agent_operability_payload(tmp_path)
    settings = next(route for route in payload["routes"] if route["route_id"] == "settings")
    actions = {action["action_id"]: action for action in payload["actions"]}

    assert "provider_acquisition_gate" in settings["state_fields"]
    assert actions["provider_acquisition_gate_inspect"]["method"] == "GET"
    assert actions["provider_acquisition_gate_inspect"]["endpoint"] == (
        "/api/provider-acquisition-gate"
    )
    assert actions["provider_acquisition_gate_inspect"]["safety_class"] == (
        "read_only_provider_acquisition_gate"
    )
