# Fundraising method history v1

**Status:** Working Builder review contract. It is not a public schema, release
contract, source-acquisition path, or a currentness estimate.

`compile_fundraising_method_histories` turns repeated, already-governed method
observations into a scope-local sequence. It retains one event per evidence
record with source identity and role, locator, exact source wording, binding
and binding basis, observed and valid time, scope, production method, review
state, coverage, and coverage description.

The sequence can contain `current`, `recent`, `historical`, `discontinued`,
`unknown`, and `not_found_in_scoped_source`. `last_evidenced_at` is only the
latest confirmed positive observation; it has no expiry period and never means
the method remains current. An explicit cessation needs an explicit
`cessation_date`; it is retained alongside all earlier evidence and never
implies that a later restart is impossible.

The compiler does not resolve sources. A current/recent assertion dated on or
after an explicit cessation is emitted as a contradiction with
`review_required: true`. Unknown binding and scoped silence remain retained
events with `practice_observed: null`, rather than becoming positive or
negative practice claims. Events are partitioned by exact method and scope, so
organisation, campaign, program, and geography evidence cannot silently leak
across a boundary.

The fixture `tests/fixtures/fundraising_method_history_projection.json` records
the expected multi-period review projection: historical, recent, current and
cessation evidence; unknown and scoped silence; and a contradictory later
current assertion. It is review-only adversarial coverage, not a source-backed
cohort denominator or a public profile.
