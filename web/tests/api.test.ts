import { afterEach, expect, test, vi } from "vitest";
import { request } from "../lib/api";

afterEach(() => vi.unstubAllGlobals());

test("plain-text proxy errors do not leak browser JSON parsing errors", async () => {
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValue(
        new Response("Internal Server Error", { status: 500 }),
      ),
  );
  await expect(
    request("investigations", { claims: ["A factual claim."] }),
  ).rejects.toThrow(
    "The server returned an unreadable response (HTTP 500). Please try again.",
  );
});

test("structured API errors retain their actionable message", async () => {
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValue(
        Response.json(
          { error: { message: "Search is unavailable." } },
          { status: 502 },
        ),
      ),
  );
  await expect(request("investigations", {})).rejects.toThrow(
    "Search is unavailable.",
  );
});
