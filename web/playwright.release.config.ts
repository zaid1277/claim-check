import { defineConfig } from "@playwright/test";
import article from "./playwright.article.config";

// Run every browser flow in isolated servers, including Safari's engine.
export default defineConfig({
  ...article,
  testMatch: ["flows.spec.ts", "article-url.flow.ts"],
  timeout: 90_000,
  expect: { timeout: 45_000 },
});
