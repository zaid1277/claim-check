# Final configuration reference

This is the configuration the project actually ships with, read directly out of
[`api/app/core/settings.py`](../api/app/core/settings.py) rather than remembered or
estimated. If a value here and the source file ever disagree, the source file is
correct — re-generate this table from it rather than guessing.

`.env.example` holds safe blanks and defaults. Blank optional values are ignored.
The API loads the repository-root `.env`; process environment variables take
precedence. Settings are cached (`lru_cache`), so restart the API after changes.

## Environment variables

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | API PostgreSQL connection; absent only for fixture/in-memory mode |
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | Local Compose database initialization |
| `CONTAINER_DATABASE_URL` | PostgreSQL URL using hostname `db`, for the full Compose stack |
| `PROVIDER_MODE` | `fixture` by default; `live` enables real web search + ML inference |
| `SEARCH_PROVIDER` | Optional preferred `tavily` / `brave`; `mock` is fixture-mode only |
| `TAVILY_API_KEY` | Server-side Tavily credential; the default live search provider |
| `BRAVE_SEARCH_API_KEY` | Optional alternative Brave Search credential |
| `ALLOW_RUNTIME_PROVIDER_KEYS` | `false` by default; opt-in trusted-localhost key entry (see below) |
| `NLI_MODEL` | Optional override for the NLI model; leave unset to use the evaluated default |
| `API_BASE_URL` | Web-to-API origin; default `http://127.0.0.1:8000`; set in `web/.env.local` or process environment before building |
| `HF_HOME` | Optional **process environment** variable for the HuggingFace model cache directory |
| `TEST_DATABASE_URL` | Explicit PostgreSQL database for tests; never point this at production |

The Next.js proxy destination is resolved at build time. Set `API_BASE_URL` before
building and keep the same value at runtime for server-rendered reports.
`web/.env.example` records that setting separately.

## Model and threshold defaults

These are the values the project currently ships with, each backed by a
validation or multi-fold measurement recorded as a comment next to the field in
`settings.py` — read that file for the full rationale and evidence behind any one
of these. They are tuned defaults, not placeholders, but they are also not
claimed to be globally optimal; several are explicitly documented as a validated
Pareto point rather than an ideal one.

| Setting | Default | What it does |
| --- | --- | --- |
| `nli_model` | `MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli` | The entailment/contradiction/neutral classifier used to score each evidence passage against a claim |
| `embedding_model` | `sentence-transformers/all-MiniLM-L6-v2` | Sentence embeddings used for passage retrieval/ranking |
| `proposition_model` | `cross-encoder/ms-marco-MiniLM-L6-v2` | Cross-encoder used to score passage-to-claim relevance |
| `min_similarity` | 0.35 | Minimum embedding cosine similarity for a passage to be considered |
| `top_k` | 10 | Passages kept per claim after similarity ranking |
| `max_sources` | 15 | Sources fetched per claim (raised from 10; see settings.py comment) |
| `max_candidates_per_domain` | 3 | Cap on candidate passages from a single registrable domain before ranking |
| `allow_follow_up_search` / `max_follow_up_queries` | `true` / 1 | One deterministic follow-up search when an atomic claim has no independent evidence |
| `min_proposition_relevance` | 2.0 | Cross-encoder score above which a passage is at full relevance weight |
| `relevance_floor` | 0.0 | Below this cross-encoder score, non-contradiction evidence is excluded outright |
| `contradiction_relevance_floor` | -1.5 | Separate, more permissive floor for contradiction evidence only (multi-fold validated; see settings.py) |
| `relevance_full_weight` | 4.0 | At/above this score, relevance stops discounting the evidence weight |
| `min_nli_confidence` | 0.65 | Minimum NLI confidence for support/neutral evidence to count |
| `min_contradiction_confidence` | 0.68 | Minimum NLI confidence specifically for contradiction evidence (see settings.py for the generalization story behind this number) |
| `max_atomic_claims` | 4 | Atomic claims extracted per investigation |
| `duplicate_similarity` | 0.9 | Similarity above which two passages are treated as near-duplicates |
| `duplicate_source_weight` | 0.35 | Discount (not exclusion) applied to a second same-stance passage from an already-used domain |
| `current_evidence_days` | 365 | Age window used for "current evidence" framing |
| `minimum_evidence` | 0.20 | Minimum aggregate evidence weight before a claim can be assessed rather than abstained on |
| `dominance_ratio` | 2.0 | How much stronger one side's evidence must be to declare a verdict rather than MIXED_EVIDENCE |
| `high_risk_minimum_evidence` | 0.65 | Stricter `minimum_evidence` for medical/financial/statistical/political claims |
| `high_risk_dominance_ratio` | 2.5 | Stricter `dominance_ratio` for the same high-risk claims |
| `high_risk_min_independent_sources` | 2 | Minimum independent sources required for a high-risk claim |
| `authority_tiebreak_enabled` | `true` | Lets one clearly authoritative source resolve a MIXED_EVIDENCE tie under the conditions below |
| `authority_tiebreak_min_weight` | 0.90 | Minimum source weight to qualify as the authoritative side of a tiebreak |
| `authority_tiebreak_max_opposing_weight` | 0.75 | Tiebreak only applies if the opposing side isn't itself this authoritative |
| `authority_tiebreak_max_opposing_sources` | 2 | Tiebreak only applies if the opposing side isn't corroborated by more than this many independent sources |
| `max_passages` | 100 | Hard cap on passages considered per claim |
| `max_claims` | 5 | Hard cap on claims per investigation |
| `min_claim_chars` | 20 | Minimum length for a proposed atomic claim sentence |
| `embedding_batch_size` | 16 | Batch size for the embedding model |
| `nli_max_tokens` | 512 | Max token length for NLI inputs |
| `max_image_bytes` / `max_image_pixels` | 5,000,000 / 12,000,000 | OCR upload limits |
| `requests_per_minute` | 30 | Rate limit per direct peer, per process |

