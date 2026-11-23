import type { Investigation } from "../lib/api";

export default function Result({ result }: { result: Investigation }) {
  return (
    <article aria-label="Investigation result">
      {result.mode === "fixture" && (
        <p className="notice">
          Demonstration fixtures — not live research or a real-world assessment.
        </p>
      )}
      {result.assessments.map((assessment, index) => (
        <section key={index} className="assessment">
          <p className="eyebrow">Claim {index + 1}</p>
          <h2>{assessment.claim}</h2>
          <p className="eyebrow">Assessment</p>
          <h3>{assessment.verdict.replaceAll("_", " ")}</h3>
          <p>{assessment.explanation}</p>
          <p>
            <strong>What we checked:</strong> The claim as written above.
          </p>
          {(assessment.atomic_claims?.length ?? 0) > 1 && (
            <section aria-label="Claim coverage">
              <h3>Claim coverage</h3>
              <ul>
                {assessment.atomic_claims?.map((atom, i) => (
                  <li key={i}>
                    {atom.claim} — {atom.verdict.replaceAll("_", " ")}
                  </li>
                ))}
              </ul>
            </section>
          )}
          {(["support", "contradict", "neutral"] as const).map((stance) => (
            <section key={stance} className="evidence-group">
              <h3>
                {stance === "contradict"
                  ? "Evidence against"
                  : stance === "support"
                    ? "Evidence supporting"
                    : "Other relevant evidence"}
              </h3>
              {assessment.evidence.filter((e) => e.stance === stance).length ===
                0 && (
                <p className="muted">No retained passages in this category.</p>
              )}
              {assessment.evidence.map((e, i) =>
                e.stance !== stance ? null : (
                  <div className="citation" key={i}>
                    <p>
                      <strong>[{i + 1}] </strong>
                      <a href={e.url} target="_blank" rel="noreferrer">
                        {e.title}
                      </a>
                    </p>
                    <p className="muted">
                      {e.domain} ·{" "}
                      {e.published_at || "Publication date unavailable"}
                    </p>
                    <blockquote>{e.passage}</blockquote>
                    {e.atomic_claim &&
                      (assessment.atomic_claims?.length ?? 0) > 1 && (
                        <p>Addresses: {e.atomic_claim}</p>
                      )}
                    {e.exclusion_reason && (
                      <p className="muted">Not counted: {e.exclusion_reason}</p>
                    )}
                    <details>
                      <summary>Why this evidence?</summary>
                      <dl>
                        <dt>Cosine relevance</dt>
                        <dd>{e.similarity.toFixed(3)}</dd>
                        <dt>
                          Model stance / confidence before eligibility checks
                        </dt>
                        <dd>
                          {e.raw_stance ?? e.stance} /{" "}
                          {e.stance_confidence.toFixed(3)}
                        </dd>
                        <dt>Retained stance</dt>
                        <dd>{e.stance}</dd>
                        <dt>Source heuristic / weight</dt>
                        <dd>
                          {e.source_type} / {e.source_weight.toFixed(2)}
                        </dd>
                        <dt>Evidence score</dt>
                        <dd>{e.evidence_score.toFixed(3)}</dd>
                      </dl>
                      <p>
                        NLI confidence describes the passage–claim relationship,
                        not the probability that the claim is true.
                      </p>
                    </details>
                  </div>
                ),
              )}
            </section>
          ))}
          <details>
            <summary>Methodology / technical details</summary>
            <p>
              Evidence score = relevance × stance confidence × source weight.
              Only independent retained evidence contributes to each
              proposition. Support and contradiction are added separately; weak
              or missing evidence requires abstention.
            </p>
            <p>
              Supporting total: {assessment.support_total.toFixed(3)} ·
              Contradicting total: {assessment.contradict_total.toFixed(3)}
            </p>
            <pre>{JSON.stringify(result.model_metadata, null, 2)}</pre>
          </details>
        </section>
      ))}
      <footer>
        <p>Checked at {new Date(result.created_at).toLocaleString()}</p>
        <p>
          Evidence may be incomplete, outdated, or misinterpreted. Medical,
          legal, financial and political claims need particular care; this
          report is not professional advice.
        </p>
      </footer>
    </article>
  );
}
