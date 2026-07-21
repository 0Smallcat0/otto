"""M26 S1.3 — the agent-contract response map must match the territory.

The agent contract is the AI operator's map of this terminal. The 2026-07-07
100-action health check found eight response_contract entries describing keys
the endpoints no longer return. This test executes every deterministic local
action against a seeded store and asserts that every response_contract key
resolves in the real response, so the map can never silently drift again.

Coverage rules:
- every GET action runs;
- every local POST runs, in dependency order, with valid bodies;
- network refreshes (endpoint containing "refresh" or the refresh job), the
  DPAPI secret store, and safety-disabled endpoints are skipped with reasons;
- a completeness guard forces every future action to be classified here.

Path syntax in response_contract: "a.b.c" walks dicts, "rows[].field" checks
each list element (an empty list counts as present — shape unverifiable).
"""

from typing import Any

from fastapi.testclient import TestClient

from otto.local_terminal import server
from otto.local_terminal.agent_contract import ACTION_CONTRACTS
from otto.local_terminal.markets import default_markets_layout, markets_payload
from otto.local_terminal.storage import LocalStateStore


def _fake_tickers(symbols: list[str]) -> list[dict[str, str]]:
    return [
        {
            "symbol": symbol,
            "lastPrice": "100.00",
            "priceChange": "1.00",
            "priceChangePercent": "1.00",
            "highPrice": "110.00",
            "lowPrice": "90.00",
            "volume": "12345",
            "bidPrice": "99.50",
            "askPrice": "100.50",
            "openPrice": "99.00",
        }
        for symbol in symbols
    ]


def _resolve(obj: Any, dotted: str) -> bool:
    parts = dotted.split(".")

    def walk(cur: Any, idx: int) -> bool:
        if idx == len(parts):
            return True
        part = parts[idx]
        if part.endswith("[]"):
            key = part[:-2]
            if not isinstance(cur, dict) or not isinstance(cur.get(key), list):
                return False
            rows = cur[key]
            if idx + 1 == len(parts) or not rows:
                return True
            return any(walk(row, idx + 1) for row in rows)
        if not isinstance(cur, dict) or part not in cur:
            return False
        return walk(cur[part], idx + 1)

    return walk(obj, 0)


_STRATEGY_BODY = {
    "name": "Truth Strategy",
    "entry_conditions": ["fast SMA crosses above slow SMA"],
    "exit_conditions": ["fast SMA crosses below slow SMA"],
}

# Skipped actions and why. Everything else must execute.
SKIP_REASONS = {
    "markets_quote_lookup": "live network fetch by design; covered by test_quote_lookup with an injected fetcher",
    "equity_submit_paper_order": "fills at a live network quote by design; covered by test_equity_paper with an injected fetcher",
    "tw_equity_submit_paper_order": "fills at a live network quote by design; covered by test_equity_paper with an injected fetcher",
    "equity_cancel_paper_order": "needs a WORKING order placed at a live quote; covered by test_equity_paper with an injected fetcher",
    "tw_equity_cancel_paper_order": "needs a WORKING order placed at a live quote; covered by test_equity_paper with an injected fetcher",
    "markets_candles_read": "needs a candle cache (network refresh); covered by test_m27_candles with a seeded cache",
    "store_optional_data_provider_secret": "writes the real DPAPI secret store",
    "crypto_reset_paper": "destructive paper-ledger wipe; delete path covered by m16 tests",
    "nodes_execute_disabled": "disabled by safety contract; refusal covered by m11 tests",
    "code_run_disabled": "disabled by safety contract; refusal covered by m12 tests",
    "quant_lab_execute_disabled": "disabled by safety contract; refusal covered by m13 tests",
    "quantlib_external_execute_disabled": "disabled by safety contract; refusal covered by m14 tests",
}


def _network_refresh(endpoint: str) -> bool:
    return "refresh" in endpoint


