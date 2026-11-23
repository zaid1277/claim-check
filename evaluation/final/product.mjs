// Each attempted case is journalled once, including errors. No final-case retries.
import { chromium } from "../../web/node_modules/playwright/index.mjs";
import { readFileSync, appendFileSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { resolve } from "node:path";
const root = fileURLToPath(new URL(".", import.meta.url));
const mode = process.argv[2] || "controlled";
if (mode !== "smoke" && !existsSync(root + "lock.json"))
  throw Error("Final lock required");
if (mode !== "smoke") {
  const lock = JSON.parse(readFileSync(root + "lock.json"));
  for (const [name, expected] of Object.entries(lock.files)) {
    const actual = createHash("sha256")
      .update(readFileSync(resolve(root, "../..", name)))
      .digest("hex");
    assert.equal(actual, expected, `Frozen file changed: ${name}`);
  }
}
const journal = root + `results/product-${mode}.jsonl`;
const finished = new Set(
  existsSync(journal)
    ? readFileSync(journal, "utf8")
        .trim()
        .split("\n")
        .filter(Boolean)
        .map((x) => JSON.parse(x).key)
    : [],
);
const api = "http://127.0.0.1:8102";
const web = "http://127.0.0.1:3102";
async function request(path, body, method = "POST") {
  const response = await fetch(api + path, {
    method,
    headers: { "Content-Type": "application/json" },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    signal: AbortSignal.timeout(360000),
  });
  const data = await response.json();
  if (!response.ok)
    throw Error(`HTTP ${response.status}: ${JSON.stringify(data)}`);
  return data;
}
const identity = await request("/evaluation/trace", undefined, "GET");
assert.equal(identity.variant, mode === "baseline" ? "pass2" : "candidate");
assert.equal(identity.stage, mode === "smoke" ? "development" : "final");
const browser = await chromium.launch();
const page = await browser.newPage();
page.setDefaultTimeout(150000);
async function rendered(result, share = false) {
  const saved = await request(
    "/api/v1/investigations/" + result.id,
    undefined,
    "GET",
  );
  assert.deepEqual(saved.assessments, result.assessments);
  await page.goto(web + "/investigations/" + result.id);
  await page
    .getByRole("heading", { name: "Evidence report", exact: true })
    .waitFor();
  const sections = page.locator(".assessment");
  assert.equal(await sections.count(), result.assessments.length);
  for (const [i, assessment] of result.assessments.entries()) {
    assert.equal(
      await sections.nth(i).locator("h3").first().innerText(),
      assessment.verdict.replaceAll("_", " "),
    );
    for (const [j, stance] of ["contradict", "support", "neutral"].entries()) {
      const passages = await sections
        .nth(i)
        .locator(".evidence-group")
        .nth(j)
        .locator("blockquote")
        .allTextContents();
      assert.deepEqual(
        passages,
        assessment.evidence
          .filter((e) => e.stance === stance)
          .map((e) => e.passage),
      );
    }
  }
  if (share) {
    const published = await request(
      `/api/v1/investigations/${result.id}/share`,
      {},
    );
    const shared = await request(
      "/api/v1/reports/" + published.share_slug,
      undefined,
      "GET",
    );
    assert.deepEqual(shared.assessments, result.assessments);
    await page.goto(web + "/reports/" + published.share_slug);
    await page
      .getByText("Read-only evidence report", { exact: true })
      .waitFor();
  }
  return { persisted: true, rendered: true, shared: share };
}
async function submitButton(name) {
  const response = page.waitForResponse(
    (r) =>
      r.url().endsWith("/api/v1/investigations") &&
      r.request().method() === "POST",
  );
  // A timeout here still surfaces via the await below; this only stops a slow
  // page interaction from crashing the whole run as an unhandled rejection.
  response.catch(() => {});
  await page.getByRole("button", { name, exact: true }).click();
  const resolved = await response;
  const body = await resolved.json();
  if (!resolved.ok()) throw Error(JSON.stringify(body));
  return body;
}
async function attempt(key, details, fn) {
  if (finished.has(key)) return;
  const start = performance.now();
  let result;
  try {
    result = { success: true, ...(await fn()) };
  } catch (error) {
    result = { success: false, error: String(error) };
  }
  const trace = await request("/evaluation/trace", undefined, "GET").catch(
    () => ({}),
  );
  appendFileSync(
    journal,
    JSON.stringify({
      key,
      ...details,
      ...result,
      seconds: (performance.now() - start) / 1000,
      trace,
    }) + "\n",
  );
  console.log(key, result.success ? "completed" : "FAILED");
  // Pace test traffic below the API limit; exclude pacing from measured latency.
  await new Promise((resolve) =>
    setTimeout(resolve, Math.max(0, 1000 - (performance.now() - start))),
  );
}
const cases =
  mode === "smoke"
    ? JSON.parse(readFileSync(root + "../pass2/data/verdicts.json"))
        .filter((r) => r.split === "development")
        .slice(0, 1)
    : JSON.parse(readFileSync(root + "data/verdicts.json"));
if (["controlled", "baseline", "smoke"].includes(mode)) {
  for (const [i, row] of cases.entries())
    await attempt(
      row.id,
      { case_id: row.id, route: i < 50 ? "typed-browser" : "typed-api" },
      async () => {
        await request("/evaluation/select/" + row.id, {});
        let result;
        if (i < 50) {
          await page.goto(web);
          await page.getByLabel("Claim to investigate").fill(row.claim);
          result = await submitButton("Check claim");
        } else
          result = await request("/api/v1/investigations", {
            claim: row.claim,
            input_type: "claim",
          });
        return { result, ...(await rendered(result, i % 25 === 0)) };
      },
    );
}
if (mode === "modal") {
  const images = JSON.parse(readFileSync(root + "data/images.json"));
  for (const [i, row] of cases.slice(0, 20).entries())
    for (const route of ["text", "image", ...(i < 10 ? ["url"] : [])]) {
      await attempt(
        row.id + "-" + route,
        { case_id: row.id, route },
        async () => {
          await request("/evaluation/select/" + row.id, {});
          await page.goto(web);
          let ocr;
          if (route === "image") {
            await page
              .getByRole("radio", { name: "Screenshot / image", exact: true })
              .check();
            await page
              .getByLabel("PNG or JPEG image (up to 5 MB)")
              .setInputFiles(root + "data/" + images[i].file);
            const response = page.waitForResponse((r) =>
              r.url().endsWith("/inputs/image"),
            );
            response.catch(() => {});
            await page.getByRole("button", { name: "Read image text" }).click();
            const ocrResponse = await response;
            ocr = await ocrResponse.json();
            appendFileSync(
              root + "results/ocr-observations.jsonl",
              JSON.stringify({
                case_id: row.id,
                status: ocrResponse.status(),
                ocr,
                transcript: images[i].transcript,
              }) + "\n",
            );
            await page
              .getByLabel("Article text")
              .fill(images[i].corrected_text);
          } else if (route === "text") {
            await page
              .getByRole("radio", { name: "Pasted article", exact: true })
              .check();
            const extra =
              i % 4 === 0
                ? "\nIn my opinion, this subject is fascinating."
                : i % 4 === 1
                  ? "\nThe following paragraph provides context for the statement. ".repeat(
                      50,
                    )
                  : "\nThe reader should evaluate the supplied evidence.";
            await page.getByLabel("Article text").fill(row.claim + extra);
          } else {
            await page
              .getByRole("radio", { name: "Article URL", exact: true })
              .check();
            await page
              .getByLabel("Public article URL")
              .fill("https://evaluation-input.org/" + row.id);
          }
          const proposalResponse = page.waitForResponse(
            (r) => r.url().includes("/inputs/") && !r.url().endsWith("/image"),
          );
          proposalResponse.catch(() => {});
          await page.getByRole("button", { name: "Propose claims" }).click();
          const proposals = await (await proposalResponse).json();
          assert.equal(proposals.claims[0], row.claim);
          for (let j = 1; j < proposals.claims.length; j++)
            await page
              .getByLabel("Investigate claim " + (j + 1), { exact: true })
              .uncheck();
          const result = await submitButton("Investigate selected claims");
          assert.equal(result.assessments[0].claim, row.claim);
          return {
            result,
            proposals,
            ocr,
            transcript: route === "image" ? images[i].transcript : undefined,
            ...(await rendered(result)),
          };
        },
      );
    }
}
if (mode === "urls") {
  const urls = readFileSync(root + "data/public-urls.txt", "utf8")
    .trim()
    .split("\n");
  for (const [i, url] of urls.entries())
    await attempt(
      "url-" + i,
      {
        url,
        route: "public-url",
        selection: i % 3 === 0 ? "one" : i % 3 === 1 ? "multiple" : "all",
      },
      async () => {
        await request("/evaluation/select/live", {});
        await page.goto(web);
        await page
          .getByRole("radio", { name: "Article URL", exact: true })
          .check();
        await page.getByLabel("Public article URL").fill(url);
        const response = page.waitForResponse((r) =>
          r.url().endsWith("/inputs/url"),
        );
        response.catch(() => {});
        await page.getByRole("button", { name: "Propose claims" }).click();
        const resolved = await response;
        const proposals = await resolved.json();
        if (!resolved.ok())
          return { success: false, extraction_failed: true, proposals };
        appendFileSync(
          root + "results/public-proposals.jsonl",
          JSON.stringify({ url, proposals }) + "\n",
        );
        const n =
          i % 3 === 0
            ? 1
            : i % 3 === 1
              ? Math.min(2, proposals.claims.length)
              : proposals.claims.length;
        assert(n > 0, "No proposals");
        for (let j = n; j < proposals.claims.length; j++)
          await page
            .getByLabel("Investigate claim " + (j + 1), { exact: true })
            .uncheck();
        const start = performance.now();
        const result = await submitButton("Investigate selected claims");
        return {
          result,
          proposals,
          selected_count: n,
          investigation_seconds: (performance.now() - start) / 1000,
          ...(await rendered(result, i === 0)),
        };
      },
    );
}
if (mode === "live") {
  const lines = readFileSync(root + "data/live-claims.tsv", "utf8")
    .trim()
    .split("\n")
    .slice(1);
  for (const [i, line] of lines.entries()) {
    const [difficulty, claim] = line.split("\t");
    await attempt(
      "live-" + i,
      { difficulty, claim, route: "live-typed" },
      async () => {
        await request("/evaluation/select/live", {});
        const result = await request("/api/v1/investigations", {
          claim,
          input_type: "claim",
        });
        return { result, ...(await rendered(result, i % 20 === 0)) };
      },
    );
  }
}
await browser.close();
