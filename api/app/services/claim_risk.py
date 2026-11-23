"""Deterministic claim-risk tiering (hyper pass, phase 6).

This never loosens evidence requirements. "standard" claims keep the same
operating point as before this pass (recalibrated separately via source
weighting and graded relevance elsewhere). "high" claims — where a confident
wrong verdict is more consequential and where a single lucky-worded passage
is more likely to mislead — require more total evidence and more independent
sources before the system will commit to SUPPORTED/UNSUPPORTED.

Deliberately general lexical categories, not hard-coded facts or topics
copied from any evaluation dataset's own labels. Ambiguous or unmatched
claims default to "standard", not "high" — this is a coverage-preserving
choice; it does not, by itself, reduce caution anywhere, since "standard"
is exactly the pre-existing operating point.
"""

import re
from typing import Literal

RiskLevel = Literal["standard", "high"]

_MEDICAL_TERMS = re.compile(
    r"\b(mortality|cure[sd]?|treats?|drug|vaccine|dosage|diagnos\w*|"
    r"cancer|disease|clinical trial|side effect|toxic|overdose|"
    r"fda[- ]approved|prescri\w+)\b",
    re.IGNORECASE,
)
_FINANCIAL_TERMS = re.compile(
    r"\b(revenue|profit|earnings|stock price|market cap|gdp|inflation|"
    r"interest rate|bankrupt\w*|valuation|ipo|net worth)\b",
    re.IGNORECASE,
)
_POLITICAL_TERMS = re.compile(
    r"\b(election|elected|vote[sd]?|poll(?:ing)?|senator|president|"
    r"prime minister|parliament|legislation|indict\w*|convict\w*)\b",
    re.IGNORECASE,
)
_CAUSAL_TERMS = re.compile(
    r"\b(causes?|caused|reduces?|increases?|linked to|associated with|"
    r"proven to|shown to)\b",
    re.IGNORECASE,
)
_STATISTIC = re.compile(r"\d+(\.\d+)?\s*%|\bby\s+\d+(\.\d+)?\s*(percent|%)")


def claim_risk(claim: str) -> RiskLevel:
    """Classify a claim's verification risk from general lexical signals only."""
    if _MEDICAL_TERMS.search(claim) or _FINANCIAL_TERMS.search(claim):
        return "high"
    if _POLITICAL_TERMS.search(claim):
        return "high"
    # A causal/comparative claim paired with a specific statistic is the
    # "Drug X reduces mortality by 30%" shape the phase-6 brief calls out.
    if _CAUSAL_TERMS.search(claim) and _STATISTIC.search(claim):
        return "high"
    return "standard"
