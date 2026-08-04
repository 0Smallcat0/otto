"""TWSE ex-rights / ex-dividend events, so a dividend stops reading as a loss.

On 2026-08-04 台企銀 (2834) closed at 16.90 against a previous close of 18.20.
Every surface in this terminal called that −7.14%, the worst move in the
universe, on a day the index fell 1.32%. It was not a fall. The stock went
ex-rights-and-dividend that morning for 1.471029 of value per share; against the
16.72 reference price TWSE published, it rose 1.08% and beat the index by 2.4
points. The holder was not down 7%, they were up and holding the dividend.

The same arithmetic runs through the judgment ledger. A call carries the price
it was struck at, and scoring divides today's price by that — so an ex-dividend
between the two counts money that was paid out as money that was lost, grades a
thesis that never failed, and drags an invalidation level it was never measured
against. Taiwan listings go ex-dividend once a year, mostly July to September,
so this misfires on every TW holding annually rather than rarely.

TWT49U is TWSE's own 除權除息計算結果表: the pre-event close, the value
distributed, and the reference price the exchange itself opened against. No key,
no account. `權/息` distinguishes a cash dividend (息), a stock dividend (權),
and both (權息); all three move the price mechanically and all three are
adjusted here.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

TWSE_EXRIGHT_URL = "https://www.twse.com.tw/rwd/zh/exRight/TWT49U"
TWSE_EXRIGHT_DOCS_URL = "https://www.twse.com.tw/zh/trading/exchange/twt49u.html"
TWSE_EXRIGHT_DOCS_CHECKED_AT = "2026-08-05"
TWSE_EXRIGHT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"

# Column positions in TWT49U. The endpoint ships its own `fields` list; these are
# resolved by name against it and only fall back to position, because a silently
# reordered column would corrupt every adjustment rather than fail.
_FIELD_DATE = "資料日期"
_FIELD_CODE = "股票代號"
_FIELD_NAME = "股票名稱"
_FIELD_PREV_CLOSE = "除權息前收盤價"
_FIELD_REFERENCE = "除權息參考價"
_FIELD_VALUE = "權值+息值"
_FIELD_KIND = "權/息"

REQUIRED_FIELDS = (
    _FIELD_DATE,
    _FIELD_CODE,
    _FIELD_PREV_CLOSE,
    _FIELD_REFERENCE,
    _FIELD_VALUE,
)


class TwseExRightError(RuntimeError):
    """TWSE ex-rights data could not be read."""


def _decimal(value: Any) -> Decimal | None:
    text = str(value or "").replace(",", "").strip()
    if not text or text in {"-", "--"}:
        return None
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return None


def roc_to_iso(value: str) -> str | None:
    """`115年08月04日` → `2026-08-04`.

    TWSE dates the rows in Republic-of-China years with CJK separators and
    nothing else; a row whose date cannot be read is dropped rather than
    guessed, because an event applied to the wrong day is worse than an event
    that is missing.
    """
    text = str(value or "").strip()
    digits = [part for part in text.replace("年", " ").replace("月", " ").replace("日", " ").split()]
    if len(digits) != 3:
        return None
    try:
        year, month, day = (int(part) for part in digits)
    except ValueError:
        return None
    if year < 1911:
        year += 1911
    try:
        return datetime(year, month, day, tzinfo=UTC).strftime("%Y-%m-%d")
    except ValueError:
        return None


def fetch_twse_ex_rights(
    *, start: str, end: str, timeout: float = 20.0
) -> list[dict[str, Any]]:
    """Ex-rights/ex-dividend events between two ISO dates, inclusive.

    Rows are resolved by TWSE's own `fields` header rather than by fixed index:
    a reordered column would otherwise be applied as if it were a price.
    """
    params = f"?startDate={start.replace('-', '')}&endDate={end.replace('-', '')}&response=json"
    request = Request(
        f"{TWSE_EXRIGHT_URL}{params}",
        headers={"User-Agent": TWSE_EXRIGHT_USER_AGENT, "Accept": "application/json"},
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (TimeoutError, URLError, OSError, json.JSONDecodeError) as exc:
        raise TwseExRightError(f"TWSE ex-rights fetch failed: {exc}") from exc
    return normalize_twse_ex_rights(payload)


def normalize_twse_ex_rights(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        raise TwseExRightError("TWSE ex-rights response was not an object")
    if str(payload.get("stat") or "").upper() != "OK":
        raise TwseExRightError(f"TWSE ex-rights response not OK: {payload.get('stat')}")
    fields = payload.get("fields")
    fields = [str(f) for f in fields] if isinstance(fields, list) else []
    missing = [f for f in REQUIRED_FIELDS if f not in fields]
    if missing:
        raise TwseExRightError(f"TWSE ex-rights response is missing columns: {missing}")
    index = {name: fields.index(name) for name in fields}
    rows = payload.get("data")
    rows = rows if isinstance(rows, list) else []
    events: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, list) or len(row) < len(fields):
            continue
        day = roc_to_iso(row[index[_FIELD_DATE]])
        code = str(row[index[_FIELD_CODE]] or "").strip()
        prev_close = _decimal(row[index[_FIELD_PREV_CLOSE]])
        reference = _decimal(row[index[_FIELD_REFERENCE]])
        value = _decimal(row[index[_FIELD_VALUE]])
        if not day or not code or reference is None or reference <= 0 or value is None:
            continue
        events.append(
            {
                "ex_date": day,
                "code": code,
                "symbol": f"{code}.TW",
                "name": str(row[index[_FIELD_NAME]] or "").strip() if _FIELD_NAME in index else "",
                "prev_close": str(prev_close) if prev_close is not None else None,
                "reference_price": str(reference),
                "value_per_share": str(value),
                "kind": str(row[index[_FIELD_KIND]] or "").strip() if _FIELD_KIND in index else "",
                "source": "twse_twt49u_ex_right",
            }
        )
    return events


def events_by_symbol(events: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Group events per symbol, oldest first, so a window can be summed."""
    grouped: dict[str, list[dict[str, Any]]] = {}
    for event in events:
        grouped.setdefault(str(event.get("symbol") or ""), []).append(event)
    for rows in grouped.values():
        rows.sort(key=lambda row: str(row.get("ex_date")))
    return grouped


def distributed_between(
    events: list[dict[str, Any]], *, symbol: str, after: str, upto: str
) -> Decimal:
    """Total value per share distributed by `symbol` in (after, upto].

    The lower bound is exclusive: an event on the day a call was struck was
    already in the price it was struck at, so adding it back would credit the
    holder with a dividend the entry price had already discounted.
    """
    total = Decimal("0")
    for event in events:
        if str(event.get("symbol")) != symbol:
            continue
        ex_date = str(event.get("ex_date") or "")
        if not ex_date or ex_date <= after or ex_date > upto:
            continue
        value = _decimal(event.get("value_per_share"))
        if value is not None:
            total += value
    return total


def adjusted_return_pct(
    *, ref_price: Decimal, price: Decimal, distributed: Decimal
) -> Decimal | None:
    """Total return: the price move plus what was paid out along the way.

    Without the second term a holding that paid a 1.47 dividend on an 18.20
    share reads as an 8% loss to someone who is exactly even.
    """
    if ref_price <= 0:
        return None
    return ((price + distributed) / ref_price - 1) * 100
