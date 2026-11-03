# Discovery-contract input sufficiency analysis

The existing v1.4 execution seam requires a concrete proposition, typed demand requirements, operation/joins, scope, temporal requirement, and evidence obligation. A discovery question instead has an answer variable whose value is to be discovered. It cannot be made executable by recasting that output as a user input.

The authorised v2 fixture package verifies the product-level count of 17 discovery-contract gaps, but does not provide a per-template list, semantic signatures, request-operation mapping, answer-variable schema, scope/temporal requirements, or evidence obligations for those 17 templates. The final 36-entry manifest carries only template identities and hashes. Four successor natural-language templates are present, but they cannot establish the semantics of the remaining gaps.

Accordingly, a v1.5 lowering implementation would have to invent operations or answer variables for unprovided template semantics. That would violate losslessness and the sealed-holdout boundary.