Source weights: research **1.00**, official **0.95**, institution **0.90**,
reporting **0.75**, encyclopedia **0.75**, general **0.70**, unknown **0.30**.
Classification uses a small, reviewable domain map (`source_domains` in
`settings.py`) plus `.gov`/`.edu`-style suffix heuristics. These are not claimed
to be universal source-quality scores — they are a coarse, documented heuristic,
and the domain map itself is short enough to read in full in the source file.

## Runtime provider setup

`ALLOW_RUNTIME_PROVIDER_KEYS` defaults to `false`. With `PROVIDER_MODE=live`,
setting it to `true` enables key validation at `POST /api/v1/setup/providers`.
This feature is restricted to localhost: direct peer, Host, and browser Origin
must all be local; cross-site requests are rejected. It is not a public
multi-user BYOK service. Bind both development servers to loopback and use one
API process. Do not expose a runtime-enabled installation through a public
tunnel or proxy. Container deployments keep it disabled; the localhost check
deliberately rejects container-to-container peers.

A validated key is held as a `SecretStr` in backend process memory. It is never
written to disk, returned through status/report APIs, or stored in browser
storage. The password field is cleared after submission. It disappears on
restart; `.env` is the persistent developer option. A single validation search
consumes provider quota. Server environment credentials take precedence and
cannot be replaced through the form. Revoked credentials detected during search
return the web UI to setup; a server-owned key must be fixed by the operator.

`GET /api/v1/setup/status` reports configuration only, with no secret values.
"Configured" is not a continuous provider health check. Database status here
indicates a connection string exists; `/api/v1/ready` checks actual connectivity.
Models are loaded lazily, so setup readiness does not guarantee model
availability. Fixture mode requires neither a key nor a database and skips
setup.

## Search provider selection

The default is Tavily. With a nonblank `SEARCH_PROVIDER`, that provider is
preferred if its server key exists. Otherwise the app chooses a configured
Tavily key, then a configured Brave key, then a validated local runtime
provider. Without any key, setup presents Tavily first. This fallback is
configuration resolution only: HTTP errors, revoked keys, and quota failures
never silently trigger another paid provider mid-request.

`SEARCH_PROVIDER=mock` is valid only with `PROVIDER_MODE=fixture`. The fixture
investigation stays explicitly labelled as such. `SearchProvider` remains
injectable in tests. Runtime POST payload:
`{ "provider": "tavily", "api_key": "<key>" }` (or `brave`). Validation uses
one basic search call; normal queries use `search_results`. Tavily answer
generation, raw content, and automatic parameter selection are disabled.
Normalized snippets and provider scores are retained by the adapter but do not
replace independently fetched article passages or cosine relevance.

API contract reference: https://docs.tavily.com/documentation/api-reference/endpoint/search
