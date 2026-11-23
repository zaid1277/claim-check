"""Opt-in regression against actual configured weights; no provider calls."""

import os

import pytest

from app.core.settings import get_settings
from app.services.nli import LocalNLI


@pytest.mark.skipif(
    os.getenv("RUN_LOCAL_NLI_TESTS") != "1",
    reason="Set RUN_LOCAL_NLI_TESTS=1 with local model dependencies/cache",
)
@pytest.mark.parametrize("terminal_period", [True, False])
@pytest.mark.parametrize(
    "claim,passage,expected",
    [
        (
            "The Eiffel Tower is in Paris.",
            (
                "The Eiffel Tower is a wrought-iron lattice tower "
                "on the Champ de Mars in Paris, France."
            ),
            "support",
        ),
        (
            "The Eiffel Tower is in Rome.",
            (
                "The Eiffel Tower is a wrought-iron lattice tower "
                "on the Champ de Mars in Paris, France."
            ),
            "contradict",
        ),
        (
            "The Eiffel Tower is made of iron.",
            "Paris is the capital and largest city of France.",
            "neutral",
        ),
    ],
)
def test_configured_nli_model(claim, passage, expected, terminal_period):
    settings = get_settings()
    if not terminal_period:
        claim = claim.removesuffix(".")
    stance, _ = LocalNLI(settings.nli_model, settings.min_nli_confidence).classify(
        claim, passage
    )
    assert stance == expected
