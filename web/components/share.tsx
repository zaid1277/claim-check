"use client";
import { useState } from "react";
import Link from "next/link";
import { request } from "../lib/api";

export default function Share({ id }: { id: string }) {
  const [slug, setSlug] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function publish() {
    setBusy(true);
    setError("");
    try {
      setSlug(
        (
          await request<{ share_slug: string }>(
            `investigations/${id}/share`,
            {},
          )
        ).share_slug,
      );
    } catch (error) {
      setError(error instanceof Error ? error.message : "Sharing failed.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <section>
      <p>
        Publishing makes this report readable by anyone with its link. Avoid
        sharing sensitive personal information.
      </p>
      {slug ? (
        <p role="status">
          <Link href={`/reports/${slug}`}>Open shareable report</Link>
        </p>
      ) : (
        <button onClick={publish} disabled={busy}>
          Publish share link
        </button>
      )}
      {error && <p role="alert">{error}</p>}
    </section>
  );
}
