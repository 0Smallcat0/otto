// GIF v2: story-driven capture. Title card -> mission wall -> AI ACTIVITY close-ups
// while a real agent works -> highlighted new backtest run -> end card.
import { chromium } from "playwright";
import { mkdirSync, writeFileSync } from "node:fs";
import { spawn } from "node:child_process";

const BASE = "http://127.0.0.1:8765";
const OUT = "../artifacts/screenshots/m28/gif2";
mkdirSync(OUT, { recursive: true });

const mcpConfig = {
  mcpServers: {
    otto: {
      command: "../.venv/Scripts/python.exe",
      args: ["-m", "src.local_terminal.mcp_server"],
      env: { LOCAL_TERMINAL_URL: BASE, LOCAL_TERMINAL_MCP_AUTOSTART: "0", PYTHONPATH: "D:/Otto" },
    },
  },
};
writeFileSync("_gif2_mcp.json", JSON.stringify(mcpConfig));

const PROMPT =
  "You are operating the Otto local financial terminal through the otto MCP tools. " +
  "Step 1: write an agent activity event with action_id backtest_run_closed_candle, state planned, summary Starting SMA 6/14 cross study. " +
  "Step 2: run a closed-candle backtest for BTCUSDT on the 15m timeframe with the sma_cross strategy using fast_window 6 and slow_window 14. " +
  "Step 3: write an agent activity event for the same action id with state succeeded and a summary naming the run id and total return percent. " +
  "Answer with the run id and total return percent.";

const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2, colorScheme: "dark" });
await context.addInitScript(() => {
  window.localStorage.setItem("ft-lang", "en");
  window.localStorage.setItem("ft-theme", "dark");
});
const page = await context.newPage();

const card = async (path, title, lines, accent) => {
  await page.evaluate(([t, ls, ac]) => {
    const el = document.createElement("div");
    el.id = "story-card";
    el.innerHTML =
      `<div style="font:600 40px/1.3 'Cascadia Mono',Consolas,monospace;color:${ac};max-width:1100px">${t}</div>` +
      ls.map((l) => `<div style="font:22px/1.6 'Cascadia Mono',Consolas,monospace;color:#c9d1d9;margin-top:18px;max-width:1000px">${l}</div>`).join("");
    Object.assign(el.style, {
      position: "fixed", inset: "0", zIndex: "99999", background: "#0b0e13",
      display: "flex", flexDirection: "column", justifyContent: "center",
      alignItems: "center", textAlign: "center", padding: "60px",
    });
    document.body.appendChild(el);
  }, [title, lines, accent]);
  await page.screenshot({ path });
  await page.evaluate(() => document.getElementById("story-card")?.remove());
};

const banner = async (text) => {
  await page.evaluate((t) => {
    document.getElementById("story-banner")?.remove();
    const el = document.createElement("div");
    el.id = "story-banner";
    el.textContent = t;
    Object.assign(el.style, {
      position: "fixed", left: "0", right: "0", top: "0", zIndex: "99999",
      padding: "16px 26px", background: "#151a22", color: "#ffb347",
      font: "600 21px/1.4 'Cascadia Mono',Consolas,monospace", borderBottom: "2px solid #ffb347",
    });
    document.body.appendChild(el);
  }, text);
};

const activityClip = async () => {
  const box = await page.evaluate(() => {
    const nodes = [...document.querySelectorAll("div,section,h1,h2,h3,span")];
    const head = nodes.find((n) => (n.textContent || "").trim().replace(/\s+/g, " ").toUpperCase().startsWith("AI ACTIVITY") && (n.textContent || "").length < 40);
    let panel = head || null;
    for (let i = 0; i < 8 && panel; i += 1) {
      const r = panel.getBoundingClientRect();
      if (r.height > 380 && r.width > 500) return { x: r.x, y: r.y, width: r.width, height: r.height };
      panel = panel.parentElement;
    }
    return null;
  });
  if (box) {
    return { x: Math.max(0, box.x - 8), y: Math.max(0, box.y - 8), width: Math.min(box.width + 16, 1440), height: Math.min(box.height + 16, 900) };
  }
  return { x: 400, y: 300, width: 760, height: 580 };
};

await page.goto(BASE + "/", { waitUntil: "networkidle", timeout: 60000 });
await page.waitForTimeout(2500);

// 0. title card
await card(`${OUT}/f000.png`,
  '&gt; you: "run an SMA-cross backtest on BTCUSDT 15m and log your steps"',
  ["Otto has no forms to fill. You say it once —", "an AI agent operates the terminal through MCP tools.", "Watch the AI ACTIVITY feed on the dashboard."],
  "#ffb347");

// 1. mission wall, oriented
await banner("Mission wall — the human view. The agent is about to work; watch AI ACTIVITY (center).");
await page.screenshot({ path: `${OUT}/f001.png` });

// 2. spawn the real agent
const claude = spawn("cmd", ["/c", "claude", "-p", PROMPT, "--output-format", "json",
  "--model", "claude-haiku-4-5-20251001", "--max-turns", "14",
  "--mcp-config", "_gif2_mcp.json", "--strict-mcp-config",
  "--allowedTools", "mcp__otto", "--setting-sources", ""], { cwd: process.cwd() });
let done = false;
claude.on("exit", () => { done = true; });

// 3. activity close-ups while the agent works
let index = 2;
const started = Date.now();
while (!done && Date.now() - started < 150000 && index < 40) {
  await page.reload({ waitUntil: "networkidle" }).catch(() => {});
  await page.waitForTimeout(1200);
  await banner("A real agent is working now — each ✓ lands in this feed as it acts.");
  const clip = await activityClip();
  await page.screenshot({ path: `${OUT}/f${String(index).padStart(3, "0")}.png`, clip });
  index += 1;
  await page.waitForTimeout(1800);
}

// 4. final activity state
await page.reload({ waitUntil: "networkidle" }).catch(() => {});
await page.waitForTimeout(2000);
await banner("Done — planned ➜ ran backtest ➜ succeeded, all logged by the agent itself.");
const clip = await activityClip();
await page.screenshot({ path: `${OUT}/f${String(index).padStart(3, "0")}.png`, clip });
const finalActivityIdx = index;
index += 1;

// 5. backtests page, newest run highlighted
await page.click('[data-testid="route-button-backtest"]');
await page.waitForTimeout(3000);
await banner("The run landed on the Backtests wall with a full artifact report.");
await page.evaluate(() => {
  const row = document.querySelector("table tbody tr, [class*=row]");
  if (row) { row.style.outline = "3px solid #ffb347"; row.style.outlineOffset = "-3px"; }
});
await page.screenshot({ path: `${OUT}/f${String(index).padStart(3, "0")}.png` });
index += 1;

// 6. end card (numbers filled by assembler after reading claude output)
await card(`${OUT}/f${String(index).padStart(3, "0")}.png`,
  "One sentence in — a graded, auditable run out.",
  ["Every action passed through the safety contract:", "LIVE OFF and EXEC OFF are structural, not settings.", "20-task agent benchmark: sonnet 20/20 · haiku 19/20 — see evals/EVAL.md"],
  "#7ee08a");

console.log("frames", index + 1, "agentDone", done, "finalActivityIdx", finalActivityIdx);
await browser.close();
