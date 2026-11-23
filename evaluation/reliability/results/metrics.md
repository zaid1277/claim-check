# Held-out measurements

| Metric | Baseline | Final |
|---|---:|---:|
| Raw NLI macro F1 | 0.6084 | 0.7886 |
| Raw support precision | 0.8793 | 0.9375 |
| Raw contradiction precision | 0.5758 | 0.7917 |
| Raw neutral precision | 0.3333 | 0.6111 |
| Raw false contradiction rate | 0.1628 | 0.0581 |
| Effective contradiction precision | 0.5758 | 0.9000 |
| Effective contradiction recall | 0.9500 | 0.4500 |
| Effective false contradiction rate | 0.1628 | 0.0116 |
| Recall@5 | 1.0000 | 1.0000 |
| Recall@10 | 1.0000 | 1.0000 |
| Addressing proportion@5 | 0.6250 | 0.6250 |
| Verdict accuracy | 0.5000 | 0.6500 |
| easy verdict accuracy | 0.6667 | 0.8333 |
| medium verdict accuracy | 0.5714 | 0.7143 |
| difficult verdict accuracy | 0.2857 | 0.4286 |

Raw labels mean LocalNLI output after its existing 0.65 confidence floor. Effective pair labels additionally use the production eligibility gate, without decomposition or retrieval. Full verdict tests use both.

## Confusion matrices
Rows are expected, columns predicted.

baseline nli; order: support, contradict, neutral
```json
[[51, 5, 10], [1, 19, 0], [6, 9, 5]]
```

baseline verdicts; order: SUPPORTED, UNSUPPORTED, MIXED_EVIDENCE, INSUFFICIENT_EVIDENCE
```json
[[2, 3, 0, 0], [1, 4, 0, 0], [1, 3, 1, 0], [2, 0, 0, 3]]
```

final nli; order: support, contradict, neutral
```json
[[60, 0, 6], [0, 19, 1], [4, 5, 11]]
```

final verdicts; order: SUPPORTED, UNSUPPORTED, MIXED_EVIDENCE, INSUFFICIENT_EVIDENCE
```json
[[3, 0, 1, 1], [0, 2, 0, 3], [1, 0, 4, 0], [1, 0, 0, 4]]
```
