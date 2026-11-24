# Claim Check

An evidence-analysis tool for investigating factual claims: it retrieves web
passages, ranks them by relevance, classifies their stance with natural
language inference, and produces a weighted, cited assessment. It is a
research/portfolio project, not a production fact-checking service — see
[Limitations](#limitations) and [Evaluation](#evaluation) for exactly what it
does and doesn't establish.

## Overview

A claim can sound plausible while resting on weak, outdated, or contradictory
sources. Claim Check gathers relevant passages for a claim, scores how each
one relates to it, and shows its work: which passages support the claim,
which contradict it, which are related but inconclusive, and why the system
landed on its verdict. It is an evidence-analysis tool, not an oracle of
absolute truth, and it says so directly in every report it produces.

## Features

- Four input modes: typed claims, article URLs, pasted article text, and
  PNG/JPEG screenshots (OCR), with an editable review step before any claim
  is investigated.
- Live web search (Tavily by default, Brave as an alternative) with layered
  article extraction and a graceful pasted-text fallback when a page can't
  be read.
- Local embedding-based retrieval, a cross-encoder relevance re-score, and
  local NLI stance classification — no external LLM or generation API in
  the assessment path itself.
- Transparent, documented evidence scoring: every retained passage shows its
  relevance, stance confidence, and source-type weight, tucked behind a
  "Why this evidence?" disclosure rather than dumped inline.
- Four assessment outcomes (below) with cited, numbered evidence and an
  explicit abstention path when evidence is too weak to call.
- PostgreSQL-backed report storage with explicit, opt-in read-only sharing.
- A Manifest V3 browser extension for checking selected text or the current
  page from a right-click menu.
- Local-only first-run provider setup: validates a search-provider key and
  holds it in backend process memory only — never written to disk or
  returned through any API response.

Fixture mode (no live search key required) uses clearly labelled synthetic
evidence for demonstration; it never invents a result for an arbitrary claim.

## How It Works

```text
Claim → web search → article extraction → embeddings → cosine ranking
      → cross-encoder relevance → NLI stance → evidence scoring
      → weighted aggregation → cited assessment
```

1. Take a typed claim, extracted article sentences, or corrected OCR text,
   reviewed and editable before investigation.
2. Search the web and extract readable passages from public URLs (a layered
   fallback: strict extraction, then a more permissive pass, then structured
   page metadata, then a last-resort visible-text pass).
3. Embed the claim and candidate passages locally (MiniLM) and rank by
   cosine similarity, capping how many passages one domain can contribute.
4. Re-score the top passages with a cross-encoder for claim relevance, and
   classify each passage's stance toward the claim with a local NLI model.
5. Gate low-relevance or low-confidence evidence out (contradiction evidence
   uses a separately calibrated, more permissive relevance floor — see
   [`docs/final-configuration.md`](docs/final-configuration.md)).
6. Weight retained evidence by relevance × stance confidence × a documented
   source-type heuristic, and aggregate support and contradiction totals
   separately per atomic claim.
7. Produce a verdict, abstaining when evidence is too weak or too evenly
   split, and explain it with the retained, numbered citations.

Claim proposal from articles/OCR text uses simple sentence heuristics, not a
trained extraction model — that's why every proposed claim is reviewable and
editable before it's investigated. Explanations are template-generated from
the scored evidence, not written by a generative LLM.

## Architecture

```mermaid
flowchart TD
    Web[Next.js web app] --> API[FastAPI]
    Extension[Chrome / Edge extension] --> API
    API --> Review[Claim review & OCR/article extraction]
    Review --> Search[Tavily / Brave search + article extraction]
    Search --> Retrieval[MiniLM embeddings + cosine ranking]
    Retrieval --> Cross[Cross-encoder relevance re-score]
    Cross --> NLI[DeBERTa NLI stance classification]
    NLI --> Score[Evidence scoring + weighted aggregation]
    Score --> Reports[PostgreSQL report storage + sharing]
```

One synchronous FastAPI service serves both the web app and the browser
extension. External services (search, database) sit behind small interfaces
so they're mockable in tests and fixture mode. Models are loaded once per
process and cached; embeddings are computed per request, not stored.
[`docs/architecture.md`](docs/architecture.md) covers the request lifecycle,
security boundaries, and the reasoning behind each dependency choice in more
depth.

## Technology Stack

| Area | Technologies |
| --- | --- |
| Frontend | Next.js App Router, React, TypeScript, Tailwind CSS |
| Backend | Python, FastAPI, Pydantic, HTTPX, Trafilatura |
| Machine learning | Sentence-Transformers (MiniLM embeddings), a cross-encoder relevance model, a DeBERTa-v3-large NLI model (Transformers/PyTorch), RapidOCR (ONNX Runtime) |
| Database | PostgreSQL, Psycopg, SQL migrations |
| Browser extension | Plain JavaScript, Manifest V3, Side Panel API |
| Testing/tooling | pytest, Ruff, Vitest, Testing Library, Playwright, axe-core, ESLint, Prettier, GitHub Actions |

## Verdict Types

| Verdict | Meaning |
| --- | --- |
| **Supported** | Retained evidence weight clearly favors the claim (at least a 2:1 support-to-contradiction ratio, above the minimum evidence floor) |
| **Unsupported** | Retained evidence weight clearly contradicts the claim, by the same ratio |
| **Mixed Evidence** | Both sides have meaningful, retained evidence and neither dominates |
| **Insufficient Evidence** | Retained evidence is too weak, sparse, or low-confidence to call — an explicit abstention, not a guess |

Compound claims are split into atomic propositions and assessed individually;
the top-level verdict reflects how those propositions combine.
[`docs/final-configuration.md`](docs/final-configuration.md) has the exact
thresholds behind each of these, with the evidence behind each value.

## Evaluation

The [23 November 2026 release verification](docs/release-verification.md) records
the latest software checks and live smoke test. This is a portfolio preview;
the research reliability targets below remain unmet.

This project went through several independent measurement generations —
each one built fresh, disjoint evaluation data, measured honestly, and
reported what did and didn't work, including negative results. The full
chain, in order, is in [`evaluation/README.md`](evaluation/README.md); the
headline reports are:

- [`docs/final-reliability-report.md`](docs/final-reliability-report.md) and
  [`docs/hyper-final-reliability-report.md`](docs/hyper-final-reliability-report.md) —
  the first two independent frozen holdouts.
- [`docs/remediation-final-report.md`](docs/remediation-final-report.md) —
  targeted fixes (contradiction gating, URL extraction, OCR measurement),
  re-measured on a new confirmation holdout: **76.0% overall accuracy,
  62.0% coverage, 91.4% selective accuracy** on 150 held-out investigations.
  Contradiction precision/recall/false-contradiction-rate targets were met;
  coverage, hard-case accuracy, and public-URL completion were not — read
  first.
- [`docs/accuracy-max-report.md`](docs/accuracy-max-report.md) — a
  diagnostic pass (no production changes) that isolated the bottleneck: the
  gating/aggregation logic is ~98% efficient, so the ceiling is set by the
  NLI model's own raw accuracy, not by how evidence is combined.
- [`docs/nli-upgrade-report.md`](docs/nli-upgrade-report.md) and
  [`docs/accuracy95-development-report.md`](docs/accuracy95-development-report.md) —
  two follow-up attempts to raise that ceiling (a LoRA fine-tune, and a
  local LLM "evidence-grounded reasoning" verifier). Neither was adopted:
  the fine-tune's gains were too small to justify the added complexity, and
  the LLM verifier measured **worse** than the current model (-26 points
  macro F1) at over 30x the latency. Both reports say so plainly.

These controlled benchmarks measured roughly **76–81% verdict accuracy**,
with substantial abstention. They do not establish live-web accuracy or a
universal accuracy ceiling for local models. Diagnostic oracle results apply
only to the evaluated cases and retained evidence. The remaining errors and
attempts to reduce them are documented — see
[`docs/claim-check-explained.md`](docs/claim-check-explained.md) for the
full narrative of how that conclusion was reached.

The [November accuracy pass and research shortlist](docs/accuracy90-research.md)
records a small retrieval correction: development replay improved from 76.0% to
76.57%. This is not a new independent accuracy result, and 90% has not been reached.

## Getting Started

Prerequisites: Git, Node.js 24 LTS, Python 3.12, and Docker Compose (or an
existing PostgreSQL server) for durable/live investigations. No provider key
is required for the fixture demo.

```sh
git clone https://github.com/zaid1277/claim-check.git
cd claim-check
cp .env.example .env
```

Start the API (from the repository root):

```sh
cd api
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.lock
python -m pip install --no-deps --no-build-isolation -e .
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 --no-proxy-headers
```

In a second terminal, start the web app (from the repository root):

```sh
cd web
npm ci
npm run dev -- --hostname 127.0.0.1
```

Open [localhost:3000](http://localhost:3000), choose **Use demonstration
claim**, then **Check claim**. Without a database, fixture reports use a
bounded in-memory store and disappear on restart.

### PostgreSQL and live mode

See [`docs/postgresql.md`](docs/postgresql.md) for a local PostgreSQL setup
without Docker. With Docker Compose, set the database variables in `.env`
(sample-only credentials, for a new local database):

```dotenv
POSTGRES_USER=claim_check
POSTGRES_PASSWORD=local_dev_password
POSTGRES_DB=claim_check
DATABASE_URL=postgresql://claim_check:local_dev_password@localhost:5432/claim_check
```

```sh
docker compose up -d --wait
cd api
source .venv/bin/activate
python -m app.db.migrate
python -m pip install -r requirements-models.txt
```

For live web search, set `PROVIDER_MODE=live` and `TAVILY_API_KEY` in `.env`
and restart the API — or set `ALLOW_RUNTIME_PROVIDER_KEYS=true` and leave the
key blank to use the in-app local setup form instead (trusted localhost use
only; see [`docs/final-configuration.md`](docs/final-configuration.md)).
Models download on first live/OCR use.

## Environment Variables

`.env.example` (and `web/.env.example`) list every variable with a blank or
placeholder value — never real credentials. Copy and fill in your own.

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | PostgreSQL connection; unset for the ephemeral fixture demo |
| `PROVIDER_MODE` | `fixture` (default) or `live` |
| `SEARCH_PROVIDER` | `tavily` (default), `brave`, or fixture-only `mock` |
| `TAVILY_API_KEY` / `BRAVE_SEARCH_API_KEY` | Search-provider credentials |
| `ALLOW_RUNTIME_PROVIDER_KEYS` | Opt-in local-only key entry via the setup UI |
| `NLI_MODEL` | Optional model override; leave blank for the evaluated default |
| `API_BASE_URL` | Web-to-API origin (build-time for the web app) |

Full reference, including thresholds and their evidence:
[`docs/final-configuration.md`](docs/final-configuration.md).

## Running Tests

```sh
./scripts/verify.sh
# With browser/axe checks (after installing Chromium once):
cd web && npx playwright install chromium && cd ..
./scripts/verify.sh --browser
```

This runs backend lint/format/tests, frontend lint/format/typecheck/unit
tests, extension tests, and (with `--browser`) Playwright + accessibility
checks. It fails on the first failing check. Set `TEST_DATABASE_URL` to
include the PostgreSQL integration tests (they create and drop their own
randomly named schema — never point this at production).

Individual suites, from the repository root:

```sh
# Backend (api/, with the virtual environment active)
ruff check . ../evaluation && ruff format --check . ../evaluation && pytest -q

# Frontend (web/)
npm run lint && npm run format:check && npm run typecheck && npm test && npm run build

# Extension
cd web && npm run test:extension

# Browser end-to-end (after `npx playwright install chromium`)
cd web && npm run test:e2e
```

## Repository Structure

```text
api/app/api/       input, investigation, image, extension, report and health routes
api/app/core/      typed settings, safe errors and request limits
api/app/db/        connections, SQL migration runner and report stores
api/app/schemas/   validated requests and responses
api/app/services/  extraction, search, embeddings, retrieval, NLI and scoring
api/migrations/    PostgreSQL schema
api/tests/         unit/API and opt-in PostgreSQL integration tests
web/app/           Next.js routes and shared styles
web/components/    input/review workbench, evidence display and share action
web/e2e/           Playwright/axe flows
extension/         Manifest V3 client and handler tests
evaluation/         every measurement generation: corpora, harnesses, results
docs/              architecture, configuration, evaluation reports, guides
```

## Limitations

- This is not a production fact-checking service and is not marketed as one.
  Measured accuracy tops out around 80% on held-out data (see
  [Evaluation](#evaluation)) — verdicts are a weighted summary of retrieved
  evidence, not a guarantee about the world.
- NLI stance classification can miss context, negation, dates, and numeric
  detail; the [`docs/claim-check-explained.md`](docs/claim-check-explained.md)
  narrative documents specific known failure modes.
- Sentence-level claim extraction from articles/OCR text is heuristic, not a
  trained model — always review proposed claims before investigating.
- Source weights are a small, reviewable heuristic (domain/category-based),
  not a universal trust score.
- Public URL extraction can fail on paywalled, JS-heavy, or bot-protected
  pages; pasting the article text is the documented fallback.
- OCR quality depends on image clarity; always review and correct extracted
  text before it's investigated (the product enforces this review step).
- Requests run synchronously with a two-minute browser timeout; there is no
  durable background job queue.
- There are no accounts or private permissions — anyone with a shared
  report link can read its visible contents. Avoid submitting sensitive
  personal data.
- English, relatively short inputs are the tested focus. No claim of
  multilingual quality, calibrated truth probabilities, or professional
  (medical/legal/financial) advice is made — those domains need extra care
  and independent verification.

## Future Improvements

A materially higher accuracy ceiling would need a stronger evidence-grounded
verifier than what free/local resources in this project's development
environment could produce — see
[`docs/accuracy95-development-report.md`](docs/accuracy95-development-report.md)
for exactly what was tried and why it wasn't enough. Concretely: a larger,
better-labelled NLI/verifier training corpus (or access to a materially
stronger hosted model, which this project deliberately avoided paying for),
a measured retrieval-recall ceiling (blocked here by search-API quota), and
closing the coverage/hard-case accuracy gaps the remediation pass left open.
These are documented as future work, not implied to already work.

## Browser Extension

1. Run the local web/API services.
2. In Chrome open `chrome://extensions`, or in Edge open `edge://extensions`.
3. Enable Developer mode, choose **Load unpacked**, and select this
   repository's `extension/` directory.
4. On any page, highlight text and choose **Check with Claim Check** from
   the right-click menu, then review and submit it in the side panel.
5. Use **Open full investigation** for details or a share link; **Check
   this page** opens URL review in the web app.
6. For a deployed instance, open the extension's connection settings and
   approve its HTTPS web origin. Keep API keys on the server, never in the
   extension.

[`docs/source-guide.md`](docs/source-guide.md) points at the core
implementation files across the whole codebase.

## License

[MIT](LICENSE). Downloaded model weights and third-party dependencies retain
their own licenses; this project's license does not relicense those
artifacts.
