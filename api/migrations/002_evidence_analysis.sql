ALTER TABLE evidence ADD COLUMN analysis jsonb NOT NULL DEFAULT '{}';
ALTER TABLE assessments ADD COLUMN atomic_claims jsonb NOT NULL DEFAULT '[]';
