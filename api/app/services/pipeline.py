from datetime import UTC, datetime

from app.core.settings import Settings
from app.schemas.investigation import Assessment, AtomicAssessment, Evidence
from app.services.collection import collect_evidence
from app.services.embeddings import EmbeddingProvider
from app.services.evidence_scoring import assess
from app.services.independence import source_group
from app.services.nli import NLIProvider
from app.services.proposition_relevance import relevance_score
from app.services.propositions import decompose_claim
from app.services.retrieval import rank_passages
from app.services.search import SearchProvider, follow_up_query, search_queries
from app.services.source_quality import source_quality
from app.services.temporal_scope import context_exclusion, needs_current_evidence

# structured_contradiction.py (group 2, phase 10) is intentionally not wired
# in here -- see the comment on `structured_signal` below in check_atomic.


def temporal_exclusion(
    claim: str, published_at: str | None, settings: Settings
) -> str | None:
    """Explicitly current claims require recent dates; age does not establish truth."""
    if not needs_current_evidence(claim):
        return None
    try:
        published = datetime.fromisoformat(published_at[:10]).replace(tzinfo=UTC)
    except (ValueError, TypeError):
        return "Currentness cannot be established without a usable publication date."
    age = (datetime.now(UTC) - published).days
    if age < 0 or age > settings.current_evidence_days:
        return "The publication date is outside the current-evidence window."
    return None


def relevance_weight_and_directness(score, settings, floor=None):
    """Grade relevance instead of a hard cliff (hyper pass, phases 3-4).

    Below the floor the passage is irrelevant and excluded outright, as
    before. Between the floor and min_proposition_relevance it used to be
    discarded entirely; it now contributes at a steep discount instead, since
    the false-abstention analysis found real supporting/contradicting
    passages being thrown away in exactly that band. At/above
    relevance_full_weight, relevance no longer discounts evidence_score.
    Piecewise-linear, not learned -- built from the existing cross-encoder
    score, no new model.

    `floor` defaults to settings.relevance_floor; gate_stance passes a more
    permissive, contradiction-specific floor for that stance (remediation
    pass 5, parts 5/8) so the continuous weight curve can extend below 0.0
    for evidence that would otherwise be excluded outright.
    """
    floor = settings.relevance_floor if floor is None else floor
    knee, ceiling = settings.min_proposition_relevance, settings.relevance_full_weight
    if score <= floor:
        return 0.0, "irrelevant"
    if score >= ceiling:
        return 1.0, "direct"
    if score >= knee:
        span = ceiling - knee
        weight = 0.55 + 0.45 * ((score - knee) / span if span > 0 else 1)
        return weight, "direct" if weight >= 0.85 else "related"
    span = knee - floor
    weight = 0.15 + 0.40 * ((score - floor) / span if span > 0 else 1)
    return weight, "contextual"


def gate_stance(claim, passage, stance, confidence, published_at, settings):
    """Retain the model output separately from conservative evidence eligibility."""
    exclusion = temporal_exclusion(claim, published_at, settings)
    exclusion = exclusion or context_exclusion(claim, passage)
    score = relevance_score(claim, passage, settings.proposition_model)
    # Remediation pass 5, parts 5/8: contradiction evidence is checked
    # against its own, more permissive floor (see settings.py for the
    # multi-fold evidence this was chosen on); every other stance keeps the
    # original general floor unchanged.
    floor = (
        settings.contradiction_relevance_floor
        if stance == "contradict"
        else settings.relevance_floor
    )
    weight, directness = relevance_weight_and_directness(score, settings, floor=floor)
    if weight <= 0:
        exclusion = exclusion or (
            f"Proposition relevance {score:.2f} is at or below the irrelevance "
            f"floor {floor:.2f}; topic overlap is insufficient."
        )
    if stance == "contradict" and confidence < settings.min_contradiction_confidence:
        exclusion = (
            exclusion
            or "Contradiction confidence is below the required operating point."
        )
    stance = "neutral" if exclusion else stance
    return stance, exclusion, score, directness, weight


