# Controlled reliability evaluation

Read [the final reliability report](../../docs/final-reliability-report.md) before
citing scores — this generation's own write-up was superseded by that report.
Data are authored, including fictional/counterfactual propositions. Labels express
relations between supplied text, not independent fact checks. No live source
reputation or web retrieval recall is measured by these files.

`build_data.py` constructs 320 NLI pairs, 60 candidate retrieval tasks and 60
verdict cases from propositions.tsv. Group split keeps all variants together:
30 development, 10 validation and 20 test groups. Frozen hashes are in manifest.json;
regression tests verify them. Do not rebuild/relabel data after inspecting errors.
`SELECTION.md` records the model/operating policy fixed before opening test metrics.

`run.py` uses real local models. NLI evaluates raw and gated labels separately;
retrieval ranks the supplied candidate corpus; verdict evaluation replaces only
source collection, then calls the real pipeline. It does not benchmark Tavily,
HTTP extraction, persistence or UI latency. Those have separate integration tests.
`report.py` writes the exhaustive error CSV, held-out metrics and relative gate.
`runtime.py` measures one warmed candidate per process on validation text.

For baseline reproduction extract baseline-app.tar.gz into a temporary directory
and set PYTHONPATH to that directory before calling run.py with the old model.
The runner recognizes the baseline's absent eligibility gate and reports raw
labels for both pair fields. Use a new output path; do not overwrite baseline.json.
Install the current environment dependencies first; the archive contains source,
not an environment lock. The original baseline RSS/latency remains the frozen
pre-change measurement and is not guaranteed across machines or library versions.

All errors must remain visible. Do not tune against the now-disclosed test set.
A new reasoning iteration needs new untouched evaluation groups.
