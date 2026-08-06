"""Taiwan single-name company facts — the data a TW judgment actually needs.

On 2026-07-25 a call on the owner's largest real holding (2834 臺企銀, 63.5% of
his book) had to be recorded as "no directional view" because, as the thesis
put it, there was no company-level data to be had: Yahoo cannot resolve TW
listings and that day's general TW feed happened not to mention it. Naming the
gap and stopping there was the failure — the data exists, free and official,
and had simply never been wired in.

TWSE publishes it through its public OpenAPI, no key required:
- `exchangeReport/BWIBBU_ALL` — per-listing P/E, dividend yield and P/B, which
  for a bank like 2834 is most of the fundamental picture;
- `opendata/t187ap04_L` — the day's material announcements (重大訊息) per
  company, i.e. the single-name catalysts themselves.

Honesty conventions match the rest of the data layer: one retry on a transient
blip, a real error raised rather than faked, and a symbol with no announcement
today returns nothing at all — companies only file when something happens, so
silence is a fact about the day, not a hole to paper over.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

TWSE_OPENAPI_PROVIDER_ID = "twse_openapi_public"
TWSE_VALUATION_URL = "https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL"
TWSE_MATERIAL_NEWS_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap04_L"
TWSE_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
TWSE_MAX_SYMBOLS = 12
TWSE_SCREEN_MAX_ROWS = 30
TWSE_SUBJECT_CHARS = 200
TWSE_DETAIL_CHARS = 600


class TwseCompanyError(ValueError):
    """Raised when TWSE public company data cannot be fetched or parsed."""


def tw_listing_code(symbol: Any) -> str:
    """The bare TWSE listing code for a symbol ("2834.TW" -> "2834")."""
    raw = str(symbol or "").strip().upper()
    if not raw:
        return ""
    code = raw.split(".")[0]
    return "".join(ch for ch in code if ch.isalnum())[:10]


def _fetch_json(url: str, *, timeout: float = 20.0) -> list[dict[str, Any]]:
    request = Request(url, headers={"User-Agent": TWSE_USER_AGENT, "Accept": "application/json"})
    last_error: Exception | None = None
    for attempt in (1, 2):
        try:
            with urlopen(request, timeout=timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
            break
        except (TimeoutError, URLError, HTTPError, OSError, ValueError) as exc:
            last_error = exc
            if attempt == 2:
                raise TwseCompanyError(
                    f"TWSE fetch failed for {url}: {exc.__class__.__name__}"
                ) from exc
    else:  # pragma: no cover - loop always breaks or raises
        raise TwseCompanyError(f"TWSE fetch failed for {url}: {last_error}")
    if not isinstance(payload, list):
        raise TwseCompanyError(f"TWSE response for {url} is not a list")
    return [row for row in payload if isinstance(row, dict)]


def fetch_twse_valuations(*, timeout: float = 20.0) -> list[dict[str, Any]]:
    return _fetch_json(TWSE_VALUATION_URL, timeout=timeout)


def fetch_twse_material_news(*, timeout: float = 20.0) -> list[dict[str, Any]]:
    return _fetch_json(TWSE_MATERIAL_NEWS_URL, timeout=timeout)


def _text(value: Any, limit: int) -> str:
    return " ".join(str(value or "").split())[:limit]


def _roc_date(value: Any) -> str:
    """TWSE stamps dates in ROC form (1150724 = 2026-07-24)."""
    digits = "".join(ch for ch in str(value or "") if ch.isdigit())
    if len(digits) != 7:
        return ""
    try:
        year = int(digits[:3]) + 1911
        return f"{year:04d}-{digits[3:5]}-{digits[5:7]}"
    except ValueError:
        return ""


def _valuation_row(row: dict[str, Any]) -> dict[str, Any]:
    def number(key: str) -> str | None:
        text = str(row.get(key, "")).strip()
        return text if text and text not in {"-", "0.00"} else None

    return {
        "code": str(row.get("Code", "")).strip(),
        "name": str(row.get("Name", "")).strip(),
        "as_of": _roc_date(row.get("Date")),
        "pe_ratio": number("PEratio"),
        "dividend_yield_pct": number("DividendYield"),
        "pb_ratio": number("PBratio"),
    }


def _announcement_row(row: dict[str, Any]) -> dict[str, Any]:
    # TWSE ships this key with a trailing space in the JSON; accept both.
    subject = row.get("主旨 ", row.get("主旨"))
    return {
        "code": str(row.get("公司代號", "")).strip(),
        "name": str(row.get("公司名稱", "")).strip(),
        "announced_at": _roc_date(row.get("發言日期")),
        "occurred_at": _roc_date(row.get("事實發生日")),
        "subject": _text(subject, TWSE_SUBJECT_CHARS),
        "detail": _text(row.get("說明"), TWSE_DETAIL_CHARS),
    }


_FACTS_NOTE = (
    "Official TWSE public OpenAPI, no key. Valuation is the exchange's own "
    "P/E, dividend yield and P/B for the latest session. Announcements are "
    "the day's 重大訊息 filings for these companies — an empty list means "
    "the company filed nothing today, which is a fact about the day, not "
    "missing data, and must never be replaced with index-level news. "
    "Listed (上市) companies only; OTC (上櫃) listings are not in this feed."
)


_SCREEN_SORTS = {
    "dividend_yield_pct": True,  # True = highest first
    "pe_ratio": False,
    "pb_ratio": False,
}

_SCREEN_NOTE = (
    "Official TWSE public OpenAPI, no key: the exchange's own P/E, dividend "
    "yield and P/B for the latest session, ranked over every 上市 listing "
    "rather than a list of codes someone already knew to ask for. These are "
    "TRAILING figures — the yield is what was paid, the P/E is on reported "
    "earnings — so a low multiple is a question, not an answer, and a bank "
    "trading below book may be cheap or may be marking losses nobody has "
    "taken yet. A listing whose ranked field the exchange did not publish "
    "(loss-making companies carry no P/E, non-payers no yield) is excluded "
    "from the ranking and counted in excluded_missing_count, never sorted as "
    "if the number were zero. OTC (上櫃) listings are not in this feed."
)


def tw_valuation_screen_payload(
    *,
    sort: str = "dividend_yield_pct",
    max_pe: float | None = None,
    max_pb: float | None = None,
    min_dividend_yield_pct: float | None = None,
    limit: int = 20,
    valuation_fetcher: Any | None = None,
) -> dict[str, Any]:
    """Rank every TW listing on the exchange's own valuation table.

    tw_company_facts_payload already fetches this whole table and then keeps
    only the codes it was handed, so the terminal could answer "what is 2834
    worth" but never "what is worth owning" — which is the half of the job that
    finds something the owner did not already hold. Same fetch, nothing new
    from the network.
    """
    if sort not in _SCREEN_SORTS:
        raise TwseCompanyError(f"sort must be one of {tuple(_SCREEN_SORTS)}")
    limit = max(1, min(int(limit), TWSE_SCREEN_MAX_ROWS))

    errors: list[str] = []
    rows: list[dict[str, Any]] = []
    screened = 0
    try:
        for raw in (valuation_fetcher or fetch_twse_valuations)():
            screened += 1
            rows.append(_valuation_row(raw))
    except (TwseCompanyError, OSError, ValueError) as exc:
        errors.append(f"valuations: {exc.__class__.__name__}")

    def numeric(row: dict[str, Any], key: str) -> float | None:
        try:
            return float(row[key]) if row.get(key) is not None else None
        except (TypeError, ValueError):
            return None

    ranked: list[dict[str, Any]] = []
    excluded_missing = 0
    for row in rows:
        key_value = numeric(row, sort)
        if key_value is None:
            excluded_missing += 1
            continue
        pe, pb = numeric(row, "pe_ratio"), numeric(row, "pb_ratio")
        yld = numeric(row, "dividend_yield_pct")
        # A filter the exchange cannot answer for this listing excludes it,
        # rather than passing it through as if the bound were satisfied.
        if max_pe is not None and (pe is None or pe > max_pe):
            continue
        if max_pb is not None and (pb is None or pb > max_pb):
            continue
        if min_dividend_yield_pct is not None and (yld is None or yld < min_dividend_yield_pct):
            continue
        ranked.append(row)
    ranked.sort(key=lambda r: float(r[sort]), reverse=_SCREEN_SORTS[sort])

    return {
        "as_of": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "sort": sort,
        "filters": {
            "max_pe": max_pe,
            "max_pb": max_pb,
            "min_dividend_yield_pct": min_dividend_yield_pct,
        },
        "screened_count": screened,
        "match_count": len(ranked),
        "excluded_missing_count": excluded_missing,
        "returned_count": min(len(ranked), limit),
        "rows": ranked[:limit],
        "source_errors": errors,
        "provider_id": TWSE_OPENAPI_PROVIDER_ID,
        "note": _SCREEN_NOTE,
        "safety": {"read_only": True, "orderable": False},
    }


def _empty_facts_payload() -> dict[str, Any]:
    return {
        "as_of": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "requested_symbols": [],
        "companies": [],
        "valuation_covered_count": 0,
        "announcement_total": 0,
        "source_errors": [],
        "provider_id": TWSE_OPENAPI_PROVIDER_ID,
        "note": _FACTS_NOTE,
        "safety": {"read_only": True, "orderable": False},
    }


def tw_company_facts_payload(
    symbols: list[str] | None,
    *,
    valuation_fetcher: Any | None = None,
    news_fetcher: Any | None = None,
) -> dict[str, Any]:
    """Valuation and same-day material announcements for TW listings.

    A symbol with no announcement is reported with an empty list, never with a
    substitute: companies file 重大訊息 only when something happens, so "nothing
    today" is a real answer and must not be dressed up as market news.
    """
    codes: list[str] = []
    for symbol in symbols or []:
        code = tw_listing_code(symbol)
        if code and code not in codes:
            codes.append(code)
        if len(codes) >= TWSE_MAX_SYMBOLS:
            break

    if not codes:
        # Nothing asked for means nothing to fetch: never spend a network call
        # (or a rate-limit slot) to answer an empty question.
        return _empty_facts_payload()

    errors: list[str] = []
    valuations: dict[str, dict[str, Any]] = {}
    try:
        for row in (valuation_fetcher or fetch_twse_valuations)():
            parsed = _valuation_row(row)
            if parsed["code"] in codes:
                valuations[parsed["code"]] = parsed
    except (TwseCompanyError, OSError, ValueError) as exc:
        errors.append(f"valuations: {exc.__class__.__name__}")

    announcements: dict[str, list[dict[str, Any]]] = {code: [] for code in codes}
    try:
        for row in (news_fetcher or fetch_twse_material_news)():
            parsed = _announcement_row(row)
            if parsed["code"] in announcements:
                announcements[parsed["code"]].append(parsed)
    except (TwseCompanyError, OSError, ValueError) as exc:
        errors.append(f"material_news: {exc.__class__.__name__}")

    companies = [
        {
            "symbol": f"{code}.TW",
            "code": code,
            "name": (valuations.get(code) or {}).get("name")
            or next((a["name"] for a in announcements.get(code, []) if a.get("name")), None),
            "valuation": valuations.get(code),
            "announcements": announcements.get(code, []),
            "announcement_count": len(announcements.get(code, [])),
        }
        for code in codes
    ]
    covered = sum(1 for row in companies if row["valuation"])
    return {
        "as_of": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "requested_symbols": [f"{code}.TW" for code in codes],
        "companies": companies,
        "valuation_covered_count": covered,
        "announcement_total": sum(row["announcement_count"] for row in companies),
        "source_errors": errors,
        "provider_id": TWSE_OPENAPI_PROVIDER_ID,
        "note": _FACTS_NOTE,
        "safety": {"read_only": True, "orderable": False},
    }


TWSE_MARGIN_URL = "https://openapi.twse.com.tw/v1/exchangeReport/MI_MARGN"

_MARGIN_NOTE = (
    "Official TWSE public OpenAPI, no key: yesterday's and today's margin "
    "(融資) balance for every listed issue. Balances are LOT counts (張), not "
    "money — TWSE reports the cash figure elsewhere — so the aggregate is a "
    "crude proxy: a lot of a NT$2000 stock and a lot of a NT$10 stock count "
    "the same. Read reduced_symbol_count alongside it; that one is "
    "dimensionless. This measures whether leveraged holders are still being "
    "forced out, which is the question a price chart cannot answer: on "
    "2026-07-30 a reduce call was made on the reasoning that three sessions "
    "closing at the lows meant sellers were still in control, and the next "
    "session was limit-up across the board. Capitulation and continuation look "
    "identical in price."
)


def fetch_twse_margin(*, timeout: float = 25.0) -> tuple[list[dict[str, Any]], str]:
    """Margin rows plus the session they describe, read from Last-Modified.

    The rows say 融資今日餘額 and carry no date. "Today" means the last session
    TWSE published, which before the afternoon release is yesterday — so a
    caller reading this at lunchtime gets the previous session labelled today.
    That is the same shape as every stale-quote defect this terminal has had,
    so the stamp travels with the data instead of being assumed.
    """
    request = Request(
        TWSE_MARGIN_URL,
        headers={"User-Agent": TWSE_USER_AGENT, "Accept": "application/json"},
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            published = str(response.headers.get("Last-Modified") or "")
            payload = json.loads(response.read().decode("utf-8"))
    except (TimeoutError, URLError, HTTPError, OSError, ValueError) as exc:
        raise TwseCompanyError(
            f"TWSE fetch failed for {TWSE_MARGIN_URL}: {exc.__class__.__name__}"
        ) from exc
    if not isinstance(payload, list):
        raise TwseCompanyError(f"TWSE response for {TWSE_MARGIN_URL} is not a list")
    return [row for row in payload if isinstance(row, dict)], published


MAX_MARGIN_SESSIONS = 400


def default_margin_history_state() -> dict[str, Any]:
    return {"sessions": [], "last_fetch_at": None}


def normalize_margin_history_state(payload: Any) -> dict[str, Any]:
    state = payload if isinstance(payload, dict) else {}
    rows = state.get("sessions")
    rows = [r for r in rows if isinstance(r, dict) and r.get("session")] if isinstance(rows, list) else []
    rows.sort(key=lambda r: str(r.get("session")))
    return {"sessions": rows, "last_fetch_at": state.get("last_fetch_at") or None}


def margin_session_row(payload: dict[str, Any]) -> dict[str, Any] | None:
    """One day of margin balance, compact enough to keep for a year.

    Only the aggregate and whatever symbols the caller asked about: the full
    1,291-issue file is not worth storing daily, and the two questions this
    answers — is market-wide deleveraging slowing, and is my own holding still
    being forced out — need the aggregate and a handful of names.

    Keyed on the published session. TWSE's rows are labelled 今日餘額 and carry
    no date at all, so the HTTP Last-Modified stamp is the only date there is;
    a payload without one is refused rather than filed under a guess.
    """
    session = _published_session(payload.get("published_at"))
    if not session:
        return None
    symbols = payload.get("symbols") if isinstance(payload.get("symbols"), list) else []
    return {
        "session": session,
        "published_at": str(payload.get("published_at") or ""),
        "issue_count": payload.get("issue_count"),
        "margin_lots_today": payload.get("margin_lots_today"),
        "margin_lots_prev": payload.get("margin_lots_prev"),
        "change_pct": payload.get("change_pct"),
        "reduced_symbol_count": payload.get("reduced_symbol_count"),
        "increased_symbol_count": payload.get("increased_symbol_count"),
        "symbols": [
            {
                "code": s.get("code"),
                "margin_lots_today": s.get("margin_lots_today"),
                "change_pct": s.get("change_pct"),
            }
            for s in symbols
            if isinstance(s, dict) and s.get("code")
        ],
    }


def _published_session(stamp: Any) -> str | None:
    """`Wed, 05 Aug 2026 21:23:22 GMT` -> `2026-08-05`."""
    text = str(stamp or "").strip()
    if not text:
        return None
    try:
        return parsedate_to_datetime(text).astimezone(UTC).strftime("%Y-%m-%d")
    except (TypeError, ValueError):
        return None


def merge_margin_session(
    state: dict[str, Any], row: dict[str, Any] | None, *, now: datetime | None = None
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Fold one session in. Existing sessions are never rewritten.

    TWSE publishes one file and keeps no archive, so a session nobody fetched
    is a session permanently absent — and a single snapshot cannot answer the
    question the data exists for. Price cannot separate capitulation from
    continuation; a run of sessions where forced sellers stop being forced can.
    """
    store = normalize_margin_history_state(state)
    stamp = (now or datetime.now(tz=UTC)).isoformat(timespec="seconds")
    if row is None:
        store["last_fetch_at"] = stamp
        return store, {"added": False, "reason": "no published session stamp", "held": len(store["sessions"])}
    known = {str(r.get("session")) for r in store["sessions"]}
    added = str(row["session"]) not in known
    if added:
        store["sessions"].append(row)
        store["sessions"].sort(key=lambda r: str(r.get("session")))
        dropped = max(0, len(store["sessions"]) - MAX_MARGIN_SESSIONS)
        if dropped:
            store["sessions"] = store["sessions"][dropped:]
    store["last_fetch_at"] = stamp
    return store, {
        "added": added,
        "session": row["session"],
        "held": len(store["sessions"]),
        "reason": None if added else "already held",
    }


