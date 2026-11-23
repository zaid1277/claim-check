# Claim Check — V1 Product Requirements & Build Specification

> Product requirements, architecture and scope for Claim Check V1. Prefer simple, reviewable implementations.

## Development rules

- Do not generate the whole repository in one pass.
- Before each milestone, list files you will create/modify and why.
- Do not add LangChain/LangGraph, Redis/Celery, microservices, a vector DB, Kubernetes, or other infrastructure not requested here.
- Do not fabricate metrics or accuracy claims.
- Keep tunable ML values in one settings module.
- Follow the UI rules exactly: no purple gradients, glowing blobs, chatbot bubbles, “AI-powered” badges, excessive rounded cards, or generic generated SaaS styling.
- Comments should read like a capable student wrote them: explain **why**, assumptions, thresholds, and edge cases; do not narrate obvious syntax.

## Product

Claim Check is a web application and Chrome/Edge extension that investigates factual claims. Inputs can be typed claims, URLs/articles, screenshots, pasted articles, or browser-highlighted text.

Pipeline:

```text
Input → claim extraction → live web search → article extraction → passages
→ embeddings + cosine similarity → Top-K evidence → NLI stance
→ source heuristic → evidence scoring → verdict → grounded explanation/report
```

Verdicts:

- `SUPPORTED`
- `MIXED_EVIDENCE`
- `UNSUPPORTED`
- `INSUFFICIENT_EVIDENCE`

Never display “True / False” or a fake “93% true” score.

## Portfolio objective

Demonstrate:

- Next.js + TypeScript
- Python + FastAPI
- live search + article extraction
- embeddings + cosine similarity
- NLI classification
- transparent evidence-scoring/abstention logic
- Chrome/Edge Manifest V3 extension
- testing and measured evaluation
- clean public deployment and GitHub documentation

## V1 inputs

1. Typed claim
2. URL (extract article → propose claims → user selects/edits)
3. Pasted article
4. Screenshot/image (OCR → propose claims → user corrects/selects)
5. Browser-selected text
6. “Check this page” extension flow

## High-stakes topics

Politics, medicine, and finance are allowed, but:

- show suitable caution/“not professional advice” language
- make source identity/date prominent
- favor primary/official evidence where appropriate
- prefer insufficient evidence over overclaiming

## Non-goals

- no accounts in V1
- no social/community features
- no custom-trained foundation model
- no fine-tuning requirement
- no BM25/hybrid retrieval initially
- no cross-encoder reranker initially
- no learned source-quality model
- no distributed queue unless deployment proves necessary
- no native mobile app

## Stack

| Layer | Choice |
|---|---|
| Web | Next.js + React + TypeScript |
| Styling | Tailwind + small custom component layer |
| API | Python + FastAPI + Pydantic |
| Database | PostgreSQL (Supabase acceptable) |
| Article extraction | trafilatura or equivalent |
| Embeddings | sentence-transformers or provider adapter |
| NLI | pre-trained MNLI/FEVER-style transformer |
| Search | `SearchProvider`: Tavily default, Brave optional, fixtures for tests |
| Screenshot text | OCR adapter |
| Extension | Chrome/Edge Manifest V3 + Side Panel |
| Tests | pytest + Vitest/Testing Library + Playwright |

## Repository

```text
claim-check/
├── README.md
├── PROJECT_SPEC.md
├── docs/
│   ├── ml-notes.md
│   ├── evaluation.md
│   └── architecture.md
├── web/
├── api/
│   └── app/
│       ├── api/
│       ├── core/
│       ├── db/
│       ├── models/
│       ├── schemas/
│       └── services/
│           ├── claim_extraction.py
│           ├── search.py
│           ├── article_extraction.py
│           ├── embeddings.py
│           ├── retrieval.py
│           ├── nli.py
│           ├── source_quality.py
│           └── evidence_scoring.py
├── extension/
├── evaluation/
└── .env.example
```

## Investigation workflow

