# M03/M04 — predecessor product and retrieval audit

Consumed: `charitygraph/scripts/run_megarun8b_direct_semantic.py`, its generated `PRODUCT_QA_EVALUATION.json` and `RETRIEVAL_PRODUCT_STRESS.json` in the run-8 runtime root, and the direct M01 source checks.

M03: Ten generated Q&A rows were inspected across the four literal question stems (“What does it report…”, “scope…”, “evidence…”, “what should not be inferred…”). Each interpolates a known hard-coded claim and always writes `grounded:true`, `unsupported_overclaim:false`, and a locator. None tests an answer selected from a natural donor question. The false-confidence safeguards are therefore unexercised. Terminal: PASS (forensic audit completed; output quarantined).

M04: Ten retrieval rows were inspected. Each intent is mechanically “find {semantic area} evidence for {subject}”, filtered to that known subject and source role, and its expected hit is assigned by `props[:80]`. This is metadata lookup of a seeded known answer, not retrieval difficulty. It cannot establish synonym, temporal, scope, negative, or distractor performance. Terminal: PASS (forensic audit completed; output quarantined).

Defect/counterexample: an exact SHA/page drill-down can prove lineage after a hit, but it does not prove discovery quality or product groundedness before the hit. Later modules remain independent.
