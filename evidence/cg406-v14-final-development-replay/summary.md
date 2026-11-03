# CG406 v1.4 final development replay

Status: `READY_FOR_SOL_CG406_FINAL_DEVELOPMENT_ADJUDICATION`. This is a
development handoff, not a Gate-3 closure recommendation or independent
semantic adjudication. Record `CG406_DEVELOPMENT_COHORT_CLOSED_FOR_TUNING`;
future quality work uses a fresh independent holdout and requires a new
Product Owner decision.

Repository: branch `gate3-cg406-remediation`, HEAD
`6daf2a10d495a933cb56a49f2e87b974e664c879`. Frozen subject and demand SHA-256
identities match the expected values. Contract 1.4 and schema
`1.4-provenance-claim-separation` were used in 12 prepared Standard requests
bound to the approved existing project and `gpt-5.6-luna` at low reasoning,
concurrency 1, no semantic/automatic retries. Prepared-run hash:
`da77187aa3fff0d59ef8931958f68b9bea7e88a716d0657dfc4a7c30ce8b5925`.

Greg supplied trusted direct authorization in conversation. The platform
execution proceeded with exactly 12 provider posts and 12 completed, valid
transport parses; no ambiguous crossings or retries occurred. Maximum bound
was USD 0.182657 / AUD 0.277645; actual was USD 0.141008 / AUD 0.214338.
With prior reconciled actual AUD 0.510035, cumulative actual is AUD 0.724373,
under the AUD 1.00 ceiling. Deterministic resume replayed all 12 terminal rows
with zero provider posts and no additional response files.

The immutable result manifest has embedded identity
`9f8ae0fe0ff7841b9c1095677b0e7a4326eda7eed4f3f44d152193cd79eed0dd` and file
SHA-256 `D578510A774C18903350724597618AD0D7326EEA81213C278E088C29499BF3D6`.
Its terminal ledger SHA-256 is
`587FE13FEDA16CA8704357775540CDCE5A32FBD0060C51A408527F548D343999`.
Validation and row-level comparison are supplemental post-freeze artifacts;
the frozen result manifest is not edited to add analysis fields.

All seven admitted Source Universe v1 families were represented across the
63 provider-visible evidence records: ACNC register 12 records / 12 requests;
ACNC AIS bundle 12/12; ATO ABR/DGR 12/12; annual reports 11/11; official
websites 9/9; PFRA 3/3; Wikipedia/Wikimedia 4/4. Each row's packet,
selection, rejection, claim/requirement state, source record, role, family,
native locator, and payload hash are in the Sol handoff.

Raw outcomes were unchanged from v1.3: 11 `insufficient_evidence`, 1
`supported`. Mechanical validation was 6 valid / 6 invalid in both versions,
but six rows changed validity: Cancer Council Victoria, UWA and Plan moved to
valid; Amnesty, Caritas and SDC-0019 moved to invalid. The single raw
`supported` response (Cancer Council Victoria) is mechanically valid, not a
semantic adjudication. Invalid v1.4 patterns are four uses of `guarded` on
non-inference-ineligible requirements and two proposition supports marked
strong while scope/time is unresolved. Good Friday Appeal remains insufficient
and invalid because the model did not carry the ABR historical effective date
through to the identity proposition, despite the contract's binding rule.
See `targeted-diagnostics.md` and `validation-results.json`.

SDC-0019 remains `CANDIDATE_SOURCE_GAP`; Source Universe v1 was not changed.
No source acquisition, promotion, projection, release, push, or merge occurred.
The frozen v1.3 outputs and independent oracle were not modified. Oracle
content was not semantically accessed; its two frozen identities were checked
by SHA-256 only, after the v1.4 terminal manifest was frozen. The known 15 S0 test failures still trace to absent
`C:\CharityGraph-clean\.s0-policy-data` fixtures; the focused CG406 suite
passes 47 tests. No validation was weakened.

Process-integrity disclosure: while checking the established artifact shape,
a v1.3 result-manifest excerpt and the first lines of its terminal ledger were
read before the v1.4 result manifest was frozen. No v1.4 response was inspected
before that freeze, and no oracle content was opened or interpreted. This
sequence deviation is disclosed for Sol; it does not affect first-response
preservation or the frozen v1.4 response hashes, but the timing is part of this
record.
