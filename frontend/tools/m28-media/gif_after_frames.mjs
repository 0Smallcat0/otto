import { chromium } from "playwright";
const OUT = "../artifacts/screenshots/m28/gif-frames";
const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 1600, height: 900 }, colorScheme: "dark" });
await context.addInitScript(() => {
  window.localStorage.setItem("ft-lang", "en");
  window.localStorage.setItem("ft-theme", "dark");
});
const page = await context.newPage();
await page.goto("http://127.0.0.1:8765/", { waitUntil: "networkidle", timeout: 60000 });
await page.click('[data-testid="route-button-backtest"]');
await page.waitForTimeout(3500);
await page.evaluate(() => {
  const bar = document.createElement("div");
  bar.textContent =
    '> agent: done -- run bt-20260710100600 landed, +0.09% total return, report written.   LIVE stays OFF; paper and research only.';
  Object.assign(bar.style, {
    position: "fixed", left: "0", right: "0", bottom: "0", zIndex: "9999",
    padding: "14px 22px", background: "rgba(10,12,16,0.92)", color: "#7ee08a",
    font: "16px/1.4 'Cascadia Mono', Consolas, monospace", borderTop: "1px solid #333",
  });
  document.body.appendChild(bar);
});
for (let i = 31; i < 39; i += 1) {
  await page.screenshot({ path: `${OUT}/f${String(i).padStart(3, "0")}.png` });
  await page.waitForTimeout(800);
}
console.log("after-frames done");
await browser.close();
