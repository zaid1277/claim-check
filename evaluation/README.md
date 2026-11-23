# Evaluation

This directory holds every measurement generation this project ran, in
chronological order. Each subdirectory is a self-contained harness: its own
corpus, its own scripts, and its own frozen results, used to produce one of
the reports in `../docs/`. Numbers here are real saved outputs from real
local models, not a public benchmark and not a claim of live-web accuracy —
see the "Evaluation" section of the root `README.md` and each generation's
report for exactly what was measured and what it does and doesn't establish.

| Directory | Report | What it measured |
| --- | --- | --- |
| `reliability/` | superseded by `../docs/final-reliability-report.md` | First frozen holdout, original DistilBERT-era pipeline |
| `pass2/` | superseded by `../docs/final-reliability-report.md` | Interim pass after switching to a DeBERTa MNLI/FEVER/ANLI NLI model |
| `final/` | `../docs/final-reliability-report.md` | The locked "Groups 1-3" run this report is drawn from: cross-encoder evidence eligibility, threshold tuning, and the final combined holdout |
| `hyper/` | `../docs/hyper-final-reliability-report.md` | Independent "Group 4" holdout — the first to genuinely stress-test generalization |
| `remediation/` | `../docs/remediation-final-report.md` | Targeted fixes for contradiction generalization, coverage, URL ingestion and OCR, re-measured on a new confirmation holdout |
| `accuracy-max/` | `../docs/accuracy-max-report.md` | Diagnostic-only pass separating aggregation cost from verifier-capability cost (no production changes) |
| `nli-upgrade/` | `../docs/nli-upgrade-report.md` | LoRA fine-tuning experiment on a from-scratch NLI corpus (not adopted; see report) |
| `accuracy95/` | `../docs/accuracy95-development-report.md` | Feasibility study for a 95%-accuracy target, including an evidence-grounded LLM verifier experiment (not adopted; see report) |
| `results/`, `run_*.py`, `nli.json`, `retrieval.json`, `verdicts.json` | — | The original small authored smoke-test harness, predating the generations above |

Every later generation was measured **diagnostically against its own new,
independently-built data** — never re-tuned against an earlier generation's
frozen holdout. That discipline (and the occasional honest "this did not
generalize") is the throughline across these reports; read them in order to
see the project's actual development history, not just its current state.

To reproduce any generation's numbers, see that subdirectory's own README or
report for its exact run commands — each has its own lock file and result
set, and most take real time and, for live-search phases, a configured
search-provider key to re-run.
