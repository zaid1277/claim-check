export type Evidence = {
  title: string;
  url: string;
  domain: string;
  published_at: string | null;
  passage: string;
  similarity: number;
  stance: "support" | "contradict" | "neutral";
  stance_confidence: number;
  source_type: string;
  source_weight: number;
  evidence_score: number;
  raw_stance?: Evidence["stance"] | null;
  exclusion_reason?: string | null;
  independence_group?: string | null;
  counted?: boolean;
  atomic_claim?: string | null;
  relevance_score?: number | null;
  directness?: "direct" | "related" | "contextual" | "irrelevant" | null;
  relevance_weight?: number | null;
  structured_signal?: "numeric" | "temporal" | "location" | "negation" | null;
};
export type Assessment = {
  claim: string;
  verdict: string;
  explanation: string;
  support_total: number;
  contradict_total: number;
  evidence: Evidence[];
  atomic_claims?: {
    claim: string;
    verdict: string;
    evidence_indices: number[];
  }[];
  verified_atom_fraction?: number | null;
  contradicted_atom_fraction?: number | null;
};
export type Investigation = {
  id: string;
  created_at: string;
  mode: string;
  assessments: Assessment[];
  share_slug: string | null;
  model_metadata: Record<string, string>;
};

export async function request<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`/api/v1/${path}`, {
    method: "POST",
    signal: AbortSignal.timeout(120_000),
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await response.json().catch((error: unknown) => {
    // Proxy failures may be plain text, which browsers report as parsing errors.
    if (error instanceof SyntaxError)
      throw new Error(
        `The server returned an unreadable response (HTTP ${response.status}). Please try again.`,
      );
    throw error;
  });
  if (!response.ok)
    throw new Error(
      data.error?.message ||
        "The request could not be completed. Check your input and try again.",
    );
  return data;
}
