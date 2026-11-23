"""Small, conservative grammar checks; never supply facts absent from the input."""

import re
from functools import lru_cache

from app.core.errors import ProviderError


@lru_cache(maxsize=1)
def parser():
    import spacy

    try:
        return spacy.load("en_core_web_sm")
    except OSError as exc:
        raise ProviderError(
            "Install the English parser before live investigations."
        ) from exc


def sentence_texts(text: str) -> list[str]:
    # Keep decimal values intact; preserve adjacent sentences for coreference in chunks.
    return [
        s.strip()
        for s in re.split(r'(?<=[.!?])\s+(?=[A-Z\d"“])|\n+', text)
        if s.strip()
    ]


def decompose_claim(claim: str, limit: int = 4) -> list[str]:
    """Split explicit coordinated finite predicates; leave ambiguous scope intact."""
    if " and " not in claim.lower():
        return [claim]
    doc = parser()(claim)
    if any(
        t.tag_ == "MD"
        or t.dep_ in {"neg", "ccomp", "xcomp"}
        or t.lower_ in {"if", "unless", "or", "because", "before", "after"}
        for t in doc
    ):
        return [claim]
    boundaries = [
        t
        for t in doc
        if t.lower_ == "and"
        # A conjunction inside reported speech belongs to its embedded subject.
        and t.dep_ == "cc"
        and t.head.dep_ in {"ROOT", "conj"}
        and all(parent.dep_ in {"ROOT", "conj"} for parent in t.head.ancestors)
        and t.i + 1 < len(doc)
        and doc[t.i + 1].pos_ in {"VERB", "AUX", "PRON"}
    ]
    if not boundaries or len(boundaries) >= limit:
        return [claim]
    first = claim[: boundaries[0].idx].strip().rstrip(",")
    left = parser()(first)
    subject = next(
        (t for t in left if t.dep_ in {"nsubj", "nsubjpass"} and t.head.dep_ == "ROOT"),
        None,
    )
    if subject is None or subject.pos_ == "PRON":
        return [claim]
    subject_text = left[subject.left_edge.i : subject.right_edge.i + 1].text
    atoms = [first.rstrip(". ") + "."]
    for i, boundary in enumerate(boundaries):
        end = boundaries[i + 1].idx if i + 1 < len(boundaries) else len(claim)
        part = claim[boundary.idx + len(boundary.text) : end].strip().rstrip("., ")
        right = parser()(part)
        if not right or right[0].pos_ not in {"VERB", "AUX", "PRON"}:
            return [claim]
        if right[0].lower_ in {"it", "they"}:
            part = subject_text + part[len(right[0].text) :]
        elif right[0].pos_ == "PRON":
            return [claim]
        else:
            auxiliary = ""
            if right[0].tag_ == "VBN":
                auxiliary = " ".join(
                    t.text for t in left if t.dep_ in {"aux", "auxpass"}
                )
                if not auxiliary:
                    return [claim]
            part = " ".join(p for p in (subject_text, auxiliary, part) if p)
        atoms.append(part + ".")
    return atoms
