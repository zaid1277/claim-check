"""NLI upgrade pass, Phases 5-9, 11: LoRA fine-tune of the base NLI model
on the new train split, with proper train/validation separation, fixed
seeds, checkpointing, and early stopping.

Base model chosen (Phase 5): DeBERTa-v3-base-mnli-fever-anli, continued
via LoRA rather than full fine-tuning -- Phase 6's hardware feasibility
assessment (Apple M1, 8GB total RAM, ~180MB free at assessment time, no
CUDA) ruled out full fine-tuning of the 435M-parameter large model
entirely, and even base-model full fine-tuning carries real OOM risk.
LoRA keeps the optimizer-state memory small (only the adapter matrices
have gradients/Adam state); the base forward/backward activation cost is
unavoidable regardless of PEFT, which is why batch size stays tiny with
gradient accumulation.
"""

import argparse
import json
import random
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "api"))
ROOT = Path(__file__).resolve().parent

import numpy as np  # noqa: E402
import torch  # noqa: E402
from peft import LoraConfig, get_peft_model  # noqa: E402
from sklearn.metrics import f1_score  # noqa: E402
from transformers import AutoModelForSequenceClassification, AutoTokenizer  # noqa: E402

from app.services.nli import normalize_hypothesis  # noqa: E402

BASE_MODEL = "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli"
LABEL2ID = {
    "support": 0,
    "neutral": 1,
    "contradict": 2,
}  # this checkpoint's own id2label order


def set_seed(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def load_split(name):
    rows = json.loads((ROOT / f"data/{name}.json").read_text())
    return rows


def resolve_label_ids(model):
    """Confirm this checkpoint's id2label order before training -- do not
    assume the conventional 0/1/2 = entailment/neutral/contradiction
    ordering without checking (phase 11 discipline applied to the base
    model itself, not just the training datasets)."""
    id2label = {int(k): v.lower() for k, v in model.config.id2label.items()}
    mapped = {
        "entailment": "support",
        "neutral": "neutral",
        "contradiction": "contradict",
    }
    label2id = {}
    for idx, raw in id2label.items():
        label2id[mapped[raw]] = idx
    return label2id


def encode(tokenizer, rows, max_length):
    texts_a = [r["passage"] for r in rows]
    texts_b = [normalize_hypothesis(r["claim"]) for r in rows]
    return tokenizer(
        texts_a,
        texts_b,
        truncation="only_first",
        max_length=max_length,
        padding=True,
        return_tensors="pt",
    )


def batches(rows, batch_size, shuffle, seed):
    indices = list(range(len(rows)))
    if shuffle:
        random.Random(seed).shuffle(indices)
    for i in range(0, len(indices), batch_size):
        yield [rows[j] for j in indices[i : i + batch_size]]


def evaluate(model, tokenizer, rows, label2id, max_length, device):
    model.eval()
    all_preds, all_labels = [], []
    with torch.inference_mode():
        for batch in batches(rows, 8, shuffle=False, seed=0):
            inputs = encode(tokenizer, batch, max_length).to(device)
            logits = model(**inputs).logits
            preds = logits.argmax(dim=-1).tolist()
            all_preds += preds
            all_labels += [label2id[r["label"]] for r in batch]
    macro_f1 = f1_score(all_labels, all_preds, average="macro")
    per_label_f1 = f1_score(all_labels, all_preds, average=None, labels=[0, 1, 2])
    accuracy = sum(
        p == label for p, label in zip(all_preds, all_labels, strict=True)
    ) / len(all_labels)
    return {
        "accuracy": accuracy,
        "macro_f1": macro_f1,
        "per_label_f1": {
            "support": per_label_f1[0],
            "neutral": per_label_f1[1],
            "contradict": per_label_f1[2],
        },
        "n": len(all_labels),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-length", type=int, default=384)
    parser.add_argument("--epochs", type=int, default=4)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--grad-accum", type=int, default=8)
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--seed", type=int, default=20260916)
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="tiny run to verify the pipeline works",
    )
    parser.add_argument("--out", default="results/lora-base")
    args = parser.parse_args()

    set_seed(args.seed)
    device = "cpu"  # MPS shares the same 8GB unified memory as everything
    # else on this box; CPU keeps memory behavior predictable and matches
    # how the production NLI model already runs (see api/app/services/nli.py).

    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
    model = AutoModelForSequenceClassification.from_pretrained(BASE_MODEL)
    label2id = resolve_label_ids(model)
    print("Resolved label2id from checkpoint:", label2id)

    lora_config = LoraConfig(
        task_type="SEQ_CLS",
        r=8,
        lora_alpha=16,
        lora_dropout=0.1,
        target_modules=["query_proj", "key_proj", "value_proj"],
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()
    model.to(device)

    train_rows = load_split("train")
    val_rows = load_split("validation")
    if args.smoke_test:
        train_rows = train_rows[:12]
        val_rows = val_rows[:12]
        args.epochs = 1

    print(f"Train: {len(train_rows)}  Validation: {len(val_rows)}")

    optimizer = torch.optim.AdamW(
        [p for p in model.parameters() if p.requires_grad], lr=args.lr
    )

    history = []
    best_macro_f1 = -1
    best_state = None
    patience, bad_epochs = 2, 0

    for epoch in range(1, args.epochs + 1):
        model.train()
        epoch_start = time.perf_counter()
        running_loss, step_count = 0.0, 0
        optimizer.zero_grad()
        for step, batch in enumerate(
            batches(train_rows, args.batch_size, shuffle=True, seed=args.seed + epoch)
        ):
            inputs = encode(tokenizer, batch, args.max_length).to(device)
            labels = torch.tensor([label2id[r["label"]] for r in batch], device=device)
            outputs = model(**inputs, labels=labels)
            loss = outputs.loss / args.grad_accum
            loss.backward()
            running_loss += outputs.loss.item()
            step_count += 1
            if (step + 1) % args.grad_accum == 0:
                optimizer.step()
                optimizer.zero_grad()
        optimizer.step()
        optimizer.zero_grad()

        val_metrics = evaluate(
            model, tokenizer, val_rows, label2id, args.max_length, device
        )
        elapsed = time.perf_counter() - epoch_start
        record = {
            "epoch": epoch,
            "train_loss": running_loss / max(1, step_count),
            "val_accuracy": val_metrics["accuracy"],
            "val_macro_f1": val_metrics["macro_f1"],
            "val_per_label_f1": val_metrics["per_label_f1"],
            "elapsed_seconds": elapsed,
        }
        history.append(record)
        print(json.dumps(record, indent=2))

        if val_metrics["macro_f1"] > best_macro_f1:
            best_macro_f1 = val_metrics["macro_f1"]
            best_state = {
                k: v.clone() for k, v in model.state_dict().items() if "lora" in k
            }
            bad_epochs = 0
        else:
            bad_epochs += 1
            if bad_epochs >= patience:
                print(
                    f"Early stopping at epoch {epoch} (no improvement for {patience})"
                )
                break

    out_dir = ROOT / args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    if best_state is not None:
        model.load_state_dict(best_state, strict=False)
    model.save_pretrained(str(out_dir))
    tokenizer.save_pretrained(str(out_dir))
    (out_dir / "label2id.json").write_text(json.dumps(label2id, indent=2))
    (out_dir / "training-history.json").write_text(json.dumps(history, indent=2))
    (out_dir / "training-config.json").write_text(json.dumps(vars(args), indent=2))
    print(f"\nBest validation macro F1: {best_macro_f1:.4f}")
    print(f"Saved adapter + tokenizer + history to {out_dir}")


if __name__ == "__main__":
    main()
