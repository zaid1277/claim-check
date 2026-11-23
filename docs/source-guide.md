# Source guide

These files explain the main product and ML decisions without requiring a tour
of every route or component.

1. [Settings](../api/app/core/settings.py): configurable thresholds, limits and source weights.
2. [Pipeline](../api/app/services/pipeline.py): retrieval, classification and scoring order.
3. [Retrieval](../api/app/services/retrieval.py): explicit cosine mathematics, filtering and Top-K.
4. [NLI](../api/app/services/nli.py): premise/hypothesis order, labels and confidence handling.
5. [Evidence scoring](../api/app/services/evidence_scoring.py): directional totals and abstention.
6. [Search adapters](../api/app/services/search.py): Tavily/Brave normalization and safe provider errors.
7. [Provider selection](../api/app/services/provider_setup.py): server preference, fallback and runtime credentials.
8. [Report storage](../api/app/db/reports.py): persistence, retrieval and public sharing.
9. [Workbench](../web/components/workbench.tsx): input/review states and investigation requests.
10. [Verdict evaluation](../evaluation/run_verdicts.py): measured offline behavior and its limits.

URL fetching and setup endpoints contain the security boundaries.
The provider setup UI is in web/components/provider-gate.tsx; the extension has
no separate ML logic. See architecture.md and claim-check-explained.md for
long-form reasoning and known tradeoffs, and remediation-final-report.md /
accuracy-max-report.md / nli-upgrade-report.md / accuracy95-development-report.md
for the measured evidence behind them.
