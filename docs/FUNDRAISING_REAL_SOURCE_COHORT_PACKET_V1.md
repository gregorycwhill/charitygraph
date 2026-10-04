# Fundraising real-source cohort packet v1

**Status:** Implemented local review-packet contract. **Version:** 1.0.

`FundraisingCohortPacket` is a non-acquiring validator for the next
independently identity-adjudicated, rights-cleared source-backed cohort. It is
not a source store, ingestion path, public contract, quality threshold or
release claim.

Each retained case requires source identity, role, locator, source-native
wording, cleared review-retention rights, identity adjudication and assertions
bound to that source. Every assertion retains a binding basis, scope,
production method, review state, coverage state and disposition. Finance
compatibility additionally requires entity, period and basis. A retained money
link requires same-source, exact-grain evidence.

The packet ledger reports case and assertion denominators separately, plus
retained/edited/rejected/refused dispositions and named error classes. It does
not emit a composite quality score, precision, recall, ROI, attribution or
derived finance value. An empty template is deliberately `not_processed`; a
fixture-only packet is rejected rather than being mistaken for external
evidence.
