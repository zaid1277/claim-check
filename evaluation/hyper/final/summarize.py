"""Summarize locked Hyper-holdout observations without changing labels,
predictions or code. Adapted from evaluation/final/summarize.py for the
single-variant Group 4 harness."""

import csv
import json
import statistics
from collections import Counter
from pathlib import Path

import numpy as np
from sklearn.metrics import confusion_matrix, precision_recall_fscore_support

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"


def read(name):
    path = RESULTS / name
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def distribution(seconds):
    return dict(
        n=len(seconds),
        median=statistics.median(seconds) if seconds else None,
        p95=float(np.percentile(seconds, 95)) if seconds else None,
    )


def pair_metrics(rows, field):
    labels = ["support", "contradict", "neutral"]
    truth = [r["expected"] for r in rows]
    predictions = [r[field] for r in rows]
    p, r, f, n = precision_recall_fscore_support(
        truth, predictions, labels=labels, zero_division=0
    )
    return dict(
        count=len(rows),
        macro_f1=float(f.mean()),
        accuracy=sum(a == b for a, b in zip(truth, predictions, strict=True))
        / len(rows),
        confusion_matrix=confusion_matrix(truth, predictions, labels=labels).tolist(),
        labels=labels,
        per_label={
            label: dict(
                precision=float(p[i]), recall=float(r[i]), f1=float(f[i]), n=int(n[i])
            )
            for i, label in enumerate(labels)
        },
        false_contradiction_rate=sum(
            a != "contradict" and b == "contradict"
            for a, b in zip(truth, predictions, strict=True)
        )
        / sum(a != "contradict" for a in truth),
    )


def verdict_metrics(rows):
    decided = [
        r
        for r in rows
        if r["predicted"] in {"SUPPORTED", "UNSUPPORTED", "MIXED_EVIDENCE"}
    ]
    total = len(rows)
    return dict(
        count=total,
        correct=sum(r["predicted"] == r["expected"] for r in rows),
        accuracy=sum(r["predicted"] == r["expected"] for r in rows) / total
        if total
        else None,
        coverage=len(decided) / total if total else None,
        selective_accuracy=sum(r["predicted"] == r["expected"] for r in decided)
        / len(decided)
        if decided
        else None,
        abstention_rate=sum(r["predicted"] == "INSUFFICIENT_EVIDENCE" for r in rows)
        / total
        if total
        else None,
        failures=sum(r["predicted"] == "ERROR" for r in rows),
        correct_abstentions=sum(
            r["predicted"] == r["expected"] == "INSUFFICIENT_EVIDENCE" for r in rows
        ),
        false_abstentions=sum(
            r["predicted"] == "INSUFFICIENT_EVIDENCE"
            and r["expected"] != "INSUFFICIENT_EVIDENCE"
            for r in rows
        ),
        confident_errors=sum(r["predicted"] != r["expected"] for r in decided),
    )


def edit_distance(left, right):
    previous = list(range(len(right) + 1))
    for i, a in enumerate(left, 1):
        current = [i]
        for j, b in enumerate(right, 1):
            current.append(
                min(current[-1] + 1, previous[j] + 1, previous[j - 1] + (a != b))
            )
        previous = current
    return previous[-1]


