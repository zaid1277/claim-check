# Data provenance and limits

ANLI: Facebook/Meta and collaborators, Adversarial NLI. Public Hugging Face
`facebook/anli`, dev_r1/dev_r2/dev_r3, offsets recorded in anli-provenance.json.
The 600 selected pairs exclude every premise in the earlier downloaded 600-row
pool and earlier list-format pair benchmarks. Unique normalized premise AND claim
hashes prevent variants crossing the new splits. ANLI dev is not the authors'
unseen test set; the deployed model was trained on ANLI training data. This is
new to this project's tuning, not a claim of pretraining contamination immunity.

SciFact: David Wadden et al., *Fact or Fiction: Verifying Scientific Claims*,
Allen Institute for AI, https://github.com/allenai/scifact. Original human-labelled
claims_dev.jsonl and corpus.jsonl are preserved. Claims/evidence annotations are
CC BY 4.0; abstracts are S2ORC, ODC-By 1.0. See SCIFACT-LICENSE.md.
Download: https://scifact.s3-us-west-2.amazonaws.com/release/latest/data.tar.gz
SHA256: 11c621288d41ac144d29b13b0f8503b3820b7d6e8b1f6ff24dff335c196d76be.
Fifty document-disjoint claims are selected by hash and label quotas, not model
predictions. Citation abstracts are supplied as controlled search results. This
measures verification over supplied documents, not discovery across the full
SciFact corpus. No inferred labels are applied to the unlabelled SciFact test set.

Authored evidence: facts.tsv contains 100 factual claims with contrasting claims.
These are controlled summaries written for testing, NOT quotes from the fixture
URLs. The 25 hard scenarios include fictional conflict/absence probes; they are
not represented as independently verified real events. Gold verdicts concern the
supplied evidence. The 48 pair probes use hypothetical premises to isolate NLI
relations and text corruption across 16 domains. They are not factual assertions
about real organizations. Author review is not independent human annotation.

Difficulty is assigned before inference. Forty easy cases have direct positive
or negative evidence. Sixty medium cases include distractors or missing retrieval;
this label describes a constructed stratum, not an independently calibrated human
difficulty rating. Fifty expert SciFact claims and 25 authored stress cases are
hard. Results must be stratified by origin: an overall average cannot establish
real-web truth accuracy. The empty-source controls are explicit retrieval outages,
not evidence that their underlying claims are false.

OCR source images are browser-rendered from exact transcripts. Twenty fonts,
layout/theme/compression variants do not establish performance on arbitrary user
screenshots. Corrected-text investigations and raw OCR errors are separate metrics.

Mined hard neutrals: eight reviewed passages from 30 actual high-ranking Tavily
retrieval candidates; three development queries. Labels are passage-local and do
not use external facts to infer a missing claim relation. They remain development
material and cannot inflate the final holdout denominator. Full candidate text and
URLs are retained for reproducibility; no source independence is implied by chunks.
