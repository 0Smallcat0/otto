"""Phase 0 contracts for the clean-room local terminal shell."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath, PureWindowsPath


@dataclass(frozen=True)
class ShellRoute:
    route_id: str
    label: str
    path: str


@dataclass(frozen=True)
class MenuItem:
    item_id: str
    label: str
    kind: str = "command"
    route_id: str | None = None
    enabled: bool = True


@dataclass(frozen=True)
class MenuSection:
    section_id: str
    label: str
    items: tuple[MenuItem, ...]


@dataclass(frozen=True)
class LocalStoragePaths:
    settings: str = "settings"
    workspace_layouts: str = "workspace_layouts"
    artifacts: str = "artifacts"

    def values(self) -> tuple[str, ...]:
        return (self.settings, self.workspace_layouts, self.artifacts)


@dataclass(frozen=True)
class SafetyInvariants:
    real_orders: bool = False
    private_api_required: bool = False
    margin: bool = False
    leverage: bool = False
    short: bool = False
    derivatives_live_execution: bool = False

    def enabled_prohibited_capabilities(self) -> tuple[str, ...]:
        return tuple(name for name, value in vars(self).items() if value)


@dataclass(frozen=True)
class LocalProfilePolicy:
    cloud_account_required: bool = False
    billing_enabled: bool = False
    subscription_required: bool = False
    cr_required: bool = False
    credits_enabled: bool = False
    private_api_required: bool = False

    def enabled_remote_requirements(self) -> tuple[str, ...]:
        return tuple(name for name, value in vars(self).items() if value)


SHELL_ROUTES: tuple[ShellRoute, ...] = (
    ShellRoute("dashboard", "Dashboard", "/dashboard"),
    ShellRoute("markets", "Markets", "/markets"),
    ShellRoute("crypto", "Crypto", "/crypto"),
    ShellRoute("paper", "Paper", "/paper"),
    ShellRoute("portfolio", "Portfolio", "/portfolio"),
    ShellRoute("news", "News", "/news"),
    ShellRoute("ai_chat", "AI Chat", "/ai-chat"),
    ShellRoute("backtest", "Backtest", "/backtest"),
    ShellRoute("algo", "Algo", "/algo"),
    ShellRoute("nodes", "Nodes", "/nodes"),
    ShellRoute("code", "Code", "/code"),
    ShellRoute("quant_lab", "Quant Lab", "/quant-lab"),
    ShellRoute("quantlib", "QuantLib", "/quantlib"),
    ShellRoute("forum", "Forum", "/forum"),
    ShellRoute("settings", "Settings", "/settings"),
    ShellRoute("profile", "Profile", "/profile"),
)

SHELL_ROUTE_IDS: tuple[str, ...] = tuple(route.route_id for route in SHELL_ROUTES)
SHELL_ROUTES_BY_ID: dict[str, ShellRoute] = {route.route_id: route for route in SHELL_ROUTES}


def _command(item_id: str, label: str, *, enabled: bool = True) -> MenuItem:
    return MenuItem(item_id=item_id, label=label, enabled=enabled)


def _route(route_id: str) -> MenuItem:
    route = SHELL_ROUTES_BY_ID[route_id]
    return MenuItem(item_id=route.route_id, label=route.label, kind="route", route_id=route_id)


GLOBAL_MENUS: tuple[MenuSection, ...] = (
    MenuSection(
        "file",
        "File",
        (
            _command("new_window", "New Window"),
            _command("move_to_monitor", "Move to Monitor"),
            _command("new_layout", "New Layout"),
            _command("open_layout", "Open Layout"),
            _command("save_layout", "Save Layout"),
            _command("save_layout_as", "Save Layout As"),
            _command("import_layout", "Import Layout"),
            _command("export_layout", "Export Layout"),
            _command("file_manager", "File Manager"),
            _command("refresh_all", "Refresh All"),
        ),
    ),
    MenuSection(
        "navigate",
        "Navigate",
        tuple(_route(route_id) for route_id in SHELL_ROUTE_IDS),
    ),
    MenuSection(
        "view",
        "View",
        (
            _command("component_browser", "Component Browser"),
            _command("fullscreen", "Fullscreen"),
            _command("focus_mode", "Focus Mode"),
            _command("always_on_top", "Always on Top"),
            _command("float_panel", "Float Panel"),
            _command("quick_switch", "Quick Switch"),
            _command("refresh_screen", "Refresh Screen"),
            _command("take_screenshot", "Take Screenshot"),
        ),
    ),
    MenuSection(
        "help",
        "Help",
        (
            _command("local_docs", "Local Docs"),
            _command("help_center", "Help Center"),
            _command("diagnostics", "Diagnostics"),
            _command("about_local_terminal", "About Local Terminal"),
            _command("local_terms", "Local Terms"),
            _command("local_privacy", "Local Privacy"),
            _command("attributions", "Attributions"),
            _command("check_for_updates", "Check for Updates"),
            _command("switch_local_profile", "Switch Local Profile"),
        ),
    ),
)

GLOBAL_MENUS_BY_ID: dict[str, MenuSection] = {menu.section_id: menu for menu in GLOBAL_MENUS}
LOCAL_STORAGE_PATHS = LocalStoragePaths()
DEFAULT_SAFETY_INVARIANTS = SafetyInvariants()
DEFAULT_LOCAL_PROFILE_POLICY = LocalProfilePolicy()


def is_repo_local_path(raw_path: str) -> bool:
    value = raw_path.strip()
    if not value or "://" in value or value.startswith("~"):
        return False

    windows_path = PureWindowsPath(value)
    posix_path = PurePosixPath(value)
    return (
        not windows_path.is_absolute()
        and not posix_path.is_absolute()
        and not windows_path.drive
        and ".." not in windows_path.parts
        and ".." not in posix_path.parts
    )
