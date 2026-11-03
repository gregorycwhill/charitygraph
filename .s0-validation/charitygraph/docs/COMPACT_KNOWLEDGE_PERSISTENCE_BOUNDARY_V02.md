# Compact Knowledge Persistence Boundary v0.2

The provider contract is now card-blind and temporally deterministic. Each
`CompactAtomV02` contains a proposition, explicit scope kind/label,
`effective_from`, `effective_to`, and `reporting_period` (all provider-owned
temporal fields may be null), epistemic status, packet-local evidence locators,
and qualifications. `observed_at` is injected by Builder. No North-Star section,
taxonomy, card completeness, or durable opaque identifier is provider-owned.

The persistence adapter deterministically:

1. resolves `subject` scope to the registered subject and creates/reuses a
   `ScopeRecord` for named-program/service and other supported non-subject scopes;
2. converts each atom into a candidate `Observation` with predicate
   `compact_statement` and preserves supported versus explicit-absence in the
   observation value;
3. maps packet locators to existing evidence locator IDs and source records;
4. constructs existing `ObservationTime` from strict ISO dates/reporting period
   plus Builder-owned `observed_at`;
5. preserves qualifications and deterministic `derived_from` lineage to the
   model result and task.

Assertions, promotion, adjudication, taxonomy assignment, relationship
normalisation and publication remain downstream. Replaying the same task/result
and atom yields the same scope and observation IDs.

The reviewed v0.1 sample remains historical calibration material. Its awkward
ACF absence proposition and the less cautious LWB financial wording are not
patched by English rules: mechanically valid model observations are not
automatically promoted factual assertions.
