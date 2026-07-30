"""TW single-name facts: the company-level data a TW judgment needs.

Regression for the 2026-07-25 failure where a call on the owner's largest
holding was recorded as "no directional view" because no company data was
wired in — while TWSE published it publicly the whole time.
"""

from __future__ import annotations

from otto.local_terminal.twse_company import (
    TwseCompanyError,
    tw_company_facts_payload,
    tw_listing_code,
    tw_valuation_screen_payload,
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


_SCREEN_ROWS = [
    {"Date": "1150729", "Code": "2834", "Name": "臺企銀", "PEratio": "13.70",
     "DividendYield": "5.57", "PBratio": "1.17"},
    {"Date": "1150729", "Code": "2884", "Name": "玉山金", "PEratio": "16.59",
     "DividendYield": "3.84", "PBratio": "2.07"},
    {"Date": "1150729", "Code": "2528", "Name": "皇普", "PEratio": "8.05",
     "DividendYield": "15.58", "PBratio": "1.17"},
    # loss-making: the exchange publishes no P/E and no yield for it
    {"Date": "1150729", "Code": "9999", "Name": "虧損公司", "PEratio": "-",
     "DividendYield": "0.00", "PBratio": "0.30"},
]


def _screen(**kwargs):
    return tw_valuation_screen_payload(
        valuation_fetcher=lambda: list(_SCREEN_ROWS), **kwargs
    )


def test_the_screen_ranks_the_whole_exchange_not_a_list_you_already_knew():
    """Every judgment in the ledger was hold or avoid on a name already held.

    tw_company_facts fetches this entire table and keeps only the codes handed
    to it, so the terminal could price a holding but never find one. Same fetch,
    ranked (2026-07-30).
    """
    top = _screen(sort="dividend_yield_pct", limit=3)
    assert [r["code"] for r in top["rows"]] == ["2528", "2834", "2884"]
    assert top["screened_count"] == 4  # the whole table was examined
    cheap = _screen(sort="pe_ratio", limit=3)
    assert [r["code"] for r in cheap["rows"]] == ["2528", "2834", "2884"]  # lowest first


def test_a_listing_the_exchange_never_priced_is_excluded_not_treated_as_zero():
    # 9999 has no P/E and no yield. Sorted ascending by P/E it would lead the
    # board as "the cheapest company on the exchange" if a missing number were
    # read as 0 — the loss-making company presented as the best value.
    by_pe = _screen(sort="pe_ratio")
    assert "9999" not in [r["code"] for r in by_pe["rows"]]
    assert by_pe["excluded_missing_count"] == 1
    # but it IS priced on book, so a P/B ranking may legitimately include it
    assert "9999" in [r["code"] for r in _screen(sort="pb_ratio")["rows"]]


def test_a_filter_the_exchange_cannot_answer_excludes_the_listing():
    # 9999 has no yield at all. A max_pe/min_yield bound must not pass it
    # through on the grounds that nothing contradicted the bound.
    rows = _screen(sort="pb_ratio", min_dividend_yield_pct=1.0)
    assert "9999" not in [r["code"] for r in rows["rows"]]
    assert [r["code"] for r in _screen(sort="pb_ratio", max_pb=1.5)["rows"]] == [
        "9999", "2834", "2528",
    ]


def test_an_unknown_sort_is_refused_rather_than_silently_ignored():
    import pytest

    with pytest.raises(TwseCompanyError, match="sort must be"):
        _screen(sort="market_cap")


def test_the_screen_says_trailing_and_says_it_is_not_a_buy_signal():
    note = _screen()["note"]
    assert "TRAILING" in note
    assert "not an answer" in note  # a low multiple is a question
    assert "上櫃" in note  # coverage stated, not implied
