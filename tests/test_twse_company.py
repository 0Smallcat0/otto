"""TW single-name facts: the company-level data a TW judgment needs.

Regression for the 2026-07-25 failure where a call on the owner's largest
holding was recorded as "no directional view" because no company data was
wired in — while TWSE published it publicly the whole time.
"""

from __future__ import annotations

from otto.local_terminal.twse_company import (
    tw_company_facts_payload,
    tw_listing_code,
)

_VALUATIONS = [
    {"Date": "1150724", "Code": "2330", "Name": "台積電", "PEratio": "31.59",
     "DividendYield": "0.94", "PBratio": "10.34"},
    {"Date": "1150724", "Code": "2834", "Name": "臺企銀", "PEratio": "13.74",
     "DividendYield": "5.56", "PBratio": "1.17"},
    {"Date": "1150724", "Code": "9999", "Name": "別家", "PEratio": "-",
     "DividendYield": "0.00", "PBratio": "2.00"},
]

_NEWS = [
    {"公司代號": "2834", "公司名稱": "臺企銀", "發言日期": "1150724",
     "事實發生日": "1150723", "主旨 ": "公告本行115年第2季自結盈餘",
     "說明": "1.事實發生日：民國115年07月23日\r\n2.內容：自結稅前盈餘..."},
    {"公司代號": "1721", "公司名稱": "三晃", "發言日期": "1150724",
     "事實發生日": "1150629", "主旨 ": "公告本公司名稱變更", "說明": "更名"},
]


def _facts(symbols):
    return tw_company_facts_payload(
        symbols,
        valuation_fetcher=lambda: list(_VALUATIONS),
        news_fetcher=lambda: list(_NEWS),
    )


def test_listing_code_strips_suffix():
    assert tw_listing_code("2834.TW") == "2834"
    assert tw_listing_code("2330") == "2330"
    assert tw_listing_code("") == ""


def test_valuation_and_announcement_reach_the_requested_symbol():
    payload = _facts(["2834.TW"])
    company = payload["companies"][0]
    assert company["symbol"] == "2834.TW"
    assert company["name"] == "臺企銀"
    # the fundamentals that were previously called unavailable
    assert company["valuation"]["pe_ratio"] == "13.74"
    assert company["valuation"]["dividend_yield_pct"] == "5.56"
    assert company["valuation"]["pb_ratio"] == "1.17"
    assert company["valuation"]["as_of"] == "2026-07-24"  # ROC 115 -> 2026
    # and the single-name catalyst
    assert company["announcement_count"] == 1
    assert "自結盈餘" in company["announcements"][0]["subject"]
    assert company["announcements"][0]["announced_at"] == "2026-07-24"
    assert payload["valuation_covered_count"] == 1


def test_other_companies_announcements_never_leak_in():
    payload = _facts(["2330.TW"])
    company = payload["companies"][0]
    assert company["valuation"]["pe_ratio"] == "31.59"
    # 1721 and 2834 filed today; 2330 did not — silence, not a substitute
    assert company["announcements"] == []
    assert company["announcement_count"] == 0
    assert payload["announcement_total"] == 0
    assert "not missing data" in payload["note"]


def test_blank_valuation_fields_become_null_not_zero():
    payload = _facts(["9999.TW"])
    valuation = payload["companies"][0]["valuation"]
    assert valuation["pe_ratio"] is None  # "-" is unknown, not a P/E of zero
    assert valuation["dividend_yield_pct"] is None  # "0.00" placeholder
    assert valuation["pb_ratio"] == "2.00"


def test_no_symbols_makes_no_network_call():
    called = {"n": 0}

    def boom():
        called["n"] += 1
        return []

    payload = tw_company_facts_payload(
        [], valuation_fetcher=boom, news_fetcher=boom
    )
    assert called["n"] == 0  # an empty question costs nothing
    assert payload["companies"] == []
    assert payload["source_errors"] == []


def test_one_source_failing_still_returns_the_other():
    def boom():
        raise OSError("twse down")

    payload = tw_company_facts_payload(
        ["2834.TW"], valuation_fetcher=boom, news_fetcher=lambda: list(_NEWS)
    )
    company = payload["companies"][0]
    assert company["valuation"] is None
    assert company["announcement_count"] == 1  # announcements survived
    assert payload["source_errors"] == ["valuations: OSError"]
