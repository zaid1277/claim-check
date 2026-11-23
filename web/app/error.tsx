"use client";
export default function ErrorPage({ reset }: { reset: () => void }) {
  return (
    <main id="main" className="shell">
      <h1>This page is unavailable</h1>
      <p>Check that the API is running and try again.</p>
      <button onClick={reset}>Try again</button>
    </main>
  );
}
