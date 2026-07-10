import { chromium } from "playwright";
import { mkdirSync } from "node:fs";

const BASE = "http://127.0.0.1:8765";
const OUT = "../artifacts/screenshots/m28";
const ROUTES = ["dashboard", "markets", "backtest", "portfolio", "news", "paper"];

mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch();
const context = await browser.newContext({
  viewport: { width: 1600, height: 900 },
  deviceScaleFactor: 2,
  colorScheme: "dark",
});
await context.addInitScript(() => {
  window.localStorage.setItem("ft-lang", "en");
  window.localStorage.setItem("ft-theme", "dark");
});
const page = await context.newPage();
await page.goto(BASE + "/", { waitUntil: "networkidle", timeout: 60000 });
await page.waitForTimeout(2000);
for (const id of ROUTES) {
  await page.click(`[data-testid="route-button-${id}"]`, { timeout: 15000 });
  await page.waitForTimeout(3500);
  await page.screenshot({ path: `${OUT}/${id}.png` });
  console.log("shot", id);
}
await browser.close();