def main():
    pairs = json.loads((RESULTS / "final-pairs.json").read_text())["predictions"]["nli"]
    labels = {
        "entailment": "support",
        "contradiction": "contradict",
        "neutral": "neutral",
    }
    for row in pairs:
        row["winning"] = labels[max(row["probabilities"], key=row["probabilities"].get)]
    report = {
        "nli": {
            field: pair_metrics(pairs, field)
            for field in ["winning", "raw", "predicted"]
        }
    }
    cases = {
        r["id"]: r for r in json.loads((ROOT / "data/investigations.json").read_text())
    }
    attempts = read("product-controlled.jsonl")
    by_id = {r["case_id"]: r for r in attempts}
    outputs = []
    for identifier, case in cases.items():
        attempt = by_id.get(identifier, {})
        result = attempt.get("result", {}).get("assessments", [])
        outputs.append(
            dict(
                id=identifier,
                expected=case["expected"],
                predicted=result[0]["verdict"] if result else "ERROR",
                domain=case["domain"],
                difficulty=case["difficulty"],
                origin=case["origin"],
                tag=case["tag"],
            )
        )
    report["controlled"] = dict(
        overall=verdict_metrics(outputs),
        by_difficulty={
            d: verdict_metrics([r for r in outputs if r["difficulty"] == d])
            for d in ["easy", "medium", "hard"]
        },
        by_origin={
            o: verdict_metrics([r for r in outputs if r["origin"] == o])
            for o in sorted({r["origin"] for r in outputs})
        },
        rows=outputs,
    )
    modal = read("product-modal.jsonl")
    typed = by_id
    report["workflow"] = {}
    for route in ["text", "image", "url"]:
        rows = [r for r in modal if r["route"] == route]
        report["workflow"][route] = dict(
            attempted=len(rows),
            completed=sum(r["success"] for r in rows),
            latency=distribution([r["seconds"] for r in rows if r["success"]]),
        )
    images = json.loads((ROOT / "data/images.json").read_text())
    cross_modal_ids = [img["id"] for img in images[:20]]
    cross = []
    for identifier in cross_modal_ids:
        rows = [typed.get(identifier, {})] + [
            r for r in modal if r["case_id"] == identifier
        ]
        signatures = [
            [
                (a["claim"], a["verdict"])
                for a in r.get("result", {}).get("assessments", [])
            ]
            for r in rows
        ]
        complete = len(rows) == 4 and all(r.get("success") for r in rows)
        cross.append(
            dict(
                id=identifier,
                complete=complete,
                consistent=complete and all(s == signatures[0] for s in signatures),
                signatures=signatures,
            )
        )
    report["cross_modal"] = dict(
        count=len(cross), consistent=sum(r["consistent"] for r in cross), rows=cross
    )
    ocr = []
    for row in read("ocr-observations.jsonl"):
        transcript = " ".join(row.get("transcript", "").split())
        actual = " ".join(row.get("ocr", {}).get("text", "").split())
        ocr.append(
            dict(
                id=row["case_id"],
                success=row["status"] == 200,
                cer=edit_distance(transcript, actual) / max(1, len(transcript)),
                wer=edit_distance(transcript.split(), actual.split())
                / max(1, len(transcript.split())),
                recognized=actual,
                transcript=transcript,
            )
        )
    report["ocr"] = ocr
    urls = read("product-urls.jsonl")
    live = read("product-live.jsonl")
    report["public_urls"] = dict(
        attempted=len(urls),
        completed=sum(r["success"] for r in urls),
        latency=distribution([r["seconds"] for r in urls if r["success"]]),
        five_claim_latency=distribution(
            [
                r["seconds"]
                for r in urls
                if r["success"] and r.get("selected_count") == 5
            ]
        ),
    )
    report["live_observations"] = dict(
        attempted=len(live),
        completed=sum(r["success"] for r in live),
        by_difficulty=dict(Counter(r["difficulty"] for r in live)),
        verdicts=dict(
            Counter(
                a["verdict"]
                for r in live
                for a in r.get("result", {}).get("assessments", [])
            )
        ),
        latency=distribution([r["seconds"] for r in live if r["success"]]),
    )
    report["typed_latency"] = distribution(
        [
            r["seconds"]
            for r in typed.values()
            if r["success"] and r["route"] == "typed-browser"
        ]
    )
    misses = []
    for row in pairs:
        if row["expected"] != "contradict" or row["predicted"] == "contradict":
            continue
        reason = row.get("reason") or ""
        category = (
            "NLI prediction"
            if row["winning"] != "contradict"
            else "NLI confidence"
            if row["raw"] != "contradict" or "confidence" in reason.lower()
            else "relevance filter"
            if "relevance" in reason.lower()
            else "temporal/context filter"
        )
        misses.append(
            dict(
                id=row["id"],
                claim=row["claim"],
                winning=row["winning"],
                raw=row["raw"],
                retained=row["predicted"],
                confidence=row["confidence"],
                category=category,
                reason=reason,
            )
        )
    with (RESULTS / "missed-contradictions.csv").open("w") as stream:
        writer = csv.DictWriter(
            stream, fieldnames=list(misses[0]) if misses else ["id"]
        )
        writer.writeheader()
        writer.writerows(misses)
    report["missed_contradiction_categories"] = dict(
        Counter(r["category"] for r in misses)
    )

    investigation_errors = []
    for row in report["controlled"]["rows"]:
        if row["predicted"] == row["expected"]:
            continue
        attempt = typed.get(row["id"], {})
        assessments = attempt.get("result", {}).get("assessments", [])
        evidence = assessments[0]["evidence"] if assessments else []
        category = (
            "workflow/provider failure"
            if not assessments
            else "retrieval/ranking produced no retained evidence"
            if not evidence
            else "eligibility filters"
            if all(e["stance"] == "neutral" for e in evidence)
            and any(e.get("exclusion_reason") for e in evidence)
            else "NLI prediction or confidence"
            if all(e["stance"] == "neutral" for e in evidence)
            else "aggregation/source weight/atomic coverage"
            if row["predicted"] == "INSUFFICIENT_EVIDENCE"
            else "retained evidence relation or source conflict"
        )
        investigation_errors.append(dict(row, category=category, evidence=evidence))
    (RESULTS / "investigation-errors.json").write_text(
        json.dumps(investigation_errors, indent=2) + "\n"
    )

    nli = report["nli"]["predicted"]
    verdict = report["controlled"]["overall"]
    report["targets"] = {
        "nli_macro_f1": nli["macro_f1"] >= 0.88,
        "contradiction_precision": nli["per_label"]["contradict"]["precision"] >= 0.88,
        "contradiction_recall": nli["per_label"]["contradict"]["recall"] >= 0.65,
        "false_contradiction_rate": nli["false_contradiction_rate"] <= 0.04,
        "overall_accuracy": (verdict["accuracy"] or 0) >= 0.80,
        "coverage": (verdict["coverage"] or 0) >= 0.70,
        "selective_accuracy": (verdict["selective_accuracy"] or 0) >= 0.92,
        "cross_modal": (
            report["cross_modal"]["consistent"] / report["cross_modal"]["count"]
            if report["cross_modal"]["count"]
            else 0
        )
        >= 0.90,
        "public_url_completion": report["public_urls"]["completed"] / 30 >= 0.85,
        "pasted_completion": report["workflow"]["text"]["completed"] / 30 >= 0.95,
        "ocr_completion": report["workflow"]["image"]["completed"] / 30 >= 0.90,
    }
    for difficulty, target in [("easy", 0.95), ("medium", 0.90), ("hard", 0.60)]:
        measured = report["controlled"]["by_difficulty"][difficulty]["accuracy"]
        report["targets"][difficulty + "_accuracy"] = (measured or 0) >= target
    report["decision"] = (
        "TARGETS MET; REVIEW REQUIRED"
        if all(report["targets"].values())
        else "NOT READY"
    )
    (RESULTS / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
    print("Wrote", RESULTS / "summary.json")
    print("Decision:", report["decision"])
    print("Targets:", report["targets"])


if __name__ == "__main__":
    main()
