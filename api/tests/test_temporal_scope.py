"""Versions and reporting periods identify context, unlike an event's date/value."""

import pytest

from app.services.temporal_scope import context_exclusion, needs_current_evidence


@pytest.mark.parametrize(
    "claim,passage",
    [
        ("Version 12 supports backups.", "Version 11 supports backups."),
        ("Release 2.01 reads images.", "Release 2.02 reads images."),
        ("Revenue was $3 million in 2023.", "Revenue was $3 million in 2022."),
        ("Rainfall was 42 mm in 2020.", "Rainfall was 48 mm in 2021."),
    ],
)
def test_different_context_cannot_disprove_current_proposition(claim, passage):
    assert context_exclusion(claim, passage) is not None


@pytest.mark.parametrize(
    "claim,passage",
    [
        ("The museum opened in 1850.", "The museum opened in 1860."),
        ("Revenue was $3 million in 2023.", "Revenue was $4 million in 2023."),
        ("Version 12 supports backups.", "Version 12 does not support backups."),
        ("The score was 25.", "The score was 26."),
    ],
)
def test_actual_values_remain_eligible_for_nli_contradiction(claim, passage):
    assert context_exclusion(claim, passage) is None


@pytest.mark.parametrize(
    "claim,current",
    [
        ("Amara is the CEO of Northwind.", True),
        ("Tariq is mayor of the city.", True),
        ("Amara was the CEO of Northwind in 2008.", False),
        ("Amara is the CEO of Northwind in 2008.", False),
        ("The sample is a mineral.", False),
        ("The population is currently two million.", True),
    ],
)
def test_explicit_and_role_implied_currentness(claim, current):
    assert needs_current_evidence(claim) is current


@pytest.mark.integration
def test_real_models_recover_contradiction_without_matching_verbs():
    import os

    if os.environ.get("RUN_LOCAL_NLI_TESTS") != "1":
        pytest.skip("Set RUN_LOCAL_NLI_TESTS=1 for cached model integration")
    from app.core.settings import Settings
    from app.services.nli import LocalNLI
    from app.services.pipeline import gate_stance

    settings = Settings(_env_file=None)
    claim = "The public pool is open on Saturdays."
    passage = "The public pool is closed every Saturday."
    raw, confidence = LocalNLI(
        settings.nli_model, settings.min_nli_confidence
    ).classify(claim, passage)
    assert raw == "contradict"
    assert (
        gate_stance(claim, passage, raw, confidence, None, settings)[0] == "contradict"
    )
