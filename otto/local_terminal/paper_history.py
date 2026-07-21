"""Net-value history for the three paper books, plus benchmark reference prices.

The decision loop can now run (2026-07-20 dogfood), but nothing measured
whether running it is any good: each book reports point-in-time P&L, while
"did the agent's decisions beat doing nothing" needs a time series. A
snapshot records all three books' equity at one moment together with a few
benchmark prices, so later reads can compare the books' change against
buy-and-hold over the same window with plain arithmetic — no extra fetches,
no reconstruction from order history.

Honesty rules carried over from the fill path:
- every snapshot stores how stale its marks were (`oldest_quote_age_seconds`,
  `unmarked_position_count`); a snapshot taken on cold caches says so
- benchmarks that could not be fetched are recorded as `unavailable`, never
  silently dropped, so a later comparison cannot pretend the window had data
- change percentages are computed in each book's or benchmark's own currency;
  the payload says so instead of implying a cross-currency ranking
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import uuid4

# ~5.5 years of daily snapshots; oldest rows are dropped first and the read
# payload reports the retained window so truncation is never silent.
MAX_SNAPSHOTS = 2000
HISTORY_DEFAULT_LIMIT = 30
HISTORY_MAX_LIMIT = 200

# One natural buy-and-hold baseline per book (crypto / US equity / TW equity).
BENCHMARK_SYMBOLS = ("BTC-USD", "SPY", "0050.TW")

BOOK_IDS = ("crypto_usdt", "us_equity_usd", "tw_equity_twd")

# Decision-journal note an agent may attach to any paper order. Bounded so the
# ledger stays readable; never required, never invented.
RATIONALE_MAX_CHARS = 500


def clean_rationale(value: Any) -> str | None:
    """Normalize an agent-supplied order rationale (strip, cap, empty→None)."""
    if value is None:
        return None
    text = str(value).strip()
    return text[:RATIONALE_MAX_CHARS] or None


def default_paper_history_state() -> dict[str, Any]:
    return {"snapshots": []}


def normalize_paper_history_state(payload: Any) -> dict[str, Any]:
    state = payload if isinstance(payload, dict) else {}
    raw = state.get("snapshots")
    snapshots = [entry for entry in raw if isinstance(entry, dict)] if isinstance(raw, list) else []
    return {"snapshots": snapshots[-MAX_SNAPSHOTS:]}


def _decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _book_row(book_id: str, summary: dict[str, Any]) -> dict[str, Any]:
    """Compress one summary payload into a snapshot row, keeping mark quality."""
    account = summary.get("account") if isinstance(summary.get("account"), dict) else {}
    positions = summary.get("positions") if isinstance(summary.get("positions"), list) else []
    ages = [
        _int_or_none(entry.get("quote_age_seconds"))
        for entry in positions
        if isinstance(entry, dict)
    ]
    known_ages = [age for age in ages if age is not None]
    unmarked = sum(
        1
        for entry in positions
        if isinstance(entry, dict) and str(entry.get("last_price", "N/A")) == "N/A"
    )
    currency = "USDT"
    scope = summary.get("scope") if isinstance(summary.get("scope"), dict) else {}
    scope_currency = str(scope.get("currency", ""))
    if scope_currency.endswith("symbols only"):
        currency = scope_currency.split(" ", 1)[0]
    return {
        "book": book_id,
        "currency": currency,
        "cash": str(account.get("cash", "N/A")),
        "equity": str(account.get("equity", "N/A")),
        "total_pnl": str(account.get("total_pnl", "N/A")),
        "position_count": len(positions),
        "unmarked_position_count": unmarked,
        "oldest_quote_age_seconds": max(known_ages) if known_ages else None,
    }


def _age_seconds(retrieved_at: str) -> int | None:
    try:
        stamp = datetime.fromisoformat(retrieved_at.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=UTC)
    return int((datetime.now(tz=UTC) - stamp).total_seconds())


def _benchmark_row(symbol: str, quote_row: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(quote_row, dict) or _decimal(quote_row.get("price")) is None:
        return {"symbol": symbol, "state": "unavailable", "price": None}
    age = _age_seconds(str(quote_row.get("retrieved_at", "")))
    if age is None:
        state = "unknown_age"
    elif age <= 900:
        state = "live"
    else:
        state = "stale_cache"
    return {
        "symbol": symbol,
        "state": state,
        "price": str(quote_row.get("price")),
        "currency": str(quote_row.get("currency", "")),
        "retrieved_at": str(quote_row.get("retrieved_at", "")),
        "age_seconds": age,
    }


def record_paper_snapshot(
    state: dict[str, Any],
    *,
    crypto_summary: dict[str, Any],
    us_summary: dict[str, Any],
    tw_summary: dict[str, Any],
    benchmark_rows: list[dict[str, Any]] | None = None,
    note: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    history = normalize_paper_history_state(state)
    by_symbol = {
        str(row.get("symbol", "")).upper(): row
        for row in benchmark_rows or []
        if isinstance(row, dict)
    }
    snapshot = {
        "snapshot_id": f"snap-{uuid4().hex[:12]}",
        "recorded_at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "note": (str(note).strip()[:300] or None) if note is not None else None,
        "books": [
            _book_row("crypto_usdt", crypto_summary),
            _book_row("us_equity_usd", us_summary),
            _book_row("tw_equity_twd", tw_summary),
        ],
        "benchmarks": [
            _benchmark_row(symbol, by_symbol.get(symbol)) for symbol in BENCHMARK_SYMBOLS
        ],
    }
    history["snapshots"].append(snapshot)
    return normalize_paper_history_state(history), snapshot


def _change_pct(start: Decimal | None, end: Decimal | None) -> str | None:
    if start is None or end is None or start <= 0:
        return None
    return f"{(end / start - 1) * 100:.2f}"


def _books_by_id(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    books = snapshot.get("books") if isinstance(snapshot.get("books"), list) else []
    return {str(row.get("book", "")): row for row in books if isinstance(row, dict)}


def _benchmarks_by_symbol(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = snapshot.get("benchmarks") if isinstance(snapshot.get("benchmarks"), list) else []
    return {str(row.get("symbol", "")): row for row in rows if isinstance(row, dict)}


def _window_performance(window: list[dict[str, Any]]) -> dict[str, Any] | None:
    if len(window) < 2:
        return None
    first, last = window[0], window[-1]
    first_books, last_books = _books_by_id(first), _books_by_id(last)
    books = []
    for book_id in BOOK_IDS:
        start = _decimal(first_books.get(book_id, {}).get("equity"))
        end = _decimal(last_books.get(book_id, {}).get("equity"))
        change = _change_pct(start, end)
        books.append(
            {
                "book": book_id,
                "currency": last_books.get(book_id, {}).get("currency"),
                "start_equity": str(start) if start is not None else None,
                "end_equity": str(end) if end is not None else None,
                "change_pct": change,
            }
        )
    first_marks, last_marks = _benchmarks_by_symbol(first), _benchmarks_by_symbol(last)
    benchmarks = []
    for symbol in BENCHMARK_SYMBOLS:
        start = _decimal(first_marks.get(symbol, {}).get("price"))
        end = _decimal(last_marks.get(symbol, {}).get("price"))
        benchmarks.append(
            {
                "symbol": symbol,
                "start_price": str(start) if start is not None else None,
                "end_price": str(end) if end is not None else None,
                "change_pct": _change_pct(start, end),
            }
        )
    return {
        "window": {
            "from": str(first.get("recorded_at", "")),
            "to": str(last.get("recorded_at", "")),
            "snapshot_count": len(window),
        },
        "books": books,
        "benchmarks": benchmarks,
        "note": (
            "change_pct is measured in each book's or benchmark's own currency over "
            "the same window; rows are not currency-converted or ranked against each "
            "other. A null change_pct means one endpoint of the window had no usable "
            "value — it is missing data, not zero performance."
        ),
    }


def paper_history_payload(state: dict[str, Any], *, limit: int | None = None) -> dict[str, Any]:
    history = normalize_paper_history_state(state)
    snapshots = history["snapshots"]
    if limit is None:
        limit = HISTORY_DEFAULT_LIMIT
    limit = max(1, min(int(limit), HISTORY_MAX_LIMIT))
    window = snapshots[-limit:]
    performance = _window_performance(window)
    payload: dict[str, Any] = {
        "as_of": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "snapshot_count_total": len(snapshots),
        "snapshot_count_returned": len(window),
        "max_snapshots_retained": MAX_SNAPSHOTS,
        "snapshots": window,
        "performance": performance,
        "record_action": "paper_snapshot_record",
        "safety": {"paper_only": True, "live_execution": "disabled"},
    }
    if performance is None:
        payload["performance_note"] = (
            "Need at least two snapshots in the window to measure change; record "
            "snapshots across time with paper_snapshot_record."
        )
    return payload
