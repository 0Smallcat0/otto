from __future__ import annotations

from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi.testclient import TestClient

from src.local_terminal import server
from src.local_terminal.commodity_data import (
    commodity_data_payload,
    normalize_cftc_cot_legacy_futures,
    normalize_world_bank_commodity_prices,
)
from src.local_terminal.markets import default_markets_layout, markets_payload
from src.local_terminal.providers import providers_payload
from src.local_terminal.storage import LocalStateStore


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _cell(ref: str, value: str) -> str:
    return f'<c r="{ref}" t="inlineStr"><is><t>{value}</t></is></c>'


def _row(number: int, values: dict[str, str]) -> str:
    cells = "".join(_cell(ref, value) for ref, value in values.items())
    return f'<row r="{number}">{cells}</row>'


def _world_bank_xlsx() -> bytes:
    sheet = f"""<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData>
    {_row(1, {"A1": "World Bank Commodity Price Data (The Pink Sheet)"})}
    {_row(4, {"A4": "Updated on May 04, 2026"})}
    {_row(5, {
        "B5": "Crude oil, WTI",
        "C5": "Gold",
        "D5": "Copper",
        "E5": "Wheat, US SRW",
    })}
    {_row(6, {
        "B6": "($/bbl)",
        "C6": "($/troy oz)",
        "D6": "($/mt)",
        "E6": "($/mt)",
    })}
    {_row(7, {
        "B7": "CRUDE_WTI",
        "C7": "GOLD",
        "D7": "COPPER",
        "E7": "WHEAT_US_SRW",
    })}
    {_row(8, {"A8": "2026M03", "B8": "91.16", "C8": "4855.54", "D8": "12528.71", "E8": "244.5"})}
    {_row(9, {"A9": "2026M04", "B9": "98.63", "C9": "4721.42", "D9": "12950.96", "E9": "252.75"})}
  </sheetData>
</worksheet>
"""
    workbook = """<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
  xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
    <sheet name="Monthly Prices" sheetId="1" r:id="rId1"/>
  </sheets>
</workbook>
"""
    rels = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1"
    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"
    Target="worksheets/sheet1.xml"/>
