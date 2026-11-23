from app.core.settings import Settings
from app.schemas.investigation import Assessment, Evidence, Verdict
from app.services.claim_risk import claim_risk
from app.services.independence import same_content, source_group


def _authority_tiebreak(support_side, contradict_side, settings):
    """Group 3, phase 11/13: only when the dominance ratio alone can't
    resolve support vs. contradict, check whether one side is carried by a
    source clearly more authoritative than anything the other side has, AND
    the other side isn't itself well-corroborated by several independent
    sources. This is deliberately narrow: it never touches evidence that
    hasn't already cleared every relevance/eligibility gate (so it cannot
    "rescue" irrelevant evidence -- see phase 13), and a well-corroborated
    losing side (several independent sources) is left as MIXED_EVIDENCE
    rather than overridden, so "5 independent investigative sources" is
    never simply out-ranked by "1 official statement". Returns a Verdict or
    None (no tiebreak -- fall through to MIXED_EVIDENCE)."""

    def strongest(side):
        return max((e.source_weight for e in side), default=0.0)

    def independent_count(side):
        return len({e.independence_group for e in side})

    for winning_side, losing_side, verdict in [
        (support_side, contradict_side, "SUPPORTED"),
        (contradict_side, support_side, "UNSUPPORTED"),
    ]:
        if not winning_side:
            continue
        if strongest(winning_side) < settings.authority_tiebreak_min_weight:
            continue
        if strongest(losing_side) >= settings.authority_tiebreak_max_opposing_weight:
            continue  # the other side has a comparably authoritative source too
        if (
            independent_count(losing_side)
            > settings.authority_tiebreak_max_opposing_sources
        ):
            continue  # well-corroborated by several sources -- not a tiebreak case
        return verdict
    return None


def aggregate(
    support: float,
    contradict: float,
    independent_sources: int,
    settings: Settings,
    risk: str,
    support_evidence: list[Evidence] | None = None,
    contradict_evidence: list[Evidence] | None = None,
) -> Verdict:
    minimum_evidence = (
        settings.high_risk_minimum_evidence
        if risk == "high"
        else settings.minimum_evidence
    )
    dominance_ratio = (
        settings.high_risk_dominance_ratio
        if risk == "high"
        else settings.dominance_ratio
    )
    if support + contradict < minimum_evidence:
        return "INSUFFICIENT_EVIDENCE"
    if (
        risk == "high"
        and independent_sources < settings.high_risk_min_independent_sources
    ):
        # Enough total weight, but a high-risk claim still needs more than one
        # independent source before committing (hyper pass, phase 5/6).
        return "INSUFFICIENT_EVIDENCE"
    if support >= dominance_ratio * contradict:
        return "SUPPORTED"
    if contradict >= dominance_ratio * support:
        return "UNSUPPORTED"
    if settings.authority_tiebreak_enabled and support_evidence is not None:
        tiebreak = _authority_tiebreak(support_evidence, contradict_evidence, settings)
        if tiebreak is not None:
            return tiebreak
    return "MIXED_EVIDENCE"


def assess(claim: str, evidence: list[Evidence], settings: Settings) -> Assessment:
    """Keep opposing totals separate so disagreement cannot disappear by subtraction."""
    for item in evidence:
        item.evidence_score = (
            item.similarity
            * item.stance_confidence
            * item.source_weight
            * (item.relevance_weight if item.relevance_weight is not None else 1.0)
        )
    retained = []
    used: dict[tuple, int] = {}
    for item in sorted(evidence, key=lambda e: -e.evidence_score):
        item.independence_group = source_group(item.url)
        item.counted = item.stance != "neutral"
        if not item.counted:
            continue
        key = (item.independence_group, item.stance)
        duplicate = any(
            old.stance == item.stance
            and same_content(item.passage, old.passage, settings.duplicate_similarity)
            for old in retained
        )
        occurrences = used.get(key, 0)
        if duplicate:
            item.counted = False
            item.exclusion_reason = (
                "Near-duplicate content; not independent confirmation."
            )
        elif occurrences == 0:
            used[key] = 1
            retained.append(item)
        elif occurrences == 1:
            # A second passage from a domain already contributing this stance
            # is real evidence, not noise -- retain it at a steep discount
            # instead of discarding it outright (hyper pass, phase 3:
            # false-abstention subtype D). Capped at one discounted bonus
            # per domain+stance -- a third+ passage from the same domain
            # gets no further credit, so volume from one domain cannot
            # outweigh a single independent source without bound (hyper
            # pass, group 2, phase 13: caught a real confident error in
            # validation where an uncapped discount let a syndicated
            # source's repetition overwhelm one authoritative contradiction).
            used[key] = 2
            item.evidence_score *= settings.duplicate_source_weight
            item.exclusion_reason = (
                "Additional passage from an already-counted source; "
                "retained at reduced weight, not full independent confirmation."
            )
            retained.append(item)
        else:
            item.counted = False
            item.exclusion_reason = (
                "A third or later passage from an already-counted source "
                "adds no further independent weight."
            )
    support_evidence = [e for e in retained if e.stance == "support"]
    contradict_evidence = [e for e in retained if e.stance == "contradict"]
    support = sum(e.evidence_score for e in support_evidence)
    contradict = sum(e.evidence_score for e in contradict_evidence)
    independent_sources = len({e.independence_group for e in retained})
    risk = claim_risk(claim)
    verdict = aggregate(
        support,
        contradict,
        independent_sources,
        settings,
        risk,
        support_evidence,
        contradict_evidence,
    )
    if verdict == "INSUFFICIENT_EVIDENCE":
        explanation = (
            "The retained evidence is too weak or incomplete "
            "for a supported assessment."
        )
    else:
        explanation = {
            "SUPPORTED": "The retained passages predominantly support the claim.",
            "UNSUPPORTED": "The retained passages predominantly contradict the claim.",
            "MIXED_EVIDENCE": "The retained passages contain substantial disagreement.",
        }[verdict]
    citations = [
        f"[{i + 1}] {item.stance}: “{item.passage}”"
        for i, item in enumerate(evidence)
        if item.stance != "neutral" and item.counted
    ]
    explanation += " " + " ".join(citations)
    return Assessment(
        claim=claim,
        verdict=verdict,
        explanation=explanation.strip(),
        support_total=support,
        contradict_total=contradict,
        evidence=evidence,
    )