def test_every_response_contract_key_resolves(tmp_path, monkeypatch) -> None:
    store = LocalStateStore(root=tmp_path)
    monkeypatch.setattr(server, "STORE", store)
    live = markets_payload(default_markets_layout(), {}, fetcher=_fake_tickers, refresh=True)
    store.write_market_cache(live["cache"])
    client = TestClient(server.create_app())

    actions = {action.action_id: action for action in ACTION_CONTRACTS}
    executed: dict[str, Any] = {}
    failures: list[str] = []

    def run(
        action_id: str,
        body: dict | None = None,
        endpoint: str | None = None,
    ) -> dict[str, Any] | None:
        action = actions[action_id]
        target = endpoint or action.endpoint
        if action.method == "GET":
            response = client.get(target)
        else:
            response = client.post(target, json=body if body is not None else {})
        if response.status_code != 200:
            failures.append(
                f"{action_id}: HTTP {response.status_code} {response.text[:160]}"
            )
            executed[action_id] = None
            return None
        payload = response.json()
        executed[action_id] = payload
        for key in action.response_contract:
            if not _resolve(payload, key):
                failures.append(f"{action_id}: response_contract key '{key}' missing")
        return payload

    # ---- all GET actions, fresh-store reads ----
    late_gets = {"portfolio_export"}  # 404s until an active portfolio exists
    for action in ACTION_CONTRACTS:
        if (
            action.method == "GET"
            and action.action_id not in SKIP_REASONS
            and action.action_id not in late_gets
            and "{" not in action.endpoint  # detail reads run later with real ids
        ):
            run(action.action_id)

    # ---- local POST actions in dependency order ----
    run("ai_chat_create_session", {"name": "Truth probe"})
    run("ai_chat_append_message", {"content": "truth test ping"})
    run("agent_activity_event", {
        "action_id": "markets_refresh_public",
        "state": "succeeded",
        "summary": "truth test event",
    })

    nodes_state = run("nodes_load_template", {"template_id": "template-hello-local"})
    run("nodes_dry_run", {})
    workflow = None
    if isinstance(nodes_state, dict):
        active_id = nodes_state.get("active_workflow_id")
        library = nodes_state.get("library")
        if isinstance(library, list):
            workflow = next(
                (
                    row.get("workflow")
                    for row in library
                    if isinstance(row, dict) and isinstance(row.get("workflow"), dict)
                ),
                None,
            )
        if workflow is None and isinstance(nodes_state.get("active_workflow"), dict):
            workflow = nodes_state["active_workflow"]
        if workflow is None and active_id:
            workflows = nodes_state.get("workflows")
            if isinstance(workflows, dict) and isinstance(workflows.get(active_id), dict):
                workflow = workflows[active_id]
    if workflow is not None:
        run("nodes_save_workflow", {"workflow": workflow})
    else:
        failures.append("nodes_save_workflow: no workflow definition found to save")
        executed["nodes_save_workflow"] = None

    # a notebook must exist before analyze/export (setup via non-contract route)
    assert client.post("/api/code/notebook", json={}).status_code == 200
    run("code_analyze", {})
    run("code_export", {})
    run("quant_lab_select_module", {"module_slug": "feature-engineering"})
    run("quant_lab_run_preview", {})
    run("quantlib_select_action", {"action_id": "bs-price"})
    run("quantlib_compute", {})
    run("profile_save_local_preferences", {
        "display_name": "Truth User",
        "theme": "system",
        "default_route": "dashboard",
    })
    run("dashboard_save_layout", {})
    run("dashboard_reset", {"confirm": True})
    # dashboard layout now has a slot-1 backup (save above), so the restore
    # endpoint can run against a real backup chain
    run("local_state_restore", {"kind": "dashboard_layout", "slot": 1, "confirm": True})
    run("news_layout_save", {})
    run("markets_watchlist_update", {"group": "us", "symbols": ["AAPL", "MSFT"]})
    run("news_information_packet", {"symbols": ["BTCUSDT"], "limit": 3})
    run("news_digest_write", {"items": [
        {"item_id": "truth-item-1", "title_zh": "測試標題", "summary_zh": "一句話總結"}
    ]})
    brief = run("news_research_brief", {})
    brief_id = None
    if isinstance(brief, dict):
        research_brief = brief.get("research_brief")
        if isinstance(research_brief, dict):
            brief_id = research_brief.get("brief_id")
        brief_id = brief_id or brief.get("brief_id")
    if brief_id:
        run("news_brief_detail", endpoint=f"/api/news/briefs/{brief_id}")
    else:
        failures.append("news_brief_detail: no brief_id captured from news_research_brief")
        executed["news_brief_detail"] = None

    forum_state = run("forum_create_post", {"title": "Truth post", "content": "probe"})
    post_id = None
    if isinstance(forum_state, dict):
        active_post = forum_state.get("active_post")
        if isinstance(active_post, dict):
            post_id = active_post.get("post_id")
        if not post_id:
            posts = forum_state.get("posts")
            if isinstance(posts, list) and posts and isinstance(posts[0], dict):
                post_id = posts[0].get("post_id")
    run("forum_reply", {"post_id": post_id, "content": "probe reply"})
    run("forum_repair_derivatives", {})

    # portfolio chain
    created = run("portfolio_create", {"name": "Truth Book"})
    created_id = created.get("active_portfolio_id") if isinstance(created, dict) else None
    if created_id:
        run("portfolio_book_detail", endpoint=f"/api/portfolio/books/{created_id}")
    else:
        failures.append("portfolio_book_detail: no portfolio id captured")
        executed["portfolio_book_detail"] = None
    run("portfolio_export")
    run("portfolio_load_demo", {})
    if created_id:
        run("portfolio_select", {"portfolio_id": created_id})
    run("portfolio_import", {
        "mode": "create_new",
        "portfolio": {
            "name": "Truth Import",
            "positions": [{"symbol": "AAPL", "quantity": 1, "avg_cost": 100}],
        },
    })
    run("portfolio_report", {})
    if created_id:
        run("portfolio_delete", {"portfolio_id": created_id, "confirm": True})

    # paper order chain: a MARKET fill first so the ledger has a position to link
    run("crypto_submit_paper_order", {
        "symbol": "BTCUSDT",
        "side": "BUY",
        "order_type": "MARKET",
        "quantity": "0.001",
    })
    run("portfolio_link_paper", {})
    order_state = run("crypto_submit_paper_order", {
        "symbol": "BTCUSDT",
        "side": "BUY",
        "order_type": "LIMIT",
        "quantity": "0.001",
        "limit_price": "1.00",
    })
    order_id = None
    if isinstance(order_state, dict):
        orders = order_state.get("orders")
        if isinstance(orders, list):
            order_id = next(
                (
                    row.get("order_id")
                    for row in orders
                    if isinstance(row, dict) and row.get("status") == "WORKING"
                ),
                None,
            )
    run("crypto_cancel_paper_order", {"order_id": order_id or "paper-missing"})
    # after the cancel no WORKING orders remain; the report still returns
    # every contract key (empty filled/skipped, remaining count 0)
    run("crypto_process_paper_orders", {})
    # refresh=False keeps the snapshot hermetic: no held equity symbols, no
    # benchmark fetch — the row records its own mark staleness instead
    run("paper_snapshot_record", {"refresh": False, "note": "truth probe"})

    # algo chain
    saved = run("algo_save_strategy", _STRATEGY_BODY)
    strategy_id = saved.get("active_strategy_id") if isinstance(saved, dict) else None
    run("algo_select_strategy", {"strategy_id": strategy_id})
    run("algo_scan", {
        "strategy_id": strategy_id,
        "symbols": "BTCUSDT",
        "timeframe": "15m",
        "lookback_days": 30,
    })
    run("algo_run_backtest", {"strategy_id": strategy_id})
    run("algo_scan_artifacts_repair", {})
    if strategy_id:
        run("algo_delete_strategy", {"strategy_id": strategy_id, "confirm": True})

    # backtest chain
    bt_run = run("backtest_run_closed_candle", {})
    bt_run_id = bt_run.get("run_id") if isinstance(bt_run, dict) else None
    if bt_run_id:
        run("backtest_run_detail", endpoint=f"/api/backtest/runs/{bt_run_id}")
    else:
        failures.append("backtest_run_detail: no run_id captured from backtest_run")
        executed["backtest_run_detail"] = None
    run("backtest_walk_forward_run", {"fold_count": 3})
    run("backtest_optimize", {"parameter_grid": {"fast_window": [3], "slow_window": [8]}})
    run("backtest_comparison_packet", {"max_runs": 2})
    run("portfolio_link_backtest", {})

    # governance / lifecycle local POSTs
    run("governance_diagnostics", {})
    run("artifact_lifecycle_archive_plan", {})

    # ---- generic sweep: any remaining local empty-body POST ----
    for action in ACTION_CONTRACTS:
        aid = action.action_id
        if aid in executed or aid in SKIP_REASONS or action.method != "POST":
            continue
        if _network_refresh(action.endpoint):
            continue
        if "empty" in action.request_contract.lower():
            run(aid)

    # ---- completeness guard: every action classified ----
    unclassified = [
        action.action_id
        for action in ACTION_CONTRACTS
        if action.action_id not in executed
        and action.action_id not in SKIP_REASONS
        and not _network_refresh(action.endpoint)
    ]
    assert not unclassified, (
        "New actions must be added to this truth test (run or skip with reason): "
        f"{unclassified}"
    )

    assert not failures, "contract-vs-response drift:\n" + "\n".join(failures)


def test_activity_event_contract_documents_the_state_enum() -> None:
    """The request_contract prose must name every accepted state (M26 S1.4)."""
    from otto.local_terminal.agent_activity import AGENT_ACTIVITY_STATES

    action = next(a for a in ACTION_CONTRACTS if a.action_id == "agent_activity_event")
    for state in sorted(AGENT_ACTIVITY_STATES):
        assert state in action.request_contract, f"state '{state}' undocumented"
