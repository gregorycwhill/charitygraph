# Fundraising evidence resolution v1

**Status:** local, review-only evidence presentation contract. It does not alter a card, acquire sources, or publish a population claim.

`fundraising_evidence_resolution` receives already extracted, subject-confirmed source assertions. An exact repeated extraction (same subject, typed fact/value, source identity, locator, wording, scope and valid-time) is one canonical claim for coverage counting; every original claim and evidence ID remains in its duplicate group. The same asserted value from different source identities is corroboration, never a discarded duplicate.

Different scope or valid-time windows are displayed as scope-distinct or temporal-successor observations, rather than manufactured conflicts. A same-subject, same-fact, same-scope and same-valid-time disagreement remains inspectable with all values and source lineages. The resolver names a preferred claim only when all inputs are reviewed and a strict source-role precedence is unique: first-party practice/campaign page, then annual report, then agency/platform case evidence. Equal, unsupported, unreviewed, unknown-time, or differently scoped claims never receive a winner.

Money values must arrive with an already governed semantic key that includes the relevant measurement identity. This resolver neither parses amount wording, converts accounting bases, adds values, nor attributes organisation-level finance to practices, campaigns or providers.
