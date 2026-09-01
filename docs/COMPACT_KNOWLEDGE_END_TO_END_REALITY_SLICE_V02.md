# Compact Knowledge end-to-end reality slice v0.2

This bounded slice proves the path:

`governed evidence → Luna Compact v0.2 → deterministic adapter → persisted governed Observations`

The three reused subjects were Life Without Barriers, Australian Conservation
Foundation and Australian Red Cross Society. No source acquisition occurred.
Each used one fresh Compact v0.2 task, Luna with `reasoning=none`, a 7,000-token
ceiling, one physical request and no retry.

| Subject | Input | Output | Atoms | Candidate Observations | New scopes | Cost (USD) |
|---|---:|---:|---:|---:|---:|---:|
| Life Without Barriers | 14,511 | 1,223 | 12 | 12 | 0 | 0.004370 |
| Australian Conservation Foundation | 20,700 | 1,076 | 11 | 11 | 2 | 0.005431 |
| Australian Red Cross Society | 36,183 | 2,172 | 21 | 21 | 7 | 0.009843 |

All three responses were JSON/schema-valid and their packet-local evidence
references resolved to durable evidence locator records. Observation lineage
contains deterministic `derived_from` edges to the model-result and task
identities. No Assertions, taxonomy assignments, relationship normalization or
publication occurred.

Temporal shapes observed in the real outputs:

- `effective_from`: 15 atoms;
- `effective_to`: 0 atoms (no bounded end date was evidenced in these packets);
- `reporting_period`: 11 atoms;
- all temporal fields null: 21 atoms.

Malformed temporal strings were rejected by the adapter in synthetic tests; no
semantic repair was applied. A local replay using the original observation
timestamps produced no duplicate scopes or observations and preserved stable
lineage/IDs. Total provider cost was USD 0.019644 across three calls. Raw
responses remain private under `C:\CharityGraph-runtime\compact-e2e-v02`.

The existing durable primitives represented every valid atom; no durable
representation gap emerged. The distinction remains explicit: a valid governed
Observation is not automatically a promoted factual Assertion.
