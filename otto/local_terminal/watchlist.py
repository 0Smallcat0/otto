"""User-facing quote watchlist state (M27-R2).

The mission wall's quote monitor renders whatever the AI keeps in this state;
"watch X for me" in the conversation becomes one contract action. Groups map
to providers: us→Finnhub, tw→TWSE, fx→Twelve Data, crypto→the public Binance
cache (crypto symbols are limited to SUPPORTED_SYMBOLS because paper trading,
backtests, and the per-exchange pair maps are wired per symbol).
"""

from __future__ import annotations

import copy
from typing import Any

from otto.local_terminal.crypto import SUPPORTED_SYMBOLS

WATCHLIST_GROUPS: tuple[str, ...] = ("crypto", "us", "tw", "fx")
MAX_SYMBOLS_PER_GROUP = 20

DEFAULT_WATCHLIST: dict[str, list[str]] = {
    "crypto": list(SUPPORTED_SYMBOLS),
    "us": ["AAPL", "MSFT", "NVDA", "SPY"],
    "tw": ["2330", "2317", "0050"],
    "fx": ["EUR/USD"],
}


class WatchlistError(ValueError):
    """Raised when a watchlist update cannot be applied safely."""


def default_watchlist_state() -> dict[str, Any]:
    return {group: list(symbols) for group, symbols in DEFAULT_WATCHLIST.items()}


def normalize_watchlist_state(state: dict[str, Any] | None) -> dict[str, Any]:
    source = state if isinstance(state, dict) else {}
    normalized: dict[str, Any] = {}
    for group in WATCHLIST_GROUPS:
        raw = source.get(group)
        symbols = _clean_symbols(group, raw) if isinstance(raw, list) else None
        normalized[group] = symbols if symbols else list(DEFAULT_WATCHLIST[group])
    return normalized


def update_watchlist(state: dict[str, Any], group: str, symbols: Any) -> dict[str, Any]:
    """Replace one group's symbols; unknown groups and empty lists are rejected."""

    normalized_group = str(group or "").strip().lower()
    if normalized_group not in WATCHLIST_GROUPS:
        raise WatchlistError(f"Unknown watchlist group; use one of {'/'.join(WATCHLIST_GROUPS)}")
    if isinstance(symbols, str):
        symbols = [part for part in symbols.replace(";", ",").split(",")]
    if not isinstance(symbols, list):
        raise WatchlistError("Symbols must be a list or comma-separated string")
    cleaned = _clean_symbols(normalized_group, symbols)
    if not cleaned:
        raise WatchlistError("At least one valid symbol is required")
    next_state = normalize_watchlist_state(copy.deepcopy(state))
    next_state[normalized_group] = cleaned
    return next_state


def watchlist_payload(state: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_watchlist_state(state)
    return {
        "groups": normalized,
        "group_order": list(WATCHLIST_GROUPS),
        "limits": {
            "max_symbols_per_group": MAX_SYMBOLS_PER_GROUP,
            "crypto_supported_symbols": list(SUPPORTED_SYMBOLS),
        },
        "write_action": {
            "action_id": "markets_watchlist_update",
            "method": "POST",
            "endpoint": "/api/markets/watchlist",
            "request_contract": '{"group":"us|tw|fx|crypto","symbols":["..."]}',
        },
        "safety": {
            "safety_class": "local_watchlist_state_only",
            "mutates_local_state": True,
            "external_calls": False,
        },
    }


def _clean_symbols(group: str, raw: list[Any]) -> list[str]:
    cleaned: list[str] = []
    for value in raw:
        symbol = str(value or "").strip().upper()
        if group == "fx":
            symbol = "".join(ch for ch in symbol if ch.isalnum() or ch == "/")
            if "/" not in symbol:
                continue
        else:
            symbol = "".join(ch for ch in symbol if ch.isalnum() or ch in {".", "^", "-"})
        if not symbol or len(symbol) > 16:
            continue
        if group == "crypto" and symbol not in SUPPORTED_SYMBOLS:
            continue
        if symbol not in cleaned:
            cleaned.append(symbol)
        if len(cleaned) >= MAX_SYMBOLS_PER_GROUP:
            break
    return cleaned
