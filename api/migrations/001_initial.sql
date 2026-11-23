CREATE TABLE investigations (
    id uuid PRIMARY KEY,
    input_type text NOT NULL,
    raw_text text NOT NULL,
    source_url text,
    status text NOT NULL CHECK (status = 'complete'),
    share_slug text UNIQUE,
    created_at timestamptz NOT NULL,
    mode text NOT NULL
);
CREATE TABLE claims (
    id uuid PRIMARY KEY,
    investigation_id uuid NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
    claim_text text NOT NULL,
    selected boolean NOT NULL DEFAULT true,
    position integer NOT NULL
);
CREATE TABLE sources (
    id uuid PRIMARY KEY,
    investigation_id uuid NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
    url text NOT NULL,
    domain text NOT NULL,
    title text NOT NULL,
    published_at text,
    source_type text NOT NULL,
    source_weight double precision NOT NULL CHECK (source_weight BETWEEN 0 AND 1)
);
CREATE TABLE evidence (
    id uuid PRIMARY KEY,
    claim_id uuid NOT NULL REFERENCES claims(id) ON DELETE CASCADE,
    source_id uuid NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    passage_text text NOT NULL,
    similarity double precision NOT NULL CHECK (similarity BETWEEN 0 AND 1),
    stance text NOT NULL CHECK (stance IN ('support','contradict','neutral')),
    stance_confidence double precision NOT NULL CHECK (stance_confidence BETWEEN 0 AND 1),
    evidence_score double precision NOT NULL CHECK (evidence_score BETWEEN 0 AND 1),
    position integer NOT NULL
);
CREATE TABLE assessments (
    id uuid PRIMARY KEY,
    claim_id uuid NOT NULL UNIQUE REFERENCES claims(id) ON DELETE CASCADE,
    support_total double precision NOT NULL,
    contradict_total double precision NOT NULL,
    verdict text NOT NULL CHECK (verdict IN ('SUPPORTED','UNSUPPORTED','MIXED_EVIDENCE','INSUFFICIENT_EVIDENCE')),
    explanation text NOT NULL,
    model_metadata jsonb NOT NULL
);
CREATE INDEX claims_investigation_idx ON claims(investigation_id);
CREATE INDEX sources_investigation_idx ON sources(investigation_id);
CREATE INDEX evidence_claim_idx ON evidence(claim_id);
