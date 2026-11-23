import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, expect, test } from "vitest";
import Result from "../components/result";
import type { Investigation } from "../lib/api";
afterEach(cleanup);
test("renders coverage and preserves gated evidence categories", () => {
  const result: Investigation = {
    id: "test",
    created_at: "2026-09-13",
    mode: "live",
    share_slug: null,
    model_metadata: {},
    assessments: [
      {
        claim: "A compound claim",
        verdict: "INSUFFICIENT_EVIDENCE",
        explanation: "Partial coverage.",
        support_total: 0.9,
        contradict_total: 0,
        atomic_claims: [
          {
            claim: "First proposition",
            verdict: "SUPPORTED",
            evidence_indices: [0],
          },
          {
            claim: "Second proposition",
            verdict: "INSUFFICIENT_EVIDENCE",
            evidence_indices: [],
          },
        ],
        evidence: [
          {
            title: "Related source",
            url: "https://example.org",
            domain: "example.org",
            published_at: null,
            passage: "Related passage",
            stance: "neutral",
            raw_stance: "contradict",
            stance_confidence: 0.99,
            similarity: 0.9,
            source_type: "general",
            source_weight: 0.55,
            evidence_score: 0.49,
            counted: false,
            exclusion_reason: "Different predicate.",
          },
        ],
      },
    ],
  };
  render(<Result result={result} />);
  expect(
    within(screen.getByRole("region", { name: "Claim coverage" })).getByText(
      /Second proposition/,
    ),
  ).toBeTruthy();
  const other = screen.getByRole("heading", {
    name: "Other relevant evidence",
  }).parentElement!;
  expect(within(other).getByText("Related passage")).toBeTruthy();
  expect(screen.getByText("Not counted: Different predicate.")).toBeTruthy();
  const against = screen.getByRole("heading", {
    name: "Evidence against",
  }).parentElement!;
  expect(within(against).queryByText("Related passage")).toBeNull();
});
