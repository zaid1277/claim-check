import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { fileURLToPath } from "node:url";
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

test("manifest references shipped files and minimal required permissions", () => {
  const manifest = JSON.parse(
    fs.readFileSync(path.join(root, "manifest.json")),
  );
  assert.equal(manifest.manifest_version, 3);
  for (const file of [
    manifest.background.service_worker,
    manifest.side_panel.default_path,
    manifest.options_page,
  ]) {
    assert.ok(fs.existsSync(path.join(root, file)));
  }
  assert.ok(manifest.permissions.includes("sidePanel"));
  assert.ok(!manifest.permissions.includes("<all_urls>"));
  for (const file of ["background.js", "panel.js", "options.js"]) {
    new vm.Script(fs.readFileSync(path.join(root, file), "utf8"));
  }
});

test("context menu opens the panel and preserves selected page context", () => {
  let installed, clicked, menu, selection;
  const calls = [];
  const chrome = {
    runtime: {
      onInstalled: {
        addListener(fn) {
          installed = fn;
        },
      },
    },
    contextMenus: {
      create(value) {
        menu = value;
      },
      onClicked: {
        addListener(fn) {
          clicked = fn;
        },
      },
    },
    sidePanel: {
      setPanelBehavior() {},
      open(value) {
        calls.push(["open", value.tabId]);
      },
    },
    storage: {
      session: {
        set(value) {
          selection = value.selection;
          calls.push(["save"]);
        },
      },
    },
  };
  vm.runInNewContext(
    fs.readFileSync(path.join(root, "background.js"), "utf8"),
    { chrome },
  );
  installed();
  assert.equal(menu.title, "Check with Claim Check");
  clicked(
    {
      menuItemId: "claim-check",
      selectionText: "Some factual claim",
      pageUrl: "https://example.org",
    },
    { id: 42, title: "Example" },
  );
  assert.deepEqual(calls, [["open", 42], ["save"]]);
  assert.equal(selection.claim, "Some factual claim");
  assert.equal(selection.page_title, "Example");
  assert.equal(selection.source_url, "https://example.org");
});
