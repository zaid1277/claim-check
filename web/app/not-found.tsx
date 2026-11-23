import Link from "next/link";
export default function NotFound() {
  return (
    <main id="main" className="shell">
      <h1>Report not found</h1>
      <p>
        The link may be incorrect, or a temporary demonstration report may have
        expired.
      </p>
      <Link href="/">Start a new check</Link>
    </main>
  );
}
