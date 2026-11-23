"""Distinguish a measurement's context from the value being tested."""

import re

VERSION = re.compile(
    r"\b(?:version|release|edition|revision)\s+(\d+(?:\.\d+)*)\b", re.I
)
YEAR = re.compile(r"\b(?:19|20)\d{2}\b")
QUANTITY = re.compile(r"\b\d+(?:[.,]\d+)*\b")
CURRENT_ROLE = re.compile(
    r"\bis\s+(?:(?:currently|now)\s+)?(?:the\s+)?"
    r"(?:chief executive officer|chief financial officer|CEO|CFO|president|"
    r"chair|chairperson|director|mayor|governor|head coach)\b",
    re.I,
)


def context_exclusion(claim: str, passage: str) -> str | None:
    claim_versions = set(VERSION.findall(claim))
    evidence_versions = set(VERSION.findall(passage))
    if (
        claim_versions
        and evidence_versions
        and claim_versions.isdisjoint(evidence_versions)
    ):
        return "The evidence concerns a different product version."
    claim_years = set(YEAR.findall(claim))
    evidence_years = set(YEAR.findall(passage))
    # An event date can be contradicted; a value for another reporting year cannot.
    other_numbers = QUANTITY.findall(YEAR.sub("", claim))
    if (
        claim_years
        and evidence_years
        and other_numbers
        and claim_years.isdisjoint(evidence_years)
    ):
        return "The measurement concerns a different reporting period."
    return None


def needs_current_evidence(claim: str) -> bool:
    explicit = re.search(r"\b(currently|current|today|now|latest)\b", claim, re.I)
    return bool(explicit or (CURRENT_ROLE.search(claim) and not YEAR.search(claim)))