def margin_trend(state: dict[str, Any], *, sessions: int = 5) -> dict[str, Any]:
    """The shape a single snapshot cannot show.

    consecutive_reducing counts sessions ending today where market-wide margin
    fell. Deleveraging that has run for days and then stops is the distinction
    price charts cannot make — every capitulation candle and every continuation
    candle closes at the low.
    """
    store = normalize_margin_history_state(state)
    rows = store["sessions"][-max(1, sessions):]
    streak = 0
    for row in reversed(store["sessions"]):
        pct = str(row.get("change_pct") or "")
        if pct.startswith("-"):
            streak += 1
        else:
            break
    return {
        "sessions_held": [r["session"] for r in store["sessions"]],
        "recent": rows,
        "consecutive_reducing_sessions": streak,
        "note": (
            "TWSE publishes one session and keeps no archive, so sessions_held is "
            "everything this store has ever seen — a gap is a day nobody fetched, "
            "not a quiet market. Balances are LOT counts, not money, so the "
            "aggregate is dimensionally crude; read it beside "
            "reduced_symbol_count, which is dimensionless."
        ),
    }


def deleveraging_progress(
    state: dict[str, Any],
    index_candles: list[dict[str, Any]] | None,
    *,
    index_symbol: str = "0050",
) -> dict[str, Any]:
    """Has margin fallen further than the market it was leveraging?

    This is the comparison Taiwan desks actually run, and it is not a streak.
    The rule of thumb is that a bottom cannot be called while the index has
    fallen further than margin has unwound: on 2026-07-28 the weighted index
    was 12.86% off its wave high while margin balance had given back 9.93%,
    and the read was that deleveraging had further to go
    (https://www.setn.com/news/1880517).

    `consecutive_reducing_sessions` cannot answer that. Three sessions of
    -0.1% is a streak of three and is nearly nothing; one session of -5%
    against a market down 3% is a single session and means the forced sellers
    are done ahead of the tape. The streak counts days; this measures distance.

    Both legs are peak-to-latest over the *same* window, and the window is the
    margin store's own — a comparison drawn across two different spans is the
    kind of number that looks identical to a real one. `0050` stands in for the
    index because it is the series this terminal already keeps and already
    benchmarks calls against; it is a large-cap ETF, not the weighted index,
    and the payload says so rather than letting the reader assume.
    """
    store = normalize_margin_history_state(state)
    sessions = store["sessions"]
    unknown = {
        "verdict": "unknown",
        "margin_decline_pct": None,
        "index_decline_pct": None,
        "index_symbol": index_symbol,
        "window": None,
    }
    if len(sessions) < 2:
        return unknown | {
            "reason": (
                f"{len(sessions)} session(s) held; a cumulative decline needs at "
                "least two, and TWSE keeps no archive to backfill from"
            )
        }

    lots = [(str(r.get("session")), _margin_int(r.get("margin_lots_today"))) for r in sessions]
    lots = [(session, value) for session, value in lots if value]
    if len(lots) < 2:
        return unknown | {"reason": "stored sessions carry no usable margin lot counts"}

    peak_at, peak = max(lots, key=lambda row: row[1])
    latest_at, latest = lots[-1]
    if peak_at >= latest_at:
        return unknown | {
            "reason": f"margin peaked on the latest session held ({latest_at}); no decline to measure"
        }
    margin_decline = (latest / peak - 1) * 100

    closes = [
        (str(c.get("closed_at")), _margin_float(c.get("close")))
        for c in (index_candles or [])
        if isinstance(c, dict)
    ]
    closes = [(day, value) for day, value in closes if day and value]
    in_window = [(day, value) for day, value in closes if peak_at <= day <= latest_at]
    covers_latest = any(day >= latest_at for day, _ in closes)
    if not in_window or not covers_latest:
        newest = max((day for day, _ in closes), default="never fetched")
        return unknown | {
            "margin_decline_pct": f"{margin_decline:.2f}",
            "window": [peak_at, latest_at],
            "reason": (
                f"{index_symbol} history ends {newest}, so it cannot cover the "
                f"{peak_at}..{latest_at} window the margin store spans; refresh it "
                "with markets_history_refresh before reading this comparison"
            ),
        }

    index_peak = max(value for _, value in in_window)
    index_latest = in_window[-1][1]
    index_decline = (index_latest / index_peak - 1) * 100

    if index_decline >= 0:
        verdict = "not_a_drawdown"
    elif margin_decline < index_decline:
        verdict = "margin_led"
    else:
        verdict = "incomplete"
    return {
        "verdict": verdict,
        "margin_decline_pct": f"{margin_decline:.2f}",
        "index_decline_pct": f"{index_decline:.2f}",
        "index_symbol": index_symbol,
        "window": [peak_at, latest_at],
        "reason": None,
        "note": (
            "Deleveraging is read as unfinished while the index has fallen "
            "further than margin has unwound; margin_led means the forced "
            "selling ran ahead of the tape. 0050 is a large-cap ETF standing in "
            "for the weighted index, and both legs are peak-to-latest inside "
            "the window the margin store itself spans."
        ),
    }