1. Normalize input.
2. OCR images or extract URL/article text.
3. Identify checkable claims; user can edit/select.
4. Generate 3–5 focused web queries per selected claim.
5. Search and collect candidate URLs/metadata.
6. Extract clean article text and split into passages.
7. Embed claim/passages and compute cosine similarity.
8. Keep Top-K passages above minimum similarity.
9. Run NLI on each retained claim/passage pair.
10. Assign transparent source-type weight.
11. Calculate evidence score.
12. Aggregate supporting/contradicting evidence.
13. Produce one of four verdicts.
14. Generate an explanation using only stored evidence/citations.
15. Save and expose a read-only share report.

## ML contract

`EvidenceScore = Relevance × StanceConfidence × SourceWeight`

Direction:

- support `+1`
- contradict `-1`
- neutral `0`

Keep separate totals:

- `S = Σ supporting scores`
- `C = Σ contradicting scores`

Illustrative logic:

```python
if (S + C) < MINIMUM_EVIDENCE:
    verdict = INSUFFICIENT_EVIDENCE
elif S >= DOMINANCE_RATIO * C:
    verdict = SUPPORTED
elif C >= DOMINANCE_RATIO * S:
    verdict = UNSUPPORTED
else:
    verdict = MIXED_EVIDENCE
```

All thresholds live in configuration and are tuned/documented through evaluation.

### Starting source weights

| Source type | Initial weight |
|---|---:|
| Peer-reviewed / original research | 1.00 |
| Government / official statistics | 0.95 |
| Recognized research institution | 0.90 |
| Established reporting | 0.75 |
| General website | 0.55 |
| Unknown blog/social post | 0.30 |

These are heuristic starting values, not universal truth scores.

## Data model

- `investigations`: id, input_type, raw_text, source_url, status, share_slug, created_at
- `claims`: id, investigation_id, claim_text, selected, position
- `sources`: id, investigation_id, url, domain, title, published_at, source_type, source_weight
- `evidence`: id, claim_id, source_id, passage_text, similarity, stance, stance_confidence, evidence_score
- `assessments`: id, claim_id, support_total, contradict_total, verdict, explanation, model_metadata

Embeddings do **not** need to be persisted in V1.

## API

- `POST /api/v1/inputs/claims`
- `POST /api/v1/inputs/url`
- `POST /api/v1/inputs/image`
- `POST /api/v1/investigations`
- `GET /api/v1/investigations/{id}`
- `GET /api/v1/reports/{share_slug}`
- `POST /api/v1/extension/check`

Use Pydantic schemas and structured errors. Never expose provider exceptions directly.

## UI: editorial, not AI

**Use:** warm white background, charcoal type, one restrained deep-blue/green accent, strong rules/dividers, evidence-first layout, square/light 4–6px corners, plain language, subtle motion.

**Avoid:** purple/blue gradients, neon colors, chatbot bubbles, assistant avatars, giant hero text, sparkles, floating blobs, “AI-powered truth engine,” every section in a rounded card.

Suggested tokens:

- background: `#F7F5EF` / `#FAF9F5`
- primary text: `#171717`
- muted: `#676760`
- accent: around `#244B5A`
- support: muted deep green
- contradict: muted brick/red
- mixed: muted ochre
- insufficient: neutral gray

## Required screens

1. Home / New Check
2. Claim Selection
3. Checking State (real stages; no fake percentage)
4. Investigation Result
5. Share Report
6. Methodology
7. Extension Side Panel

### Result hierarchy

```text
CLAIM CHECK                                      Share
----------------------------------------------------------------
CLAIM
"..."

ASSESSMENT
UNSUPPORTED
Short evidence-grounded explanation.

WHAT WE CHECKED
- interpretation/sub-question

----------------------------------------------------------------
EVIDENCE AGAINST
01  source / date
    relevant excerpt

EVIDENCE SUPPORTING
01  ...

----------------------------------------------------------------
METHODOLOGY / TECHNICAL DETAILS
----------------------------------------------------------------
Limitations · Checked at timestamp
```

## Browser extension

