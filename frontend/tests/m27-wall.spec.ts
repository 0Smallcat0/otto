import { expect, test } from "@playwright/test";

// M27 AI-first shell — the terminal is operated by the AI through /api; the
// browser UI is a read-only mission wall. These tests run against an isolated
// LOCAL_TERMINAL_STATE_ROOT (see playwright.config.ts), i.e. a FRESH terminal:
// default paper account, empty caches, empty activity journal.

// Page H1 mirrors the sidebar — the localized ROUTE_ZH label (default lang = zh).
const HUMAN_ROUTES: Array<{ id: string; path: string; heading: string }> = [
  { id: "dashboard", path: "dashboard", heading: "任務牆" },
  { id: "markets", path: "markets", heading: "行情" },
  { id: "crypto", path: "crypto", heading: "加密" },
  { id: "paper", path: "paper", heading: "紙上交易" },
  { id: "portfolio", path: "portfolio", heading: "帳本" },
  { id: "news", path: "news", heading: "新聞" },
  { id: "backtest", path: "backtest", heading: "回測" },
  { id: "algo", path: "algo", heading: "策略研究" },
  { id: "settings", path: "settings", heading: "系統" }
];

// Hidden from the sidebar (AI-operated), still routable by hash.
const AI_ROUTES: Array<{ id: string; path: string }> = [
  { id: "profile", path: "profile" }, // merged into Settings for humans (R4)
  { id: "ai_chat", path: "ai-chat" },
  { id: "nodes", path: "nodes" },
  { id: "code", path: "code" },
  { id: "quant_lab", path: "quant-lab" },
  { id: "quantlib", path: "quantlib" },
  { id: "forum", path: "forum" }
];

test("mission wall renders shell, equity banner, and the three columns", async ({ page }) => {
  await page.goto("/#/dashboard");
  await expect(page.getByTestId("shell-topstrip")).toContainText("OTTO");
  await expect(page.getByTestId("shell-topstrip")).toContainText("實盤");
  await expect(page.getByTestId("workspace-dashboard")).toBeVisible();

  // FreqUI convention: P&L is a first-class citizen. Fresh paper book = 100,000 start.
  const equity = page.getByTestId("wall-equity");
  await expect(equity).toContainText("帳戶權益");
  await expect(equity).toContainText("100,000");

  await expect(page.getByTestId("wall-quotes")).toContainText("報價監視");
  await expect(page.getByTestId("wall-activity")).toContainText("AI 動態");
  await expect(page.getByTestId("wall-news")).toContainText("頭條");

  // Fresh terminal: empty journal shows the conversational call-to-action.
  await expect(page.getByTestId("wall-activity")).toContainText("尚無活動");
});

test("sidebar lists human routes only; AI-operated routes stay hidden", async ({ page }) => {
  await page.goto("/#/dashboard");
  for (const route of HUMAN_ROUTES) {
    await expect(page.getByTestId(`route-button-${route.path}`)).toBeVisible();
  }
  for (const route of AI_ROUTES) {
    await expect(page.getByTestId(`route-button-${route.path}`)).toHaveCount(0);
  }
});

test("every human route navigates to its workspace with the contract heading", async ({ page }) => {
  await page.goto("/#/dashboard");
  for (const route of HUMAN_ROUTES) {
    await page.getByTestId(`route-button-${route.path}`).click();
    const workspace = page.getByTestId(`workspace-${route.path}`);
    await expect(workspace).toBeVisible();
    await expect(workspace.locator("h1").first()).toHaveText(route.heading);
  }
});

test("AI-operated routes remain reachable by hash for deep links", async ({ page }) => {
  for (const route of AI_ROUTES) {
    await page.goto(`/#/${route.id}`);
    await expect(page.getByTestId(`workspace-${route.path}`)).toBeVisible();
  }
});

test("theme toggle flips the document theme and back", async ({ page }) => {
  await page.goto("/#/dashboard");
  const initial = await page.evaluate(() => document.documentElement.dataset.theme);
  await page.getByTestId("theme-toggle").click();
  const flipped = await page.evaluate(() => document.documentElement.dataset.theme);
  expect(flipped).not.toBe(initial);
  await page.getByTestId("theme-toggle").click();
  const restored = await page.evaluate(() => document.documentElement.dataset.theme);
  expect(restored).toBe(initial);
});

test("fresh terminal shows no alerts and reports zero actions today", async ({ page }) => {
  await page.goto("/#/dashboard");
  await expect(page.getByTestId("shell-alerts")).toContainText("無警示");
  await expect(page.getByTestId("wall-activity")).toContainText("今日 0 動作");
});
