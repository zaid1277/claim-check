import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  testMatch: "article-url.flow.ts",
  timeout: 60_000,
  workers: 1,
  use: { baseURL: "http://127.0.0.1:3101", trace: "retain-on-failure" },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
    { name: "webkit", use: { ...devices["Desktop Safari"] } },
  ],
  webServer: [
    {
      command:
        "../api/.venv/bin/uvicorn article-api:app --app-dir e2e/fixtures --host 127.0.0.1 --port 8101",
      url: "http://127.0.0.1:8101/api/v1/health",
      env: { PROVIDER_MODE: "fixture", DATABASE_URL: "" },
    },
    {
      command: "node e2e/fixtures/article-web.mjs",
      url: "http://127.0.0.1:3101",
      env: { API_BASE_URL: "http://127.0.0.1:8101" },
    },
  ],
});