- Manifest V3
- selected text context menu: “Check with Claim Check”
- Side Panel result
- send selected text + page URL + page title
- “Check this page” opens article/claim-selection flow
- no separate ML logic in extension

## Student-style comments

Good:

```python
# Keep the threshold configurable so we can tune it on the validation set.
if similarity < settings.min_similarity:
    continue

# NLI confidence describes the relationship between this passage and the
# claim. It is not the probability that the real-world claim is true.
stance, confidence = nli.classify(claim, passage)
```

Bad:

```python
# Increment i
i += 1

# Call the function
result = get_result()
```

Rules:

- docstrings for public services and non-obvious algorithms
- short comments for decisions, assumptions, units, thresholds, edge cases
- keep comments focused on code behavior and implementation decisions
- descriptive names instead of excessive comments

## Error handling

- unreadable URL → offer paste-text path
- search failure → return error, never invent evidence
- no relevant evidence → insufficient evidence
- low-confidence NLI → uncertain/neutral
- OCR uncertainty → user edits extracted text
- paywall/block → do not fabricate passage
- claim extraction failure → manual claim entry

## Evaluation

Store evaluation data/scripts/results in the repo.

- Retrieval: Recall@5 / Recall@10
- NLI: precision / recall / F1 / confusion matrix
- Verdict: small labelled end-to-end set + manual error review
- UX: test all input types and extension flows

README metrics must come from saved evaluation output. Never invent numbers.

## Testing

- backend units: cosine ranking, thresholds, source weights, evidence score, verdict logic
- error cases: malformed URL, empty input, OCR fail, no search results, no relevant evidence
- API contract tests
- frontend component tests
- at least one Playwright e2e path using mocked external providers
- provider adapters must be mockable

## Security/privacy basics

- env vars for secrets; `.env.example` contains names only
- do not log keys/auth headers
- protect URL fetching against obvious SSRF
- image upload size/type limits
- sanitize fetched text/HTML
- rate-limit public creation before release
- clear methodology/limitations

## Milestones

| Milestone | Definition |
|---|---|
| M0 | Repository foundation, lint/format, env, health route, DB connection, CI smoke tests |
| M1 | Typed-claim vertical slice using deterministic fixtures |
| M2 | Live search + article extraction |
| M3 | Embedding retrieval + Recall@K harness |
| M4 | NLI + evidence scoring + evaluation |
| M5 | URL/article claim selection |
| M6 | Screenshot/OCR input |
| M7 | Shareable reports |
| M8 | Browser extension |
| M9 | Evaluation + UX/accessibility polish |
| M10 | Portfolio release: README, screenshots, demo, deployment, tagged release |

## GitHub release rules

- incremental commits, not one giant generated commit
- keep `PROJECT_SPEC.md` and ML notes
- README explains choices in your own words
- measured metrics + saved result files
- honest limitations section
- 2–4 screenshots + short demo clip/GIF

## CV wording — only after implementation

> **Claim Check — Multimodal Evidence Verification Platform | Next.js, TypeScript, FastAPI, Python, NLP**  
> Built a full-stack claim investigation platform that accepts text, URLs, screenshots, and browser-selected content. Implemented semantic evidence retrieval using text embeddings and cosine similarity, NLI-based support/contradiction classification, and a transparent evidence-scoring algorithm with an insufficient-evidence state. Added shareable reports, a Manifest V3 browser extension, automated tests, and an evaluation harness for retrieval and classification performance.

Do not use this wording until the features are genuinely implemented.

## Future work — only if V1 evaluation justifies it

- BM25/hybrid retrieval
- cross-encoder reranking
- source deduplication/clustering
- NLI fine-tuning
- learned source-quality model
- accounts/history

## Official references

- Next.js: https://nextjs.org/docs
- FastAPI: https://fastapi.tiangolo.com/tutorial/
- Chrome Extensions: https://developer.chrome.com/docs/extensions
- Chrome Side Panel API: https://developer.chrome.com/docs/extensions/reference/api/sidePanel
