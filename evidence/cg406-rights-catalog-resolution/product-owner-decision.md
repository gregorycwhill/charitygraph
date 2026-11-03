# Product Owner decision: source-native workbook bounded representation

Question: may a retained annual-report XLSX workbook be transmitted as a narrowly bounded, source-native structured factual representation for private provider analysis?

Existing policy is insufficient: Fair Dealing V1 sets a deterministic bound for PDF reports (no more than five selected pages and no more than 20% of the document) but does not define the comparable unit or maximum for workbooks. PUBLIC_FACTS_ONLY_V1 requires a structured factual representation, but does not specify whether a selected workbook sheet/range is an admissible one-record representation.

Security, copyright, and provenance: the artefact was already acquired through a governed public ACNC filing flow; the proposed payload must retain source-artifact, source-record, receipt, sheet/range and exact-representation hashes. A whole workbook must remain prohibited pending a decision.

ALLOW consequence: define an explicit versioned maximum sheet/range boundary and required provenance/attribution fields; the one blocked CG406 row can be represented without acquisition or semantic inference. DENY consequence: the workbook remains provider-ineligible while all other rows remain usable. Recommended default: deny whole-workbook transmission and permit only a later, explicit bounded-sheet/range policy. A narrower representation could avoid a broader authorization once that policy exists.
