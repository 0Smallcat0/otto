// Shell route registry. route_id/path pairs mirror the backend agent-contract
// ROUTE_CONTRACTS — the 16 hash routes survive the M27 teardown as contract
// anchors even though every page behind them was rebuilt.

export interface ShellRoute {
  route_id: string;
  label: string;
  path: string;
}

// Routes the AI operates through the API but a person never needs to open.
// Hidden from the human sidebar; still routable by #/<id> hash.
// R4: profile merged into Settings for humans; the route stays for the contract.
export const AI_OPERATOR_ROUTES = new Set(["nodes", "code", "quant_lab", "quantlib", "ai_chat", "forum", "profile"]);

export const fallbackRoutes: ShellRoute[] = [
  { route_id: "dashboard", label: "Dashboard", path: "/dashboard" },
  { route_id: "markets", label: "Markets", path: "/markets" },
  { route_id: "crypto", label: "Crypto", path: "/crypto" },
  { route_id: "paper", label: "Paper", path: "/paper" },
  { route_id: "portfolio", label: "Portfolio", path: "/portfolio" },
  { route_id: "news", label: "News", path: "/news" },
  { route_id: "ai_chat", label: "AI Chat", path: "/ai-chat" },
  { route_id: "backtest", label: "Backtest", path: "/backtest" },
  { route_id: "algo", label: "Algo", path: "/algo" },
  { route_id: "nodes", label: "Nodes", path: "/nodes" },
  { route_id: "code", label: "Code", path: "/code" },
  { route_id: "quant_lab", label: "Quant Lab", path: "/quant-lab" },
  { route_id: "quantlib", label: "QuantLib", path: "/quantlib" },
  { route_id: "forum", label: "Forum", path: "/forum" },
  { route_id: "settings", label: "Settings", path: "/settings" },
  { route_id: "profile", label: "Profile", path: "/profile" }
];