</Relationships>
"""
    payload = BytesIO()
    with ZipFile(payload, "w", ZIP_DEFLATED) as workbook_zip:
        workbook_zip.writestr("xl/workbook.xml", workbook)
        workbook_zip.writestr("xl/_rels/workbook.xml.rels", rels)
        workbook_zip.writestr("xl/worksheets/sheet1.xml", sheet)
    return payload.getvalue()


def _fake_commodities() -> bytes:
    return _world_bank_xlsx()


def _cftc_raw() -> bytes:
    return b"""[
      {
        "market_and_exchange_names": "GOLD - COMMODITY EXCHANGE INC.",
        "report_date_as_yyyy_mm_dd": "2026-05-19T00:00:00.000",
        "open_interest_all": "379325",
        "noncomm_positions_long_all": "211018",
        "noncomm_positions_short_all": "51185",
        "comm_positions_long_all": "69520",
        "comm_positions_short_all": "261149"
      },
      {
        "market_and_exchange_names": "WHEAT-SRW - CHICAGO BOARD OF TRADE",
        "report_date_as_yyyy_mm_dd": "2026-05-19T00:00:00.000",
        "open_interest_all": "474622",
        "noncomm_positions_long_all": "143267",
        "noncomm_positions_short_all": "143004",
        "comm_positions_long_all": "157233",
        "comm_positions_short_all": "159225"
      },
      {
        "market_and_exchange_names": "CRUDE OIL, LIGHT SWEET-WTI - ICE FUTURES EUROPE",
        "report_date_as_yyyy_mm_dd": "2026-05-19T00:00:00.000",
        "open_interest_all": "836880",
        "noncomm_positions_long_all": "87907",
        "noncomm_positions_short_all": "116163",
        "comm_positions_long_all": "524702",
        "comm_positions_short_all": "497652"
      },
      {
        "market_and_exchange_names": "COPPER- #1 - COMMODITY EXCHANGE INC.",
        "report_date_as_yyyy_mm_dd": "2026-05-19T00:00:00.000",
        "open_interest_all": "88500",
        "noncomm_positions_long_all": "42000",
        "noncomm_positions_short_all": "35000",
        "comm_positions_long_all": "21000",
        "comm_positions_short_all": "29000"
      }
    ]"""


def _fake_cftc() -> bytes:
    return _cftc_raw()


def test_world_bank_commodity_normalize_no_key_monthly_xlsx() -> None:
    payload = normalize_world_bank_commodity_prices(_world_bank_xlsx(), retrieved_at=_now())

    assert payload["status"]["provider_id"] == "world_bank_commodity_monthly_public"
    assert payload["status"]["source"] == "world_bank_pink_sheet"
    assert payload["latest"]["period"] == "2026M04"
    wti = next(row for row in payload["rows"] if row["code"] == "CRUDE_WTI")
    assert wti["value"] == "98.63"
    assert wti["unit"] == "($/bbl)"
    assert wti["monthly_reference"] is True
    assert "api_key" not in str(payload).lower()


def test_cftc_cot_normalize_no_key_positioning_context() -> None:
    payload = normalize_cftc_cot_legacy_futures(_cftc_raw(), retrieved_at=_now())

    assert payload["status"]["provider_id"] == "cftc_cot_legacy_public"
    assert payload["status"]["source"] == "cftc_cot_legacy_futures_only"
    assert payload["summary"]["row_count"] == 4
    assert payload["summary"]["report_date"] == "2026-05-19"
    assert payload["summary"]["gold_noncommercial_net"] == "159833"
    assert payload["summary"]["wti_crude_noncommercial_net"] == "-28256"
    assert payload["rows"][0]["contract"] == "Gold"
    assert payload["rows"][0]["positioning_context"] is True
    assert "api_key" not in str(payload).lower()


def test_commodity_payload_and_markets_expose_world_bank_monthly_rows() -> None:
    commodities = commodity_data_payload(
        fetcher=_fake_commodities,
        cftc_fetcher=_fake_cftc,
        refresh=True,
    )
    markets = markets_payload(default_markets_layout(), {}, commodity_data=commodities)

    assert commodities["status"]["state"] == "live"
    assert commodities["world_bank"]["summary"]["period"] == "2026M04"
    assert commodities["cftc"]["summary"]["report_date"] == "2026-05-19"
    assert commodities["world_bank"]["summary"]["crude_wti"] == "98.63"
    assert markets["commodities"]["summary"]["gold"] == "4721.42"
    assert markets["commodities"]["cftc"]["gold_noncommercial_net"] == "159833"
    assert markets["commodities"]["rows"][0]["code"] == "CRUDE_WTI"
    assert any(
        row["runtime_role"] == "positioning_context"
        and row["provider_id"] == "cftc_cot_legacy_public"
        and row["quote_semantics"] == "not_quote"
        for row in markets["source_coverage_matrix"]
    )
    assert any(
        gateway["tab_id"] == "commodities"
        and gateway["state"] == "commodity_reference_available"
        for gateway in markets["asset_gateways"]
    )
    assert "offline_fixture" not in str(markets).lower()
    assert "mock" not in str(markets["commodities"]).lower()


def test_commodity_refresh_writes_cache_and_updates_provider_health(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = LocalStateStore(root=tmp_path)
    monkeypatch.setattr(server, "STORE", store)
    monkeypatch.setattr(server, "COMMODITY_FETCHER", _fake_commodities)
    monkeypatch.setattr(server, "CFTC_COT_FETCHER", _fake_cftc)
    client = TestClient(server.create_app())

    refreshed = client.post("/api/markets/commodities/refresh")
    commodities = client.get("/api/commodities")
    providers = providers_payload(store)
    local_state = client.get("/api/local-state")

    assert refreshed.status_code == 200
    assert refreshed.json()["commodities"]["status"]["state"] == "live"
    assert refreshed.json()["commodities"]["summary"]["period"] == "2026M04"
    assert commodities.status_code == 200
    assert commodities.json()["world_bank"]["summary"]["row_count"] == 4
    assert commodities.json()["cftc"]["summary"]["row_count"] == 4
    assert "cache" not in commodities.json()
    assert (
        tmp_path / "market_data" / "commodities" / "world_bank" / "pink_sheet_monthly.json"
    ).is_file()
    assert (
        tmp_path / "market_data" / "commodities" / "cftc" / "cot_legacy_futures.json"
    ).is_file()
    assert any(
        provider["provider_id"] == "world_bank_commodity_monthly_public"
        and provider["health"]["state"] == "active"
        for provider in providers["providers"]
    )
    assert any(
        provider["provider_id"] == "cftc_cot_legacy_public"
        and provider["health"]["state"] == "active"
        for provider in providers["providers"]
    )
    assert local_state.json()["storage"]["world_bank_commodity_cache"] == (
        "market_data/commodities/world_bank/pink_sheet_monthly.json"
    )
    assert local_state.json()["storage"]["cftc_cot_cache"] == (
        "market_data/commodities/cftc/cot_legacy_futures.json"
    )
    assert "api_key" not in refreshed.text.lower()
    assert "private" not in refreshed.text.lower()
