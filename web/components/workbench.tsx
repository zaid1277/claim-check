"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import Share from "./share";
import Result from "./result";
import { request, type Investigation } from "../lib/api";

type Candidate = { text: string; selected: boolean };
type Proposal = { text: string; claims: string[] };

export default function Workbench({
  initialUrl = "",
  onConfigurationError,
}: {
  initialUrl?: string;
  onConfigurationError?: () => Promise<void>;
}) {
  const [image, setImage] = useState<File | null>(null);
  const [ocrReview, setOcrReview] = useState(false);
  const [mode, setMode] = useState(initialUrl ? "url" : "claim");
  const [claim, setClaim] = useState("");
  const [text, setText] = useState("");
  const [url, setUrl] = useState(initialUrl);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [result, setResult] = useState<Investigation | null>(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const resultHeading = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    if (result) resultHeading.current?.focus();
  }, [result]);

  async function run(claims: string[]) {
    setBusy("Checking evidence — waiting for the investigation response.");
    setError("");
    setResult(null);
    try {
      setResult(
        await request<Investigation>("investigations", {
          claims,
          input_type: ocrReview ? "image" : mode,
          source_url: mode === "url" ? url : null,
          raw_text: mode === "claim" ? claim : text,
        }),
      );
    } catch (error) {
      setError(error instanceof Error ? error.message : "Request failed.");
      await onConfigurationError?.();
    } finally {
      setBusy("");
    }
  }
  async function propose(event: React.FormEvent) {
    event.preventDefault();
    setError("");
    setCandidates([]);
    setResult(null);
    if (mode === "claim") {
      await run([claim]);
      return;
    }
    if (mode === "image") {
      if (!image) {
        setError("Choose a PNG or JPEG image.");
        return;
      }
      if (image.size > 5_000_000) {
        setError("Image exceeds the 5 MB limit.");
        return;
      }
      setBusy("Reading text from the image.");
      try {
        const response = await fetch("/api/v1/inputs/image", {
          method: "POST",
          headers: { "Content-Type": image.type },
          body: image,
          signal: AbortSignal.timeout(120_000),
        });
        const data = await response.json();
        if (!response.ok)
          throw new Error(
            data.error?.message || "OCR failed. Paste the text instead.",
          );
        setText(data.text);
        setMode("text");
        setOcrReview(true);
      } catch (error) {
        setError(error instanceof Error ? error.message : "OCR failed.");
      } finally {
        setBusy("");
      }
      return;
    }
    setBusy("Reading text and proposing claims for your review.");
    try {
      const proposal = await request<Proposal>(
        `inputs/${mode}`,
        mode === "url" ? { url } : { text },
      );
      setText(proposal.text);
      setCandidates(proposal.claims.map((text) => ({ text, selected: true })));
      if (!proposal.claims.length)
        setError(
          "No suitable sentences were found. Enter a claim manually or edit the pasted text.",
        );
    } catch (error) {
      setError(
        error instanceof Error
          ? error.message
          : "Reading failed. Paste the article text instead.",
      );
    } finally {
      setBusy("");
    }
  }
  return (
    <div className="shell">
      <header className="masthead">
        <Link href="/">Claim Check</Link>
        <span>Research · Evidence · Context</span>
      </header>
      <main id="main">
        <p className="eyebrow">New investigation</p>
        <h1>Follow the evidence.</h1>
        <p className="intro">
          Enter a factual claim. Inspect the passages, their sources, and the
          limits of the assessment.
        </p>
        <fieldset disabled={Boolean(busy)} className="input-modes">
          <legend>Input source</legend>
          {[
            ["claim", "Typed claim"],
            ["url", "Article URL"],
            ["text", "Pasted article"],
            ["image", "Screenshot / image"],
          ].map(([value, label]) => (
            <label key={value}>
              <input
                type="radio"
                name="mode"
                value={value}
                checked={mode === value}
                onChange={() => {
                  setMode(value);
                  setOcrReview(false);
                  setCandidates([]);
                  setError("");
                }}
              />{" "}
              {label}
            </label>
          ))}
        </fieldset>
        {ocrReview && (
          <p className="notice">
            Review the extracted text below. Correct OCR mistakes before
            proposing claims.
          </p>
        )}
        <form onSubmit={propose} aria-busy={Boolean(busy)}>
          {mode === "image" && (
            <>
              <label htmlFor="image">PNG or JPEG image (up to 5 MB)</label>
              <input
                id="image"
                type="file"
                accept="image/png,image/jpeg"
                required
                onChange={(event) => setImage(event.target.files?.[0] || null)}
              />
            </>
          )}
          {mode === "claim" && (
            <>
              <label htmlFor="claim">Claim to investigate</label>
              <textarea
                id="claim"
                required
                minLength={3}
                maxLength={1000}
                rows={4}
                value={claim}
                onChange={(event) => setClaim(event.target.value)}
              />
            </>
          )}
          {mode === "url" && (
            <>
              <label htmlFor="url">Public article URL</label>
              <input
                id="url"
                type="url"
                required
                maxLength={2048}
                value={url}
                onChange={(event) => setUrl(event.target.value)}
              />
              <p className="muted">
                If the page cannot be read, select Pasted article and paste its
                text.
              </p>
            </>
          )}
          {mode === "text" && (
            <>
              <label htmlFor="article">Article text</label>
              <textarea
                id="article"
                required
                minLength={20}
                maxLength={30000}
                rows={8}
                value={text}
                onChange={(event) => setText(event.target.value)}
              />
            </>
          )}
          <div className="actions">
            <button disabled={Boolean(busy)}>
              {mode === "claim"
                ? "Check claim"
                : mode === "image"
                  ? "Read image text"
                  : "Propose claims"}
            </button>
            {mode === "claim" && (
              <button
                type="button"
                className="secondary"
                disabled={Boolean(busy)}
                onClick={() =>
                  setClaim("The demonstration library opens on Sundays.")
                }
              >
                Use demonstration claim
              </button>
            )}
          </div>
        </form>
        {candidates.length > 0 && (
          <section aria-label="Claim selection">
            <h2>Review the claims</h2>
            <p>
              These are sentence proposals, not verified facts. Correct names,
              dates and context before continuing.
            </p>
            {candidates.map((candidate, index) => (
              <div className="claim-edit" key={index}>
                <label>
                  <input
                    type="checkbox"
                    checked={candidate.selected}
                    onChange={(event) =>
                      setCandidates(
                        candidates.map((c, i) =>
                          i === index
                            ? { ...c, selected: event.target.checked }
                            : c,
                        ),
                      )
                    }
                  />{" "}
                  Investigate claim {index + 1}
                </label>
                <label htmlFor={`candidate-${index}`} className="muted">
                  Edit claim {index + 1}
                </label>
                <textarea
                  id={`candidate-${index}`}
                  maxLength={1000}
                  value={candidate.text}
                  onChange={(event) =>
                    setCandidates(
                      candidates.map((c, i) =>
                        i === index ? { ...c, text: event.target.value } : c,
                      ),
                    )
                  }
                />
              </div>
            ))}
            <button
              disabled={
                Boolean(busy) ||
                !candidates.some((c) => c.selected) ||
                candidates.some((c) => c.selected && c.text.trim().length < 3)
              }
              onClick={() =>
                run(candidates.filter((c) => c.selected).map((c) => c.text))
              }
            >
              Investigate selected claims
            </button>
          </section>
        )}
        {busy && <p role="status">{busy}</p>}
        {error && (
          <p role="alert" className="notice">
            {error}
          </p>
        )}
        {result && (
          <>
            <h2 ref={resultHeading} tabIndex={-1} className="result-heading">
              Investigation result
            </h2>
            <Result result={result} />
            <Share id={result.id} />
          </>
        )}
      </main>
      <footer>
        <Link href="/methodology">Methodology and limitations</Link>
      </footer>
    </div>
  );
}
