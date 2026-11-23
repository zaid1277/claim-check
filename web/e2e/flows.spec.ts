import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const demo = "The demonstration library opens on Sundays.";
test("typed claim, keyboard, real fixture API, and share report", async ({
  page,
}) => {
  await page.goto("/");
  if (process.env.CAPTURE_SCREENSHOTS) {
    await page.getByLabel("Claim to investigate").waitFor();
    await page.screenshot({
      path: "../docs/screenshots/new-check.png",
      fullPage: true,
    });
  }
  await page.getByLabel("Claim to investigate").fill(demo);
  await page.getByRole("button", { name: "Check claim", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "SUPPORTED", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText(
      "Demonstration fixtures — not live research or a real-world assessment.",
    ),
  ).toBeVisible();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.getByRole("button", { name: "Publish share link" }).click();
  await page.getByRole("link", { name: "Open shareable report" }).click();
  await expect(page.getByText("Read-only evidence report")).toBeVisible();
  if (process.env.CAPTURE_SCREENSHOTS)
    await page.screenshot({
      path: "../docs/screenshots/report.png",
      fullPage: true,
    });
  await expect(
    page.getByRole("button", { name: "Publish share link" }),
  ).toHaveCount(0);
});

test("URL extraction mock requires editable claim selection", async ({
  page,
}) => {
  await page.route("**/api/v1/inputs/url", (route) =>
    route.fulfill({ json: { text: demo, claims: [demo] } }),
  );
  await page.goto("/?url=https%3A%2F%2Fexample.org%2Farticle");
  await page.getByRole("button", { name: "Propose claims" }).click();
  await expect(page.getByLabel("Edit claim 1")).toHaveValue(demo);
  if (process.env.CAPTURE_SCREENSHOTS)
    await page.screenshot({
      path: "../docs/screenshots/claim-selection.png",
      fullPage: true,
    });
  await page
    .getByLabel("Edit claim 1")
    .fill("A different claim with no fixture evidence.");
  await page
    .getByRole("button", { name: "Investigate selected claims" })
    .click();
  await expect(
    page.getByRole("heading", { name: "INSUFFICIENT EVIDENCE", exact: true }),
  ).toBeVisible();
});

test("OCR mock requires correction before investigation", async ({ page }) => {
  await page.route("**/api/v1/inputs/image", (route) =>
    route.fulfill({
      json: {
        text: "The demonstratlon library opens on Sundays.",
        review_required: true,
      },
    }),
  );
  await page.goto("/");
  await page.getByRole("radio", { name: "Screenshot / image" }).check();
  await page.getByLabel("PNG or JPEG image (up to 5 MB)").setInputFiles({
    name: "test.png",
    mimeType: "image/png",
    buffer: Buffer.from("mocked upload"),
  });
  await page.getByRole("button", { name: "Read image text" }).click();
  await expect(page.getByText(/Correct OCR mistakes/)).toBeVisible();
  await page.getByLabel("Article text").fill(demo);
  const proposalRequest = page.waitForRequest(
    (request) =>
      request.url().endsWith("/inputs/text") && request.method() === "POST",
  );
  await page.getByRole("button", { name: "Propose claims" }).click();
  expect((await proposalRequest).postDataJSON()).toEqual({ text: demo });
  const investigationRequest = page.waitForRequest(
    (request) =>
      request.url().endsWith("/investigations") && request.method() === "POST",
  );
  await page
    .getByRole("button", { name: "Investigate selected claims" })
    .click();
  await expect(
    page.getByRole("heading", { name: "SUPPORTED", exact: true }),
  ).toBeVisible();
  expect((await investigationRequest).postDataJSON()).toMatchObject({
    claims: [demo],
    raw_text: demo,
    input_type: "image",
  });
});

test("responsive input surface and URL failure fallback", async ({
  page,
  browserName,
}) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto("/");
  await page.getByLabel("Claim to investigate").waitFor();
  // macOS WebKit uses Option-Tab to include links in keyboard navigation.
  await page.keyboard.press(
    browserName === "webkit" && process.platform === "darwin"
      ? "Alt+Tab"
      : "Tab",
  );
  await expect(
    page.getByRole("link", { name: "Skip to content" }),
  ).toBeFocused();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.getByRole("radio", { name: "Article URL" }).check();
  await page.getByLabel("Public article URL").fill("http://127.0.0.1");
  await page.getByRole("button", { name: "Propose claims" }).click();
  await expect(page.getByRole("main").getByRole("alert")).toBeVisible();
  await page.getByRole("radio", { name: "Pasted article" }).check();
  await expect(page.getByLabel("Article text")).toBeVisible();
});

test("local setup, invalid credentials, and transition are accessible", async ({
  page,
}) => {
  const setup = {
    ready: false,
    mode: "live",
    runtime_keys_allowed: true,
    database_configured: true,
    providers: { search: { configured: false, provider: "tavily" } },
  };
  await page.route("**/api/v1/setup/status", (route) =>
    route.fulfill({ json: setup }),
  );
  await page.route("**/api/v1/setup/providers", (route) =>
    route.fulfill({
      status: 502,
      json: { error: { message: "Tavily rejected this API key." } },
    }),
  );
  await page.goto("/");
  await expect(page.getByLabel("Tavily API key")).toBeVisible();
  await page.getByRole("radio", { name: "Brave", exact: true }).check();
  await expect(page.getByLabel("Brave API key")).toBeVisible();
  await page.getByRole("radio", { name: "Tavily", exact: true }).check();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  if (process.env.CAPTURE_SCREENSHOTS)
    await page.screenshot({
      path: "../docs/screenshots/setup.png",
      fullPage: true,
    });
  await page.getByLabel("Tavily API key").fill("invalid-test-example");
  await page.getByRole("button", { name: "Validate and continue" }).click();
  await expect(page.getByRole("main").getByRole("alert")).toContainText(
    "rejected",
  );
  await expect(page.getByLabel("Tavily API key")).toHaveValue("");
  await page.route("**/api/v1/setup/providers", (route) =>
    route.fulfill({ json: { ...setup, ready: true } }),
  );
  await page.getByLabel("Tavily API key").fill("valid-test-example");
  await page.getByRole("button", { name: "Validate and continue" }).click();
  await expect(page.getByLabel("Claim to investigate")).toBeVisible();
});
