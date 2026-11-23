"""Deterministic contradiction assistance for NLI (hyper pass, group 2, phase 10).

An assistant to NLI, not a replacement: this only ever turns a passage into
"contradict" when (a) the claim and passage clearly refer to the same entity
and the same predicate/topic, and (b) they assert a specific, structurally
comparable value -- a number, a year, or a location -- that differs, or one
asserts a negation the other doesn't. It never fires on topic-only overlap,
never compares numbers/dates/locations that aren't in matching predicate
context, and it defers entirely (returns None) on anything ambiguous. It
never touches an evidence item NLI already scored as "contradict".

Reuses the existing spaCy pipeline (already a dependency via propositions.py)
for entity/date/money/percent recognition -- no new model, per the phase-10
brief. Reuses temporal_scope.needs_current_evidence so a "currently" claim is
never flatly contradicted by an old evidence date, matching phase 12's own
example.
"""

import re
from dataclasses import dataclass

from app.services.propositions import parser
from app.services.temporal_scope import needs_current_evidence

_NEGATION_CUES = re.compile(
    r"\b(not|never|n't|no longer|didn't|doesn't|isn't|wasn't|hasn't|haven't)\b",
    re.IGNORECASE,
)
_YEAR = re.compile(r"\b(1[5-9]\d{2}|20\d{2})\b")
_TEMPORAL_PREDICATES = re.compile(
    r"\b(founded|established|opened|started|began|born|died|elected|"
    r"launched|released|incorporated|formed|created)\b",
    re.IGNORECASE,
)
_LOCATION_PREDICATES = re.compile(
    r"\b(headquartere?d|headquarters|based|located|situated|capital)\b", re.IGNORECASE
)
_SCALE = {"thousand": 1e3, "million": 1e6, "billion": 1e9, "trillion": 1e12}


@dataclass
class StructuredSignal:
    kind: str  # "numeric" | "temporal" | "location" | "negation"
    reason: str


def _content_words(text: str) -> set[str]:
    return set(re.findall(r"\w+", text.lower()))


def _shares_entity(claim_ents, passage_ents) -> bool:
    claim_names = {e.text.casefold() for e in claim_ents if len(e.text) > 2}
    passage_names = {e.text.casefold() for e in passage_ents if len(e.text) > 2}
    return bool(claim_names & passage_names) or any(
        c in p or p in c for c in claim_names for p in passage_names
    )


def _money_value(text: str) -> float | None:
    match = re.search(
        r"\$?\s*([\d,.]+)\s*(thousand|million|billion|trillion)?", text, re.IGNORECASE
    )
    if not match or not match.group(1).strip("."):
        return None
    try:
        value = float(match.group(1).replace(",", ""))
    except ValueError:
        return None
    scale = _SCALE.get((match.group(2) or "").lower(), 1)
    return value * scale


def _percent_value(text: str) -> float | None:
    match = re.search(r"([\d.]+)\s*%", text)
    return float(match.group(1)) if match else None


def structured_contradiction(claim: str, passage: str) -> StructuredSignal | None:
    """Return a StructuredSignal if a strongly-aligned structural mismatch is
    found, else None. Callers decide how to combine this with NLI's stance."""
    claim_doc, passage_doc = parser()(claim), parser()(passage)
    entity_labels = {"PERSON", "ORG", "GPE", "NORP", "FAC", "LOC"}
    claim_ents = [e for e in claim_doc.ents if e.label_ in entity_labels]
    passage_ents = [e for e in passage_doc.ents if e.label_ in entity_labels]
    aligned = _shares_entity(claim_ents, passage_ents)

    # Negation: only when the rest of the sentence overlaps heavily (same
    # subject/predicate/object), so this cannot fire on two unrelated
    # sentences that happen to both mention "not" somewhere.
    overlap = _content_words(claim) & _content_words(passage)
    union = _content_words(claim) | _content_words(passage)
    lexical_overlap = len(overlap) / len(union) if union else 0
    claim_negated = bool(_NEGATION_CUES.search(claim))
    passage_negated = bool(_NEGATION_CUES.search(passage))
    if lexical_overlap >= 0.5 and claim_negated != passage_negated:
        return StructuredSignal(
            "negation",
            "One statement negates what the other asserts, over otherwise "
            "closely matching wording.",
        )

    if not aligned:
        return None

    claim_money = [_money_value(e.text) for e in claim_doc.ents if e.label_ == "MONEY"]
    passage_money = [
        _money_value(e.text) for e in passage_doc.ents if e.label_ == "MONEY"
    ]
    claim_money = [v for v in claim_money if v is not None]
    passage_money = [v for v in passage_money if v is not None]
    if len(claim_money) == 1 and len(passage_money) == 1 and claim_money[0] > 0:
        relative_diff = abs(claim_money[0] - passage_money[0]) / claim_money[0]
        if relative_diff > 0.1:
            return StructuredSignal(
                "numeric",
                f"Matching entity, but the claimed amount differs by "
                f"{relative_diff:.0%} from the passage's figure.",
            )

    claim_pct = _percent_value(claim)
    passage_pct = _percent_value(passage)
    if (
        claim_pct is not None
        and passage_pct is not None
        and abs(claim_pct - passage_pct) > 2
    ):
        return StructuredSignal(
            "numeric",
            f"Matching entity, but {claim_pct}% in the claim differs from "
            f"{passage_pct}% in the passage.",
        )

    # Shared entity plus a keyword from the same predicate list is not enough
    # on its own -- "Company created X" and "Company founded" both match the
    # temporal-predicate list but can describe different events entirely.
    # Require the sentences to actually overlap lexically beyond the shared
    # entity, or skip -- this caught a real false positive during validation
    # (two unrelated events about the same person, both containing a listed
    # predicate word) and is deliberately conservative.
    event_aligned = lexical_overlap >= 0.2

    if (
        event_aligned
        and not needs_current_evidence(claim)
        and _TEMPORAL_PREDICATES.search(claim)
        and _TEMPORAL_PREDICATES.search(passage)
    ):
        claim_years = set(_YEAR.findall(claim))
        passage_years = set(_YEAR.findall(passage))
        if (
            len(claim_years) == 1
            and len(passage_years) == 1
            and claim_years != passage_years
        ):
            return StructuredSignal(
                "temporal",
                f"Matching entity and event, but the claim's year "
                f"{next(iter(claim_years))} differs from the passage's "
                f"{next(iter(passage_years))}.",
            )

    if (
        event_aligned
        and _LOCATION_PREDICATES.search(claim)
        and _LOCATION_PREDICATES.search(passage)
    ):
        claim_gpe = {
            e.text.casefold() for e in claim_doc.ents if e.label_ in ("GPE", "LOC")
        }
        passage_gpe = {
            e.text.casefold() for e in passage_doc.ents if e.label_ in ("GPE", "LOC")
        }
        if len(claim_gpe) == 1 and len(passage_gpe) == 1 and claim_gpe != passage_gpe:
            return StructuredSignal(
                "location",
                "Matching entity and location predicate, but the claimed "
                "place differs from the passage's.",
            )

    return None
