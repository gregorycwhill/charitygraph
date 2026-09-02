# Offline consolidation and v4 preflight (2026-09-02)

This note records the bounded, provider-free consolidation performed after the
September broad Compact diagnostic campaigns. It is diagnostic evidence, not a
release, assertion set, or semantic-quality claim.

## Recovered campaigns

The persisted raw responses were re-read in independent stages: provider
completion, response extraction, Compact v0.2 JSON/schema, temporal validation,
evidence-reference validation, and adaptation/persistence. Parseable atoms are
retained even when a later stage is unavailable. The v2 campaign recovers 378
atoms; v3 recovers 404 atoms. The v3 aggregate's repeated `KeyError: 'source'`
was a diagnostic-harness defect, not a provider schema failure. Historical v2
packets have no persisted locator namespace and both campaigns therefore retain
`unavailable_historical_packet` evidence status rather than inventing mappings.

## Packet-size diagnosis

Across the 30 matched identities, v2 packets total 682,382 bytes (median
21,155); v3 totals 1,960,780 bytes (median 55,517). The measured expansion is
the repeated packet-local locator arrays (18,222 line locators in v3) and their
text, not increased source-family coverage. Future packets should preserve
source/locator maps as deterministic review artefacts while sending only the
semantic material required for interpretation.

## Generic boundary clarifications

- Exact calendar dates are `YYYY-MM-DD`; coarser periods remain
  `reporting_period`, without manufactured precision.
- `explicit_absence` is reserved for evidenced absence/none/zero. “Pending”,
  “not yet submitted” and future due states remain ordinary supported status.
- `reporting_group` is an evidenced consolidation scope. A named fund, trust,
  legal vehicle or organisational unit is not silently treated as a
  `named_program_or_service`.
- Source-native relationship strength is retained; beneficiary, DGR listing,
  or classification labels are not upgraded into delivery/operation claims.
- A nearby year does not establish the temporal association of a financial
  value unless the source structure does so.

Explicit structured regulatory fields remain on the deterministic source-native
path (identifiers/status, registration, size, purposes/subtypes, DGR/tax status,
locations, filing status, workforce, financial/KMP/related-party/fundraising
fields and explicit program/beneficiary records where structurally supplied).
Prose requiring interpretation remains Compact semantic work. No assertions or
publication are produced by this diagnostic tranche.

## v4 preflight

`C:\CharityGraph-runtime\broad-compact-diagnostic-v4-preflight\campaign-preflight.json`
contains 35 existing, prose-rich candidate packets across official websites,
Wikipedia/Wikimedia and PFRA material. Structured ACNC/ATO families are
excluded from the future semantic workload. Each candidate records subject,
source family, source lineage, deterministic material identity and the reason
Luna would be required. This is preflight only; provider calls: 0.

Private recovered atoms and stage diagnostics remain under the runtime campaign
directories. No private evidence is committed here.
