import json
from pathlib import Path

import yaml

from otto.local_terminal.contracts import (
    DEFAULT_LOCAL_PROFILE_POLICY,
    DEFAULT_SAFETY_INVARIANTS,
    GLOBAL_MENUS,
    GLOBAL_MENUS_BY_ID,
    LOCAL_STORAGE_PATHS,
    SHELL_ROUTE_IDS,
    SHELL_ROUTES,
    is_repo_local_path,
)


EXPECTED_ROUTE_LABELS = (
    "Dashboard",
    "Markets",
    "Crypto",
    "Paper",
    "Portfolio",
    "News",
    "AI Chat",
    "Backtest",
    "Algo",
    "Nodes",
    "Code",
    "Quant Lab",
    "QuantLib",
    "Forum",
    "Settings",
    "Profile",
)


def test_phase0_shell_routes_are_complete_and_unique() -> None:
    labels = tuple(route.label for route in SHELL_ROUTES)
    route_ids = tuple(route.route_id for route in SHELL_ROUTES)
    paths = tuple(route.path for route in SHELL_ROUTES)

    assert labels == EXPECTED_ROUTE_LABELS
    assert len(SHELL_ROUTES) == 16
    assert len(route_ids) == len(set(route_ids))
    assert len(paths) == len(set(paths))
    assert all(path.startswith("/") for path in paths)


def test_global_menu_contract_contains_required_items() -> None:
    assert tuple(menu.label for menu in GLOBAL_MENUS) == ("File", "Navigate", "View", "Help")

    file_items = {item.item_id for item in GLOBAL_MENUS_BY_ID["file"].items}
    assert {
        "new_window",
        "new_layout",
        "open_layout",
        "save_layout",
        "save_layout_as",
        "import_layout",
        "export_layout",
        "file_manager",
        "refresh_all",
    }.issubset(file_items)

    navigate_route_ids = {
        item.route_id for item in GLOBAL_MENUS_BY_ID["navigate"].items if item.kind == "route"
    }
    assert navigate_route_ids == set(SHELL_ROUTE_IDS)

    view_items = {item.item_id for item in GLOBAL_MENUS_BY_ID["view"].items}
    assert {"fullscreen", "focus_mode", "float_panel", "quick_switch"}.issubset(view_items)

    help_items = {item.item_id for item in GLOBAL_MENUS_BY_ID["help"].items}
    assert {"local_docs", "help_center", "diagnostics", "about_local_terminal"}.issubset(
        help_items
    )
    assert not {"billing", "subscription", "credits", "cr"}.intersection(help_items)


def test_default_safety_contract_disables_prohibited_capabilities() -> None:
    assert DEFAULT_SAFETY_INVARIANTS.enabled_prohibited_capabilities() == ()
    assert DEFAULT_LOCAL_PROFILE_POLICY.enabled_remote_requirements() == ()


def test_config_example_does_not_enable_prohibited_capabilities() -> None:
    root = Path(__file__).resolve().parents[1]
    config = yaml.safe_load((root / "configs" / "local_terminal.example.yaml").read_text())

    assert config["app"]["mode"] == "local"
    assert config["safety"] == {
        "real_orders": False,
        "private_api_required": False,
        "margin": False,
        "leverage": False,
        "short": False,
        "derivatives_live_execution": False,
    }
    assert config["profile"] == {
        "cloud_account_required": False,
        "billing_enabled": False,
        "subscription_required": False,
        "cr_required": False,
        "credits_enabled": False,
    }
    assert config["features"]["nodes_execution"] is False
    assert config["features"]["code_execution"] is False
    assert config["features"]["quantlab_execution"] is False
    assert config["features"]["live_broker_sync"] is False


def test_local_profile_example_does_not_require_cloud_billing_or_cr() -> None:
    root = Path(__file__).resolve().parents[1]
    profile = json.loads((root / "settings" / "local_profile.example.json").read_text())

    assert profile["cloud_account_required"] is False
    assert profile["billing_enabled"] is False
    assert profile["subscription_required"] is False
    assert profile["cr_required"] is False
    assert profile["credits_enabled"] is False
    assert profile["private_api_required"] is False


def test_workspace_artifact_paths_stay_repo_local() -> None:
    root = Path(__file__).resolve().parents[1]
    config = yaml.safe_load((root / "configs" / "local_terminal.example.yaml").read_text())
    storage = config["storage"]
    configured_paths = (
        storage["settings_dir"],
        storage["workspace_layouts_dir"],
        storage["artifacts_dir"],
    )

    assert configured_paths == LOCAL_STORAGE_PATHS.values()
    assert all(is_repo_local_path(path) for path in configured_paths)
    assert all((root / path).resolve().is_relative_to(root.resolve()) for path in configured_paths)
