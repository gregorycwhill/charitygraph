# Fundraising identity binding v1

Status: local, review-only identity precondition for fundraising evidence. This does not acquire sources, create subjects, promote a practice observation, or alter a public projection.

`fundraising_identity_binding` resolves a candidate only when the source adapter has retained a source-record ID and one of these authority-backed facts yields exactly one governed subject:

- an exact 11-digit ABN;
- an explicit relationship naming the durable subject ID; or
- a source fact that a domain is subject-controlled, followed by an exact match to one governed canonical domain.

The output always retains the evidence ID, selected subject (only when confirmed), basis, candidate set and a refusal reason. An exact name, a domain without the control fact, no identifier, or multiple exact candidates remains `unresolved` or `ambiguous`. Names are retained as source-native context but never participate in resolution.

This boundary deliberately keeps a shared domain, duplicated ABN, parent/subsidiary ambiguity, provider/client ambiguity, and any source without a stable authority-backed fact out of fundraising promotion. Callers must pass its result to the existing evidence-role gate; only `confirmed` can meet that gate's binding precondition. Counts must continue to report `confirmed`, `ambiguous` and `unresolved` separately.
