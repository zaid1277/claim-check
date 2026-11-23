import { createServer } from "node:http";
import { cpSync, rmSync, mkdtempSync, symlinkSync } from "node:fs";
import { resolve } from "node:path";
import { tmpdir } from "node:os";
import next from "../../web/node_modules/next/dist/server/next.js";

// A separate checkout keeps this test from restarting the user's dev server.
const root = process.cwd();
const directory = mkdtempSync(resolve(tmpdir(), "claim-check-final-web-"));
process.once("exit", () => rmSync(directory, { recursive: true, force: true }));
for (const name of [
  "app",
  "components",
  "lib",
  "package.json",
  "tsconfig.json",
  "next.config.ts",
  "postcss.config.mjs",
]) {
  cpSync(resolve(root, name), resolve(directory, name), { recursive: true });
}
symlinkSync(
  resolve(root, "node_modules"),
  resolve(directory, "node_modules"),
  "dir",
);
const app = next({
  dev: true,
  webpack: true,
  dir: directory,
  hostname: "127.0.0.1",
  port: 3102,
});
await app.prepare();
createServer(app.getRequestHandler()).listen(3102, "127.0.0.1");
