import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import ProviderGate from "../components/provider-gate";
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
const status = {
  ready: false,
  mode: "live",
  runtime_keys_allowed: true,
  database_configured: true,
  providers: { search: { configured: false, provider: "tavily" } },
};
test("missing credentials show labelled masked input and transition after validation", async () => {
  const fetch = vi
    .fn()
    .mockResolvedValueOnce({ ok: true, json: async () => status })
    .mockResolvedValueOnce({
      ok: true,
      json: async () => ({ ...status, ready: true }),
    });
  vi.stubGlobal("fetch", fetch);
  render(<ProviderGate />);
  const input = await screen.findByLabelText("Tavily API key");
  expect(input.getAttribute("type")).toBe("password");
  fireEvent.change(input, { target: { value: "test-example" } });
  fireEvent.submit(input.closest("form")!);
  await screen.findByLabelText("Claim to investigate");
  expect(fetch.mock.calls[1][0]).toBe("/api/v1/setup/providers");
});
test("hosted setup never requests visitor credentials", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ ...status, runtime_keys_allowed: false }),
    }),
  );
  render(<ProviderGate />);
  await screen.findByText(/site operator must configure/);
  expect(screen.queryByLabelText("Tavily API key")).toBeNull();
});
test("unavailable API has an accessible retry error", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error()));
  render(<ProviderGate />);
  await waitFor(() =>
    expect(screen.getByRole("alert").textContent).toContain("cannot reach"),
  );
});

test("server-configured Tavily opens claim input without asking for a key", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        ...status,
        ready: true,
        providers: { search: { configured: true, provider: "tavily" } },
      }),
    }),
  );
  render(<ProviderGate />);
  await screen.findByLabelText("Claim to investigate");
  expect(screen.queryByLabelText("Tavily API key")).toBeNull();
});
