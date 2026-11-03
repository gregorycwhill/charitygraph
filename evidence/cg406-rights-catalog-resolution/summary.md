# CG406 rights/catalog resolution — provider-free replay

Branch/commit: `gate3-cg406-remediation` / `50648cf94a230d929a2f4843f15d5c3ed5741387`.

This replay used only the frozen CG406 subject/demand manifests and already-acquired Phase-5 Source Universe v1 artefacts. It made zero provider calls and no source acquisitions, did not alter either frozen side, and leaves SDC-0019 as `CANDIDATE_SOURCE_GAP`.

The old provider-visible corpus had 24 ACNC records only. The replay reconstructs ordinary catalog/receipt/source-record lineage for all 30 admitted non-ACNC records and narrows 29 payloads under existing policy: 12 ABR/DGR and three PFRA source-native structured factual records, four bound Wikimedia search-result factual records, and ten bounded annual-report PDF excerpts. Those 29 records have exact representation-bound rights decisions. Provider-visible rows are now 53: ACNC Register 12, ACNC AIS 12, ABR/DGR 12, annual report 10, Wikimedia 4, PFRA 3.

One annual-report artefact is an XLSX workbook. Existing Fair Dealing V1 specifies the maximum bounded representation only for PDF pages; PUBLIC_FACTS_ONLY_V1 does not determine a source-native workbook subset. Its provider representation is therefore not constructed and is a genuine `TRUE_POLICY_GAP`, not a semantic finding, source-universe expansion request, or an acquisition failure.

The real frozen-experiment preparation lifecycle completed provider-free: 12 prepared, never-sent rows; prepared-run identity `ebb5a5776a1ca7c8cc56ea250effab6b37fb03e2343f78e426d9cbbf9b4a0f8f`; maximum USD `0.182657`, AUD `0.277645`.

Regression suite: 127 passed (`test_baseline_corpus`, `test_frozen_experiment`, `test_frozen_experiment_cli`, `test_phase5_execution_packet`, `test_phase5_execution_tickets`, `test_phase5_execution_mandate`, `test_phase6_semantic_contracts`, `test_source_rights`, `test_phase5_baseline_corpus`).
