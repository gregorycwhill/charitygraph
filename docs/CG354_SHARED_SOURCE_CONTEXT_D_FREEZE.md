# CG354 D: shared source-oriented context

Status: execution design and workshop gate.  This is private experimental
material. It does not promote candidates or alter a public contract.

D is one Luna `openai.responses` call per organisation.  It receives a single
registry whose selected retained representations are keyed by immutable
representation hash and emitted once.  The registry retains every source ID,
source record, locator, source role, scope/time provenance and each section
binding; it does not concatenate A and B packets.

The mechanical pre-send validator rejects changed bytes, ambiguous identity,
duplicate IDs, duplicate representation hashes and registry hash changes.
The model must return the existing typed Compact Knowledge and separate
Ethos/Notability candidate families. Python does not interpret language.

Workshop-only procedure: run EEN-01..EEN-10 once with
`cg354-shared-source-context-v1`; at most one general prompt/schema revision
may follow. The five original blind cases must not be materialised, requested,
or inspected until this document's final identities and gates are frozen.

Blind gate, frozen before opening: no new dangerous error; evaluable precision
no worse than the comparator by 3 percentage points; recall no worse by 5;
100% accepted-fact provenance binding; and at least 20% fewer input tokens
than A+B (preferably 15% below C). If the experimental reference makes a
metric non-evaluable, record that fact and do not infer a pass.
