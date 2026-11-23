import pytest

from app.services.nli import interpret_label, normalize_hypothesis


@pytest.mark.parametrize(
    "claim,expected",
    [
        ("A dog is running", "A dog is running."),
        ("  A dog is running.  ", "A dog is running."),
        ("The door is closed!", "The door is closed!"),
        ("Is the door closed?", "Is the door closed?"),
        ('The sign says "Closed."', 'The sign says "Closed."'),
        ("The text continues…", "The text continues…"),
        ("", ""),
    ],
)
def test_hypothesis_sentence_punctuation(claim, expected):
    assert normalize_hypothesis(claim) == expected
    assert normalize_hypothesis(expected) == expected


def test_confidence_threshold_and_label_mapping():
    assert interpret_label("entailment", 0.64, 0.65) == ("neutral", 0.64)
    assert interpret_label("entailment", 0.65, 0.65) == ("support", 0.65)
    assert interpret_label("contradiction", 0.9, 0.65) == ("contradict", 0.9)
    with pytest.raises(ValueError):
        interpret_label("LABEL_0", 0.9, 0.65)


@pytest.mark.parametrize(
    "claim,passage,label,expected",
    [
        ("A dog is running.", "A dog is running in the park.", "ENTAILMENT", "support"),
        ("A dog is running", "A dog is running in the park.", "ENTAILMENT", "support"),
        ("The door is open.", "The door is closed.", "CONTRADICTION", "contradict"),
        ("The door is open.", "A bird is singing.", "NEUTRAL", "neutral"),
        (
            "The Eiffel Tower is in Paris.",
            (
                "The Eiffel Tower is a wrought-iron lattice tower "
                "on the Champ de Mars in Paris, France."
            ),
            "ENTAILMENT",
            "support",
        ),
    ],
)
def test_local_nli_preserves_premise_order_and_model_labels(
    monkeypatch, claim, passage, label, expected
):
    import sys
    from contextlib import nullcontext
    from types import SimpleNamespace

    from app.services.nli import LocalNLI

    class Probabilities(list):
        def argmax(self):
            return max(range(len(self)), key=self.__getitem__)

    def tokenize(premise, hypothesis, **kwargs):
        assert premise == passage
        assert hypothesis == normalize_hypothesis(claim)
        assert kwargs["truncation"] == "only_first"
        return {}

    class Model:
        # Put the winner at a non-default index to catch hard-coded label orders.
        config = SimpleNamespace(id2label={0: "NEUTRAL", 1: label, 2: "OTHER"})

        def __call__(self, **kwargs):
            return SimpleNamespace(
                logits=[
                    SimpleNamespace(
                        softmax=lambda dim: Probabilities([0.01, 0.98, 0.01])
                    )
                ]
            )

    monkeypatch.setitem(
        sys.modules, "torch", SimpleNamespace(inference_mode=nullcontext)
    )
    monkeypatch.setattr("app.services.nli.load_nli", lambda name: (tokenize, Model()))
    assert LocalNLI("test-model", 0.65).classify(claim, passage) == (expected, 0.98)
