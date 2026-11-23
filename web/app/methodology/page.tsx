import Link from "next/link";
export default function Methodology() {
  return (
    <main id="main" className="shell">
      <Link href="/">← Claim Check</Link>
      <h1>Methodology & limitations</h1>
      <p>
        Claim Check compares a claim with retrieved evidence. A verdict
        summarizes the retained passages; it is not a guarantee about the world.
      </p>
      <h2>Evidence, step by step</h2>
      <ol>
        <li>Extract and review factual claims.</li>
        <li>Search for sources and extract passages.</li>
        <li>Rank passages using embeddings and cosine similarity.</li>
        <li>Classify support, contradiction or neutrality with NLI.</li>
        <li>
          Weight and aggregate the evidence, abstaining when evidence is
          insufficient.
        </li>
      </ol>
      <p>
        The current provider mode is shown on each result. Demonstration
        fixtures do not perform live research.
      </p>
      <p>
        Source weights are transparent heuristics, not universal trust scores.
        Sources can be mistaken, dependent on each other, or outdated. NLI can
        miss context, dates, negation, and numerical details.
      </p>
      <p>
        Medical, financial and political subjects require particular caution.
        Check original sources and consult qualified professionals where
        appropriate.
      </p>
    </main>
  );
}
