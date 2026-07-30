import { defineConfig, devices } from "@playwright/test";

const stateRoot = `.omx/playwright-state-${Date.now()}`;

export default defineConfig({
  testDir: "./tests",
  // tests/unit is vitest's. Without this Playwright loads those files, calls
  // its own describe on them and dies before running a single browser test.
  testMatch: "**/*.spec.ts",
  timeout: 30_000,
  expect: {
    timeout: 10_000
  },
  use: {
    baseURL: "http://127.0.0.1:5173",
    trace: "on-first-retry"
  },
  webServer: [
    {
      command:
        ".\\.venv\\Scripts\\python.exe -m uvicorn otto.local_terminal.server:app --host 127.0.0.1 --port 8765",
      cwd: "..",
      env: {
        ...process.env,
        LOCAL_TERMINAL_STATE_ROOT: stateRoot
      },
      url: "http://127.0.0.1:8765/api/health",
      reuseExistingServer: false,
      timeout: 30_000
    },
    {
      command: "npm run dev -- --host 127.0.0.1 --port 5173",
      url: "http://127.0.0.1:5173",
      reuseExistingServer: false,
      timeout: 30_000
    }
  ],
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] }
    }
  ]
});
