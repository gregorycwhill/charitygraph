# Gate 3 v1.5.1 provider interface implementation

Status: provider-free implementation complete; fresh-36 execution blocked by a frozen subject-binding mismatch.

The new generic interface is `charitygraph.generic-discovery-provider/v1.5.1`. It consumes a compiled v1.5 contract and exact packet evidence IDs, creates a strict provider JSON Schema with enum-bound answer variables, states, record evidence references, and exhaustiveness evidence references, renders a generic prompt from the frozen question/contract/identity/evidence, and validates outputs against the same exact packet ID set. Unknown v1.5 answer-variable types/cardinality remain textual and unspecified; the implementation does not infer them. Partial results require evidence-backed records and explicit qualification. A negative conclusion requires explicit exhaustive state and in-packet exhaustiveness evidence.

The implementation is explicitly post-sample-selection. Original question, subject-selection, and candidate packet artifacts remain unchanged.

## Verification

- Synthetic implementation and contract regression tests: 49 passed.
- Frozen selected-subject manifest SHA-256: `41b4ce5f1c39afd31a28b1f819d2a9759c89880eb0ddb2d2b143662cf4dda7a9` (raw file SHA-256).
- Existing frozen candidate packet manifest SHA-256: `bc321f06a5873997562828fda0b689995a101ab56e9848b6e4dbbbfb4b4f60db` (raw file SHA-256).
- Both contain 36 rows, but their ABN sets have 0 intersections. The request compiler now fails closed on this mismatch.
- No rights decisions could be validly issued for the requested selected cohort from these mismatched packets; rights decisions and rights-admitted evidence count for the selected cohort: 0.
- A preliminary output generated before the cohort guard was added is quarantined at `C:\CharityGraph-runtime\g3fresh36-provider-free-corpus-v1\g3fresh36-semantic-execution-v1.5.1`. Its 36 request rows had zero evidence, zero rights decisions, and zero source-family coverage. Plan hash `26302d9b671425c313425290530a9d6987b0687f6066127c117d4ed38f92c25f`; do not use it, authorize it, or execute it.
- The quarantined diagnostic forecast was US$0.371159; it is not a forecast for the intended cohort.
- Provider requests: 0. Valid outputs: 0. Retries: 0. Actual expenditure: US$0.00. Oracle accesses: 0. Source acquisitions: 0.

## Exact blocker

Provide or designate the immutable 36-row execution-instance manifest that binds the 36 selected subjects in the manifest above to the 36 frozen question identities/demand definitions. The current frozen provider-free packet manifest binds a disjoint subject set. The Builder must not modify either side or select replacements. Once the correct bound manifest is available, the new compiler can create exact rights assessments and request bodies, then the exact plan can be submitted to the trusted run-bound authorization flow.
