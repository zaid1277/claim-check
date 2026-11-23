# Pass 2 held-out tables

All comparisons below use the same new test split.

| Metric | Pass 1 | Pass 2 |
|---|---:|---:|
| Raw NLI macro F1 | 0.4070 | 0.6672 |
| Effective NLI macro F1 | 0.4077 | 0.6788 |
| False contradiction rate | 0.0811 | 0.0405 |
| Verdict accuracy | 0.6452 | 0.8710 |
| Decision coverage | 0.7419 | 0.7742 |
| Abstention rate | 0.2581 | 0.2258 |
| Selective accuracy | 0.6957 | 0.9167 |
| Incorrect confident verdict rate | 0.2258 | 0.0645 |
| Definitive coverage | 0.7097 | 0.6129 |
| Definitive selective accuracy | 0.6818 | 0.8947 |

## Pass 1 effective NLI

| Label | Precision | Recall | F1 | Count |
|---|---:|---:|---:|---:|
| support | 0.4643 | 0.3514 | 0.4000 | 37 |
| contradict | 0.5714 | 0.2162 | 0.3137 | 37 |
| neutral | 0.3913 | 0.7297 | 0.5094 | 37 |

Confusion matrix: rows expected; columns predicted; order support, contradict, neutral.
```json
[[13, 3, 21], [8, 8, 21], [7, 3, 27]]
```

## Pass 2 raw NLI

| Label | Precision | Recall | F1 | Count |
|---|---:|---:|---:|---:|
| support | 0.7297 | 0.7297 | 0.7297 | 37 |
| contradict | 0.6857 | 0.6486 | 0.6667 | 37 |
| neutral | 0.5897 | 0.6216 | 0.6053 | 37 |

Confusion matrix: rows expected; columns predicted; order support, contradict, neutral.
```json
[[27, 2, 8], [5, 24, 8], [5, 9, 23]]
```

## Pass 2 effective NLI

| Label | Precision | Recall | F1 | Count |
|---|---:|---:|---:|---:|
| support | 0.7500 | 0.6486 | 0.6957 | 37 |
| contradict | 0.8750 | 0.5676 | 0.6885 | 37 |
| neutral | 0.5455 | 0.8108 | 0.6522 | 37 |

Confusion matrix: rows expected; columns predicted; order support, contradict, neutral.
```json
[[24, 0, 13], [4, 21, 12], [4, 3, 30]]
```

## Pass 1 verdict

| Label | Precision | Recall | F1 | Count |
|---|---:|---:|---:|---:|
| SUPPORTED | 0.6429 | 0.9000 | 0.7500 | 10 |
| UNSUPPORTED | 0.7500 | 0.6667 | 0.7059 | 9 |
| MIXED_EVIDENCE | 1.0000 | 0.2000 | 0.3333 | 5 |
| INSUFFICIENT_EVIDENCE | 0.5000 | 0.5714 | 0.5333 | 7 |

Confusion matrix: rows expected; columns predicted; order SUPPORTED, UNSUPPORTED, MIXED_EVIDENCE, INSUFFICIENT_EVIDENCE.
```json
[[9, 0, 0, 1], [0, 6, 0, 3], [4, 0, 1, 0], [1, 2, 0, 4]]
```

## Pass 2 verdict

| Label | Precision | Recall | F1 | Count |
|---|---:|---:|---:|---:|
| SUPPORTED | 1.0000 | 0.9000 | 0.9474 | 10 |
| UNSUPPORTED | 0.8000 | 0.8889 | 0.8421 | 9 |
| MIXED_EVIDENCE | 1.0000 | 1.0000 | 1.0000 | 5 |
| INSUFFICIENT_EVIDENCE | 0.7143 | 0.7143 | 0.7143 | 7 |

Confusion matrix: rows expected; columns predicted; order SUPPORTED, UNSUPPORTED, MIXED_EVIDENCE, INSUFFICIENT_EVIDENCE.
```json
[[9, 0, 0, 1], [0, 8, 0, 1], [0, 0, 5, 0], [0, 2, 0, 5]]
```

## Candidate comparison (validation only)

| Model | Raw macro F1 | Support F1 | Contradiction F1 | Neutral F1 | Contradiction precision | Contradiction recall | Raw false contradiction rate |
|---|---:|---:|---:|---:|---:|---:|---:|
| cross-encoder/nli-deberta-v3-small | 0.5271 | 0.5373 | 0.5915 | 0.4524 | 0.6176 | 0.5676 | 0.1757 |
| MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli | 0.7057 | 0.7353 | 0.7397 | 0.6420 | 0.7500 | 0.7297 | 0.1216 |
| typeform/distilbert-base-uncased-mnli | 0.4668 | 0.4533 | 0.5526 | 0.3944 | 0.5385 | 0.5676 | 0.2432 |
