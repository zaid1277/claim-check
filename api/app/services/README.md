# Investigation services

The services follow PROJECT_SPEC.md: reviewed claims, search/article passages,
embeddings/cosine ranking, NLI, source heuristics, evidence scoring and grounded
explanation. Providers are replaceable for tests. Live failures never silently
switch to demonstration evidence. See ../../../../docs/architecture.md and
../../../../docs/claim-check-explained.md for the full pipeline and its
measured behavior.
