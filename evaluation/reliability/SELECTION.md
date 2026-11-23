# Selection record, before opening held-out results

Selected cross-encoder/nli-deberta-v3-small using validation only: raw macro F1
0.8510 versus 0.8300 for MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli;
full updated pipeline verdict accuracy 9/10 versus 8/10. Original pipeline 5/10;
small-model-only pipeline 7/10. Small model has worse raw contradiction precision
(0.7143 versus 0.7692); the separate conservative gate is therefore important,
and its recall cost must be reported. Validation is only ten proposition groups.

Frozen operating points: existing similarity .35, NLI .65, source weights,
score product and aggregation .5/2 unchanged; contradiction eligibility .85,
explicit subject/predicate anchors, four-atom cap, .9 content Jaccard and
365-day current-evidence window. These are transparent heuristics, not calibrated
probabilities or guarantees. They were not selected against held-out results.

Final evaluation now runs the frozen 320/60/60 controlled corpus; test group
results must be reported even if worse. No further reasoning changes based on
that set. A release gate requires improved raw NLI macro F1 and verdict accuracy,
non-increasing gated false contradiction rate, and non-decreasing gated
contradiction precision relative to baseline. Passing is evidence on this small
controlled corpus, not evidence of general real-web accuracy.
