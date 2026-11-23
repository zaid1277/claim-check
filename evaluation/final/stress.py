"""Measure development source-independence limits and mined hard neutrals."""

import json
from pathlib import Path

from app.core.settings import Settings
from app.schemas.investigation import Evidence
from app.services.evidence_scoring import assess
from app.services.nli import LocalNLI
from app.services.pipeline import gate_stance

ROOT = Path(__file__).resolve().parent
settings = Settings(_env_file=None)
base = (
    "The observatory recorded a peak wind speed of 120 kilometres "
    "per hour during the overnight storm."
)
variants = [
    (
        "one-page-ten-chunks",
        [f"https://archive.org/a#{i}" for i in range(10)],
        [base + f" Instrument {i}." for i in range(10)],
        1,
    ),
    (
        "identical-mirrors",
        [f"https://mirror-{i}.org/a" for i in range(5)],
        [base] * 5,
        1,
    ),
    (
        "syndicated-with-introductions",
        [f"https://publisher-{i}.org/a" for i in range(5)],
        [f"Regional bulletin number {i}: " + base for i in range(5)],
        1,
    ),
    (
        "scraper-copy",
        ["https://origin.org/a", "https://scraper.net/a"],
        [base, base + " Click here for more."],
        1,
    ),
    (
        "translated-copy",
        ["https://original.org/a", "https://translated.fr/a"],
        [
            base,
            "L'observatoire a enregistré une vitesse maximale du vent de "
            "120 kilomètres par heure pendant la tempête nocturne.",
        ],
        1,
    ),
    (
        "primary-quoted-in-story",
        ["https://observatory.gov/a", "https://newspaper.com/a"],
        [
            base,
            "According to the observatory, winds reached 120 kilometres per hour "
            "overnight. The paper repeated the official measurement without "
            "taking its own observations.",
        ],
        1,
    ),
    (
        "different-independent-observations",
        ["https://instrument-a.org/a", "https://instrument-b.org/a"],
        [
            base,
            "An independent calibrated anemometer measured the maximum "
            "overnight storm wind at 120 km/h.",
        ],
        2,
    ),
]
outputs = []
for name, urls, passages, expected in variants:
    evidence = [
        Evidence(
            url=url,
            title="Controlled source provenance probe",
            domain=url.split("/")[2],
            passage=passage,
            similarity=1,
            stance="support",
            stance_confidence=0.99,
            source_weight=0.9,
            evidence_score=0,
        )
        for url, passage in zip(urls, passages, strict=True)
    ]
    result = assess(
        "The peak wind speed was 120 kilometres per hour.", evidence, settings
    )
    actual = sum(e.counted for e in result.evidence)
    outputs.append(
        dict(
            name=name,
            expected_origins=expected,
            counted_origins=actual,
            correct=actual == expected,
            result=result.model_dump(),
        )
    )
nli = LocalNLI(settings.nli_model, settings.min_nli_confidence)
neutrals = []
for row in json.loads((ROOT / "data/hard-neutrals.json").read_text()):
    raw, confidence = nli.classify(row["claim"], row["passage"])
    stance, reason = gate_stance(
        row["claim"], row["passage"], raw, confidence, None, settings
    )
    neutrals.append(
        dict(row, raw=raw, confidence=confidence, predicted=stance, reason=reason)
    )
(ROOT / "results/development-stress.json").write_text(
    json.dumps(dict(independence=outputs, hard_neutrals=neutrals), indent=2) + "\n"
)
print("Independence:", sum(r["correct"] for r in outputs), "/", len(outputs))
print(
    "Mined neutral retained:",
    sum(r["predicted"] == "neutral" for r in neutrals),
    "/",
    len(neutrals),
)
