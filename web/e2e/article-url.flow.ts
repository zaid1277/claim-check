import { test, expect } from "@playwright/test";

const url = "https://en.wikipedia.org/wiki/Eiffel_Tower";
for (const count of [1, 5]) {
  test(`article URL creates and renders ${count} selected claims across a slow API`, async ({
    page,
  }) => {
    await page.goto("/");
    await page.getByRole("radio", { name: "Article URL", exact: true }).check();
    await page.getByLabel("Public article URL").fill(url);
    await page.getByRole("button", { name: "Propose claims" }).click();
    await expect(
      page.getByRole("heading", { name: "Review the claims" }),
    ).toBeVisible();
    const claims = await page
      .getByRole("textbox", { name: /Edit claim/ })
      .evaluateAll((nodes) =>
        nodes.map((node) => (node as HTMLTextAreaElement).value),
      );
    expect(claims).toHaveLength(5);
    for (let i = count + 1; i <= 5; i++) {
      await page
        .getByLabel(`Investigate claim ${i}`, { exact: true })
        .uncheck();
    }
    const responsePromise = page.waitForResponse(
      (response) =>
        response.url().endsWith("/api/v1/investigations") &&
        response.request().method() === "POST",
      { timeout: 45_000 },
    );
    await page
      .getByRole("button", { name: "Investigate selected claims" })
      .click();
    const response = await responsePromise;
    expect(response.request().postDataJSON()).toMatchObject({
      input_type: "url",
      source_url: url,
      claims: claims.slice(0, count),
    });
    expect(response.status()).toBe(200);
    const investigation = await response.json();
    expect(investigation.assessments).toHaveLength(count);
    await expect(
      page.getByRole("heading", { name: "Investigation result", exact: true }),
    ).toBeVisible();
    await expect(page.getByRole("main").getByRole("alert")).toHaveCount(0);
    await page.goto(`/investigations/${encodeURIComponent(investigation.id)}`);
    await expect(
      page.getByRole("heading", { name: "Evidence report", exact: true }),
    ).toBeVisible();
    for (const claim of claims.slice(0, count)) {
      await expect(
        page.getByRole("heading", { name: claim, exact: true }),
      ).toBeVisible();
    }
  });
}
