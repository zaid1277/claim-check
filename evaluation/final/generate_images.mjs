// Exact text fixtures let OCR errors be measured against a known transcript.
import { chromium } from "../../web/node_modules/playwright/index.mjs";
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
const root = fileURLToPath(new URL(".", import.meta.url));
const cases = JSON.parse(readFileSync(root + "data/verdicts.json")).slice(
  0,
  20,
);
mkdirSync(root + "data/images", { recursive: true });
const browser = await chromium.launch();
const page = await browser.newPage({
  viewport: { width: 900, height: 500 },
  deviceScaleFactor: 1,
});
const rows = [];
for (const [i, row] of cases.entries()) {
  const dark = i % 4 === 0;
  const text =
    row.claim +
    (i % 3 === 0
      ? "\n\nThis extract contains a factual statement for review.\nCheck the evidence before accepting the conclusion."
      : "");
  const font = [24, 18, 14, 28, 20][i % 5];
  const family = ["Georgia", "Arial", "Times New Roman", "Verdana"][i % 4];
  const blur = i === 7 || i === 17 ? ".35px" : "0px";
  await page.setContent("<body><article></article></body>");
  await page.locator("article").evaluate(
    (element, { text, dark, font, family, blur, i }) => {
      element.textContent = text;
      Object.assign(element.style, {
        whiteSpace: "pre-wrap",
        font: `${font}px ${family}`,
        lineHeight: "1.6",
        padding: "32px",
        width: i % 5 === 2 ? "370px" : "700px",
        background: dark ? "#171a1c" : "#faf9f5",
        color: dark ? "#ffffff" : "#202020",
        filter: `blur(${blur})`,
        letterSpacing: i === 9 ? "2px" : "normal",
      });
    },
    { text, dark, font, family, blur, i },
  );
  const compressed = i % 5 === 4;
  const filename = `images/${String(i).padStart(2, "0")}.${compressed ? "jpg" : "png"}`;
  await page.locator("article").screenshot({
    path: root + "data/" + filename,
    ...(compressed ? { type: "jpeg", quality: 65 } : { type: "png" }),
  });
  rows.push({
    id: row.id,
    file: filename,
    transcript: text,
    corrected_text: row.claim,
    conditions: {
      dark,
      font,
      family,
      blur,
      jpeg_quality: compressed ? 65 : null,
      wrapped: i % 5 === 2,
      spacing: i === 9,
    },
  });
}
writeFileSync(root + "data/images.json", JSON.stringify(rows, null, 2) + "\n");
await browser.close();