def _margin_float(value: Any) -> float | None:
    text = str(value or "").strip().replace(",", "")
    if not text:
        return None
    try:
        parsed = float(text)
    except ValueError:
        return None
    return parsed if parsed > 0 else None


def _margin_int(value: Any) -> int | None:
    text = str(value or "").strip().replace(",", "")
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def tw_margin_balance_payload(
    symbols: list[str] | None = None,
    *,
    margin_fetcher: Any | None = None,
) -> dict[str, Any]:
    """Whether leveraged holders are still being forced out of the TW market.

    A price chart cannot separate capitulation from continuation — both are red
    candles closing at the low. The margin balance can: forced selling shows up
    as the balance collapsing, and it stops when the sellers are gone.
    """
    wanted = [code for code in (tw_listing_code(s) for s in symbols or []) if code]
    errors: list[str] = []
    rows: list[dict[str, Any]] = []
    published = ""
    try:
        rows, published = (margin_fetcher or fetch_twse_margin)()
    except (TwseCompanyError, OSError, ValueError) as exc:
        errors.append(f"margin: {exc.__class__.__name__}")

    today_total = prev_total = 0
    reduced = increased = unchanged = 0
    unreadable = 0
    per_symbol: list[dict[str, Any]] = []
    for row in rows:
        today = _margin_int(row.get("融資今日餘額"))
        prev = _margin_int(row.get("融資前日餘額"))
        if today is None or prev is None:
            # A blank balance is not a zero balance; counting it as one would
            # move the aggregate by the whole of that issue's position.
            unreadable += 1
            continue
        today_total += today
        prev_total += prev
        if today < prev:
            reduced += 1
        elif today > prev:
            increased += 1
        else:
            unchanged += 1
        code = str(row.get("股票代號", "")).strip()
        if code in wanted:
            per_symbol.append(
                {
                    "code": code,
                    "name": str(row.get("股票名稱", "")).strip(),
                    "margin_lots_today": today,
                    "margin_lots_prev": prev,
                    "change_lots": today - prev,
                    "change_pct": f"{((today / prev - 1) * 100):.2f}" if prev else None,
                    "short_lots_today": _margin_int(row.get("融券今日餘額")),
                }
            )

    change = today_total - prev_total
    return {
        "as_of": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        # The session these balances describe, not the day they were read. The
        # rows carry no date and say 今日 regardless.
        "published_at": published or None,
        "issue_count": len(rows),
        "priced_issue_count": reduced + increased + unchanged,
        "unreadable_count": unreadable,
        "margin_lots_today": today_total,
        "margin_lots_prev": prev_total,
        "change_lots": change,
        "change_pct": f"{((today_total / prev_total - 1) * 100):.2f}" if prev_total else None,
        "reduced_symbol_count": reduced,
        "increased_symbol_count": increased,
        "unchanged_symbol_count": unchanged,
        "symbols": per_symbol,
        "source_errors": errors,
        "provider_id": TWSE_OPENAPI_PROVIDER_ID,
        "note": _MARGIN_NOTE,
        "safety": {"read_only": True, "orderable": False},
    }
