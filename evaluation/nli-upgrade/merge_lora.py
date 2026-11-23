"""Merge a trained LoRA adapter into the base model and save a standalone
checkpoint, so it can be loaded through the exact same
`AutoModelForSequenceClassification.from_pretrained(path)` call the
production `LocalNLI` class already uses -- no production code changes
needed to test it (evaluation/nli-upgrade/pipeline_integration.py)."""

import argparse
import json
from pathlib import Path

from peft import PeftModel
from transformers import AutoModelForSequenceClassification, AutoTokenizer

BASE_MODEL = "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--adapter", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    adapter_dir = Path(args.adapter)
    label2id = json.loads((adapter_dir / "label2id.json").read_text())

    tokenizer = AutoTokenizer.from_pretrained(str(adapter_dir))
    base = AutoModelForSequenceClassification.from_pretrained(BASE_MODEL)
    model = PeftModel.from_pretrained(base, str(adapter_dir))
    merged = model.merge_and_unload()

    # Preserve the checkpoint's own id2label ordering (verified during
    # training, phase 11 discipline) rather than assuming.
    id2label = {v: k for k, v in label2id.items()}
    mapped_back = {
        "support": "entailment",
        "neutral": "neutral",
        "contradict": "contradiction",
    }
    merged.config.id2label = {i: mapped_back[id2label[i]] for i in range(3)}
    merged.config.label2id = {v: k for k, v in merged.config.id2label.items()}

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    merged.save_pretrained(str(out_dir))
    tokenizer.save_pretrained(str(out_dir))
    print(f"Saved merged standalone model to {out_dir}")
    print(f"id2label: {merged.config.id2label}")


if __name__ == "__main__":
    main()
