import { chromium } from "playwright";
import { mkdirSync, writeFileSync } from "node:fs";
import { spawn } from "node:child_process";

const BASE = "http://127.0.0.1:8765";
const OUT = "../artifacts/screenshots/m28/gif-frames";
mkdirSync(OUT, { recursive: true });

const mcpConfig = {
  mcpServers: {
    otto: {
      command: process.env.PYTHON || "../.venv/Scripts/python.exe",
      args: ["-m", "otto.local_terminal.mcp_server"],
      env: { LOCAL_TERMINAL_URL: BASE, LOCAL_TERMINAL_MCP_AUTOSTART: "0", PYTHONPATH: "D:/Otto" },
    },
  },
};
writeFileSync("_m28_mcp.json", JSON.stringify(mcpConfig));

const PROMPT =
  "You are operating the Otto local financial terminal through the otto MCP tools. " +
  "First write an agent activity event with action_id backtest_run_closed_candle and state planned and summary Starting SMA cross study. " +
  "Then run a closed-candle backtest for BTCUSDT on the 15m timeframe with the sma_cross strategy using fast_window 4 and slow_window 9. " +
  "Then write an agent activity event for the same action id with state succeeded and a one-line summary that includes the run id. " +
  "Answer with the run id and total return percent.";

const browser = await chromium.launch();
const context = await browser.newContext({
  viewport: { width: 1600, height: 900 },
  deviceScaleFactor: 1,
  colorScheme: "dark",
});
await context.addInitScript(() => {
  window.localStorage.setItem("ft-lang", "en");
  window.localStorage.setItem("ft-theme", "dark");
});
const page = await context.newPage();
await page.goto(BASE + "/", { waitUntil: "networkidle", timeout: 60000 });
await page.click('[data-testid="route-button-backtest"]');
await page.waitForTimeout(2500);
await page.evaluate(() => {
  const bar = document.createElement("div");
  bar.id = "demo-bar";
  bar.textContent =
    '> you: "run an SMA-cross backtest on BTCUSDT 15m and log your steps"   -- Otto is operated by the AI agent; this dashboard just watches.';
  Object.assign(bar.style, {
    position: "fixed", left: "0", right: "0", bottom: "0", zIndex: "9999",
    padding: "14px 22px", background: "rgba(10,12,16,0.92)", color: "#ffb347",
    font: "16px/1.4 'Cascadia Mono', Consolas, monospace",
    borderTop: "1px solid #333",
  });
  document.body.appendChild(bar);
});

const claude = spawn(
  "cmd",
  ["/c", "claude", "-p", PROMPT, "--output-format", "json", "--model", "claude-haiku-4-5-20251001",
   "--max-turns", "14", "--mcp-config", "_m28_mcp.json", "--strict-mcp-config",
   "--allowedTools", "mcp__otto", "--setting-sources", ""],
  { cwd: process.cwd() }
);
let done = false;
claude.on("exit", () => { done = true; });

let index = 0;
const started = Date.now();
while (!done && Date.now() - started < 150000) {
  await page.screenshot({ path: `${OUT}/f${String(index).padStart(3, "0")}.png` });
  index += 1;
  await page.waitForTimeout(1200);
}
// A few settle frames after the agent finishes, so the new run row is visible.
for (let extra = 0; extra < 6; extra += 1) {
  await page.waitForTimeout(1500);
  await page.screenshot({ path: `${OUT}/f${String(index).padStart(3, "0")}.png` });
  index += 1;
}
console.log("frames", index, "agentDone", done);
await browser.close();
