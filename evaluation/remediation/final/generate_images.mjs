// Group 4, phase 6: 30 new OCR fixtures with varied, documented visual
// difficulty, built from the new investigation set (not the old 20 images).
// Exact text fixtures let OCR errors be measured against a known transcript.
import { chromium } from "../../../web/node_modules/playwright/index.mjs";
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
const root = fileURLToPath(new URL(".", import.meta.url));
const all = JSON.parse(readFileSync(root + "data/investigations.json"));
// Pick a diverse 30: a mix of easy/medium/hard, favoring claims with digits,
// dates, or punctuation so OCR has real numeric/punctuation content to get
// right or wrong, not just plain prose.
const withDigits = all.filter((r) => /\d/.test(r.claim));
const withoutDigits = all.filter((r) => !/\d/.test(r.claim));
const cases = [...withDigits.slice(0, 12), ...withoutDigits.slice(0, 8)];
mkdirSync(root + "data/images", { recursive: true });
const browser = await chromium.launch();
const page = await browser.newPage({
  viewport: { width: 900, height: 560 },
  deviceScaleFactor: 1,
});
const rows = [];
for (const [i, row] of cases.entries()) {
  const dark = i % 3 === 0;
  const multiParagraph = i % 4 === 1;
  const text =
    row.claim +
    (multiParagraph
      ? "\n\nThis passage is presented for factual review.\nPlease verify the statement against independent sources before drawing conclusions.\nAdditional context may be required for claims involving dates or statistics."
      : i % 5 === 3
        ? "\n\nSource: internal briefing document, page 2."
        : "");
  const font = [26, 15, 13, 30, 19, 22][i % 6]; // includes "small text" (13-15px) cases
  const family = ["Georgia", "Arial", "Times New Roman", "Verdana", "Courier New"][i % 5];
  const blur = i % 7 === 3 ? ".4px" : i % 11 === 5 ? ".2px" : "0px";
  const narrow = i % 6 === 2; // forces line wrapping
  await page.setContent("<body><article></article></body>");
  await page.locator("article").evaluate(
    (element, { text, dark, font, family, blur, narrow }) => {
      element.textContent = text;
      Object.assign(element.style, {
        whiteSpace: "pre-wrap",
        font: `${font}px ${family}`,
        lineHeight: "1.6",
        padding: "32px",
        width: narrow ? "340px" : "720px",
        background: dark ? "#12151a" : "#fbfaf6",
        color: dark ? "#f2f2f2" : "#1e1e1e",
        filter: `blur(${blur})`,
      });
    },
    { text, dark, font, family, blur, narrow },
  );
  const compressed = i % 5 === 4; // "moderate compression"
  const filename = `images/${String(i).padStart(2, "0")}.${compressed ? "jpg" : "png"}`;
  await page.locator("article").screenshot({
    path: root + "data/" + filename,
    ...(compressed ? { type: "jpeg", quality: 60 } : { type: "png" }),
  });
  rows.push({
    id: row.id,
    file: filename,
    transcript: text,
    corrected_text: row.claim,
    difficulty: row.difficulty,
    expected: row.expected,
    conditions: {
      dark,
      font,
      family,
      blur,
      jpeg_quality: compressed ? 60 : null,
      narrow_wrapped: narrow,
      multi_paragraph: multiParagraph,
      has_digits: /\d/.test(row.claim),
    },
  });
}
writeFileSync(root + "data/images.json", JSON.stringify(rows, null, 2) + "\n");
console.log(`Generated ${rows.length} images`);
await browser.close();
