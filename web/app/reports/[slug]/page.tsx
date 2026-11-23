import Link from "next/link";
import { notFound } from "next/navigation";
import Result from "../../../components/result";
import type { Investigation } from "../../../lib/api";

export const dynamic = "force-dynamic";
export default async function ReportPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const response = await fetch(
    `${process.env.API_BASE_URL || "http://127.0.0.1:8000"}/api/v1/reports/${encodeURIComponent(slug)}`,
    { cache: "no-store", signal: AbortSignal.timeout(10_000) },
  );
  if (response.status === 404) notFound();
  if (!response.ok)
    return (
      <main id="main" className="shell">
        <h1>Report unavailable</h1>
        <p>The report service is temporarily unavailable. Try again later.</p>
      </main>
    );
  const result: Investigation = await response.json();
  return (
    <main id="main" className="shell">
      <header className="masthead">
        <Link href="/">Claim Check</Link>
        <span>Read-only evidence report</span>
      </header>
      <h1>Evidence report</h1>
      <Result result={result} />
      <Link href="/methodology">Methodology and limitations</Link>
    </main>
  );
}