def _gather_evidence(claim, settings, search, embeddings, nli, queries=None):
    candidates = collect_evidence(
        claim,
        search,
        max_sources=settings.max_sources,
        passage_words=settings.passage_words,
        max_passages=settings.max_passages,
        queries=queries,
    )[: settings.max_passages]
    unique = {}
    for article, passage in candidates:
        key = " ".join(passage.casefold().split())
        old = unique.get(key)
        if (
            old is None
            or source_quality(article.domain, settings)[1]
            > source_quality(old[0].domain, settings)[1]
        ):
            unique[key] = (article, passage)
    candidates = list(unique.values())
    # Source diversity (hyper pass, group 2, phase 13): cap how many
    # candidate passages from one registrable domain can occupy the ranking
    # window, so a single prolific source cannot crowd out differently-
    # sourced evidence before it ever reaches similarity ranking or NLI.
    # collect_evidence already round-robins across distinct URLs, but many
    # URLs can share one domain (e.g. a syndicated wire feed), which this
    # catches. Order-preserving, so it doesn't change which passage from a
    # capped domain is kept.
    if settings.max_candidates_per_domain:
        per_domain: dict[str, int] = {}
        diverse = []
        for article, passage in candidates:
            group = source_group(article.url)
            count = per_domain.get(group, 0)
            if count >= settings.max_candidates_per_domain:
                continue
            per_domain[group] = count + 1
            diverse.append((article, passage))
        candidates = diverse
    ranked = rank_passages(
        claim,
        [text for _, text in candidates],
        embeddings,
        settings.top_k,
        settings.min_similarity,
    )
    evidence = []
    for match in ranked:
        article, passage = candidates[match.index]
        stance, confidence = nli.classify(claim, passage)
        raw_stance = stance
        stance, exclusion, rel_score, directness, rel_weight = gate_stance(
            claim, passage, stance, confidence, article.published_at, settings
        )
        # Group 2 ablation: a deterministic structural contradiction check
        # (structured_contradiction.py) was built and validated here, but
        # measured on both the NLI-pair holdout and the 175-case controlled
        # replay, it fired only on cases the NLI model already got right at
        # 100% confidence and caught zero of its actual misses -- real
        # latency cost (an extra spaCy parse pair per evidence item) for
        # zero measured benefit. Left unwired per "remove anything that adds
        # complexity without measurable benefit." See GROUP2-RESULTS.md.
        structured_signal = None
        kind, weight = source_quality(article.domain, settings)
        evidence.append(
            Evidence(
                title=article.title,
                url=article.url,
                domain=article.domain,
                published_at=article.published_at,
                passage=passage,
                similarity=match.similarity,
                stance=stance,
                raw_stance=raw_stance,
                stance_confidence=confidence,
                source_type=kind,
                source_weight=weight,
                evidence_score=0,
                exclusion_reason=exclusion,
                atomic_claim=claim,
                structured_signal=structured_signal,
                relevance_score=rel_score,
                directness=directness,
                relevance_weight=rel_weight,
            )
        )
    return evidence


def check_atomic(claim, settings, search, embeddings, nli):
    evidence = _gather_evidence(claim, settings, search, embeddings, nli)
    result = assess(claim, evidence, settings)
    # Targeted follow-up search (hyper pass, group 2, phase 15): only when
    # the first pass found nothing usable at all -- not merely a case that
    # landed on INSUFFICIENT_EVIDENCE with some retained-but-weak evidence,
    # which is a legitimate, calibrated abstention, not a retrieval gap.
    no_usable_evidence = result.support_total == 0 and result.contradict_total == 0
    if (
        settings.allow_follow_up_search
        and settings.max_follow_up_queries > 0
        and no_usable_evidence
    ):
        follow_up = follow_up_query(claim)
        if follow_up and follow_up not in search_queries(claim):
            more = _gather_evidence(
                claim, settings, search, embeddings, nli, queries=[follow_up]
            )
            seen_urls = {e.url for e in evidence}
            evidence = evidence + [e for e in more if e.url not in seen_urls]
            result = assess(claim, evidence, settings)
    return result


def check_claim(
    claim: str,
    settings: Settings,
    search: SearchProvider,
    embeddings: EmbeddingProvider,
    nli: NLIProvider,
) -> Assessment:
    """Verify explicit propositions independently and preserve the original claim."""
    atoms = decompose_claim(claim, settings.max_atomic_claims)
    results = [check_atomic(atom, settings, search, embeddings, nli) for atom in atoms]
    evidence, coverage = [], []
    for result in results:
        indices = list(range(len(evidence), len(evidence) + len(result.evidence)))
        evidence.extend(result.evidence)
        coverage.append(
            AtomicAssessment(
                claim=result.claim,
                verdict=result.verdict,
                support_total=result.support_total,
                contradict_total=result.contradict_total,
                evidence_indices=indices,
            )
        )
    if len(results) == 1:
        results[0].claim = claim
        results[0].atomic_claims = coverage
        return results[0]
    verdicts = {r.verdict for r in results}
    if "UNSUPPORTED" in verdicts:
        verdict = "UNSUPPORTED"
    elif "MIXED_EVIDENCE" in verdicts:
        verdict = "MIXED_EVIDENCE"
    elif verdicts == {"SUPPORTED"}:
        verdict = "SUPPORTED"
    else:
        verdict = "INSUFFICIENT_EVIDENCE"
    explanation = "Each proposition was assessed separately. " + " ".join(
        f"{r.claim} — {r.verdict.replace('_', ' ').lower()}." for r in results
    )
    return Assessment(
        claim=claim,
        verdict=verdict,
        explanation=explanation,
        support_total=sum(r.support_total for r in results),
        contradict_total=sum(r.contradict_total for r in results),
        evidence=evidence,
        atomic_claims=coverage,
        verified_atom_fraction=sum(1 for r in results if r.verdict == "SUPPORTED")
        / len(results),
        contradicted_atom_fraction=sum(1 for r in results if r.verdict == "UNSUPPORTED")
        / len(results),
    )
