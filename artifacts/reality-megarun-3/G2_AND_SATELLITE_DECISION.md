# G2 proposition and satellite decision

## Decision

Adopt the following as the leading canonical design hypothesis, at high confidence for preservation and display safety, medium confidence for full schema shape: an atomic attributed G2 proposition is the durable core; satellites carry semantics that would otherwise be lost.

Required satellites for this evidence class: `subject`, `predicate`, `value/measurement`, `evidence_locator`, `source_role`, `valid_at`, `reporting_scope`, `production_method`, `review_state`, `coverage/missingness`, `comparison_classification`, and an explicit reviewed `supersedes_display_slot` link. Keep correction/adjudication and projection-contract version alongside them where applicable.

## Non-decisions

Coverage/missingness is not a proposition value. Routing is not semantic inference and does not own raw truth. A first-party candidate is not a promoted observation. Neither a source-role difference nor a scoped difference authorises overwriting.

## Counterevidence

No true correction or temporal supersession was observed, so `supersedes_display_slot` is reasoned from safety requirements rather than empirically validated. The sample has no relationship, program, evaluation, adverse, or complex multi-endpoint evidence; those may require additional satellites or companion records.
