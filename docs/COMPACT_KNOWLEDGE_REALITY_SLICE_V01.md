# Compact knowledge production reality slice v0.1

This experiment tests a card-blind provider boundary over one modest,
source-coherent shard for each of three existing subjects. The wire contract is
`CompactKnowledgeOutput { atoms[] }`. Each atom contains only a concise
proposition, scope kind/label, temporal kind/value, epistemic status,
packet-local evidence locators and qualifications. Every atom requires at least
one supporting locator. North-Star section IDs, section assessments, card
completeness, taxonomies, cross-source synthesis and durable opaque IDs are
downstream or Builder-owned and are absent from the provider contract.

The three preflighted calls completed HTTP execution under standing Luna
authorization, with no retries. Inputs/outputs/costs were:

| Subject | Input tokens | Output tokens | Cost (USD) | Valid JSON |
|---|---:|---:|---:|---|
| Australian Red Cross Society | 36,150 | 7,000 | 0.015630 | no |
| Life Without Barriers | 14,478 | 7,000 | 0.011296 | no |
| Australian Conservation Foundation | 20,667 | 7,000 | 0.012533 | no |

All three responses were marked incomplete and ended in unterminated JSON at
the output ceiling. Accordingly completion rate and mechanical-validity rate
were 0/3, no compact atoms were eligible for persistence, and no downstream
section projection was generated. Raw responses and usage metadata remain in
the private runtime under `C:\CharityGraph-runtime\compact-knowledge-v01`.

This is an execution result, not a semantic-quality judgement. It shows that
the selected 7,000-token ceiling remains insufficient for these high-recall
responses even after removing card-shaped fields. No durable representation gap
was demonstrated. The next decision is architectural review of output sizing
and/or compactness before further provider calls; no automatic tuning or retry
was performed here.
