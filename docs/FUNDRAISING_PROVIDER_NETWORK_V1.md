# Fundraising provider/platform network v1

**Status:** Working Builder review contract. It is neither source acquisition,
production ingestion, a public schema nor a claim that a charity has a
standing fundraising practice.

`compile_provider_network` retains a directed charity-to-agency or
charity-to-platform relationship only from already-governed structured
evidence. Every record preserves source identity/role, locator and wording,
charity and provider binding bases, observed time, explicit relationship scope,
lifecycle, coverage and review status. The compiler performs no name matching,
prose classification, recency rule or provider-to-practice inference.

Only a reviewed, observed assertion with confirmed charity binding and a
resolved durable provider subject can produce
`candidate_evidence_discovery`. That disposition only authorises a candidate
locator for later evidence review. It cannot create a practice, campaign,
currentness, setting, compensation, regular-giving or finance observation.

Ambiguous, candidate and unresolved provider identities remain explicit review
records with no provider subject ID and `do_not_seed`. An ended relationship
requires an explicit end date and remains `review_only`; former provider use
cannot seed current discovery. Duplicate assertions are retained rather than
merged, so contradictory or multi-period evidence remains inspectable.

The fixture cohort includes a resolved agency, a resolved platform, ambiguous
identity, an ended former provider and an unreviewed relationship. It is an
adversarial review fixture, not a source-backed denominator or a population
claim.
