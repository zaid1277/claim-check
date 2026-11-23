import { fireEvent, render, screen, cleanup } from "@testing-library/react";
import { afterEach, expect, test } from "vitest";
import Home from "../components/workbench";
afterEach(cleanup);
test("provides labelled claim entry and a deliberate fixture example", () => {
  render(<Home />);
  fireEvent.click(
    screen.getByRole("button", { name: "Use demonstration claim" }),
  );
  expect(
    (screen.getByLabelText("Claim to investigate") as HTMLTextAreaElement)
      .value,
  ).toContain("demonstration library");
});
