import { fireEvent, render, screen, cleanup } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import Workbench from "../components/workbench";

const fixture = {
  id: "00000000-0000-0000-0000-000000000001",
  created_at: "2026-09-01T00:00:00Z",
  mode: "fixture",
  share_slug: null,
  model_metadata: {},
  assessments: [
    {
      claim: "A test claim",
      verdict: "INSUFFICIENT_EVIDENCE",
      explanation: "No evidence.",
      evidence: [],
      support_total: 0,
      contradict_total: 0,
    },
  ],
};

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function enterClaim() {
  fireEvent.change(screen.getByLabelText("Claim to investigate"), {
    target: { value: "A test claim" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Check claim" }));
}

test("focus moves to the result after the asynchronous response is rendered", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({ ok: true, json: async () => fixture }),
  );
  render(<Workbench />);
  enterClaim();
  const heading = await screen.findByRole("heading", {
    name: "Investigation result",
  });
  expect(document.activeElement).toBe(heading);
  expect(screen.getByText(/Demonstration fixtures/)).toBeTruthy();
});

test("an unavailable provider is shown as an error, not an evidence result", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: false,
      json: async () => ({ error: { message: "Search is unavailable." } }),
    }),
  );
  render(<Workbench />);
  enterClaim();
  expect((await screen.findByRole("alert")).textContent).toBe(
    "Search is unavailable.",
  );
  expect(
    screen.queryByRole("article", { name: "Investigation result" }),
  ).toBeNull();
});

test("checking state exposes a status and prevents duplicate submissions", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(() => new Promise(() => {})),
  );
  render(<Workbench />);
  enterClaim();
  expect((await screen.findByRole("status")).textContent).toContain(
    "Checking evidence",
  );
  expect(
    (
      screen.getByRole("button", {
        name: "Check claim",
      }) as HTMLButtonElement
    ).disabled,
  ).toBe(true);
});

test("claim selection cannot submit an empty selection", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        text: "A proposed factual sentence.",
        claims: ["A proposed factual sentence."],
      }),
    }),
  );
  render(<Workbench initialUrl="https://example.org/article" />);
  fireEvent.click(screen.getByRole("button", { name: "Propose claims" }));
  const checkbox = await screen.findByLabelText("Investigate claim 1");
  fireEvent.click(checkbox);
  expect(
    (
      screen.getByRole("button", {
        name: "Investigate selected claims",
      }) as HTMLButtonElement
    ).disabled,
  ).toBe(true);
});

test("OCR correction is used for both proposals and the saved investigation", async () => {
  const corrected = "The observatory opened in 1998.";
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        text: "The observat0ry opened in 199B.",
        review_required: true,
      }),
    })
    .mockResolvedValueOnce({
      ok: true,
      json: async () => ({ text: corrected, claims: [corrected] }),
    })
    .mockResolvedValueOnce({ ok: true, json: async () => fixture });
  vi.stubGlobal("fetch", fetchMock);
  render(<Workbench />);
  fireEvent.click(screen.getByRole("radio", { name: "Screenshot / image" }));
  fireEvent.change(screen.getByLabelText("PNG or JPEG image (up to 5 MB)"), {
    target: {
      files: [
        new File(["image fixture"], "article.png", { type: "image/png" }),
      ],
    },
  });
  // jsdom does not populate the native file-input value from a FileList fixture.
  fireEvent.submit(
    screen.getByRole("button", { name: "Read image text" }).closest("form")!,
  );
  const editor = await screen.findByLabelText("Article text");
  fireEvent.change(editor, { target: { value: corrected } });
  fireEvent.click(screen.getByRole("button", { name: "Propose claims" }));
  await screen.findByLabelText("Edit claim 1");
  expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toEqual({
    text: corrected,
  });
  fireEvent.click(
    screen.getByRole("button", { name: "Investigate selected claims" }),
  );
  await screen.findByRole("heading", { name: "Investigation result" });
  expect(JSON.parse(fetchMock.mock.calls[2][1].body)).toEqual({
    claims: [corrected],
    input_type: "image",
    source_url: null,
    raw_text: corrected,
  });
});
