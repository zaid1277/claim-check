# Claim Check — Simple Project Guide

*A guide for explaining the project in interviews, career fairs and technical
conversations, kept in sync with the code and the final evaluation reports.*

**Current status:** a working evidence-analysis prototype with a documented,
measured accuracy ceiling around 80% on held-out data. It is explicitly not
production-ready fact-checking, and the project's own evaluation reports say
so directly — see [Evaluation and Reliability](#11-evaluation-and-reliability).

You don't need to memorize every model name to explain this project well.
Understand the journey from a claim to evidence, why each stage exists, and
be honest about where it still gets things wrong.

## 1. What Claim Check Is

### 10-second explanation

"Claim Check finds web evidence for a claim and shows whether the retrieved
passages support it, contradict it, or leave it unresolved."

### 30-second explanation

"I built an evidence-analysis tool with a Next.js frontend and a Python
backend. You type a claim, review sentences pulled from an article, or
correct text read from a screenshot. It searches the web, ranks passages by
relevance, and uses language models to compare each one with the claim. The
result shows the evidence, the scoring, and the system's own limitations —
it doesn't just hand you a verdict and hope you trust it."

### 60-second explanation

See [section 19](#19-my-60-second-interview-pitch) for the full version —
short version: it's an evidence pipeline, not an oracle. Every stage
(retrieval, relevance, stance classification, scoring) is separately
inspectable, and I measured each one honestly, including the parts that
didn't work as well as I wanted.

### 2-minute explanation

See [section 20](#20-my-2-minute-technical-explanation) for the full
walkthrough of the architecture, the scoring rule, and what the evaluation
actually found.

### A little more detail

The project tries to make claim checking *inspectable*. Instead of only
returning a verdict, it shows the passages, links, model classifications,
scores, and the reasons any evidence was excluded.

It asks a narrower question than "is this true": **what does the evidence I
found say about this specific statement?** A model can misread a passage, a
source can be wrong, and search can miss the evidence that actually matters.
That's why the honest framing is "evidence-analysis tool," not "fact
checker" — and why abstaining ("Insufficient Evidence") is a first-class,
frequently-correct outcome, not a failure state.

There are two operating modes: **live mode** uses real web search and local
models; **fixture mode** uses clearly labelled synthetic demonstration data
so the interface can be built and tested without pretending to do live
research.

## 2. The Problem I Was Trying to Solve

Claims are easy to repeat and expensive to check carefully. A page can
mention the right entity while discussing a completely different fact. An
article can be accurate for its publication date but wrong as evidence about
today.

Finding *a* source is only the start. The system has to ask: does this
passage actually address the claim, what relationship does it express, and
is there enough independent evidence to justify a verdict at all?

For example, a paragraph about a scientist's university doesn't establish
their birth year. Treating that as a contradiction would manufacture
disagreement out of missing information — and early versions of this
project genuinely did that kind of thing (see [section 10](#10-how-this-actually-developed)).

Sometimes the right answer is "I didn't find enough evidence." The
alternative — turning uncertainty into a confident guess — is worse than
useless for a claim-checking tool.

## 3. High-Level Architecture

```text
Typed claim ---------------------------------+
Article URL -> fetch page -> sentence review  |
Pasted text -------------> sentence review    |  Next.js / React interface
Screenshot -> OCR -> user correction ---------+
                                              |
                                              v
                                     FastAPI / Python API
                                              ^
Browser extension -> editable selection -------+
  via an explicitly approved web origin        |
                                              v
                          Validate input and reviewed claims
                                              |
                          Conservative atomic decomposition
                                              |
                            For each resulting proposition:
                                              |
                       Search (Tavily, or configured Brave)
                                              |
                       Fetch public pages / extract passages
                        (layered fallback — see section 10)
                                              |
                       MiniLM embeddings / cosine top-K ranking
                                              |
                       NLI: support / contradict / neutral
                                              |
                       Cross-encoder relevance re-score +
                       gating (confidence + relevance floor,
                       contradiction gated more carefully)
                                              |
                       Source grouping / near-duplicate handling
                                              |
                       Evidence scoring / per-atom assessment
                                              |
                       Combine atomic results into claim verdict
                                              |
                       PostgreSQL: save the completed investigation
                                              |
                       Response -> evidence UI / saved report
                                              |
                            Optional explicit share link
```

The **frontend** handles input, editing, and presentation — it never
computes the verdict itself. The **backend** validates requests, calls
search and local models, runs the scoring rules, and saves results. The
**database** makes completed results survive restarts. The **extension** is
just another client of the same backend, not a separate reasoning system.

The implementation is synchronous — the request waits for the investigation
to finish. There's no durable background job queue; the browser and proxy
allow a two-minute budget.

## 4. What Happens When I Check a Claim

Take **"The Eiffel Tower is in Paris."** — an illustration, not a special
case with different rules.

1. **Enter the claim.** For articles/screenshots, you review and edit
   proposed sentences first; up to five claims can be submitted together.
2. **Validate and normalize.** Request validation checks length and count;
   whitespace is normalized before the claim reaches search or NLI.
3. **Consider decomposition.** A simple claim stays intact. Clearly
   coordinated claims (conjunctions) can be split into smaller propositions
   — conservatively, capped at four atoms, preserving ambiguous scope.
4. **Generate search queries** — the claim itself, plus a couple of
   query variants (`... evidence research`, `... official statistics`).
5. **Search the web.** Tavily by default, Brave as a configured
   alternative. A live search failure never silently falls back to fixture
   data.
6. **Fetch source pages**, with bounded downloads and checks against
   private/internal destinations and redirect abuse.
7. **Extract readable text.** A layered fallback — strict extraction, a
   more permissive pass, then structured page metadata, then a last-resort
   visible-text pass — because no single extractor handles every real page
   (see [section 10](#10-how-this-actually-developed)).
8. **Build passages** of roughly 100 words, capped per source and per
   domain so one prolific source can't crowd out everything else.
9. **Rank by relevance.** MiniLM embeds the claim and passages; cosine
   similarity keeps the top-K (10 by default) above a similarity floor.
10. **Classify stance.** The NLI model reads the passage as premise and the
    claim as hypothesis, producing support / contradict / neutral plus a
    confidence score.
11. **Gate eligibility.** A cross-encoder re-scores relevance; low-relevance
    or low-confidence evidence is excluded — contradiction evidence gets
    its own, separately calibrated (more permissive) relevance floor, a
    change made after real generalization testing (section 10).
12. **Weight and group evidence** by a source-type heuristic; duplicate and
    near-duplicate passages from the same domain don't each add full weight.
13. **Aggregate** eligible support and contradiction scores *separately*
    per proposition.
14. **Produce the verdict** — for a decomposed claim, every atom's outcome
    matters, not just the first one.
15. **Save and display.** With PostgreSQL configured, the completed
    investigation is saved before the response returns. Sharing is a
    separate, explicit action.

An article's original text is *input* for proposing claims — it isn't
automatically treated as trustworthy evidence.

## 5. The Machine Learning Parts

### Embeddings

An **embedding** is a list of numbers representing a piece of text — imagine
placing sentences on a map where similar meanings end up nearby. Claim Check
uses `sentence-transformers/all-MiniLM-L6-v2` to embed the claim and each
candidate passage, then compares them. This makes shortlisting passages
practical on a local CPU, without a hosted retrieval service.

**Cosine similarity** compares the *direction* of two vectors, which
usually — not always — tracks related meaning. It does not measure truth:
"the museum opens on Mondays" and "the museum closes on Mondays" can be very
close, because they're about almost the same thing. That's exactly why
retrieval, relevance, and stance classification are three separate stages
here, not one.

### Cross-encoder / relevance model

`cross-encoder/ms-marco-MiniLM-L6-v2` reads the claim and a passage
*together*, rather than comparing separately computed vectors — think of
embeddings as shortlisting candidates and the cross-encoder as taking a
closer look at each one. It supplies a relevance score used for gating, not
a truth verdict, and it's still a general-purpose relevance model: it
doesn't prove entity identity or verify a specific predicate, and it
sometimes rejects genuinely useful counter-evidence. It runs only on the
already-shortlisted top-K set, so the extra cost is small.

### Natural Language Inference (NLI)

**NLI** compares two texts and predicts whether the first (the *premise*)
supports, contradicts, or leaves unresolved a second text (the
*hypothesis*). Here, the evidence passage is the premise and the claim is
the hypothesis.

| Evidence premise | Intended relation to "Tokyo is the capital of Japan." |
| --- | --- |
| "Tokyo is Japan's capital." | Support |
| "Kyoto is the capital of Japan." | Contradiction (a hypothetical conflicting premise, not a claim this doc endorses) |
| "Tokyo hosted the Olympics." | Neutral |

**Neutral matters.** It doesn't always mean "unrelated" — the Olympics
sentence mentions Tokyo but answers a different question entirely.

The model outputs class probabilities; the code reads the winning class
through the model's own label mapping (never an assumed numeric order — a
mistake that would silently invert every prediction). Below a confidence
threshold (0.65) the returned stance becomes neutral rather than a
low-confidence guess; contradiction needs a separately calibrated, higher
bar (0.68, plus its own relevance floor — see section 10 for why).

The current default model is `MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli`,
chosen after directly benchmarking it against a smaller version of the same
model family and other practical local-CPU candidates — it won on every
axis measured (macro F1, contradiction precision *and* recall) at a real
but acceptable latency/memory cost. No model was trained from scratch for
this project's production path; a separate fine-tuning *experiment* was run
later and is discussed honestly in section 10 — it wasn't adopted.

### Atomic claim decomposition

An **atomic claim** is one smaller factual proposition — "the museum opened
in 1990 and closed in 2000" becomes two checks that keep the museum as their
subject. This uses spaCy's `en_core_web_sm` dependency parser (which
estimates grammatical relationships, like which subject belongs to which
verb) plus conservative rules, capped at four atoms. It deliberately avoids
several ambiguous constructions (negation, modal verbs like "may," embedded/reported
speech) because an early version of this splitting logic genuinely invented
an actor by mishandling reported speech — see section 10.

### Narrow safeguards, not general reasoning

A handful of pattern-based checks exist for known failure modes: version/edition
mismatches, reporting-year mismatches (a measurement from one year
shouldn't silently contradict a measurement from another), and a
"currentness" check for present-tense claims that require a recent
publication date. These are narrow safeguards, not a general temporal or
numerical reasoner — they catch specific patterns that were observed to
cause real errors, and nothing more.

## 6. Evidence Scoring

For each retained passage:

```text
Evidence score = cosine relevance × NLI confidence × source weight
```

- **Cosine relevance** — how close the claim and passage embeddings are.
- **NLI confidence** — the model's confidence in the *relationship it
  classified*, not the probability the claim is true.
- **Source weight** — a small, reviewable domain/category heuristic (research
  1.0, official 0.95, institution 0.90, reporting/encyclopedia 0.75, general
  0.70, unknown 0.30) — not a learned trustworthiness score.

The cross-encoder score isn't multiplied into this formula; it only decides
eligibility. Excluded evidence contributes to neither directional total.

Supporting scores form total **S**; contradicting scores form total **C** —
kept as two separate positive totals, not one signed net score, which
matters because a claim with lots of *both* strong support and strong
contradiction should read as genuinely mixed, not cancel out to a false
"no evidence."

Before totaling, the system keeps only the strongest item per registrable
domain per stance, and treats passages with very high word-overlap
(Jaccard ≥ 0.9) as near-duplicates. This reduces repeated-source inflation
but doesn't establish true independence — a translated or paraphrased copy
can still slip through, a known, documented limitation.

## 7. The Four Verdicts

```text
If S + C < minimum_evidence:  INSUFFICIENT_EVIDENCE
Otherwise if S >= 2×C:        SUPPORTED
Otherwise if C >= 2×S:        UNSUPPORTED
Otherwise:                    MIXED_EVIDENCE
```

- **Supported** — retained evidence clearly favors the claim (≥2:1). Doesn't
  mean "all possible evidence was found," just that what was retained backs
  the claim.
- **Unsupported** — retained evidence clearly contradicts the claim (≥2:1).
  The name is easy to misread: it means *substantial contradicting
  evidence*, not merely "we didn't find support."
- **Mixed Evidence** — enough combined evidence, but neither side dominates.
  Genuine disagreement produces this correctly; irrelevant passages
  misclassified as contradictory can also produce it incorrectly — a known
  failure mode, not a solved one.
- **Insufficient Evidence** — eligible evidence is too weak, sparse, or a
  compound claim has unresolved parts. This is an explicit abstention, and
  it's frequently the *correct* answer, not a fallback for a broken system.

For a decomposed claim, every atom's outcome matters: any unsupported atom
makes the whole claim unsupported; otherwise any mixed atom makes it mixed;
every atom must be supported for the whole to be supported.

## 8. Why These Technologies Were Chosen

| Technology | What it does | Why it fits |
| --- | --- | --- |
| Next.js / React / TypeScript | Input, review, and report UI | One app handles interactive editing and server-rendered report pages, with typed request/response shapes |
| FastAPI / Pydantic | Python HTTP API | Fits Python's ML ecosystem; strict validation keeps malformed input away from the pipeline |
| PostgreSQL / Psycopg | Durable reports | Claims, sources, and evidence have clear relational structure; no ORM needed at this scale |
| Tavily (+ optional Brave) | Web search | Outsources search instead of building a crawler; results are still checked, not trusted blindly |
| Trafilatura, layered | Article extraction | A strong general extractor, with a documented fallback chain for the pages it alone missed |
| Sentence-Transformers MiniLM | Local embeddings | Small enough for interactive CPU latency, good enough for a first-pass relevance ranking |
| Cross-encoder relevance model | Pairwise relevance re-score | Cheap because it only runs on an already-shortlisted set; catches "same topic, wrong question" cases embeddings alone miss |
| DeBERTa-v3-large NLI | Stance classification | Won a direct benchmark against smaller local-CPU candidates on every measured axis |
| spaCy `en_core_web_sm` | Conservative claim decomposition | Enough grammatical structure to split clear conjunctions safely, without a generative rewriting model |
| RapidOCR (ONNX Runtime) | Screenshot text extraction | CPU-friendly, no GPU dependency, matching the project's local-first constraint |
| Manifest V3 / plain JavaScript | Browser extension | Thin client over the same API — no ML logic duplicated in the browser |
| pytest / Vitest / Playwright / axe | Testing | Unit, component, and real-browser coverage, including accessibility |

## 9. Why I Did NOT Just Use an LLM

The goal was something inspectable and measurable, not a conversational
model producing an unexplained answer. Each stage — retrieval, relevance,
stance classification, aggregation — has one job, so when a verdict is
wrong I can find which stage failed. Explanations are template-generated
from the scored evidence, not written by a generative model, which removes
one route for invented text (though NLI can still misclassify a real
relationship, and sources can still be wrong).

This project *did* later test an LLM-based verifier as a genuine
architecture alternative — and rejected it because it measured clearly
worse, not because LLMs were dismissed on principle. See section 10.

## 10. How This Actually Developed

This is the honest version of how the system got to where it is —
including the parts that didn't work.

**Early over-abstention.** The first working version was too eager to say
"insufficient evidence" — clean-looking passages were routinely excluded by
gates tuned without enough evidence behind them, which looked "safe" but
actually threw away real, usable evidence.

**Graded relevance weighting.** A hard relevance cutoff (in or out) was
replaced with a graded discount curve — passages between a floor and a
full-weight threshold contribute at a reduced weight instead of being
discarded outright. This recovered real evidence that a hard cliff had been
losing, without needing to loosen the underlying thresholds.

**Contradiction generalization.** A contradiction-confidence threshold that
looked strong on its own development split (~88% precision / 75% recall)
did *not* hold up on a genuinely independent holdout (dropped to ~76%/58%,
with a false-contradiction rate creeping up too) — a real generalization
gap, not a measurement fluke. The fix that actually held up on a second,
independent confirmation holdout was a **two-signal gate**: confidence
*plus* a separately calibrated, more permissive relevance floor specifically
for contradiction evidence, validated with a multi-fold (3-fold) corpus
before ever being checked against held-out data. That's why contradiction
evidence in the code has its own floor, not the general one.

**OCR harness fix.** The OCR/cross-modal *evaluation harness* itself was
broken for three consecutive measurement passes (a Playwright/browser-automation
bug that made real OCR unmeasurable, not a production OCR defect) — worth
knowing because "the test said 0%" was a test bug, not a product bug, and
finding that took real debugging before the actual OCR pipeline could be
measured at all.

**URL fallback.** Public-article extraction was measurably too narrow — a
single-strategy extractor missed real, legitimately-extractable pages. A
layered fallback chain (described in section 4, step 7) measurably improved
completion on an independent URL benchmark.

**Independent holdouts, every time.** Each of these fixes was validated on
data the fix was *not* tuned against — a standing rule for this project.
When a later, harder confirmation holdout showed some metrics regressing
even after a fix that helped its own target metric (contradiction
generalization improved; overall accuracy and coverage did not), that was
reported as "not ready," not smoothed over.

**Diagnosing the real ceiling.** A dedicated diagnostic pass asked a
precise question: is the *bottleneck* how evidence gets combined, or the
NLI model's own raw judgment? By re-running the real aggregation logic with
gating bypassed, it measured the gating/aggregation layer at roughly 98%
efficiency — meaning the ceiling is set almost entirely by the NLI model's
own accuracy (~80% raw), not by scoring rules. That reframed everything
downstream: further threshold tuning wasn't going to move the number much.

**Trying to raise that ceiling — and being honest when it didn't work.**
Two genuinely different architecture changes were tried:

- A **LoRA fine-tune** of the NLI model on a freshly built, from-scratch
  training corpus (never touching any holdout used to *evaluate* the
  system). It measured a real but modest gain (+1.95 macro F1 points) with
  properly separated validation — not enough to clear this project's own
  adoption bar, and it showed a real regression on hard cases in an
  end-to-end replay. **Not adopted**, and the report says exactly why.
- A **local, evidence-grounded LLM verifier** (a small instruction-tuned
  model, prompted to judge only whether the *supplied evidence* establishes
  the claim, not whether the claim is true in general). This measured
  clearly *worse* than the existing NLI model — a 26-point drop in macro
  F1, at roughly 30x the latency. **Not adopted.** This is a genuinely
  useful negative result: it rules out "just use an LLM" as a shortcut with
  the resources actually available here, rather than leaving that question
  open.

**The honest conclusion:** this system's measured accuracy ceiling with
free/local resources is around 80%, set primarily by the NLI model's own
raw capability rather than by retrieval, scoring, or gating logic. Getting
materially past that would need a stronger verifier than anything tested
here — see [`docs/accuracy95-development-report.md`](accuracy95-development-report.md)
for the full accounting.

## 11. Evaluation and Reliability

This project's evaluation is a chain of independent measurement
generations, not one number — each generation built new data, measured
honestly, and said plainly what did and didn't work. The full list is in
[`../evaluation/README.md`](../evaluation/README.md).

The most recent confirmation-holdout result (150 independent investigations,
run once against pre-committed targets):

| Metric | Result |
| --- | --- |
| Overall verdict accuracy | 76.0% |
| Coverage (non-abstention rate) | 62.0% |
| Selective accuracy (accuracy among non-abstentions) | 91.4% |
| Easy / medium / hard accuracy | 90.0% / 98.0% / 48.3% |
| Contradiction precision / recall / F1 | 85.7% / 66.7% / 75.0% |
| False contradiction rate | 4.52% |

This pass's *targeted* fixes (contradiction precision/recall/false-rate)
were genuinely achieved and independently validated. Overall accuracy,
coverage, and hard-case accuracy were **not** improved and remain below
target — reported as "not ready" rather than reframed as a success. Full
detail, including exactly which of 13 pre-committed targets were met and
which weren't: [`docs/remediation-final-report.md`](remediation-final-report.md).

A separate diagnostic pass found the aggregation/gating layer runs at ~98%
efficiency — the accuracy ceiling is set by the NLI model's raw judgment
(~80% raw success on the same evidence), not by how evidence is scored or
combined. Two attempts to raise that raw number (a fine-tune, a local LLM
verifier) didn't clear the bar — see section 10 above and
[`docs/nli-upgrade-report.md`](nli-upgrade-report.md) /
[`docs/accuracy95-development-report.md`](accuracy95-development-report.md).

**Precision, recall, and F1**, for anyone who needs the refresher:
**precision** asks "of everything I predicted positive, how many actually
were?" — low precision means too many false alarms. **Recall** asks "of
everything that actually was positive, how many did I catch?" — low recall
means real cases get missed. They trade off against each other (a model
that predicts "contradiction" constantly gets perfect recall and terrible
precision), so **F1** (their harmonic mean) is used to balance both into
one number when neither alone tells the full story. This project tracks
contradiction precision and recall *separately*, deliberately, because
optimizing only for accuracy would hide exactly this kind of tradeoff — a
threshold that refuses too many real contradictions can look "safer" while
actually being worse.

**Coverage and abstention**: coverage is the fraction of investigations
that get a real verdict rather than "Insufficient Evidence." A system that
abstains on everything hard would show high *selective* accuracy (it's only
right about the easy cases it dares to answer) while covering very little —
which is exactly why both numbers are reported together, never one without
the other.

## 12. Testing

A **regression test** reproduces a bug so a future change can't silently
reintroduce it. This project's tests check both individual functions and
the boundaries between components — the most recorded, full run (backend
with PostgreSQL and real models enabled, no skips) passed 167 backend
tests, 13 frontend component tests, 2 extension tests, and 14 Playwright
flows across Chromium and WebKit (7 flows × 2 browsers), with embedded
accessibility (axe-core) checks passing on both. Lint, formatting, type
checking, and the production build all pass. See
[`docs/github-release-checklist.md`](github-release-checklist.md) for the
exact commands, and the root README's "Running Tests" section for how to
reproduce this.

Testing matters because a correct model prediction is useless if the API
mishandles a field, the browser submits uncorrected OCR text instead of the
user's edits, or saving a report silently drops evidence. Conversely, a
passing software test suite doesn't prove unfamiliar claims get correct
verdicts — that's what the evaluation reports in section 11 are for. These
are deliberately two separate kinds of confidence, and neither substitutes
for the other.

## 13. Database

| Table | Stores |
| --- | --- |
| `investigations` | Input type, source URL, status, creation time, mode, optional share slug |
| `claims` | Selected claim text, order, parent investigation |
| `sources` | URL, domain, title, publication date, source category and weight |
| `evidence` | Passage text, links to claim/source, similarity, stance, confidence, score |
| `assessments` | Support/contradiction totals, verdict, explanation, model metadata |

A **UUID** identifies each record; a separately generated share slug
identifies a public report link — publishing sets that field on the
investigation rather than duplicating data into a second table. Memory-only
storage (fixture mode without a database) disappears on restart and is
explicitly a demo-only fallback. Embeddings and uploaded images are never
persisted. There are no accounts or private permissions — anyone with a
report link can read its visible contents.

## 14. Browser Extension

```text
Highlight webpage text
  -> right-click "Check with Claim Check"
  -> service worker opens the side panel
  -> selection and page context go into session storage
  -> user reviews/edits the claim and clicks Check
  -> the approved web origin's /api/v1/extension/check
  -> same investigation pipeline and report storage as the web app
  -> side-panel result, with a link to the full saved report
```

A **Manifest V3** extension declares its permissions and pages plus an
event-driven background service worker (it reacts to browser events rather
than staying open as a page). A separate **Check this page** action opens
the web app's URL-review flow with the current page's URL — the backend
still retrieves its own evidence; highlighting text on a page doesn't make
that page's own claims authoritative. Provider keys always stay server-side;
the extension is a thin client, never a second copy of the ML pipeline.

## 15. Current Limitations

- **Search limits what can be checked** — missing pages, paywalls, and
  extraction failures can hide decisive evidence.
- **NLI is imperfect** — confident misclassifications, entity confusion, and
  missed negation/numeric detail remain real, measured error modes.
- **Gating has a real cost** — tighter contradiction gates reduce false
  positives but measurably cost recall; this project reports both rather
  than only the flattering one.
- **Source weighting is a coarse heuristic**, not a learned or comprehensive
  credibility system, and copied/syndicated content can look independent.
- **Decomposition is conservative** — it misses legitimate splits and
  avoids resolving ambiguous pronouns or reported speech on purpose.
- **Claim proposals are sentence heuristics**, not a trained extraction
  model — always meant to be reviewed and edited, not trusted blindly.
- **OCR needs review** — dates, names, and numbers can be misread; the
  product enforces an edit step precisely because of this.
- **No durable job queue, no multilingual claim, no calibrated truth
  probability** — requests run synchronously with a two-minute budget.

## 16. What Makes This Project Technically Interesting

1. Connecting several NLP stages while keeping their responsibilities
   genuinely separate (and separately measurable).
2. Distinguishing semantic retrieval from proposition relevance from stance
   classification — three different failure modes, three different fixes.
3. A real, working example of separating "did the software work" from "was
   the conclusion correct," with independent evidence for each.
4. A documented diagnostic technique (bypassing gating to isolate
   aggregation cost from model-capability cost) that cleanly located the
   actual bottleneck instead of guessing at it.
5. Two honestly-reported *negative* results (a fine-tune that wasn't enough,
   an LLM verifier that measured worse) — knowing what doesn't work, and
   being able to show the measurement, is its own kind of engineering
   value.
6. Multiple independent, disjoint holdouts used the way holdouts are
   supposed to be used — never tuned against, and reported honestly even
   when the news wasn't good.

## 17. Interview Questions I Might Get

**What does your project do?** It collects web evidence and assesses how
that evidence relates to a claim — support, contradiction, both, or not
enough evidence to say.

**Why embeddings?** To find passages with related meaning even when the
wording differs, cheaply enough to shortlist candidates before more
expensive models run on them.

**What is cosine similarity?** The angle between two vectors — smaller
angle, more similar direction. It doesn't tell you the two texts agree,
just that they're about similar things.

**What is NLI?** A model that predicts whether one text (the premise)
supports, contradicts, or is neutral toward another (the hypothesis). Here
the evidence passage is the premise and the claim is the hypothesis.

**Why a cross-encoder too?** Embeddings are convenient for ranking many
candidates cheaply, but can overvalue topic overlap. The cross-encoder reads
the claim and passage together for a closer relevance check, on just the
shortlisted set.

**Why not just ask an LLM?** I wanted something inspectable and
measurable — and I actually tested that alternative (a local
evidence-grounded LLM verifier) rather than assuming it wouldn't work. It
measured clearly worse than the current approach; see section 10.

**Did you train the models?** The production NLI model is pretrained, not
trained from scratch — my work was selection, integration, and evaluation.
I *did* run a LoRA fine-tuning experiment as a separate research question;
it's documented and wasn't adopted into production.

**What's your actual accuracy?** About 76% overall verdict accuracy and
91.4% selective accuracy on the most recent independent confirmation
holdout — with coverage and hard-case accuracy still below what I'd want.
I can point to exactly which numbers, on which holdout, and what's still
weak.

**What would you improve next?** Coverage and hard-case accuracy are the
biggest open gaps from the most recent evaluation pass — see the
"Remaining limitations" section of `docs/remediation-final-report.md`.
Structurally, the ceiling is the NLI model's own raw judgment; closing that
gap needs a stronger verifier than what I could produce or run for free
locally, which is itself a finding worth having, not just a blocker.

**Can it run at production scale?** Not established, and not claimed.
Requests are synchronous with a bounded timeout; there's no durable worker
queue or demonstrated multi-user capacity.

## 18. Things I Should Be Able to Explain on a Whiteboard

| Topic | What to draw and say |
| --- | --- |
| Architecture | `Clients -> API -> search/models/scoring -> database -> reports`; name which layer owns each responsibility |
| Embeddings | Two nearby arrows for paraphrases — text becomes vectors so meaning can be compared numerically |
| Cosine similarity | The angle between two arrows — smaller angle, more similar direction, not the same truth value |
| Retrieval | `Many passages -> similarity sort -> top 10 above threshold` — some useful evidence is lost right here |
| NLI | Two boxes labeled premise/hypothesis, three outputs: support / contradict / neutral |
| Scoring | `relevance × confidence × source weight`; two separate S/C buckets, gating happens before the buckets |
| Precision vs. recall | Precision: of my positive predictions, how many were right? Recall: of the real positives, how many did I catch? |
| Abstention/coverage | Coverage = fraction that get a real verdict at all; report it alongside selective accuracy, never alone |
| Decomposition | `A and B -> check A; check B`; both must be supported; keep ambiguous scope intact rather than guess |

```text
cosine(a, b) = dot_product(a, b) / (length(a) × length(b))
```

## 19. My 60-Second Interview Pitch

"Claim Check is a project I built to investigate factual claims using
visible web evidence. You can type a claim, review sentences from an
article, or correct text read from a screenshot — there's also a browser
extension for selected text on any page.

The backend searches for sources, extracts passages, and uses embeddings to
find relevant text, then a cross-encoder and an NLI model to figure out
whether each passage actually supports or contradicts the claim. Evidence is
scored explicitly and aggregated into a verdict, with abstention as a real
outcome when there isn't enough good evidence.

The most interesting part was the reliability work: I built independent
holdouts, found that a contradiction threshold that looked great on its own
development data didn't generalize, fixed it with a two-signal gate that
*did* hold up independently, and then ran a diagnostic that showed the real
ceiling is the NLI model's own accuracy, not the scoring logic. I tried two
ways to push past that ceiling — a fine-tune and a local LLM verifier —
and I'm upfront that neither cleared the bar. It's a working prototype with
a real, measured ~80% accuracy ceiling, not a production fact-checker."

## 20. My 2-Minute Technical Explanation

"I built Claim Check as an evidence-analysis project rather than a chatbot
that just gives a yes-or-no answer. The frontend is Next.js/TypeScript, the
backend is FastAPI because the ML side is Python-based, and PostgreSQL
stores completed investigations, claims, sources, evidence, and assessments.

There are four input routes: typed claims, article URLs, pasted text, and
screenshots. Article and OCR text go through a review step where the user
edits proposed claim sentences before anything is investigated — that
review step exists specifically because claim proposal is a sentence
heuristic, not a trained extractor, and OCR can misread text.

For each claim, the system conservatively splits clear compound statements,
searches the web through Tavily or Brave, and extracts article text with a
layered fallback chain — because a single extraction strategy measurably
missed real pages. MiniLM embeddings and cosine similarity shortlist
relevant passages; a cross-encoder re-scores relevance on that shortlist;
an NLI model classifies each passage as supporting, contradicting, or
neutral. Contradiction evidence goes through its own, separately calibrated
gate, because a general-purpose threshold was measurably too aggressive
about excluding genuine contradictions.

Scoring is explicit: relevance times NLI confidence times a source weight,
accumulated into separate support and contradiction totals after
near-duplicate and same-domain grouping. Compound claims need every part
supported before the whole claim can be.

The most valuable engineering lesson was a diagnostic experiment: I
re-ran the real aggregation logic with gating bypassed to separate
'how much is the scoring/gating losing' from 'how much is the model itself
getting wrong.' That showed the gating layer is about 98% efficient — the
real ceiling is the NLI model's raw accuracy, around 80%. I tried a LoRA
fine-tune and a local LLM-based verifier to push past that, and reported
honestly that neither was good enough to adopt — the fine-tune's gain was
too small, and the LLM verifier measured 26 points worse in macro F1 at
30 times the latency. My most recent independent confirmation holdout shows
76% overall accuracy and 91.4% selective accuracy, with coverage and
hard-case accuracy as the clearest remaining gaps — and that's documented,
not hidden, in the project's evaluation reports."

## 21. CV Description

See the root README and `docs/github-release-checklist.md` for the exact,
approved CV wording used for this project — kept in one place so it can't
drift out of sync with what's actually true.

## 22. Cheat Sheet

| Remember | Current fact |
| --- | --- |
| Purpose | Inspectable evidence analysis; explicitly not a guaranteed truth detector |
| Frontend | Next.js App Router, React, TypeScript |
| Backend | Python 3.12, FastAPI, Pydantic |
| Database | PostgreSQL — claims, sources, evidence, assessments, saved/shareable investigations |
| Search | Tavily by default, optional Brave; no silent live-to-fixture fallback |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` |
| NLI | `MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli` |
| Relevance model | `cross-encoder/ms-marco-MiniLM-L6-v2` — an eligibility gate, not a reranker |
| OCR / grammar | RapidOCR (ONNX Runtime); spaCy `en_core_web_sm` for conservative decomposition |
| Evidence formula | Cosine relevance × NLI confidence × source weight |
| Key thresholds | Cosine 0.35, top-10; NLI confidence 0.65; contradiction confidence 0.68 + its own relevance floor; dominance ratio 2:1 |
| Verdicts | Below minimum evidence: insufficient. Otherwise 2:1 dominance gives supported/unsupported; remaining disagreement is mixed |
| Most recent confirmation holdout | 76.0% overall accuracy, 62.0% coverage, 91.4% selective accuracy (150 independent cases) |
| Contradiction metrics | Precision 85.7%, recall 66.7%, false-contradiction rate 4.52% |
| Measured accuracy ceiling | ~80%, set by NLI model raw accuracy (aggregation/gating measured ~98% efficient) |
| Tried and not adopted | LoRA NLI fine-tune (+1.95 F1, not enough); local LLM evidence-grounded verifier (-26 F1, 30x latency) |
| Latest recorded tests | 167 backend, 13 frontend, 2 extension, 14 Playwright (Chromium+WebKit), 0 accessibility violations |
| Biggest limitation | Coverage and hard-case accuracy remain below target; contradiction recall is a real, reported tradeoff |
| Biggest technical lesson | A metric that improves on its own development data can still fail to generalize — always confirm on independent, never-tuned-on holdout data |
