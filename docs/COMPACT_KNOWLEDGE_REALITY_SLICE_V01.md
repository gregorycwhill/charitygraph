# Compact knowledge production reality slice v0.1

This experiment tests a card-blind provider boundary over one modest,
source-coherent shard for each of three existing subjects. The wire contract is
`CompactKnowledgeOutput { atoms[] }`. Each atom contains only a concise
proposition, scope kind/label, temporal kind/value, epistemic status,
packet-local evidence locators and qualifications. Every atom requires at least
one supporting locator. North-Star section IDs, section assessments, card
completeness, taxonomies, cross-source synthesis and durable opaque IDs are
downstream or Builder-owned and are absent from the provider contract.

The initial high-effort calls completed HTTP execution under standing Luna
authorization, with no retries, but their output ceilings were dominated by
reasoning tokens and all three were incomplete. A retrieval-only token audit
confirmed that confound. A controlled follow-up reused identical packet,
prompt and schema bytes with `reasoning=none`:

| Subject | Input | Output | Atoms | Cost (USD) |
|---|---:|---:|---:|---:|
| Australian Red Cross Society | 36,150 | 1,938 | 21 | 0.009556 |
| Life Without Barriers | 14,478 | 1,921 | 21 | 0.005201 |
| Australian Conservation Foundation | 20,667 | 1,364 | 14 | 0.005770 |

The controlled reasoning-free run completed and validated all three responses
(3/3), yielding 56 evidence-grounded atoms in total. Evidence locators resolved
against the unchanged packets. Total controlled cost was USD 0.020527. Raw
responses and usage metadata remain private under
`C:\CharityGraph-runtime\compact-knowledge-v01-none-lwb` and
`C:\CharityGraph-runtime\compact-knowledge-v01-none-acf-red`.

This is an execution result, not a semantic-quality judgement. The high-effort
failure was materially confounded by reasoning-token
consumption; the controlled result validates the compact card-blind production
boundary for this bounded three-subject experiment. `reasoning=none` is the
validated configuration for this experiment only, not a permanent policy for
all future semantic tasks. No durable representation gap was demonstrated.
