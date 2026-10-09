# CG353 unified semantic experiment contract

Status: private frozen measurement contract. No provider request is authorised by this document.

The real existing general semantic boundary is `compact_knowledge.py`'s
`CompactKnowledgeOutputV02` / `COMPACT_V02_SCHEMA`, used by the Compact v0.2
Luna Responses execution path. §15/§17's existing provider-shaped boundary is
`ethos_notability_extraction.py`'s `OpenAIResponsesExtractionProvider`,
`ethos-notability-extraction-v1`, and its candidate-only `CandidateBundle`.

Arms consume the same frozen retained-source packet for each case:

* A — current Compact Knowledge general extraction.
* B — dedicated §15 Ethos + §17 Notable History extraction through the existing provider adapter.
* C — one general extraction whose strict output is `UnifiedSemanticOutput`: `general` Compact v0.2 output plus an independently typed `ethos_notability` candidate bundle.

The immutable CG352 cohort is the cohort manifest hash bound by the corpus:
10 challenge/workshop cases and 5 deterministic blind controls. Harness access
returns challenge cases only unless the final-holdout switch is set. No blind
outputs may be read during tuning.

Before any measurement, the harness freezes hashes for the cohort, evidence
corpus, baseline identities, unified schema and metric list. The metric list is:
supported precision/recall where evaluable; unsupported positives; scope
transfer; current/historical confusion; source-role and temporal error;
qualification loss; §16/17 leakage; event dedupe/lineage errors;
missingness/abstention; provenance defects; malformed/reject rate; review
burden proxy; input/output tokens; calls; and USD/organisation. Review labels
are supplied externally; scoring performs no prose interpretation.

All future live work must use the OpenAI Responses provider with `gpt-5.6-luna`,
append the common cumulative ledger after each response, and call the mechanical
cap check before each request. This task made zero provider calls and recorded
no smoke. The smoke ceiling remains US$0.05; campaign cap remains US$2.00.
